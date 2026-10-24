# 独立HV候选电路

这两份文件记录实际新GDS所对应的独立W/L与连线参考，未填入猜测的junction几何。它们不是独立可用的final PEX deck；正式晶体管验证应使用对应physical-contract冻结的geometry-only/full-RC extraction。

- A：所有六只MOS改06v0，N L0.7µm/P L0.55µm，输入poly电阻8×1µm；最初真实48×1µm候选与8µm前后结果都保留。
- B：四只inverter与两只steering switch为06v0；REF/BASE/TAIL继续03v3；poly58×1µm，RREF仍接固定VDUMMY。
- LED/RX与外部电源名义值没有重新调校。06器件的较弱低压驱动与较大寄生带来带宽代价，不能依据DC或DRC通过宣称原1Gb/s目标通过。

验证状态以 `evidence/highspeed-nrz-robustness/` 与 `evidence/highspeed-nrz-robustness-layout/` 最新明确命名报告为准。候选名称不表示全部组合角均通过，也不表示硅后验证。

`*_selected_geometry.spice` 另外保存实际选定GDS提取的MOS junction面积／周长与连线控制，A的P2/POUT实际宽15.72µm，扩散几何0.44µm。它们包含实际器件几何但刻意去掉显式互连R/C，不能代替full-RC。`selected-source-hashes.json`冻结这两份GEOM文件的SHA256；最终full-RC源身份见 `build/highspeed-nrz-robustness/selected-a8-b58-r4/manifest.json`。
