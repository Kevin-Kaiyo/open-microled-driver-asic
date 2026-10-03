"""Fetch an immutable, hash-checked public model subset (not a full PDK)."""
from pathlib import Path
import hashlib
import json
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / ".cache/pdk/gf180mcu"


def fetch_models():
    lock = json.loads((ROOT / "analog/models/pdk-lock.json").read_text())
    base = lock["repository"].replace("https://github.com/", "https://raw.githubusercontent.com/")
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    for source, digest in lock["files"].items():
        target = MODEL_DIR / Path(source).name
        if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() == digest:
            continue
        request = urllib.request.Request(f"{base}/{lock['commit']}/{source}", headers={"User-Agent": "open-microled-driver-asic"})
        with urllib.request.urlopen(request, timeout=60) as response:
            data = response.read()
        if hashlib.sha256(data).hexdigest() != digest:
            raise RuntimeError(f"Model SHA256 mismatch: {source}")
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_bytes(data)
        temporary.replace(target)
    return lock


if __name__ == "__main__":
    lock = fetch_models()
    print(f"Verified GF180MCU model subset at {lock['commit']}")
