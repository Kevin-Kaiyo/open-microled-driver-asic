"""Render the stage update with the project's established report typography."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT/'scripts/driver_pvt_20261117/render_html.py'
spec = importlib.util.spec_from_file_location('stage_report_html', SOURCE)
html = importlib.util.module_from_spec(spec)
spec.loader.exec_module(html)
html.REPORT = ROOT/'docs/research/driver-ab-20261118'
html.STYLE += """
@media print{
h2{break-before:page;border:0;margin:0 0 .5em;padding:0}
figure{break-inside:avoid}figure img{max-height:110mm}
}
"""
html.build('README.md', '<a href="technical-stage-report.pdf">下载 PDF</a><a href="reproduce.html">复现与数据</a><a href="../driver-pvt-20261117/index.html">上一轮 PVT 报告</a>')
html.build('reproduce.md', '<a href="index.html">返回研究报告</a>')
for filename in ['index.html', 'reproduce.html']:
    links = html.LocalLinks()
    links.feed((html.REPORT/filename).read_text())
    for link in links.links:
        parsed = html.urlsplit(link)
        if not parsed.scheme and parsed.path and parsed.path != 'technical-stage-report.pdf':
            assert (html.REPORT/html.unquote(parsed.path)).resolve().is_file(), link
