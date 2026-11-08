#!/usr/bin/env python3
"""Generate a Chinese progress review from scoped source audits; no simulation rerun."""
from pathlib import Path
import ast,base64,hashlib,html,importlib.util,json,os,re,shutil,subprocess,sys
from urllib.parse import quote
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,Image,PageBreak,KeepTogether
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from PIL import Image as PILImage
import content as c
ROOT=c.ROOT;DOC=ROOT/'docs/research/project-progress-review-20261108';ASSET=DOC/'assets';EV=c.EV;WORK=ROOT/'build/project-progress-review-20261108'
PIN='79117978252dce1d5c84b5254689b0b0848c2a58'
PUBLIC='https://github.com/Kevin-Kaiyo/open-microled-driver-asic/blob/'+PIN+'/'
W=A4[0]-40*mm
FIGURES=[]
def sha(p):
 with Path(p).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def dump(p,q):p.write_text(json.dumps(q,ensure_ascii=False,indent=2)+'\n')
def wrap(s,n):
 return [s[i:i+n] for i in range(0,len(s),n)]
def draw_diagrams():
 font='font-family="PingFang SC,Hiragino Sans GB,Arial,sans-serif"'
 def svg(name,width,height,contents):
  p=ASSET/(name+'.svg');p.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}"><rect width="100%" height="100%" fill="white"/>'+''.join(contents)+'</svg>\n')
 def text(x,y,s,size=22,color='#233f4b',bold=False):
  glyphs=''.join('<tspan font-family="Arial">'+html.escape(ch)+'</tspan>' if ch in 'Ωµμτ≈×²→−≤≥' else html.escape(ch) for ch in s)
  return f'<text x="{x}" y="{y}" {font} font-size="{size}" font-weight="{600 if bold else 400}" fill="{color}">{glyphs}</text>'
 def rect(x,y,w,h,color='#eef4f3',stroke='#bfd1d0'):return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{color}" stroke="{stroke}" stroke-width="2"/>'
 def path(d,color='#437b80',width=3):return f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{width}"/>'
 z=[text(34,40,'从命令到发光，再到可检查的证据',27,bold=True)]
 boxes=[(34,76,240,115,'数字命令与控制','帧校验 / PWM / 故障'),(316,76,240,115,'缓冲与模拟驱动','参考 / 电流 / 电源'),(598,76,240,115,'发光器件负载','MicroLED 或 VCSEL'),(880,76,282,115,'观察与评价','电荷 / RX / 能量 / 应力')]
 for x,y,w,h,a,b in boxes:z +=[rect(x,y,w,h),text(x+18,y+42,a,24,bold=True),text(x+18,y+80,b,20)]
 for x in [274,556,838]:z +=[path(f'M{x} 133 L{x+28} 133 M{x+20} 125 L{x+28} 133 L{x+20} 141')]
 rows=[('照明 PWM','固定开态电流 + 导通时间','已验证：100µA、3.90625kHz、实际宏PEX','#eaf3ef'),('MicroLED 数据','A 电压 / B 转向 / C PAM4','49电气case；132条完整RX分析记录未通过','#f8f2e8'),('VCSEL 数据','偏置 + 调制 + 双反馈供电','73MOS；有限帧通过，快冷启动待解决','#edf2f7')]
 for i,(a,b,d,col) in enumerate(rows):
  y=230+i*94;z +=[rect(34,y,1128,78,col),text(52,y+31,a,24,bold=True),text(286,y+31,b,22),text(286,y+61,d,20)]
 z +=[text(35,545,'共同底座：公开PDK / RTL与晶体管 / DRC-LVS-PEX / 数值控制 / 来源哈希与失败记录',21),text(35,583,'实物LED/VCSEL、绝对光功率、噪声BER和流片签核仍是后续证据层。',21,color='#697b83')]
 svg('architecture',1200,610,z)
 z=[text(32,42,'同样写“1MHz”，对应的PWM能力不同',27,bold=True)]
 z +=[text(34,94,'现有已验证',23,bold=True),text(238,94,'clock = 1MHz；slot = 1µs；256 slots/frame',23)]
 z +=[path('M238 145 L238 115 L278 115 L278 145 L318 145 L318 115 L358 115 L358 145 L398 145 L398 115 L438 115 L438 145 L478 145 L478 115 L518 115 L518 145 L558 145 L558 115 L598 115 L598 145'),text(644,136,'…… 共256个时隙',21)]
 z +=[path('M238 212 L238 175 L278 175 L278 212 L1030 212'),text(238,248,'最低码：导通1µs；完整PWM周期256µs；载波3.90625kHz',23)]
 z +=[path('M34 281 L1156 281','#d5e0df',2),text(34,329,'新条件推导',23,bold=True),text(238,329,'若要求1MHz载波 + 8bit等时隙计数PWM',23)]
 z +=[rect(238,353,800,65,'#f8f2e8'),text(258,394,'周期1µs / 256 = 3.90625ns；计数clock = 256MHz',24,bold=True)]
 z +=[text(34,466,'示意图不按同一时间比例绘制。新条件尚未在当前RTL/输出级/负载上完成验证。',21,color='#697b83')]
 svg('pwm-timing',1200,495,z)
 z=[text(32,43,'每个证据层分别回答一个问题',27,bold=True)]
 rows=[('文献与模型','器件参数/测量条件有哪些？','资料已整理；动态物理识别仍有缺口','#eef4f3'),('RTL与晶体管','数字时序、电流和接收是否符合模型？','已有指定范围实验，保留通过与失败','#eef4f3'),('布局与寄生','实际几何连接及寄生怎样改变电路？','照明宏/共同顶层和旧高速核心有结果','#eef4f3'),('完整芯片/封装','全部电路、接口、电源与可靠性是否闭合？','未完成完整签核','#f8f2e8'),('硅片与光学链路','真实光功率、误码、温度与寿命如何？','尚未实物验证','#f8f2e8')]
 for i,(a,b,d,col) in enumerate(rows):
  y=76+i*80;z +=[rect(32,y,1136,66,col),text(49,y+28,a,22,bold=True),text(292,y+28,b,21),text(292,y+54,d,19,color='#657a84')]
 z +=[text(32,514,'通过某一层，不会自动使下一层通过；教学三维几何也不是TCAD/热/电磁场求解。',21)]
 svg('evidence-layers',1200,545,z)
 z=[text(28,37,'同一负载与固定接收器：电路连接及观察参考面',27,bold=True)]
 z +=[text(35,85,'VLED=5V',20),path('M150 80 L175 80 L175 70 L225 70 L225 90 L175 90 M225 80 L285 80 L285 140'),text(171,58,'0.25Ω',19)]
 z +=[path('M85 140 L285 140 M85 140 L85 190 M85 235 L85 258 M85 304 L85 350 L285 350 M285 140 L285 222 M285 245 L285 350'),text(300,145,'Va',20),text(300,354,'Vk',20)]
 z +=[path('M62 190 L108 190 L85 230 Z M61 235 L109 235'),text(36,183,'I-V',19),'<circle cx="85" cy="281" r="23" stroke="#437b80" stroke-width="3" fill="white"/>',text(122,286,'VSENSE=0V',19),path('M262 222 L308 222 M262 245 L308 245'),text(310,229,'CLED',19),text(310,253,'假设值',19)]
 z +=[path('M85 350 L85 375 L75 375 L75 415 L95 415 L95 375 M85 415 L85 435 C115 435 115 450 85 450 C115 450 115 465 85 465 L85 490'),text(120,401,'Rpkg=1Ω',20),text(120,455,'Lpkg=0.5nH',20),rect(28,490,334,67),text(45,517,'A/B/C 显式驱动电路',22,bold=True),text(45,543,'参考、供电与缓冲保持原输入',18)]
 for x,a,b in [(460,'导电电流','原生波形'),(705,'光响应状态','τ为敏感性假设'),(950,'固定RX','1GHz + 原阈值')]:z +=[rect(x,128,218,88),text(x+16,164,a,23,bold=True),text(x+16,193,b,18)]
 z +=[path('M678 172 L705 172 M923 172 L950 172'),rect(460,265,708,105),text(479,302,'电荷与能量分别统计',24,bold=True),text(479,337,'I端口 = I导电 + C·d(Va - Vk)/dt',22),rect(460,410,708,143,'#f8f2e8'),text(479,448,'整链S21幅频拟合只留在频域证据层',23,bold=True),text(479,483,'没有重复串入已有CLED / 光状态 / RX之后。',22),text(479,519,'七源端口能量 / 4096尝试payload位；不是光学测量。',20)]
 svg('load-reference',1200,585,z)
 def nmos(x,y,label):
  out=[path(f'M{x} {y-48} L{x} {y-22} M{x} {y-22} L{x} {y+22} M{x} {y+22} L{x} {y+48} M{x-27} {y-22} L{x-27} {y+22} M{x-67} {y} L{x-27} {y}'),text(x+18,y+7,label,22)]
  return out
 def resistor(x,y,label):return [path(f'M{x} {y} L{x} {y+12} L{x-10} {y+12} L{x-10} {y+52} L{x+10} {y+52} L{x+10} {y+12} M{x} {y+52} L{x} {y+65}'),text(x+20,y+38,label,21)]
 def ground(x,y):return [path(f'M{x} {y} L{x} {y+10} M{x-17} {y+10} L{x+17} {y+10} M{x-11} {y+17} L{x+11} {y+17} M{x-5} {y+24} L{x+5} {y+24}')]
 z=[text(24,38,'VCSEL：反馈设定电流，高速数据选择电流路径',27,bold=True),text(24,70,'NMOS三端简图；体端VSS及OTA电源未展开，原网表/完整器件图保留。',20,color='#697b83')]
 z +=[path('M330 110 L1070 110 M600 110 L600 155 M600 205 L600 235 L330 235 L330 252 M600 235 L600 272'),text(345,101,'VL：调节后的激光供电（低输入可dropout）',22)]
 z +=[path('M578 155 L622 155 L600 200 Z M577 205 L623 205 M637 170 L660 151 M652 174 L676 155'),text(680,177,'VCSEL + 封装R/L',23),text(619,237,'OUT',21)]
 z +=resistor(1070,140,'RDUMMY 500Ω');z +=[path('M1070 110 L1070 140 M1070 205 L1070 272'),text(1088,244,'DUMMY',21)]
 z +=nmos(330,300,'XBASE ×2');z +=nmos(600,320,'XSTEER');z +=nmos(1070,320,'XDUMP')
 z +=[text(470,308,'GP',22),text(939,308,'GN',22),path('M480 320 L533 320 M946 320 L1003 320 M600 368 L600 400 L1070 400 L1070 368 M810 400 L810 442'),text(828,399,'VX',21)]
 z +=[path('M100 254 L100 346 L220 300 Z M220 300 L263 300 M30 271 L100 271 M330 348 L330 373 L75 373 L75 328 L100 328'),text(112,308,'OTA-B',21),text(82,275,'+',20),text(82,333,'-',20),text(24,248,'VSET',20),text(349,374,'SBASE',21)]
 z +=[path('M330 373 L330 388')];z +=resistor(330,388,'50Ω');z +=ground(330,453)
 z +=nmos(810,490,'XTAIL ×2');z +=[path('M550 444 L550 536 L674 490 Z M674 490 L743 490 M480 462 L550 462 M810 538 L810 559 L516 559 L516 518 L550 518'),text(562,497,'OTA-T',21),text(530,466,'+',20),text(531,524,'-',20),text(465,441,'VSET',20),text(831,560,'STAIL',21)]
 z +=[path('M810 559 L810 574')];z +=resistor(810,574,'37.5Ω');z +=ground(810,639)
 z +=[text(24,554,'VSET = 0.15V',23,bold=True),text(24,591,'IBIAS ≈ 3mA；IMOD ≈ 4mA（设定）',22),text(24,630,'D=1：IMOD经VCSEL / XSTEER',22),text(24,666,'D=0：IMOD经RDUMMY / XDUMP',22),text(24,704,'IBIAS两态均流过VCSEL；GP/GN来自实际数据缓冲。',22,color='#526f7a')]
 z +=[f'<circle cx="{x}" cy="{y}" r="4" fill="#437b80"/>' for x,y in [(600,110),(600,235),(330,373),(810,400),(810,559)]]
 svg('vcsel-core',1320,735,z)



