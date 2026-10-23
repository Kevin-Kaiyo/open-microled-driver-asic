# NRZ transistor-core source and dependency notices

The routing generators, physical assembly, independent schematic derivation,
validation scripts and teaching records in this directory were independently
implemented for Open MicroLED Driver ASIC. Project-authored code is covered by
the repository's MIT LICENSE. This does not replace third-party license terms.

The generated MOS and 6 V high-R poly resistor geometry uses the unchanged public
GF180MCU Magic parameterized cells from the pinned full `gf180mcuD` PDK. The new
DI routing and VSS-connected substrate contact strip are project-authored assembly.
The resistor compact model is referenced from the full PDK and not copied here:

- `open_pdks` commit `54435919abffb937387ec956209f9cf5fd2dfbee`.
- GF180 primitive commit `41918f5a2356b9fb49a897ecc4fb4716b0ab1041`.
- Magic device generator by R. Timothy Edwards, revision header dated 2022-04-25.
- Magic technology file: Copyright (c) 2022 Efabless, Inc.; created for the
  Google / Global Foundries Open PDK project.
- GF180 models and verification sources: Copyright 2022/2023 GlobalFoundries
  PDK Authors; Apache License 2.0. Original notices remain in the full pinned
  PDK, and its model files are included by reference, not relicensed here.

Upstream locators:

- https://github.com/RTimothyEdwards/open_pdks
- https://github.com/google/gf180mcu-pdk
- https://github.com/google/gf180mcu-pdk-libs-gf180mcu_fd_pr
- https://github.com/google/gf180mcu-pdk-libs-gf180mcu_fd_pv
- https://www.apache.org/licenses/LICENSE-2.0

`layout/pdk-lock.json` and the physical result manifest retain exact dependency
hashes and tool versions. A successful educational core DRC/LVS/PEX run does not
constitute foundry qualification, tape-out acceptance or permission to use a
different process configuration.

The incremental research Release includes frozen public model subsets and generated
DRC rule copies required to interpret the archived experiments. Their original
copyright headers are preserved. A copy of Apache License 2.0 accompanies this
notice as `LICENSE-APACHE-2.0.txt`; no complete PDK or environment is redistributed.
