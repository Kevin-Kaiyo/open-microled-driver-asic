# 单通道 NRZ：慢热接收与快冷端电压修正

日期：2026-10-23。项目定位：实验性研发方法验证与教学。

先读 [中文研究报告](index.html)，再打开 [真实 GDS 分层查看器](layout-viewer.html)。报告按问题、原始失败、修改、物理实现、同条件数据和下一研究方向展开。全部原始波形在 `build/`，紧凑证据在 [`evidence/highspeed-nrz-pvt`](../../../evidence/highspeed-nrz-pvt)。

## 本轮实际改变

- A 电压驱动：保留 6 MOS 及原 VH/VL；DATA 输入增加 GF180 `ppolyf_u_1k_6p0`，W=1 µm、L=48 µm。
- B 电流转向：保留 9 MOS；输入电阻 W=1 µm、L=58 µm；外部 88.386106 kΩ 的 RREF 改接已有固定 3.3 V 的 VDUMMY。该电源仍为理想源，不是本轮实现的稳压器。
- 版图：缩短电阻后的 DI 连接，在电阻与 MOS 区间增加连续 p+ 衬底接触带、接触孔与 VSS 金属，保留电阻四侧接触。最终物理运行是 `build/highspeed-nrz-pvt-layout/final-r4`，最终仿真是 `build/highspeed-nrz-pvt/final-r4`。
- MicroLED 静态模型、动态 C/R/L、20 ps 外部输入、码型、接收代理、阈值、采样训练和余量判据全部保持原条件。

三组联合条件 TT/27°C/3.3 V、SS/125°C/3.0 V、FF/−40°C/3.6 V 下，七档测试速率中共同通过接收与项目端电压筛查的最高点是 A 1 Gb/s、B 0.5 Gb/s。A 的 2 Gb/s 仍失败；本轮通过限制工作速率获得可接受设计点，不能说已解决 2 Gb/s 接收失败。B 的原慢热 0.5 Gb/s 失败已在新 RC 电路中通过。

3.63 V 是项目筛查线，不是晶圆厂对所有端子、脉冲与寿命的可靠性签核。511 位零错误、仿真接收余量、DRC/LVS、光学 BER 和硅片验证分别属于不同证据层级。

## 文件与证据入口

| 内容 | 位置 |
|---|---|
| 最终原理图与选型定义 | [`analog/highspeed_nrz_pvt`](../../../analog/highspeed_nrz_pvt) |
| 独立物理布局定义 | [`layout/highspeed_nrz_pvt`](../../../layout/highspeed_nrz_pvt) |
| 结果主表、数值控制、源身份验证 | [`summary.json`](../../../evidence/highspeed-nrz-pvt/summary.json)、[`validation.json`](../../../evidence/highspeed-nrz-pvt/validation.json) |
| 实际 GDS、DRC/LVS/PEX、开路/短路反例 | [`physical/summary.json`](../../../evidence/highspeed-nrz-pvt/physical/summary.json) |
| 电阻角、DI 电容、衬底线性 R 网络计算 | [`physical/final-metrics.json`](../../../evidence/highspeed-nrz-pvt/physical/final-metrics.json) |
| 原始失败与修复过程 | [`diagnosis.json`](../../../evidence/highspeed-nrz-pvt/diagnosis.json)、[`layout-r1-body-bounce.json`](../../../evidence/highspeed-nrz-pvt/layout-r1-body-bounce.json) |
| 对照阶段 | [2026-10-20 报告](../highspeed-nrz-pex-20261020/index.html) |
| 原始附件、恢复依赖与回执 | [开发交接说明](../../development-handoff.md) |
| 一手资料与支持范围 | [`sources.json`](sources.json) |

## 复现与验证

先按开发交接说明恢复原始附件，并准备锁定的 Python、ngspice、完整 GF180 PDK 和物理工具。仅 `analog/models/pdk-lock.json` 不足以重跑物理流程。`build/layout/venv/bin/python` 要保留虚拟环境路径，不能先解析符号链接成裸解释器。

```sh
# 检查已有归档；这些检查不等于重新跑 EDA
build/layout/venv/bin/python scripts/highspeed_nrz_pvt_layout/validate_delivery.py
build/layout/venv/bin/python scripts/highspeed_nrz_pvt/validate.py \
  --work build/highspeed-nrz-pvt/final-r4

# 重新生成报告图表；先完成上面的验证
build/layout/venv/bin/python scripts/highspeed_nrz_pvt_diagrams.py
build/layout/venv/bin/python scripts/highspeed_nrz_pvt_report/draw_voltage.py
build/layout/venv/bin/python scripts/highspeed_nrz_pvt_report/draw_steering.py
build/layout/venv/bin/python scripts/highspeed_nrz_pvt_report/render_layout.py
build/layout/venv/bin/python scripts/highspeed_nrz_pvt_report/plots.py
build/layout/venv/bin/python scripts/highspeed_nrz_pvt_report/build_report.py
```

新建实验应使用新的目录，步骤见 [`scripts/highspeed_nrz_pvt/README.md`](../../../scripts/highspeed_nrz_pvt/README.md) 与 [`layout/highspeed_nrz_pvt/README.md`](../../../layout/highspeed_nrz_pvt/README.md)。不要覆盖冻结的 `final-r4`，也不要为绕过缓存身份核验而修改旧分析文件。

报告新增 SVG/PNG 由电路连接、实际 GDS 和仿真数据确定性生成。`geometry.json` 保留来源 GDS 哈希，`report-data.json` 固定主表身份。二维图中的颜色用于分层，不表示材料厚度，也不是三维电磁仿真。中文定量图使用上一阶段已归档的 Noto Sans CJK 字体；报告正文优先 PingFang SC。

## 尚待验证

独立电阻角与 MOS 角组合、失配、LED 动态/温度实测、供电扰动、封装和衬底模型、真实稳压器、完整收发链路、pad/ESD、制造规则接受和硅后光学测试均未完成。本轮约 9–11 mV 的快冷端电压筛查余量不能解释为量产可靠性余量。
