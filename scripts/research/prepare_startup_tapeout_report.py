"""Prepare derived report blocks from current frozen experiment summaries."""
from pathlib import Path
import csv,json,hashlib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/research/startup-tapeout-20261014'
def read(p):return json.loads((ROOT/p).read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def wave(row):
 data=list(csv.DictReader((ROOT/row['csvpath']).open()))
 return {k:[float(r[k]) for r in data] for k in data[0]}
def main():
 s=read('evidence/startup-v2/summary.json');r={x['name']:x for x in s['results']}
 if s['functional_contract_passed'] is not True or s['passed'] is not False:raise ValueError('Revise prose for actual experiment status')
 b={};b['_source_summary_sha256']=sha(ROOT/'evidence/startup-v2/summary.json')
 tt=r['startup_tt_ramp100ns'];base=r['baseline_matched_finite_gear'];ss=r['startup_ss_ramp100ns'];norm=r['normal_d1_10ns'];conv={x['name']:x for x in s['convergence']}
 maxpeak=max(x['startup']['branch_max_abs_a'] for x in s['results'] if x['name'].startswith('startup_'))
 ramp_names={f'startup_{e}_ramp{v}ns' for e in ['tt','ss','ff'] for v in [100,1000,10000]}
 maxramp=max(r[n]['startup']['branch_max_abs_a'] for n in ramp_names)
 b['CURRENT_STATUS']=(f'**新增结果：** CMOS传输门隔离后，所测启动峰最大{maxpeak*1e9:.5f} nA，低于原1 nA守卫；正常最低码和停钟fault原合同通过。'
                     f'**整体仍未全通过：** 极小启动Q+的10→2 ns相对变化{conv["startup"]["change_pct"]:.3f}%，未达原0.2%门槛，summary保持passed=false。')
 b['FAILURE_FIGURE']='![真实PEX电容的因果路径](figures/coupling-path.svg)\n\n<p class="caption">图1　从实际selected PEX抽出三条电容连接；未展开其余器件和寄生。旧失败数据与新匹配A/B分别报告。</p>'
 b['ISOLATION_FIGURE']='![新五MOS传输门隔离原理图](figures/reference-isolator.svg)\n\n<p class="caption">图2　按最终网表逐个核对D/G/S/B；NMOS与PMOS并联传送BIAS，体端分别接VSS和有效logic rail。参考rail与logic nominal相同，本图没有跨电源隔离保证。</p>'
 b['ISOLATION_EXPLANATION']=('**先验候选失败：** 单NMOS串联的四MOS方案在SS/85°C/2.97 V下输出仅68.04685 µA：REFOUT2.56410 V、BIAS1.39714 V，串联压降1.16696 V，参考PMOS复制支路失去余量。启动通过不够，保留这组失败而不选用。\n\n'
 '最终改成**五MOS CMOS transmission gate**：原NMOS与新增PMOS并联；FAULT_B驱动N管、FAULT驱动P管。fault高时两管关、XDIS开；fault低时两管开、XDIS关。两路并联改善正常传送能力，但仍需检查串联压降、体结和关断泄漏。')
 # Actual analog trace and actual RTL replay markers.
 plt.rcParams.update({'font.family':'Avenir Next','svg.fonttype':'none','font.size':9,'axes.spines.top':False,'axes.spines.right':False})
 w=wave(tt);t=w['time_s'];fig,ax=plt.subplots(1,2,figsize=(7.25,2.65),layout='constrained')
 indices=[n for n,x in enumerate(t) if 19.95e-6<=x<=23e-6]
 ax[0].plot([(t[n]-20e-6)*1e6 for n in indices],[w['v(bias)'][n] for n in indices],color='#176e73',label='BIAS')
 ax[0].plot([(t[n]-20e-6)*1e6 for n in indices],[w['v(fault_pin)'][n] for n in indices],color='#a3653f',label='FAULT')
 ax[0].plot([(t[n]-20e-6)*1e6 for n in indices],[w['v(permit)'][n] for n in indices],color='#849b9d',label='PERMIT')
 ax[0].set(xlabel='Time from fault release (µs)',ylabel='Terminal voltage (V)',xlim=(-.05,3));ax[0].legend(fontsize=8)
 short=[n for n,x in enumerate(t) if 19.95e-6<=x<=20.5e-6]
 ax[1].plot([(t[n]-20e-6)*1e6 for n in short],[w['i(VLEDLOAD)'][n]*1e6 for n in short],color='#176e73',label='LED branch')
 ax[1].set(xlabel='Time from fault release (µs)',ylabel='Branch current (µA)',xlim=(-.05,.5));ax[1].axhline(0,lw=.6,color='#849b9d')
 fig.savefig(BASE/'figures/recovery-waveforms.svg');plt.close(fig)
 b['RECOVERY_FIGURE']='![实际恢复电压与电流波形](figures/recovery-waveforms.svg)\n\n<p class="caption">图3　实际模拟波形及RTL事件回放。t=20 µs fault撤销，21.5 µs permit置高，22.5 µs raw PWM才高。不是片上POR或寄存器晶体管级时序。</p>'
 rel=tt['fault_release_before_permit'];settle=(tt['bias_recovery_settle_s']-20e-6)*1e9
 b['RECOVERY_EXPLANATION']=(f'故障撤销后BIAS峰{tt["bias_recovery_peak_v"]:.3f} V，约{settle:.2f} ns后稳定到最终值±1%；保护PWM在permit仍低时保持0。'
  f'恢复段另有{rel["branch_min_a"]*1e6:.3f} µA负支路峰，模型导电最大{rel["conduction_max_abs_a"]*1e15:.3f} fA，主要是电荷重分配；不能叫作提前亮脉冲。'
  '旧shunt撤销也存在位移峰，因此不将整个峰归因于新隔离。')
 fig,ax=plt.subplots(1,2,figsize=(7.25,2.45),layout='constrained')
 for row,label,color in [(base,'No isolation','#a3653f'),(tt,'CMOS TG isolation','#176e73')]:
  q=wave(row);idx=[n for n,x in enumerate(q['time_s']) if x<=.3e-6]
  ax[0].plot([q['time_s'][n]*1e9 for n in idx],[abs(q['i(VLEDLOAD)'][n])*1e9 for n in idx],label=label,color=color)
 ax[0].axhline(1,color='#899da1',ls='--',lw=1,label='1 nA guard');ax[0].set(yscale='log',xlabel='Reference startup time (ns)',ylabel='|LED branch| (nA)',ylim=(1e-6,10),xlim=(0,300));ax[0].legend(fontsize=7)
 q=wave(norm);idx=[n for n,x in enumerate(q['time_s']) if 514.4e-6<=x<=516e-6]
 ax[1].plot([(q['time_s'][n]-514.5e-6)*1e6 for n in idx],[q['i(VLEDLOAD)'][n]/norm['dc_full_a'] for n in idx],color='#176e73')
 ax[1].set(xlabel='Minimum-code start (µs)',ylabel='LED current / full-on',xlim=(-.1,1.5),ylim=(-.1,1.15))
 fig.savefig(BASE/'figures/startup-and-pwm.svg');plt.close(fig)
 tab='![同条件启动A/B与最低PWM码](figures/startup-and-pwm.svg)\n\n<p class="caption">图4　启动A/B共同使用finite-junction参考、Gear与100 ns ramp；区别是有无隔离。原报告5.791 nA来自zero-junction／Trap历史fixture，不直接用于该A/B比值。</p>\n\n'
 tab+='| 新实验，外部fault有效 | 结果 | 原门槛判断 |\n| --- | ---: | --- |\n'
 tab+=f'| TT匹配A/B启动峰 | {base["startup"]["branch_max_abs_a"]*1e9:.6f}→{tt["startup"]["branch_max_abs_a"]*1e9:.6f} nA | 失败→通过 |\n'
 tab+=f'| TT／SS／FF×3升速启动峰 | 最大{maxramp*1e9:.6f} nA | <1 nA |\n'
 dc=[r['startup_'+e+'_ramp100ns']['dc_full_a']*1e6 for e in ['tt','ss','ff']]
 tab+='| TT／SS／FF全开LED | '+'／'.join(f'{x:.5f}' for x in dc)+' µA | 均在100 µA±5% |\n'
 tab+=f'| TT最低码电荷误差 | {norm["area_error_pct"]:+.6f}% | <2% |\n'
 tab+='| 停钟fault→稳定<1 nA | '+'／'.join(f'{r["fault_"+e]["fault_to_safe_s"]*1e9:.3f}' for e in ['tt','ss','ff'])+' ns | 均<1 µs |\n'
 b['RESULTS_TABLE']=tab
 b['RESULTS_INTERPRETATION']='TT／27°C：logic=reference3.3 V、LED5 V；SS／85°C：2.97 V、4.5 V；FF／0°C：3.63 V、5.5 V。升速为100 ns／1 µs／10 µs；另测晚VSET和zero-junction敏感性，未覆盖任意独立供电。'
 b['SCOPE_COUNTS']=f'新实验{len(s["results"])} transient、{s["dc_runs"]} DC及{len(s["checks"])}检查；functional合同通过，整体passed=false。fault首1 µs Q+最大{max(r["fault_"+e]["fault"]["branch_charge"]["positive_c"] for e in ["tt","ss","ff"])*1e12:.4f} pC、|Q−|最大{max(abs(r["fault_"+e]["fault"]["branch_charge"]["negative_c"]) for e in ["tt","ss","ff"])*1e12:.4f} pC，分别低于10／20 pC预算。'
 c=conv['startup'];diag=c['numerical_resolution']
 b['CONVERGENCE_RESULTS']=(f'**修改后：** Gear的TT启动Q+为{c["coarse_charge_c"]:.4e}／{c["fine_charge_c"]:.4e} C；相对变化{c["change_pct"]:.4f}%，原严格项仍失败。'
 f'绝对差{diag["absolute_difference_c"]:.4e} C约为10 pC故障预算的{diag["difference_fraction_of_fault_10pC_budget"]:.3e}，只是附加数值诊断，不能替代原判据。'
 f'正常电荷与故障Q+步长变化分别{conv["normal"]["change_pct"]:.6f}%、{conv["fault"]["change_pct"]:.6f}%，通过原0.2%门槛。')
 b['NEW_BOUNDARIES']=('**已解决电路峰值问题，尚未关闭极小Q+严格相对收敛项。** 不把它按“低于一个电子”截断；SPICE电荷模型连续，实际仪器分辨率也未知。'
 '原5.79 nA失败、四MOS SS电流失败、求解器失败均保留。有限结面积候选的参考XPOUT曾有端子相对体端约+0.21674 V的小正偏；没有保存该体电流，不能据此量化衬底注入或判断可靠性。\n\n'
 '新传输门bulk接logic rail；当前reference与logic使用同名义电压、logic已有效。若reference高于logic或logic掉电，PMOS体结可能改变偏置和反灌路径；这只是待测风险，未声称已验证任意电源顺序。')
 b['NEXT_GATE']='当前选择CMOS传输门隔离继续研究，拒绝四MOS单NMOS方案。进入新版图前，先解释并关闭严格数值项，补全参考环路和真实R/C、跨rail及掉电合同；不以整体false的报告跳到制造提交。'
 sources=read('docs/research/startup-tapeout-20261014/fabrication-sources.json');ids=['GFSTATUS','OPDK','GFCAP','GFMIMDENSITY','GFEM','GFTAPE','WSPRECHECK','GFPAD']
 lookup={x['id']:x for x in sources['sources']}
 b['PRIMARY_SOURCES']='公开一级来源，2026-10-14核读；精确章节、版本、支持范围和本地hash另列：\n\n'+'\n'.join(f'- [{lookup[i]["title"]}]({lookup[i]["url"]})' for i in ids)
 b['REPRODUCTION']='```sh\nbuild/layout/venv/bin/python scripts/startup_v2/run.py --publish-evidence\nbuild/layout/venv/bin/python scripts/startup_v2/validate.py\n```\n\n第一条完整实验保留原严格失败，可能按设计返回非零；必须查看functional与legacy_relative标志。第二条是数据审计，不能把audit成功当全部实验成功。精确命令、raw与失败清单见[新实验说明](../../../evidence/startup-v2/README.md)。'
 (BASE/'report-blocks.json').write_text(json.dumps(b,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'blocks':len(b),'source_sha256':b['_source_summary_sha256'],'overall_experiment_passed':s['passed']}))
if __name__=='__main__':main()
