#!/usr/bin/env python3
"""Build separate PWM and NRZ reports with local inputs hashed and linked."""
from pathlib import Path
import argparse,hashlib,html,json,re
import markdown
ROOT=Path(__file__).resolve().parents[2]
DIRS={'pwm':'pwm-reference-startup-20261024','nrz':'nrz-b-reference-power-20261024'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def build(key):
 out=ROOT/'docs/research'/DIRS[key];cfg=json.loads((out/'report-config.json').read_text());source=(out/'report.md').read_text()
 for token,path in cfg.get('sections',{}).items():
  section=(ROOT/path).read_text()
  if token=='RESULTS' and '{{OVERVIEW}}' in source:
   overview,detail=section.split('\n## ',1)
   source=source.replace('{{OVERVIEW}}',overview)
   section='## '+detail
  source=source.replace('{{'+token+'}}',section)
 assert '{{' not in source,'Unresolved report placeholder'
 source=source.rstrip()+'\n'
 (out/'report-complete.md').write_text(source)
 rendered=markdown.markdown(source,extensions=['tables','fenced_code','toc','attr_list'])
 css=(ROOT/'docs/research/highspeed-nrz-pvt-20261023/report.css').read_text()+'\n.scroll th,.scroll td{white-space:normal;min-width:105px}th,td{white-space:normal;overflow-wrap:anywhere}img{max-width:100%}h4{font-size:18px}.toc ul{line-height:1.9}.status{font-size:14px;color:#607982}.jump{display:flex;gap:22px;flex-wrap:wrap}\n'
 (out/'report.css').write_text(css)
 peer='nrz' if key=='pwm' else 'pwm';peerlabel='高速 B：参考与供电' if peer=='nrz' else '显示 PWM：参考与启动'
 navigation=f'<nav><a href="../{DIRS[peer]}/index.html">{peerlabel}</a><a href="../driver-robustness-20261024/index.html">上一阶段对照</a><a href="report-complete.md">Markdown 源文</a><a href="report-provenance.json">来源与哈希</a></nav>'
 (out/'index.html').write_text('<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+html.escape(cfg['title'])+'</title><link rel="stylesheet" href="report.css"></head><body><main><p class="eyebrow">OPEN MICROLED DRIVER ASIC / 2026-10-24 / 实验性研发方法验证与教学</p>'+navigation+rendered+'</main></body></html>\n')
 inputs=[out/'report.md',out/'report-config.json',ROOT/'evidence/reference-v2-research/sources.json']+[ROOT/x for x in cfg.get('evidence_inputs',[])]+[ROOT/x for x in cfg.get('sections',{}).values()]
 assert all(p.exists() for p in inputs)
 figures=[p for folder in ['figures','electrical-figures'] for p in (out/folder).glob('*') if p.suffix in ['.svg','.png','.json','.csv']]
 proof={'status':cfg['status'],'baseline_commit':'112ba95969ac6a2141c305324ea694e7b96c0765','inputs':{str(p.relative_to(ROOT)):sha(p) for p in inputs},'figures':{str(p.relative_to(out)):sha(p) for p in figures},'markdown_sha256':sha(out/'report-complete.md'),'html_sha256':sha(out/'index.html'),'generator_sha256':sha(Path(__file__))}
 (out/'report-provenance.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'report':key,'status':cfg['status'],'html':str(out/'index.html'),'inputs':len(inputs),'figures':len(figures)},ensure_ascii=False))
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('report',choices=['pwm','nrz','both'],default='both',nargs='?');a=ap.parse_args()
 for k in (DIRS if a.report=='both' else [a.report]):build(k)
