"""Build the audit HTML from README.md; Markdown==3.8.2 is an authoring extra.

Run in the physical-flow venv after installing that extra and generating plots.
PDF export uses a local browser's print-to-PDF with the CSS A4 page settings.
The data/source is README.md; this file contains presentation only.
"""
import base64
from pathlib import Path
import re
from urllib.parse import urljoin

import markdown

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "docs/review/README.md"
PUBLIC = "https://github.com/Kevin-Kaiyo/open-microled-driver-asic/blob/main/docs/review/"


def main():
    parts = SOURCE.read_text().split("<!-- page -->")
    pages = []
    for part in parts:
        body = markdown.markdown(part, extensions=["tables", "fenced_code"])
        def embed(match):
            path = (SOURCE.parent / match.group(1)).resolve()
            payload = base64.b64encode(path.read_bytes()).decode()
            return 'src="data:image/png;base64,' + payload + '"'
        body = re.sub(r'src="([^"]+\.png)"', embed, body)
        body = re.sub(r'href="([^"]+)"', lambda m: 'href="' + urljoin(PUBLIC, m.group(1)) + '"', body)
        pages.append('<section class="page">'+body+'</section>')
    css = """
    @page { size:A4; margin:20mm; }
    * { box-sizing:border-box; }
    body { margin:0; color:#243d49; background:#edf2f2;
      font-family:'Avenir Next','PingFang SC',sans-serif; font-size:11pt; line-height:1.6;
      -webkit-print-color-adjust:exact; print-color-adjust:exact; }
    .page { max-width:210mm; margin:24px auto; padding:20mm; background:white; }
    h1 { font-size:25pt; line-height:1.28; font-weight:600; margin:0 0 12pt; color:#163c4b; }
    h2 { font-size:17pt; line-height:1.4; font-weight:600; margin:0 0 16pt; color:#176f79;
      padding-bottom:8pt; border-bottom:1px solid #b8d6d7; }
    h1 + p { font-size:10pt; color:#647c84; }
    p { margin:0 0 10pt; }
    strong { font-weight:600; }
    a { color:#176f79; text-decoration:none; border-bottom:1px solid #bad4d5; overflow-wrap:anywhere; }
    table { width:100%; border-collapse:collapse; table-layout:auto; margin:12pt 0;
      font-size:9.5pt; line-height:1.48; }
    thead { display:table-header-group; }
    th { text-align:left; background:#eaf3f3; color:#17616b; font-weight:600; }
    th,td { padding:7pt 7pt; border-bottom:1px solid #dce5e7; vertical-align:top; }
    tr { break-inside:avoid; }
    img { width:100%; height:auto; display:block; margin:8pt 0; }
    code { font:inherit; font-size:.93em; background:#f0f4f5; overflow-wrap:anywhere; }
    pre { background:#f0f4f5; padding:10pt; font-size:8.3pt; line-height:1.55;
      white-space:pre-wrap; overflow-wrap:anywhere; }
    ul { padding-left:18pt; margin:5pt 0 10pt; }
    li { margin:4pt 0; }
    @media print { body { background:white; } .page { max-width:none; padding:0; margin:0;
      break-after:page; } .page:last-child { break-after:auto; } a { border-bottom:none; } }
    """
    result = '<!DOCTYPE html><html lang="zh-CN"><meta charset="utf-8"><title>单像素研究前提与正确性检阅</title><style>'+css+'</style><body>'+''.join(pages)+'</body></html>'
    (SOURCE.parent / "review.html").write_text(result)
    print(f"Created {len(pages)} report sections")


if __name__ == "__main__":
    main()
