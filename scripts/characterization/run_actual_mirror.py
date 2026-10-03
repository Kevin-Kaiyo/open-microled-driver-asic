"""Verify actual W20/L4 extracted RC, gated by an explicit expected input hash.

Preserve prior W10/L2 and conceptual W20/L4 evidence. Freeze all mutable circuit,
reference, RTL and replay inputs before simulations; PDK files remain hash-locked.
"""
from dataclasses import replace
from pathlib import Path
import argparse
import itertools
import json
import re
import shutil
import sys
import tempfile

import run_reference_matching as base

PROJECT = base.ROOT
OUTPUT = base.EVIDENCE
ACTUAL_SOURCE = PROJECT / "evidence/layout/pixel_driver_rc.spice"
FROZEN_RC = PROJECT / "scripts/characterization/candidates/pixel_driver_rc_actual_w20_l4.spice"
N = 256


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rc-sha256", required=True, help="Expected hash of the freshly extracted W20/L4 RC file")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-f0-9]{64}", args.rc_sha256) or base.sha(ACTUAL_SOURCE) != args.rc_sha256:
        raise RuntimeError("Actual RC hash does not match the explicitly supplied extraction")
    netlist = ACTUAL_SOURCE.read_text()
    for instance in (2, 4):
        line = next((x for x in netlist.splitlines() if x.startswith(f"X{instance} ")), "")
        if not re.search(r" nfet_06v0 .*w=20u l=4u$", line):
            raise RuntimeError(f"Actual X{instance} is not the expected 20/4 mirror; inspect mapping")
    if "led_k" not in next(x for x in netlist.splitlines() if x.startswith("X2 ")):
        raise RuntimeError("X2 is no longer MOUT; update measurement mapping explicitly")
    if next(x for x in netlist.splitlines() if x.startswith("X4 ")).count("bias") != 2:
        raise RuntimeError("X4 is no longer diode-connected MREF; update measurement mapping explicitly")
    if FROZEN_RC.exists() and base.sha(FROZEN_RC) != args.rc_sha256:
        raise RuntimeError("Do not overwrite an existing different actual extraction snapshot")
    FROZEN_RC.write_bytes(ACTUAL_SOURCE.read_bytes())
    base.PIXEL = FROZEN_RC
    lock = base.check_models()
    work = Path(tempfile.mkdtemp(prefix="actual-w20-l4-", dir=PROJECT / "build/characterization"))
    frozen = work / "frozen"
    mutable_inputs = [
        "analog/models/microled.spice", "scripts/characterization/external_reference.spice",
        "rtl/pixel_pwm.v", "sim/rtl/tb_pixel_pwm.v", "scripts/run_phase1.py", "scripts/fetch_models.py",
        "layout/pdk-lock.json", "evidence/characterization/reference-matching-summary.json",
        "evidence/characterization/candidate-w20-l4-summary.json",
    ]
    hashes = {}
    for name in mutable_inputs:
        source = PROJECT / name
        destination = frozen / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        hashes[name] = base.sha(destination)
    copies = [frozen / name for name in mutable_inputs]
    original_summary = json.loads((frozen / "evidence/characterization/reference-matching-summary.json").read_text())
    conceptual_summary = json.loads((frozen / "evidence/characterization/candidate-w20-l4-summary.json").read_text())
    # case_prefix and pulse_check resolve their LED and replay modules under ROOT.
    base.ROOT = frozen
    base.REFERENCE = frozen / "scripts/characterization/external_reference.spice"
    source_scripts = [Path(__file__).resolve(), Path(base.__file__).resolve(), FROZEN_RC]
    for path in source_scripts:
        hashes[str(path.relative_to(PROJECT))] = base.sha(path)
    nominal = base.op(base.Condition(), work / "nominal_ideal")
    nominal_reference = base.op(base.Condition(reference="bounded"), work / "nominal_bounded")
    populations = {}
    for name, c in {
        "local_only": base.Condition(local_mismatch=1),
        "global_and_local": base.Condition(library="statistical", global_variation=1, local_mismatch=1),
        "reference_nominal_and_global_local": base.Condition(library="statistical", global_variation=1, local_mismatch=1, reference="bounded"),
    }.items():
        print(f"Actual 20/4 MC {name}: {N}", flush=True)
        rows = [base.op(c,work/name/f"sample_{n:04d}",base.SEED_START+n) for n in range(N)]
        populations[name] = rows
        base.save_csv(OUTPUT / f"actual-w20-l4-mc-{name}.csv", rows)
    print("Actual 20/4 fixed-corner/reference matrix: 1080", flush=True)
    matrix = []
    for n,(corner,temp,vl,vs,gain,tc,line) in enumerate(itertools.product(
        ("typical","ff","ss","fs","sf"), (0,27,85), (2.97,3.3,3.63), (4.5,5,5.5),
        (-base.CAL_BOUND,base.CAL_BOUND),(-base.TC_BOUND_PPM,base.TC_BOUND_PPM),(-base.LINE_BOUND_PPM_V,base.LINE_BOUND_PPM_V))):
        c = base.Condition(library=corner,temperature_c=temp,logic_v=vl,led_supply_v=vs,reference="bounded",
                           calibration_error=gain,tc_ppm=tc,line_ppm_v=line)
        matrix.append(base.op(c,work/"reference_pvt"/f"case_{n:04d}"))
    base.save_csv(OUTPUT / "actual-w20-l4-reference-pvt.csv", matrix)
    low, high = min(matrix,key=lambda r:r["iout"]), max(matrix,key=lambda r:r["iout"])
    for name,row in (("conditional_low",low),("conditional_high",high)):
        print(f"Actual 20/4 MC {name}: {N}",flush=True)
        c = replace(base.Condition(**{k:row[k] for k in base.Condition.__dataclass_fields__}),local_mismatch=1)
        rows = [base.op(c,work/name/f"sample_{n:04d}",base.SEED_START+n) for n in range(N)]
        populations[name] = rows
        base.save_csv(OUTPUT / f"actual-w20-l4-mc-{name}.csv",rows)
    binary = work / "pixel_pwm.vvp"
    base.run_command(["iverilog","-g2012","-Wall","-s","tb_pixel_pwm","-o",binary,
                      frozen/"rtl/pixel_pwm.v",frozen/"sim/rtl/tb_pixel_pwm.v"],work,"rtl-compile.log")
    pulses = []
    for name,row in (("nominal",nominal_reference),("low",low),("high",high)):
        c = base.Condition(**{k:row[k] for k in base.Condition.__dataclass_fields__})
        for step in (50e-9,10e-9):
            print(f"Actual 20/4 RTL pulse {name}: maxstep {step:g}s",flush=True)
            pulses.append(dict(case=name,**base.pulse_check(c,work/"pulses"/f"{name}_{step:g}",binary,row["iout"],step)))
    # Check frozen inputs, not mutable project paths: all simulations used copies.
    after = {str(p.relative_to(frozen)):base.sha(p) for p in copies}
    after.update({str(p.relative_to(PROJECT)):base.sha(p) for p in source_scripts})
    if hashes != after:
        raise RuntimeError("A frozen input changed during the actual extraction check")
    for name, expected in lock["files"].items():
        if base.sha(base.PDK/name) != expected:
            raise RuntimeError(f"PDK input changed during the actual extraction check: {name}")
    summary = {
        "date":"2026-10-04", "evidence_level":"actual W20/L4 extracted RC; conditional model MC, bounded external reference, actual RTL pulse replay; no manufacturing qualification",
        "raw_directory":str(work.relative_to(PROJECT)), "snapshot_directory":str(frozen.relative_to(PROJECT)),
        "actual_rc_sha256":args.rc_sha256,"source_hashes":hashes,"pdk_build":lock["open_pdks_commit"],
        "primitive_commit":lock["primitive_commit"],"pdk_model_sha256":lock["files"]["libs.tech/ngspice/sm141064.ngspice"],
        "rc_count":{"R":len(re.findall(r"^R\d+ ",netlist,re.M)),"C":len(re.findall(r"^C\d+ ",netlist,re.M))},
        "tools":{"ngspice":base.run_command(["ngspice","--version"],work,"ngspice-version.log"),"python":sys.version},
        "candidate_targets":original_summary["candidate_targets"],"reference_specification":original_summary["reference_specification"],
        "nominal_ideal_reference":nominal,"nominal_bounded_reference":nominal_reference,
        "mc":{"samples_per_population":N,"seed_first":base.SEED_START,"seed_last":base.SEED_START+N-1,
              "seed_method":"Same PDK recipe as historical baseline: one process/sample; setseed then reset then op; no random reference error distribution invented.",
              "populations":{k:base.describe(v) for k,v in populations.items()}},
        "reference_pvt":{"n":len(matrix),"summary":base.describe(matrix),"minimum_case":low,"maximum_case":high,
                         "all_within_five_pct":all(r["absolute_current_budget_pass"] for r in matrix),
                         "all_reference_headrooms_valid":all(r["headroom"]>=1 for r in matrix)},
        "lowest_code_pulses":pulses,
        "comparison_to_conceptual_w20_l4":{name:{"mean_iout_change_a":base.describe(rows)["iout"]["mean"]-conceptual_summary["mc"]["populations"][name]["iout"]["mean"],
                                               "iout_sd_ratio":base.describe(rows)["iout"]["sample_sd"]/conceptual_summary["mc"]["populations"][name]["iout"]["sample_sd"]} for name,rows in populations.items()},
        "limits":["Only the specified finite conditional populations were sampled; pass fractions are not manufacturing yield.",
                  "Synthetic LED electrical and temperature behavior remains assumed; measured LED static coupling is separate.",
                  "Reference is a candidate calibrated external-source specification, not an on-chip generator or selected part.",
                  "No RC process corners, systematic mismatch gradients, reference noise/bandwidth/startup, pad/ESD, silicon or optical validation.",
                  "Three deterministic pulse conditions do not constitute an MC pulse-area/yield study."]}
    (OUTPUT / "actual-w20-l4-summary.json").write_text(json.dumps(summary,indent=2)+"\n")
    print(json.dumps({"rc_sha256":args.rc_sha256,"pvt_range_uA":[low["iout"]*1e6,high["iout"]*1e6],
                      "mc_outside":{k:base.describe(v)["over_absolute_current_budget_count"] for k,v in populations.items()},
                      "pulse_max_abs_error_pct":max(p["max_abs_area_error_pct"] for p in pulses),
                      "raw":str(work.relative_to(PROJECT))},indent=2),flush=True)


if __name__ == "__main__":
    main()
