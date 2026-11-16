#!/usr/bin/env python3
"""Produce final comparison, documented scope, and append-only lane delivery freeze."""
from pathlib import Path
import hashlib,json,subprocess,datetime
ROOT=Path(__file__).resolve().parents[3];B=ROOT/'build/driver-pvt-20261117/b';E=ROOT/'evidence/driver-pvt-20261117/b';A=ROOT/'docs/research/driver-pvt-20261117/assets'
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def load(p):return json.loads(p.read_text())
def result(p):
 r=load(p/'result.json');return {'case':str(p.relative_to(ROOT)),'result_sha256':sha(p/'result.json'),'manifest_sha256':sha(p/'manifest.json'),'raw_sha256':r.get('raw_sha256'),'gzip_sha256':r.get('gzip_sha256')},r
oldref,old=result(ROOT/'build/driver-interface-20261115/MicroLED/B-protected_v6r/continuous-f4-net1.6-s40')
newref,new=result(B/'clamp5v_buffer_soft/tt-normal1-s40');ssref,ss=result(B/'clamp5v_buffer_soft/ss_hot_low-full-s40')
f0=old['frames'][0];f1=new['frames'][0]
def metrics(f):return {'energy_pJ_per_attempted_payload_bit':f['energy_pJ_per_attempted_payload_bit'],'receiver':f['full_receiver'],'source_energy_J':f['source_energy_J'],'explicit_storage_caps':f['explicit_storage_caps']}
delay0=load(E/'gate-delay-before.json');delay1=load(E/'gate-delay-TT-after.json')
short=[]
for mode in ['assert','release']:
 ar,a=result(B/f'clamp5v_buffer_soft/ss_hot_low-{mode}-s40');br,b=result(B/f'clamp5v_buffer_soft/ss_hot_low-{mode}-s80')
 da=(B/f'clamp5v_buffer_soft/ss_hot_low-{mode}-s40/testbench.spice').read_text().splitlines();db=(B/f'clamp5v_buffer_soft/ss_hot_low-{mode}-s80/testbench.spice').read_text().splitlines()
 diffs=[{'s40':x,'s80':y} for x,y in zip(da[1:],db[1:]) if x!=y];assert len(da)==len(db) and len(diffs)==1 and all(diffs[0][k].startswith('tran ') for k in ['s40','s80']),diffs
 x={'mode':mode,'s40':ar,'s80':br,'only_electrical_deck_difference':diffs,'non_electrical_title_change':[da[0],db[0]],'s40_terminal_pass':a['terminal_pass'],'s80_terminal_pass':b['terminal_pass'],'s40_body_V':a['body_forward_V'],'s80_body_V':b['body_forward_V'],'body_delta_mV':(b['body_forward_V']-a['body_forward_V'])*1e3,'scope':'Short diagnostic numerical edge comparison only; not full protocol finer-step validation.'}
 if mode=='assert':
  for k in ['max_abs_current_uA','last_above_threshold_ns']:x[k]={'s40':a['shutdown'][k],'s80':b['shutdown'][k],'delta':b['shutdown'][k]-a['shutdown'][k]}
 short.append(x)
