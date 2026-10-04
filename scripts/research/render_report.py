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
    source=SOURCE.read_text()
    version=re.search(r'研究报告\s+(v\d+\.\d+)',source).group(1)
    for i,part in enumerate(source.split('<!-- page -->'),1):
        body=markdown.markdown(part,extensions=['tables','fenced_code'])
        def embed(m):
            p=(SOURCE.parent/m.group(1)).resolve()
            return 'src="data:image/png;base64,'+base64.b64encode(p.read_bytes()).decode()+'"'
        body=re.sub(r'src="([^"]+\.png)"',embed,body)
        body=re.sub(r'href="([^"]+)"',lambda m:'href="'+(m.group(1) if m.group(1).startswith('#') else urljoin(PUBLIC,m.group(1)))+'"',body)
        pages.append('<section class="page" id="section-'+str(i).zfill(2)+'">'+body+'</section>')
    css='''
    @page { size:A4; margin:20mm; }
    * { box-sizing:border-box; }
    body { margin:0; color:#263f4c; background:#edf2f2; font-family:'Avenir Next','PingFang SC',sans-serif;
      font-size:11pt; line-height:1.6; -webkit-print-color-adjust:exact; print-color-adjust:exact; }
    .page { max-width:210mm; margin:24px auto; padding:20mm; background:white; }
    .reading-nav { max-width:210mm; margin:20px auto; display:flex; gap:10px; flex-wrap:wrap; }
    .reading-nav a { padding:8px 14px; border:1px solid #b9d4d7; background:white; border-radius:4px; }
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
    @media print { body { background:white; } .reading-nav { display:none; } .page { width:170mm; max-width:none; padding:0; margin:0; break-after:page; }
      .page:last-child { break-after:auto; } }
    '''
    nav=''
    if version=='v0.4':
        nav='<nav class="reading-nav" aria-label="按阅读目的选择">'+''.join(
            '<a href="#section-'+n+'">'+label+'</a>' for n,label in
            [('01','总体结论'),('02','入门原理'),('08','工程证据'),('24','价值与方向')])+'</nav>'
    (SOURCE.parent/'research-report.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8">'+
      '<title>Open MicroLED Driver ASIC 单像素研究报告 '+version+'</title><style>'+css+'</style><body>'+nav+''.join(pages)+'</body></html>')
    print('Rendered',len(pages),'report sections')
if __name__=='__main__':main()
