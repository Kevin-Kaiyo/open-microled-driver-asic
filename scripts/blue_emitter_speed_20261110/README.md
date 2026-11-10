# 固定器件模型的真实扫速

本目录对已有黄色 20 µm MicroLED 模型及 850 nm VCSEL r10 电路执行真实晶体管级扫速。它不把这些模型重新命名为蓝光器件。每个新增速率均重新生成 PWL、终止时刻和最大步长，再运行 ngspice；不压缩历史波形的时间轴。

## 条件

- MicroLED A/B/C 保持原冻结网表、25/100 µA 两电平或 25/50/75/100 µA 四电平、200 fF 假设并联结电容、1 Ω/0.5 nH 封装、200 ps 假设光学时间常数、1 GHz 接收极点。
- VCSEL 保持 r10 网表、原 850 nm L–I–V / 光学图读模型、150 fF、0.5 Ω/0.2 nH、5 GHz 接收极点。
- 4736 位固定 PRBS 派生测试帧，其中 4096 位为独立验证载荷，训练计分位为 [64,512)，验证为 [576,4672)。net / line = 4096/4736。没有实现协议、FEC 或物理 BER 测量。
- 各速率仅以训练段选一次采样延迟，范围 0–8 个线速率 bit UI，步进 1/64 bit UI。NRZ 与 PAM4 的绝对延迟预算和时间余量标准一致。
- 研究筛查要求训练与验证均零错误、最差有符号幅度 ≥7.5 µAeq、单侧时间余量 ≥0.37 bit UI。后者在净 3.2 Gb/s 时恰好为 100 ps。另列原始 100 ps 判据，不能跨速率混用。
- 合并筛查还要求 MOS 端间电压筛查、体结正向电压 ≤0.3 V 及当前模型静态电流范围内。它不是可靠性、PVT 或流片签核。
- 能耗统计全帧 7 个已实例化源端口的正向输出、返能和净能量，分母为 4096 个尝试传送的载荷位。接收失败时不可称为可靠有效数据的 pJ/bit。

## 重现

先按 `docs/research/highspeed-workbench-20261110/reproduce.html` 恢复冻结输入和已有 3.2/16/32 Gb/s 原生锚点。新阶段还读取原 MicroLED B 的 0/10/50/800 fF 原生负载扫描以及 VCSEL `frame-TT-halfstep-r10`。PDK 文件必须匹配清单 SHA-256。

在仓库根目录使用 Python 3.12 环境和 ngspice 47。以下命令顺序执行时最多两路 ngspice。

```sh
build/layout/venv/bin/python scripts/blue_emitter_speed_20261110/sweep.py microled --rates 0.4 0.8 1.6
build/layout/venv/bin/python scripts/blue_emitter_speed_20261110/sweep.py microled --routes C --rates 0.2
build/layout/venv/bin/python scripts/blue_emitter_speed_20261110/sweep.py microled --routes B --rates 0.4 --cap-fF 800
build/layout/venv/bin/python scripts/blue_emitter_speed_20261110/sweep.py microled --routes A --rates 0.8 --steps 80
build/layout/venv/bin/python scripts/blue_emitter_speed_20261110/sweep.py microled --routes B --rates 0.4 --steps 80
build/layout/venv/bin/python scripts/blue_emitter_speed_20261110/sweep.py microled --routes C --rates 0.4 --steps 80
build/layout/venv/bin/python scripts/blue_emitter_speed_20261110/sweep.py vcsel --rates 4.8 6.4 12.8
build/layout/venv/bin/python scripts/blue_emitter_speed_20261110/sweep.py vcsel --rates 4.8 --steps 80
build/layout/venv/bin/python scripts/blue_emitter_speed_20261110/analyze.py --family all
build/layout/venv/bin/python scripts/blue_emitter_speed_20261110/plot.py
```

`sweep.py` 不覆盖未完成目录或既有结果，已有完成点须匹配工况和 gzip SHA-256 后才复用。首次队列中预排的 0.1 Gb/s 点被取消，相关中断记录在 `build/blue-emitter-speed-review-20261110/cancelled-extra-rate-queue/`，未完成点不作为电路失败；被打断的 0.8/1.6 点重新从头求解。

原始波形、网表、日志及分析中间件放在 `build/blue-emitter-speed-review-20261110/`。`evidence/blue-emitter-speed-review-20261110/speed-sweep-all.json` 记录每点的原始文件 SHA-256、能耗、错误数、余量、应力及已测试通过上界。相邻通过/失败点仅定义离散实验边界，不对其间速度插值为产品极限。

`microled/manifest.json` 的旧 `schema`、`created` 和 `assumptions.rates=3.2` 保留了原始冻结输入的来源身份，不表示本轮所有点均运行在 3.2 Gb/s。实际速率、温度、电容和最大步长以每个 `case.json` / `result.json.case` 为准；VCSEL 以该点 `manifest.json.net_Gbps`、`steps_per_UI` 为准。独立的 `speed-sweep-protocol.json` 汇总这一区别、实际点表和复用锚点，不修改正在使用的冻结清单。
