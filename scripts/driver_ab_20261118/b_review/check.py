"""Independent native-data scoring of B F2 or F1. Uses two parallel first-order filters."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "evidence/driver-ab-20261118/b_review"
UI = (4096 / 4736) / 1.6e9
FRAME = 4736 * UI


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def cascade(t, current):
    # H(s) = a/(a-b)/(1+as) - b/(a-b)/(1+bs).
    # Integrate each first-order section exactly for linear input on native intervals.
    delta = np.diff(current)
    h = np.diff(t)

    def section(tau):
        x = h / tau
        one_minus_decay = -np.expm1(-x)
        ramp_gain = np.divide(x - one_minus_decay, x)
        tiny = x < 1e-3
        v = x[tiny]
        ramp_gain[tiny] = v * (0.5 + v * (-1 / 6 + v * (1 / 24 - v / 120)))
        out = np.empty_like(current)
        out[0] = current[0]
        increment = delta * ramp_gain
        for i, gain in enumerate(one_minus_decay):
            out[i + 1] = out[i] + gain * (current[i] - out[i]) + increment[i]
        return out

    a, b = 200e-12, 1 / (2 * np.pi * 1e9)
    return (a * section(a) - b * section(b)) / (a - b)


def score(t, signal, times, bits, start, end):
    threshold = 62.5
    distance_v = np.interp(times, t, signal) - threshold
    signed_v = distance_v * (2 * np.asarray(bits, dtype=int) - 1)
    zero = signal - threshold
    edges = np.flatnonzero((zero[:-1] * zero[1:]) < 0)
    crossings = t[edges] + np.diff(t)[edges] * (-zero[edges]) / np.diff(zero)[edges]
    crossings = np.sort(
        np.r_[
            start,
            crossings[(crossings > start) & (crossings < end)],
            t[(zero == 0) & (t > start) & (t < end)],
            end,
        ]
    )
    pos = np.searchsorted(crossings, times)
    left = times - crossings[np.maximum(0, pos - 1)]
    right = crossings[np.minimum(pos, len(crossings) - 1)] - times
    timing = np.where(signed_v > 0, np.maximum(0, np.minimum(left, right)), 0)
    return np.count_nonzero((distance_v >= 0) != bits, axis=-1), signed_v, timing


def train(t, y, bits):
    # Use only the preroll/training samples and the project's fixed 1/64 UI phase grid.
    train_bits = np.arange(64, 512)
    phase_grid = np.arange(513) / 64
    sample_times = (train_bits[None, :] + phase_grid[:, None]) * UI
    k = t < 576 * UI
    errors, heights, widths = score(
        t[k], y[k], sample_times, bits[train_bits], 64 * UI, t[k][-1]
    )
    quality = np.minimum(heights.min(axis=1) / 7.5, widths.min(axis=1) / (0.37 * UI))
    best = np.argmax(quality)
    return float(phase_grid[best]), int(errors[best])


def energy(t, power):
    p, q = power[:-1], power[1:]
    dt = np.diff(t)
    # Correct trapezoidal area on intervals whose sign changes.
    cross = p * q < 0
    correction = (
        dt[cross]
        * np.minimum(abs(p[cross]), abs(q[cross]))
        * np.maximum(abs(p[cross]), abs(q[cross]))
        / (2 * (abs(p[cross]) + abs(q[cross])))
    ).sum()
    positive = np.trapezoid(np.maximum(power, 0), t) - correction
    negative = np.trapezoid(np.maximum(-power, 0), t) - correction
    return np.array([positive, negative, positive - negative])


def review(path):
    path = path.resolve()
    m = json.loads((path / "manifest.json").read_text())
    r = json.loads((path / "result.json").read_text())
    assert r["simulation_ok"] and not r.get("analysis_error")
    names = m["vectors"]
    with gzip.open(path / "waveform.dat.gz", "rt") as stream:
        raw = np.loadtxt(stream, skiprows=1)
    t = raw[:, 0]

    def node(name):
        return raw[:, names[name]] if name != "0" else 0

    assert np.all(np.diff(t) > 0) and np.isclose(t[-1], m["end_s"], rtol=0, atol=1e-14)
    stress = []
    for i, d in enumerate(m["devices"]):
        values = [node(n) for n in d["nodes"]]
        pairs = [
            (float(np.max(abs(values[j] - values[k]))), j, k)
            for j in range(4)
            for k in range(j + 1, 4)
        ]
        peak, j, k = max(pairs)
        body = max(
            0,
            max(
                float(
                    np.max(
                        (values[3] - values[j])
                        * (1 if d["model"].startswith("nfet") else -1)
                    )
                )
                for j in [0, 2]
            ),
        )
        ref = r["stress"][i]
        assert (
            d["instance"] == ref["instance"]
            and abs(peak - ref["peak_pair_V"]) < 1e-5
            and abs(body - ref["body_forward_V"]) < 1e-5
        )
        margin = ref["limit_V"] - peak
        stress.append(
            {
                "instance": d["instance"],
                "nodes": [d["nodes"][j], d["nodes"][k]],
                "peak_V": peak,
                "terminal_margin_V": margin,
                "body_V": body,
            }
        )
    result = {
        "case": str(path.relative_to(ROOT)),
        "result_sha256": digest(path / "result.json"),
        "raw_sha256": r["raw_sha256"],
        "native_points": len(t),
        "mos_count": len(stress),
        "worst_terminal": min(stress, key=lambda v: v["terminal_margin_V"]),
        "worst_body": max(stress, key=lambda v: v["body_V"]),
        "terminal_violations": [s for s in stress if s["terminal_margin_V"] < 0],
        "body_violations": [s for s in stress if s["body_V"] > 0.3],
        "frames": [],
    }
    current = node("iled_cond") * 1e6
    signal = cascade(t, current)
    bits = np.array(json.loads((path / "stimulus.json").read_text())["bits"], dtype=int)
    assert len(bits) == 4736
    for k, frame in enumerate(r["frames"]):
        start, stop = k * FRAME, (k + 1) * FRAME
        mask = (t > start) & (t < stop)
        tt = np.r_[start, t[mask], stop]

        def window(x, start=start, mask=mask, stop=stop):
            return np.r_[np.interp(start, t, x), x[mask], np.interp(stop, t, x)]

        local, y = tt - start, window(signal)
        own_phase, train_errors = train(local, y, bits)
        if k == 0:
            fixed_phase = own_phase
        own = frame["full_receiver"]
        assert (
            abs(own_phase - own["delay_bit_UI"]) < 1e-10
            and train_errors == own["train_errors"]
        )
        phases = {"trained": own_phase, "frozen": fixed_phase}
        checks = {}
        for label, phase in phases.items():
            indices = np.arange(576, 4672)
            times = (indices + phase) * UI
            err, signed, width = score(local, y, times, bits[indices], 0, FRAME)
            fields = {
                "errors": int(err),
                "vertical_uAeq": float(signed.min()),
                "timing_UI": float(width.min() / UI),
                "delay_UI": phase,
            }
            if label == "frozen":
                ref = frame["first_frame_phase_receiver"]
                values = [ref["errors"], ref["amplitude_uAeq"], ref["timing_UI"]]
            else:
                values = [
                    own["errors"],
                    own["worst_signed_margin_uAeq"],
                    own["one_sided_margin_bit_UI"],
                ]
            assert np.allclose(
                [fields["errors"], fields["vertical_uAeq"], fields["timing_UI"]],
                values,
                rtol=0,
                atol=2e-7,
            ), (path, k, label, fields, values)
            checks[label] = fields
        ledger = {
            port: dict(
                zip(
                    ("drawn", "returned", "net"),
                    energy(
                        tt,
                        -window(node(port + "_voltage"))
                        * window(node(port + "_current")),
                    )
                    * 1e12
                    / 4096,
                )
            )
            for port in m["sources"]
        }
        total = np.sum([list(v.values()) for v in ledger.values()], axis=0)
        assert np.allclose(
            total,
            [
                frame["energy_pJ_per_attempted_payload_bit"][name]
                for name in ["positive", "returned", "net"]
            ],
            rtol=1e-9,
            atol=1e-8,
        )
        capacitance = m.get("circuit_change", {}).get("CIB1_fF", 0) * 1e-15
        vi, vf = np.interp([start, stop], t, node("ib1"))
        extra_cap = {
            "C_fF": capacitance * 1e15,
            "initial_V": vi,
            "final_V": vf,
            "delta_pJ": 0.5 * capacitance * (vf**2 - vi**2) * 1e12,
        }
        result["frames"].append(
            dict(
                number=k + 1,
                training_errors=train_errors,
                **checks,
                total_pJ_bit=dict(zip(("drawn", "returned", "net"), total)),
                ports_pJ_bit=ledger,
                CIB1_storage=extra_cap,
            )
        )
    # Sample one fixed payload segment for display only. It uses the same line-bit indices in every case.
    first, count = 1040, 12
    plot_t = (np.arange(count * 48 + 1) / 48 + first) * UI
    frame_phase = (len(r["frames"]) - 1) * FRAME
    result["example_rx_window"] = {
        "line_index_start": first,
        "count": count,
        "steps_per_UI": 48,
        "expected": bits[first : first + count].tolist(),
        "rx_uAeq": np.interp(frame_phase + plot_t, t, signal).round(5).tolist(),
        "current_uA": np.interp(frame_phase + plot_t, t, current).round(5).tolist(),
        "input_V": np.interp(frame_phase + plot_t, t, node("d0")).round(5).tolist(),
    }
    if m["case"]["mode"] == "fault":
        off, on = m["fault"]["assert_s"], m["fault"]["release_s"]
        mask = (t >= off + 20e-9) & (t <= on)
        last = t[(t >= off) & (t < on) & (abs(current) > 0.1)]
        times = np.arange(len(bits) * m["frames"]) * UI + fixed_phase * UI
        use = (times >= on + m["fault"]["edge_s"]) & (times <= t[-1] - 8 * UI)
        _, height, width = score(
            t, signal, times[use], np.tile(bits, m["frames"])[use], 0, t[-1]
        )
        misses = (height < 7.5) | (width < 0.37 * UI)
        last_bad = times[use][misses][-1] if misses.any() else on + m["fault"]["edge_s"]
        recovery = (last_bad + UI - on) * 1e9
        remaining = (times[use][-1] - last_bad) * 1e9
        max_off = float(np.max(abs(current[mask])))
        assert (
            abs(max_off - r["shutdown"]["max_abs_current_uA"]) < 1e-8
            and abs(recovery - r["shutdown"]["recovery_screen"]["upper_bound_ns"])
            < 2e-5
        )
        sample = np.flatnonzero((t >= on) & (t < on + 160e-9))
        ip = int(sample[np.argmax(node("out")[sample])])
        result["fault"] = {
            "off_max_uA": max_off,
            "last_over_0p1uA_ns": (last[-1] - off) * 1e9 if len(last) else 0,
            "recovery_upper_ns": recovery,
            "remaining_ns": remaining,
            "release_peak_OUT": {
                "time_after_ns": (t[ip] - on) * 1e9,
                "nodes": {
                    name: float(node(name)[ip])
                    for name in [
                        "out",
                        "led_a",
                        "led_k",
                        "iso_p",
                        "data_safe",
                        "ib1",
                        "xdrv.bias",
                    ]
                },
            },
        }
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("case", type=Path)
    p.add_argument("--name", required=True)
    args = p.parse_args()
    OUT.mkdir(exist_ok=True, parents=True)
    report = review(args.case)
    (OUT / (args.name + ".json")).write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    )
    print(report["case"], report["native_points"], len(report["frames"]), "checked")
