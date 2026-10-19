# Third-party material in the startup/closure layout

Copyright 2022 GlobalFoundries PDK Authors.

`official_buf_2.gds` and `official_buf_2.spice` contain public GF180MCU
`gf180mcu_fd_sc_mcu7t5v0` standard-cell material. The generated layouts and
extracted views in `evidence/layout-v3/`, `build/layout-v3/`, and
`build/control-v3/physical/final/` can contain the same library material.
This material is licensed under Apache-2.0, not the project's MIT license.
The full license is preserved at
[`evidence/physical/APACHE-2.0.txt`](../../evidence/physical/APACHE-2.0.txt);
[the physical source notice](../../evidence/physical/NOTICE.md) identifies
the upstream library and pinned source records.

The SPICE file is a selected subcircuit from the locked public library, with
unit/model names adapted for the documented simulation flow. This notice
accompanies its retained historical bytes so that existing evidence hashes
are not silently changed. Original model headers remain in the archived
PDK model copies; `layout/pdk-lock.json` and the physical-library lock identify
the actual inputs. No endorsement, foundry acceptance or silicon validation
is implied.
