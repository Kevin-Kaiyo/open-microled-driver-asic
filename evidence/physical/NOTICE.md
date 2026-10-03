# Third-party physical-library notice

Copyright 2022 GlobalFoundries PDK Authors.

The routed digital GDS in `digital/gds/pixel_pwm.gds` includes cells from the
public `gf180mcu_fd_sc_mcu7t5v0` standard-cell library. Its library material is
licensed under the Apache License, Version 2.0. A complete, unmodified copy of
that license is included in [APACHE-2.0.txt](APACHE-2.0.txt). The project MIT
license does not replace the license of these embedded third-party cells.

Primary source and license:

- [Public standard-cell library](https://github.com/google/globalfoundries-pdk-libs-gf180mcu_fd_sc_mcu7t5v0).
- [Upstream license](https://github.com/google/globalfoundries-pdk-libs-gf180mcu_fd_sc_mcu7t5v0/blob/main/LICENSE), retrieved 2026-10-04. SHA-256: `cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30`.
- Copyright and Apache notice were also verified in the actual compiled library's `libs.ref/gf180mcu_fd_sc_mcu7t5v0/verilog/gf180mcu_fd_sc_mcu7t5v0.v` header.

The implemented library, rule-deck and technology inputs are identified by the
708 file hashes in [the physical PDK lock](../../scripts/physical/pdk-lock.json).
The compiled PDK's `SOURCES` records open_pdks build
`54435919abffb937387ec956209f9cf5fd2dfbee`; this is a build identifier, not a
claim that the upstream library's current branch was the implemented revision.

Project changes consist of independent PWM RTL, synthesis choices, floorplan,
cell placement, clock-tree construction, routing, verification scripts and
generated top-level views. Embedded standard-cell layouts are retained as
provided by the locked PDK. No upstream endorsement or fabrication acceptance
is implied. The analog macro is independently assembled from public-PDK MOS
parameterized cells; its separate model and physical input notices remain in
[analog model provenance](../../analog/models/pdk-lock.json) and
[layout provenance](../../layout/pdk-lock.json).