def make_margin_chart():
 code=r"""import json,sys
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
root=Path(sys.argv[1]);target=Path(sys.argv[2]);p='/System/Library/Fonts/Hiragino Sans GB.ttc';font_manager.fontManager.addfont(p)
plt.rcParams.update({'font.family':[font_manager.FontProperties(fname=p).get_name(),'DejaVu Sans'],'font.size':15,'axes.unicode_minus':False,'svg.fonttype':'none','svg.hashsalt':'progress-review-20261108'})
q=json.loads((root/'evidence/microled-dynamic-v1/rx-summary.json').read_text())['records'];rows=[]
for route in 'ABC':rows.append(next(x for x in q if x['route']==route and x['corner']=='typical' and x['steps_per_symbol']==40 and x['stage']=='full' and abs(x['capacitance_fF']-10)<1e-6 and x['optical_tau_ps']==25))
fig,axs=plt.subplots(1,2,figsize=(10.4,4.3));metrics=[('min_signed_margin_uA','最小有符号幅度 / µAeq',7.5,(-48,17)),('min_time_margin_ps','最小单侧时间 / ps',100,(-8,122))]
for ax,(key,label,gate,lims) in zip(axs,metrics):
 vals=[x[key] for x in rows];ax.bar(list('ABC'),vals,color='#5b8d91',width=.5);ax.axhline(0,color='#7c8e94',lw=.8);ax.axhline(gate,color='#94693e',lw=1.3,ls='--',label=f'固定门槛 {gate:g}');ax.set(ylim=lims,ylabel=label);ax.spines[['top','right']].set_visible(False);ax.grid(axis='y',alpha=.16);ax.legend(frameon=False,fontsize=12,loc='upper left')
 for i,v in enumerate(vals):ax.text(i,v+(1.4 if key=='min_signed_margin_uA' else 2),f'{v:.2f}',ha='center',va='bottom',fontsize=14)
fig.tight_layout(pad=1.7)
fig.savefig(target.with_suffix('.png'),dpi=180)
fig.savefig(target.with_suffix('.svg'),metadata={'Date':'2026-11-08'})
p=target.with_suffix('.svg');p.write_text('\n'.join(x.rstrip() for x in p.read_text().splitlines())+'\n')
"""
 subprocess.run([str(ROOT/'build/layout/venv/bin/python'),'-c',code,str(ROOT),str(ASSET/'rx-margins')],check=True)

