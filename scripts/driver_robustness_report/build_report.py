#!/usr/bin/env python3
"""Render the existing research-report format from reviewed Markdown and real rows."""
from pathlib import Path
import csv, hashlib, html, json, re
import markdown
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'docs/research/driver-robustness-20261024'
ENERGY='rail_plus_DATA_positive_draw_fJ_per_gross_bit'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads((ROOT/p).read_text())
def fmt(x,n=3):return '—' if x is None else f'{x:.{n}f}'
def table(head,rows):
    return '<div class="scroll"><table><thead><tr>'+''.join('<th>'+html.escape(str(x))+'</th>' for x in head)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+str(x)+'</td>' for x in row)+'</tr>' for row in rows)+'</tbody></table></div>'
def result_table(rows):
    rr=[]
    for r in rows:
        if 'dc_bit' in r:continue
        status='通过' if r.get('combined_screen_passed') else ('未通过' if r.get('analysis_ok') else '仿真失败')
        margin=r.get('minimum_device_specific_margin_V',r.get('terminal_screen_margin_V'))
        rr.append([r['route'],html.escape(r['kind']),f"{r['rate_Gbps']:g}",f"{r['corner']} / {r['temp_C']:g} / {r['vdd_V']:g}",html.escape(str(r.get('res_corner','—'))),r.get('errors','—'),fmt(r.get('threshold_margin_normalized'),4),fmt(r.get('timing_min_margin_ui'),4),fmt(r.get('max_abs_terminal_V'),4),fmt(margin*1000 if margin is not None else None,2),fmt(r.get(ENERGY),2),f'<span class="{"pass" if status=="通过" else "fail"}">{status}</span>'])
    return table(['路线','实验条件','Gb/s','MOS / °C / VDD(V)','电阻角','错误/511','垂直余量','水平/UI','最大端差/V','器件最小余量/mV','fJ/gross bit','联合判定'],rr)
def figure(name,caption):
    return f'<figure><a href="figures/{name}.svg"><img src="figures/{name}.svg" alt="{html.escape(caption)}" loading="lazy"></a><figcaption>{caption} 点击查看完整 SVG。</figcaption></figure>'
def same_energy_rows(rows):
    out=[]
    for label,a,b in [('TT / 3.3 V','TT_rate04','TT_common04'),('SS / 2.95 V','SSminus50_rate04','SSminus50_common04'),('FF / 3.65 V','FFplus50_rate04','FFplus50_common04')]:
        aa=[r for r in rows if r['route']=='A' and r['kind']==a and r['rate_Gbps']==.4];bb=[r for r in rows if r['route']=='B' and r['kind']==b and r['rate_Gbps']==.4]
        if not aa or not bb:continue
        a,b=aa[0],bb[0];assert a['combined_screen_passed'] and b['combined_screen_passed']
        out.append([label,fmt(a[ENERGY],2),fmt(b[ENERGY],2),fmt((b[ENERGY]/a[ENERGY]-1)*100,2)+'%',fmt(a['timing_min_margin_ui'],4)+' / '+fmt(b['timing_min_margin_ui'],4)])
    return out

def matched_rows(old,new):
    out=[]
    for route,rate,kind in [('A',1,'FFplus50_1G'),('B',.5,'FFplus50')]:
        for label,rows,k in [('旧03v3',old,'FFplus50_tracking'),('新实际器件',new,kind)]:
            r=next(r for r in rows if r['route']==route and r['kind']==k and r['rate_Gbps']==rate)
            out.append([f'{route} / {rate:g}G / {label}',fmt(r['max_abs_terminal_V'],6),fmt(r['minimum_device_specific_margin_V'],6),fmt(r['threshold_margin_normalized'],4),fmt(r['timing_min_margin_ui'],4),fmt(r[ENERGY],2),'通过' if r['combined_screen_passed'] else '电压未通过'])
    return out

