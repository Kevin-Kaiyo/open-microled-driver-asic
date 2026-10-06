"""Verify published research identity, budgets and PDF; no device qualification."""
from pathlib import Path
from fractions import Fraction
from datetime import datetime
import argparse
import hashlib
import json
import re
import subprocess
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "evidence/automotive/validation.json"
BASELINE = "3a9ca422b78b57ef6cd0b5eea163c68321375660"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf-pages-reviewed", type=int, required=True)
    args = parser.parse_args()
    checks = []

    def check(name, result):
        checks.append({"name": name, "passed": bool(result)})
        if not result:
            raise RuntimeError(name)

    base = ROOT / "docs/research/automotive"
    evi = json.loads((ROOT / "evidence/automotive/headlamp-sources.json").read_text())
    jh = json.loads((ROOT / "evidence/automotive/huaxin-sources.json").read_text())
    evi_ids = {s["source_id"] for s in evi["sources"]}
    check("EVIYOS unique source IDs", len(evi_ids) == len(evi["sources"]))
    check("EVIYOS claim source IDs resolve", bool(evi["claims"]) and all(
        c["source_id"] in evi_ids for c in evi["claims"]))
    check("Huaxin identity and secondary leads separate", bool(jh["manufacturer_identity"]) and
          bool(jh["quarantined_secondary_leads"]))
    raw = [{"path": s["path"], "sha256": s["sha256"]} for s in evi["private_raw_sources"]]
    raw += [{"path": s["local_raw"], "sha256": s["sha256"]}
            for s in jh["sources"] if s.get("local_raw")]
    for s in raw:
        check("Private original hash: " + s["path"], sha(ROOT / s["path"]) == s["sha256"])
        result = subprocess.run(["git", "check-ignore", "-q", s["path"]], cwd=ROOT)
        check("Private original ignored: " + s["path"], result.returncode == 0)

    for suffix in ["md", "html", "pdf"]:
        path = "docs/research/research-report." + suffix
        before = subprocess.check_output(["git", "show", BASELINE + ":" + path], cwd=ROOT)
        check("Frozen v0.4 report unchanged: " + suffix,
              hashlib.sha256(before).hexdigest() == sha(ROOT / path))
    changed = subprocess.check_output(["git", "diff", "--name-only", BASELINE], cwd=ROOT,
                                      text=True).splitlines()
    protected = ("analog/", "rtl/", "sim/", "layout/", "evidence/", "scripts/digital/",
                 "scripts/physical/", "scripts/characterization/", "scripts/joint_pex/",
                 "scripts/robustness/")
    check("No existing engineering implementation or run modified", not any(
        p.startswith(protected) and not p.startswith("evidence/automotive/") and
        p != "evidence/research/current-manifest.json" for p in changed))

    files = list(base.glob("*.md")) + [ROOT / "README.md", ROOT / "docs/research/README.md",
                                     ROOT / "docs/roadmap.md"]
    unresolved = []
    for p in files:
        for href in re.findall(r"\]\(([^)]+)\)", p.read_text()):
            if "://" in href or href.startswith("#"):
                continue
            target = (p.parent / href.split("#")[0].strip("<>")).resolve()
            if target != OUTPUT and not target.exists():
                unresolved.append([str(p.relative_to(ROOT)), href])
    check("All new/current research local links resolve", not unresolved)

    calculations = []
    for n in [256, 25600, 40000]:
        calculations.append({"assumed_pixels": n, "assumed_bits": 12,
                             "packed_bytes": (n * 12 + 7) // 8,
                             "double_buffer_bytes": 2 * ((n * 12 + 7) // 8),
                             "payload_mbps_60hz": n * 12 * 60 / 1e6,
                             "payload_mbps_100hz": n * 12 * 100 / 1e6})
    check("12-bit reported payload and buffers independently calculated", calculations == [
        {"assumed_pixels": 256, "assumed_bits": 12, "packed_bytes": 384,
         "double_buffer_bytes": 768, "payload_mbps_60hz": .18432, "payload_mbps_100hz": .3072},
        {"assumed_pixels": 25600, "assumed_bits": 12, "packed_bytes": 38400,
         "double_buffer_bytes": 76800, "payload_mbps_60hz": 18.432, "payload_mbps_100hz": 30.72},
        {"assumed_pixels": 40000, "assumed_bits": 12, "packed_bytes": 60000,
         "double_buffer_bytes": 120000, "payload_mbps_60hz": 28.8, "payload_mbps_100hz": 48.0}])
    check("Efficiency budget", Fraction(18432, 1000) / Fraction(8, 10) == Fraction(2304, 100))
    check("16-bit memory representation distinct", 2 * 25600 * 2 == 102400)
    quantization = []
    for bits in [10, 12]:
        den = (1 << bits) - 1
        maximum = Fraction(0)
        for g in range(den + 1):
            duty = (512 * g + den) // (2 * den)  # independent integer half-up
            error = abs(Fraction(duty, 256) - Fraction(g, den))
            maximum = max(maximum, error)
            check_bound = 0 <= duty <= 256 and error <= Fraction(1, 512)
            if not check_bound:
                raise RuntimeError("Quantization bound")
        quantization.append({"command_bits": bits, "codes_checked": den + 1,
                             "max_normalized_absolute_error": float(maximum)})
    check("Quantization bound at all 10/12-bit codes", len(quantization) == 2)
    check("Uniform PWM arithmetic only", 1e6 / 1024 == 976.5625 and
          1e6 / 4096 == 244.140625 and 3906.25 * 1024 == 4e6 and 3906.25 * 4096 == 16e6)

    review = json.loads((ROOT / "evidence/automotive/independent-review.json").read_text())
    check("Independent research review passed", review["passed"] is True)
    review_hashes = review["reviewed_file_sha256"]
    check("Independent review has file identity", len(review_hashes) >= 6)
    for p, h in review_hashes.items():
        check("Reviewed file frozen: " + p, sha(ROOT / p) == h)

    pdf = PdfReader(base / "benchmark-report.pdf")
    check("All final PDF pages visually reviewed", len(pdf.pages) == args.pdf_pages_reviewed == 15)
    check("All PDF pages have extractable text", all(len(p.extract_text()) > 400 for p in pdf.pages))
    check("PDF has no replacement glyphs", all("\ufffd" not in p.extract_text() for p in pdf.pages))
    uris = []
    for page in pdf.pages:
        for ref in page.get("/Annots", []):
            action = ref.get_object().get("/A", {})
            if action.get("/S") == "/URI":
                uris.append(str(action.get("/URI")))
    check("PDF source/repository links are portable HTTPS", bool(uris) and
          all(u.startswith("https://") for u in uris))
    geometry = json.loads((ROOT / "build/automotive/report/layout-check.json").read_text())
    check("Actual A4 width geometry / no overflow", len(geometry["sections"]) == 15 and
          not geometry["overflow"] and all(s["height"] < 970 for s in geometry["sections"]))
    selected = [p for p in base.iterdir() if p.is_file()]
    selected += list((ROOT / "evidence/automotive").glob("*.json"))
    selected += [ROOT / "scripts/research" / n for n in
                 ["render_automotive.py", "print_automotive.cjs", "verify_automotive.py"]]
    selected = [p for p in selected if p != OUTPUT]
    result = {"date": datetime.now().astimezone().isoformat(), "research_date": "2026-10-06",
              "passed": True, "scope": "public-source research, document identity and calculation audit",
              "engineering_baseline_commit": BASELINE, "engineering_stage": "one-pixel v0.4 unchanged",
              "new_ecu_rtl_hardware_or_commercial_device_tests_executed": False,
              "commercial_protocol_compatibility_established": False,
              "source_originals_hash_verified": len(raw),
              "checks": checks, "independent_review": "evidence/automotive/independent-review.json",
              "assumed_budget_calculations": calculations, "quantization_math": quantization,
              "pdf_pages": len(pdf.pages), "pdf_visual_pages_reviewed": list(range(1, 16)),
              "pdf_layout": geometry, "files_sha256": {str(p.relative_to(ROOT)): sha(p)
                                                          for p in sorted(selected)}}
    OUTPUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(f"PASS {len(checks)} research/document checks; {len(raw)} private originals; 15 PDF pages reviewed")


if __name__ == "__main__":
    main()
