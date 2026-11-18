"""Compare the native fault and receive scores across matched source, load and stimulus."""

import hashlib
import itertools
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EV = ROOT / "evidence/driver-ab-20261118/b_review"
WORK = ROOT / "build/driver-ab-20261118"
OLD = ROOT / "build/driver-pvt-20261117/b/clamp5v_buffer_soft"
FINAL = "merged220c10r260"
matrix = {
    "TT-normal": (OLD / "tt-normal1-s40", WORK / "b" / FINAL / "tt-normal1-s40"),
    "SS-fault": (
        OLD / "ss_hot_low-full-s40",
        WORK / "b" / FINAL / "ss_hot_low-full-s40",
    ),
    "FF-fault": (
        WORK / "b_review/reference/clamp5v_buffer_soft/ff_cold_high-full-s40",
        WORK / "b" / FINAL / "ff_cold_high-full-s40",
    ),
}
fixed_elements = [
    "VIN",
    "RVIN",
    "LVIN",
    "RCVIN",
    "CVIN",
    "VDD",
    "RVDD",
    "LVDD",
    "RCVDD",
    "CVDD",
    "VREF",
    "RREF",
    "VLED",
    "RLEDSRC",
    "VDISABLE",
    "RDISABLE",
    "VD0",
    "RD0",
    "VD1",
    "RD1",
    "XLED",
    "VSENSE",
    "CLED",
    "RPKG",
    "LPKG",
    ".temp",
    ".options",
    "tran",
]


def footprint(path):
    m = json.loads((path / "manifest.json").read_text())
    circuit = (path / "testbench.spice").read_text().splitlines()
    matched = {}
    for part in fixed_elements:
        lines = [line for line in circuit if line.startswith(part + " ")]
        assert len(lines) == 1, (path, part)
        matched[part] = hashlib.sha256(lines[0].encode()).hexdigest()
    for name, digest in m["inputs"].items():
        if name != "route_b.spice":
            matched["input/" + name] = digest
    matched["stimulus.json"] = hashlib.sha256(
        (path / "stimulus.json").read_bytes()
    ).hexdigest()
    matched["sources"] = m["sources"]
    matched["model_sections"] = [line for line in circuit if line.startswith(".lib ")]
    matched["PVT"] = m["pvt"]
    matched["training_and_filter_helper_digests"] = {
        name: info["sha256"]
        for name, info in m["execution_helpers"].items()
        if name.endswith(
            (
                "receiver_equal_latency_v2.py",
                "microled_dynamic_v1/analyze.py",
                "blue_emitter_speed_20261110/analyze.py",
            )
        )
    }
    return matched


def summary():
    out = {}
    for name, (before, after) in matrix.items():
        a = footprint(before)
        b = footprint(after)
        assert a == b, [k for k in a if a[k] != b.get(k)]
        rows = []
        for label, folder in [("reference", before), ("final", after)]:
            file = EV / (label + "-" + name + ".json")
            data = json.loads(file.read_text())
            assert data["case"] == str(folder.relative_to(ROOT))
            r = json.loads((folder / "result.json").read_text())
            f = data["frames"][-1]
            rows.append(
                {
                    "version": r["case"]["variant"],
                    "case": data["case"],
                    "mos": data["mos_count"],
                    "terminal_margin_V": data["worst_terminal"]["terminal_margin_V"],
                    "limiting_MOS": data["worst_terminal"]["instance"],
                    "body_V": data["worst_body"]["body_V"],
                    "errors": f["frozen"]["errors"],
                    "train_errors": f["training_errors"],
                    "amp_uAeq": f["frozen"]["vertical_uAeq"],
                    "timing_UI": f["frozen"]["timing_UI"],
                    "positive_pJ_b": f["total_pJ_bit"]["drawn"],
                    "returned_pJ_b": f["total_pJ_bit"]["returned"],
                    "net_pJ_b": f["total_pJ_bit"]["net"],
                    "last_frame": f["number"],
                    "cap_CIB1": f["CIB1_storage"],
                    "fault": data.get("fault"),
                    "energy_by_port": f["ports_pJ_bit"],
                    "full_RX_train_phase_UI": f["trained"]["delay_UI"],
                    "frozen_phase_UI": f["frozen"]["delay_UI"],
                    "f1_validation_errors": data["frames"][0]["frozen"]["errors"],
                    "steady_state_qualified": r["steady_state_qualified"],
                }
            )
        after_manifest = json.loads((after / "manifest.json").read_text())
        bits = json.loads((after / "stimulus.json").read_text())["bits"]
        falling = sum(i == 1 and j == 0 for i, j in itertools.pairwise(bits))
        if rows[1]["last_frame"] > 1 and bits[-1] == 1 and bits[0] == 0:
            falling += 1
        supply = after_manifest["pvt"]["VDD_V"]
        cib = after_manifest["circuit_change"]["CIB1_fF"]
        expected = falling * cib * 1e-15 * supply**2 / 4096 * 1e12
        out[name] = {
            "ideal_inverter_cap_energy_estimate": {
                "input_falls": falling,
                "VDD_V": supply,
                "CIB1_fF": cib,
                "CV2_per_rise_pJ_bit": expected,
                "scope": "Full-swing charging from VDD; excludes internal short-circuit transitions, other nodes and finite rise time. Not a separately measured energy term.",
            },
            "identical_contract_sha256": a,
            "rows": rows,
            "delta": {
                "positive_pJ_b_by_port": {
                    port: rows[1]["energy_by_port"][port]["drawn"]
                    - rows[0]["energy_by_port"][port]["drawn"]
                    for port in rows[0]["energy_by_port"]
                },
                "amp_uAeq": rows[1]["amp_uAeq"] - rows[0]["amp_uAeq"],
                "timing_ps": (rows[1]["timing_UI"] - rows[0]["timing_UI"])
                * 4096
                / 4736
                / 1.6e9
                * 1e12,
                "positive_pJ_b": rows[1]["positive_pJ_b"] - rows[0]["positive_pJ_b"],
                "positive_percent": 100
                * (rows[1]["positive_pJ_b"] / rows[0]["positive_pJ_b"] - 1),
            },
        }
    (EV / "matched-comparison.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + "\n"
    )
    return out


if __name__ == "__main__":
    summary()
