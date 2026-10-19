"""Reproduce the public study: independent illustrative figures, calculations and HTML."""
from pathlib import Path
import hashlib
import html
import json
import math
import subprocess

import markdown
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/research/driver-circuit-layout-20261012'
FIG = BASE / 'figures'


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def svg(name, width, height, body):
    (FIG / name).write_text(f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img">
<style>text{{font-family:'Avenir Next','PingFang SC',sans-serif;fill:#24353c;font-size:17px}}.title{{font-size:21px;fill:#164f5b;font-weight:600}}.small{{font-size:14px;fill:#526b73}}.line{{stroke:#397e83;stroke-width:2;fill:none}}.box{{fill:#edf4f3;stroke:#a7c3c1;stroke-width:1.5}}</style>
<defs><marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10" fill="#397e83"/></marker></defs>
<rect width="{width}" height="{height}" fill="#fff"/>{body}</svg>\n''')


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    vf = 3.767909545
    calculations = {
        'study_date': '2026-10-12',
        'classification': 'Calculations, not new EDA or physical/optical measurements',
        'led_headroom': {'formula': 'Vrail - Vf', 'Vrail_V': 5.0, 'Vf_at_100uA_V': vf,
            'remainder_V': 5.0-vf, 'source': 'Independent interpolation of one public 20 um yellow static curve; temperature unknown; no dynamic model'},
        'oxide_scale': {'formula': 'Cox * W * L', 'Cox_fF_per_um2': 2.3, 'W_um': 20, 'L_um': 4,
            'scale_fF': 2.3*20*4, 'scope': 'Geometric oxide scale only; not Cgg or LED/PEX C'},
        'single_pole_RC': {'formula': 'ln(9) * R * C', 'hypothetical': True, 'R_ohm': 100,
            'C_pF': [1, 10], 'rise_ps': [math.log(9)*100*c*1e-12*1e12 for c in [1, 10]],
            'scope': 'Single-pole linear 10-90% electrical response; not optical bandwidth or BER'},
        'inductive_return': {'formula': 'L * channels * deltaI_per_channel / edge_time',
            'hypothetical': True, 'L_nH': .5, 'channels': 16, 'deltaI_per_channel_mA': 1,
            'edge_ps': 100, 'deltaV_mV': .5e-9*16*.001/(100e-12)*1000,
            'scope': 'Inductive term only; actual individual rail current steps must be determined'},
        'storage_drift': {'formula': 'Ileak * hold / Cstore', 'hypothetical': True,
            'Ileak_pA': 1, 'hold_us': 100, 'Cstore_fF': 100,
            'deltaV_mV': 1e-12*100e-6/100e-15*1000},
        'historical_size_tradeoff': {'classification': 'Derived from saved v0.2 analog-only RC evidence',
            'old_cell_um2': 2532.7, 'new_cell_um2': 3577.7,
            'area_increase_pct': (3577.7/2532.7-1)*100,
            'old_sigma_uA': .79380, 'new_sigma_uA': .38428, 'n_each': 256,
            'sigma_reduction_pct': (1-.38428/.79380)*100,
            'scope': 'Nominal local-only model sampling, not current joint MC or silicon yield'},
        'hypothetical_RLED_10kohm': {'classification': 'Arithmetic on saved transistor simulation',
            'Iout_uA': 88.265992, 'target_uA': 100,
            'error_pct': (88.265992/100-1)*100},
        'common_centroid': {'classification': 'Proposed equal unit-device centers; not implemented layout',
            'A_xy': [[0,0],[3,0],[1,1],[2,1]], 'B_xy': [[1,0],[2,0],[0,1],[3,1]],
            'A_centroid': [1.5,.5], 'B_centroid': [1.5,.5],
            'scope': 'Identical unit weights, linear gradient only'}
    }
    (BASE/'calculations.json').write_text(json.dumps(calculations,ensure_ascii=False,indent=2)+'\n')

    svg('architectures.svg',900,318,'''<text x="20" y="30" class="title">Gate-bias PWM</text><text x="468" y="30" class="title">Current steering</text>
<text x="20" y="54" class="small">当前像素的功能示意</text><text x="468" y="54" class="small">待比较的机制示意，未实现</text>
<rect x="20" y="91" width="110" height="48" rx="6" class="box"/><text x="34" y="120">IREF / bias</text>
<path d="M130 115 H162" class="line" marker-end="url(#arrow)"/>
<rect x="166" y="91" width="105" height="48" rx="6" class="box"/><text x="182" y="120">pass / clamp</text>
<path d="M218 139 V173 H260 V206 H280" class="line" marker-end="url(#arrow)"/><text x="175" y="80" class="small">gate偏置</text>
<rect x="281" y="185" width="109" height="43" rx="6" class="box"/><text x="304" y="213">电流管</text>
<text x="301" y="75">LED rail</text><path d="M335 81 V103" class="line"/>
<rect x="303" y="111" width="64" height="39" rx="6" class="box"/><text x="318" y="137">LED</text>
<path d="M335 150 V185 M335 228 V251 H281" class="line" marker-end="url(#arrow)"/><text x="290" y="273" class="small">return</text>
<path d="M80 189 H155 V129 H164" class="line" marker-end="url(#arrow)"/><text x="168" y="209">PWM / 反相</text>
<path d="M445 65 V278" stroke="#d4dfdf"/>
<text x="506" y="82">LED rail</text><text x="706" y="82">dummy rail</text>
<rect x="514" y="96" width="100" height="44" rx="6" class="box"/><text x="543" y="125">LED</text>
<rect x="723" y="96" width="100" height="44" rx="6" class="box"/><text x="742" y="125">dummy</text>
<path d="M564 140 V159 H670 M773 140 V159 H670 V177" class="line"/>
<rect x="601" y="178" width="139" height="39" rx="6" class="box"/><text x="622" y="204">差分支路切换</text>
<path d="M670 217 V230" class="line"/><rect x="590" y="232" width="160" height="37" rx="6" class="box"/><text x="610" y="257">已偏置的电流源</text>
<path d="M670 269 V286 H588" class="line" marker-end="url(#arrow)"/><text x="772" y="203" class="small">data / pre-driver</text>
<text x="20" y="304" class="small">原创建模示意；未画全晶体管、电源、cascode、寄生及保护结构</text>''')
    svg('headroom.svg',900,220,f'''<text x="20" y="32" class="title">100 µA 静态点的余量预算</text>
<rect x="30" y="75" width="{760*vf/5:.3f}" height="55" fill="#397e83"/>
<rect x="{30+760*vf/5:.3f}" y="75" width="{760*(5-vf)/5:.3f}" height="55" fill="#c6d9d3"/>
<text x="55" y="110" style="fill:white">LED Vf ≈ 3.76791 V</text><text x="615" y="108">余量 ≈ 1.23209 V</text>
<text x="30" y="160">5 V rail − Vf；当前支付输出管与支路压降，新拓扑还要预算串联器件</text>
<text x="30" y="191" class="small">计算：一条20 µm yellow LED公开静态曲线；温度未确认，不是动态验证</text>''')
    rows=['D D D D D D','D A B B A D','D B A A B D','D D D D D D']
    cells=[]
    for iy,row in enumerate(rows):
        for ix,letter in enumerate(row.split()):
            x,y=28+ix*53,63+iy*42
            fill={'A':'#397e83','B':'#b5d2c8','D':'#e8eded'}[letter]
            color='white' if letter=='A' else '#24353c'
            cells.append(f'<rect x="{x}" y="{y}" width="47" height="35" rx="4" fill="{fill}"/><text x="{x+17}" y="{y+24}" style="fill:{color}">{letter}</text>')
    svg('matching.svg',900,269,'''<text x="20" y="31" class="title">相同单位管的对称布局概念</text>'''+''.join(cells)+'''<text x="382" y="91">A / B 的加权质心相同</text><text x="382" y="123">D 为边缘虚设晶体管，连接须单独设计</text><text x="382" y="157">栅极 / 源极 / 漏极连接仍需相似寄生与偏置</text><text x="382" y="191">降低一阶梯度影响；不消除随机失配</text><text x="20" y="250" class="small">拟采用的排列；不是实际掩膜版图。当前为两个独立单元，尚未实现此结构</text>''')
    plt.rcParams.update({'font.family':'Avenir Next','svg.fonttype':'none','font.size':11,'axes.labelcolor':'#24353c','text.color':'#24353c','axes.edgecolor':'#a2b8bd'})
    fig,ax=plt.subplots(figsize=(8.7,2.8),layout='constrained')
    c=np.logspace(-1,1,101)
    for r,col in [(50,'#89b4aa'),(100,'#397e83'),(500,'#274450')]:
        ax.loglog(c,math.log(9)*r*c*1e-3,color=col,label=f'R = {r} ohm')
    ax.set(xlabel='Hypothetical lumped C (pF)',ylabel='10-90% rise time (ns)',title='Illustrative single-pole RC sensitivity')
    ax.grid(alpha=.18,which='both');ax.legend(frameon=False,ncol=3,loc='upper left')
    ax.spines[['top','right']].set_visible(False)
    fig.savefig(FIG/'rc-sensitivity.svg');plt.close(fig)

    from driver_circuit_figures import main as render_component_figures
    render_component_figures()

    for diagram in FIG.glob('*.svg'):
        diagram.write_text('\n'.join(line.rstrip() for line in diagram.read_text().splitlines())+'\n')

    old=json.loads((ROOT/'docs/research/driver-literature-20261012/sources.json').read_text())
    ids={'G03','G04','G05','C01','H03','H05','H06','T03','T04','T05','T08'}
    records=[x for x in old['records'] if x['id'] in ids]
    extra=[
        ('G-MATCH','GF180 matched pair layout guidelines','https://gf180mcu-pdk.readthedocs.io/en/latest/physical_verification/design_manual/drm_10_6_2.html','MP.1–MP.13; not-coded guidelines','Matched devices, dummy, symmetry, same environment, similar interconnect and DC bias; current common-centroid drawing is our proposed interpretation'),
        ('G-EM','GF180 electro-migration','https://gf180mcu-pdk.readthedocs.io/en/latest/physical_verification/design_manual/drm_14_2.html','§14.2.1 / Tables14.3–14.4','Temperature and material/geometry dependent line/contact/via currents; bidirectional definition is not signed cancellation'),
        ('G-ESD','GF180 ESD layout guidelines','https://gf180mcu-pdk.readthedocs.io/en/latest/physical_verification/design_manual/drm_14_4.html','§14.4','Protection structures and layout; normal functional transients do not qualify ESD'),
        ('D-LED','Lin 2026 public yellow LED static curve','https://doi.org/10.5281/zenodo.20034288','One 20 um yellow LED, independently interpolated I–V point','Vf at 100 uA; temperature not confirmed; no calibrated dynamic C/thermal/optical model')]
    for ident,title,url,locator,support in extra:
        records.append({'id':ident,'title':title,'url':url,'locator':locator,'supports':support,
            'source_type':'public_dataset' if ident=='D-LED' else 'official_public_PDK_documentation',
            'access_level':'local_data_independently_calibrated' if ident=='D-LED' else 'official_documentation',
            'checked_on':'2026-10-12','reuse':'Source link and factual summary only; no source figure/PDF reproduced'})
    library={'schema_version':1,'study_date':'2026-10-12','scope':'15 selected sources directly relevant to circuit/layout decisions; not exhaustive or a performance ranking',
        'records':records,'research_papers':8,'new_EDA_runs':0,'original_figures':8}
    assert len(records)==15 and sum(bool(x.get('doi')) for x in records)==8
    (BASE/'sources.json').write_text(json.dumps(library,ensure_ascii=False,indent=2)+'\n')
    css="""@page{size:A4;margin:20mm}*{box-sizing:border-box}body{margin:0;color:#24353c;font:10.7pt/1.62 'Avenir Next','PingFang SC',sans-serif}
    h1,h2,h3{color:#164f5b;line-height:1.35}h1{font-size:24pt;margin:0 0 6mm}h2{font-size:18.5pt;margin:0 0 5mm;padding-bottom:3mm;border-bottom:1px solid #bdced0}h3{font-size:12pt}
    p{margin:0 0 3mm}strong{color:#183e49}a{color:#176977;text-decoration:none;overflow-wrap:anywhere}table{border-collapse:collapse;width:100%;margin:3mm 0 4mm;font-size:9.5pt;line-height:1.5}
    th{text-align:left;background:#eaf1f1;color:#164f5b;font-weight:600}th,td{padding:2mm 2.3mm;border-bottom:1px solid #d9e1e2;vertical-align:top;overflow-wrap:anywhere}tr{break-inside:avoid}
    code{font-family:inherit;font-size:.94em}img{display:block;width:100%;height:auto;margin:3mm 0 4mm}.page{break-after:page}.page:last-child{break-after:auto}
    @media print{body,.page{width:170mm}}@media screen{body{background:#edf2f2}.page{background:white;width:210mm;min-height:297mm;margin:8mm auto;padding:20mm;box-shadow:0 1px 8px #bac9ca}}
    """
    pages=[f'<section class="page" data-page="{i}">{markdown.markdown(s.strip(),extensions=["tables","fenced_code"])}</section>' for i,s in enumerate((BASE/'report.md').read_text().split('<!-- PAGE -->'),1)]
    assert len(pages)==14
    (BASE/'report.html').write_text('<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>MicroLED晶体管 电路与互连研究</title><style>'+css+'</style></head><body>'+'\n'.join(pages)+'</body></html>\n')
    cards=[]
    for x in records:
        data=''.join(f'<li>{html.escape(str(d["label"]))}: {html.escape(str(d["value"]))} {html.escape(str(d["unit"]))} — {html.escape(str(d["conditions"]))}</li>' for d in x.get('data',[]))
        access='关键全文已核查' if x['access_level']=='fulltext_reviewed' else ('数据独立校准' if x['id']=='D-LED' else '官方资料')
        cards.append(f'<article><h2>{x["id"]} · {html.escape(x["title"])}</h2><p>{access} · <a href="{html.escape(x["url"])}">原来源</a>'+ (f' · <a href="{html.escape(x["open_fulltext_url"])}">公开全文入口</a>' if x.get('open_fulltext_url') else '')+f'</p><p><b>定位：</b>{html.escape(str(x["locator"]))}</p><p>{html.escape(str(x["supports"]))}</p><ul>{data}</ul></article>')
    indexcss="""body{margin:0;background:#f4f7f5;color:#24353c;font:16px/1.7 'Avenir Next','PingFang SC',sans-serif}main{max-width:960px;margin:auto;padding:35px 22px}h1,h2{color:#164f5b;line-height:1.4}h2{font-size:20px}article{background:white;padding:22px 25px;border:1px solid #d1dfdc;border-radius:8px;margin:18px 0}a{color:#176977;overflow-wrap:anywhere}input{font:inherit;width:100%;padding:12px;border:1px solid #a5bfba;border-radius:5px}article[hidden]{display:none}li{margin:8px 0}@media(max-width:600px){main{padding:20px 14px}article{padding:18px 14px}h1{font-size:26px}}"""
    js="""const q=document.querySelector('input'),cards=[...document.querySelectorAll('article')];q.addEventListener('input',()=>{let n=0;for(const c of cards){c.hidden=!c.textContent.toLowerCase().includes(q.value.toLowerCase().trim());if(!c.hidden)n++}document.getElementById('count').textContent=n+' / '+cards.length});"""
    (BASE/'index.html').write_text('<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>MicroLED电路与互连研究来源</title><style>'+indexcss+'</style></head><body><main><h1>MicroLED电路与互连研究来源</h1><p>2026-10-12 · 8篇研究论文及7条PDK/数据来源 · 按问题选择，非穷尽综述。</p><p><a href="report.pdf">14页研究报告PDF</a> · <a href="report.html">网页版</a> · <a href="sources.json">完整来源数据</a> · <a href="calculations.json">独立计算</a></p><p>数字须按对应工况阅读。仅链接原文，未复制来源图或源PDF。图示设计与教学计算不代表制造/光学验证。</p><input aria-label="搜索论文与条件" placeholder="搜索 current steering、GaN、via、DOI、条件…"><p id="count">15 / 15</p>'+''.join(cards)+'</main><script>'+js+'</script></body></html>\n')
    paths=['analog/driver/pixel_driver.spice','analog/models/pdk-lock.json','scripts/layout/generate_pixel.tcl',
        'evidence/characterization/reference-matching-summary.json','evidence/characterization/actual-w20-l4-summary.json',
        'evidence/characterization/actual-w20-l4-area.json','evidence/characterization/measured-load-summary.json',
        'evidence/joint-pex/nominal/summary.json','docs/research/decision-review-20261011/report.md',
        'docs/research/driver-literature-20261012/sources.json',
        'evidence/robustness/main-summary.json','evidence/robustness/boundary-summary.json',
        'analog/models/measured-led/source-lock.json']
    (BASE/'provenance.json').write_text(json.dumps({'date':'2026-10-12','engineering_baseline':head,
        'local_input_sha256':{p:sha(ROOT/p) for p in paths},'report_source_sha256':sha(BASE/'report.md'),
        'renderer_sha256':sha(Path(__file__)), 'figure_renderer_sha256':sha(ROOT/'scripts/research/driver_circuit_figures.py'),'new_EDA_runs':0,'figures_original':True,
        'historical_mc_scope':'2026-10-04 v0.2 analog-only RC, nominal local-only n=256 each',
        'engineering_scope':'Existing v0.4 joint signal PEX, ideal PG projection; not full PG or manufacturing/optical proof'},ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'pages':len(pages),'sources':len(records),'calculations':len(calculations)-2,'original_figures':8,'new_EDA_runs':0}))


if __name__=='__main__':
    main()
