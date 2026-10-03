"""Independent timing/integration checks for the RTL-to-SPICE boundary."""
from pathlib import Path
import hashlib
import sys
import tempfile
import unittest
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from run_phase1 import average, digital_duty, pwl_points, source_hashes, verify_trace_window


class BridgeTests(unittest.TestCase):
    def test_voltage_ramp_starts_at_actual_rtl_edge(self):
        events = [(0.5e-6, 0), (2.5e-6, 1), (66.5e-6, 0)]
        points = pwl_points(events, stop=100e-6, slew=10e-9)
        self.assertEqual(points[1], (2.5e-6, 0.0))
        self.assertAlmostEqual(points[2][0], 2.51e-6)
        self.assertEqual(points[2][1], 3.3)
        self.assertEqual(points[3], (66.5e-6, 3.3))

    def test_exact_boundary_edges_and_full_on(self):
        self.assertAlmostEqual(digital_duty([(0, 0), (1, 1), (2, 0)], (1, 2)), 1)
        self.assertAlmostEqual(digital_duty([(0, 0), (1, 1), (2, 0)], (0, 2)), 0.5)
        self.assertEqual(digital_duty([(0, 0)], (1, 2)), 0)

    def test_irregular_samples_use_time_weighted_integration(self):
        t = np.array([0, 0.1, 0.2, 0.9, 1.0])
        self.assertAlmostEqual(average(t, 2 * t + 1, (0.15, 0.85)), 2.0)

    def test_missing_interval_fails(self):
        with self.assertRaises(ValueError):
            average(np.array([0, 1]), np.array([0, 0]), (0, 2))

    def test_overlapping_voltage_transitions_fail(self):
        with self.assertRaises(ValueError):
            pwl_points([(0, 0), (1e-6, 1), (1.001e-6, 0)], stop=2e-6)

    def test_trace_timing_drift_is_rejected_even_for_constant_pwm(self):
        verify_trace_window("TRACE first_frame_ns=2500 measure_start_ns=514500 measure_end_ns=1538500")
        with self.assertRaises(ValueError):
            verify_trace_window("TRACE first_frame_ns=2500 measure_start_ns=256000 measure_end_ns=512000")
        with self.assertRaises(ValueError):
            verify_trace_window("TRACE missing")

    def test_provenance_covers_sources_and_ignores_local_metadata(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sources = ("rtl/pixel.v", "sim/rtl/test.v", "analog/driver/pixel.spice",
                       "analog/models/pdk-lock.json", "scripts/run.py", "scripts/bootstrap.sh")
            ignored = ("analog/.DS_Store", "scripts/.DS_Store", "scripts/__pycache__/run.py",
                       "scripts/.cache/run.py", "scripts/.hidden.py", "analog/waveform.dat",
                       "scripts/run.log")
            for name in sources + ignored:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(name)
            self.assertEqual(source_hashes(root), {
                name: hashlib.sha256(name.encode()).hexdigest() for name in sources
            })


if __name__ == "__main__":
    unittest.main()
