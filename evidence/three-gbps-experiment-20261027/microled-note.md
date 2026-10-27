# MicroLED 单通道净 3.2 Gb/s：原理级分层诊断

证据层级：新 SCHEM ngspice 仿真与离线接收代理；没有新增布局、DRC/LVS/PEX、硅片或光学测量。

## 冻结定义

- 帧效率 4096/4736 = 32/37；净 3.2 Gb/s、线路 3.7 Gb/s；A/B NRZ 为 3.7 GBd，C PAM4 为 1.85 GBd。
- 保留原 TT 校准参数、静态 LED PWL、200 fF、1 Ω/0.5 nH 封装、20 ps 数据边沿和全部七端口计能。
- 接收机保持 v2：0–8 ns、5 ps 网格，只在训练区选延迟；固定 7.5 µA 与 100 ps 门槛。各隔离阶段分别训练，不能把多个阶段的结果串接成已实现链路。
- 电气层使用 LED conduction current，排除外接电容位移电流；光学代理为 200 ps 一阶极点，RX 为 1 GHz 一阶极点。所有光学/RX 输出仍是等效电流，非测得光功率。

## 原条件角落结果

| 路线/角落 | 错误 bit / 4096 | 最小判决裕量 µA | 最小时序裕量 ps | 七端口正向 pJ/net-bit | 电压 screen |
|---|---:|---:|---:|---:|---|
| A/typical | 844 | -38.842 | 0.000 | 0.525627 | True |
| B/typical | 1440 | -29.041 | 0.000 | 0.501387 | True |
| C/typical | 1399 | -36.790 | 0.000 | 0.744521 | True |
| A/ss | 2055 | -47.744 | 0.000 | 0.362657 | True |
| B/ss | 1884 | -34.551 | 0.000 | 0.435358 | True |
| C/ss | 1678 | -52.148 | 0.000 | 0.629781 | True |
| A/ff | 925 | -44.400 | 0.000 | 0.787206 | True |
| B/ff | 1389 | -27.865 | 0.000 | 0.555909 | True |
| C/ff | 1403 | -37.321 | 0.000 | 0.841079 | True |

能量是失败工作点的电气计能，不是合格 3.2 Gb/s 链路能效；未计源 IC 内耗、RX、时钟、主机。完整七端口分项、返回能量、body-forward 峰值见 JSON。

## TT 分层与零电容对照

| 条件 | 电气错误 / 裕量 µA | 仅光学错误 / 裕量 µA | 仅 RX 错误 / 裕量 µA | 完整代理错误 / 裕量 µA |
|---|---:|---:|---:|---:|
| BASE-TT-A-3p2G | 1205 / -38.425 | 953 / -38.663 | 1158 / -38.635 | 844 / -38.842 |
| BASE-TT-B-3p2G | 1045 / -18.384 | 1435 / -27.192 | 1404 / -26.020 | 1440 / -29.041 |
| BASE-TT-C-3p2G | 1281 / -31.842 | 1359 / -35.547 | 1347 / -34.794 | 1399 / -36.790 |
| CAP0-TT-A-3p2G | 597 / -41.491 | 1335 / -39.593 | 1328 / -39.447 | 1288 / -40.050 |
| CAP0-TT-B-3p2G | 0 / 34.471 | 0 / 5.675 | 0 / 11.596 | 773 / -13.190 |
| CAP0-TT-C-3p2G | 114 / -6.379 | 465 / -7.705 | 466 / -5.446 | 756 / -12.615 |

CAP0 只移除外接 200 fF，不改变静态 I–V、驱动参数或接收判据。它是负载动态的反事实隔离，不能充当真实 LED 产品假设。

## 独立理想源对照

| 输入/负载 | 格式 | 电气错误 | 完整代理错误 | 完整裕量 µA / 时序 ps |
|---|---|---:|---:|---:|
| 理想 conduction 电流 | NRZ | 0 | 0 | 0.496 / 25.953 |
| ngspice 理想 sink，C=200 fF | A | 863 | 1158 | -23.520 / 0.000 |
| ngspice 理想 sink，C=0 fF | A | 0 | 0 | 0.492 / 25.839 |
| 理想 conduction 电流 | PAM4 | 0 | 215 | -1.559 / 0.000 |
| ngspice 理想 sink，C=200 fF | C | 1199 | 1377 | -41.200 / 0.000 |
| ngspice 理想 sink，C=0 fF | C | 0 | 232 | -1.587 / 0.000 |

理想源不是某个真实拓扑的严格性能上界；它只是 25/100 µA NRZ 或 25/50/75/100 µA PAM4、20 ps 边沿在既有代理中的参考点。预加重/均衡可能改变输入形状，必须另立电流/能量/接收预算验证。

## 校准、数值与局限

- 新增 16 个 TT DC 检查；相同路线/电平的 200 fF 与 0 fF DC 电流最大差为 0 µA。未进行按速率重新调参。
- 理想源时间网格从 5 ps 收紧到 2.5/1.25 ps；完整代理的 NRZ 错误保持 0，PAM4 保持 215。最细网格 NRZ 裕量约 0.499 µA、26.06 ps；PAM4 约 −1.555 µA、0 ps。
- 晶体管 max-step 从 symbol/40 收紧到 symbol/80；所有原数值门槛保留，不能用失败结论稳定替代数值完全收敛。

| 路线 | Δ能量 % | Δ裕量 µA | Δ错误 bit | 历史数值门槛全部满足 | 完整 screen 仍失败 |
|---|---:|---:|---:|---|---|
| A | -0.004314 | -0.000182 | 0 | True | True |
| B | -0.001003 | -0.005425 | 0 | True | True |
| C | -0.000076 | -0.000048 | 0 | True | True |

仿真/分析失败：[]；未执行：[]。

静态曲线、C、光学寿命与接收噪声未组成同器件测量闭环。确定性有限帧错误率不是测得 BER；通道、温度、封装、失配、噪声与可靠性尚未完整闭合。

## 重现命令与身份

在仓库根目录执行；已有 case 只复核/读取，不覆盖：

```sh
build/layout/venv/bin/python scripts/three_gbps_experiment/microled_diagnosis.py --phase run --jobs 2
build/layout/venv/bin/python scripts/three_gbps_experiment/microled_validation.py --phase refine --jobs 1
build/layout/venv/bin/python scripts/three_gbps_experiment/microled_diagnosis.py --phase analyze
build/layout/venv/bin/python scripts/three_gbps_experiment/microled_validation.py --phase validate
build/layout/venv/bin/python scripts/three_gbps_experiment/microled_validation.py --phase note
```

- legacy runner SHA-256：`0316afadb96dabc2c7554214bad408779d8f07ea3b430074140899c685a92873`
- v2 receiver SHA-256：`54e016be473be37a32d2da84956009e6cab78942c6206f3f3c16a086d80195e0`
- frozen manifest SHA-256：`580809a8984de15b1c19398a36b91e4f515515bfb2073e77e1241899b9b503b2`
- summary SHA-256：`ad7ec973e87d8642ee6d9cd25c54dd4d5a80f2c670d67e152a4f06f77fa62de6`
- validation SHA-256：`d1d0908281c793c899af9a0081bd94b41614ccf2c9c8e0c2fcb542db97566ef6`
- 所有 deck/result/raw/gzip hashes 见 microled-summary.json；原始波形、完整逐阶段判决和 ngspice log 在 build/three-gbps-experiment-20261027/microled/run-r1/。