def rasterize(path):
 path=Path(path)
 if path.suffix.lower()!='.svg':return path
 name=path.stem if path.parent==ASSET else 'reuse-'+path.parent.parent.name+'-'+path.stem
 dst=ASSET/(name+'.png')
 code="import cairosvg,sys;cairosvg.svg2png(url=sys.argv[1],write_to=sys.argv[2],scale=1.6)"
 env={**os.environ,'DYLD_FALLBACK_LIBRARY_PATH':'/opt/homebrew/lib'}
 subprocess.run([str(ROOT/'build/layout/venv/bin/python'),'-c',code,str(path),str(dst)],check=True,env=env)
 return dst

def prepare_sources():
 source=[]
 for ident,title,path,locator in c.SOURCES:
  p=ROOT/path
  if not p.exists():raise FileNotFoundError(path)
  source.append({'id':ident,'title':title,'path':path,'locator':locator,'sha256':sha(p),'bytes':p.stat().st_size,'url':('https://github.com/Kevin-Kaiyo/open-microled-driver-asic/blob/main/' if ident in ['S21','S22','S23'] else PUBLIC)+quote(path,safe='/')})
 # Include every audited source identity, with exact scope retained in the audit files.
 scoped={}
 for n in ['pwm-physical-audit.json','highspeed-audit.json','platform-delivery-audit.json']:
  q=json.loads((EV/n).read_text());items=q.get('sources',[])
  if isinstance(items,dict):items=items.values()
  for x in items:
   if isinstance(x,dict) and 'path' in x and 'sha256' in x:scoped[x['path']]=x['sha256']
  for claim in q['claims']:
   for x in claim.get('sources',[]):
    if 'path' in x and 'sha256' in x:scoped[x['path']]=x['sha256']
 for path,digest in scoped.items():assert sha(ROOT/path)==digest, 'Audited source changed: '+path
 dump(EV/'sources.json',{'as_of':'2026-11-08','audit_baseline_commit':PIN,'report_is_synthesis_not_new_experiment':True,'sources':source,'audited_source_hashes':scoped})
 return {x['id']:x for x in source}