out={'schema':'b-pvt-final-comparison-v1','status':'frozen','nominal_comparison':{'scope':'Same TT27 rails/load/receiver/pattern, first2.56us frame from initial OP. No continuous-state or thermal steady-state claim. Old frame1 of4 vs new frame1 of1.','before':oldref|metrics(f0),'after':newref|metrics(f1),'positive_energy_change_percent':100*(f1['energy_pJ_per_attempted_payload_bit']['positive']/f0['energy_pJ_per_attempted_payload_bit']['positive']-1),'amplitude_delta_uAeq':f1['full_receiver']['worst_signed_margin_uAeq']-f0['full_receiver']['worst_signed_margin_uAeq'],'timing_delta_ps':f1['full_receiver']['one_sided_margin_ps']-f0['full_receiver']['one_sided_margin_ps'],'propagation_median_delta_ps':{k:delay1['edges'][k]['median_ps']-delay0['edges'][k]['median_ps'] for k in ['rising','falling']},'propagation_sources':[{'path':str((E/n).relative_to(ROOT)),'sha256':sha(E/n)} for n in ['gate-delay-before.json','gate-delay-TT-after.json']]},'full_SS':ssref|{'shutdown':ss['shutdown'],'body_forward_V':ss['body_forward_V'],'terminal_pass':ss['terminal_pass'],'body_pass':ss['body_pass'],'recovered_frame':metrics(ss['frames'][1]),'all_research_gates_pass':False,'reason':'Full waveform shutdown/recovered RX passes, but independent100uA DC=97.455081uA fails +/-1%. Full protocol only S40; S80 short comparison is narrower evidence.'},'short_half_step':short,'boundaries':['Final44MOS not selected as production architecture. TT high input-buffer and FF cold/high release terminal failures remain.','SS original and revised assertion comparisons have identical DATA snippet and diagnostic initialization; old full nominal is not a matched full SS baseline.','No errors in4096payload bits is finite deterministic observation, not measured BER or hardware qualification.','No LED thermal scaling, independent resistor process corner, mismatch, layout, PEX or optical extinction qualification.']}
(E/'comparison.json').write_text(json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
rows=['| 同TT第一帧，净1.6Gb/s | 原39MOS | 新44MOS |','|---|---:|---:|']
for name,a,b in [('正向取能pJ/bit',f0['energy_pJ_per_attempted_payload_bit']['positive'],f1['energy_pJ_per_attempted_payload_bit']['positive']),('返还pJ/bit',f0['energy_pJ_per_attempted_payload_bit']['returned'],f1['energy_pJ_per_attempted_payload_bit']['returned']),('净pJ/bit',f0['energy_pJ_per_attempted_payload_bit']['net'],f1['energy_pJ_per_attempted_payload_bit']['net']),('幅度余量uAeq',f0['full_receiver']['worst_signed_margin_uAeq'],f1['full_receiver']['worst_signed_margin_uAeq']),('单侧时间余量ps',f0['full_receiver']['one_sided_margin_ps'],f1['full_receiver']['one_sided_margin_ps'])]:rows.append(f'| {name} | {a:.6f} | {b:.6f} |')
(E/'comparison-table.md').write_text('\n'.join(rows)+'\n\n两组均4096位0观察错误；这是首帧比较，不是持续运行稳态。新增缓冲的实际D0到GP中位延迟，上升增加85.403ps，下降增加81.699ps；并未提高本轮速率。\n')
subprocess.run([str(ROOT/'build/layout/venv/bin/python'),str(Path(__file__).with_name('collect.py')),'--final'],check=True,cwd=ROOT)
files=[]
paths=list((ROOT/'scripts/driver_pvt_20261117/b').rglob('*'))+list(E.rglob('*'))+list(B.rglob('*'))+list(A.glob('b-*'))
for p in sorted(set(paths)):
 if not p.is_file() or '__pycache__' in p.parts or p==E/'freeze.json' or p.name.startswith('b-clamp-bias-probe'):continue
 files.append({'path':str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'sha256':sha(p)})
freeze={'schema':'b-pvt-freeze-v1','status':'frozen','created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'required_cases':[str(p.parent.relative_to(ROOT)) for p in sorted(B.glob('*/*/result.json'))],'files':files,'scope':'129 cases including failures, diagnostics, DC and two complete waveform protocols; frozen does not mean all research gates passed.','exclusions':['__pycache__','this self-referential freeze file','root-owned b-clamp-bias-probe assets'],'full_protocol_finer_step':'not run; SS assertion/release S40/S80 short diagnostics completed'}
(E/'freeze.json').write_text(json.dumps(freeze,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'cases':len(freeze['required_cases']),'files':len(files),'bytes':sum(x['bytes'] for x in files),'energy_change_percent':out['nominal_comparison']['positive_energy_change_percent'],'freeze_sha256':sha(E/'freeze.json')}))
