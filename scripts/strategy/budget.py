#!/usr/bin/env python3
"""Recompute illustrative array budgets; never describe them as an array implementation."""
from __future__ import annotations

import csv
import hashlib
import io
import json
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "evidence/strategy"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    area_path = ROOT / "evidence/characterization/actual-w20-l4-area.json"
    load_path = ROOT / "evidence/characterization/measured-load-summary.json"
    area = json.loads(area_path.read_text(), parse_float=Decimal)
    load = json.loads(load_path.read_text(), parse_float=Decimal)
    dbu = area["dbu_um"]
    x0, y0, x1, y1 = area["bbox_dbu"]
    width = Decimal(x1 - x0) * dbu
    height = Decimal(y1 - y0) * dbu
    area_um2 = width * height
    nominal = [r for r in load["dc_results"] if r["group"] == "matrix"
               and r["corner"] == "typical" and r["vled_v"] == 5
               and r["vlogic_v"] == Decimal("3.3") and r["iref_uA"] == 100]
    assert len(nominal) == 1
    n = nominal[0]
    led_full_uW = Decimal(5) * n["current_uA"]
    reference_floor_uW = Decimal("3.3") * Decimal(100)
    full_measured_uW = n["led_rail_power_uW"] + n["logic_rail_power_uW"]
    assert abs(led_full_uW - n["led_rail_power_uW"]) < Decimal("1e-10")
    clock_hz, slots, command_bits = Decimal(1_000_000), Decimal(256), 9
    pwm_hz = clock_hz / slots
    rows = []
    for count in (1, 16, 64, 256):
        packet_bits = 32 + 16 * count
        rows.append({
            "pixels": count,
            "analog_copies_bbox_sum_mm2": area_um2 * count / Decimal(1_000_000),
            "independent_reference_floor_mW": reference_floor_uW * count / Decimal(1000),
            "full_on_analog_plus_LED_mW": full_measured_uW * count / Decimal(1000),
            "single_buffer_bits": command_bits * count,
            "double_buffer_bits": 2 * command_bits * count,
            "raw_60Hz_bps": 60 * command_bits * count,
            "raw_each_PWM_frame_bps": pwm_hz * command_bits * count,
            "proposed_packet_bits": packet_bits,
            "proposed_packet_60Hz_bps": 60 * packet_bits,
            "proposed_packet_each_PWM_frame_bps": pwm_hz * packet_bits,
        })
    key = rows[1]
    assert key["analog_copies_bbox_sum_mm2"] == Decimal("0.0572432")
    assert key["independent_reference_floor_mW"] == Decimal("5.28")
    assert key["raw_60Hz_bps"] == 8640
    assert key["proposed_packet_each_PWM_frame_bps"] == Decimal(1_125_000)
    d1_16_uW = reference_floor_uW * 16 + led_full_uW * 16 / slots
    quarter_16_uW = reference_floor_uW * 16 + led_full_uW * 16 / 4
    budget = {
        "status": "calculated_scenarios_only",
        "date": "2026-10-05",
        "not_array_validation": True,
        "assumptions": {
            "pixel_target_uA": 100, "Vlogic_V": "3.3", "VLED_V": 5,
            "PWM_clock_Hz": 1_000_000, "slots_per_frame": 256,
            "PWM_frame_Hz": str(pwm_hz), "command_bits": command_bits,
            "proposed_packet": "4 byte header/check plus 2 bytes per pixel; not implemented",
            "power": "Freeze each analog/reference copy; ideal static I-V times duty. No true LED dynamic/temperature or shared reference validation.",
            "area": "Sum of separate analog-cell bounding boxes only. Not array bbox, chip die or optical pitch.",
        },
        "source_hashes": {str(p.relative_to(ROOT)): sha(p) for p in
                          (area_path, load_path, ROOT / "rtl/pixel_pwm.v", Path(__file__))},
        "source_nominal": {k: str(n[k]) for k in ("name", "current_uA", "led_v", "led_rail_power_uW", "logic_rail_power_uW")},
        "analog_cell": {"width_um": str(width), "height_um": str(height), "bbox_area_um2": str(area_um2)},
        "rows": [{k: str(v) if isinstance(v, Decimal) else v for k, v in r.items()} for r in rows],
        "additional": {
            "16_pixel_d1_total_estimate_mW": str(d1_16_uW / 1000),
            "16_pixel_d64_total_estimate_mW": str(quarter_16_uW / 1000),
            "16_pixel_hypothetical_one_shared_reference_full_mW": str((reference_floor_uW + led_full_uW * 16) / 1000),
            "16_pixel_hypothetical_one_shared_reference_d1_mW": str((reference_floor_uW + led_full_uW * 16 / slots) / 1000),
            "shared_reference_status": "hypothesis; fanout, startup, accuracy, noise, RC and power not validated",
            "VGA_8bit_60Hz_raw_bps": 640 * 480 * 8 * 60,
            "VGA_RGB_8bits_per_color_60Hz_raw_bps": 640 * 480 * 24 * 60,
            "current_density_20um_square_A_per_cm2": str(Decimal("100e-6") / Decimal("4e-6")),
            "hypothetical_current_density_4um_square_A_per_cm2": str(Decimal("100e-6") / Decimal("1.6e-7")),
            "analog_bbox_to_4um_square_area_ratio": str(area_um2 / 16),
        },
        "exclusions": ["digital power and cell area", "real current-reference generator power/area", "shared bias circuitry",
                       "clock/protocol/register implementation", "pads/ESD/package/board", "power IR/EM and routing spacing",
                       "LED optical power/EQE/thermal behavior", "manufacturing yield and monetary cost"],
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "budget.json").write_text(json.dumps(budget, ensure_ascii=False, indent=2) + "\n")
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    (OUT / "budget.csv").write_text(stream.getvalue())
    print("PASS: exact geometry, power arithmetic and 4x4 bandwidth budgets; scenarios remain unimplemented.")


if __name__ == "__main__":
    main()