def inline(text,sources,mode='html'):
 text=escape(str(text)).replace('\n','<br/>')
 text=re.sub(r'\*\*(.+?)\*\*',r'<b>\1</b>',text)
 for ident,src in sources.items():
  if mode=='html':link=f'<a href="#source-{ident}">[{ident}]</a>'
  else:link=f'<link href="{escape(src["url"])}" color="#226f76">[{ident}]</link>'
  text=text.replace('['+ident+']',link)
 return text

def prepare_pages(sources):
 pages=c.build_pages()
 for chunk,title in [(list(sources.values())[:12],'主要证据来源（1/2）'),(list(sources.values())[12:],'主要证据来源（2/2）')]:
  rows=[['['+s['id']+']',s['title'],Path(s['path']).name+'\nSHA '+s['sha256'][:12]] for s in chunk]
  pages.append(c.page(title,'来源附录 · 完整路径与SHA另见sources.json',[
   c.p('点击来源编号可打开审计基线下的原文件；本报告新增审计S21-S23则链接当前配套文件。JSON来源保留完整精度，报告按阅读需要取舍小数位。'),c.table(['编号','来源内容','文件名 / SHA前12位'],rows,[.11,.52,.37]),c.note('来源S21-S23的本轮审计与sources.json记录逐claim条件、版本/模型身份及不能支持的结论。受限论文原图未被重新发布，复用图片为本项目既有原创电路、数据图或教学渲染。')]))
 for ident in ['S21','S22','S23']:
  sources[ident]['url']='https://github.com/Kevin-Kaiyo/open-microled-driver-asic/blob/main/'+sources[ident]['path']
 for pg in pages:
  for b in pg['blocks']:
   if b['type']!='figure':continue
   source=(DOC/b['path']).resolve()
   if source.parent==ASSET and source.with_suffix('.svg').exists():source=source.with_suffix('.svg')
   png=rasterize(source)
   if png.parent!=ASSET:
    dst=ASSET/('reuse-'+source.parent.parent.name+'-'+png.name);shutil.copyfile(png,dst);png=dst
   b['resolved_png']=str(png.relative_to(ROOT));b['local_asset']='assets/'+png.name
   if source.parent==ASSET:b['original_link']='assets/'+source.name
   else:b['original_link']=PUBLIC+quote(str(source.relative_to(ROOT)),safe='/')
   FIGURES.append({'source_path':str(source.relative_to(ROOT)),'source_sha256':sha(source),'rendered_path':str(png.relative_to(ROOT)),'rendered_sha256':sha(png),'caption':b['caption'],'reuse':'Repository original schematic/plot/teaching render, or new report concept diagram; no restricted paper images.'})
 upstream={'architecture':['evidence/project-progress-review-20261108/pwm-physical-audit.json','evidence/project-progress-review-20261108/highspeed-audit.json'],'pwm-timing':['docs/pwm.md'],'load-reference':['docs/research/microled-dynamic-validation-20261108/figures/model-circuit.svg'],'rx-margins':['evidence/microled-dynamic-v1/rx-summary.json'],'vcsel-core':['docs/research/vcsel-reference-microled-dynamics-20261029/figures/servo-current-core.svg'],'evidence-layers':['evidence/project-progress-review-20261108/pwm-physical-audit.json','evidence/project-progress-review-20261108/highspeed-audit.json']}
 for entry in FIGURES:
  key=Path(entry['source_path']).stem
  entry['basis_sources']=[{'path':p,'sha256':sha(ROOT/p)} for p in upstream.get(key,[])]
 dump(EV/'figure-ledger.json',{'figures':FIGURES,'optical_or_field_simulation':False})
 dump(DOC/'content.json',{'title':'Open MicroLED Driver ASIC 开发进度与主要成果报告','as_of':'2026-11-08','pages':pages})
 return pages

