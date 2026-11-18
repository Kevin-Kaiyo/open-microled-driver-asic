"""Locate slow-corner F2 timing failures at the frozen F1 phase on native data."""

import argparse
import gzip
import json
from pathlib import Path

import numpy as np
from check import FRAME, OUT, ROOT, UI, cascade, digest


def inspect(case):
    case = case.resolve()
    manifest = json.loads((case / "manifest.json").read_text())
    r = json.loads((case / "result.json").read_text())
    assert r["frames"][-1]["frame"] == 2 and r["case"]["pvt_key"] == "ss_hot_low"
    series = manifest["vectors"]
    with gzip.open(case / "waveform.dat.gz", "rt") as stream:
        native = np.loadtxt(stream, skiprows=1, usecols=(0, series["iled_cond"]))
    t = native[:, 0]
    y = cascade(t, native[:, 1] * 1e6) - 62.5
    line = np.arange(576, 4672)
    frame = r["frames"][-1]
    delay = frame["first_frame_phase_receiver"]["delay_ps"] * 1e-12
    expected = np.asarray(
        json.loads((case / "stimulus.json").read_text())["bits"], dtype=int
    )
    times = FRAME + line * UI + delay
    crossing_idx = np.flatnonzero(np.signbit(y[1:]) != np.signbit(y[:-1]))
    crossings = (
        t[crossing_idx]
        - y[crossing_idx] * np.diff(t)[crossing_idx] / np.diff(y)[crossing_idx]
    )
    direction = np.where(y[crossing_idx + 1] > y[crossing_idx], "rising", "falling")
    pos = np.searchsorted(crossings, times)
    signed_amp = np.interp(times, t, y) * (2 * expected[line] - 1)
    left = (times - crossings[pos - 1]) / UI
    right = (crossings[pos] - times) / UI
    narrow = np.minimum(left, right)
    wrong = signed_amp <= 0
    narrow[wrong] = 0
    fails = narrow < 0.37
    assert abs(narrow.min() - frame["first_frame_phase_receiver"]["timing_UI"]) < 5e-9
    groups = {}
    for direction_key, sign in [("left", left <= right), ("right", left > right)]:
        for edge in ["rising", "falling"]:
            near = direction[pos - 1] if direction_key == "left" else direction[pos]
            use = sign & (near == edge)
            if not use.any():
                continue
            ix = np.flatnonzero(use)[np.argmin(narrow[use])]
            groups[direction_key + "-" + edge] = {
                "all_bits": int(use.sum()),
                "below_0p37UI_bits": int((fails & use).sum()),
                "worst_margin_UI": float(narrow[ix]),
                "worst_frame2_line_bit": int(line[ix]),
                "expected_bit": int(expected[line[ix]]),
                "sequence_3before_self_3after": "".join(
                    map(str, expected[line[ix] - 3 : line[ix] + 4])
                ),
            }
    phases = []
    for ticks in np.arange(-2, 3, dtype=int):
        ts = times + ticks * UI / 64
        pd = np.searchsorted(crossings, ts)
        sample_amp = np.interp(ts, t, y) * (2 * expected[line] - 1)
        w = np.maximum(0, np.minimum(ts - crossings[pd - 1], crossings[pd] - ts)) / UI
        w[sample_amp <= 0] = 0
        phases.append(
            {
                "offset_1_64_UI": int(ticks),
                "min_time_UI": float(w.min()),
                "min_vertical_uAeq": float(sample_amp.min()),
                "bits_below_time_threshold": int((w < 0.37).sum()),
            }
        )
    example_bit = 3511
    relative = np.linspace(-0.85, 0.3, 1601)
    probe = FRAME + example_bit * UI + delay + relative * UI
    idx = int(np.flatnonzero(line == example_bit)[0])
    return {
        "sample_3511": {
            "line": example_bit,
            "expected": int(expected[example_bit]),
            "relative_UI": relative.round(8).tolist(),
            "received_uAeq": (62.5 + np.interp(probe, t, y)).round(7).tolist(),
            "prev_crossing_relative_UI": float(-left[idx]),
        },
        "case": str(case.relative_to(ROOT)),
        "result_sha256": digest(case / "result.json"),
        "raw_sha256": r["raw_sha256"],
        "phase_UI": delay / UI,
        "payload_bits": len(line),
        "amplitude_fail_count": int((signed_amp < 7.5).sum()),
        "timing_fail_count": int(fails.sum()),
        "minimum_left_UI": float(left.min()),
        "minimum_right_UI": float(right.min()),
        "nearest_crossing_by_side": groups,
        "phase_sensitivity": phases,
        "scope": "Phase offsets use validation data as a diagnostic only; only offset zero is scored. Native two-pole receiver, no continued adaptation.",
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("case", type=Path)
    p.add_argument("name")
    a = p.parse_args()
    (OUT / (a.name + ".json")).write_text(json.dumps(inspect(a.case), indent=2) + "\n")
