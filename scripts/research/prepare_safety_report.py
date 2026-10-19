"""Create narrowly scoped safety prose and figures from frozen records."""
from pathlib import Path
import csv, hashlib, json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/research/reference-safety-20261013'
def read(p):return json.loads((ROOT/p).read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def table(headers,rows):return '| '+' | '.join(headers)+' |\n| '+' | '.join(['---']*len(headers))+' |\n'+'\n'.join('| '+' | '.join(map(str,r))+' |' for r in rows)
def wave(path):
    rows=list(csv.DictReader(path.open()));return {k:[float(r[k]) for r in rows] for k in rows[0]}
def main():
    core=read('evidence/safety/summary.json');servo=read('evidence/safety/servo-summary.json')
    stop=next(x for x in core['results'] if x['name']=='stop_high')
    valid=[x for x in core['results'] if x.get('fault_to_safe_current_s') is not None and not x.get('expected_negative_control_failure')]
    servo_stop=next(x for x in servo['results'] if 'stopped' in x['name'] or ('fault' in x['name'] and x.get('fault_to_safe_current_s') is not None))
    startup=next(x for x in servo['results'] if 'startup' in x and not x['name'].endswith('fine'))
    startup_fine=next(x for x in servo['results'] if 'startup' in x and x['name'].endswith('fine'))
    normal=next(x for x in servo['results'] if x.get('area_error_pct') is not None and not x['name'].endswith('fine'))
    blocks={}
    blocks['SAFETY_CIRCUIT']=('**新实现分两层。** RTL使用异步fault置位的inhibit记忆，只有fault低、显式recover_request和raw PWM低时才在时钟边沿恢复。'
        '晶体管层新增10MOS组合门，实现`protected = raw_PWM ∧ permit ∧ ¬fault`，接入原12MOS selected signal PEX。'
        '另加2MOS LED端钳位；恢复存储目前只有RTL证据，未做其晶体管与物理实现。')
    blocks['SAFETY_CONTRACT']=('**先验门槛：** 从RTL fault事件、即PWL开始上升的t0计；完整边沿10 ns，50%在t0+5 ns，仅作分账。'
        't0后1 µs内进入1 nA以下，t0+1～2 µs保持；[t0,t0+1 µs]正向尾电荷≤10 pC。'
        '钳位新增负向尾电荷20 pC、负峰10 mA及reverse0.5 V教学预算。'
        '这些不是真实LED或人身安全认证。FAULT必须在有效供电下有确定电平；1 MΩ外部pull-up研究断线默认关断。')
    blocks['SAFETY_RESULTS']=(table(['场景','进入并保持1 nA阈值','判断'],[
        ['core TT／停钟，fault直接路径',f'{stop["fault_to_safe_current_s"]*1e9:.2f} ns','原1 µs门槛通过'],
        ['core已测相位／TT、SS85、FF0',f'最长{max(x["fault_to_safe_current_s"] for x in valid)*1e9:.2f} ns','各声明场景通过'],
        ['实际servo＋停钟＋钳位',f'{servo_stop["fault_to_safe_current_s"]*1e9:.2f} ns','原故障门槛通过'],
        ['停钟，移除保护负对照','仍约100.75 µA','预期失效被检测']])+
        (f'\n\n**TT停钟尾电荷：** Q+={stop["tail_charge"]["positive_c"]*1e12:.3f} pC，Q−={stop["tail_charge"]["negative_c"]*1e12:.3f} pC；'
         f'电容分量signed约{stop["model_LED_capacitive_charge"]["signed_c"]*1e12:.3f} pC，导电分量约{stop["model_LED_conduction_charge"]["signed_c"]*1e12:.3f} pC。'
         '负支路电荷主要为电容处置；clamp rail约56.516 pC含电阻持续耗流，不能用signed LED电荷代表整个保护负担。'))
    blocks['SAFETY_LIMITATIONS']=(f'**附加全启动守卫仍失败。** 只让reference rail冷启动、逻辑和LED rail已有效、fault保持时，'
        f'整个启动窗branch峰约{startup["startup"]["LED_max_abs_current_a"]*1e9:.3f} nA；'
        'diode导电峰约3.24×10⁻¹⁷ A，电容为主。这个额外“全窗≤1 nA”守卫未通过，极小尾电荷步长变化也未闭环。'
        'Core22个transient／141项检查通过；servo联合suite整体passed=false，原正常／fault合同通过，附加startup两项仍失败。'
        '启动只有reference rail ramp100 ns，VSET固定0.5 V、logic3.3 V／LED5 V已有效，外部fault保持20 µs。'
        '\n\n正常PWM逻辑回归保持原合同；本次servo同fixture最低码面积约'
        f'{normal["area_error_pct"]:.6f}%。两帧514.5～1026.5 µs，以同fixture DC{normal["dc_full_a"]*1e6:.6f} µA×duty/256归一；'
        '使用10 ns输入刺激，不能同旧0.700133%或参考源独立回归直接排名。')
    (BASE/'safety-report-blocks.json').write_text(json.dumps(dict(summary_source_sha256=sha(ROOT/'evidence/safety/summary.json'),
        servo_source_sha256=sha(ROOT/'evidence/safety/servo-summary.json'),blocks=blocks),ensure_ascii=False,indent=2)+'\n')
    plt.rcParams.update({'font.family':'Avenir Next','svg.fonttype':'none','font.size':9,'axes.spines.top':False,'axes.spines.right':False})
    w=wave(ROOT/'evidence/safety/waveforms/stop_high/waveform.csv');origin=stop['conditions']['fault_ns']*1e-9
    fig,axes=plt.subplots(1,2,figsize=(7.2,2.8),layout='constrained')
    t=[(x-origin)*1e6 for x in w['time_s']]
    axes[0].plot(t,[x*1e6 for x in w['i(VLEDLOAD)']],color='#a36a49',label='LED branch')
    axes[0].plot(t,[(a-b)*1e6 for a,b in zip(w['@d.xled.dled[id]'],w['@d.xled.dled[capcur]'])],color='#236c7b',label='Diode conduction')
    axes[0].set(xlim=(-.04,.5),xlabel='Time from fault PWL start (µs)',ylabel='Current (µA)');axes[0].legend(fontsize=8)
    for name,label,color in [('stop_high','TT + active clamp','#236c7b'),('fault_ss','SS + active clamp','#a36a49')]:
        row=next(x for x in core['results'] if x['name']==name);data=wave(ROOT/f'evidence/safety/waveforms/{name}/waveform.csv')
        axes[1].semilogy([(x-row['conditions']['fault_ns']*1e-9)*1e6 for x in data['time_s']],
                         [max(abs(x)*1e9,1e-8) for x in data['i(VLEDLOAD)']],color=color,label=label)
    gate_path=ROOT/'evidence/safety-clamp-ab/clamp0_step2.csv'
    if gate_path.exists():
        old=wave(gate_path);axes[1].semilogy([(x-20.125e-6)*1e6 for x in old['time_s']],
            [max(abs(x)*1e9,1e-8) for x in old['LED_branch_A']],color='#899b9c',linestyle='--',label='Clamp disabled, same 10 ns slew')
    axes[1].axhline(1,color='#7b8b90',linewidth=.8,linestyle=':');axes[1].axvline(1,color='#7b8b90',linewidth=.8,linestyle=':')
    axes[1].set(xlim=(0,3.5),ylim=(1e-3,1e6),xlabel='Time from fault (µs)',ylabel='Absolute LED branch current (nA)');axes[1].legend(fontsize=7)
    fig.savefig(BASE/'figures/safety-waveform.svg');plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(7.2,2.5),layout='constrained')
    def events(name):
        rows=list(csv.DictReader((ROOT/f'evidence/safety/waveforms/{name}/rtl-events.csv').open()));collapsed={}
        for row in rows:
            if 513500<=float(row['time_ns'])<=771500:collapsed[float(row['time_ns'])]=row
        # Carry the last known values at the window left boundary.
        prior=[r for r in rows if float(r['time_ns'])<513500 and all(r[k] in ['0','1'] for k in ['raw_pwm','protected_pwm','fault'])]
        if prior:collapsed[513500.0]=prior[-1]
        if collapsed:collapsed[771500.0]=collapsed[max(collapsed)]
        return sorted(collapsed.items())
    values=events('fault_d1_phase375')
    for level,key,label,color in [(4,'raw_pwm','Raw PWM, duty=1','#829b9d'),(2,'fault','Fault','#a36a49'),(0,'protected_pwm','Protected PWM','#236c7b')]:
        axes[0].step([(t-514500)/1000 for t,r in values],[level+int(r[key]) for t,r in values],where='post',label=label,color=color)
    axes[0].set(xlim=(-.1,2),ylim=(-.2,5.3),yticks=[.5,2.5,4.5],yticklabels=['Protected','Fault','Raw PWM'],xlabel='Time from frame start (µs)')
    for name,level,label,color in [('normal_d1',2,'duty=1','#236c7b'),('normal_d64',0,'duty=64','#a36a49')]:
        values=events(name);axes[1].step([(t-514500)/1000 for t,r in values],[level+int(r['raw_pwm']) for t,r in values],where='post',label=label,color=color)
    axes[1].set(xlim=(-1,257),ylim=(-.2,3.3),yticks=[.5,2.5],yticklabels=['duty=64','duty=1'],xlabel='One 256 µs frame (µs)')
    fig.savefig(BASE/'figures/pwm-timing.svg');plt.close(fig)
    print(json.dumps(dict(core_passed=core['passed'],servo_suite_passed=servo['passed'],core_fault_max_ns=max(x['fault_to_safe_current_s'] for x in valid)*1e9)))
if __name__=='__main__':main()
