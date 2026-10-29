#!/usr/bin/env python3
"""Render the evidence-bounded device study; never run/change driver simulations."""
from pathlib import Path
import json
import re

import markdown
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "docs/research/microled-device-codesign-20261029"
EV = ROOT / "evidence/microled-device-codesign-20261029"


def read(path):
    return json.loads(path.read_text())


def table(header, rows):
    def safe(value):
        return str(value).replace("|", "&#124;").replace("\n", "<br>")
    return "\n".join(["| " + " | ".join(header) + " |",
                       "|" + "|".join(["---"] * len(header)) + "|"] +
                      ["| " + " | ".join(safe(v) for v in row) + " |" for row in rows])


def font():
    for path in ["/System/Library/Fonts/PingFang.ttc",
                 "/System/Library/Fonts/STHeiti Light.ttc"]:
        if Path(path).exists():
            font_manager.fontManager.addfont(path)
            plt.rcParams["font.family"] = font_manager.FontProperties(fname=path).get_name()
            break
    plt.rcParams.update({"font.size": 12, "axes.unicode_minus": False,
                         "svg.fonttype": "path", "svg.hashsalt": "microled-device-codesign-20261029",
                         "figure.facecolor": "white"})


def save(fig, stem):
    fig.tight_layout(pad=1.7)
    for ext in ("svg", "png"):
        fig.savefig(DOC / "figures" / (stem + "." + ext), dpi=155,
                    metadata={"Date": "2026-10-29"} if ext == "svg" else {})
    plt.close(fig)


def plots(calc, sources):
    font()
    a = sources["L01-RAJABI2018"]["bandwidth"]["reported_values_MHz"]
    b = sources["L06-ZHU2024-ELECTRODE"]["bandwidth"]
    assert a == [214, 536] and [b["before_MHz"], b["after_MHz"]] == [203, 249.8]
    fig, axes = plt.subplots(1, 2, figsize=(11.6, 4.5))
    for ax, values, labels, title, note in [
        (axes[0], a, ["传统对照", "超薄阱/势垒"],
         "Rajabi 2018 · J=2.5 kA/cm²", "尺寸/截止定义未从全文核实"),
        (axes[1], [b["before_MHz"], b["after_MHz"]], ["浅刻蚀", "深刻蚀"],
         "Zhu 2024 · J=4 kA/cm²", "电极电容减少量来自等效模型拟合")]:
        ax.bar(labels, values, color=["#9baeb8", "#247c82"], width=.55)
        ax.set(title=title, ylabel="作者报告的截止频率 / MHz", ylim=(0, max(values)*1.28))
        for i, val in enumerate(values):
            ax.text(i, val + max(values)*.035, f"{val:g}", ha="center")
        ax.text(.5, -.22, note, transform=ax.transAxes, ha="center", fontsize=10)
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", alpha=.14)
    fig.suptitle("只在每项研究内部作前后比较；两面板不是跨材料性能排名", fontsize=14)
    save(fig, "05-within-study-bandwidth")

    rows = calc["rc"]["rows"]
    fig, axes = plt.subplots(1, 2, figsize=(11.6, 4.7))
    x = [r["square_side_um"] for r in rows]
    axes[0].plot(x, [r["total_C_fF"] for r in rows], "o-", color="#247c82", label="总电容")
    axes[0].axhline(100, ls="--", color="#9d7149", label="假设固定项 100 fF")
    axes[0].set(xlabel="正方形边长 / µm", ylabel="教学假设电容 / fF", title="缩小面积不会消除固定寄生")
    for key, label, color in [("same_I_100uA", "同 I=100 µA", "#247c82"),
                              ("same_J_25A_cm2", "同 J=25 A/cm²", "#9d7149")]:
        axes[1].plot(x, [r[key]["ideal_current_input_pole_GHz"] for r in rows],
                     "o-", color=color, label=label)
    axes[1].set(xlabel="正方形边长 / µm", ylabel="假设电流输入 RC 极点 / GHz", title="比较条件改变，尺寸趋势也会改变")
    for ax in axes:
        ax.set_xticks(x)
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(alpha=.14)
        ax.legend(frameon=False)
    fig.suptitle("纯解析教学示例：不是任何实际器件的电光带宽", fontsize=14)
    save(fig, "06-size-rc-illustration")


