"""Check all matched full B protocols after the specified simulations have finished."""

import argparse
import sys
import time

import check
import compare

STAGE = compare.WORK
FINAL = compare.FINAL
PRED = "merged220c10"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--wait",
        action="store_true",
        help="Poll until all named runs finish, with a finite deadline.",
    )
    parser.add_argument(
        "--reuse-reviewed",
        action="store_true",
        help="Reuse a saved check only when its result and raw identity still match.",
    )
    args = parser.parse_args()
    pending = []
    for name, (before, after) in compare.matrix.items():
        pending += [("reference-" + name, before), ("final-" + name, after)]
    pending.extend(
        [
            ("intermediate-FF-fault", STAGE / "b" / PRED / "ff_cold_high-full-s40"),
            ("intermediate-TT-normal", STAGE / "b" / PRED / "tt-normal1-s40"),
            ("intermediate-SS-fault", STAGE / "b" / PRED / "ss_hot_low-full-s40"),
        ]
    )
    deadline = time.monotonic() + 5400
    while pending:
        for name, folder in pending.copy():
            ev = check.OUT / (name + ".json")
            if not (folder / "result.json").is_file():
                continue
            current = check.json.loads((folder / "result.json").read_text())
            saved = (
                check.json.loads(ev.read_text())
                if args.reuse_reviewed and ev.is_file()
                else {}
            )
            reuse = (
                saved.get("result_sha256") == check.digest(folder / "result.json")
                and saved.get("raw_sha256") == current["raw_sha256"]
                and (folder / "waveform.dat.gz").is_file()
                and "example_rx_window" in saved
            )
            if not reuse:
                print("scoring", name, flush=True)
                result = check.review(folder)
                ev.write_text(
                    check.json.dumps(result, ensure_ascii=False, indent=2) + "\n"
                )
            pending.remove((name, folder))
            print("verified", name, flush=True)
        if pending:
            if not args.wait or time.monotonic() > deadline:
                sys.exit("Missing records: " + ", ".join(n for n, p in pending))
            time.sleep(15)
    compare.summary()


if __name__ == "__main__":
    main()