def main():
    cfg=json.loads((OUT/'report-config.json').read_text())
    baseline=load(cfg['baseline_summary']); final=load(cfg['final_summary']); final=final.get('selected',final)
    text=(OUT/'report.md').read_text()
    for token,path in [('PWM_SECTION','pwm-section.md'),('PHYSICAL_SECTION','physical-section.md')]:
        section=(OUT/path).read_text()
        if token=='PWM_SECTION':
            section='\n'.join(section.splitlines()[1:]);section=re.sub(r'^## ', '### ',section,flags=re.M)
        else:section=re.sub(r'^(#{2,5}) ',r'#\1 ',section,flags=re.M)
        text=text.replace('<!-- '+token+' -->',section)
    replacements={
       'nrztargets':result_table([r for r in final['rows'] if r['kind'] in cfg['target_kinds'] and r.get('rate_Gbps') in cfg['target_rates']]),
       'nrzmatrix':result_table(final['rows']),
       'sameenergy':table(['条件，均0.4 Gb/s','A正向 fJ/bit','B正向 fJ/bit','B相对A取能增幅','A/B水平余量/UI'],same_energy_rows(final['rows'])),
       'matchedcomparison':table(['FF/−40°C，VDD与DATA高均3.65 V','最大端差/V','器件最小余量/V','垂直余量','水平/UI','正向 fJ/bit','联合判定'],matched_rows(baseline['rows'],final['rows'])),
       'nrzdc':table(['路线','条件','MOS / 温度','VDD/V','数据位','LED/uA','相对原目标误差/%'],[[r['route'],html.escape(r['kind']),f"{r['corner']} / {r['temp_C']}°C",r['vdd_V'],r['dc_bit'],fmt(r.get('LED_current_A',0)*1e6,4),fmt(r.get('LED_current_error_percent'),3)] for r in final['rows'] if 'dc_bit' in r]),
       'baselinematrix':result_table(baseline['rows']),
       'voltagefigure':figure('nrz-voltage-budget','旧薄栅氧核心供电扫描；3.600 V点引用10月23日原证据，其余为本轮；各路线用原目标速率。'),
       'aschematic':figure('voltage-schematic','A 的实际候选连接：全摆幅 MOS 改为06v0，输入阻尼与局部体接触分别设计。图中未展开互连寄生。'),
       'bschematic':figure('steering-schematic','B 的实际候选连接：全摆幅反相器与转向管采用06v0，3只偏置MOS保留03v3。')}
    for k,v in replacements.items():text=text.replace('{{'+k+'}}',v)
    if '{{' in text:raise ValueError('Unresolved report token')
    body=markdown.markdown(text,extensions=['tables','fenced_code','toc'])
    css=(ROOT/'docs/research/highspeed-nrz-pvt-20261023/report.css').read_text()+'\nimg{max-width:100%}th,td{white-space:normal}.scroll th,.scroll td{white-space:nowrap}h4{font-size:18px}td{overflow-wrap:anywhere}.scroll{max-height:760px}table thead th{position:sticky;top:0}details .scroll{max-height:650px}.status{color:#5c747c;font-size:14px}\n'
    (OUT/'report.css').write_text(css)
    page='<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>MicroLED驱动器：供电、电阻角与封装扰动验证</title><link rel="stylesheet" href="report.css"></head><body><main><p class="eyebrow">OPEN MICROLED DRIVER ASIC / 2026-10-24 / 实验性研发方法验证与教学</p>'+body+'</main></body></html>\n'
    (OUT/'index.html').write_text(page)
    inputs=[ROOT/'evidence/highspeed-nrz-pvt/summary.json',ROOT/'evidence/highspeed-nrz-robustness-layout/final-selection.json',OUT/'sources.json',OUT/'report.md',OUT/'report-config.json',OUT/'pwm-section.md',OUT/'physical-section.md',ROOT/cfg['baseline_summary'],ROOT/cfg['final_summary']]
    inputs += [ROOT/'evidence/highspeed-nrz-robustness/baseline-A-supply-return-window-global.csv',ROOT/'evidence/highspeed-nrz-robustness/baseline-A-supply-return-window-global.json',ROOT/'evidence/highspeed-nrz-robustness/final-A-supply-return-window-matched.csv',ROOT/'evidence/highspeed-nrz-robustness/final-A-supply-return-window-matched.json',ROOT/'evidence/pwm-robustness/20261024/summary.json',ROOT/'evidence/pwm-robustness/20261024/validation.json',ROOT/'evidence/pwm-robustness/20261024/final-audit.json',ROOT/'evidence/highspeed-nrz-robustness/sampler-discrete-points-source.json',ROOT/'evidence/highspeed-nrz-robustness/baseline-A-supply-return-window.csv',ROOT/'evidence/highspeed-nrz-robustness/baseline-A-supply-return-window.json',ROOT/'build/blender-pwm-animation/fonts/NotoSansCJKsc-Regular.otf',OUT/'geometry.json',OUT/'layout-viewer.html']
    provenance={'date':'2026-10-24','status':cfg['status'],'generator_sha256':sha(Path(__file__)),'inputs':{str(p.relative_to(ROOT)):sha(p) for p in inputs},'html_sha256':sha(OUT/'index.html'),'figures':{str(p.relative_to(OUT)):sha(p) for d in ['figures','pwm-figures'] for p in sorted((OUT/d).glob('*')) if p.suffix in ['.svg','.png']},'authoring_sources':{str(p.relative_to(ROOT)):sha(p) for d in ['scripts/driver_robustness_report','scripts/pwm_robustness'] for p in sorted((ROOT/d).glob('*.py'))},'shared_circuit_drawing_sha256':sha(ROOT/'scripts/highspeed_routes/circuits.py')}
    (OUT/'report-provenance.json').write_text(json.dumps(provenance,ensure_ascii=False,indent=2)+'\n')
    columns=['route','kind','dc_bit','LED_current_A','LED_current_error_percent','rate_Gbps','corner','temp_C','vdd_V','res_corner','r_pkg','l_pkg','analysis_ok','errors','threshold_margin_normalized','timing_min_margin_ui','max_abs_terminal_V','minimum_device_specific_margin_V',ENERGY,'combined_screen_passed','result_json','analysis_json']
    with (OUT/'nrz-final-data.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=columns,extrasaction='ignore');w.writeheader();w.writerows(final['rows'])
    print(json.dumps({'html':str(OUT/'index.html'),'baseline_rows':len(baseline['rows']),'final_rows':len(final['rows']),'status':cfg['status']}))
if __name__=='__main__':main()
