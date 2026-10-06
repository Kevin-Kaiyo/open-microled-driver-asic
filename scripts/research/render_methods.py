"""Render the dated experimental-methods study without replacing frozen v0.4 reports."""
from pathlib import Path
import html
import markdown
import re

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "docs/research/experimental-methods"


def public_links(body):
    """Keep exported PDF links usable outside this local checkout."""
    def replace(match):
        href = html.unescape(match.group(1))
        if "://" in href or href.startswith("#"):
            return match.group(0)
        path, separator, fragment = href.partition("#")
        target = (BASE / path).resolve().relative_to(ROOT)
        url = "https://github.com/Kevin-Kaiyo/open-microled-driver-asic/blob/main/" + target.as_posix()
        if separator:
            url += "#" + fragment
        return 'href="' + html.escape(url, quote=True) + '"'
    return re.sub(r'href="([^"]+)"', replace, body)


def main():
    source = (BASE / "report.md").read_text()
    pages = source.split("<!-- PAGE -->")
    sections = []
    for i, text in enumerate(pages, 1):
        body = public_links(markdown.markdown(text.strip(), extensions=["tables", "fenced_code"]))
        sections.append(f'<section class="page" data-page="{i}">{body}</section>')
    css = """
    @page { size:A4; margin:20mm; }
    * { box-sizing:border-box; }
    body { margin:0; color:#24353c; font:10.7pt/1.62 'Avenir Next','PingFang SC',sans-serif; }
    h1,h2,h3 { color:#164f5b; font-family:'Avenir Next','PingFang SC',sans-serif; line-height:1.35; }
    h1 { font-size:26pt; margin:0 0 6mm; }
    h2 { font-size:19pt; margin:0 0 5mm; padding-bottom:3mm; border-bottom:1.2px solid #bcced1; }
    h3 { font-size:12.5pt; margin:4mm 0 2mm; }
    p { margin:0 0 3mm; }
    strong { color:#183e49; }
    a { color:#176977; text-decoration:none; overflow-wrap:anywhere; }
    ul,ol { margin:2mm 0 4mm; padding-left:5.5mm; }
    li { margin-bottom:1.5mm; }
    table { border-collapse:collapse; width:100%; margin:3mm 0 4mm; font-size:9.4pt; line-height:1.48; }
    th { text-align:left; background:#eaf1f1; color:#164f5b; font-weight:600; }
    th,td { padding:2.2mm 2.4mm; border-bottom:1px solid #d9e1e2; vertical-align:top; overflow-wrap:anywhere; }
    tr { break-inside:avoid; }
    code { font-family:'Avenir Next','PingFang SC',sans-serif; font-size:0.94em; }
    pre { padding:3mm; background:#f0f4f4; white-space:pre-wrap; font-size:9.5pt; line-height:1.5; }
    blockquote { margin:4mm 0; padding:3.5mm 4mm; border-left:3px solid #397e83; background:#edf4f3; }
    blockquote p:last-child { margin:0; }
    .page { break-after:page; }
    .page:last-child { break-after:auto; }
    .flow { display:grid; grid-template-columns:1fr 1fr 1fr; gap:3mm; margin:5mm 0; }
    .node { border:1px solid #bfd0d2; border-radius:2mm; padding:3mm; background:#f6f9f8; }
    .node b { display:block; color:#164f5b; margin-bottom:1mm; }
    .small { font-size:9.1pt; color:#536d74; }
    @media print { body,.page { width:170mm; } }
    @media screen { body { background:#edf2f2; } .page { background:white; width:210mm; min-height:297mm; margin:8mm auto; padding:20mm; box-shadow:0 1px 8px #bac9ca; } }
    """
    target = BASE / "report.html"
    target.write_text('<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
                      '<meta name="viewport" content="width=device-width,initial-scale=1">'
                      f'<title>{html.escape("MicroLED 实验性研发方法验证 · 2026-10-06")}</title>'
                      f'<style>{css}</style></head><body>'+"\n".join(sections)+"</body></html>\n")
    print(f"Rendered {len(pages)} sections: {target.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
