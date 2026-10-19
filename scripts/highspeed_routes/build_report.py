# -*- coding: utf-8 -*-
"""Build the Chinese high-speed MicroLED route study from local evidence.

Original circuit drawings and budget calculations are concepts, not EDA results.
"""
from pathlib import Path
import html
import json

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'docs/research/highspeed-driver-routes-20261019'
records = json.loads((OUT / 'evidence-sources.json').read_text())['records']
sources = {r['id']: r for r in records}

def ref(key, label=None):
    r = sources[key]
    return f'<a href="{html.escape(r["primary_url"], quote=True)}" target="_blank" rel="noopener">{html.escape(label or r["title"])}</a>'

def figure(name, caption, alt=None):
    return f'<figure><a href="figures/{name}" target="_blank"><img loading="lazy" src="figures/{name}" alt="{html.escape(alt or caption, quote=True)}"></a><figcaption>{caption} · 点击图片打开原尺寸</figcaption></figure>'

def route(letter, title, subtitle, intro, steps, layout):
    return f'''<article class="route-panel" id="route-{letter}" role="tabpanel" aria-labelledby="tab-{letter}" {'hidden' if letter != 'a' else ''}>
    <div class="route-intro"><span class="tag">路线 {letter.upper()} · 原创概念电路</span><h3>{title}</h3><p class="lead">{subtitle}</p><p>{intro}</p></div>
    {figure(f'route-{letter}.svg', '标准 MOS 符号、器件端口、传统电流方向与逻辑状态；未选择 W/L，未做高速 SPICE。')}
    <div class="two"><div><h4>沿着电流路径读图</h4><ol>{''.join('<li>'+x+'</li>' for x in steps)}</ol></div><div class="note"><h4>芯片上怎样安排</h4><p>{layout}</p><p>图中的块是功能区，不是可制造单元。电源、保护、校准与数据通路都必须进入后续网表和版图。</p></div></div>
    {figure(f'floorplan-{letter}.svg', '芯片功能分区 Floorplan 概念：器件位置解释设计意图，不代表面积、金属层数或完成的布线。')}
    </article>'''

route_a = route('a', '受限摆幅 CMOS 电压驱动', '用较小的电压变化，切换 LED 的两个光强状态。',
    'MP 与 MN 构成互补输出级，OUT 在 V_H 与 V_L 之间切换；LED 从 VLED 接到 OUT。电压驱动是被研究的候选方法，不能据此推断任何未公开芯片的内部电路。', [
    '<b>DATA=1：</b>前置驱动令 CTRL 高，MN 导通、MP 关断。传统电流沿 VLED → LED → R_LIM → MN → V_L 流动，LED 达到 I₁。',
    '<b>DATA=0：</b>CTRL 低，MP 导通、MN 关断，将 OUT 拉向 V_H，减小 LED 正向压差。LED 电流为 I₀；只有电压与器件特性满足时，才接近关断。',
    '<b>电流由什么决定：</b>联立 LED 的 I–V 曲线、串联电阻和输出晶体管导通特性。近似 VLED−VOUT = V_F(I)+I·R_LIM，不能把电压码直接当成恒流码。',
    '<b>偏置与校准：</b>可慢速调节电源轨或分段输出强度以修正 I₀/I₁。监测回路不必逐比特跟随，但需要温度与批次校准证据。',
    '<b>必须检查：</b>若 V_H&lt;VLED 且 I₀ 非零，暗态电流可能经 MP 回灌到 V_H。上轨需有吸收电流能力或另设偏置路径；浮动低轨、体端隔离、交越电流与所有端间耐压均待验证。'],
    '前置驱动靠近 MP/MN，MP/MN 靠近 LED 焊点。输出节点尽量小；高、低轨的本地去耦和回流要一起规划。若 V_L 不等于衬底电位，必须确认隔离阱或 SOI 等实际工艺选项，不能任意接体端。')
route_b = route('b', '恒流源 + 差分电流转向 OOK', '保持尾电流，把它切向 LED 或 Dummy 旁路。',
    '这是容易看清 IREF、镜像偏置和数据开关如何分工的基线。公开论文已有 NMOS 恒流源、cascode 和差分转向的实例；本图为独立教学简化，省略可选 cascode。' + ref('HS19-DLC', '电路依据：Jalajakumari 等，2017。'), [
    '<b>建立尾电流：</b>IREF 流经二极管连接 MREF，建立 BIAS。MI 与 MREF 共栅；在足够 VDS、匹配和相同温度等条件下，I_T 近似等于 IREF×(W/L)_MI/(W/L)_MREF。沟道长度调制与失配使其不精确。',
    '<b>DATA=1：</b>G+ 高于 G−（共模与摆幅另设），ML 导通。电流沿 VLED → LED → ML → MI → VSS，LED 发光。',
    '<b>DATA=0：</b>G+ 低于 G−（共模与摆幅另设），MD 导通。电流沿 VDUMMY → R_DUMMY → MD → MI → VSS。LED 支路降低电流，但尾电流持续存在。',
    '<b>为什么可能更快：</b>数据只改变转向开关，不反复建立参考电流。中间节点 VX 摆幅若受控，可以减轻充放电与电流源恢复；效果必须用寄生和实际负载验证。',
    '<b>为什么未必更省电：</b>Dummy 的电压、电流、互补预驱动都耗能。开关重叠/短暂全关会造成分流或 VX 扰动；I_LED+I_DUMMY≈I_T 只在稳态且有足够电压余量时成立。'],
    'ML、MD 与 MI 紧凑放置，互补控制线长度和负载尽量对称。LED 支路与 Dummy 支路的阻抗差会引起动态电流变化。偏置线远离高速时钟，本地去耦；镜像器件匹配、保护和电流密度仍需版图设计。')
