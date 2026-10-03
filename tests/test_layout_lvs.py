"""Regression controls for real Netgen false-positive wording found in review."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/layout"))
from run_layout import verify_lvs_report


class LayoutLvsTests(unittest.TestCase):
    def test_successful_connectivity_and_properties(self):
        verify_lvs_report("Netlists match uniquely.\nFinal result: Circuits match uniquely.\n.\n")

    def test_real_wrong_width_report_is_rejected(self):
        # Observed when XOUT width was changed from 10u to 20u; Netgen exit=0.
        report = ("Netlists match uniquely with property errors.\n"
                  "w circuit1: 1e-05 circuit2: 2e-05 (delta=66.7%, cutoff=1%)\n"
                  "Final result: Circuits match uniquely.\nProperty errors were found.\n")
        with self.assertRaises(ValueError):
            verify_lvs_report(report)

    def test_wrong_connectivity_is_rejected(self):
        with self.assertRaises(ValueError):
            verify_lvs_report("Final result: Netlists do not match.\n")

    def test_incomplete_or_ambiguous_report_is_rejected(self):
        for report in ("Netlists match uniquely.\n", "", "Final result: Circuits match uniquely.\n"*2):
            with self.subTest(report=report), self.assertRaises(ValueError):
                verify_lvs_report(report)


if __name__ == "__main__":
    unittest.main()
