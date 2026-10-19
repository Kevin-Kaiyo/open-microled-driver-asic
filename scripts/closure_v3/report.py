"""Render a dated evidence-backed supplement without changing historic reports."""
from pathlib import Path
import argparse,hashlib,json,re,shutil,sys
import markdown
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'docs/research/single-pixel-closure-20261015'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads((ROOT/p).read_text())
def table(head,rows):return '| '+' | '.join(head)+' |\n|'+'|'.join(['---']*len(head))+'|\n'+'\n'.join('| '+' | '.join(map(str,r))+' |' for r in rows)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--analog-tag',required=True);ap.add_argument('--joint-summary',required=True);ap.add_argument('--new-numerical',required=True);a=ap.parse_args()
 apath=f'evidence/analog-v3/{a.analog_tag}/summary.json';s=load(apath);dc=load('evidence/analog-v3/pvt-pex-r5-bleed10M/summary.json');num=load('evidence/startup-v3/numerical/refined-summary.json');newnum=load(a.new_numerical);phys=load('evidence/layout-v3/r5/summary.json');joint=load(a.joint_summary);dig=load('evidence/control-v3/summary.json');cou=load('evidence/control-v3/coupled-r5-bleed10/summary.json');ac=load('evidence/analog-v3/ac-pex-r5-bleed10M/summary.json')
 r=s['results'];startup=[x for x in r if x['kind']=='startup'];fault=[x for x in r if x['kind']=='fault'];normal=[x for x in r if x['kind']=='normal'];startup_max=max(x['startup']['branch_max_abs_a'] for x in startup if x.get('simulation_completed'))
 blocks={}
 blocks['RESULTS']=table(['验证层','本轮实际进展'],[['数值方法','旧4.909%失败保留；新增近零绝对预算、局部网格与跨积分方法验证'],['单像素电路',f'{len(startup)}组启动 / {len(fault)}组故障 / {len(normal)}组PWM；最终套件：{"通过" if s["passed"] else "未通过"}'],['模拟版图','39MOS完整宏；两套DRC、LVS、GDS回读与29/29网络RC'],['数字版图','PWM+恢复存储；9角STA/SDF；200×200 µm'],['共同顶层','独立DRC/LVS/PEX，详见本报告共同顶层页'],['制造与实测','尚未达到流片签核；无硅片或光学测量']])
 acrows=[]
 for env in ['tt','ss','ff']:
  vals=[]
  for cc in [3,30]:vals.append(next(x['crossings'][0]['phase_margin_deg'] for x in ac['results'] if x['envelope']==env and x['cc_pf']==cc and x['csense_pf']==30))
  acrows.append([env.upper(),'30 pF',f'{vals[0]:.2f}°',f'{vals[1]:.2f}°'])
 blocks['AC_TABLE']=table(['包络','SENSE附加C','原CC=3pF','新CC=30pF'],acrows)
 blocks['NUMERICAL_FIGURE']='![数值收敛证据](figures/numerical.svg)'
 blocks['NUMERICAL']=f'旧电路最终10组结果两两比较共45对，全部满足新增预算；最大波形差 **{num["selected_maximum_current_difference_a"]*1e12:.4f} pA**，最大电荷差 **{num["selected_maximum_charge_difference_c"]:.4g} C**。新PEX的启动也独立进行了首步细化；不能直接沿用旧电路结论。具体对照见新PEX数值审查文件。'
 blocks['BLEED']='新增 **RBLEED=10 MΩ**，REFOUT接至VSS。典型试验初始偏差降至约48.63 µV；DC LED电流由99.8841 µA降至99.7391 µA，差0.1450 µA。随后对这个包含电阻的候选重新做DC/PVT、环路、启动、PWM与故障试验。旧无电阻候选和首步尖峰失败均保留。'
 blocks['STARTUP_COMPARE_FIGURE']='![完整PEX启动修复前后](figures/startup-comparison.svg)'
 blocks['LAYOUT_FIGURE']='![r5实际版图](figures/r5-overview.svg)\n\n[放大查看参考源局部版图](figures/r5-reference-detail.svg) · [可缩放二维版图与图层选择](layout/viewer.html)'
 blocks['LAYOUT_CHANGES']='r5把每条网络限制在所需端点之间，电源端口改在适当位置接入，VSS主干由0.6 µm加宽至8 µm。实际PEX中，REFOUT–LED_K耦合由8.24068 fF变为零提取项，VREF–LED_K由0.99898 fF变为零；LED_K–VSS由54.26149 fF降至15.86925 fF。零提取项表示该抽取模型中未出现该耦合，不表示物理空间绝对零电容。\n\n实际宏边界637.03×200.36 µm，约0.12764 mm²。提取39只MOS、345个R、288个C。可在配套二维查看器中缩放和切换工艺层。'
 rows=[]
 for e in ['tt','ss','ff']:
  starts=[x for x in startup if x['envelope']==e];f=next(x for x in fault if x['envelope']==e);n=next(x for x in normal if x['envelope']==e)
  rows.append([e.upper(),f'{max(x["startup"]["branch_max_abs_a"] for x in starts)*1e9:.4f}',f'{f["fault_to_safe_s"]*1e9:.2f}',f'{n["d1_error_pct"]:+.4f}%'])
 blocks['PEX_TABLE']=table(['包络','启动最大绝对电流 / nA','故障关闭 / ns','duty=1电荷误差'],rows)+'\n\n最终片外元件与输入条件：VSET=0.5 V，RSET=5 kΩ，RBIAS/RRELEASE=100 kΩ，CCOMP=30 pF，SENSE附加电容预算30 pF，RBLEED=10 MΩ。完整套件：'+('通过' if s['passed'] else '未通过')+f'。270点DC导通电流{dc["on_min_a"]*1e6:.4f}–{dc["on_max_a"]*1e6:.4f} µA，关断最大{dc["off_max_abs_a"]*1e12:.2f} pA。MOS角/温压扫描不含统计失配、电阻容差或RC工艺角。'
 blocks['PEX_FIGURE']='![提取后启动和故障波形](figures/pex-waveforms.svg)'
 blocks['FAULT_FIGURE']='![SDF到PEX的故障与恢复](figures/sdf-fault.svg)'
 c1,c2=cou['results'];blocks['COUPLED']=f'将真实数字SDF时间戳输入完整r5模拟PEX（引脚斜率仍假设10 ns），典型duty=1误差 **{c1["error_pct"]:+.4f}%**，停钟故障关闭 **{c2["fault_to_safe_ns"]:.2f} ns**，Q+ **{c2["charge"]["positive_c"]*1e12:.4f} pC**，Q− **{c2["charge"]["negative_c"]*1e12:.4f} pC**。这是明确边界的联合回放，尚非共同顶层全部晶体管的动态仿真。'
 blocks['DIGITAL']=table(['检查','实际结果'],[['RTL / 布线后功能网表','各10个用例通过'],['九角SDF','每角4108项检查；故障观测输出关闭0.767–2.429 ns'],['寄存器setup最小余量',f'{dig["r2r_setup_min_ns"]:.3f} ns'],['寄存器hold最小余量',f'{dig["r2r_hold_min_ns"]:.6f} ns'],['slew/cap/fanout','9角0违规；SDC条件有效'],['DRC / LVS / GDS XOR','数字宏对应结果均0错误']])
 # Joint text is a separately reviewed evidence block because schema depends on extraction audit.
 blocks['JOINT']=(BASE/'joint-block.md').read_text()
 blocks['NEXT']='当前可继续在单像素完整物理模型上研究，但仍有两项直接影响产品规格：① 参考电源3.3→2.97→3.3 V、100 ns边沿的TT扰动使电流瞬时达到60.16–147.24 µA，回到±0.5%需约2.49 µs；必须制定电源扰动和瞬态过冲预算。② FAULT任意相位释放、所有电源同时启动/掉电、POR/欠压和封装寄生尚未闭合。\n\n共同顶层已生成的全部RC网络仍需系统级动态回归；目前电气结论针对模拟宏完整PEX及数字SDF边界回放。外部参考、精密电阻、补偿与放电元件也是平台的一部分。'
 template=(BASE/'report-template.md').read_text()
 for k,v in blocks.items():template=template.replace('@@'+k+'@@',v)
 assert not re.findall(r'@@[A-Z_]+@@',template)
 pages=template.split('<!-- PAGE -->');(BASE/'report.md').write_text(template)
 css="""@page{size:A4;margin:18mm 20mm}*{box-sizing:border-box}body{margin:0;color:#29434c;font:10.7pt/1.63 'Avenir Next','PingFang SC',sans-serif}h1,h2{color:#176e73;line-height:1.3}h1{font-size:25pt;margin:0 0 6mm}h2{font-size:16.5pt;margin:0 0 5mm;border-bottom:1px solid #c7d8d5;padding-bottom:3mm}p{margin:0 0 3mm}a{color:#176e73;overflow-wrap:anywhere}strong{color:#174c59}img{display:block;width:100%;max-height:135mm;object-fit:contain;margin:3mm auto}table{width:100%;border-collapse:collapse;margin:3mm 0;font-size:9.4pt;line-height:1.5}th,td{padding:2mm;border-bottom:1px solid #d7e2df;text-align:left;vertical-align:top}th{background:#eef4f2}tr{break-inside:avoid}code{font-size:.92em;overflow-wrap:anywhere}ul{padding-left:5mm}.page{break-after:page}.page:last-child{break-after:auto}@media screen{body{background:#ecf2f0}.page{width:210mm;min-height:297mm;margin:7mm auto;padding:18mm 20mm;background:white;box-shadow:0 1px 6px #b9c9c4}}@media print{.page{width:170mm}}"""
 html='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>单像素启动、保护与版图验证</title><style>'+css+'</style><body>'+''.join('<section class="page">'+markdown.markdown(p.strip(),extensions=['tables','fenced_code'])+'</section>' for p in pages)+'</body></html>'
 (BASE/'report.html').write_text(html)
 inputs=[apath,a.joint_summary,a.new_numerical,'evidence/startup-v3/numerical/refined-summary.json','evidence/analog-v3/pvt-pex-r5-bleed10M/summary.json','evidence/analog-v3/ac-pex-r5-bleed10M/summary.json','evidence/control-v3/summary.json','evidence/control-v3/coupled-r5-bleed10/summary.json','evidence/layout-v3/r5/summary.json']
 (BASE/'manifest.json').write_text(json.dumps({'date':'2026-10-15','pages_expected':len(pages),'analog_final_tag':a.analog_tag,'analog_final_passed':s['passed'],'report_source_hashes':{p:sha(ROOT/p) for p in inputs},'physical_scope':'common top DRC/LVS/PEX, macro electrical plus digital SDF replay; no full joint transient/silicon/optics'},ensure_ascii=False,indent=2)+'\n')
 print(f'{len(pages)} sections rendered')
if __name__=='__main__':main()
