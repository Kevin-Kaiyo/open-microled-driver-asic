"""Validate source identity and independent arithmetic for a documentation-only study."""
from pathlib import Path
import argparse
import csv
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import json
import re
import subprocess

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "docs/research/decision-review-20261011"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads((ROOT / path).read_text())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf-pages-reviewed", type=int, required=True,
                        help="Actual number of final rendered pages directly inspected by the reviewer")
    args = parser.parse_args()
    ledger = json.loads((BASE / "evidence-ledger.json").read_text())
    checks = []

    def check(name, passed, detail=None):
        checks.append({"name": name, "passed": bool(passed), "detail": detail})
        if not passed:
            raise AssertionError(name + ": " + str(detail))

    check("Engineering HEAD matches declared baseline",
          subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip() == ledger["engineering_baseline"])
    changed = subprocess.check_output(["git", "diff", "HEAD", "--name-only"], cwd=ROOT, text=True).splitlines()
    check("Tracked engineering inputs unchanged", set(changed) <= {"README.md", "docs/research/README.md"}, changed)
    for p, digest in ledger["sources_sha256"].items():
        check("Ledger source " + p, sha(ROOT / p) == digest)

    # Preserve the one known historical TB revision; never silently retag an old run.
    mapping = read("evidence/research/input-mapping.json")
    historical = mapping["historical_input"]
    check("Historical TB snapshot identity", sha(ROOT / historical["public_snapshot"]) == historical["sha256"])
    check("Current TB mapping identity", sha(ROOT / mapping["current_input"]["path"]) == mapping["current_input"]["sha256"])
    as_run = []
    for p, key in [("evidence/robustness/main-summary.json", "source_hashes"),
                   ("evidence/robustness/boundary-summary.json", "source_hashes"),
                   ("evidence/characterization/measured-load-summary.json", "source_hashes"),
                   ("evidence/control/validation.json", "source_sha256")]:
        entries = read(p)[key]
        differences = []
        for target, digest in entries.items():
            if sha(ROOT / target) != digest:
                check("Only mapped historical TB differs", p == "evidence/characterization/measured-load-summary.json"
                      and target == historical["original_path"] and digest == historical["sha256"]
                      and mapping["passed"] and mapping["default_exported_trace_byte_identical"], target)
                differences.append({"path": target, "as_run_sha256": digest, "handling": "Preserved snapshot and existing default-behavior mapping; not a new EDA run"})
        as_run.append({"summary": p, "declared_inputs": len(entries), "current_matching_inputs": len(entries)-len(differences), "historical_differences": differences})

    # Independent raw CSV interpolation and dimensional calculations.
    rows = list(csv.DictReader((ROOT / "analog/models/measured-led/lin2026-yellow20-diamond-iv.csv").open()))
    points = [(float(x["current_A"]), float(x["voltage_V"])) for x in rows]
    check("100 static source points and mA to A conversion", len(rows) == 100 and all(abs(float(x["source_current_mA"]) * .001 - float(x["current_A"])) < 1e-15 for x in rows))
    vf = next(v0 + (v1-v0) * (100e-6-i0)/(i1-i0) for (i0,v0),(i1,v1) in zip(points, points[1:]) if i0 <= 100e-6 <= i1)
    check("Raw CSV independently gives report Vf", abs(vf-ledger["calculations"]["vf100_uA_v"]) < 1e-12)
    check("5V headroom arithmetic", abs((5-vf)-ledger["calculations"]["available_headroom_at_5V_v"]) < 1e-12)
    boundary = read("evidence/robustness/boundary-summary.json")
    r10 = next(x for x in boundary["dc_results"] if x["rled_ohm"] == 10000)
    err = (r10["current_uA"] / 100 - 1) * 100
    check("10k case fails predeclared full-current guard with IREF retained", abs(err-ledger["calculations"]["R10k_error_percent_vs_100uA"]) < 1e-12 and err < -5 and r10["reference_uA"] == 100)
    check("Ideal lowest-code charge and average units", Fraction(100, 10**6)*Fraction(1, 10**6) == Fraction(1,10**10)
          and abs(ledger["calculations"]["ideal_Q1_C"] - 1e-10) < 1e-24
          and abs(ledger["calculations"]["ideal_average_duty1_A"] - .390625e-6) < 1e-20)
    quant = [Fraction((2*256*c+4095)//8190,256)-Fraction(c,4095) for c in range(4096)]
    max_quant_pp = float(max(map(abs,quant)) * 100)
    check("Independent all-command quantization", abs(max_quant_pp-.195265) < .000001
          and len({(2*256*c+4095)//8190 for c in range(4096)}) == 257)
    main_result = read("evidence/robustness/main-summary.json")
    results = {x["name"]: x for x in main_result["results"]}
    area = []
    for name, x in results.items():
        if x.get("area_error_pct") is None:
            continue
        prefix = name.split("_d")[0]
        reference = results[prefix + "_d256"]["current_uA"]
        calculated = (x["current_uA"] / (reference*x["duty"]/256) - 1) * 100
        check("Independent area denominator " + name, abs(calculated - x["area_error_pct"]) < 1e-9)
        area.append(abs(calculated))
    check("Worst area is within predeclared 2percent guard", abs(max(area)-ledger["calculations"]["main_max_abs_area_error_pct"]) < 1e-9 and max(area) < 2)
    measured = read("evidence/characterization/measured-load-summary.json")
    caps = sorted([x for x in measured["assumed_capacitance_transients"] if x["duty"] == 1 and x["maxstep_ns"] == 20], key=lambda x: x["assumed_cap_pF"])
    for x, value in zip(caps, ledger["calculations"]["cap_duty1_outside_domain_signed_charge_percent"]):
        domain = x["measured_domain"]
        ratio = domain["outside_measured_domain_signed_conduction_charge_c"] / domain["static_conduction_charge_c"] * 100
        check("Signed model-domain ratio " + x["name"], abs(ratio-value) < 1e-12 and not x["dynamic_qualification"])

    for p in [BASE / "report.md", BASE / "README.md"]:
        missing = []
        for href in re.findall(r'\]\(([^)]+)\)', p.read_text()):
            if "://" not in href and not href.startswith("#") and not (p.parent / href.split("#")[0]).exists():
                if href != "validation.json":
                    missing.append(href)
        check("Local document links " + p.name, not missing, missing)
    layout = read("build/research-decision-20261011/layout-check.json")
    check("A4 geometry, no overflow, all figures loaded", len(layout["sections"]) == 9 and not layout["overflow"]
          and all(x["height"] < 970 for x in layout["sections"]) and all(x["loaded"] for x in layout["images"]))
    pdf = PdfReader(str(BASE / "report.pdf"))
    check("Nine readable PDF pages", len(pdf.pages) == 9 and all(len(p.extract_text()) > 300 for p in pdf.pages))
    check("All final pages directly visually inspected", args.pdf_pages_reviewed == len(pdf.pages))
    for name, item in ledger["figures"].items():
        check("Figure output identity " + name, sha(BASE / name) == item["sha256"])
    validation = {"study_date": "2026-10-11", "validated_at_UTC": datetime.now(timezone.utc).isoformat(),
        "passed": all(x["passed"] for x in checks), "checks": checks, "as_run_input_identity": as_run,
        "independent_quantization_max_full_scale_percentage_points": max_quant_pp,
        "engineering_baseline": ledger["engineering_baseline"], "new_EDA_runs": 0,
        "peer_review": {"independent_read_only_reviews": 2, "corrections": ["Behavioral source sensitivity separated from implemented source compliance", "Fault signed charge separated from directional tails/peaks and sustained current threshold", "Network differences separated from threshold failures", "STA/SDF explicitly attributed to digital macro"]},
        "pdf_review": {"pages": len(pdf.pages), "direct_visual_pages": list(range(1,len(pdf.pages)+1)), "overflow": [], "issues": []},
        "layout": layout,
        "validator_sha256": sha(Path(__file__)),
        "outputs_sha256": {p.name: sha(p) for p in BASE.iterdir() if p.is_file() and p.name != "validation.json"},
        "publication": "Local working documents; no commit/push or external upload in this turn",
        "scope": "Current source/record identity and independent report arithmetic, link and render validation. Not a new circuit regression or new measurement."}
    (BASE / "validation.json").write_text(json.dumps(validation, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({"passed": validation["passed"], "checks": len(checks), "as_run_hash_entries": sum(x["declared_inputs"] for x in as_run),
                      "preserved_historical_TB": 1, "PDF_pages_visually_reviewed": args.pdf_pages_reviewed, "new_EDA_runs": 0}))


if __name__ == "__main__":
    main()