SUMMARIES = {
 "L01-RAJABI2018": ["超薄量子阱/势垒", "c-plane InGaN/GaN；阱 1 nm / 势垒 3 nm；横向尺寸未核实",
   "J=2.5 kA/cm²；214→536 MHz；摘要称截止频率，dB 约定未核实",
   "未核实 EQE、WPE 或完整能耗；同时改变阱和势垒", "摘要"],
 "L02-XU2023-SEMIPOLAR": ["半极性晶向", "直径 60 µm；5 周期 MQW；蓝/绿约 455/520 nm",
   "绿 >500 MHz@43.8 A/cm²；>1 GHz@120.6 A/cm²；最大值受 1 GHz APD 限制",
   "峰值 EQE 蓝/绿 3.49%/1.99%，不是带宽工作点值；OFDM 净开销未核实", "公开原始全文"],
 "L03-LI2023-QD": ["有源 InGaN 量子点", "多种直径；摘要中的 20 µm 用于 RC 分析，不能绑定全部最高值",
   "蓝/绿约 3.6/1.4 GHz，J<1 kA/cm²；−3 dB 的归一化/去嵌未核实",
   "无已核实净速率/pJ/bit；125°C 可工作不是最高带宽的温度证明", "摘要"],
 "L04-LI2024-NANOACTIVE": ["纳米工程有源区", "三层纳米结构，交替生长中断；横向尺寸与 J 未核实",
   "作者称 E–E −3 dB >2.6 GHz；NRZ 自由空间 3.07、光纤 2.60 Gb/s",
   ">0.5 mW 的偏置与最高带宽是否相同未核实；不等于净 3.2 Gb/s", "摘要"],
 "L05-LI2025-THINWELL": ["阱宽的效率反例", "In=19%；阱 2.1–3.6 nm，势垒 18 nm；光谱随之约 465–570 nm；横向尺寸未核实",
   "Fig.5：薄阱低 J 动态还受逃逸影响；不提供可横排的 GHz 数字",
   "本样品组约 2.7 nm 效率较优，过薄的低 J 效率下降；高 J 下部分薄阱趋近；不是通用最佳阱宽", "预印本+接受稿全文"],
 "L06-ZHU2024-ELECTRODE": ["深刻蚀/电极寄生", "浅/深刻蚀 GaN；横向尺寸未核实",
   "J=4 kA/cm²；203→249.8 MHz；截止定义未核实",
   "电极 C 减少 24.9 pF 是模型拟合；无已核实 EQE/能效", "摘要"],
 "L07-WANG2019-PHC": ["光子晶体/刻蚀", "PC60/PC30 是半径 60/30 µm；InGaN/GaN 倒装",
   "PC60：212 MHz@1 kA/cm²；PC30：285 MHz@2 kA/cm²；源称 optical −3 dB",
   "同尺寸 PhC 出光降低；Purcell 1.81 与提取率 68% 属 FDTD 模拟", "全文+原 Fig.6–7"],
 "L08-FERREIRA2016": ["尺寸+接触/版图工程", "A/B 发光面积 435/1369 µm²；c-plane，450 nm，倒装",
   "A/B 最高 E–O 833/397 MHz；Fig.3 DC 扫描 A10–70/B10–110 mA；频响 PD1.4 GHz",
   "高阶通信使用 B 及相应均衡/处理；不可把 A 的 833 MHz 与最高 OFDM 速率绑定", "作者托管正式全文"],
 "L09-FAN2022-RED-SIZE": ["红光尺寸/侧壁", "AlGaInP 垂直结构、Si 承载；边长 160/80/40/20/10 µm",
   "没有调制带宽实验；研究尺寸的电学与光效率影响",
   "小尺寸串联电阻/侧壁损失上升，也改善部分高注入 droop；不支持跨材料速度排名", "摘要"],
}


def references(sources, extra):
    blocks = ["以下原始研究按问题检索，未按性能排名。精确数值的完整条件以台账为准。"]
    for item in list(sources.values()) + extra:
        sid = item["id"]
        authors = item.get("authors", "")
        if isinstance(authors, list):
            authors = authors[0] + " et al."
        title = item["title"]
        locator = item.get("locator", "")
        depth = item.get("depth", item.get("read_depth", ""))
        unknown_items = item.get("unknowns", item.get("limitations", []))
        if isinstance(unknown_items, str):
            unknown_items = [unknown_items]
        unknowns = "；".join(unknown_items)
        blocks.append(f'<a id="source-{sid}"></a>\n\n**{sid}** · {authors} · '
                      f'[{title}]({item["url"]}) · DOI `{item["doi"]}`。\n\n'
                      f'定位：{locator}。核查层级：{depth}。' +
                      (f' 待确认：{unknowns}。' if unknowns else ""))
    blocks.append("方法参考：[NIST 精确二项式置信区间](https://www.itl.nist.gov/div898/handbook/prc/section2/prc241.htm)。本报告的零误码数字由公开公式独立计算；不是硬件认证。")
    return "\n\n".join(blocks)


