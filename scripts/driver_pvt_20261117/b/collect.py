#!/usr/bin/env python3
from pathlib import Path
import argparse,hashlib,json
ROOT=Path(__file__).resolve().parents[3];B=ROOT/'build/driver-pvt-20261117/b';E=ROOT/'evidence/driver-pvt-20261117/b'
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
VARIANTS={'baseline':'冻结v6r原39MOS','clamp5v':'仅钳位gate由DISABLE改iso_g，39MOS','clamp5v_r1k':'直接5V钳位+新增输入poly2→1方块，39MOS，失败支线','clamp5v_delayed':'5V钳位+100kohm门电阻+W4/L0.7快复位，40MOS','clamp5v_delay200':'仅钳位门电阻100→200kohm，40MOS','clamp5v_buffer':'200kohm钳位+原输入poly后2级真实CMOS反相器，44MOS','clamp5v_buffer_soft':'仅钳位复位NMOS W4→W0.5/L0.7，44MOS；全协议评估候选','clamp5v_buffer_damped':'慢撤版本两缓冲级之间再加1方块poly，44MOS；第一输出过冲仍未解决','unit_tail':'单只W5.76/L1尾管改3只W2/L1单位管；DC单独支线41MOS','unit_long':'参考/基流/3尾单位管均W4/L2，保持W/L；仅DC41MOS','unit_long_trim':'长单位管+固定RSET19975.586ohm（−0.75%），仅DC41MOS'}
rows=[]
for p in sorted(B.glob('*/*/result.json')):
 r=json.loads(p.read_text());m=json.loads(p.with_name('manifest.json').read_text());c=r['case'];mode=c.get('mode');s=r.get('shutdown',{});good=r.get('simulation_ok',False) and not r.get('analysis_error') and r.get('terminal_pass',False) and r.get('body_pass',False)
 if c.get('kind')=='dc':good=good and r.get('DC_pass',False)
 elif mode=='assert':good=good and s.get('off_current_screen_pass',False)
 elif mode=='fault':good=good and s.get('off_current_screen_pass',False) and s.get('recovery_within_1us_verified',False) and s.get('last_frame_full_rx_pass',False)
 elif mode not in ['release']:good=good and bool(r.get('frames')) and all(f['full_receiver']['research_margin_pass'] and f['first_frame_phase_receiver']['research_margin_pass'] for f in r.get('frames',[]))
 x={'case':str(p.parent.relative_to(ROOT)),'variant':c['variant'],'pvt':c['pvt_key'],'mode':mode,'result_sha256':sha(p),'manifest_sha256':sha(p.with_name('manifest.json')),'waveform_gzip_sha256':r.get('gzip_sha256'),'applicable_case_screens_pass':bool(good),'diagnostic_only':r.get('diagnostic_only',False),'result':r}
 q=p.with_name('execution-provenance-correction.json')
 if q.exists():x['execution_provenance_correction']={'path':str(q.relative_to(ROOT)),'sha256':sha(q),'record':json.loads(q.read_text())}
 q=p.with_name('stress-positions.json')
 if q.exists():x['native_stress_positions']={'path':str(q.relative_to(ROOT)),'sha256':sha(q)}
 rows.append(x)
selected='clamp5v_buffer_soft';sel={'variant':selected,'full_fault':'build/driver-pvt-20261117/b/'+selected+'/ss_hot_low-full-s40','nominal_receive':'build/driver-pvt-20261117/b/'+selected+'/tt-normal1-s40','DC_grid':[x['case'] for x in rows if x['variant']==selected and x['result']['case'].get('kind')=='dc'],'open_failures':['100uA DC current misses +/-1% in6of9corners, unchanged by protection-only changes','TT high prior buffer stage has ib1 3.639V above3.63V; series resistor only isolates following gate','FF cold high release still OUT3.6815V during high-side reconnection, while DATA_SAFE remains0','Unit long mirror trim passes DC grid only; unintegrated with new protection and untested for dynamic loading and receiver']}
p=argparse.ArgumentParser();p.add_argument('--final',action='store_true');args=p.parse_args()
if args.final:
 for k in ['full_fault','nominal_receive']:assert any(x['case']==sel[k] for x in rows),k
out={'schema':'b-pvt-summary-v1','status':'frozen' if args.final else 'in_progress','protocol':{'path':str((E/'protocol.json').relative_to(ROOT)),'sha256':sha(E/'protocol.json')},'variants':VARIANTS,'selection_for_protocol_evaluation':sel,'rows':rows,'evidence_boundaries':['Short diagnostic initial OP and96/160ns waveforms are not full RX or original continuous history.','No autonomous fault detector, actual optical leakage model, measured LED temperature scaling, layout or reliability qualification.','Case-level waveform pass does not override independent DC failure or missing PVT coverage.','All gates retain prior thresholds. No PDK-resistor process corner or ideal reference resistor temperature coefficient is inferred.','Power counted at7ports including independentVREF2.5V. Model internal id/vth/vdsat outputs are observational quantities with A/V units. Historical DC nodes_V includes model quantities; use names and new model_operating_quantities units, not that legacy dictionary name.']}
(E/'summary.json').write_text(json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False)+'\n');print('rows',len(rows),'status',out['status'])
