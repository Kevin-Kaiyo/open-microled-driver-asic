"""Render the dated teaching report from frozen new and historical evidence."""
from pathlib import Path
import csv, hashlib, html, json, re
import markdown
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/research/reference-safety-20261013'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads((ROOT/p).read_text())
def fmt(v,n=3):return f'{v:.{n}f}'
def waveform(path):
    rows=list(csv.DictReader((ROOT/path).open()))
    return {k:[float(x[k]) for x in rows] for k in rows[0]}
def main():
    BASE.mkdir(parents=True,exist_ok=True);(BASE/'figures').mkdir(exist_ok=True)
    blocks=json.loads((BASE/'report-blocks.json').read_text())
    s=read('evidence/current-range/summary.json')
    plt.rcParams.update({'font.family':'Avenir Next','svg.fonttype':'none','font.size':9,
                         'axes.spines.top':False,'axes.spines.right':False,'axes.labelcolor':'#263c43'})
    fig,ax=plt.subplots(1,2,figsize=(7.2,2.8),layout='constrained')
    for rail,color in [(5,'#a46a45'),(6,'#236979')]:
        rows=[x for x in s['DC'] if x['load']=='measured_static' and x['led_v']==rail]
        ax[0].plot([x['target_A']*1e3 for x in rows],[x['current_A']*1e3 for x in rows],label=f'{rail} V rail',color=color)
    ax[0].plot([.1,7],[.1,7],'--',color='#87969a',label='Target')
    ax[0].set(xlabel='Geometry target (mA)',ylabel='DC LED current (mA)',xlim=(0,7.2),ylim=(0,7.3));ax[0].legend(fontsize=8)
    cases=[('pwm_n1_d1_step5','1 unit','#849b9c'),('pwm_n70_d1_step5','70 units, IREF','#a46a45'),
           ('pwm70_ideal_voltage_switch10_d1','70 units, stiff bias + 10x switch','#236979')]
    for name,label,color in cases:
        row=next(x for x in s['PWM'] if x['name']==name);w=waveform(row['evidence_waveform'])
        full=next(x for x in s['PWM'] if x['units']==row['units'] and x['duty']==256
                  and x.get('bias_mode','ideal_current')==row.get('bias_mode','ideal_current')
                  and x.get('switch_scale',1)==row.get('switch_scale',1))['current_average_A']
        filtered=[(t,i) for t,i in zip(w['time_s'],w['LED_branch_A']) if 514.4e-6<=t<=516e-6]
        ax[1].plot([(t-514.5e-6)*1e6 for t,i in filtered],[i/full for t,i in filtered],label=label,color=color)
    ax[1].set(xlabel='Time from minimum-code start (µs)',ylabel='LED current / same-case full-on',xlim=(-.1,1.5),ylim=(-.05,1.08))
    ax[1].legend(fontsize=7,loc='lower center');fig.savefig(BASE/'figures/current-range.svg');plt.close(fig)
    d5=next(x for x in s['DC'] if x['load']=='measured_static' and x['led_v']==5 and x['units']==70)
    d6=next(x for x in s['DC'] if x['load']=='measured_static' and x['led_v']==6 and x['units']==70)
    syn=next(x for x in s['DC'] if x['load']=='synthetic' and x['units']==70)
    blocks['RANGE_RESULTS']='| 7 mA目标，理想IREF隔离输出问题 | 实际电流 | 相对目标 |\n| --- | --- | --- |\n'+ '\n'.join(
        f'| {label} | {x["current_A"]*1e3:.6f} mA | {x["error_pct"]:+.3f}% |'
        for label,x in [('公开静态LED／5 V',d5),('公开静态LED／6 V研究点',d6),('合成LED／5 V',syn)])
    lookup={x['name']:x for x in s['PWM']}
    errs=[lookup[n]['area_error_pct'] for n in ['pwm_n70_d1_step5','pwm70_ideal_current_switch10_d1',
                'pwm70_ideal_voltage_switch1_d1','pwm70_ideal_voltage_switch10_d1']]
    blocks['RANGE_DECISION']=(f'**机制对照：** 最低码误差从原结构{errs[0]:.3f}%，仅增大pass/clamp到10倍为{errs[1]:.3f}%；'
        f'仅改为理想低阻电压bias为{errs[2]:.3f}%，两者同时改变为{errs[3]:.3f}%。'
        '这支持bias供给与开关充电共同限制短脉冲。理想电压源只是定位机制，不是已完成bias buffer；'
        '6 V DC点也不是可靠性或允许LED电流认证。Q按514.5～1026.5 µs两完整帧signed电支路积分，'
        '用同条件全开×duty/256归一，不代表光功率。最终证据含143个电路DC、16个PWM和4个独立LED校准。')
    text=(BASE/'report-template.md').read_text()
    for name,value in blocks.items():text=text.replace('@@'+name+'@@',value)
    remaining=re.findall(r'@@[A-Z_]+@@',text)
    if remaining:raise ValueError('Unfilled report evidence: '+str(remaining))
    caption_index=0
    def number_caption(m):
        nonlocal caption_index
        caption_index+=1
        return '<p class="caption">图'+str(caption_index)+'　'
    text=re.sub(r'<p class="caption">图\d*\s*',number_caption,text)
    pages=text.split('<!-- PAGE -->')
    # Date-stable semantic headings; page numbering follows actual final sections.
    for i,p in enumerate(pages,1):
        if i>1:p=re.sub(r'^##\s+(?:\d+\s*　?\s*)?',f'## {i}　',p,count=1,flags=re.M)
        pages[i-1]=p
    text='<!-- PAGE -->'.join(pages);(BASE/'report.md').write_text(text)
    css='''@page{size:A4;margin:19mm 20mm 20mm}*{box-sizing:border-box}body{margin:0;color:#263c43;font:10.6pt/1.59 'Avenir Next','PingFang SC',sans-serif}h1,h2,h3{font-family:'Avenir Next','PingFang SC',sans-serif;color:#175664;line-height:1.25}h1{font-size:25pt;margin:0 0 4mm}h2{font-size:17pt;border-bottom:1px solid #b9cdd0;margin:0 0 4mm;padding-bottom:3mm}h3{font-size:12pt;margin:3mm 0 2mm}p{margin:0 0 3mm}a{color:#176778;text-decoration:none;overflow-wrap:anywhere}strong{color:#174c59}table{width:100%;border-collapse:collapse;font-size:9.2pt;line-height:1.45;margin:3mm 0}th{background:#edf3f3;text-align:left}th,td{padding:1.9mm 2mm;vertical-align:top;border-bottom:1px solid #dce5e5;overflow-wrap:anywhere}tr{break-inside:avoid}ul,ol{padding-left:5.8mm;margin:2mm 0 3mm}li{margin:1mm 0}img{display:block;width:100%;margin:2mm 0 1mm}.caption{font-size:8.6pt;color:#596f76;line-height:1.48;margin-bottom:3mm}.eq{padding:2.5mm 3mm;background:#f1f6f5;border-left:2px solid #3b7d88;font-size:10pt;line-height:1.55;margin:3mm 0}code{font-family:'Avenir Next','PingFang SC',sans-serif;font-size:.95em;overflow-wrap:anywhere}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f5f7f7;padding:3mm;font-size:8.5pt;line-height:1.45}blockquote{margin:3mm 0;padding:3mm;background:#edf5f3;border-left:3px solid #3c7c86}blockquote p:last-child{margin:0}.page{break-after:page}.page:last-child{break-after:auto}@media print{body,.page{width:170mm}}@media screen{body{background:#ecf1f1}.page{width:210mm;min-height:297mm;padding:19mm 20mm 20mm;margin:8mm auto;background:white;box-shadow:0 1px 8px #bac9ca}}'''
    sections=[f'<section class="page" data-page="{i}">'+markdown.markdown(p.strip(),extensions=['tables','fenced_code'])+'</section>' for i,p in enumerate(pages,1)]
    (BASE/'report.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>MicroLED 参考源、保护与架构研究 · 2026-10-14</title><style>'+css+'</style><body>'+''.join(sections)+'</body></html>\n')
    print(json.dumps(dict(sections=len(pages),report_sha256=sha(BASE/'report.md')),ensure_ascii=False))
if __name__=='__main__':main()