CSS = """
:root{--ink:#233c4d;--muted:#526b79;--teal:#246f77;--line:#dce5e7;--paper:#fff;--wash:#f3f7f7}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;color:var(--ink);background:#f5f7f8;font:17px/1.72 Bahnschrift,"PingFang SC","Noto Sans CJK SC",Arial,sans-serif}
header{background:#213d4c;color:#fff;padding:25px max(24px,calc((100vw - 1160px)/2));font-size:15px}header a{color:#d8f1ef}
main{max-width:1220px;margin:0 auto;padding:34px 42px 70px;background:var(--paper)}h1,h2,h3{line-height:1.35;color:#203e50;font-weight:600;scroll-margin-top:20px}h1{font-size:34px;margin:0 0 22px}h2{font-size:25px;border-top:1px solid var(--line);margin:52px 0 20px;padding-top:26px}h3{font-size:20px;margin-top:28px}p,li{max-width:950px}p{margin:14px 0}a{color:var(--teal);text-underline-offset:3px}strong{font-weight:650}code{font-size:.92em;background:var(--wash);padding:2px 5px;border-radius:3px;overflow-wrap:anywhere}pre{overflow:auto;background:var(--wash);padding:16px}pre code{padding:0}blockquote{border-left:3px solid var(--teal);padding-left:18px;margin-left:0;color:var(--muted)}img{max-width:100%;height:auto;background:white}p:has(>img){max-width:none;margin:28px 0 6px}p:has(>em:only-child){color:var(--muted);font-size:15px;max-width:none}table{border-collapse:collapse;width:100%;font-size:15px;line-height:1.6;display:block;overflow-x:auto;margin:20px 0}th,td{padding:12px 13px;border:1px solid var(--line);vertical-align:top;min-width:100px}th{background:#eef4f5;text-align:left}td:nth-child(2),td:nth-child(3){min-width:190px}tbody tr:nth-child(even){background:#fafcfc}details{border:1px solid var(--line);padding:12px 18px;background:var(--wash);border-radius:5px;margin:24px 0}summary{cursor:pointer;color:var(--teal);font-weight:600}.toc ul{list-style:none;padding-left:18px}.toc>ul{padding:0;columns:2}.toc a{text-decoration:none}footer{font-size:14px;border-top:1px solid var(--line);padding-top:20px;color:var(--muted);margin-top:40px}.status{font-size:14px;letter-spacing:.03em;color:#cae5e4}.back{float:right}
p:has(>a>img){max-width:none;margin:28px 0 6px}a:has(>img){display:block}
@media(max-width:720px){body{font-size:16px}main{padding:24px 18px}h1{font-size:27px}h2{font-size:22px}.toc>ul{columns:1}table{font-size:14px}header{padding:18px}.back{float:none;display:block;margin-top:5px}}
@media print{body,main{background:white}main{padding:0;max-width:none}body{font-size:10.8pt;line-height:1.65}h1{font-size:25pt}h2{font-size:15pt;break-after:avoid}h3{font-size:12pt;break-after:avoid}header,details,.back{display:none}img{max-height:230mm;object-fit:contain}table{display:table;font-size:8.5pt;table-layout:fixed}th,td{min-width:0;padding:6px;overflow-wrap:anywhere}p:has(>img){break-inside:avoid}a{color:inherit}@page{size:A4;margin:20mm}}
"""


