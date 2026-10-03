"""Paired PDK DC/MC comparison of mirror W/L 10/2 and conceptual 20/4 um.

The candidate preserves the original RC and junction geometry deliberately. It
isolates W/L's model effect, and is NOT a candidate extracted layout or transient
qualification. Old 10/2 characterization is read-only and its source hash checked.
"""
from dataclasses import asdict, replace
from pathlib import Path
import csv
import itertools
import json
import math
import tempfile

import numpy as np
import run_reference_matching as base

N = 256
CANDIDATES = Path(__file__).resolve().parent / "candidates"
BASELINE = CANDIDATES / "pixel_driver_rc_w10_l2.spice"
CANDIDATE = CANDIDATES / "pixel_driver_rc_w20_l4.spice"


def main():
    historical_file = base.EVIDENCE / "reference-matching-summary.json"
    historical = json.loads(historical_file.read_text())
    if base.sha(BASELINE) != historical["source_hashes"]["evidence/layout/pixel_driver_rc.spice"]:
        raise RuntimeError("Frozen baseline does not match historical evidence")
    original = BASELINE.read_text()
    candidate = CANDIDATE.read_text().splitlines(keepends=True)[2:]
    expected = original.replace("w=10u l=2u", "w=20u l=4u")
    if "".join(candidate) != expected or original.count("w=10u l=2u") != 2:
        raise RuntimeError("Only the two mirror W/L values may change")
    base.PIXEL = CANDIDATE
    lock = base.check_models()
    work = Path(tempfile.mkdtemp(prefix="candidate-w20-l4-", dir=base.ROOT / "build/characterization"))
    files = [BASELINE, CANDIDATE, Path(__file__).resolve(), Path(base.__file__).resolve(), base.REFERENCE,
             historical_file, base.ROOT / "analog/models/microled.spice", base.ROOT / "layout/pdk-lock.json"]
    hashes = {str(p.relative_to(base.ROOT)): base.sha(p) for p in files}
    nominal = base.op(base.Condition(), work / "nominal_ideal")
    nominal_reference = base.op(base.Condition(reference="bounded"), work / "nominal_bounded")
    populations = {}
    for name, c in {
        "local_only": base.Condition(local_mismatch=1),
        "global_and_local": base.Condition(library="statistical", global_variation=1, local_mismatch=1),
        "reference_nominal_and_global_local": base.Condition(library="statistical", global_variation=1, local_mismatch=1, reference="bounded"),
    }.items():
        print(f"20/4 MC {name}: {N}", flush=True)
        rows = [base.op(c, work / name / f"sample_{n:04d}", base.SEED_START+n) for n in range(N)]
        populations[name] = rows
        base.save_csv(base.EVIDENCE / f"candidate-w20-l4-mc-{name}.csv", rows)
    print("20/4 fixed-corner/reference matrix: 1080", flush=True)
    matrix = []
    for n, (corner,temp,vl,vs,gain,tc,line) in enumerate(itertools.product(
        ("typical","ff","ss","fs","sf"), (0,27,85), (2.97,3.3,3.63), (4.5,5,5.5),
        (-base.CAL_BOUND,base.CAL_BOUND), (-base.TC_BOUND_PPM,base.TC_BOUND_PPM), (-base.LINE_BOUND_PPM_V,base.LINE_BOUND_PPM_V))):
        c = base.Condition(library=corner, temperature_c=temp, logic_v=vl, led_supply_v=vs,
                           reference="bounded", calibration_error=gain, tc_ppm=tc, line_ppm_v=line)
        matrix.append(base.op(c, work / "reference_pvt" / f"case_{n:04d}"))
    base.save_csv(base.EVIDENCE / "candidate-w20-l4-reference-pvt.csv", matrix)
    low, high = min(matrix,key=lambda r:r["iout"]), max(matrix,key=lambda r:r["iout"])
    for name, row in (("conditional_low",low),("conditional_high",high)):
        print(f"20/4 MC {name}: {N}", flush=True)
        c = replace(base.Condition(**{k:row[k] for k in base.Condition.__dataclass_fields__}), local_mismatch=1)
        rows = [base.op(c,work/name/f"sample_{n:04d}",base.SEED_START+n) for n in range(N)]
        populations[name] = rows
        base.save_csv(base.EVIDENCE / f"candidate-w20-l4-mc-{name}.csv", rows)
    with (base.EVIDENCE / "mc-local_only.csv").open() as f:
        old_rows = list(csv.DictReader(f))
    old_sigma = .7071*.01155/math.sqrt((2-.4)*(10+.5))
    new_sigma = .7071*.01155/math.sqrt((4-.4)*(20+.5))
    expected_scale = new_sigma/old_sigma
    paired_delta = max(abs(row[f"x{x}_dvth"]-float(old[f"x{x}_dvth"])*expected_scale)
                       for row,old in zip(populations["local_only"],old_rows) for x in (2,4))
    if len(old_rows)!=N or paired_delta>1e-12:
        raise RuntimeError("Paired same-seed W/L threshold scale check failed")
    beforeafter = {}
    for name, rows in populations.items():
        prior = historical["mc"]["populations"][name]
        current = base.describe(rows)
        beforeafter[name] = {"w10_l2":prior,"w20_l4":current,
                            "iout_sd_ratio_new_over_old":current["iout"]["sample_sd"]/prior["iout"]["sample_sd"]}
    if {str(p.relative_to(base.ROOT)):base.sha(p) for p in files} != hashes:
        raise RuntimeError("An input source changed during the candidate comparison")
    summary = {
        "date":"2026-10-04", "evidence_level":"conceptual DC and model Monte Carlo candidate; frozen original RC/junction geometry, not a new extracted physical design",
        "raw_directory":str(work.relative_to(base.ROOT)), "pdk_build":lock["open_pdks_commit"],
        "primitive_commit":lock["primitive_commit"], "pdk_model_sha256":lock["files"]["libs.tech/ngspice/sm141064.ngspice"],
        "source_hashes":hashes, "nominal_ideal_reference":nominal,"nominal_bounded_reference":nominal_reference,
        "changes":{"instances":["X2 (MOUT)","X4 (MREF)"],"old_w_l_um":[10,2],"new_w_l_um":[20,4],
                   "width_over_length":5,"mirror_gate_area_ratio":4,"six_mos_gate_area_um2_old_new":[50,170],
                   "junction_geometry":"unchanged original AD/AS/PD/PS", "wire_rc":"unchanged original 59 R / 43 C"},
        "mc":{"samples_per_population":N,"seed_first":base.SEED_START,"seed_last":base.SEED_START+N-1,
              "seed_method":"same as baseline: one process/sample, setseed then reset then op; PDK agauss draws only",
              "expected_old_new_local_vth_sigma_v":[old_sigma,new_sigma],"expected_local_vth_scale":expected_scale,
              "paired_vth_max_abs_error_v":paired_delta,"populations":{k:base.describe(v) for k,v in populations.items()},
              "comparison":beforeafter},
        "reference_pvt":{"n":len(matrix),"summary":base.describe(matrix),"minimum_case":low,"maximum_case":high,
                         "all_within_five_pct":all(r["absolute_current_budget_pass"] for r in matrix),
                         "all_reference_headrooms_valid":all(r["headroom"]>=1 for r in matrix)},
        "limits":["Conditional finite samples are not manufacturing yield or a guarantee for unobserved draws.",
                  "Candidate RC and junction geometry are intentionally frozen from W10/L2; actual layout, DRC/LVS, extraction and PWM rechecks are mandatory before adoption.",
                  "Synthetic LED remains unmeasured. Measured LED coupling is a separate experiment.",
                  "Total cell area, systematic mismatch gradients, supply noise, reference noise/bandwidth/startup and RC variation are not qualified."]}
    (base.EVIDENCE / "candidate-w20-l4-summary.json").write_text(json.dumps(summary,indent=2)+"\n")
    print(json.dumps({"range_uA":[low["iout"]*1e6,high["iout"]*1e6],
                      "population_summary":{k:{"mean_uA":v["iout"]["mean"]*1e6,"sd_uA":v["iout"]["sample_sd"]*1e6,
                                               "min_uA":v["iout"]["min"]*1e6,"max_uA":v["iout"]["max"]*1e6,
                                               "outside":v["over_absolute_current_budget_count"]} for k,v in summary["mc"]["populations"].items()},
                      "raw":summary["raw_directory"]},indent=2),flush=True)


if __name__ == "__main__":
    main()
