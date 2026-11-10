#!/usr/bin/env python3
"""Build the evidence-bound stage review as a paginated PDF and readable HTML."""
from pathlib import Path
import hashlib, html, json, re, sys
from urllib.parse import urlparse
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Image, Table, TableStyle, PageBreak, Spacer, KeepTogether
from PIL import Image as PILImage

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT/'docs/research/driver-improvement-20261111'
EV = ROOT/'evidence/ab-improvement-20261111'
WIDTH = A4[0]-40*mm
CSS = '''
:root{--ink:#213e49;--teal:#236d73;--muted:#5b727d;--line:#d3e0df;--light:#edf4f3}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:#eef3f2;color:var(--ink);font:16px/1.72 "PingFang SC","Noto Sans CJK SC",Arial,sans-serif}header{background:#203e49;color:#fff;padding:24px max(22px,calc((100vw - 1060px)/2));font-size:14px;letter-spacing:.06em}main{max-width:1120px;margin:auto;background:white;padding:24px 44px 64px}h1,h2,h3{font-family:"Avenir Next","PingFang SC",sans-serif;line-height:1.35;color:var(--teal)}h1{font-size:clamp(29px,4vw,42px)}h2{font-size:28px}h3{font-size:20px;margin-top:24px}p{margin:0 0 16px}section{padding:28px 0;border-bottom:1px solid var(--line);scroll-margin-top:20px}a{color:var(--teal);overflow-wrap:anywhere;text-underline-offset:3px}nav{display:flex;gap:18px;flex-wrap:wrap;font-size:14px}details{padding:18px 22px;background:var(--light);margin:22px 0}summary{cursor:pointer;font-weight:650}.toc{columns:2;padding-left:20px}.toc li{break-inside:avoid;padding:4px 0}.kicker{font:13px/1.6 "Avenir Next","PingFang SC",sans-serif;color:var(--muted);letter-spacing:.08em}.note{padding:16px 18px;background:var(--light);border-left:3px solid #6c9e9f;color:#49636e}.table-scroll{overflow:auto;margin:20px 0}table{border-collapse:collapse;width:100%;font-size:14px;line-height:1.6}td,th{padding:10px 11px;text-align:left;vertical-align:top;border-bottom:1px solid var(--line)}th{background:var(--light);color:var(--teal)}figure{margin:22px 0}img{max-width:100%;height:auto;display:block;margin:auto}figcaption{font-size:13px;line-height:1.6;color:var(--muted);margin-top:10px}code{overflow-wrap:anywhere;font-size:.9em}li{margin:8px 0}@media(max-width:680px){main{padding:18px 18px 40px}.toc{columns:1}h2{font-size:25px}table{min-width:560px}section{padding:22px 0}}@media print{body{background:#fff;font-size:11pt}main{padding:0}header,nav,details{display:none}section{break-after:page}tr,figure{break-inside:avoid}h2,h3{break-after:avoid}table{font-size:9pt}.note,th{print-color-adjust:exact}}
'''

def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def inline(s,pdf=False):
    s=html.escape(str(s)).replace('\n','<br/>')
    s=re.sub(r'\*\*(.+?)\*\*',r'<b>\1</b>',s)
    s=re.sub(r'`([^`]+)`',r'\1' if pdf else r'<code>\1</code>',s)
    def link(m):
        text,url=m.groups();url=html.unescape(url)
        if pdf and not urlparse(url).scheme:
            path=(DOC/url).resolve()
            try:url='https://github.com/Kevin-Kaiyo/open-microled-driver-asic/blob/main/'+str(path.relative_to(ROOT))
            except ValueError:raise ValueError(url)
        return f'<a href="{html.escape(url,quote=True)}"'+(' color="#236d73"' if pdf else '')+f'>{text}</a>'
    s=re.sub(r'\[([^\]]+)\]\(([^)]+)\)',link,s)
    if pdf:
        # The bundled TrueType CJK fallback lacks a few mathematical glyphs.
        s=re.sub(r'[µμτλΓη≤≥≈×−²π√∝Σ₋₃⁻⁰¹²³⁴⁵⁶⁷⁸⁹→←]',lambda m:'<font name="Latin">'+m.group(0)+'</font>',s)
    return s

