# A lane reproducibility

Run from the repository root. The stage intentionally reads frozen predecessor
templates rather than editing them. Restore prior Release inputs to their original
relative paths first; a Git clone alone does not restore ignored `build/` data.

Required predecessor inputs:

- `build/driver-interface-20261115/MicroLED/A-protected_v3r/inputs/`
- The same folder's `DC-L0`, `DC-L1`, `fault-f2-net1.6-s40`,
  `fault-f2-net1.6-s80`, `continuous-f4-net1.6-s40` manifests, decks and stimulus.
- `build/driver-methods-20261111/A_rcff31p275/execution-sources/legacy_engine.py`.
- Tracked predecessor Python receivers/analysis imported by the scripts.

Do not overwrite an existing case when changing parameters or dependencies.
Existing-case deck/manifest/parameter assertions intentionally reject that action.
Use a new variant name for a different experiment. `toolchain.json` records the
observed ngspice 47 / Python / NumPy environment; use the project interpreter.

Core commands:

```sh
build/layout/venv/bin/python scripts/driver_pvt_20261117/a/run.py dc-grid
build/layout/venv/bin/python scripts/driver_pvt_20261117/a/calibrate.py track
build/layout/venv/bin/python scripts/driver_pvt_20261117/a/calibrate.py tracklong
build/layout/venv/bin/python scripts/driver_pvt_20261117/a/calibrate.py trackwide4
build/layout/venv/bin/python scripts/driver_pvt_20261117/a/calibrate.py trackwide4gm5
build/layout/venv/bin/python scripts/driver_pvt_20261117/a/calibrate.py trackwide4gm5a37
```

Each calibration fits only TT 27°C nominal, rounds the fixed reference-resistor
choice, then applies the same values across the nine declared points. Iteration
decks and failed results remain in `build/driver-pvt-20261117/a/`.

For waveform replay, use `run.py wave` with `--point`, `--variant`, `--rh` and
`--rl` from the exact case manifest or calibration JSON. The original waveform set
has `baseline/SShotlow` and `trackwide4gm5-fixed/{TT,SShotlow,FFcoldhigh}` in
`--mode fault`, 40 steps per line symbol. The targeted predriver variants
`trackwide4gm5pre2-fixed` and `trackwide4gm5buf2-fixed` use the same RH/RL as
trackwide4gm5, with `--mode continuous --frames 1 --point TT`. Both also have the
same nine-point DC regression via `run.py dc-grid --variant ... --rh ... --rl ...`.

The baseline SS fault solver completes but the frozen recovery analyzer cannot
handle an empty threshold-crossing list. Preserve its original result and append:

```sh
build/layout/venv/bin/python scripts/driver_pvt_20261117/a/reanalyze.py build/driver-pvt-20261117/a/baseline/SShotlow-fault-s40
```

This patch keeps the ordinary receiver/training unchanged and treats wrong bits as
zero timing margin. It does not repair the physical receiver failure.

Generate compact evidence and figures after all selected cases finish:

```sh
build/layout/venv/bin/python scripts/driver_pvt_20261117/a/run.py collect
build/layout/venv/bin/python scripts/driver_pvt_20261117/a/summarize.py
build/layout/venv/bin/python scripts/driver_pvt_20261117/a/physical_budget.py
build/layout/venv/bin/python scripts/driver_pvt_20261117/a/compare_buffers.py
build/layout/venv/bin/python scripts/driver_pvt_20261117/a/plot.py
build/layout/venv/bin/python scripts/driver_pvt_20261117/a/edge_plot.py
build/layout/venv/bin/python scripts/driver_pvt_20261117/a/protection_plot.py
build/layout/venv/bin/python scripts/driver_pvt_20261117/a/validate.py --final
```

`matrix.json` records numerical failures and distinguishes transient criteria from
paired ±1% DC checks. `validation.json` is an integrity audit, not a claim that all
circuits pass. No new layout/PEX, measured optical BER, independent new holdout,
or silicon qualification is established by this stage.
