"""Render the Chinese research report and the native replay waveform excerpts."""

import csv
import hashlib
import json
from html import escape
from pathlib import Path

import markdown
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "docs/research/highspeed-workbench-20261110"
EVIDENCE = ROOT / "evidence/highspeed-workbench-20261110"
CSS = """
:root{color-scheme:light;--ink:#172d3a;--sub:#48606c;--accent:#176467;--rule:#cddde2;--light:#eff6f6}
*{box-sizing:border-box}
body{margin:0;background:#f7faf9;color:var(--ink);font:16px/1.69 "PingFang SC","Noto Sans CJK SC",sans-serif}
main{max-width:1060px;margin:0 auto;padding:42px 52px 72px;background:white}
h1,h2,h3{line-height:1.27;font-family:"Tw Cen MT","Avenir Next","PingFang SC","Noto Sans CJK SC",sans-serif}
h1{font-size:clamp(30px,5vw,47px);margin:16px 0 12px;letter-spacing:-.035em}
h2{font-size:27px;border-top:1px solid var(--rule);padding-top:28px;margin-top:42px}
h3{font-size:20px;margin-top:28px}
p,ul,ol{margin:14px 0}
li{margin:8px 0}
a{color:var(--accent);text-underline-offset:3px;overflow-wrap:anywhere}
nav{font-size:14px;color:var(--sub);padding-bottom:8px}
header{border-bottom:1px solid var(--rule)}
table{border-collapse:collapse;width:100%;font-size:.9em;line-height:1.55;margin:20px 0}
td,th{padding:10px 12px;text-align:left;vertical-align:top;border-bottom:1px solid var(--rule)}
th{background:var(--light);font-weight:650}
img{max-width:100%;height:auto;border-radius:7px}
figure{margin:22px 0}
figure.pair{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;align-items:center}
figure.pair img{width:100%;border:1px solid var(--rule)}
figcaption{grid-column:1/-1;color:var(--sub);font-size:14px}
pre{white-space:pre-wrap;overflow-wrap:anywhere;background:var(--light);padding:12px}
code{font-size:.92em;overflow-wrap:anywhere}
.table-scroll{overflow:auto}
@media(max-width:680px){main{padding:22px 18px 45px}figure.pair{grid-template-columns:1fr}td,th{padding:8px}.table-scroll table{min-width:520px}}
@media print{main{padding:0}body{background:white;font-size:11pt;line-height:1.58}figure,tr,h2,h3{break-inside:avoid}h2,h3{break-after:avoid}nav{display:none}th{print-color-adjust:exact}}
"""


def waveform_plot(summary):
    csv_path = EVIDENCE / "replay-waves.csv"
    if hashlib.sha256(csv_path.read_bytes()).hexdigest() != summary["waveform_extract"]["sha256"]:
        raise ValueError("CSV does not match the fresh replay receipt")
    with csv_path.open() as file:
        rows = list(csv.DictReader(file))
    fig, axes = plt.subplots(2, 2, figsize=(11, 6.2), layout="constrained")
    for ax, (route, item) in zip(axes.flat, summary["routes"].items()):
        metrics = item["metrics"]
        ui_ns = 1 / metrics["symbol_rate_Gbaud"]
        route_rows = [row for row in rows if row["route"] == route]
        t = [float(row["relative_time_ns"]) for row in route_rows]
        led = [float(row["emitter_current_mA"]) for row in route_rows]
        rx = [float(row["receiver_proxy"]) for row in route_rows]
        current, = ax.plot(t, led, color="#176467", lw=1.6, label="Emitter current")
        ax.set(xlabel="Time from validation segment (ns)", ylabel="Current (mA)",
               title=f"{route}  ·  {metrics['modulation']} {metrics['symbol_rate_Gbaud']:g} GBd")
        ax.tick_params(axis="y", colors="#176467")
        ax.spines["top"].set_visible(False)
        ax2 = ax.twinx()
        response, = ax2.plot(t, rx, color="#a15924", lw=1.45, label="RX proxy")
        unit, threshold_key = ("mW", "thresholds_mW") if route == "VCSEL" else ("µAeq", "thresholds_uAeq")
        ax2.set_ylabel(f"RX proxy ({unit})")
        ax2.tick_params(axis="y", colors="#a15924")
        ax2.spines["top"].set_visible(False)
        for value in metrics["receiver"][threshold_key]:
            ax2.axhline(value, ls="--", color="#a15924", alpha=.4, lw=.8)
        for n in range(12):
            ax.axvline(n * ui_ns, lw=.7, color="#cddde2", zorder=0)
            ax.text((n+.5)*ui_ns, .96, route_rows[n*48]["expected_symbol"],
                    transform=ax.get_xaxis_transform(), color="#586b72", fontsize=8,
                    va="top", ha="center")
        ax.set_xlim(0, 12 * ui_ns)
        ax.legend(handles=[current, response], loc="lower right", fontsize=8, ncols=2)
    fig.savefig(REPORT / "replay-waveforms.png", dpi=160)
    plt.close(fig)


def replay_table(summary):
    rows = ["| 路线 | 位错误 / 比较位 | 最小阈值余量 | 最小单侧时间 | E+ / E净 (pJ/尝试净位) |",
            "|---|---:|---:|---:|---:|"]
    for name, route in summary["routes"].items():
        m = route["metrics"]
        rx = m["receiver"]
        rx_name = "v3" if name == "VCSEL" else "v2"
        rows.append(f"| {name} · {rx_name} | {rx['errors']:,} / {rx['compared_bits']:,} | "
                    f"{rx['signed_amplitude_margin']:+.3f} µAeq | "
                    f"{rx['minimum_one_sided_time_margin_ps']:.2f} ps | "
                    f"{m['positive_pJ_per_offered_payload_bit']:.5f} / "
                    f"{m['net_pJ_per_offered_payload_bit']:.5f} |")
    return "\n".join(rows)


def html_report(stem, summary):
    source = REPORT / ("README.md" if stem == "index" else stem + ".md")
    content = source.read_text()
    if stem == "index":
        before, table = content.split("<!-- REPLAY_TABLE_BEGIN -->", 1)
        table, after = table.split("<!-- REPLAY_TABLE_END -->", 1)
        if table.strip() != replay_table(summary):
            raise ValueError("Report replay table differs from the verified JSON")
        content = before + replay_table(summary) + after
    title = content.splitlines()[0].removeprefix("# ")
    body = markdown.markdown(content, extensions=["tables", "fenced_code", "toc"])
    body = body.replace("<table>", '<div class="table-scroll" role="region" aria-label="数据表" tabindex="0"><table>')
    body = body.replace("</table>", "</table></div>")
    if stem == "index":
        top = ('<nav aria-label="章节"><a href="literature.html">原始文献</a>　'
               '<a href="physical/index.html">物理工作台</a>　<a href="fabrication.html">制造交付</a>　'
               '<a href="reproduce.html">复现</a></nav>')
    else:
        top = '<nav><a href="index.html">返回高速光发射 Driver 研究报告</a></nav>'
    html = (f'<!doctype html>\n<html lang="zh-CN"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{escape(title)}</title><style>{CSS}</style></head>'
            f'<body><main><header>{top}</header>{body}</main></body></html>\n')
    (REPORT / (stem + ".html")).write_text(html)


def main():
    summary = json.loads((EVIDENCE / "replay-summary.json").read_text())
    waveform_plot(summary)
    for stem in ["index", "literature", "fabrication", "reproduce"]:
        html_report(stem, summary)


if __name__ == "__main__":
    main()
