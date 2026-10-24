# NRZ B reference/power V2

This is an experimental circuit/layout study. Sources, failure controls and evidence levels remain separate. It does not establish optical performance, autonomous power-on reset, silicon reliability, statistical yield or tape-out readiness.

## Selected architecture and frozen contracts

- Original 9-MOS B + real RIN, frozen LED static model/CLED200fF, original0.5Gb/s PRBS/training/RX/62.5uA threshold.
- Real10-MOS06v0 VI servo, real BIAS clamp and conditional OUT keeper switch:21MOS+RIN in the integrated GDS/fullRC.
- External2.5V anchor,200k/50k divider,RSET20k,RBIAS100k,IN2-to-board-ground150pF,RAW5V input0.25ohm/0.5nH,CIN100nF/0.2ohm ESR,RDUMMY50k.
- ExternalRKEEP1.8Mohm fromOUT toKRET. The on-chip06MOS connectsKRET toVSS only whileDISABLE is asserted. GPIO3.3V through100ohm controlsbothclampandkeeper.
- DISABLE must be asserted before supplies, then held until20us after the anchor begins its1us rise. Tested hold conductiveLED<=2uA, release-to-ready<=2us, peak<=125uA. This is a platform sequencing contract, not an autonomousPOR. Wrong early release is a retained terminal-overvoltage failure.
- SelectedRSET initialerror±0.1%,signedlinearTC±25ppm/C;RDUMMY±1%,±100ppm/C. WiderRSET±1%/±100ppm and±5% remain explicit stress/negative controls. GenericlinearTC is not a vendorboxTC guarantee. No perPVT calibration.
- Real all-source instantaneousv*i integration includesVLED,VDD,VRAW,VREF,VDISABLE andDATA. Externalprecision-reference internalIq/upstream losses remain a separate hardware budget.

Actual selected inputs are frozen in `build/nrz-reference-v2/selected-final-r2/inputs`. `manifest.json`, pre-execution `plan-*.json`, per-case deck/result/log, executed-source snapshots, and immediate losslessgzip/SHA records define identity. Public geometry is `analog/nrz_reference_v2/selected_integrated_geometry.spice`; public independent12MOS reference source is `vi_reference_switched_keeper.spice`.

## Running and auditing

Use the project Python environment with numpy; ngspice must be available. Always retain the one-NRZ-process lock `/tmp/open-microled-nrz-ngspice.lock`.

```sh
build/layout/venv/bin/python -B scripts/nrz_reference_v2/test_pipeline.py
build/layout/venv/bin/python -B scripts/nrz_reference_v2/final_v2.py --stage dc
build/layout/venv/bin/python -B scripts/nrz_reference_v2/final_v2.py --stage startup
build/layout/venv/bin/python -B scripts/nrz_reference_v2/final_v2.py --stage slow
build/layout/venv/bin/python -B scripts/nrz_reference_v2/final_v2.py --stage nrz
build/layout/venv/bin/python -B scripts/nrz_reference_v2/audit_final.py --deep
```

Existing completed cases are reused only after exact source/deck/stimulus/candidate identity checks. A mismatch raises rather than overwrites. The original pre-declared plans retain failedcases; do not remove them to improve coverage/passcounts. AC commands are recorded separately in `build/nrz-reference-v2/final-ac-plan.json`; the method is a local two-injection return-ratio estimate, not a full multi-loop Tian implementation. It is checked against the same DC OP and100us long time-domain experiments.

To reproduce one DC point from small restored inputs/metadata without downloading previous waveforms:

```sh
build/layout/venv/bin/python -B scripts/nrz_reference_v2/reproduce.py \
  --source-work build/nrz-reference-v2/selected-final-r2 \
  --out build/nrz-reference-v2/reproduction-smoke-new --smoke-dc
```

This copies inputs/stimulus into a new empty work directory, loads the original executed runner snapshot, rerunsTTbit1, and compares current to the archived original. It does not overwrite original cases or rerunEDA/fullmatrix. A real restore also needs the public source commit, frozenPDK model subset and physical input files; DRC/LVS/GDS evidence requires its matchingfullPDK/tools and is a separate evidence layer.

## Reading results

`summary-verified.json` separates identity/coverage from simulator/analysis failures and from DCcurrenttarget, receiver, devicevoltage, startupcontract and slowresponse failures. DC `combined_screen_passed` in inherited analyzer output is device screening only; it must not be interpreted as25/100uA±5% precision. Always use the explicit current error/target result. Legacy uniform `above_3p63V_screen` is not the06v0 limit: use per-device03v3=3.63V/06v0=6.0V screening and separatelyreportedgatepairs.

Historical19MOS LDO, invalidsingle-injectionAC, compensationcontrols, constantkeeper20MOS PEX and actualcurrenttarget failures remain in their immutable work folders. The final external sequencing contract and selected componenttolerance tier must not be extended to arbitrary supplyordering, full cornercrossproduct, localmismatch, LEDtemperaturevariation or measuredoptical behavior.

## Final closeout

Formalcoverage138/138 (112DC,10NRZ,11startup,5slow), plus7AC conditions. All10NRZ have0/511 observederrors and pass the frozen receiver/model-specific absolutevoltage screens. Four broad-toleranceDCcurrenttarget failures and one early-release startup/absolutevoltage failure remain. The residual-rail restart also exhibits0.746649V PMOSdiffusion-to-nwell forwardbias for a measurableinterval: originalfunctional/absolutevoltage criteria pass, but junctioninjection/latchup/reliability is notclosed. Read`restart-body-review.json`, not only`startup_passed`.

`closeout-index.json` links the deepgzip identity audit, CSVs, tests, powerdiagnostics and fresh-directoryDCreproduction. Actualretainedbuild is3.59785GiB; the lastdeclared tighter numericalcase startedbelow the approved3.5GiBprelaunchguard and itscompressedtrace caused anapproximately100MiB finalovershoot. All evidencewaspreserved andnoadditionalmatrixwasstarted; exactbytes/free-space are recordedin`storage-closeout.json`.