def fonts():
    for name,path in [('Body','/System/Library/Fonts/STHeiti Light.ttc'),('BodyBold','/System/Library/Fonts/STHeiti Medium.ttc')]:
        pdfmetrics.registerFont(TTFont(name,path,subfontIndex=0))
    pdfmetrics.registerFontFamily('Body',normal='Body',bold='BodyBold',italic='Body',boldItalic='BodyBold')
    for name,path in [('Latin','Arial.ttf'),('LatinBold','Arial Bold.ttf')]:
        pdfmetrics.registerFont(TTFont(name,'/System/Library/Fonts/Supplemental/'+path))

def build(pages,pdf_output=True):
    fonts();DOC.mkdir(parents=True,exist_ok=True);EV.mkdir(parents=True,exist_ok=True)
    styles={}
    for name,size,leading,font in [('body',10.7,17.4,'Body'),('note',10.2,16,'Body'),('cell',9.3,14.1,'Body'),('th',9.5,14.5,'BodyBold'),('cover',25,34,'BodyBold'),('title',18,25,'BodyBold'),('h',12,18,'BodyBold'),('caption',9.1,14,'Body'),('kicker',9.3,14,'Body')]:
        styles[name]=ParagraphStyle(name,fontName=font,fontSize=size,leading=leading,wordWrap='CJK',spaceAfter=8,textColor=colors.HexColor('#236d73' if name in ['cover','title','h','th'] else '#213e49'))
    styles['note'].backColor=colors.HexColor('#edf4f3');styles['note'].borderPadding=8;styles['note'].spaceBefore=8;styles['note'].spaceAfter=14
    def para(s,style='body'):return Paragraph(inline(s,True),styles[style])
    story=[];parts=[];md=[]
    for i,pg in enumerate(pages):
        if i:story.append(PageBreak())
        story.extend([para(pg['kicker'],'kicker'),para(pg['title'],'cover' if i==0 else 'title')])
        parts.append(f'<section id="s{i+1:02d}"><p class="kicker">{html.escape(pg["kicker"])}</p><h{1 if i==0 else 2}>{html.escape(pg["title"])}</h{1 if i==0 else 2}>')
        md.extend(['# '+pg['title'],'',pg['kicker'],''])
        for b in pg['blocks']:
            kind=b['type']
            if kind in ['p','h','note']:
                story.append(para(b['text'],{'p':'body','h':'h','note':'note'}[kind]))
                tag='h3' if kind=='h' else 'p';cl=' class="note"' if kind=='note' else ''
                parts.append(f'<{tag}{cl}>{inline(b["text"])}</{tag}>')
                md.extend([('### ' if kind=='h' else '> ' if kind=='note' else '')+b['text'],''])
            elif kind=='table':
                rows=[[para(v,'th' if j==0 else 'cell') for v in row] for j,row in enumerate([b['head'],*b['rows']])]
                table=Table(rows,colWidths=[WIDTH*x for x in b.get('widths',[1/len(b['head'])]*len(b['head']))],repeatRows=1,hAlign='LEFT')
                table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#edf4f3')),('VALIGN',(0,0),(-1,-1),'TOP'),('LINEBELOW',(0,0),(-1,-1),.4,colors.HexColor('#d3e0df')),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6),('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6)]))
                story.extend([table,Spacer(1,10)])
                parts.append('<div class="table-scroll" role="region" aria-label="数据表" tabindex="0"><table><thead><tr>'+''.join('<th>'+inline(x)+'</th>' for x in b['head'])+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+inline(v)+'</td>' for v in row)+'</tr>' for row in b['rows'])+'</tbody></table></div>')
                md.extend(['| '+' | '.join(b['head'])+' |','|'+'|'.join(['---']*len(b['head']))+'|']+['| '+' | '.join(str(x).replace('|','&#124;').replace('\n','<br>') for x in row)+' |' for row in b['rows']]+[''])
            elif kind=='figure':
                path=(DOC/b['path']).resolve()
                with PILImage.open(path) as im:iw,ih=im.size
                scale=min(WIDTH/iw,b.get('height',100)*mm/ih)
                story.append(KeepTogether([Image(str(path),width=iw*scale,height=ih*scale),Spacer(1,5),para(b['caption'],'caption')]))
                parts.append(f'<figure><a href="{html.escape(b.get("original",b["path"]))}"><img src="{html.escape(b["path"])}" alt="{html.escape(b["caption"])}"></a><figcaption>{inline(b["caption"])}</figcaption></figure>')
                md.extend([f'![{b["caption"]}]({b["path"]})',''])
        parts.append('</section>')
    def footer(canvas,doc):
        canvas.saveState();canvas.setStrokeColor(colors.HexColor('#cedcda'));canvas.line(20*mm,281*mm,190*mm,281*mm)
        canvas.setFillColor(colors.HexColor('#5b727d'));canvas.setFont('Latin',8);canvas.drawString(20*mm,286*mm,'OPEN MICROLED DRIVER ASIC / RESEARCH MILESTONE')
        canvas.setFont('Body',8);canvas.drawString(20*mm,13*mm,'2026-11-11 | 公开实验、模型验证与研发决策')
        canvas.setFont('Latin',8);canvas.drawRightString(190*mm,13*mm,str(doc.page));canvas.restoreState()
    pdf=SimpleDocTemplate(str(DOC/'technical-stage-report.pdf'),pagesize=A4,leftMargin=20*mm,rightMargin=20*mm,topMargin=24*mm,bottomMargin=20*mm,title='MicroLED A/B 与 VCSEL：驱动电路改进及验证报告',author='Open MicroLED Driver ASIC project')
    if pdf_output:pdf.build(story,onFirstPage=footer,onLaterPages=footer)
    toc='<details><summary>展开阅读目录</summary><ol class="toc" style="list-style:none;padding-left:0">'+''.join(f'<li><a href="#s{i+1:02d}">{html.escape(x["title"])}</a></li>' for i,x in enumerate(pages))+'</ol></details>'
    nav='<nav><a href="technical-stage-report.pdf">下载 PDF</a><a href="../blue-emitter-speed-review-20261110/index.html">前阶段基线报告</a><a href="../../../evidence/ab-improvement-20261111/summary.json">实验数据</a><a href="reproduce.html">复现与验证</a></nav>'
    page='<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>MicroLED A/B 与 VCSEL：驱动电路改进及验证报告</title><style>'+CSS+'</style></head><body><header>OPEN MICROLED DRIVER ASIC · 2026-11-11</header><main>'+nav+toc+''.join(parts)+'</main></body></html>'
    (DOC/'index.html').write_text(page);(DOC/'README.md').write_text('\n'.join(md).rstrip()+'\n')
    (DOC/'content.json').write_text(json.dumps(pages,ensure_ascii=False,indent=2)+'\n')
    (EV/'report-generation.json').write_text(json.dumps({'expected_pages':len(pages),'pdf_sha256':sha(DOC/'technical-stage-report.pdf'),'html_sha256':sha(DOC/'index.html'),'font_note':'HTML prefers PingFang SC. PDF embeds Heiti SC TrueType fallback and Arial for symbols; system PingFang CFF unsupported by ReportLab TTFont.','report_dependencies':{'reportlab':'4.4.9','pypdf':'6.10.0','pdfplumber':'0.11.9','Markdown':'3.9'},'scope':'New schematic A/B and VCSEL modifications, controlled ablations and rate envelopes; no new layout, silicon or optical measurements.'},ensure_ascii=False,indent=2)+'\n')

def chapter(name):
    import markdown
    p=DOC/(name+'.md')
    body=markdown.markdown(p.read_text(),extensions=['tables','fenced_code','toc'])
    body=body.replace('<table>','<div class="table-scroll"><table>').replace('</table>','</table></div>')
    (DOC/(name+'.html')).write_text('<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>'+CSS+'</style><title>'+html.escape(p.read_text().splitlines()[0].removeprefix('# '))+'</title></head><body><main><nav><a href="index.html">返回阶段技术报告</a></nav>'+body+'</main></body></html>')

if __name__=='__main__':
    from content import pages
    build(pages(),pdf_output='--html-only' not in sys.argv)
    for name in ['reproduce']:chapter(name)
    print('Generated stage HTML/PDF and evidence chapters')
