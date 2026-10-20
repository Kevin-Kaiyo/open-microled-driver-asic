#!/usr/bin/env python3
"""Check the saved report, local references and frozen experiment identities.

This is document delivery validation; it does not rerun SPICE or physical rules.
"""
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlsplit, unquote
import hashlib
import json
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "docs/research/highspeed-nrz-pex-20261020"
EVIDENCE = ROOT / "evidence/highspeed-nrz-pex"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Page(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.references, self.ids = [], []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.append(attrs["id"])
        for key in ("href", "src"):
            if key in attrs:
                self.references.append(attrs[key])


def main():
    checked = []
    for path in (REPORT / "index.html", REPORT / "layout-viewer.html"):
        text = path.read_text()
        assert "{{" not in text, f"Unresolved template in {path}"
        page = Page(text)
        assert len(page.ids) == len(set(page.ids)), f"Duplicate ID in {path}"
        for ref in page.references:
            url = urlsplit(ref)
            if url.scheme or url.netloc:
                continue
            target = (path.parent / unquote(url.path)).resolve() if url.path else path
            assert target.is_file(), f"Missing local reference: {path.name}: {ref}"
            assert target.is_relative_to(ROOT), f"Reference outside repository: {ref}"
            if url.fragment and target.suffix == ".html":
                assert unquote(url.fragment) in Page(target.read_text()).ids, ref
            checked.append({"from": str(path.relative_to(ROOT)), "reference": ref})
    figures = sorted((REPORT / "figures").glob("*.svg"))
    for path in figures:
        root = ET.parse(path).getroot()
        assert root.tag.endswith("svg"), path
    summary = json.loads((EVIDENCE / "summary.json").read_text())
    assert summary["completion"]["status"] == "declared_case_lists_complete"
    assert sha(ROOT / summary["analysis_json"]) == summary["analysis_sha256"]
    assert json.loads((EVIDENCE / "validation.json").read_text())["passed"]
    assert json.loads((EVIDENCE / "physical/delivery-validation.json").read_text())["passed"]
    inputs = [
        EVIDENCE / "summary.json",
        EVIDENCE / "physical/summary.json",
        EVIDENCE / "integration-method-audit.json",
        EVIDENCE / "wire-paths.json",
        ROOT / summary["analysis_json"],
    ]
    files = sorted(p for p in REPORT.rglob("*") if p.is_file())
    files += sorted(p for p in Path(__file__).parent.glob("*.py") if p.is_file())
    def entry(p):
        return {"path": str(p.relative_to(ROOT)), "size": p.stat().st_size, "sha256": sha(p)}
    result = {
        "passed": True,
        "scope": "Saved report references, SVG syntax, source hashes and final analysis identity; not electrical qualification.",
        "local_references_checked": len(checked),
        "svg_files_checked": len(figures),
        "input_files": [entry(p) for p in inputs],
        "report_and_script_files": [entry(p) for p in files],
        "references": checked,
    }
    (EVIDENCE / "report-delivery.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: result[k] for k in ("passed", "scope", "local_references_checked", "svg_files_checked")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
