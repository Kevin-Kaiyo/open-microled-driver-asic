# Project working rules

- Start from a runnable one-pixel path. Advance to layout before expanding array count.
- Explain engineering results in Chinese with English technical terms. Keep source, assumptions, evidence and status in this repository.
- Separate concept, behavioral model, RTL simulation, transistor simulation, synthesis/physical implementation, DRC/LVS/PEX, GDS, silicon and optical measurement. Never upgrade evidence because a neighboring stage passed.
- Use only public sources, public PDKs, appropriately licensed open designs and independent implementation. Record primary-source locators and conditions; do not copy commercial protocols or internal documents.
- Preserve pinned model/dependency versions and source notices. `analog/models/pdk-lock.json` is a model subset, not a complete physical PDK.
- MicroLED parameters are synthetic until fitted to traceable measurements. Average branch current is an electrical brightness proxy, not measured optical output.
- Keep raw generated outputs in `build/`; retain compact, successful evidence and source hashes in `evidence/`. Retain failure logs locally and report the actual blocker.
- Run meaningful checks for timing, integration and transistor behavior. Model/parameter changes require DC calibration and coupled regression. Update docs when assumptions change.
- Preserve existing work. Avoid reset/reclone/force-push and do not commit credentials, proprietary IP or restricted source material.
- Physical flow and MPW claims require the matching full PDK, rule decks, tool versions and actual reports. A simulation does not establish tape-out readiness.
