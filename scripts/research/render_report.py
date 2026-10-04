"""Render the current research report as readable A4 HTML; Markdown==3.8.2."""
from pathlib import Path
from urllib.parse import urljoin
import base64
import re
import markdown

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'docs/research/research-report.md'
PUBLIC='https://github.com/Kevin-Kaiyo/open-microled-driver-asic/blob/main/docs/research/'
def main():
    pages=[]
    for part in SOURCE.read_text().split('<!-- page -->'):
        body=markdown.markdown(part,extensions=['tables','fenced_code'])
        def embed(m):
            p=(SOURCE.parent/m.group(1)).resolve()
            return 'src="data:image/png;base64,'+base64.b64encode(p.read_bytes()).decode()+'"'
        body=re.sub(r'src="([^"]+\.png)"',embed,body)
        body=re.sub(r'href="([^"]+)"',lambda m:'href="'+urljoin(PUBLIC,m.group(1))+'"',body)
        pages.append('<section class="page">'+body+'</section>')
    css='''
    @page { size:A4; margin:20mm; }
    * { box-sizing:border-box; }
    body { margin:0; color:#263f4c; background:#edf2f2; font-family:'Avenir Next','PingFang SC',sans-serif;
      font-size:11pt; line-height:1.6; -webkit-print-color-adjust:exact; print-color-adjust:exact; }
    .page { max-width:210mm; margin:24px auto; padding:20mm; background:white; }
    h1 { color:#143f4e; font-size:25pt; line-height:1.3; font-weight:600; margin:0 0 18pt; }
    h2 { color:#176e78; font-size:17pt; line-height:1.4; font-weight:600; margin:0 0 16pt;
      padding-bottom:8pt; border-bottom:1px solid #b9d4d7; }
    h3 { color:#234e5c; font-size:12pt; line-height:1.45; margin:14pt 0 8pt; }
    p { margin:0 0 10pt; } strong { font-weight:600; }
    a { color:#176e78; text-decoration:none; overflow-wrap:anywhere; }
    table { width:100%; border-collapse:collapse; margin:12pt 0; font-size:9.5pt; line-height:1.48; }
    th { text-align:left; color:#17616b; background:#eaf3f3; font-weight:600; }
    th,td { padding:7pt; border-bottom:1px solid #dce6e8; vertical-align:top; }
    tr { break-inside:avoid; } thead { display:table-header-group; }
    img { width:100%; height:auto; display:block; margin:8pt 0; }
    ul,ol { padding-left:18pt; margin:5pt 0 10pt; } li { margin:4pt 0; }
    code { font:inherit; font-size:.93em; background:#f0f4f5; overflow-wrap:anywhere; }
    pre { background:#f0f4f5; padding:10pt; font-size:8.4pt; line-height:1.5;
      white-space:pre-wrap; overflow-wrap:anywhere; }
    blockquote { border-left:3px solid #91bec1; margin:12pt 0; padding:3pt 0 3pt 12pt; }
    @media print { body { background:white; } .page { width:170mm; max-width:none; padding:0; margin:0; break-after:page; }
      .page:last-child { break-after:auto; } }
    '''
    version=re.search(r'研究报告\s+(v\d+\.\d+)',SOURCE.read_text()).group(1)
    (SOURCE.parent/'research-report.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8">'+
      '<title>Open MicroLED Driver ASIC 单像素研究报告 '+version+'</title><style>'+css+'</style><body>'+''.join(pages)+'</body></html>')
    print('Rendered',len(pages),'report sections')
if __name__=='__main__':main()