def pdf_fonts():
 for name,p in [('Body','/System/Library/Fonts/STHeiti Light.ttc'),('BodyBold','/System/Library/Fonts/STHeiti Medium.ttc')]:pdfmetrics.registerFont(TTFont(name,p,subfontIndex=0))
 pdfmetrics.registerFontFamily('Body',normal='Body',bold='BodyBold',italic='Body',boldItalic='BodyBold')
 pdfmetrics.registerFont(TTFont('Latin','/System/Library/Fonts/Supplemental/Arial.ttf'))
 pdfmetrics.registerFont(TTFont('LatinBold','/System/Library/Fonts/Supplemental/Arial Bold.ttf'))
 pdfmetrics.registerFontFamily('Latin',normal='Latin',bold='LatinBold',italic='Latin',boldItalic='LatinBold')

def make_pdf(pages,sources):
 pdf_fonts();ink=colors.HexColor('#233f4b');teal=colors.HexColor('#246e73')
 styles={
 'body':ParagraphStyle('body',fontName='Body',fontSize=10.7,leading=17.2,textColor=ink,wordWrap='CJK',spaceAfter=8),
 'note':ParagraphStyle('note',fontName='Body',fontSize=9.5,leading=14.7,textColor=colors.HexColor('#526d77'),wordWrap='CJK',spaceAfter=7,borderColor=colors.HexColor('#bdd2d1'),borderWidth=.6,borderPadding=8),
 'cell':ParagraphStyle('cell',fontName='Body',fontSize=9.3,leading=14.3,textColor=ink,wordWrap='CJK'),
 'headcell':ParagraphStyle('headcell',fontName='BodyBold',fontSize=9.6,leading=14.6,textColor=teal,wordWrap='CJK'),
 'title':ParagraphStyle('title',fontName='BodyBold',fontSize=18,leading=25,textColor=teal,spaceAfter=12,wordWrap='CJK'),
 'cover':ParagraphStyle('cover',fontName='BodyBold',fontSize=25,leading=34,textColor=teal,spaceAfter=16,wordWrap='CJK'),
 'kicker':ParagraphStyle('kicker',fontName='Body',fontSize=9.5,leading=14,textColor=colors.HexColor('#71858b'),spaceAfter=7),
 'h':ParagraphStyle('h',fontName='BodyBold',fontSize=12,leading=18,textColor=teal,spaceAfter=6,spaceBefore=5),
 'caption':ParagraphStyle('caption',fontName='Body',fontSize=9.0,leading=13.8,textColor=colors.HexColor('#526d77'),wordWrap='CJK',spaceAfter=9)}
 def para(text,style='body'):return Paragraph(inline(text,sources,'pdf'),styles[style])
 story=[]
 for i,pg in enumerate(pages):
  if i:story.append(PageBreak())
  story.extend([para(pg['kicker'],'kicker'),para(pg['title'],'cover' if i==0 else 'title')])
  if i==0:story.append(para('编制日期：2026-11-09  |  证据截止：2026-11-08','kicker'))
  for b in pg['blocks']:
   t=b['type']
   if t in ('p','note','h'):story.append(para(b['text'],{'p':'body','note':'note','h':'h'}[t]))
   elif t=='bullets':
    for n,item in enumerate(b['items'],1):story.append(para(f'{n}. '+item))
   elif t=='table':
    rows=[[para(v,'headcell' if ri==0 else 'cell') for v in row] for ri,row in enumerate([b['head'],*b['rows']])]
    weights=b.get('widths') or [1/len(b['head'])]*len(b['head']);tbl=Table(rows,colWidths=[W*w for w in weights],hAlign='LEFT',repeatRows=1)
    tbl.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#eaf2f1')),('VALIGN',(0,0),(-1,-1),'TOP'),('LINEBELOW',(0,0),(-1,0),.7,colors.HexColor('#b8cecc')),('LINEBELOW',(0,1),(-1,-1),.3,colors.HexColor('#dbe4e4')),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6),('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6)]))
    story +=[tbl,Spacer(1,9)]
   elif t=='figure':
    path=ROOT/b['resolved_png']
    with PILImage.open(path) as im:iw,ih=im.size
    scale=min(W/iw,b['max_height_mm']*mm/ih);im=Image(str(path),width=iw*scale,height=ih*scale,hAlign='CENTER')
    story.append(KeepTogether([im,Spacer(1,4),para(b['caption'],'caption')]))
 def paint(canvas,doc):
  canvas.saveState();canvas.setStrokeColor(colors.HexColor('#cedcda'));canvas.setLineWidth(.5);canvas.line(20*mm,281*mm,190*mm,281*mm)
  canvas.setFont('Latin',8);canvas.setFillColor(colors.HexColor('#657e87'));canvas.drawString(20*mm,286*mm,'OPEN MICROLED DRIVER ASIC  /  DEVELOPMENT REVIEW')
  canvas.setFont('Body',8);canvas.drawString(20*mm,13*mm,'2026-11-08  |  实验性研发方法验证与教学')
  canvas.setFont('Latin',8);canvas.drawRightString(190*mm,13*mm,f'{doc.page:02d}')
  canvas.restoreState()
 doc=SimpleDocTemplate(str(DOC/'project-progress-report.pdf'),pagesize=A4,leftMargin=20*mm,rightMargin=20*mm,topMargin=24*mm,bottomMargin=20*mm,title='Open MicroLED Driver ASIC 开发进度与主要成果报告',author='Open MicroLED Driver ASIC project',pageCompression=1)
 doc.build(story,onFirstPage=paint,onLaterPages=paint)

