"""Render the dated driver literature study and a searchable primary-source index."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import html
import json
import re
import subprocess

import markdown

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "docs/research/driver-literature-20261012"
STAGING = ROOT / "build/literature-driver-20261012"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def plain(value):
    if value is None:
        return "未报告/未确认"
    if isinstance(value, dict):
        return "; ".join(f"{k}: {plain(v)}" for k, v in value.items())
    if isinstance(value, list):
        return "; ".join(plain(v) for v in value)
    return str(value)


def main():
    BASE.mkdir(parents=True, exist_ok=True)
    entries = []
    input_hashes = {}
    names = ["context.json", "cmos.json", "tft.json", "highspeed.json"]
    if all((STAGING / name).exists() for name in names):
        for name in names:
            path = STAGING / name
            data = json.loads(path.read_text())
            if isinstance(data, dict):
                data = data["records"]
            entries += data
            input_hashes[name] = sha(path)
    else:
        frozen = json.loads((BASE / "sources.json").read_text())
        entries = frozen["records"]
        input_hashes = frozen["staging_hashes"]
    ids = [x["id"] for x in entries]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate source IDs")
    guides = {
        "C01":"看CMOS与LED如何连接；高亮度和单pixel大电流不是全阵列同时工作的证明。",
        "C02":"学习leakage/IR-drop补偿；仅摘要可用，具体电路与测试条件需继续看全文。",
        "C03":"学习多channel共享DAC如何省元件；元件数减少不等于同幅度的功耗或总面积改善。",
        "C04":"学习SRAM、PAM/PWM与高压enable分工；120 µA与16级来自post-layout仿真。",
        "C05":"学习共享pixel架构；1.15T是平均成本，先分清backplane芯片与完整光学显示。",
        "C06":"学习电流均匀性与异质集成；电路仿真和光学实测分别读，均匀度条件有单位歧义。",
        "T01":"看LTPS与LED匹配的实验方法；公式、单位和bit推导有疑点，勿作性能基准。",
        "T02":"适合入门LTPO：p-LTPS加n-oxide如何分工；实测器件不等于实测pixel性能。",
        "T03":"了解真正的GaN driver原型；normally-on、负压关断与布线漏电改变系统要求。",
        "T04":"organic TFT不是OLED：电子驱动层为有机材料，发光器件仍是GaN LED。",
        "T05":"学习短脉冲下降与低灰阶积分误差；所报动态结果是拟合器件模型后的HSPICE。",
        "T06":"双gate oxide单片集成线索；本轮只有摘要，待核查stress与像素条件。",
        "T07":"Micro-LET还包含BJT；不能把电流增益都归给LTPS或a-Si TFT。",
        "T08":"学习MoS₂与GaN三维集成；实测频率、delay推算、失败pixel和制造温度分开。",
        "H01":"短光脉冲不是通信链路速率；不要由300 ps换算出已测Gbps。",
        "H02":"CMOS驱动MicroLED单通道通信的入门证据；完整BER/电流/距离条件还需补查。",
        "H03":"优先看四路并发与ground bounce；1.5 Gbit/s是四路总值。",
        "H04":"训练数据归属：同篇有ASIC设计，但最高速率实验使用AWG。",
        "H05":"优先学current steering、dummy与cascode；16颗LED属于同一DLC而非16个lane。",
        "H06":"优先学系统约束：CMOS-DAC四路和AWG九路是两套实验，不可混归速率。",
        "H07":"CMOS实现Gbit/s/lane的primary线索；仅摘要，304路同时BER/能量边界尚待查。",
    }
    for x in entries:
        x["checked_on"] = "2026-10-12"
        if x["id"] in guides:
            x["cn_guide"] = guides[x["id"]]
        x["reuse"] = "Link/cite bibliographic identity and factual values with attribution; no source figures reproduced"
        x["is_paper"] = bool(x.get("doi")) and x["source_type"] != "review"
        x["group"] = {"C": "CMOS背板", "T": "TFT与新材料", "H": "高速通信", "G": "PDK与工艺", "B": "技术背景", "R": "综述", "P": "公开材料辨识"}[x["id"][0]]
        if x["id"] == "H08":
            x["group"] = "PDK与工艺"
    counts = {"all_sources": len(entries), "research_papers": sum(x["is_paper"] for x in entries),
              "review_papers": sum(x["source_type"] == "review" for x in entries),
              "key_fulltext_research_papers": sum(x["is_paper"] and x["access_level"] == "fulltext_reviewed" for x in entries),
              "abstract_research_papers": sum(x["is_paper"] and x["access_level"] == "abstract_reviewed" for x in entries)}
    library = {"schema_version": 1, "study_date": "2026-10-12", "engineering_baseline": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "scope": "Targeted breadth across MicroLED driver materials, architectures and evidence. Not an exhaustive systematic review, production ranking or commercial product replication.",
        "access_definition": "fulltext_reviewed means relevant primary full-text sections were inspected; abstract_reviewed never establishes undisclosed implementation or detailed test conditions. Does not imply the user has read the source.",
        "counts": counts, "records": entries, "staging_hashes": input_hashes,
        "no_new_EDA": True, "search_date": "2026-10-12", "retrieval_method": "Public author/publisher/institution records and official technical documentation; parallel primary-section checks. No paywall bypass or restricted document ingestion."}
    (BASE / "sources.json").write_text(json.dumps(library, ensure_ascii=False, indent=2) + "\n")

    def cite(source_id, label=None):
        source = next(x for x in entries if x["id"] == source_id)
        return f'[{label or source_id}]({source["url"]})'

    report = f'''# MicroLED驱动器研究\n材料、工艺、架构与论文索引

2026-10-12 · 实验性研发方法验证与教学 · 公开资料研究

> **核心结论：发光器件与驱动晶体管可以采用不同材料。** MicroLED像素和高速通信驱动都存在硅基CMOS实现；高速并不必然要求改用GaN或SiC。材料、器件结构、耐压类别、几何尺寸、电路及互连需要分别判断。

## 这份研究回答什么

一是MicroLED到底由什么晶体管驱动；二是显示像素与高速通信为何选择不同器件和架构；三是公开产品是否能证明采用特殊MOS材料；四是哪些论文可以读、数据能支持什么决定。

本轮索引包含**{counts['research_papers']}篇研究论文、{counts['review_papers']}篇综述及官方技术资料，共{counts['all_sources']}条来源**。研究论文中{counts['key_fulltext_research_papers']}篇核查了关键全文段，{counts['abstract_research_papers']}篇仅核查摘要；未把后者升级为可复现电路。检索是按问题选择的代表性研究，不是穷尽检索或市场占比调查。

| 先掌握的判断 | 对研究的作用 |
| --- | --- |
| Si CMOS与GaN系LED可异质集成 | 不需要因LED材料而替换driver材料 |
| LTPS/oxide TFT适合研究大面积背板；Si CMOS适合研究集成IC | 选择制造平台，而非只选一只MOS |
| SiGe BiCMOS的高速器件可能是HBT | HBT是双极晶体管，不能统称SiGe MOS |
| GaN/MoS₂/organic TFT驱动已有研究原型 | 原型、仿真与量产工艺分开评价 |
| 最高总码率可能来自另一条仪器驱动路径 | 先读实验配置，再归属性能 |

**阅读路线：** 第2–3页解释材料与本项目MOS；第4–7页比较架构和实证；第8页核查µPLS/EVIYOS；第9–10页给研究方向和阅读顺序。完整条目在[可搜索索引](index.html)、[文字索引](papers-index.md)及[sources.json](sources.json)。

**与项目的关系：** 本轮是资料与论文研究，没有新电路/EDA/实物结果。现有GF180单像素100 µA/1 µs方法平台不继承其他论文的速度、能效或光学指标。当前工程退出条件仍按[单像素研究判断](../decision-review-20261011/report.md)执行。

<!-- PAGE -->

## 2　把材料与技术名称放到正确层次

ASIC是按特定用途设计的IC，不是一种材料。MOSFET是由gate电压控制沟道电流的器件；CMOS指互补nMOS/pMOS电路及工艺体系，**本身不是化学材料名称**。询问材料时分别问沟道、栅介质、栅电极、基底；技术还需问结构、耐压与集成方式。

| 名称 | 材料/结构的实际含义 | 本轮位置 |
| --- | --- | --- |
| Si CMOS | 通常以硅基MOS实现n/p器件；具体栅堆栈随工艺 | 单像素ASIC、集成背板和通信driver |
| LTPS TFT | 低温多晶硅薄膜沟道 | 大面积pixel与scan电路 |
| Oxide / IGZO TFT | 氧化物半导体沟道；IGZO为In-Ga-Zn-O | 背板、保持/开关/补偿研究 |
| LTPO | LTPS与oxide器件组合的工艺/电路路线 | 跨器件分工，不是单一新元素材料 |
| SiGe BiCMOS | SiGe HBT与CMOS同片集成 | 高速模拟技术参考；HBT为双极器件 |
| GaN MIS-HEMT / FET | 氮化物电子器件；可能采用绝缘gate/2DEG | 同质/单片LED-driver研究原型 |
| BCD / SOI | BCD组合Bipolar-CMOS-DMOS；SOI为硅上绝缘结构 | 不自动表示改用GaN或SiC沟道 |

GaN/InGaN等III-nitride可用于LED的发光区；硅MOS控制电流，而LED载流子复合产生光。异质集成把它们连接起来，不能由LED外延材料推断driver沟道。{cite('R01','材料背景')} / {cite('B01','Si CMOS与TFT路线')}

**“厚氧化层”也不是“不同沟道材料”。** 厚/薄gate oxide属于耐压与电性选择。单位面积氧化层电容近似 `Cox=εox/tox`，厚氧使该项变小；实际速度还取决于gm、L、器件面积、overlap、结电容与负载。不能简单说厚氧就一定有更大总C，或薄氧能直接承受LED rail。

BDD之外的BCD仍是silicon工艺族；SiGe HBT与MOS的导电机制不同。{cite('B02','BCD官方定义')} / {cite('B03','SiGe/HBT官方定义')}。厂商拥有某项工艺，不等于某个产品采用它。

<!-- PAGE -->

## 3　我们实际用了什么MOS：GF180的一项选择

当前[六MOS电路](../../../analog/driver/pixel_driver.spice)全部使用`nmos_6p0` / `pmos_6p0`，属于公开GF180MCU silicon bulk CMOS的6 V器件族。mirror管20/4 µm，pass/clamp和INV_N为2/1 µm，INV_P为4/1 µm；IREF=100 µA仍在外部testbench。

| 对象 | 可确认的数据 | 解读 |
| --- | --- | --- |
| 工艺名称 | GF180MCU / 0.18 µm | 工艺家族名称，不是每只MOS的L |
| 3.3 V NMOS / PMOS | 官方Poly2 Lmin均0.28 µm | 低压/薄gate类别 |
| 6 V NMOS / PMOS | 官方Lmin分别0.70 / 0.55 µm | 中压/厚gate类别 |
| 本项目reference/output | W20 µm、L4 µm | 为电流研究选长L，不追求最小尺寸 |
| 本项目开关 | L1 µm | 同工艺、另一组尺寸/负载任务 |

上表前三项依据官方[Poly2规则](https://gf180mcu-pdk.readthedocs.io/en/latest/physical_verification/design_manual/drm_07_08.html)，电压/可靠性边界见[operating conditions](https://gf180mcu-pdk.readthedocs.io/en/latest/physical_verification/design_manual/drm_14_1.html)。`6p0`不能理解为所有端间电压、所有温度和占空比下都可随意加6 V；要检查VGS、VGD、VDS、HCI/TDDB及电源排序。

**为什么先选它：** 公开模型和版图规则使方法可复查；较高耐压类别便于研究LED余量；长L与较大镜像面积帮助研究output resistance/matching。代价是面积与gate charge等变化，需由实际模型验证。当前选择是教学/实验基线，不是已证明最优的通信或车用工艺。

**不同功能可以用不同器件。** 一个ASIC可以同时有低压逻辑、I/O或中高压output器件、模拟reference、存储与诊断。数字clock高，并不意味着所有模拟晶体管都应缩到最小L。

现有6 V compact model的RF适用范围不能由模型名或快边沿确认；需要相关gate resistance/NQS设置、模型验证频率域、layout/ESD/package数据。现阶段没有这种完整RF证据。模型锁见[pdk-lock](../../../analog/models/pdk-lock.json)，不等于完整制造接受。

<!-- PAGE -->

## 4　显示driver：控制电流、灰度与一致性

显示器件的核心任务是稳定地产生目标亮度，同时解决通道差异、低灰阶、供电余量、温度、面积和更新时序。发光频谱/效率随电流变化时，仅用PAM调幅可能改变器件工作点；PWM固定开启电流并调时间，也会遭遇最短有效脉冲和存储开销。混合PWM/PAM是另一种可研究分配。

<div class="flow"><div class="node"><b>幅度链</b>reference → current DAC / mirror<br>accuracy、matching、headroom</div><div class="node"><b>时间链</b>memory / counter / PWM<br>最短码、更新、blank</div><div class="node"><b>负载链</b>LED / interconnect / rail<br>I–V、charge、温度、光学</div></div>

| 架构 | 解决的机制 | 必须付出的代价/验证 |
| --- | --- | --- |
| Current mirror + switch | 电流幅度与PWM时间分开 | reference、输出余量、gate charge与关断 |
| PAM / current DAC | 多个开启电流工作点 | 匹配、线性与真实L–I/色点 |
| PWM / local memory | 固定幅度、离散点亮时间 | 存储面积、时钟/最短码与供电同时切换 |
| VTH/IR-drop compensation | 补偿TFT阈值或供电变化 | 采样、保持、电容、补偿时序与残差 |
| Shared current / hybrid | 降面积或扩有效灰阶 | 共享节点耦合、扫描、输出线性 |

{cite('B01','imec的LTPS 6T2C')}把mirror、switch与selection分工，是读电路的入门例子；其6T2C与本项目六MOS不是相同电路。CMOS论文条目C组说明不同pixel-memory/PWM/PAM实现；其bit数要区分命令宽度、可执行码、有效电气精度与光学分辨率。

**研究方法：** 固定同一LED与温度，分别测Ifull、lowest-code Q、亮度L–I、通道分布和source/rail能量。平均current只能先作电气代理；不能把“8-bit input”写成“8-bit光学有效灰阶”。pixel pitch、active emitting area、IC cell area与package尺寸也应分开。

**不同证据例子：** {cite('C01')}有实际CMOS/LED光学原型；{cite('C04')}的120 µA和16级是post-layout仿真；{cite('C06')}有光学原型，但0.004 LSB和687 pA来自Cadence仿真。三种数值不能合并成同一实测结论。

本项目已具有mirror/PWM及signal PEX对照，可优先研究reference、独立关断和真实PG；TFT补偿可先作为独立行为实验。没有TFT模型与制造平台时，不应把GF180模拟称LTPS/IGZO验证。

<!-- PAGE -->

## 5　TFT与新材料：原型证明了什么

TFT提供大面积基底上的薄膜场效应器件；它与小片硅ASIC是不同制造平台。LTPS、oxide和混合LTPO的取舍涉及驱动电流、保持漏电、阈值变化、均匀性与制程。材料家族名称不足以给出通用迁移率/带宽排名，必须保留器件结构和测试条件。

本轮T组覆盖LTPS、IGZO/oxide、LTPO、organic TFT、MoS₂及GaN集成，详见[按材料筛选的索引](index.html)。以下保留原来源的证据类型，不将模型计算升级为显示实测：

| 研究对象 | 本轮确认的证据 | 读者应避免的误读 |
| --- | --- | --- |
| {cite('T02')} LTPO 8T2C / 2025 | 4 p-LTPS + 4 n-oxide；器件/反相器曲线实测，pixel为SmartSpice | <30 ns / 8-bit不能写成实物显示性能 |
| {cite('T05')} LTPO / 2026 | 器件模型拟合后HSPICE；90→10%约0.3 µs | 该下降时间不是pixel脉冲实测 |
| {cite('T08')} MoS₂ / GaN / 2021 | 32×32 1T1D原型；250 kHz；240/170 ns电气延迟分量 | 不是独立10–90%边沿；推断2.4 MHz非实测带宽 |
| {cite('T03')} GaN MIS-HEMT / 2025 | 2×2 2-HEMT-1-LED实物；normally-on、负压关断 | 0.5 W/cm²按pixel pitch归一，非LED面积/亮度 |

**真正不同的材料确实有研究。** GaN MIS-HEMT可与InGaN LED单片集成；MoS₂和organic TFT可作薄膜电子器件。但prototype不意味着普通driver必须用这些材料，也不能说明µPLS/EVIYOS采用了它们。{cite('T04')}的organic TFT仍驱动无机GaN LED，不是OLED。

**值得学习的限制：** normally-on GaN需要关断电压策略；GaN例中的布线漏电阻碍storage扩展。MoS₂原型存在开路/短路pixel，且低温BEOL集成不等于MoS₂生长也是低温。部分LTPS论文内部单位/bit推导有疑点，索引保留原报告与核查备注，不采用其数字作高可信基准。

如果下一阶段问题是稳定电流与关断，现有Si平台仍可推进；若问题变为大面积背板或同质集成，才需要新的材料模型、工艺、样片与测量路线。新材料研究应回答明确瓶颈，不能替代当前尚未闭合的reference/PG问题。

<!-- PAGE -->

## 6　通信driver：CMOS已存在实证，但要看驱动路径

高速通信要在每个bit/symbol内控制电流并形成可检测光信号。常见研究包括高速switch、current-steering DAC、differential/dummy branch和cascode；这些结构可以用硅CMOS实现。SiGe BiCMOS是另一类技术参考，其高速HBT为bipolar，并非“所有MOS换成SiGe”。

| 论文 / 原驱动路径 | 数据与条件（保留分母） | 证据结论 |
| --- | --- | --- |
| {cite('H02')} / CMOS单pixel | 450 nm、24 µm；512 Mbit/s OOK-NRZ；摘要已核查 | CMOS可用于MicroLED数百Mbit/s，详细BER条件待全文 |
| {cite('H03')} / 实际CMOS四路 | 4×375 Mbit/s = 1.5 Gbit/s；OOK-NRZ、6.5 V LED bias | 并行ASIC实测；ground bounce带来串扰 |
| {cite('H05')} / current-steering DLC | 365 Mbit/s、16-QAM OFDM、200 MHz clock、5 cm | 有实际CMOS/LED链路，不等于500 MHz光学带宽 |
| {cite('H06')} / 0.18 µm CMOS DAC | 四路总1.23–1.30 Gbit/s raw，1 m，约45 mA/LED | 硅CMOS driver用于已测通信链路 |
| {cite('H07')} / 16 nm transceiver | 作者摘要3.3 Gbit/s/lane；304-channel架构 | 初期单lane/config结果；未核查全部同时BER |

这张表是**原始数值的条件化摘录**，不是速度排名。H03采用作者定义BER<10⁻¹⁰；H05约10⁻³门槛；H06为3.8×10⁻³门槛；H07仅摘要，BER条件待查。LED、偏置、接收器、距离、调制和均衡/FEC不同，不能由节点预测某负载速率。

**重要反例：** H06的7.48 Gbit/s九路最高值用AWG替换CMOS DAC、0.5 m链路；它不能归给上述四路ASIC，更不是单lane。H04的四路1.070 Gbit/s preliminary实验也用AWG，虽然同篇介绍了fabricated CMOS driver。{cite('H04')} / {cite('H06')}

因此“有ASIC架构图＋有高速图”不足以确认二者同run。索引单列setup、驱动刺激、instrument、lane数量、raw/net与BER threshold。没有这些条件，数据只可作为待核查线索。

<!-- PAGE -->

## 7　高速差别主要在哪里：器件、负载与系统一起看

**同为Si CMOS也可完全不同。** 短L、不同耐压器件、gm/电容、gate driver与布线、ESD/pad/package会改变速度；器件结构还可能是planar、FinFET等。具体沟道应变/栅堆栈按工艺确认，不能笼统推断所有先进CMOS的每一层材料。

| 指标层次 | 真正测什么 | 不能直接换算成什么 |
| --- | --- | --- |
| MOS fT / fmax | 特定bias下晶体管高频增益 | LED光学带宽或通信码率 |
| Driver electrical edge | 实际负载下电流/电压变化 | 同样快的光输出 |
| LED E–O response | 器件偏置、光检测链下的频响 | 某驱动ASIC的已测吞吐 |
| Optical link BER / rate | Tx→optics→Rx＋算法的系统结果 | 仅driver或仅材料的性能 |
| Total parallel rate | 所测lane数据合计 | 每lane速率或每lane都通过 |

用于学习的近似：单极点负载 `tr(10→90%)≈2.2 Rdrive Cload`；若**假设**100 Ω和1 pF，则约220 ps。此计算不是本项目/论文实测；实际电路有多个极点、charge、非线性和光学动态。减小R或C可能需要更多电流、面积或不同互连。

本项目1 µs最低slot与1 Gbit/s NRZ的1 ns bit、10 Gbit/s的100 ps bit相差10³/10⁴量级。不能把现有1 ns人为PWL输入ramp或亚ns阈值交越理解为通信已经通过；它也不证明GF180工艺本身不可能做高速电路。

**高速进入条件：** 明确目标码率/调制与BER合同；同器件I–V/C–V/pulse或S21；reference和bias；真实driver输出网络＋pad/ESD/package；以真实前级产生输入slew；最后光学链路测量。eye opening、jitter、BER和energy/bit的功耗边界独立记录。

H03已观察并发channel的供电耦合，H05的dummy branch说明LED熄灭时电流仍可能流到另一支路。两者直接提示我们继续检查真实PG与能量账户，而不是先更换材料。

<!-- PAGE -->

## 8　µPLS与EVIYOS：公开资料不等于晶体管剖面

这是回应本轮材料疑问的**公开身份核查**，不是商业性能对标或内部架构复现。

| 对象 | 官方已经公开 | 当前仍不能确认 |
| --- | --- | --- |
| {cite('P01','Nichia µPLS')} / {cite('P02','Infineon说明')} | Infineon ASIC；pixel PWM、监测、温度与三维集成 | exact MOS沟道/栅堆栈、node、是否BCD/SOI、power device种类 |
| {cite('P03','EVIYOS官方说明')} | MicroLED array与CMOS driver chip的异质集成 | exact MOS材料栈、耐压类别与完整pixel电路 |
| {cite('P04','EVIYOS产品族')} | LED/IC hybrid另配companion ASIC | 不可把底部pixel driver和外部companion当同一IC |

**对“材料特殊”的回答：** µPLS供应商身份可以确认，但不足以据此断言用了GaN或SiC MOS。EVIYOS官方反而明确使用CMOS driver；其特殊之处至少包括LED/IC集成与像素控制，尚不能归因于一种特殊MOS材料。确切器件类别需产品工艺披露或可核查的剖面/公开论文。

“CMOS之外还有DMOS/HBT/隔离/多种氧化层”是某些mixed-signal工艺可能提供的能力，**不是这些产品已使用该能力的证据**。Infineon拥有Si/GaN/SiC产品，或另家foundry提供SOI/BCD，不能用于反推这颗ASIC。

若看到材料字样，先定位它指哪一层：LED的GaN/InGaN、driver沟道、硅基底、磷光转换、互连/键合金属、封装基板。再问是哪一颗芯片、哪一代、对应哪个公开证据。白光、像素数或耐高温也不足以确定MOS材料。

**研究边界：** 本轮只采用官方公开的身份与结构，未下载或复用restricted设计文件、寄存器协议和内部图。索引P组保留“已确认/未确认”；生产级工艺未公开处保持未知，通用论文只用于建立独立实验假设。

<!-- PAGE -->

## 9　对本项目的方向：先选问题，再选工艺

**近期主线仍是Si CMOS单像素。** 当前要回答的是reference/output compliance、startup/fault与实际供电/邻居依赖；这些不要求先换材料。继续现有A/B/C受控实验，比直接追求更小节点更容易建立因果证据。

| 想研究的瓶颈 | 当前可搭建的平台 | 升级前必须补的依据 |
| --- | --- | --- |
| 电流精度/余量/关断 | GF180模型＋actual signal PEX＋独立源/负载扫描 | 实现reference/fault，恢复真实PG，保存内部节点 |
| TFT阈值补偿/存储 | 独立TFT行为模型/补偿时序实验 | Traceable TFT模型、器件测量、样片；不称GF180结果 |
| 多通道共享/串扰 | 单像素闭环后选具体多通道问题 | 同时切换、reference/rail/matching与总能量 |
| Gbit/s MicroLED driver | 独立高速分支，先current-steering与负载联合分析 | RF模型/PEX、同器件动态、eye/BER测量链 |
| GaN/MoS₂/organic TFT集成 | 文献机制复查和参数敏感性 | 实际器件工艺、模型/样品、关断与产率证据 |

**与显示PWM相比，高速值得先借鉴的是架构。** H05将恒定电流在LED与dummy之间转向，并使用cascode；可以先建立独立模型分析速度与功耗。不能直接把这条拓扑搬入当前six-MOS基线，再用旧回归称全部有效。

**待回答的问题：** 当前负载在目标bias下到底需要怎样的电压/电流？Qgate、CLED和package各占多少delay？能量消耗来自reference、dummy还是互连？哪种误差能由补偿解决，哪种必须改变器件/工艺？每个问题都需要固定其他变量的对照。

**对研究价值的判断：** 一份开放的source→hypothesis→model→layout→electrical/optical evidence链，比不具备完整条件的“达到某商业指标”更可复查。材料选型的价值，应通过它解决的瓶颈及代价建立；不能用论文数量、器件新颖性或最大速率代替研究进展。

下一轮先产出output/source compliance图和reference/fault合同；高速文献与TFT模型作为独立学习支线。阵列或高速的开发应有自己的进入条件，避免把邻近阶段的成功升级为当前项目能力。

<!-- PAGE -->

## 10　怎样读与索引：按问题检索，不按数字排序

| 阅读目的 | 推荐入口 | 先看哪里 |
| --- | --- | --- |
| 建立材料与集成概念 | {cite('R01')} / {cite('B01')} | 器件与背板对象、mirror/PWM分工 |
| 硅ASIC的pixel方法 | C组全文/摘要分级条目 | pixel circuit、memory、gray与实测配置 |
| TFT/LTPO补偿机制 | T组LTPS/oxide/LTPO条目 | 仿真条件、实测器件是否等于pixel原型 |
| 实际CMOS并行链路 | {cite('H03')} | 4×375 Mbit/s与ground bounce |
| 高速current-steering电路 | {cite('H05')} | current cell、dummy、cascode与光学实测 |
| 学会核查driver数据归属 | {cite('H06')} / {cite('H04')} | CMOS与AWG setup分开，再读速率 |
| CMOS Gbit/s研究线索 | {cite('H07')} | 仅摘要，需全文/BER/能量边界补查 |
| 新材料driver可行性 | T组GaN/MoS₂/organic条目 | 实物规模、关断、缺陷与制造条件 |

[可搜索索引](index.html)支持按关键词、技术组和全文核查状态筛选。每篇保留title、author、year、DOI、publisher/author URL、公开作者稿入口、工艺、架构、量/单位/条件、section/page、supports和does-not-support。公开稿链接不保证当前可匿名取到全文；只核查摘要的记录仍保持摘要等级。

**统计口径：** {counts['research_papers']}研究论文指本轮所选original study/conference records；综述、机构文章、foundry文档和厂商公开说明另计。引用年优先journal/conference年；DOI字符串中的年份可不同。没有doi的官方网页不伪造DOI或发布日期。

**数据复用：** 本报告表格只摘录少量事实数值并保留条件，没有复制论文图或原PDF。论文版权/作者稿许可保留各来源；可点击原定位自行核查，未知图版权不默认为可公开复用。不同论文结果未合成统一性能排名。

**本轮验收：** 输入metadata、关键事实归属、局部文件链接、索引筛选、报告页数和逐页渲染分别检查；结果见[validation.json](validation.json)。保存源字段与hash，后续新增论文应新增条目和判断日期。没有新EDA、silicon或optical结果。[全文索引](papers-index.md)
'''
    # Correct an accidental word before generating all formats.
    report = report.replace("BDD之外的BCD", "BCD")
    (BASE / "report.md").write_text(report)
    # Keep new local files local; existing engineering links resolve to baseline snapshots.
    head = library["engineering_baseline"]
    def links(body):
        def replace(m):
            href = html.unescape(m.group(1))
            if "://" in href or href.startswith("#"):
                return m.group(0)
            target = (BASE / href).resolve().relative_to(ROOT).as_posix()
            tracked = subprocess.run(["git", "cat-file", "-e", head + ":" + target], cwd=ROOT, capture_output=True).returncode == 0
            return f'href="https://github.com/Kevin-Kaiyo/open-microled-driver-asic/blob/{head}/{target}"' if tracked else m.group(0)
        return re.sub(r'href="([^"]+)"', replace, body)
    sections = []
    for i, text in enumerate(report.split("<!-- PAGE -->"), 1):
        sections.append(f'<section class="page" data-page="{i}">{links(markdown.markdown(text.strip(),extensions=["tables","fenced_code"]))}</section>')
    css = '''
    @page {size:A4;margin:20mm} *{box-sizing:border-box}
    body{margin:0;color:#24353c;font:10.7pt/1.62 'Avenir Next','PingFang SC',sans-serif}
    h1,h2,h3{color:#164f5b;line-height:1.35} h1{font-size:25pt;margin:0 0 5mm}
    h2{font-size:18.5pt;margin:0 0 5mm;padding-bottom:3mm;border-bottom:1px solid #bdced0}
    h1+h2{font-size:14pt;border:0;padding:0} h3{font-size:12pt;margin:4mm 0 2mm}
    p{margin:0 0 3mm} strong{color:#183e49} a{color:#176977;text-decoration:none;overflow-wrap:anywhere}
    table{border-collapse:collapse;width:100%;margin:3mm 0 4mm;font-size:9.5pt;line-height:1.5}
    th{text-align:left;background:#eaf1f1;color:#164f5b;font-weight:600}
    th,td{padding:2.1mm 2.3mm;border-bottom:1px solid #d9e1e2;vertical-align:top;overflow-wrap:anywhere}
    tr{break-inside:avoid} code{font-family:inherit;font-size:.94em}
    blockquote{margin:4mm 0;padding:3mm 4mm;border-left:3px solid #397e83;background:#edf4f3}
    blockquote p:last-child{margin:0} .page{break-after:page}.page:last-child{break-after:auto}
    .flow{display:grid;grid-template-columns:1fr 1fr 1fr;gap:3mm;margin:4mm 0}
    .node{border:1px solid #bfd0d2;border-radius:2mm;padding:3mm;background:#f6f9f8}
    .node b{display:block;color:#164f5b;margin-bottom:1mm}
    @media print{body,.page{width:170mm}}
    @media screen{body{background:#edf2f2}.page{background:white;width:210mm;min-height:297mm;margin:8mm auto;padding:20mm;box-shadow:0 1px 8px #bac9ca}}
    '''
    (BASE / "report.html").write_text('<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>MicroLED驱动器研究 · 2026-10-12</title><style>'+css+'</style></head><body>'+'\n'.join(sections)+'</body></html>\n')

    lines = ["# MicroLED驱动研究论文与来源索引", "", "2026-10-12。研究论文、综述、机构/工艺资料与材料身份案例分开；已核查全文指关键相关段，不代表读者已经读过。", "",
        "[可搜索界面](index.html) / [研究报告](report.md) / [完整JSON](sources.json)", "", "| ID | 年份 | 组 | 文献 | 访问核查 |", "| --- | --- | --- | --- | --- |"]
    labels = {"fulltext_reviewed":"关键全文已核查", "abstract_reviewed":"仅摘要已核查", "official_documentation":"官方公开资料"}
    for x in entries:
        label = labels.get(x["access_level"], x["access_level"])
        lines.append(f'| [{x["id"]}](#{x["id"].lower()}) | {x.get("year") or "未确定"} | {x["group"]} | [{x["title"]}]({x["url"]}) | {label} |')
    cards = []
    for x in entries:
        label = labels.get(x["access_level"], x["access_level"])
        data_md = "\n".join(f'| {plain(v.get("label"))} | {plain(v.get("value"))} {plain(v.get("unit"))} | {plain(v.get("conditions"))} |' for v in x.get("data", []))
        parts = [f'## {x["id"]} · {x["title"]}', "", f'**中文导读：** {x.get("cn_guide", "技术或公开身份背景；请按本条支持范围阅读。")}', "", f'**作者/年：** {plain(x.get("authors"))} / {x.get("year") or "未确定"}。**来源类型：** {x["source_type"]}。**访问核查：** {label}。', "", f'**主题：** {plain(x["topic_tags"])}', "", f'**DOI：** '+(f'[{x["doi"]}](https://doi.org/{x["doi"]})' if x.get("doi") else "未提供/不适用"), "", f'[来源入口]({x["url"]})'+(f' / [作者稿或全文入口]({x["open_fulltext_url"]})' if x.get("open_fulltext_url") else " / 公开全文入口未确认"), "", f'**工艺/材料：** {plain(x["process"])}', "", f'**架构：** {plain(x["architecture"])}', "", f'**证据类型：** {plain(x["evidence_class"])}。**原定位：** {plain(x["locator"])}', ""]
        if data_md:
            parts += ["**原数据字段摘录（保留值、单位与条件）：**", "", "| 量 | 值/单位 | 条件/分母 |", "| --- | --- | --- |", data_md, ""]
        else:
            parts += ["**数据：** 本条不提取数值指标，保留为机制/身份资料。", ""]
        parts += [f'**支持：** {plain(x["supports"])}', "", f'**不支持：** {plain(x["does_not_support"])}', "", f'**核查备注：** {plain(x["notes"])}', "", "复用：链接/引用身份与少量事实数据；未复制论文图。", ""]
        lines += parts
        card = markdown.markdown("\n".join(parts), extensions=["tables"])
        cards.append(f'<article id="{x["id"]}" data-group="{html.escape(x["group"])}" data-access="{html.escape(x["access_level"])}" data-paper="{str(x["is_paper"]).lower()}">{card}</article>')
    (BASE / "papers-index.md").write_text("\n".join(lines)+"\n")
    groups = sorted({x["group"] for x in entries})
    options = ''.join(f'<option>{html.escape(x)}</option>' for x in groups)
    index_css = '''body{margin:0;background:#f1f5f3;color:#24353c;font:16px/1.7 'Avenir Next','PingFang SC',sans-serif}
    main{max-width:1080px;margin:auto;padding:40px 24px}h1,h2{color:#164f5b;line-height:1.4}h1{font-size:32px}h2{font-size:21px}
    a{color:#176977;overflow-wrap:anywhere}article{padding:25px 30px;background:white;border:1px solid #d2e0de;border-radius:8px;margin:22px 0}
    article[hidden]{display:none}p{margin:10px 0}table{border-collapse:collapse;width:100%;font-size:15px}td,th{padding:9px 10px;border-bottom:1px solid #dce5e3;text-align:left;vertical-align:top;overflow-wrap:anywhere}
    th{background:#edf4f1}strong{color:#183e49}.filters{position:sticky;top:0;display:flex;gap:12px;flex-wrap:wrap;align-items:center;padding:16px;background:#e5eeea;border-radius:6px;z-index:1}
    input,select{font:inherit;padding:8px;border:1px solid #9eb9b3;border-radius:4px;background:white}#query{flex:1;min-width:220px}label{display:flex;align-items:center;gap:6px}#count{font-weight:600;color:#164f5b}
    @media(max-width:640px){main{padding:20px 12px}article{padding:18px 14px}table{font-size:14px}td,th{padding:6px}h1{font-size:25px}.filters{position:static}}
    '''
    js = '''const query=document.getElementById('query'),family=document.getElementById('family'),kind=document.getElementById('kind'),full=document.getElementById('full'),cards=[...document.querySelectorAll('article')];
    function filter(){let n=0;const q=query.value.toLocaleLowerCase().trim();for(const card of cards){let match=(!q||card.textContent.toLocaleLowerCase().includes(q))&&(!family.value||card.dataset.group===family.value)&&(!kind.value||card.dataset.paper===kind.value)&&(!full.checked||card.dataset.access==='fulltext_reviewed');card.hidden=!match;if(match)n++;}document.getElementById('count').textContent=n+' / '+cards.length+' 条';}
    for(const input of [query,family,kind,full])input.addEventListener('input',filter);filter();
    '''
    index = '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>MicroLED驱动论文索引</title><style>'+index_css+'</style></head><body><main>'
    index += f'<h1>MicroLED驱动 · 可检索论文与证据</h1><p>2026-10-12 · {counts["research_papers"]}篇研究论文 / {counts["review_papers"]}篇综述 / {counts["all_sources"]}条来源。按问题选取，非穷尽检索或性能排名。</p><p><a href="report.html">先读10页研究报告</a> · <a href="papers-index.md">文字索引</a> · <a href="sources.json">JSON数据</a></p>'
    index += '<p>“关键全文已核查”指核对相关段落；仅摘要记录不能支持未披露电路或测试条件。论文数、像素数、单lane与总速率不是同一分母。未复制源PDF/图；查看原入口可继续核查。</p>'
    index += '<div class="filters"><input id="query" aria-label="搜索论文、材料、DOI或条件" placeholder="搜索：current steering、LTPO、GaN、AWG、DOI…"><select id="family" aria-label="技术组"><option value="">全部技术组</option>'+options+'</select><select id="kind" aria-label="来源类型"><option value="">全部来源</option><option value="true">研究论文</option><option value="false">综述/背景/官方资料</option></select><label><input id="full" type="checkbox">仅关键全文已核查</label><span id="count" aria-live="polite"></span></div>'
    index += '\n'.join(cards)+'</main><script>'+js+'</script></body></html>\n'
    (BASE / "index.html").write_text(index)
    (BASE / "provenance.json").write_text(json.dumps({"study_date":"2026-10-12","baseline":head,"counts":counts,
        "input_sha256":input_hashes,"local_engineering_sha256":{p:sha(ROOT/p) for p in ["analog/driver/pixel_driver.spice","analog/models/pdk-lock.json","rtl/pixel_pwm.v"]},
        "render_script_sha256":sha(Path(__file__)),"new_EDA_runs":0,"source_figures_reproduced":0,"public_push_in_this_turn":False},ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({"pages":len(sections),**counts,"new_EDA_runs":0},ensure_ascii=False))


if __name__ == "__main__":
    main()
