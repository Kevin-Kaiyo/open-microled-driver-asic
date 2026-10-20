#!/usr/bin/env python3
"""Build source-backed physical tables, preserving the report's electrical prose."""
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'docs/research/highspeed-nrz-pex-20261020'
def table(head,rows):return '<div class="scroll"><table><tr>'+''.join('<th>'+str(x)+'</th>'for x in head)+'</tr>'+''.join('<tr>'+''.join('<td>'+str(x)+'</td>'for x in row)+'</tr>'for row in rows)+'</table></div>'
p=OUT/'report-content.json';v=json.loads(p.read_text())if p.exists()else{}
s=json.loads((ROOT/'evidence/highspeed-nrz-pex/physical/summary.json').read_text())
rs=s['routes']
v['PHYSICAL_TABLE']=table(['核心','MOS','宽 × 高 (µm)','包围盒 (µm²)','金属','全网 R 覆盖','R / C 元件数'],[[r,d['counts']['mos'],' × '.join(f'{x:.2f}'for x in d['dimensions_um']),f"{d['core_area_um2']:.4f}",'M1–M4',f"{d['extracted_nets']}/{d['extracted_nets']}",f"{d['counts']['resistors']} / {d['counts']['capacitors']}"]for r,d in rs.items()])
v['VERIFICATION_TABLE']=table(['检查','A','B','证明范围'],[['Magic 原生 / GDS 回读 DRC','0 / 0','0 / 0','固定规则下的几何'],['独立 KLayout DRC','0','0','固定 FEOL/BEOL/连接/网格规则'],['原生 / GDS 回读 LVS','唯一匹配','唯一匹配','原理图与几何连接'],['RC 折叠拓扑 LVS','唯一匹配','唯一匹配','R拆网之后未接错拓扑'],['GDS 栅极断路 / VDD–VSS 短路负例','均被拒绝','均被拒绝','验证检查能发现真实连接错误'],['逐管 W/L 与 AD/AS/PD/PS 独立几何审计','通过','通过','弥补标准LVS忽略参数的范围'],['r4 RC折叠后逐节点对C守恒','通过','通过','电容值与原.ext相同；不证明空间位置准确']])
cap=[];per=[]
for r in 'AB':
 d=json.loads((ROOT/f'build/highspeed-nrz-layout/r4/{r}/capacitance-correction.json').read_text());a=json.loads((ROOT/f'build/highspeed-nrz-layout/r4/{r}/pex-audit.json').read_text())
 cap.append([r,f"{d['authoritative_ground_sum_fF']:.6f}",f"{d['authoritative_coupling_sum_fF']:.6f}",f"{d['authoritative_total_sum_fF']:.6f}"])
 for n in (['N1','CTRL','OUT']if r=='A'else['GB','GP','VX','OUT','BIAS']):
  q=a['per_net'][n];per.append([r,n,q['resistor_count'],f"{q['incident_capacitance_farad']*1e15:.4f}"])
v['CAP_TABLE']=table(['核心','对地 C (fF)','耦合 C (fF)','总显式 C (fF)'],cap)+table(['核心','网络','该网R支路数','与该网相连的C总量 (fF)'],per)
w=json.loads((ROOT/'evidence/highspeed-nrz-pex/wire-paths.json').read_text())
v['CAP_TABLE']+=table(['核心','指定端点间的被动互连路径','有效电阻 (Ω)'],[[r,p['label'],f"{p['effective_R_ohm']:.3f}"]for r,d in w['routes'].items()for p in d['paths']])
v['PEX_FIX_NARRATIVE']='初版 r3 的原生导出有三个相互影响的问题：层次导出器把 MOS 子电路误入电阻 π 模型分支，移动了栅极电容；电阻提取过程没有读取原节点对地电容，却把耦合电容复制到两端；导出时保留原节点，进一步累加这些电容。独立审阅通过固定工具源代码和实际输出确认了原因，因此 r3 的原生 C/RC 没有用于正式速率结论。r4 保持 GDS、全部 R 与 MOS 不变，直接从 GDS 回读 .ext 取得高精度对地及耦合电容，组装成有逐元件台账的模型。另启新 Magic 进程、关闭层次导出获得纯 C 参考，核对原节点分配。'
v['PEX_SCOPE']='正式 RC 是经过独立审计的模型组装，并非未经改动的 Magic 原生 RC 输出。对地 C 按 Magic 电阻网简化后保留的归一化权重分配；耦合 C 在原逻辑节点只保留一次。RC 折叠后的逐节点对误差约 10⁻³⁰ F；C-only 控制的 12 位文本输出有约 10⁻²⁷ F 舍入。矩阵守恒确认电容没有丢失或重复，但不证明高频空间分布准确。上表路径电阻由完整被动 R 网络注入 1 A、求解端差得到，其他端点开路，不包含 MOS 沟道电阻；源端与体端路径应分开看。'
p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n');print(p)
