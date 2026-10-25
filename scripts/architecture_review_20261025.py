#!/usr/bin/env python3
"""Rebuild a source-backed architecture review; does not execute any EDA flow."""
from pathlib import Path
import csv, hashlib, html, json, math, re, subprocess
import markdown
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/research/architecture-decision-review-20261025'
EV=ROOT/'evidence/architecture-review-20261025'
BODY="'PingFang SC','Noto Sans CJK SC',sans-serif"
def read(p):return json.loads((ROOT/p).read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def calculations():
 rows=list(csv.DictReader((ROOT/'evidence/nrz-reference-v2/final-tables/nominal-energy-comparison.csv').open()))
 new=next(x for x in rows if x['PVT']=='TT' and x['design']=='selected_21MOS_reference')
 e=float(new['positive_pJ_per_bit']);rate=.5;p_mw=e*rate
 refrows=[x for x in read('evidence/nrz-reference-v2/power-dc-r2.json')['rows'] if x['corner']=='typical' and x['bit']==1]
 assert len(refrows)==1
 ref=refrows[0]['source5V_allocated_power_W']
 shared_mw=sum(ref[x] for x in ['OTA_control','sense_reference','output_reference'])*1e3
 assert 0<shared_mw<p_mw
 scenarios=[]
 for n in [1,4,16,64]:
  gross=n*rate;net=.9*gross
  share=shared_mw+n*(p_mw-shared_mw)
  shared_control_mw=sum(ref[x] for x in ['OTA_control','sense_reference'])*1e3
  partial=shared_control_mw+n*(p_mw-shared_control_mw)
  scenarios.append({'lanes':n,'lane_rate_Gbps':rate,'gross_Gbps':gross,'payload_efficiency_assumed':.9,'net_Gbps':net,'replicated_total_port_positive_power_mW':n*p_mw,'ideal_shared_total_port_positive_power_mW':share,'ideal_shared_gross_pJ_per_bit':share/gross,'ideal_shared_net_pJ_per_bit':share/net,'shared_control_DC_budget_mW':shared_control_mw,'ideal_shared_control_local_output_total_port_positive_power_mW':partial,'ideal_shared_control_local_output_gross_pJ_per_bit':partial/gross,'ideal_shared_control_local_output_net_pJ_per_bit':partial/net})
 alpha=.05;nbit=511
 result={'as_of':'2026-10-25','no_new_EDA':True,'PWM':{'clock_Hz':1e6,'slots':256,'frame_us':256,'repetition_Hz':1e6/256,'duty_levels':257,'duty_LSB_percent_FS':100/256,'half_LSB_percent_FS':50/256,'ideal_average_LSB_uA_at_100uA':100/256,'updates_wait_bound_us':256,'higher_bit_depth_arithmetic':[{'bits':b,'clock_Hz':1e6,'PWM_Hz':1e6/2**b,'slot_us':1} for b in [8,10,12,16]],'clock_for_12bit_at_same_PWM_Hz':1e6*16},'NRZ':{'B_TT_positive_pJ_per_gross_bit':e,'rate_Gbps':rate,'power_mW':p_mw,'shared_reference_DC_budget_mW':shared_mw,'reference_energy_pJ_per_bit_at_0p5G':shared_mw/rate,'reference_share_of_TT_port_energy_percent_approx':100*shared_mw/p_mw,'UI_ns':1/rate,'min_selected_timing_UI':.265625,'min_selected_timing_ns':.265625/rate,'proxy_LED_tau_ps':200,'proxy_LED_3dB_GHz':1/(2*math.pi*200e-12)/1e9,'RX_bandwidth_GHz':1,'random_measurement_zero_errors_511_upper_95':-math.expm1(math.log(alpha)/nbit),'bits_for_zero_errors_upper_95_below_1e_minus12':math.ceil(math.log(alpha)/math.log1p(-1e-12)),'seconds_at_0p5G_for_that_statistical_example':math.log(alpha)/math.log1p(-1e-12)/(.5e9)},'array_scenarios':scenarios,'array_scenario_scope':'Arithmetic only. Includes a very ideal full-reference-sharing scenario and a split OTA+sense-sharing/local-output scenario. Neither includes added current buffers, mismatch, noise, PDN or thermal cost. Not simulated array performance, guaranteed lower bounds or promised savings.','interfaces':{'mono_4x4_8bit_60Hz_payload_bps':16*8*60,'RGB_4x4_8bit_60Hz_payload_bps':16*3*8*60,'RGB_3840x2160_8bit_60Hz_payload_bps':3840*2160*3*8*60,'QSPI_50MHz_SDR_raw_bps':4*50e6},'power_scaling':{'delta_1pJ_at_1Tbps_W':1e-12*1e12,'delta_1pJ_at_1000_links_1Tbps_W':1000*1e-12*1e12},'charging_scale':{'C_F':200e-15,'I_A':100e-6,'t_for_0p1V_ns':200e-15*.1/100e-6*1e9,'t_for_1V_ns':200e-15/100e-6*1e9,'scope':'Ideal constant-current charging of only this capacitor; not an extracted node transient.'}}
 assert math.isclose(result['PWM']['repetition_Hz'],3906.25)
 assert math.isclose(p_mw/1e3/(rate*1e9)*1e12,e)
 assert math.isclose(scenarios[0]['ideal_shared_gross_pJ_per_bit'],e)
 assert all(x['ideal_shared_total_port_positive_power_mW']<=x['replicated_total_port_positive_power_mW']+1e-12 for x in scenarios)
 assert all(x['ideal_shared_total_port_positive_power_mW']<=x['ideal_shared_control_local_output_total_port_positive_power_mW']<=x['replicated_total_port_positive_power_mW']+1e-12 for x in scenarios)
 assert result['interfaces']['RGB_3840x2160_8bit_60Hz_payload_bps']>result['interfaces']['QSPI_50MHz_SDR_raw_bps']
 dump(EV/'calculations.json',result);return result

def svg_architecture():
 parts=['<svg xmlns="http://www.w3.org/2000/svg" width="1300" height="760" viewBox="0 0 1300 760" role="img" aria-label="显示PWM与通信NRZ两条数据和参考路径的架构比较">',f'<style>text{{font-family:{BODY};fill:#183f49}}.h{{font-size:25px;font-weight:600}}.t{{font-size:20px}}.s{{font-size:17px;fill:#50656c}}.box{{fill:#fff;stroke:#65908e;stroke-width:2}}.a{{fill:none;stroke:#235e64;stroke-width:3;marker-end:url(#arrow)}}.b{{fill:none;stroke:#7f9298;stroke-width:2;stroke-dasharray:7 6;marker-end:url(#arrow)}}</style><defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0L10 5L0 10z" fill="#235e64"/></marker></defs><rect width="1300" height="760" fill="#f7faf9"/>']
 def text(x,y,lines,cls='t'):
  for i,line in enumerate(lines):parts.append(f'<text x="{x}" y="{y+i*28}" class="{cls}">{html.escape(line)}</text>')
 def box(x,y,w,h,lines):
  parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" class="box"/>');text(x+16,y+34,lines)
 def arrow(x1,y1,x2,y2,cls='a'):parts.append(f'<path d="M{x1} {y1} L{x2} {y2}" class="{cls}"/>')
 text(40,45,['显示：把稳定的导通电流，按帧分配给亮灯时间'],'h')
 box(40,85,205,105,['帧数据 / 本地存储','下一帧统一更新'])
 box(290,85,225,105,['计数器＋码值比较','1 μs 时隙 / 256 槽'])
 box(560,85,220,105,['缓冲＋独立保护','PWM 控制栅极'])
 box(825,85,195,105,['恒流像素输出','约 100 μA 导通'])
 box(1065,85,195,105,['MicroLED','平均电流∝占空比'])
 for x1,x2 in [(245,290),(515,560),(780,825),(1020,1065)]:arrow(x1,137,x2,137)
 box(580,230,420,80,['参考电压 → 反馈参考 → 电流镜'])
 arrow(920,230,920,190,'b')
 text(40,260,['当前：单像素＋39 MOS 模拟宏','3.90625 kHz PWM；外部 FAULT/PERMIT','新补偿和板侧滤波已完成限定回归'],'s')
 text(40,390,['通信：逐位形成可判决的两个光功率状态'],'h')
 box(40,430,205,105,['并行数据 / 测试码型','当前 .5 Gb/s NRZ'])
 box(290,430,225,105,['数字预驱动 / 缓冲','不逐位调节参考环路'])
 box(560,430,220,105,['电流转向 LED/dummy','低 / 高约 25/100 μA'])
 box(825,430,195,105,['MicroLED＋光路','当前为动态代理'])
 box(1065,430,195,105,['PD / TIA / 判决','当前为接收算法'])
 for x1,x2 in [(245,290),(515,560),(780,825),(1020,1065)]:arrow(x1,482,x2,482)
 box(290,590,490,80,['2.5 V 外部基准 → 10 MOS 反馈 → BIAS'])
 arrow(670,590,670,535,'b')
 text(825,602,['实际已布局：参考＋保护＋B核心','接收器、光学与完整协议尚为边界','偏置是慢环路；转向是快数据路径'],'s')
 text(40,725,['实线：数据 / 驱动功能路径　虚线：参考偏置　图为功能架构，非实际布线或电流密度图。'],'s')
 parts.append('</svg>');(OUT/'architecture-comparison.svg').write_text(''.join(parts))

def matched_route_comparison():
 rows=read('evidence/highspeed-nrz-robustness/summary-verified.json')['same_rate_energy']
 table=['| 条件，均为历史0.4 Gb/s核心 | A / B正向能量 pJ/bit | A / B时序余量 ps | A / B平均LED电流 µA | 结果 |','|---|---:|---:|---:|---|']
 fig,axes=plt.subplots(1,3,figsize=(11.8,3.9),sharex=True,sharey=True)
 for ax,row in zip(axes,rows):
  a,b=row['A'],row['B']
  label={'TT':'TT / 27 C / 3.3 V','SSminus50':'SS / 125 C / 2.95 V','FFplus50':'FF / -40 C / 3.65 V'}[row['condition']]
  assert a['rate_Gbps']==b['rate_Gbps']==.4 and a['combined_screen_passed'] and b['combined_screen_passed']
  xa=a['rail_plus_DATA_positive_draw_fJ_per_gross_bit']/1000;xb=b['rail_plus_DATA_positive_draw_fJ_per_gross_bit']/1000
  ya=a['timing_min_margin_ui']/a['rate_Gbps']*1000;yb=b['timing_min_margin_ui']/b['rate_Gbps']*1000
  ia=a['LED_mean_current_A']*1e6;ib=b['LED_mean_current_A']*1e6
  table.append(f"|{label}|{xa:.4f} / {xb:.4f}|{ya:.1f} / {yb:.1f}|{ia:.2f} / {ib:.2f}|均0/511，限定联合筛查通过|")
  ax.plot([xa,xb],[ya,yb],color='#b8c8c8',lw=1.5,zorder=1)
  ax.scatter([xa],[ya],s=90,color='#117d80',label='A: voltage mode',zorder=3)
  ax.scatter([xb],[yb],s=90,color='#304b70',marker='s',label='B: older current steering',zorder=3)
  ax.annotate('A',(xa,ya),xytext=(8,-14),textcoords='offset points',fontsize=12)
  ax.annotate('B',(xb,yb),xytext=(8,5),textcoords='offset points',fontsize=12)
  ax.set_title(label);ax.set_xlim(.8,2);ax.set_ylim(0,850);ax.grid(alpha=.2);ax.set_xlabel('Energy (pJ/gross bit)')
 axes[0].set_ylabel('Timing margin (ps)');handles,labels=axes[0].get_legend_handles_labels();fig.legend(handles,labels,loc='upper center',ncol=2,frameon=False,bbox_to_anchor=(.5,1.03))
 fig.tight_layout(rect=(0,0,1,.93));fig.savefig(OUT/'matched-core-comparison.png',dpi=160,bbox_inches='tight');plt.close(fig)
 return '\n'.join(table)

def build():
 OUT.mkdir(parents=True,exist_ok=True);EV.mkdir(parents=True,exist_ok=True)
 calculations();svg_architecture()
 source=(OUT/'report.md').read_text().replace('{{MATCHED_ROUTES}}',matched_route_comparison());(OUT/'report-complete.md').write_text(source);rendered=markdown.markdown(source,extensions=['tables','fenced_code','toc','attr_list'],extension_configs={'toc':{'toc_depth':'2-2'}})
 css='''*{box-sizing:border-box}html{scroll-behavior:auto}body{margin:0;color:#203b43;background:#f4f7f6;font:16px/1.75 "PingFang SC","Noto Sans CJK SC",Arial,sans-serif}main{max-width:1080px;margin:32px auto;background:#fff;padding:42px 48px 70px}h1,h2,h3{font-family:"Tw Cen MT","PingFang SC",sans-serif;color:#164f58;line-height:1.4}h1{font-size:33px;margin:22px 0}h2{font-size:25px;border-bottom:1px solid #dae6e4;padding-bottom:10px;margin-top:48px}h3{font-size:20px;margin-top:28px}p{margin:13px 0}a{color:#0c6771;text-decoration-thickness:1px;text-underline-offset:3px}nav{display:flex;gap:18px;flex-wrap:wrap;font-size:14px}.eyebrow,figcaption,.note{color:#64787e;font-size:14px}table{border-collapse:collapse;width:100%;font-size:15px;margin:22px 0}th,td{text-align:left;vertical-align:top;border-bottom:1px solid #dce6e4;padding:12px 10px;overflow-wrap:anywhere}th{background:#edf4f3}img{display:block;max-width:100%;height:auto;margin:20px auto}figure{margin:28px 0}blockquote{border-left:3px solid #3a7b7b;padding:5px 20px;margin:24px 0;background:#f2f7f6}code{font-size:.92em}pre{white-space:pre-wrap;background:#f2f5f4;padding:16px}.toc{background:#f7faf9;padding:16px 24px}.toc a{text-decoration:none}.toc li{margin:4px 0}.button{font:inherit;padding:7px 16px;border:1px solid #809d9e;background:white;color:#164f58;cursor:pointer}@media(max-width:700px){main{margin:0;padding:24px 18px}h1{font-size:27px}table{font-size:13px}th,td{padding:9px 5px}.scroll{overflow-x:auto}}@media print{body{background:white}main{max-width:none;margin:0;padding:0;font-size:11pt;line-height:1.65}h1{font-size:26pt}h2{font-size:16pt}nav,.button{display:none}figure,blockquote{break-inside:avoid}thead{display:table-header-group}@page{size:A4;margin:19mm}}'''
 (OUT/'report.css').write_text(css)
 rendered=re.sub(r'<table>(.*?)</table>',r'<div class="scroll"><table>\1</table></div>',rendered,flags=re.S)
 page='<!doctype html><html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>MicroLED Driver：显示与光通信的阶段复盘及路线选择</title><link rel="stylesheet" href="report.css"></head><body><main><p class="eyebrow">OPEN MICROLED DRIVER ASIC / 2026-10-25 / 实验性研发方法验证与教学</p><nav><a href="report-complete.md">完整 Markdown</a><a href="../../../evidence/architecture-review-20261025/calculations.json">计算表</a><a href="../../../evidence/architecture-review-20261025/sources.json">公开来源</a><a href="../pwm-reference-startup-20261024/index.html">PWM 电路报告</a><a href="../nrz-b-reference-power-20261024/index.html">高速 B 电路报告</a></nav>'+rendered+'</main></body></html>\n'
 (OUT/'index.html').write_text(page)
 inputs=[ROOT/p for p in ['evidence/pwm-reference-v2/20261024/final-summary.json','evidence/nrz-reference-v2/selected-final-r2-summary-verified.json','evidence/nrz-reference-v2/power-dc-r2.json','evidence/nrz-reference-v2/final-tables/nominal-energy-comparison.csv','evidence/nrz-reference-v2/final-tables/nrz-source-energy.csv','evidence/current-range/summary.json','evidence/reference-v2-layout/nrz-switched-keeper-summary.json','evidence/highspeed-nrz-robustness/selected-a8-b58-r4-summary.json','evidence/highspeed-nrz-robustness/summary-verified.json','docs/research/driver-robustness-20261024/figures/voltage-schematic.png','docs/research/highspeed-driver-routes-20261019/figures/route-c.png','docs/research/pwm-reference-startup-20261024/figures/external-network.png','docs/research/nrz-b-reference-power-20261024/figures/selected-b-circuit.png']]
 inputs += [p for p in EV.glob('*') if p.is_file() and p.name not in {'report-provenance.json','validation.json','visual-review.json','delivery-check.json'}]
 proof={'as_of':'2026-10-25','status':'existing-evidence-review-and-calculations; no new circuit simulations or EDA','baseline_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'inputs':{str(p.relative_to(ROOT)):sha(p) for p in inputs},'outputs':{str(p.relative_to(ROOT)):sha(p) for p in [OUT/'report.md',OUT/'index.html',OUT/'report.css',OUT/'architecture-comparison.svg',OUT/'matched-core-comparison.png',OUT/'report-complete.md']},'generator_sha256':sha(Path(__file__))}
 dump(EV/'report-provenance.json',proof)
 print('Built '+str(OUT.relative_to(ROOT)))
if __name__=='__main__':build()