route_c = route('c', '分段电流 DAC / PAM4', '每个符号从四档电流中选择一档，传递两位信息。',
    '三个等权电流转向单元并联到同一 LED，每单元尾电流 Iu 持续流动。温度计编码选择 0、1、2、3 个单元，获得四个电平。这是 2-bit 教学例；更高分辨率 DMT/OFDM DAC 需要更多单元、采样与 DSP。' + ref('HS19-DAC', '电流 DAC 与多电平链路依据：Rajbhandari 等，2017。'), [
    '<b>编码：</b>符号码 0/1/2/3 转成图中 t₁t₂t₃ 温度计码 000/100/110/111。符号编号与用户比特之间可另用 Gray 映射；码表不是唯一协议。',
    '<b>电流相加：</b>被选单元把 Iu 导向 LED，其他单元导向 Dummy；理想 LED 电流为 0、Iu、2Iu、3Iu。非零最低偏置 I₀ 需要另加可控偏置支路。',
    '<b>码率：</b>PAM4 的毛比特率 Rg=2Rs，NRZ/OOK 为 Rg=Rs。相同符号率下承载更多位，但不能在相同噪声和摆幅下免费获得两倍可靠速率。',
    '<b>关键难点：</b>单元失配与切换偏斜产生 DNL/INL 和毛刺；LED 的电流—光功率非线性使等电流间隔不等于等光功率间隔。接收器要分辨三个判决门限。',
    '<b>能量：</b>此例三个尾源一直开，稳态总尾电流为 3Iu，未选电流在 Dummy 消耗。关闭未用尾源是另一个低功耗变体，会重新引入电流建立时间，不能与本图混算。'],
    '将电流单元排成规则匹配阵列，偏置对称、译码与锁存靠近开关，控制同一符号的到达偏斜。LED 汇流节点的金属与漏端电容随单元数增加；需要电流密度、匹配、RC 和串扰共同优化。')

rows = [
 ('HS19-DLC','2017 · 集成电路 + 光链路','365 Mb/s · 16-QAM OFDM · 5 cm','BER 门限 1×10⁻³；16 个发光元件作幅度单元，不是 16 条独立 lane。完整 Tx 能耗缺少同口径数据。'),
 ('HS19-DAC','2017 · 集成 DAC 光链路','4 路总计 1.23–1.30 Gb/s · 4-PAM · 1 m','BER 门限 3.8×10⁻³；文中 7.48 Gb/s 是另一个 9 路 AWG 实验，不能归到该 ASIC。'),
 ('HS19-CSM','2022 · 作者会议全文','2 Gb/s OOK；约 1.5 pJ/bit 光源 + 0.5 pJ/bit 接收','原文报告总计 &lt;2 pJ/bit，并明确排除 50 Ω 输出驱动。32 路 SOI 阵列是另一个展示条件。'),
 ('HS19-OFC','2024 · 原始摘要','16 nm CMOS；304 通道；3.3 Gb/s/lane','摘要称约 1 pJ/bit、1 Tb/s 能力；未核对完整供电清单、全通道并发或所有测量条件。'),
 ('HS19-HOTI','2025 · 原始摘要','约 300 路 ASIC：3.5 Gb/s/lane；另有单路 11.2 Gb/s','约 1 pJ/bit 与最长 30 m 的归属仍需全文核对，不能把四个数字拼成一个工作点。'),
 ('HS19-MOSAIC','2025 · 原型实测 + 独立估算','2 Gb/s/lane · 20 m；100 通道原型，每次测 25 路','800G 时每端 3.1–5.3 W 为作者估算；50 m 是仿真。不是 FPGA 原型的功耗或速率实测。'),
 ('HS19-80FJ','2025 · 企业公开披露','4 Gb/s；100 μA；80 fJ/bit per LED','报告 raw BER 10⁻¹²、无 FEC。Rx、数字及额外驱动/供电损耗未明确包含，不能称全链路 80 fJ/bit。'),
 ('HS19-LIN','2026 · 器件光链路实测','1.5 Gb/s OOK；25 μA；56 fJ/bit','56 fJ 仅 LED 直流输入/毛码率；BER=3.1×10⁻³。6.35 Gb/s OFDM 使用另一尺寸、80 mA 工作点。')
]
table = ''.join(f'<tr><td><b>{kind}</b><br>{ref(key, sources[key]["authors"])}</td><td>{point}</td><td>{boundary}</td></tr>' for key,kind,point,boundary in rows)
refs = ''.join(f'<li id="{r["id"]}"><b>{ref(r["id"])}</b><br><span class="muted">{html.escape(r["locator"])} · {html.escape(r["evidence_class"])}</span></li>' for r in records)

