# r10 实现收尾与工程说明

本文件由完成记录生成；原始网表、仿真结果和分析不覆盖。它是报告编写与跨电脑接续的实现记录，不代替独立审查。

## 当前验证清单

| 检查 | 完成 | 数值联合筛查 |
|---|---|---|
| nominal_TT | 是 | 通过 |
| nominal_SS | 是 | 通过 |
| nominal_FF | 是 | 通过 |
| frame-TT-supply-minus-r10 | 是 | 通过 |
| frame-TT-supply-plus-r10 | 是 | 通过 |
| frame-SS-supply-minus-r10 | 是 | 通过 |
| frame-SS-Rsense-plus-r10 | 是 | 通过 |
| frame-FF-Rsense-minus-r10 | 是 | 通过 |
| frame-TT-supply-minus-ESL0p5n-r10 | 是 | 通过 |
| confirmation_seed_7B43 | 是 | 通过 |
| TT_native_UI_div80 | 是 | 通过 |
| TT_optical_grid1p25ps | 是 | 通过 |
| continuous_TT | 是 | 通过 |
| continuous_SS | 是 | 通过 |
| continuous_FF | 是 | 通过 |

## 修改与边界

- r10 相对 r8 只把激光稳压输出电容从 1 nF 改为 10 nF，激光 Miller 串联电阻从 10 kΩ 改为 100 kΩ；73 个 MOS 连接和尺寸未改变。
- 10 nF 是外部理想去耦假设，ESR 为 0.1 Ω，基线没有 ESL。另做 0.5 nH 控制实验；这不是实际封装或 PCB 提取。缓冲轨仍为 1 nF。
- 数据目标、150 fF VCSEL 电容假设、原光学代理及 5 GHz 接收代理保持不变。0/4096 是短确定性测试观察值，不是实测 BER。
- SS 两条稳压支路工作于 dropout；没有低频向下单位增益交点不代表相位余量足够。旧 AC 助手只枚举向下交越，r10 六曲线在约 8.83–10.45 MHz 还会向上交越；输入电容加载在没有有源反馈的电路里也能产生这一项。
- 因此保留的首个 180+phase 数字只是历史算术量，不能作为真实 return ratio、相位余量或稳定性证据。保留全 1 Hz–1 GHz 复数曲线；这也不等于已经证明高频振荡。r10 当前支持范围仅为完成的有限时域实验，详见 audit-ac-all-crossings.json。

## 尚未闭合的启动应力

正常数据帧的联合通过不等于任意上电时序可用。FF 的 20 ns 同步上电在 50 ps 短窗对照中仍超过 3.63 V 端压筛查线；应保留失败，后续需要电源时序/钳位方案。0.5 µs 短窗用于峰值数值复核，不用于判断几十微秒后的稳态建立。

| 启动案例 | 上升时间 / ns | 窗口 / ns | 最大端压 / V | 超过3.63V / mV |
|---|---|---|---|---|
| startup-FF-60us-r10 | 100 | 60000 | 3.627853040 | 0.000000 |
| startup-FF-fast-r10 | 20 | 60000 | 3.630879282 | 0.879282 |
| startup-FF-peak-fast-r10 | 20 | 500 | 3.630878890 | 0.878890 |
| startup-FF-peak-normal-r10 | 100 | 500 | 3.627852634 | 0.000000 |
| startup-FF-slow-r10 | 1000 | 60000 | 3.626317608 | 0.000000 |
| startup-SS-60us-r10 | 100 | 60000 | 2.969460432 | 0.000000 |
| startup-TT-60us-r10 | 100 | 60000 | 3.299014485 | 0.000000 |

## 能量与电容储能

下面的端口能量只覆盖 4736 bit / 1.28 µs 数据帧，并除以 4096 个尝试净位。启动、预充和发码前等待另记。ΔU 为所列显式电源与补偿电容的终值储能减初值储能：负数表示帧中释放了原有储能。它未覆盖 MOS 内部电荷、负载及封装全部储能，不是完整能量守恒核算，也不能直接修正成光链路能效。

