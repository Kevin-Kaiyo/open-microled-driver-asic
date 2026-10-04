# v0.4 electrical evidence

Start with `summary.json` and `manifest.json`; the Chinese interpretation is `docs/research/robustness.md`. Three final batches share exact frozen source identities:

| Group | Transient | Circuit DC | Raw directory |
|---|---:|---:|---|
| probe | 10 | 12 | build/robustness/probe-8p0a15d1 |
| main | 37 | 12 | build/robustness/main-mx5nfi8b |
| boundary | 19 | 4 | build/robustness/boundary-zkivszoz |

Each group also ran one independent synthetic LED calibration. Main has 146 predeclared guards. Boundary numerical completion is not system qualification; measured-static RLED 10kΩ deliberately fails the original full-on ±5% target. Failed development raw remains local and is described in `failure-record.json`.

The post model is the actual joint twelve-MOS selected signal-path extraction, replacing all old buffer/analog/route views. It excludes PG-only capacitance and body/PG series resistance, and explicitly clamps 34 cut neighbors. No complete chip PDN, upstream FF transistor waveform, real reference generator, real LED dynamics or optical result is claimed.

`*-dc.csv` / `*-transients.csv` retain scalar metrics and serialized nested values. `selected_terminal_power_decomposition` splits LED rail into LED-device and LED_K terminals, and reference rail into the behavioral element and BIAS terminal. These are nested accounts, not independent additive loads. `powers_uW` retains the runner energy-key names but its numeric values are energy divided by explicit duration in µW, including separately labeled capacitor storage changes.

Teaching slices are explicitly labeled with window, stride and raw hash in `summary.json`; primary integrals use every saved raw waveform point. All source/deck/waveform hashes are recorded in the group summaries. Long raw data remain in `build/`, with model source notices inherited from their frozen public sources.