page = r'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>高速 MicroLED Driver：电路、芯片与速率—能耗取舍</title>
<style>
:root{--ink:#203847;--muted:#617784;--teal:#086f73;--line:#d9e4e5;--paper:#fbfcfc;--soft:#edf5f4;--warm:#fff7e9}*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:80px}body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.75 'PingFang SC','Noto Sans CJK SC','Microsoft YaHei',sans-serif}a{color:var(--teal);text-underline-offset:3px}a:hover{color:#0b9297}button,input,select{font:inherit}header{max-width:1240px;margin:auto;padding:70px 44px 40px}h1{font-size:clamp(32px,4vw,54px);line-height:1.25;letter-spacing:-.02em;margin:14px 0 22px;max-width:1000px}h2{font-size:30px;line-height:1.4;margin:10px 0 22px}h3{font-size:25px;line-height:1.4;margin:10px 0}h4{font-size:18px;margin:16px 0 8px}p{margin:10px 0 18px}b,strong{font-weight:600}main{max-width:1240px;margin:auto;padding:0 44px 80px}.kicker,.tag{color:var(--teal);font-size:13px;letter-spacing:.07em}.lead{font-size:20px;line-height:1.65;max-width:950px}.muted,figcaption{color:var(--muted)}.status{background:var(--soft);border-left:4px solid var(--teal);padding:17px 22px;margin:24px 0}.status p{margin:0}.nav{position:sticky;top:0;z-index:10;background:#fbfcfcf5;border-block:1px solid var(--line);backdrop-filter:blur(10px)}.nav div{max-width:1240px;margin:auto;display:flex;gap:25px;overflow:auto;white-space:nowrap;padding:12px 44px}.nav a{font-size:14px;text-decoration:none}section{padding:56px 0 22px;border-bottom:1px solid var(--line)}.two{display:grid;grid-template-columns:1fr 1fr;gap:28px}.three{display:grid;grid-template-columns:repeat(3,1fr);gap:20px}.card,.note{padding:24px;border:1px solid var(--line);border-radius:12px;background:white}.note{background:var(--soft)}.caution{background:var(--warm);border-color:#eadcc0}.card p:last-child,.note p:last-child{margin-bottom:0}.number{font-size:36px;line-height:1.2;color:var(--teal)}figure{margin:24px 0 32px;background:white;border:1px solid var(--line);border-radius:10px;overflow:hidden}figure img{display:block;width:100%;height:auto}figcaption{font-size:13px;padding:12px 18px;border-top:1px solid var(--line)}.tabs{display:flex;gap:12px;margin:26px 0 30px;flex-wrap:wrap}.tabs button{border:1px solid var(--line);padding:12px 20px;border-radius:7px;background:white;color:var(--ink);cursor:pointer}.tabs button[aria-selected=true]{background:var(--teal);color:white;border-color:var(--teal)}[hidden]{display:none!important}ol,ul{padding-left:23px}li{padding:4px 0 9px}table{width:100%;border-collapse:collapse;font-size:15px}th{text-align:left;background:var(--soft);font-weight:600}td,th{padding:16px 14px;vertical-align:top;border-bottom:1px solid var(--line)}td:first-child{width:26%}td:nth-child(2){width:32%}.table-scroll{overflow:auto}code,.formula{font-family:'SFMono-Regular',Consolas,monospace;font-size:14px}.formula{background:#eff3f5;border-radius:5px;padding:16px;overflow-x:auto}.flow{display:grid;grid-template-columns:repeat(6,1fr);gap:12px;margin:24px 0}.flow .node{position:relative;border:1px solid var(--line);border-top:4px solid var(--teal);background:white;padding:18px 12px;border-radius:5px;line-height:1.6}.flow .node:not(:last-child)::after{content:'→';position:absolute;right:-16px;top:37px;z-index:2;color:var(--teal)}.node b{display:block;font-size:17px}.node small{font-size:12px;display:block;margin-top:10px;color:var(--muted)}.controls{display:grid;grid-template-columns:1fr 1fr;gap:22px}.controls label{display:flex;justify-content:space-between;margin-bottom:8px}.controls input[type=range]{width:100%;accent-color:var(--teal)}select{width:100%;padding:8px;border:1px solid var(--line);border-radius:4px;background:white}.results{display:grid;grid-template-columns:repeat(3,1fr);gap:20px;margin-top:26px}.results .card{background:var(--soft)}.results output{display:block;font-size:29px;color:var(--teal);font-variant-numeric:tabular-nums}.result-note{font-size:13px;margin-top:14px}.ref-list{font-size:14px;overflow-wrap:anywhere}.ref-list li{padding-bottom:20px}.pill{display:inline-block;background:var(--soft);padding:4px 10px;border-radius:20px;font-size:12px;margin:3px}.downloads{display:flex;gap:12px;flex-wrap:wrap}.downloads a{border:1px solid var(--line);background:white;padding:9px 15px;border-radius:6px;text-decoration:none}.step{display:grid;grid-template-columns:52px 1fr;gap:18px;padding:22px 0;border-bottom:1px solid var(--line)}.step:last-child{border:0}.step .index{font-size:29px;color:var(--teal)}.step h4{margin-top:0}footer{padding-top:35px;font-size:13px;color:var(--muted)}
@media(max-width:800px){header{padding:38px 22px 20px}main{padding:0 22px 50px}.nav div{padding:12px 22px;gap:20px}.two,.three,.controls{grid-template-columns:1fr}.flow{grid-template-columns:repeat(2,1fr)}.flow .node:nth-child(even)::after{display:none}.results{grid-template-columns:1fr}h2{font-size:26px}h3{font-size:23px}.lead{font-size:18px}td,th{padding:12px;min-width:180px}.tabs{gap:7px}.tabs button{padding:9px 12px}section{padding-top:40px}}
@media print{.nav,.tabs,.controls,.interactive-only{display:none!important}.route-panel[hidden]{display:block!important}.route-panel{break-before:page}header,main{padding:0}body{font-size:10.5pt;background:white}h1{font-size:28pt}h2{font-size:20pt}section{padding-top:20px}figure,.card,.note{break-inside:avoid}a{color:inherit}footer{margin-top:20px}@page{size:A4;margin:18mm}}
</style></head><body>
<header><div class="kicker">OPEN MICROLED DRIVER ASIC · 研究专题 2026-10-19</div><h1>高速 MicroLED Driver<br>从晶体管电路，到芯片与光链路</h1><p class="lead">怎样同时追求更高传送速率和更低每比特能耗？先把可选电路画清楚，再用相同的光路、误码率和供电范围做比较。</p>
<div class="status"><p><b>本轮成果：</b>3 条 ASIC 候选路线的 MOS 电路图与功能分区图、仪器表征电路、Blender 封装概念、8 条原始文献索引，以及可复算的能耗预算。<br><b>证据阶段：</b>原理设计与解析预算。尚未完成这些高速候选电路的晶体管仿真、DRC/LVS/PEX、硅片或光链路 BER 验证。</p></div>
<div class="downloads"><a href="#routes">先看三条电路路线 ↓</a><a href="#budget">调参数看能耗 ↓</a><a href="#plan">看下一步验证顺序 ↓</a></div></header>
<nav class="nav" aria-label="报告目录"><div><a href="#decision">研究结论</a><a href="#system">完整架构</a><a href="#routes">电路与芯片</a><a href="#bench">表征与预加重</a><a href="#package">封装与材料</a><a href="#evidence">论文数据</a><a href="#budget">速率与能耗</a><a href="#plan">验证路线</a><a href="#sources">索引与下载</a></div></nav>
<main>
<section id="decision"><span class="tag">01 · 先确定可检验的问题</span><h2>先做单通道 NRZ，再判断是否值得增加电路复杂度</h2><p>本研究以短距离芯片间／板间光互连为主要应用假设。自由空间可见光通信论文可提供电路与测量方法，但它们的距离、耦合效率和接收器不同，不能直接变成我们的能耗指标。</p>
<div class="three"><div class="card"><div class="number">A</div><h4>低能耗候选</h4><p>受限摆幅电压驱动，减少节点充放电。代价是 LED 电流随电压、温度和工艺变化，需要校准与耐压设计。</p></div><div class="card"><div class="number">B</div><h4>单通道研究基线</h4><p>恒流源持续建立，差分开关转向电流。适合先验证电流与数据的分工，代价是 Dummy 旁路的静态功耗。</p></div><div class="card"><div class="number">C</div><h4>后续多电平扩展</h4><p>电流 DAC 形成 PAM4，提升每符号信息量。必须付出线性度、匹配、接收信噪比、时钟与编码的成本。</p></div></div>
<p><b>建议：</b>先将 B 建成可校准的单 lane 基线，同时用 A 在同一个实测 LED 模型上做能量对照。完成单 lane 版图和寄生验证后，再决定预加重、PAM4 或多 lane 并行。总吞吐不足时，并行低速 lane 可能比继续推高单 LED 速率更合适，但须计入每路接收器、耦合与面积。</p>
<div class="note"><b>“最大”必须带条件。</b>目标是找出在约定 BER、温度、距离、有效载荷和功耗边界下，无法再同时提高速率和降低能耗的可行点。当前只有候选方法与不同条件的公开证据，还没有本项目的实测最优点或全行业最高纪录结论。</div></section>

<section id="system"><span class="tag">02 · 数据如何变成光</span><h2>驱动器只是链路的一部分</h2><div class="flow" role="img" aria-label="数据与PRBS，经时序和前驱动、MOS输出级、MicroLED与光路，到光电探测接收判决和BER统计"><div class="node"><b>数据／PRBS</b>有效载荷、测试码<small>可选编码与 FEC</small></div><div class="node"><b>时序与前驱动</b>锁存、互补／电平转换<small>需要时才串化；时钟需预算</small></div><div class="node"><b>MOS 输出级</b>A 电压 / B 转向 / C DAC<small>数据快路径；参考慢路径</small></div><div class="node"><b>MicroLED</b>I(t) → P光(t)<small>I–V、结电容、载流子动态</small></div><div class="node"><b>耦合与光路</b>封装、透镜、光纤<small>损耗、距离、串扰</small></div><div class="node"><b>PD / TIA / 判决</b>光 → 电 → 数据<small>噪声、均衡、误码统计</small></div></div>
<div class="two"><div><h4>与当前 PWM 像素有什么不同？</h4><p>PWM 用占空比控制一段时间内的平均电流；高速 NRZ/OOK 要让每个符号的光状态能被接收器分辨。两者都用 MOS，但关键性能从平均电流误差，转向带宽、边沿、抖动、码间干扰、噪声与能量。</p><p>已有单像素的参考、关断、验证脚本与版图流程可作为方法基础。现有 PWM 模型和通过的检查不能证明高速链路可用。</p></div><div class="note"><h4>慢控制不应被每个比特重新建立</h4><p>参考电流、偏置、温度校准和故障关断负责设定工作区；高速前置驱动和输出开关传输数据。保护信号应能覆盖数据路径，同时验证关断光残留、恢复时序和电源异常。</p><p>理想 IREF、理想数据源和理想接收器都只是接口占位，必须逐项替换并测量其功耗与非理想行为。</p></div></div></section>

<section id="routes"><span class="tag">03 · 标准电路与芯片分区</span><h2>三条路线逐一展开</h2><p>下图采用常规 MOS 器件符号；箭头表示传统电流方向。每个器件的 D/G/S/B 连接另存于 <a href="figures/circuit-metadata.json">连接元数据</a>。这些图解释候选设计，不表示任何厂商的真实内部实现。</p>
<div class="tabs" role="tablist" aria-label="候选驱动电路"><button id="tab-a" role="tab" aria-selected="true" aria-controls="route-a" data-route="a">A · 电压驱动</button><button id="tab-b" role="tab" aria-selected="false" aria-controls="route-b" data-route="b">B · 电流转向 OOK</button><button id="tab-c" role="tab" aria-selected="false" aria-controls="route-c" data-route="c">C · 电流 DAC / PAM4</button></div>
@@ROUTES@@
<div class="table-scroll"><table><thead><tr><th>路线</th><th>可能的收益</th><th>最先要证伪的问题</th></tr></thead><tbody><tr><td>A · 电压驱动</td><td>缩小输出摆幅；减少不必要的静态旁路</td><td>能否在 PVT 下得到所需 I₀/I₁，并满足耐压、回灌与光调制幅度？</td></tr><tr><td>B · 电流转向</td><td>稳定偏置；减轻电流源重复建立</td><td>动态尾电流是否稳定？速度收益能否抵消 Dummy 与互补控制耗能？</td></tr><tr><td>C · PAM4 / DAC</td><td>同符号率承载更多位；可校准幅度</td><td>光电平是否可分辨？DAC 与 LED 非线性、噪声和能耗是否仍满足预算？</td></tr></tbody></table></div></section>

<section id="bench"><span class="tag">04 · 仪器实验与可叠加方法</span><h2>先测器件极限，再决定 ASIC 要承担哪些功能</h2><p>AWG/DAC、RF 放大器和 Bias-T 可以分别设置交流调制与直流偏置，适合测 LED 的电光频响与通信能力。Bias-T 通过电容耦合交流、通过电感馈入直流；真实器件存在带宽、自谐振、阻抗和损耗。高性能仪器结果不等于同速率低功耗 CMOS ASIC 已实现。</p>
@@BENCH@@
<div class="two"><div class="card"><h4>预加重 / FFE：边沿加力，稳态减力</h4><p>在上升沿短暂增加电流，或在下降沿提供合规的电荷移除路径，用额外高频分量补偿链路低通衰减。它可叠加在 A、B、C 路线上，不是独立的 MOS 材料。</p><div class="formula">Qedge = ∫ ΔI(t) dt<br>例：1 mA × 50 ps = 50 fC</div><p>这个电荷尺度不等于光响应提升。还要检查 LED 峰值电流、反向电压、驱动器过冲、码型依赖、额外门控及接收均衡功耗。</p></div><div class="card"><h4>PAM4 与 DMT/OFDM 不能混为一谈</h4><p>PAM4 直接选择四个瞬时幅度；DMT/OFDM 通过多子载波、DAC 与 DSP 生成更复杂的波形，并为光强调制加入合适的偏置和约束。高峰均比、削顶和 LED 非线性会降低效率。</p><p>论文测得的 OFDM 高速率，只证明指定仪器、算法和工作点下的链路能力。ASIC 还要承担 DAC 采样、时钟、DSP、输出余量与散热。</p></div></div></section>

<section id="package"><span class="tag">05 · 从电路到芯片</span><h2>输出级靠近 LED，回流路径与信号路径一起设计</h2>
@@PACKAGE@@
<div class="downloads"><a href="package-concept.blend">下载可编辑 Blender 场景</a><a href="package-concept.json">场景边界与版本记录</a><a href="font-license.txt">场景内字体许可</a></div>
<div class="two"><div><h4>材料与工艺：驱动 MOS 和发光器件分开看</h4><p>本图下层是硅 CMOS 驱动芯片，上层是独立的 III–V 发光器件，例如 InGaN/GaN MicroLED。公开实例中有 130 nm SOI、0.18 μm CMOS 和 16 nm CMOS；不同实验并不具有相同负载与性能。</p><p>SOI 是硅器件的绝缘衬底结构，不能解读为 GaN MOS。更先进数字节点可能降低逻辑功耗与面积，但核心器件允许电压更低；驱动 LED 可能需要合适的 I/O 器件、电平转换、隔离或异质集成。</p><p class="muted">工艺证据：@@PROCESSREFS@@</p></div><div><h4>高速布局要解决的具体问题</h4><ul><li>缩小 LED 阴极到输出 MOS 的电容、电阻与回路电感；同时检查供电和回流。</li><li>互补控制线匹配，避免不对称延迟；DAC 单元匹配并抑制开关毛刺。</li><li>输出与时钟远离参考偏置；本地去耦、封装谐振、同时切换噪声共同仿真。</li><li>焊盘、ESD、凸点与键合寄生可能比晶体管本体更限制带宽。短垂直互连是候选方法，工艺与成本仍需确认。</li></ul></div></div>
<div class="note"><b>现在不填虚构的层数和面积。</b>金属层数、介质厚度、凸点规则与可用器件由匹配的 PDK 和封装平台决定。面积先用 A数字单元/利用率 + A模拟宏 + A供电/布线 + A焊盘/ESD/凸点保留区做预算，再由布局验证。Blender 只呈现空间关系；没有新增电磁、热、光场、制造或 GDS 验证。</div></section>

<section id="evidence"><span class="tag">06 · 已有技术路线与公开数据</span><h2>速率与能耗必须连同工作条件阅读</h2><p>下表索引截至本次检索的 8 条原始来源。它展示已发表的方法与工作点，不是统一条件下的排名，也不是穷尽全部文献。未公开的输出电路和能耗分项保留为缺口。</p><div class="table-scroll"><table><thead><tr><th>来源与证据类型</th><th>可核实的工作点</th><th>能耗与结论的边界</th></tr></thead><tbody>@@TABLE@@</tbody></table></div>
<div class="note caution"><h4>两个容易误读的“低能耗点”</h4><p><b>56 fJ/bit：</b>3.360 V × 25 μA / 1.5 Gb/s = 56 fJ/bit。这是 LED 直流输入指标；该工作点 BER 为 3.1×10⁻³，使用 FEC 门限判断，未包含完整驱动 ASIC 与接收端。</p><p><b>80 fJ/bit：</b>企业公开披露的每 LED 发射端指标，详细附加驱动、电源和接收边界未完全公开。它不能与前述 LED DC 指标直接排名，更不能称全链路能量。</p><p>本项目的比较表必须同时填写：调制、毛/净速率、BER 与比特数、lane 并发数、距离/耦合、温度、LED 工作点、全部电源和接收条件。</p></div>
<p>完整出处、页码与未解决项见 <a href="evidence-sources.json">机器可读证据索引</a>和 <a href="evidence-notes.md">中文核对笔记</a>。原始图与上下文仅存于本地研究区：<a href="http://127.0.0.1:8772/" target="_blank">打开私人原图证据卡</a>；本报告插图为独立绘制。</p></section>

<section id="budget"><span class="tag">07 · 可复算的设计预算</span><h2>先明确能量算到哪里，再谈降低多少</h2><div class="formula">P = (1/T) ∫ Σ[Vrail(t) · Irail(t)] dt<br>Egross = P / Rgross　　Enet = P / (η · Rgross)<br>η = Rnet / Rgross；多 lane 时 Rnet,total = N · η · Rgross,lane</div>
<p>实际电路需要逐电源积分，并约定回灌能量的处理与稳压器损耗。只算 LED、算完整 Tx、算 Tx+Rx、算双向模块，会得到不同结果。总功耗相除的吞吐分母也必须匹配方向和净／毛比特。</p>
@@ENERGY@@
<div class="two"><div class="card"><h4>电容项：平方关系很重要，但只是一部分</h4><p>随机独立 NRZ 中 p(0→1)=0.25。对于 0/ΔV 专用电源驱动、充分充放电、无能量回收的理想电容：</p><div class="formula">Ecap = 0.25 Ceff ΔV²<br>80 fF × 1 V² × 0.25 = 20 fJ/毛比特<br>ΔV 减半 → 5 fJ/毛比特</div><p>这里的 Ceff 是教学用等效预算，不能直接替代带偏置、非线性结电容与多个电源的 LED 电路。实际 A/B 的电容、摆幅与外围功耗应分别提取。</p></div><div class="card"><h4>静态项：Dummy 电流不能漏算</h4><p>假设同一 LED 电流状态 0/100 μA、等概率随机比特、3.2 V 电源：</p><div class="formula">直接开关平均支路功率 = 0.16 mW<br>同电源连续转向总功率 = 0.32 mW<br>其中 LED 平均 0.16 + Dummy 平均 0.16 mW</div><p>这是电源端预算，已包含该支路的电压余量耗散。低压 Dummy 可以改变结果，但其电源、稳定性和转换损耗也要进入模型。</p></div></div>
<h3>交互：改变电容、摆幅与并行数</h3><p>以下只用于理解公式，<b>输入速率不是电路已能实现的速率</b>。固定 I₁=100 μA、I₀=0、Vrail=3.2 V、p₁=0.5；每 lane 的前驱动/偏置/时钟占位为 0.20 mW，共享 Tx 逻辑为 1 mW，净／毛效率 η=0.9。Rx、稳压损耗、冷却、主机及光路损耗未计入。</p>
<div class="card"><div class="controls"><div><label for="cap">等效电容 Ceff <output id="cap-value">80 fF</output></label><input id="cap" type="range" min="40" max="1000" step="10" value="80"></div><div><label for="swing">电压摆幅 ΔV <output id="swing-value">1.0 V</output></label><input id="swing" type="range" min="0.4" max="1.8" step="0.1" value="1"></div><div><label for="rate">单 lane 毛速率（假设）<output id="rate-value">4.0 Gb/s</output></label><input id="rate" type="range" min="0.5" max="10" step="0.5" value="4"></div><div><label for="lanes">独立并行通道 N <output id="lanes-value">1</output></label><input id="lanes" type="range" min="1" max="64" step="1" value="1"></div><div><label for="mode">静态支路预算</label><select id="mode"><option value="direct">直接开关：0.16 mW / lane</option><option value="steer">连续转向：0.32 mW / lane</option></select></div><div class="muted">两种模式暂用相同 C、ΔV 与外围占位，专门隔离 Dummy 静态成本。未证明相同 OMA、BER 或器件电压余量，不作物理性能优劣判定。</div></div>
<div class="results" aria-live="polite"><div class="card">条件净吞吐<output id="out-rate">3.60 Gb/s</output></div><div class="card">条件 Tx 功耗预算<output id="out-power">1.44 mW</output></div><div class="card">每净比特能耗预算<output id="out-energy">400.0 fJ/bit</output></div></div><p class="result-note" id="out-detail">单 lane 电容项 20.0 fJ/毛比特；每 lane 功率 0.440 mW；共享逻辑只计一次。</p></div>
@@PARALLEL@@
<div class="note caution"><b>提高 R 会在公式里摊薄静态能量，但不保证链路可用。</b>当眼图、接收噪声或器件耐压先失效时，该点不可用。64×4 Gb/s×0.9=230.4 Gb/s 只是条件吞吐，要求所有 lane、接收器与接口都满足条件。η=0.9 相当于相对有效载荷约 11.11% 开销。</div>
<h3>带宽与布线的尺度，不能省略</h3><div class="two"><div><div class="formula">fRC = 1 / (2πRC)<br>fcarrier = 1 / (2πτ)<br>|H(f)|² = 1 / [(1+(f/fRC)²)(1+(f/fcarrier)²)]</div><p>两独立极点假设下，R=100 Ω、C=200 fF、τ=200 ps，综合 −3 dB 约 0.788 GHz。这里的 τ 与 C 都是假设，未按 LED 测量拟合；−3 dB 带宽不能直接换算成“最大 Gb/s”。</p></div><div><div class="formula">ΔV ≈ L · ΔI / Δt<br>L=0.5 nH，Δt=100 ps：<br>ΔI=100 μA → 0.5 mV<br>ΔI=5 mA → 25 mV</div><p>边沿电流越大，回路电感影响越明显。这只是局部尺度；完整设计还要包括回流、互感、反射、封装谐振和电源阻抗。</p></div></div>
<p>详细两极点推导、全部单位、假设与 73 项解析自检见 <a href="numerical-notes.md">计算说明</a>及 <a href="calculations.json">数值数据</a>。这些检查保证公式实现一致，不验证假设器件。</p></section>

<section id="plan"><span class="tag">08 · 可执行的后续研究</span><h2>把候选图变成可以比较的芯片设计</h2><p>当前开源环境适合做电路方法验证与公开 PDK 的物理流程练习。我们的 GF180 单像素流程可提供网表、仿真、布局、DRC/LVS/PEX 的组织方式；它不会自动继承论文中 AMS180、SOI 或 16 nm 工艺的高速性能。</p>
<div class="step"><div class="index">01</div><div><h4>先锁定 LED 与光链路的可测接口</h4><p>获取同一颗器件随偏置和温度变化的 I–V、L–I、C–V/小信号阻抗、电光 S21；记录探针、夹具、校准面和去嵌方式。确定接收噪声、距离/耦合、OMA、BER、温度和功率计入范围。没有这些数据时，只允许灵敏度扫描。</p></div></div>
<div class="step"><div class="index">02</div><div><h4>单 lane A/B 电路：DC → 瞬态 → PVT</h4><p>用可获得的合规 PDK 器件实现前驱动、电平转换、参考、开关和保护。先校验 I₀/I₁、电压余量、所有端间应力与回灌；再扫 0.5/1/2/4 Gb/s 等输入测试点，观察 PRBS、长连 0/1、交替码与故障。所有电源积分，输出眼图／光响应须由已标定模型支持。扫描数值不表示已达成速率。</p></div></div>
<div class="step"><div class="index">03</div><div><h4>完成一个通道的真实布局与寄生闭环</h4><p>沿用匹配完整 PDK 的 Magic/KLayout、Netgen 与提取流程，得到 DRC、LVS、PEX 及端口对应证据。再补焊盘、ESD、键合/凸点和回流的 RLC 或 S 参数；需要时做电磁与电源完整性分析。标准 RC PEX 不能代替所有高频封装效应。</p></div></div>
<div class="step"><div class="index">04</div><div><h4>同条件测量能量与 BER，再选择路线</h4><p>用测试码发生器/误码仪、示波器和已表征 PD/TIA，固定光路、温度、净速率与 BER 目标，记录全部供电及数据概率。零误码不等于 BER=0；在独立平稳误码近似下，零错误 N bits 的单侧 95% 上界约为 3/N。要支持 10⁻¹² 量级，需要约 3×10¹² bits 和明确的统计条件。</p></div></div>
<div class="step"><div class="index">05</div><div><h4>按瓶颈决定 FFE、PAM4 或多 lane</h4><p>带宽受限且 SNR 充足时研究预加重／多电平；接收灵敏度不足时优先优化光路和接收端；单 lane 已合格而总吞吐不足时，再评估并行及其面积、热、串扰、同步和共同供电。每增加一级，保留同条件的速度—能量对照。</p></div></div>
<div class="note"><h4>这一阶段的退出条件</h4><p>一套可复现的单 lane 网表与模型、一组同条件 A/B 波形及全部电源能量、器件应力/PVT 记录、真实布局与寄生证据、明确接收条件，以及失败点和下一步假设。用这些证据确认候选工艺是否适用、修订面积预算，并决定是否推进测试流片。</p><p><a href="https://gf180mcu-pdk.readthedocs.io/en/latest/physical_verification/design_manual/drm_14_1.html" target="_blank" rel="noopener">GF180 原始器件可靠性规则</a>要求按实际器件和端间电压检查；公开模型存在并不代表具备目标频率的测量验证或制造签核。</p></div></section>

<section id="sources"><span class="tag">09 · 可追溯与可编辑</span><h2>参考文献与源文件</h2><ol class="ref-list">@@REFS@@</ol>
<div class="downloads"><a href="evidence-sources.json">8 条来源及原图定位</a><a href="evidence-notes.md">证据核对笔记</a><a href="calculations.json">计算 JSON</a><a href="numerical-notes.md">计算推导</a><a href="figures/circuit-metadata.json">MOS 端口连接</a><a href="package-concept.blend">Blender 场景</a><a href="README.md">复现与文件说明</a></div></section>
<footer>实验性研发方法验证与教学 · 所有候选电路和芯片示意为本项目原创概念图。论文数据按原条件转述，预算与实测分开记录。现有 PWM 项目继续保留独立证据。<br>本页可离线阅读；原始来源链接需网络，私人证据卡需本机服务。制作：2026-10-19。</footer></main>
<script>
const tabs=[...document.querySelectorAll('[data-route]')];
function selectRoute(id){tabs.forEach(t=>{const active=t.dataset.route===id;t.setAttribute('aria-selected',String(active));t.tabIndex=active?0:-1;document.querySelector('#route-'+t.dataset.route).hidden=!active;});}
tabs.forEach((t,i)=>{t.addEventListener('click',()=>selectRoute(t.dataset.route));t.addEventListener('keydown',e=>{if(['ArrowLeft','ArrowRight','Home','End'].includes(e.key)){e.preventDefault();let j=e.key==='Home'?0:e.key==='End'?2:(i+(e.key==='ArrowRight'?1:2))%3;selectRoute(tabs[j].dataset.route);tabs[j].focus();}});});selectRoute('a');
function updateBudget(){const get=id=>Number(document.getElementById(id).value);const c=get('cap'),v=get('swing'),r=get('rate'),n=get('lanes');const dc=document.getElementById('mode').value==='direct'?.16:.32;const ecap=.25*c*v*v;const plane=dc+ecap*r/1000+.20;const p=n*plane+1;const net=n*.9*r;const enet=1000*p/net;for(const [id,value]of Object.entries({'cap':c+' fF','swing':v.toFixed(1)+' V','rate':r.toFixed(1)+' Gb/s','lanes':String(n)})){document.getElementById(id+'-value').textContent=value;}document.getElementById('out-rate').textContent=net.toFixed(2)+' Gb/s';document.getElementById('out-power').textContent=p.toFixed(2)+' mW';document.getElementById('out-energy').textContent=enet.toFixed(1)+' fJ/bit';document.getElementById('out-detail').textContent=`单 lane 电容项 ${ecap.toFixed(1)} fJ/毛比特；每 lane 功率 ${plane.toFixed(3)} mW；共享逻辑只计一次。此处为解析预算，未验证链路可用性。`;}
document.querySelectorAll('.controls input,.controls select').forEach(el=>el.addEventListener('input',updateBudget));updateBudget();
</script></body></html>'''

page = page.replace('@@ROUTES@@', route_a + route_b + route_c)
page = page.replace('@@TABLE@@', table).replace('@@REFS@@', refs)
page = page.replace('@@BENCH@@', figure('bench-linear.svg', '器件表征平台：电容隔直、电感供直流；RF 放大器为可选，仪器功耗不等于 ASIC 能耗。'))
page = page.replace('@@PACKAGE@@', figure('package-concept.png', 'Blender 4.5.11 LTS 原创封装概念；无 GDS 输入，尺寸采用示意单位。色块与连线表达功能和空间关系。'))
page = page.replace('@@ENERGY@@', figure('energy-budget.svg', '解析预算：相同假设下拆开电容、LED 支路、Dummy 与外围；不是实物性能排名。'))
page = page.replace('@@PARALLEL@@', figure('parallel-throughput-power.svg', '条件并行预算：共享功耗只计一次，通道数增加不改变单 LED 速度。'))
page = page.replace('@@PROCESSREFS@@', '；'.join(ref(k, label) for k,label in [('HS19-CSM','CSMANTECH 2022'),('HS19-DAC','JLT 2017'),('HS19-OFC','OFC 2024 摘要')]))
assert '@@' not in page
(OUT / 'index.html').write_text(page, encoding='utf-8')
print(f'Wrote {OUT / "index.html"}: {len(page):,} characters')
