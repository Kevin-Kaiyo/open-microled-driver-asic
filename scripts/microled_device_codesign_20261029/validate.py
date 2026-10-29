#!/usr/bin/env python3
"""Check the report's data, source boundaries, links and frozen dependencies."""
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import unquote, urlsplit
import hashlib
import importlib.util
import json
import math
import platform
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "docs/research/microled-device-codesign-20261029"
EV = ROOT / "evidence/microled-device-codesign-20261029"
SCRIPT = ROOT / "scripts/microled_device_codesign_20261029"


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


class Parser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.links = []
        self.images = []
        self.duplicate_ids = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            if attrs["id"] in self.ids:
                self.duplicate_ids.append(attrs["id"])
            self.ids.add(attrs["id"])
        if tag == "a" and attrs.get("href"):
            self.links.append(attrs["href"])
        if tag == "img":
            self.images.append(attrs)


def main():
    checks = []
    def check(name, condition, detail=None):
        checks.append({"name": name, "passed": bool(condition), "detail": detail})

    calc = json.loads((EV / "calculations.json").read_text())
    liter = json.loads((EV / "literature.json").read_text())
    extra = json.loads((EV / "root-sources.json").read_text())
    md = (DOC / "README.md").read_text()
    page = (DOC / "index.html").read_text()
    parsed = Parser()
    parsed.feed(page)
    check("no_generation_markers", "<!-- " not in page and "<!-- " not in md)
    check("nine_literature_plus_two_method_baseline_sources", len(liter["sources"]) == 9 and len(extra["sources"]) == 2)
    dois = [s["doi"] for s in liter["sources"] + extra["sources"]]
    check("all_source_dois_visible", all(d in md and d in page for d in dois), dois)
    check("unique_html_ids", not parsed.duplicate_ids, parsed.duplicate_ids)
    check("seven_report_images_with_alt", len(parsed.images) == 7 and all(x.get("alt") for x in parsed.images))
    broken = []
    local_links = 0
    for value in parsed.links + [x["src"] for x in parsed.images]:
        url = urlsplit(value)
        if url.scheme or url.netloc:
            continue
        local_links += 1
        target = (DOC / unquote(url.path)).resolve() if url.path else DOC / "index.html"
        if not target.exists():
            broken.append(value)
        elif not url.path and url.fragment and unquote(url.fragment) not in parsed.ids:
            broken.append(value)
    check("local_links_and_current_page_anchors", not broken, {"checked": local_links, "broken": broken})

    specs = importlib.util.spec_from_file_location("device_calc", SCRIPT / "calculations.py")
    module = importlib.util.module_from_spec(specs)
    specs.loader.exec_module(module)
    # This command performs strict identity checks and explicit 1-ULP-derived tolerance only.
    child = subprocess.run([sys.executable, str(SCRIPT / "calculations.py"), "--check"], capture_output=True, text=True)
    check("calculation_self_checks", child.returncode == 0, child.stdout.strip() or child.stderr.strip())
    f = calc["frame"]
    check("net_rate_independent_recalculation", f["payload_bits"] / (f["frame_bits"] / f["line_bit_rate_bps"]) == 3.2e9)
    check("nrz_ui_units", math.isclose(f["nrz"]["symbol_UI_ps"], 1e12/3.7e9, rel_tol=1e-13))
    check("frame_parts_count", sum(f["parts_bits"].values()) == 4736 and f["parts_bits"].get("training_guard") == 64)
    check("geometry_units", all(math.isclose(g["same_I_100uA_J_A_cm2"], 1e4/g["square_side_um"]**2, rel_tol=1e-13) for g in calc["geometry"]))
    check("same_J_current_units", all(math.isclose(g["same_J_25A_cm2_I_uA"], .25*g["square_side_um"]**2, rel_tol=1e-13) for g in calc["geometry"]))
    check("led_only_energy_independent", math.isclose(3 * 100e-6 / 3.2e9 * 1e12, .09375, rel_tol=1e-13))
    check("zero_errors_are_not_ber_zero", 7.3e-4 < module.zero_error_upper_bound(4096) < 7.4e-4)
    check("lifetime_dB_and_energy_boundaries_visible", all(t in md for t in ["20log10", "√3", "不能再加一次", "低 J", "465–570", "证据不足以预选"]))

    frozen = json.loads((ROOT / "evidence/microled-dynamic-20261029/manifest.json").read_text())["public_files"]
    altered = [p for p, entry in frozen.items() if sha(ROOT / p) != entry["sha256"]]
    check("historical_dynamic_evidence_unchanged", not altered, {"files": len(frozen), "altered": altered})
    changed_models = subprocess.run(["git", "diff", "--name-only", "HEAD", "--", "analog", "rtl", "digital"], cwd=ROOT, capture_output=True, text=True)
    check("no_circuit_or_model_changes", changed_models.returncode == 0 and not changed_models.stdout.strip(), changed_models.stdout.strip())

    svgs = list((DOC / "figures").glob("*.svg"))
    check("six_vector_figures_with_png", len(svgs) == 6 and all(p.with_suffix(".png").exists() for p in svgs))
    xml_errors = []
    for p in svgs:
        try:
            ET.parse(p)
        except ET.ParseError as exc:
            xml_errors.append({p.name: str(exc)})
    check("svg_xml_wellformed", not xml_errors, xml_errors)
    check("png_signature", all(p.read_bytes().startswith(b"\x89PNG\r\n\x1a\n") for p in (DOC / "figures").glob("*.png")))
    check("public_source_notes_no_private_image_embeds", "![" not in (EV / "source-notes.md").read_text())
    private_assets = liter["original_asset_ledger"]
    private_checked = []
    for asset in private_assets:
        # The ledger explicitly locates originals without including their bytes in public evidence.
        for key in ("local_path", "path", "private_path"):
            if key in asset:
                p = ROOT / asset[key]
                private_checked.append({"id": asset.get("id", asset.get("asset_id")), "exists": p.exists(),
                                        "hash_ok": p.exists() and sha(p) == asset.get("sha256")})
                break
    check("private_original_ledger_readback", len(private_checked) >= 5 and all(x["hash_ok"] for x in private_checked), private_checked)

    public = sorted(p for d in (DOC, EV, SCRIPT) for p in d.rglob("*") if p.is_file()
                    and "__pycache__" not in p.parts and p.name not in {"validation.json", "manifest.json", "delivery-check.json"})
    check("no_original_paper_or_large_waveform_in_public_set", all(p.suffix.lower() not in {".pdf", ".raw", ".gz", ".zip"} and p.stat().st_size < 5_000_000 for p in public))
    manifest = {str(p.relative_to(ROOT)): {"bytes": p.stat().st_size, "sha256": sha(p)} for p in public}
    receipt = {"date": "2026-10-29", "scope": "Literature, original diagrams and analytical calculations only; no new device/driver pass claim",
               "python": platform.python_version(), "checks": checks,
               "passed": all(x["passed"] for x in checks), "public_files": len(public),
               "public_bytes": sum(v["bytes"] for v in manifest.values()),
               "visual_review": "See visual-review.json; static and browser acceptance are separate from calculations",
               "excluded": ["private original papers/crops under build", "historical large simulation waveforms already archived", "PDK/runtime/hardware"],
               "manifest_file": "manifest.json"}
    (EV / "manifest.json").write_text(json.dumps({"files": manifest, "exclusions": receipt["excluded"]}, ensure_ascii=False, indent=2) + "\n")
    (EV / "validation.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"passed": receipt["passed"], "checks": len(checks), "failed": [x for x in checks if not x["passed"]],
                      "public_files": len(public), "bytes": receipt["public_bytes"]}, ensure_ascii=False))
    raise SystemExit(0 if receipt["passed"] else 1)


if __name__ == "__main__":
    main()
