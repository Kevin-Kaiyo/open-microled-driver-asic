"""Build the new dated supplement; preserve prior report and experiment flags."""
from pathlib import Path
import hashlib, json, re
import markdown
ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/research/startup-tapeout-20261014'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 text=(BASE/'report-template.md').read_text()
 blocks=json.loads((BASE/'report-blocks.json').read_text())
 for key,value in blocks.items():
  if key.startswith('_'):continue
  text=text.replace('@@'+key+'@@',value)
 missing=re.findall(r'@@[A-Z_]+@@',text)
 if missing:raise ValueError('Evidence not ready: '+str(missing))
 pages=text.split('<!-- PAGE -->')
 for n,page in enumerate(pages,1):
  if n>1:page=re.sub(r'^##\s+',f'## {n}　',page,count=1,flags=re.M)
  pages[n-1]=page
 text='<!-- PAGE -->'.join(pages)
 (BASE/'report.md').write_text(text)
 css="""@page{size:A4;margin:19mm 20mm 20mm}*{box-sizing:border-box}body{margin:0;color:#263c43;font:10.7pt/1.59 'Avenir Next','PingFang SC',sans-serif}h1,h2,h3{font-family:'Avenir Next','PingFang SC',sans-serif;color:#175664;line-height:1.25}h1{font-size:25pt;margin:0 0 4mm}h2{font-size:17pt;border-bottom:1px solid #b9cdd0;margin:0 0 4mm;padding-bottom:3mm}h3{font-size:12pt;margin:3mm 0 2mm}p{margin:0 0 3mm}a{color:#176778;text-decoration:none;overflow-wrap:anywhere}strong{color:#174c59}table{width:100%;border-collapse:collapse;font-size:9.2pt;line-height:1.45;margin:3mm 0}th{background:#edf3f3;text-align:left}th,td{padding:1.9mm 2mm;vertical-align:top;border-bottom:1px solid #dce5e5;overflow-wrap:anywhere}tr{break-inside:avoid}ul,ol{padding-left:5.8mm;margin:2mm 0 3mm}li{margin:1mm 0}img{display:block;width:100%;margin:2mm 0 1mm}.caption{font-size:8.6pt;color:#596f76;line-height:1.48;margin-bottom:3mm}.eq{padding:2.5mm 3mm;background:#f1f6f5;border-left:2px solid #3b7d88;font-size:10pt;line-height:1.55;margin:3mm 0}code{font-family:'Avenir Next','PingFang SC',sans-serif;font-size:.95em;overflow-wrap:anywhere}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f5f7f7;padding:3mm;font-size:8.5pt;line-height:1.45}blockquote{margin:3mm 0;padding:3mm;background:#edf5f3;border-left:3px solid #3c7c86}blockquote p:last-child{margin:0}.page{break-after:page}.page:last-child{break-after:auto}@media print{body,.page{width:170mm}}@media screen{body{background:#ecf1f1}.page{width:210mm;min-height:297mm;padding:19mm 20mm 20mm;margin:8mm auto;background:white;box-shadow:0 1px 8px #bac9ca}}"""
 sections=[f'<section class="page" data-page="{n}">'+markdown.markdown(page.strip(),extensions=['tables','fenced_code'])+'</section>' for n,page in enumerate(pages,1)]
 (BASE/'report.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>MicroLED 单像素启动与ASIC流片路线 · 2026-10-14</title><style>'+css+'</style><body>'+''.join(sections)+'</body></html>\n')
 print(json.dumps({'sections':len(pages),'report_md_sha256':sha(BASE/'report.md')},ensure_ascii=False))
if __name__=='__main__':main()