def main():
    calc = read(EV / "calculations.json")
    literature = read(EV / "literature.json")
    sources = {s["id"]: s for s in literature["sources"]}
    assert set(sources) == set(SUMMARIES), "Review table when source set changes"
    (DOC / "figures").mkdir(exist_ok=True)
    plots(calc, sources)
    rows = [[g["square_side_um"], g["square_area_um2"],
             f'{g["same_I_100uA_J_A_cm2"]:g}', f'{g["same_J_25A_cm2_I_uA"]:g}',
             f'{g["square_perimeter_over_area_um_inv"]:g}'] for g in calc["geometry"]]
    size = table(["方形边长 / µm", "面积 / µm²", "同 100 µA 的 J / A·cm⁻²", "同 J=25 的 I / µA", "周长/面积 / µm⁻¹"], rows)
    size += '\n\n![同I与同J条件下的纯教学RC计算](figures/06-size-rc-illustration.svg)\n\n'
    size += ('*图 3｜独立假设计算：C=0.25 fF/µm²×面积+0.1 fF/µm×周长+100 fF；'
             'rd=50 mV/I。它演示条件改变可反转 RC 趋势，不是拟合或电光性能预测。'
             '数值及全部假设见 calculations.json。*')
    literature_table = table(["来源/变量", "器件与几何", "偏置和响应/速率", "效率与能耗边界", "核查深度"],
        [[f'[{sid}](#source-{sid})<br>{s[0]}', *s[1:]] for sid, s in SUMMARIES.items()])
    lin = read(ROOT / "evidence/microled-dynamic-20261029/extraction-checks.json")
    lin_table = table(["偏置 / µA", "J / A·cm⁻²", "源定义 −3 dB / GHz", "源定义 −6 dB / GHz", "1.85 GHz 处 / dB"],
        [[f'{r["current_uA"]:g}', f'{r["current_density_A_cm2"]:.2f}', f'{r["source_BW3_MHz"]/1000:.4f}',
          f'{r["source_BW6_MHz"]/1000:.4f}', f'{r["source_S21_at_Nyquist1p85GHz_dB"]:.4f}'] for r in lin["selected_points"]])
    plan = (DOC / "joint-validation-plan.md").read_text()
    plan = re.sub(r"^# .+\n", "", plan)
    plan = re.sub(r"^## (.+)$", r"### \1", plan, flags=re.M)
    refs = references(sources, read(EV / "root-sources.json")["sources"])
    paired = ('![同一论文内部的带宽前后值](figures/05-within-study-bandwidth.svg)\n\n'
              '*图 5｜由两篇原始摘要披露的数值独立绘图，各面板具有自己的 J 和器件条件；'
              '频率数值见文献台账，不能据此比较两条路线的系统能耗或制造优势。*')
    values = {"SIZE_TABLE": size, "LITERATURE_TABLE": literature_table, "LIN_TABLE": lin_table,
              "JOINT_PLAN": plan, "PAIRED_FIGURE": paired, "REFERENCES": refs}
    text = (DOC / "report-template.md").read_text()
    for key, value in values.items():
        assert text.count(f"<!-- {key} -->") == 1
        text = text.replace(f"<!-- {key} -->", value)
    assert "<!-- " not in text
    (DOC / "README.md").write_text(text)
    md = markdown.Markdown(extensions=["tables", "fenced_code", "toc"], extension_configs={"toc": {"toc_depth": "2-3"}})
    body = md.convert(text)
    body = re.sub(r'<img([^>]*?) src="([^"]+)"([^>]*?)>',
                  r'<a href="\2" title="查看原尺寸图"><img\1 src="\2"\3></a>', body)
    contents = '<details><summary>阅读目录</summary>' + md.toc + '</details>'
    body = body.replace('<h2', contents + '<h2', 1)
    page = ('<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>MicroLED 器件与 Driver 联合设计｜净3.2 Gb/s研究报告</title>'
            f'<style>{CSS}</style></head><body><header><div class="status">OPEN MICROLED DRIVER ASIC · DEVICE STUDY · 2026-10-29</div>'
            '<a class="back" href="../vcsel-reference-microled-dynamics-20261029/index.html">前一阶段研究</a>'
            '文献实测 · 解析计算 · 待执行协议</header><main>' + body +
            '<footer>公开研究报告：未预选路线，未新增器件或光链路通过结果。'
            '文字源：<a href="README.md">README.md</a> · <a href="reproduce.md">复现</a></footer></main></body></html>')
    (DOC / "index.html").write_text(page)
    print(json.dumps({"report": str(DOC.relative_to(ROOT)), "literature_rows": len(sources),
                      "additional_sources": 2, "figures": len(list((DOC / "figures").glob("*.svg"))),
                      "status": "rendered; validation required"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
