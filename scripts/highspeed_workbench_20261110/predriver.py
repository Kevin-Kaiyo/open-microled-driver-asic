"""Run an isolated GF180 pre-driver gate-load experiment with fixed inputs."""

import argparse
import csv
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
PDK = ROOT / "build/microled-dynamic-v1/electrical/run-r1/inputs/pdk"
EVIDENCE = ROOT / "evidence/highspeed-workbench-20261110"
REPORT = ROOT / "docs/research/highspeed-workbench-20261110"
MODEL_HASHES = {
    "design.ngspice": "091cb530bf85160a1f07878fb81f789ca367d018991c8ab41a584cd1a85c6692",
    "sm141064.ngspice": "677822db50bf8968f77854bb455006ac5c245deb46ecfc8b352934e752135c46",
}
VDD, EDGE, WARM, COUNT = 3.3, 20e-12, 16, 127


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sequence():
    state = 127
    bits = []
    for _ in range(COUNT):
        bits.append(state & 1)
        state = (state >> 1) | (((state ^ (state >> 1)) & 1) << 6)
    assert state == 127 and sum(bits) == 64
    return np.array([0, 1] * (WARM // 2) + bits)


def pwl(bits, ui):
    points = [f"0 {bits[0]*VDD:.4g}"]
    for i in np.flatnonzero(np.diff(bits)) + 1:
        points.extend((f"{i*ui:.15g} {bits[i-1]*VDD:.4g}",
                       f"{i*ui+EDGE:.15g} {bits[i]*VDD:.4g}"))
    return "PWL(" + " ".join(points) + ")"


def deck(bits, shape, rate, cap, corner, temp, max_step):
    ui = 1e-9 / rate
    if shape == "tapped":
        input_b = ""
        net = "X1 d gb vdd inv\nX2 gb gp vdd inv"
        currents = "i(vsupply) i(vdata)"
        node_b = "v(data)"
    else:
        input_b = f"Vdata_b data_b 0 {pwl(1-bits, ui)}\nRsource_b data_b db 50"
        net = "X1 d np vdd inv\nX2 np gp vdd inv\nX3 db nb vdd inv\nX4 nb gb vdd inv"
        currents = "i(vsupply) i(vdata) i(vdata_b)"
        node_b = "v(data_b)"
    return f"""GF180 pre-driver {shape} {rate} GBd {cap} fF {corner}
.include "../pdk/design.ngspice"
.param sw_stat_global=0 sw_stat_mismatch=0
.lib "../pdk/sm141064.ngspice" {corner}
.temp {temp}
.subckt inv g y vdd
XN y g 0 0 nfet_06v0 w=2.5u l=.7u ad=1.1p as=1.1p pd=5.88u ps=5.88u
XP y g vdd vdd pfet_06v0 w=3.93u l=.55u ad=1.7292p as=1.7292p pd=8.74u ps=8.74u
.ends inv
Vsupply vdd 0 {VDD}
Vdata data 0 {pwl(bits, ui)}
Rsource data d 50
{input_b}
{net}
Cgp gp 0 {cap}f
Cgb gb 0 {cap}f
.options reltol=1e-5 abstol=1e-13 vntol=1e-7 chgtol=1e-16 method=gear maxord=2
.control
set numdgt=15
set wr_singlescale
set wr_vecnames
tran {max_step}p {len(bits)*ui:.15g} 0 {max_step}p
wrdata waveform.dat v(data) {node_b} v(gp) v(gb) {currents}
quit
.endc
.end
"""


def crossings(t, y, threshold):
    indices = np.flatnonzero(np.diff(y >= threshold))
    return t[indices] + ((threshold - y[indices]) *
                         (t[indices+1] - t[indices]) / (y[indices+1] - y[indices]))


def measure(raw, bits, rate):
    ui = 1e-9 / rate
    t, d, db, gp, gb, rail, inp, *inp_b = raw.T
    assert np.isfinite(raw).all() and np.all(np.diff(t) > 0)
    end = len(bits) * ui
    assert abs(t[-1] - end) < 1e-15
    t_center = (np.arange(WARM, len(bits)) + .5) * ui
    gp_center = np.interp(t_center, t, gp)
    gb_center = np.interp(t_center, t, gb)
    high = np.where(bits[WARM:], gp_center, gb_center)
    low = np.where(bits[WARM:], gb_center, gp_center)
    switching_bits = np.flatnonzero(np.diff(bits)) + 1
    switching_bits = switching_bits[switching_bits >= WARM]
    cp, cb = crossings(t, gp, VDD/2), crossings(t, gb, VDD/2)
    p_delays, b_delays, overlap, dead = [], [], [], []
    for i in switching_bits:
        left, right = i * ui, (i+1) * ui
        p = cp[(cp >= left) & (cp < right)]
        b = cb[(cb >= left) & (cb < right)]
        if len(p) == len(b) == 1:
            p_delays.append((p[0]-left)*1e12)
            b_delays.append((b[0]-left)*1e12)
            signed = (b[0] - p[0])*1e12 * (1 if bits[i] else -1)
            overlap.append(max(signed, 0))
            dead.append(max(-signed, 0))
    energy_t = np.r_[WARM*ui, t[(t > WARM*ui) & (t < end)], end]
    input_power = -d*inp - db*inp_b[0] if inp_b else -d*inp
    supply_power = -VDD*rail
    scale = 1e12 / COUNT

    def integral(power):
        return float(np.trapezoid(np.interp(energy_t, t, power), energy_t) * scale)

    return {
        "screen": bool(min(high) >= .8*VDD and max(low) <= .2*VDD
                       and len(p_delays) == len(switching_bits)),
        "rail_center_fail_bits": int(np.count_nonzero((high < .8*VDD) | (low > .2*VDD))),
        "paired_edges": len(p_delays), "expected_edges": len(switching_bits),
        "min_high_V": float(min(high)), "max_low_V": float(max(low)),
        "max_gp_delay_ps": max(p_delays, default=None),
        "max_gb_delay_ps": max(b_delays, default=None),
        "max_skew_ps": max((abs(p-b) for p, b in zip(p_delays, b_delays)), default=None),
        "max_both_above_ps": max(overlap, default=None),
        "max_both_below_ps": max(dead, default=None),
        "rail_net_pJ_per_line_bit": integral(supply_power),
        "input_net_pJ_per_line_bit": integral(input_power),
        "total_net_pJ_per_line_bit": integral(supply_power + input_power),
        "samples": len(t),
    }


def figures(waves, rows):
    plt.rcParams.update({"font.size": 11, "axes.spines.top": False,
                         "axes.spines.right": False, "axes.titleweight": "bold"})
    colors = ["#006e6a", "#aa5b1f", "#6f7987"]
    fig, axs = plt.subplots(2, 2, figsize=(10, 5.5), layout="constrained")
    for ax, (shape, raw) in zip(axs[0], waves.items()):
        ui = 1/3.7
        t = raw[:, 0]*1e9 - 21*ui
        keep = (t >= 0) & (t <= 5*ui)
        for idx, label, color in zip([3, 4, 1], ["GP", "GB", "Data"], colors):
            ax.plot(t[keep], raw[keep, idx], label=label, color=color, lw=1.5 if idx != 1 else 1)
        for n in range(5):
            ax.axvline((n+.5)*ui, color="#b8c6cb", lw=.8, ls=":")
        ax.axhline(VDD/2, color="#a1aab2", lw=.75, ls="--")
        ax.set(xlabel="Relative time (ns)", ylabel="Voltage (V)", title=shape.capitalize())
        ax.legend(loc="upper right", ncols=3, fontsize=9, frameon=False)
    for shape, color in zip(waves, colors):
        selected = sorted((r for r in rows if r["shape"] == shape and
                           r["corner"] == "typical" and r["rate_GBd"] == 3.7 and r["maxstep_ps"] == 2),
                          key=lambda r: r["cap_each_fF"])
        x = [r["cap_each_fF"] for r in selected]
        for col, key in enumerate(("max_skew_ps", "total_net_pJ_per_line_bit")):
            ax = axs[1, col]
            for row, cap in zip(selected, x):
                y = row[key]
                if y is not None:
                    ax.scatter(cap, y, color=color, marker="o" if row["screen"] else "x", zorder=3)
            ax.plot(x, [r[key] for r in selected], color=color, lw=1, label=shape)
    axs[1, 0].set(title="Paired 50% crossings", ylabel="Max skew (ps)", xlabel="Load per gate (fF)")
    axs[1, 1].set(title="Port energy", ylabel="Net pJ / line bit", xlabel="Load per gate (fF)")
    for ax in axs[1]:
        ax.set_xticks([10, 50, 150])
        ax.grid(alpha=.18)
        ax.legend(frameon=False)
    fig.savefig(REPORT / "predriver-waveforms.png", dpi=155)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdk", type=Path, default=PDK)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    if not args.run_id.replace("-", "").isalnum():
        parser.error("--run-id must be alphanumeric with optional hyphens")
    out = ROOT / "build/highspeed-workbench-20261110/predriver" / args.run_id
    for name, expected in MODEL_HASHES.items():
        if sha(args.pdk / name) != expected:
            raise ValueError(f"PDK SHA-256 mismatch for {name}")
    (out / "pdk").mkdir(parents=True)
    for name in MODEL_HASHES:
        shutil.copy2(args.pdk / name, out / "pdk")
    bits = sequence()
    (out / "bits.txt").write_text("".join(map(str, bits)) + "\n")
    rows, waves = [], {}
    cases = [(rate, cap, "typical", 27, 2) for rate in (1, 3.7, 6) for cap in (10, 50, 150)]
    cases += [(3.7, 50, "ss", 125, 2), (3.7, 50, "ff", -40, 2), (3.7, 50, "typical", 27, 1)]
    for shape in ("tapped", "balanced"):
        for rate, cap, corner, temp, step in cases:
            case = out / f"{shape}-{rate}G-{cap}f-{corner}-{step}ps"
            case.mkdir()
            (case / "bench.spice").write_text(deck(bits, shape, rate, cap, corner, temp, step))
            with (case / "ngspice.log").open("w") as log:
                subprocess.run(["ngspice", "-b", "bench.spice"], cwd=case, check=True,
                               stdout=log, stderr=subprocess.STDOUT, timeout=120)
            raw = np.loadtxt(case / "waveform.dat", skiprows=1)
            row = dict(case=case.name, shape=shape, rate_GBd=rate, cap_each_fF=cap,
                       corner=corner, temp_C=temp, maxstep_ps=step, **measure(raw, bits, rate))
            rows.append(row)
            if (rate, cap, corner, step) == (3.7, 50, "typical", 2):
                waves[shape] = raw
            print(case.name, row["screen"], flush=True)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    REPORT.mkdir(parents=True, exist_ok=True)
    with (EVIDENCE / "predriver-metrics.csv").open("w") as file:
        writer = csv.DictWriter(file, rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    metadata = {
        "run": str(out.relative_to(ROOT)), "script_sha256": sha(Path(__file__)),
        "source_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "ngspice": subprocess.check_output(["ngspice", "--version"], text=True).strip(),
        "numpy": np.__version__, "models_sha256": MODEL_HASHES,
        "warmup_bits": WARM, "measured_bits": COUNT, "ideal_input_edge_ps": EDGE*1e12,
        "input_resistance_ohm": 50, "supply_V": VDD, "supply_variation": "none",
        "excluded": ["FPGA PHY", "complement generation", "input receiver", "ESD",
                     "interconnect/package PEX", "switch nonlinearity/Miller effect",
                     "emitter and optical receiver"],
        "energy": "signed net integral of V*I delivered at ideal supply/data sources per measured line bit",
        "raw_files_sha256": {str(p.relative_to(out)): sha(p) for p in sorted(out.rglob("*"))
                             if p.is_file() and p.parent.name != "pdk"},
    }
    (EVIDENCE / "predriver-manifest.json").write_text(json.dumps(metadata, indent=2) + "\n")
    figures(waves, rows)


if __name__ == "__main__":
    main()
