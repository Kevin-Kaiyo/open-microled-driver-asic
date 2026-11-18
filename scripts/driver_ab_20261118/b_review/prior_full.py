"""Run the frozen 44-device B F2 fault test into a new archive directory."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PRIOR = ROOT / "scripts/driver_pvt_20261117/b/run.py"
spec = importlib.util.spec_from_file_location("historical_b", PRIOR)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
runner.BUILD = ROOT / "build/driver-ab-20261118/b_review/reference"
runner.run("clamp5v_buffer_soft", "ff_cold_high", "full")
