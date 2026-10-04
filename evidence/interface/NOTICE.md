# Interface source notice

`scripts/interface/buf_2.spice` contains the unmodified `buf_2` subcircuit from
the compiled public `gf180mcu_fd_sc_mcu7t5v0` SPICE library. It retains the
upstream copyright and Apache notice: Copyright 2022 GlobalFoundries PDK Authors.
The complete Apache License 2.0 is preserved in
[the physical-library license](../physical/APACHE-2.0.txt).

The actual compiled SPICE SHA-256 is
`0e126c5e10e45e705a83acfa47f6fd2c4ef0357e99c339dec43cdc16bfb13664`;
the physical PDK lock and interface summary identify the other implemented
model/Liberty inputs. The [upstream source locator](https://github.com/google/globalfoundries-pdk-libs-gf180mcu_fd_sc_mcu7t5v0)
does not imply its current branch equals this frozen compiled package.

Project work independently supplies testbenches, analysis methods and results;
no upstream endorsement is implied. The original project MIT license does not
replace the license of this third-party subcircuit. Measured LED source material
has a separate [dataset notice](../../analog/models/measured-led/NOTICE.md).
