#!/usr/bin/env python3
"""Build the stage's portable HTML from its maintained Markdown report."""
from html import escape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

import markdown


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / 'docs/research/driver-pvt-20261117'
STYLE = '''
:root{--ink:#223c46;--teal:#20636a;--light:#edf5f4;--rule:#cfdedd;--mute:#526c75}
*{box-sizing:border-box}body{margin:0;background:#f3f6f5;color:var(--ink);font:16px/1.68 "PingFang SC","Noto Sans CJK SC","Avenir Next",Arial,sans-serif}
main{max-width:1060px;margin:auto;background:#fff;padding:32px clamp(18px,5vw,60px) 50px}h1,h2,h3{color:var(--teal);line-height:1.35;font-family:"Avenir Next","PingFang SC",sans-serif}
h1{font-size:clamp(28px,4vw,40px);margin:.3em 0 .45em}h2{font-size:clamp(21px,3vw,28px);margin:1.65em 0 .75em;border-top:1px solid var(--rule);padding-top:.72em}h3{font-size:19px;margin:1.15em 0 .5em}
p{margin:0 0 0.85em}a{color:var(--teal);overflow-wrap:anywhere}a:focus-visible{outline:2px solid var(--teal);outline-offset:2px}
nav{display:flex;flex-wrap:wrap;gap:5px 20px;padding:10px 0;border-bottom:1px solid var(--rule);margin-bottom:20px;font-size:.88em}
.table-wrap{overflow:auto;margin:.85em 0 1.1em;max-width:100%}table{width:100%;border-collapse:collapse;font-size:.9em}th,td{padding:.45em .58em;border-bottom:1px solid var(--rule);vertical-align:top;text-align:left}th{background:var(--light);color:var(--teal)}thead{display:table-header-group}
figure{margin:1.15em 0;text-align:center}figcaption{color:var(--mute);font-size:.88em;text-align:left;margin-top:.35em}img{display:block;margin:auto;max-width:100%;height:auto;max-height:880px}
code{font-size:.9em;overflow-wrap:anywhere}pre{white-space:pre-wrap;background:var(--light);padding:.65em .8em}blockquote{margin:.8em 0;padding:.5em .8em;border-left:3px solid var(--teal);background:var(--light)}blockquote p{margin:0}
@media print{@page{size:A4;margin:18mm 19mm 19mm}body{background:#fff;font-size:10.8pt;line-height:1.56;print-color-adjust:exact;-webkit-print-color-adjust:exact}main{max-width:none;padding:0}nav{display:none}h1{font-size:24pt}h2{font-size:15pt;margin-top:1.35em}h3{font-size:12pt}h2,h3{break-after:avoid}figure,tr,.table-wrap{break-inside:avoid}.table-wrap{overflow:visible}figure{margin:.9em 0}img{max-height:137mm}a{text-decoration:none}p,li{orphans:3;widows:3}}
'''


class LocalLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        self.links.extend(value for key, value in attrs if key in ('href', 'src') and value)


def build(filename, navigation):
    source = REPORT / filename
    title = source.read_text().splitlines()[0].removeprefix('# ')
    body = markdown.markdown(source.read_text(), extensions=['tables', 'fenced_code', 'toc'])
    body = body.replace('<table>', '<div class="table-wrap" tabindex="0" role="region" aria-label="数据表"><table>').replace('</table>', '</table></div>')
    page = (f'<!doctype html>\n<html lang="zh-CN"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{escape(title)}</title><style>{STYLE}</style></head>\n'
            f'<body><main><nav>{navigation}</nav>{body}</main></body></html>\n')
    output = REPORT / ('index.html' if filename == 'README.md' else 'reproduce.html')
    output.write_text(page)


def main():
    build('README.md', '<a href="technical-stage-report.pdf">PDF 报告</a><a href="reproduce.html">复现与数据</a><a href="../driver-interface-20261115/index.html">上一阶段</a>')
    build('reproduce.md', '<a href="index.html">返回报告</a>')
    for path in [REPORT / 'index.html', REPORT / 'reproduce.html']:
        links = LocalLinks()
        links.feed(path.read_text())
        for link in links.links:
            url = urlsplit(link)
            if not url.scheme and url.path and url.path != 'technical-stage-report.pdf':
                assert (path.parent / unquote(url.path)).resolve().is_file(), (path.name, link)
        print(f'{path.name}: {len(links.links)} links/images checked')


if __name__ == '__main__':
    main()