| 案例 / 分析 | E+ / pJ每尝试净位 | 显式 ΔU / pJ每尝试净位 | 单侧时间 / ps | 联合筛查 |
|---|---|---|---|---|
| continuous-FF-r10-restored-frame / continuous-v3-r1 | 12.487286 | -0.021064 | 133.562 | 通过 |
| continuous-SS-r10-restored-frame / continuous-v3-r1 | 9.873779 | -0.005197 | 115.080 | 通过 |
| continuous-TT-r10-restored-frame / continuous-v3-r1 | 11.159363 | -0.040838 | 130.734 | 通过 |
| frame-FF-Rsense-minus-r10 / fixed-v3-r2 | 12.568135 | -0.021076 | 132.339 | 通过 |
| frame-FF-r10 / fixed-v3-r2 | 12.487360 | -0.021065 | 133.562 | 通过 |
| frame-SS-Rsense-plus-r10 / fixed-v3-r2 | 9.811465 | -0.005462 | 113.944 | 通过 |
| frame-SS-r10 / fixed-v3-r2 | 9.873946 | -0.005293 | 115.056 | 通过 |
| frame-SS-supply-minus-r10 / fixed-v3-r2 | 9.810626 | -0.009912 | 112.169 | 通过 |
| frame-TT-halfstep-r10 / fixed-v3-r2 | 11.161924 | -0.038315 | 130.725 | 通过 |
| frame-TT-r10 / fixed-v3-grid1p25 | 11.161997 | -0.038317 | 130.364 | 通过 |
| frame-TT-r10 / fixed-v3-r2 | 11.161997 | -0.038317 | 130.722 | 通过 |
| frame-TT-seed7B43-r10 / fixed-v3-r2 | 11.169341 | -0.038465 | 130.778 | 通过 |
| frame-TT-supply-minus-ESL0p5n-r10 / fixed-v3-r2 | 10.945917 | -0.192506 | 126.590 | 通过 |
| frame-TT-supply-minus-r10 / fixed-v3-r2 | 10.946292 | -0.192475 | 127.071 | 通过 |
| frame-TT-supply-plus-r10 / fixed-v3-r2 | 11.656068 | +0.133898 | 125.359 | 通过 |

对于从零上电后只发送一帧的使用方式，应另加启动及等待的输入能量；连续帧的统计不能替代这一预算。外部基准芯片内部、串行器、时钟和真实光接收器的功耗仍未实现。

## 连续运行恢复

原 continuous-TT-r10 在 360 秒进程上限被中止，日志已接近 61.28 µs 终点；失败记录保留。run_continuous_restored_r10.py 只把运行时限改为 900 秒，电路和求解设置不变。恢复名添加 -restored，使用同一次上电轨迹接续数据，提取前保留 20 ns 状态预历史，不重新建立 DC。

冻结 r10 原 runner 不变；恢复来源见 recovery-runtime-contract.json。loop_ac_r10.py 可重构六条 AC deck 并核对原始复数数据；默认不重跑已有结果。

## 可复现命令

```sh
build/layout/venv/bin/python scripts/vcsel_robustness_20261029/complete_frames_r10.py
build/layout/venv/bin/python scripts/vcsel_robustness_20261029/complete_continuous_r10.py
build/layout/venv/bin/python scripts/vcsel_robustness_20261029/loop_ac_r10.py
build/layout/venv/bin/python scripts/vcsel_robustness_20261029/summarize.py
build/layout/venv/bin/python scripts/vcsel_robustness_20261029/engineer_notes_r10.py
```

在新电脑上需先恢复对应 build 原始输入及锁定的公开 PDK 模型；本文件不下载或更换依赖。上面 continuous 命令复用已完成结果；不覆盖失败 case。
