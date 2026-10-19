"""Derive report tables and decisions from the new experiment records."""
from pathlib import Path
import csv, json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/research/reference-safety-20261013'
def read(p):return json.loads((ROOT/p).read_text())
def table(headers,rows):return '| '+' | '.join(headers)+' |\n| '+' | '.join(['---']*len(headers))+' |\n'+'\n'.join('| '+' | '.join(map(str,r))+' |' for r in rows)
def main():
    beta=read('evidence/reference/beta-summary.json');servo=read('evidence/reference/servo-summary.json')
    safety=read('evidence/safety/summary.json')
    blocks={}
    blocks['REFERENCE_CIRCUIT']=('**候选A：beta multiplier。** 两个相同PMOS镜像支路使NMOS电流接近相等；N2的W/L为N1的4倍，'
        '源极电阻产生VGS差，形成非零偏置。第三个PMOS把电流送到像素MREF。'
        '弱PMOS、感测NMOS与kick NMOS构成启动支路；当NB升高，kick逐渐关闭。'
        '本次8只MOS＋实际PDK ppolyf_u电阻模型，未使用内部理想电流源或理想运放。')
    blocks['REFERENCE_EQUATIONS']=('<div class="eq">忽略体效应及有限ro：I ≈ 2(1−1/√K)²/(β1R²)，K=4<br>'
        'β1=μnCox(W/L)1；R与μn变化会改变绝对电流。</div>'
        '\n\n电阻W=2 µm、L=13.5 µm仅在TT/27°C/3.3 V、输出负载1.4 V处校准。'
        'N2源极升高产生体效应，两个PMOS漏压也不同，故公式用于理解依赖关系，实际电流由完整模型求解。')
    blocks['REFERENCE_RESULTS']=table(['候选A验证','新仿真结果','判断'],[
        ['独立名义参考，输出1.4 V',f'{beta["nominal"]["iref_a"]*1e6:.6f} µA','一个校准点通过'],
        [f'{beta["pvt"]["n"]}个离散组合',f'{beta["pvt"]["min_iref_a"]*1e6:.3f}～{beta["pvt"]["max_iref_a"]*1e6:.3f} µA',f'{beta["pvt"]["failed_absolute_budget"]}/{beta["pvt"]["n"]}超±5%'],
        ['实际模拟RC耦合，TT全开',f'{next(x for x in beta["coupled_dc"] if x["envelope"]=="tt" and x["resistor_corner"]=="res_typical" and x["pwm_on"])["iout_a"]*1e6:.6f} µA','仅该点绝对电流通过']])
    blocks['REFERENCE_DECISION']=('**判断：启动能力与电流精度分开。** 5个MOS corner×3个独立电阻corner×3温度×3逻辑电源构成135点；'
        '它是离散条件网格，不是制造概率。多数点失败，不能把这只未修调beta源选作当前精密100 µA主方案。'
        '保留它作为“由器件产生参考”及启动对照，再研究外部精密设定与反馈。')
    blocks['SERVO_CIRCUIT']=('**候选B：外部设定电压＋实际MOS反馈。** 10只GF180 MOS中，PMOS输入对比较VSET与VSENSE，'
        'NMOS镜像负载与共源第二级驱动CTRL；PREG经RSET建立检测电流，匹配长沟道POUT向像素BIAS供电。'
        '另有真实二极管PMOS／RBIAS生成放大器偏置，CCOMP=3 pF作名义Miller补偿。'
        '若VSET高于VSENSE，CTRL下降、PMOS供电增加，反馈使VSENSE上升。')
    coupled=servo['coupled_dc'];on=[x for x in coupled if x['pwm_on']]
    nominal_on=next(x for x in on if x['envelope']=='tt' and x.get('vset_error_fraction',0)==0 and x.get('rset_error_fraction',0)==0)
    blocks['SERVO_RESULTS']=table(['候选B验证','结果','原±5%目标'],[
        ['独立名义参考／负载1.4 V',f'{servo["nominal"]["iref_a"]*1e6:.6f} µA；VSENSE={servo["nominal"]["sense_v"]:.6f} V','通过'],
        [f'{servo["pvt"]["n"]}点，含外部设定误差',f'{servo["pvt"]["min_iref_a"]*1e6:.3f}～{servo["pvt"]["max_iref_a"]*1e6:.3f} µA',f'{servo["pvt"]["failed_absolute_budget"]}点超限'],
        ['模拟RC耦合TT全开LED',f'{nominal_on["iout_a"]*1e6:.6f} µA','通过'],
        ['已测耦合开启条件',f'{min(x["iout_a"] for x in on)*1e6:.3f}～{max(x["iout_a"] for x in on)*1e6:.3f} µA','分别记录包络与外部边界']])
    blocks['SERVO_DECISION']=('**精度来自哪一部分？** 名义VSENSE/RSET约99.866 µA，而POUT约99.252 µA；'
        '前者有有限环路增益误差，后者还因PMOS输出与PREG漏压不同出现镜像比误差。'
        '接入像素后，NMOS镜像比又改变ILED，名义值接近100 µA不能被解释为误差消失。'
        '180点是5MOS角×3温度×3电源×4组VSET/RSET误差符号；未包含随机失配、噪声、实物漂移或全芯片网络。'
        f'名义reference供电{servo["nominal"]["supply_a"]*1e6:.1f} µA，约{3.3*servo["nominal"]["supply_a"]*1e3:.3f} mW，'
        '包含内部偏置及参考负载供能，尚非全芯片功耗。')
    zero=next(x for x in beta['startup'] if x['kind']=='zero' and x['envelope']=='tt' and x['startup_enabled'])
    off=next(x for x in beta['startup'] if x['kind']=='zero' and x['envelope']=='tt' and not x['startup_enabled'])
    cold=[x for x in servo['startup'] if x['kind']=='cold']
    hard=[x for x in servo['startup'] if x['kind']=='initial']
    # Summary uses explicit kind labels; never silently infer an absent test.
    if not hard:hard=[x for x in servo['startup'] if x['kind'] not in ['cold','step']]
    blocks['REFERENCE_STARTUP']=(f'**候选A零态对照：** 启动开启后，TT最终约{zero["last_10us_mean_a"]*1e6:.3f} µA，'
        f'进入最终值±1%约{zero["settling_after_rail_s"]*1e9:.1f} ns；禁用kick最终仅约{off["last_10us_mean_a"]*1e12:.2f} pA，仍停在零态。'
        '\n\n**零结面积主候选B不是无过冲启动。** 已测9个冷ramp、6个硬初态和3个VSET阶跃均最终恢复；'
        f'冷启动的参考输出峰值最高约{max(x["peak_current_a"] for x in cold)*1e6:.1f} µA；'
        f'硬初态峰值最高约{max(x["peak_current_a"] for x in hard)*1e3:.3f} mA，VSENSE最低{min(x["sense_min_v"] for x in hard):.3f} V。'
        '这些是参考端／MREF负载的电流，不能冒称LED峰值。需外部fault默认保持到偏置稳定；实际POR与brownout尚未实现。')
    blocks['PWM_REGRESSION']=('**正常时序保持：** 1 MHz时钟→1 µs slot→256 µs frame→3906.25 Hz。'
        'duty0全关、256全开，超过256 clamp；duty/enable仅在frame boundary更新。'
        '故障中断允许缩短当前脉冲，不能对该中断套用正常最短脉冲宽度要求。'
        '\n\n**参考源接入的真实RTL回归：** 候选B在TT、SS85°C与FF0°C的最低码电荷最大绝对误差分别'+
        '、'.join(f'{max(abs(v) for x in servo["pwm"] if x["envelope"]==c and x.get("duty")==1 for v in x["charge_error_pct"]):.4f}%' for c in ['tt','slow','fast'])+
        '，按同条件全开DC归一化，均低于2%。本组为servo＋既有模拟RC像素、1 ns PWM边沿，'
        '不含保护gate/clamp或旧12MOS joint切口；不能与保护联测的−0.032016%直接比较。10→2 ns是最大求解步长对照。')
    # Safety prose is kept in its own small, source-linked adapter below.
    blocks.update(safety_blocks(safety))
    blocks['NEW_RUN_SUMMARY']='8MOS beta与10MOS反馈参考候选、独立fault路径及0.1～7 mA几何／充电实验'
    blocks['FINAL_DECISIONS']=('1. **参考源主线采用外部VSET＋精密RSET的反馈候选继续研究。** beta保留作失败／启动对照。'
        '反馈候选已有离散条件下的精度证据，外部基准、失配、补偿与实物还需核查。\n'
        '2. **正常PWM与保护分开。** 保护保留直接fault优先、显式恢复及LED端节点处置；启动必须保持fault，不能只等待frame。\n'
        '3. **7 mA另立输出级规格。** 先确定目标LED与rail、MOS余量、单位电流分辨率，再实现bias驱动和开关；'
        '理想低阻bias对照不能当已完成7 mA平台。\n'
        '4. **高速作为独立单通道研究。** 先定符号率／电流／负载及误码目标，比较direct OOK与current steering；'
        '多级DAC在两档链路证据后推进。\n'
        '5. **完成新单像素模块的layout与真实PG、LED测量后，再决定物理4×4。** 保留可复现的源、失败和门槛。')
    blocks['REPRODUCTION']='```sh\nuv run python scripts/current_range/run.py\nuv run python scripts/current_range/validate.py\n'+safety.get('reproduction_command','uv run python scripts/safety/run.py')+'\n```\n\n参考源与报告的精确命令见[复现说明](README.md)。所有工具输出在独立build目录，紧凑证据和输入hash保存在evidence；重跑不会把失败改成通过。'
    (BASE/'report-blocks.json').write_text(json.dumps(blocks,ensure_ascii=False,indent=2)+'\n')
    plt.rcParams.update({'font.family':'Avenir Next','svg.fonttype':'none','font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    for prefix,name,title in [('', 'reference-dc.svg','Beta: fixed MOS / resistor / temperature / rail conditions'),('servo-', 'reference-servo-dc.svg','Servo: fixed conditions with bounded external VSET / RSET')]:
        rows=list(csv.DictReader((ROOT/f'evidence/reference/{prefix}pvt.csv').open()))
        fig,ax=plt.subplots(figsize=(7.2,2.5),layout='constrained')
        for k,corner in enumerate(['typical','ss','ff','fs','sf']):
            values=[float(x['iref_a'])*1e6 for x in rows if x['corner']==corner]
            ax.vlines(k,min(values),max(values),color='#276c7c',linewidth=5,alpha=.7)
            ax.scatter([k,k],[min(values),max(values)],color='#276c7c',s=18)
        ax.axhspan(95,105,color='#e4efea');ax.axhline(100,color='#87999a',linestyle='--',linewidth=1)
        ax.set(xticks=range(5),xticklabels=['TT','SS','FF','FS','SF'],ylabel='Reference output (µA)',xlabel=title)
        if prefix:ax.set_ylim(95,105.5)
        fig.savefig(BASE/'figures'/name);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(7.2,2.8),layout='constrained')
    for row,label,color in [(zero,'Startup enabled','#216979'),(off,'Kick disabled','#a06b48')]:
        a=np.loadtxt(ROOT/row['raw_waveform'],skiprows=1)
        axes[0].plot(a[:,0]*1e6,a[:,1]*1e6,label=label,color=color)
    axes[0].set(xlim=(0,.25),xlabel='Hard zero-state time (µs)',ylabel='Beta reference output (µA)');axes[0].legend(fontsize=8)
    for env,color in [('tt','#216979'),('fast','#a06b48')]:
        row=next(x for x in cold if x['envelope']==env and abs(x['rise_s']-1e-7)<1e-15)
        a=np.loadtxt(ROOT/row['raw_waveform'],skiprows=1)
        axes[1].plot(a[:,0]*1e6,a[:,1]*1e6,label=env,color=color)
    axes[1].set(xlim=(0,1.5),xlabel='100 ns cold-rail ramp time (µs)',ylabel='Servo reference output (µA)');axes[1].legend(fontsize=8)
    fig.savefig(BASE/'figures/reference-startup.svg');plt.close(fig)
    print(json.dumps(dict(blocks=len(blocks),beta_points=beta['pvt']['n'],servo_points=servo['pvt']['n'])))

def safety_blocks(s):
    # Added after the safety experiment final schema is frozen.
    adapter=read('docs/research/reference-safety-20261013/safety-report-blocks.json')
    if adapter['summary_source_sha256']!=__import__('hashlib').sha256((ROOT/'evidence/safety/summary.json').read_bytes()).hexdigest():
        raise ValueError('Safety report prose belongs to a different experiment summary')
    return adapter['blocks']
if __name__=='__main__':main()
