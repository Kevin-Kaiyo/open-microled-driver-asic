# 20 µm MicroLED dynamic model and fair driver regression

> **For agentic workers:** Execute the scoped tasks in parallel where independent; preserve existing inputs and review each result before integration.

**Goal:** Constrain the existing yellow20 model using published dynamic data, perform explicit sensitivity where evidence is missing, and compare A/B/C at net3.2Gb/s with the same receiver.

**Architecture:** Preserve the published whole-chain magnitude data and fit a separately labelled frequency-response model with holdout validation. Do not put that whole-chain fit behind an already simulated LED RC or receiver. Actual transistor experiments use the measured static IV with explicitly assumed C and optical response families, frozen A/B/C circuitry and immutable equal-latency-v2 receiver.

**Tech Stack:** Existing ngspice47/GF180 model subset; Python/numpy; an isolated pinned scipy environment if required; original SVG and standard scientific plots; source/compact evidence in Git, raw outputs in versioned Release assets.

**Spec:** User request2026-11-08 and `evidence/microled-dynamic-20261029/response-contract.json`; research protocol `docs/research/microled-device-codesign-20261029/joint-validation-plan.md`.

## Global constraints

- One20µm square yellow sample class; IV/PI/S21 individual pixel identity unknown; no fabricated-device or optical BER claim.
- net3.2Gb/s =4096payload/4736frame; NRZ3.7GBd and PAM4 1.85GBd; fixed stimulus,512training incl64guard,4096validation.
- Fixed receiver1GHz, thresholds62.5µA NRZ and37.5/62.5/87.5µA PAM4; amplitude7.5µA and time100ps screens; original training-grid selection unchanged.
- Source poles, phase, charge and detector calibration remain conditional. C0 and opticaltau0 are ideal diagnostic controls.
- Energy from seven independent source ports over the whole frame; report positive/return/net, divide by4096attemptedpayloadbits. Failure energy is not successful-delivery efficiency.
- Preserve all previous model, simulation, layout and report evidence; unrelated storage migration edits are outside this commit.
- Normal-OP frame is not startup or a complete thermal/reliability regression. No route preselection.

## Review focus

1. Whole-chain S21 reused as a device block would double-count electrical/receiver filtering.
2. Numerical fit residual or DC agreement cannot resolve missing phase/C/lifetime identifiability.
3. Conduction current must exclude explicit displacement C; terminal energy must include all supply current.
4. Same sampling/threshold/latency algorithm and exact frame boundaries must hold for NRZ and PAM4.
5. Raw time refinement, stress and DC checks may fail even when the proxy receiver opens.

## Tasks and checks

- [x] Frequency fit (`scripts/microled_dynamic_v1/fit.py`, new model card/coefficients): source hashes, normalized30MHz, interleaved-frequency and leave-one-bias-out validation, stable/causal assumed family, honest residual/identifiability limits.
- [x] Electrical experiments (`run.py`): frozen input verification, append-only case registry, DC8points plus cap controls, TT C0/10/50/200/800fF ×A/B/C, selected SS/FF and half-step controls; native energy/stress, logs, verified compressed raw.
- [x] Receiver (`analyze.py`): explicit opticaltau0/25/75/200ps families plus fixed1GHzRX; exact/PWL controls and reproduction of the historical200ps baseline; stage isolation and conditional receiver/error/stress pass reasons.
- [x] Report (`report.py` and `docs/research/microled-dynamic-validation-20261108/`): source fit/holdout, actual circuit/charge diagram, capacitance/dynamic sensitivity, same-scale eyes, native port energy and failure interpretation; Chinese from foundation to evidence.
- [x] Independent review and validation: cross-check identities, units, unchanged inputs, selected-step convergence, energy sums and trace-derived margins. Record unresolved failures.
- [ ] Scoped Git backup + raw Release with SHA manifests/readback/restore. Do not include private papers, existing environments/PDK beyond permitted frozen model subset, or unrelated dirty files.