CSS='''*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:#f1f4f3;color:#243e49;font:16px/1.72 "PingFang SC","Hiragino Sans GB",Arial,sans-serif}header{background:#213f4a;color:#fff;padding:25px max(24px,calc((100vw - 1080px)/2));font:14px/1.7 "Avenir Next","PingFang SC",sans-serif;letter-spacing:.04em}main{max-width:1120px;margin:auto;padding:26px 24px 60px;background:white}h1,h2,h3{font-family:"Avenir Next","PingFang SC",sans-serif;color:#246e73;line-height:1.35}h1{font-size:clamp(27px,3.4vw,40px);margin:4px 0 25px}h2{font-size:27px;margin:4px 0 22px}h3{font-size:20px;margin:18px 0 10px}p{margin:0 0 16px}a{color:#216e78;overflow-wrap:anywhere}section{padding:38px 8px 30px;border-bottom:1px solid #d3dfde;scroll-margin-top:15px}.kicker{font-size:14px;color:#6e838b;margin-bottom:8px}.note{font-size:15px;padding:15px 18px;background:#f0f5f4;border-left:3px solid #7aa5a4;color:#4d6873;margin:18px 0}.table-scroll{overflow-x:auto;margin:18px 0}table{border-collapse:collapse;width:100%;font-size:15px;line-height:1.65;min-width:560px}th,td{text-align:left;vertical-align:top;padding:12px 13px;border-bottom:1px solid #dbe4e3}th{color:#246e73;background:#eaf2f1}figure{margin:22px 0}figure img{display:block;max-width:100%;max-height:600px;width:auto;height:auto;margin:auto}figcaption{color:#5f7982;font-size:14px;line-height:1.6;margin-top:10px}.toc{background:#f0f5f4;padding:16px 20px;margin:20px 0}.toc summary{cursor:pointer;color:#246e73;font-weight:600}.toc ol{columns:2;column-gap:38px;padding-left:22px}.toc li{break-inside:avoid;margin:6px 0}.toolbar{display:flex;flex-wrap:wrap;gap:18px;font-size:15px;margin:12px 0 20px}.source{padding:14px 0;border-bottom:1px solid #dbe4e3;font-size:14px}.source code{word-break:break-all}.source p{margin:6px 0}b{font-weight:600}li{margin-bottom:9px}@media(max-width:650px){main{padding:18px 16px 40px}section{padding:28px 0}.toc ol{columns:1}table{font-size:14px}h2{font-size:24px}figure img{max-height:none}}@media print{body{background:white;font-size:11pt}header,.toolbar,.toc{display:none}main{max-width:none;padding:0}section{break-after:page;padding:0;border:0}figure img{max-height:115mm}table{font-size:9.5pt;min-width:0}.table-scroll{overflow:visible}.note{break-inside:avoid}tr{break-inside:avoid}}'''
def make_html_md(pages,sources):
 parts=[];md=[]
 for i,pg in enumerate(pages):
  parts +=[f'<section id="section-{i+1:02d}"><p class="kicker">{html.escape(pg["kicker"])}</p><h{1 if i==0 else 2}>'+html.escape(pg['title']).replace('\n','<br>')+f'</h{1 if i==0 else 2}>']
  md +=['# '+pg['title'].replace('\n',' '),'',pg['kicker'],'']
  for b in pg['blocks']:
   t=b['type']
   if t in ('p','note','h'):
    tag='h3' if t=='h' else 'p';cl=' class="note"' if t=='note' else '';parts +=[f'<{tag}{cl}>'+inline(b['text'],sources)+f'</{tag}>'];md +=[(('### ' if t=='h' else '> ' if t=='note' else '')+b['text']),'']
   elif t=='bullets':parts +=['<ol>'+''.join('<li>'+inline(x,sources)+'</li>' for x in b['items'])+'</ol>'];md +=['- '+x for x in b['items']]+['']
   elif t=='table':
    parts +=['<div class="table-scroll"><table><thead><tr>'+''.join('<th>'+inline(x,sources)+'</th>' for x in b['head'])+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+inline(x,sources)+'</td>' for x in row)+'</tr>' for row in b['rows'])+'</tbody></table></div>']
    md +=['| '+' | '.join(b['head'])+' |','|'+'|'.join(['---']*len(b['head']))+'|']+['| '+' | '.join(str(x).replace('\n','<br>').replace('|','&#124;') for x in row)+' |' for row in b['rows']]+['']
   elif t=='figure':
    data=base64.b64encode((ROOT/b['resolved_png']).read_bytes()).decode();parts +=[f'<figure><a href="{html.escape(b["original_link"])}" title="查看原图"><img src="data:image/png;base64,{data}" alt="{html.escape(b["caption"])}"></a><figcaption>'+html.escape(b['caption'])+'</figcaption></figure>'];md +=['!['+b['caption']+']('+b['local_asset']+')','',b['caption'],'']
  parts +=['</section>'];md +=['---','']
 parts +=['<section id="sources"><h2>来源与文件身份</h2><p>来源链接指向审计基线；本报告新增审计使用当前仓库文件。完整SHA与逐项条件见配套evidence。</p>']
 for s in sources.values():parts +=[f'<article class="source" id="source-{s["id"]}"><b>{s["id"]} · {html.escape(s["title"])}</b><p><a href="{s["url"]}">{html.escape(s["path"])}</a></p><p>{html.escape(s["locator"])}</p><code>SHA-256 {s["sha256"]}</code></article>'];md +=[f'[{s["id"]}]: {s["url"]} "{s["title"]}"']
 parts +=['</section>']
 toc='<details class="toc"><summary>阅读目录 · 17个章节与附录</summary><ol>'+''.join(f'<li><a href="#section-{i+1:02d}">'+html.escape(pg['title']).replace('\n',' ')+'</a></li>' for i,pg in enumerate(pages))+'</ol></details>'
 document='<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Open MicroLED Driver ASIC 开发进度与主要成果</title><style>'+CSS+'</style></head><body><header>OPEN MICROLED DRIVER ASIC · 编制2026-11-09 · 证据截至2026-11-08</header><main><div class="toolbar"><a href="project-progress-report.pdf">下载PDF</a><a href="README.md">文字版</a><a href="#sources">证据来源</a></div>'+toc+''.join(parts)+'</main></body></html>'
 (DOC/'index.html').write_text(document);(DOC/'README.md').write_text('\n'.join(md)+'\n')

def main():
 ASSET.mkdir(parents=True,exist_ok=True);EV.mkdir(parents=True,exist_ok=True);WORK.mkdir(parents=True,exist_ok=True)
 draw_diagrams();make_margin_chart();sources=prepare_sources();pages=prepare_pages(sources);make_html_md(pages,sources);make_pdf(pages,sources)
 dump(EV/'generation.json',{'prepared_date':'2026-11-09','evidence_as_of':'2026-11-08','expected_PDF_pages':len(pages),'report_sections':len(pages),'figures':len(FIGURES),'sources':len(sources),'PDF_font':'Embedded Heiti SC light/medium with Arial display; system PingFang is CFF and unsupported by ReportLab TTFont. HTML prefers PingFang SC.','python':sys.version,'evidence_cutoff':'2026-11-08; per-source runs retain original dates','new_simulation_or_hardware':False})
 print(json.dumps({'sections':len(pages),'figures':len(FIGURES),'sources':len(sources),'PDF':str((DOC/'project-progress-report.pdf').relative_to(ROOT))}))
if __name__=='__main__':main()
