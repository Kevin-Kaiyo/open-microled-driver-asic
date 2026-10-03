"""Paired full-PDK schematic and extracted RC electrical regression.

Reuses the already-tested RTL edge replay and synthetic LED calibration code.
Raw original Phase 1 sources/models are never edited. This is a separate result.
"""
from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import run_phase1 as phase


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdk-root", type=Path, default=ROOT / "build/layout/pdk")
    parser.add_argument("--rc-netlist", type=Path, default=ROOT / "build/layout/work_v2/pixel_driver_rc.spice")
    parser.add_argument("--output", type=Path, default=ROOT / "build/layout/postlayout")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    phase.MODEL_DIR = args.pdk_root.resolve() / "gf180mcuD/libs.tech/ngspice"
    binary = output / "pixel_pwm.vvp"
    phase.command(["iverilog", "-g2012", "-Wall", "-s", "tb_pixel_pwm", "-o", binary,
                   ROOT / "rtl/pixel_pwm.v", ROOT / "sim/rtl/tb_pixel_pwm.v"], output / "rtl-compile.log")
    checked = phase.command(["vvp", binary, f"+OUT={output / 'selfcheck-events.csv'}"], output / "rtl-selfcheck.log")
    if "PASS" not in checked:
        raise RuntimeError("RTL self-check did not pass")
    calibration = phase.calibrate_led(output)
    original_make = phase.make_deck
    variant_netlist = None

    def make_deck(case, folder, events, maxstep=200e-9):
        path = original_make(case, folder, events, maxstep)
        text = path.read_text()
        original_include = next(line for line in text.splitlines() if "analog/driver/pixel_driver.spice" in line)
        text = text.replace(original_include, f'.include "{variant_netlist}"')
        text = text.replace("XPIXEL led_k pwm vlogic bias gate pwm_b pixel_driver",
                            "XPIXEL 0 bias gate pwm pwm_b led_k vlogic pixel_driver_layout")
        # Preserve solver timestamps near sharp RC edges in the exported text.
        text = text.replace("set wr_vecnames", "set numdgt=15\nset wr_vecnames")
        path.write_text(text)
        return path

    phase.make_deck = make_deck
    partials = [dict(name=f"duty_{d:03d}", duty=d) for d in (0, 1, 64, 128, 192, 255, 256)]
    partials += [dict(name="disabled", duty=128, enable=0)]
    partials += [dict(name=f"vf_{vf:.1f}", duty=256, vf_v=vf) for vf in (2.4, 3.2)]
    partials += [dict(name=f"headroom_{v:.1f}", duty=256, supply_v=v) for v in (2.9, 3.0, 3.3)]
    partials += [dict(name=f"corner_{c}", duty=256, corner=c) for c in ("ff", "ss")]
    partials += [dict(name=f"temp_{t}", duty=256, temperature_c=t) for t in (0, 85)]
    defaults = dict(vf_v=2.8, supply_v=5.0, temperature_c=27, corner="typical", enable=1)
    results = {}
    checks = []
    for variant, netlist in (("schematic_full_pdk", ROOT / "layout/pixel_driver_schematic.spice"),
                             ("layout_rc", args.rc_netlist.resolve())):
        variant_netlist = netlist
        results[variant] = {}
        for partial in partials:
            case = defaults | partial
            result, _ = phase.run_case(case, output / variant, binary)
            if variant == "layout_rc" and "on_vds_v" in result:
                result["on_cathode_to_global_ground_v"] = result.pop("on_vds_v")
            results[variant][case["name"]] = result
            print(variant, case["name"], f"{result['average_current_uA']:.6f} uA", flush=True)
    for partial in partials:
        name = partial["name"]
        pre = results["schematic_full_pdk"][name]["average_current_uA"]
        post = results["layout_rc"][name]["average_current_uA"]
        # 1% current-change guard plus 1 nA absolute guard near zero.
        tolerance = max(abs(pre) * 0.01, 0.001)
        checks.append(dict(name=f"paired_current_{name}", pre_uA=pre, post_uA=post,
                           delta_uA=post-pre, tolerance_uA=tolerance,
                           passed=abs(post-pre) <= tolerance))
    for duty in (1, 64):
        case = defaults | dict(name=f"convergence_{duty:03d}", duty=duty)
        result, _ = phase.run_case(case, output / "layout_rc", binary, maxstep=50e-9)
        baseline = results["layout_rc"][f"duty_{duty:03d}"]["average_current_uA"]
        tolerance = max(abs(baseline) * 0.002, 0.001)
        checks.append(dict(name=f"rc_step_convergence_{duty}", baseline_uA=baseline,
                           fine_uA=result["average_current_uA"], tolerance_uA=tolerance,
                           passed=abs(result["average_current_uA"]-baseline) <= tolerance))
    summary = dict(evidence_level="standalone analog cell: Magic DRC, Netgen LVS, Magic RC extraction, paired electrical regression",
                   model_source="locked full gf180mcuD package; not the older Phase 1 model subset",
                   metric_node_notes={"schematic_on_vds_v": "schematic output MOS led_k minus VSS; VSS is testbench ground",
                                      "layout_on_cathode_to_global_ground_v": "external cell pin led_k minus global testbench ground; includes wiring drop and is not internal MOS VDS",
                                      "layout_gate_v": "external gate monitor pin; internal output MOS gate is a separate RC node",
                                      "layout_internal_output_mos_nodes": "this extracted snapshot: led_k.t0 and VSS.t6; actual internal MOS VDS was not recorded"},
                   conditions=dict(defaults, reference_uA=100, logic_supply_V=3.3,
                                   measurement_window_s=phase.WINDOW, measured_frames=4,
                                   coupling="actual RTL edge replay; no analog-to-RTL feedback"),
                   cases_per_variant=len(partials), transistor_runs=2*len(partials)+2,
                   isolated_led_calibrations=calibration,
                   results=results, checks=checks, passed=all(c["passed"] for c in checks))
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    if not summary["passed"]:
        raise RuntimeError("Paired RC regression guard failed; inspect summary.json")
    print(f"PASS {len(checks)} paired/convergence guards; {summary['transistor_runs']} transient runs + 3 DC LED calibrations")


if __name__ == "__main__":
    main()
