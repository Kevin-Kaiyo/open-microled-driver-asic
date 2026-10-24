# 参考／供电模块的物理证据

## 当前：21-MOS 参考与 B 核心真实联通顶层

入口 `nrz-switched-keeper-summary.json`。选定 12-MOS 参考模块包含原
10-MOS 伺服、DISABLE 钳位和受 DISABLE 控制的 KRET 回路；与原 B 的
9 MOS / PDK RIN 经真实 M4/M5 桥连接。外部 1.8 MΩ keeper 接 OUT→KRET，
外部 150 pF 补偿接 IN2→板地。VIN 5 V 与独立逻辑 VDD 不短接。

- 成功模块：`vi-switched-keeper-pg-r1b/`；完整顶层：
  `nrz-switched-keeper-joint-r1/`。20 条网络全部提取，21 MOS、1 个 PDK
  RIN、638 个寄生 R、322 个 C；权威互连 C 为 1.444159 pF。
- 最终 GDS：`363e51112c60692538da2130c99664d22a24c15fa0ca9327c244494938b4065c`。
  fullRC：`925b0e98ede116b7d3dc0c0f326aa1704fd08b84dd8cabe39cf03ae4ac4f3d6a`。
  尺寸 348.99 × 340.06 µm、bounding box 0.118678 mm²，属于实验模块，
  不能称完整芯片面积。
- Magic / KLayout DRC 均 0；native / 回读 / RC-collapse LVS 均唯一匹配。
  123 个原始 manifest 文件复核通过。真实切断 BIAS 桥 6 µm² 后 LVS 拒绝，
  VSET 开路和 VIN/VSS 短路负控也拒绝。C 矩阵最大误差 2.02e-28 F。
- 原 B 与新参考的全部制造多边形保留，11 个非布线层的合并图形严格相等。
  Magic GDS 往返丢失的原 N+ 拐角共 0.0608 µm² 从原 GDS 恢复，原往返文件
  保留；所有最终 DRC/LVS/PEX 都重新读取恢复后的实际 GDS。
- 最大 D/S 有效路径：VIN 17.31 Ω、VSS 37.47 Ω；BIAS 到 gate 最大
  51.68 Ω。VIN / VSS 最大 body 图路径仍为 108.44 / 353.11 Ω，完整保留。
  此 substrate 数值只描述 Magic 导出网络，不是经场解验证的衬底模型。

实际版图图：`visuals/nrz-switched-keeper-joint-r1.png` / `.svg`；旁列旧
19-MOS 图，明确是不同电路，不能把面积变化说成纯布线优化。新 fullRC 已交
电气回归；物理通过不代表电流、启动、AC 或高速接收验收完成。

`nrz-joint-r1c/` 的 20-MOS 持续 keeper 顶层同样物理通过，但实际 fullRC
FF DC 出现 I0 +6.485%、I1 +5.919%，作为失败对照原样保留。
`nrz-joint-attempts.json` 保存本阶段失败与修复原因和原始文件哈希。

## 10-MOS 供电布线单因素对照

入口 `vi-power-summary.json` / `vi-power-comparison.json`。两份真实 GDS 为
`vi-thin-r1b/` 与 `vi-pg-r2d/`；同一 10-MOS 电流伺服、相同器件/位置/
独立 schematic。旧制造图层多边形全部保留，只新增供电金属与 via。
19-MOS 含 LDO 的旧模块属于不同电路，不能把面积差称为纯布局优化。

| 项目 | 10-MOS 薄线 | 10-MOS 加强 PG |
|---|---:|---:|
| VIN 最大 D/S 有效路径 | 88.47 Ω | 17.31 Ω |
| VSS 最大 D/S 有效路径 | 46.34 Ω | 13.17 Ω |
| IOUT 有效路径 | 42.53 Ω | 13.18 Ω |
| VIN 最大 body 路径 | 141.01 Ω | 108.44 Ω |
| VSS 最大 body 路径 | 127.40 Ω | 107.39 Ω |
| 面积 | 39,633.97 µm² | 40,670.00 µm² |
| `.ext` 互连 C 总量 | 1.286594 pF | 1.335923 pF |
| fullRC | 95 R / 92 C | 399 R / 224 C |

新增真实 M5 trunk 宽 6 µm、M4 port feed 宽 1.6 µm、M2 供电支路宽
1 µm，并有真实三排 via。面积 +2.61%、互连 C +3.83%，所有新增铜与
所有体端路径均进入 PEX，没有手改理想短路。两份均通过 Magic / KLayout
DRC、native / GDS-readback / RC-collapse LVS、实际 GDS 开短路负控和
逐文件 SHA 复核。最大 VIN body 路径仍含 102.373 Ω 的 degree-one 分支，
详见 `vi-pg-remaining-body-path.json`；这不能解释为经过场解验证的体电阻。

实际 GDS 等比例对照图：`visuals/vi-power-comparison.svg` / `.png`，
明确标出 VIN、VSS、VSET、IOUT/BIAS 和新增 trunk，已视觉检查。
`vi-power-attempts.json` 记录保留的 DRC、GDS port 恢复及原打印舍入阈值失败。
新增本地 C 审计按 native SPICE 每个原打印 token 的半末位精度检查舍入；
权威 `.ext` / assembled RC 矩阵的 1e-27 F 约束不变。

PG fullRC：`vi-pg-r2d/V/full-rc/nrz_vi_reference_rc.spice`，端口顺序
`VIN VSS VSET SENSE IOUT IPB IN2 ICTRL`。电气代理已收到此文件。
该 10-MOS 对照只用于供电布线单因素判断；新增 clamp / switched keeper
已另建以上 12-MOS 模块及 21-MOS 顶层，不能混用其 RC 或面积。

NRZ 的新 **19-MOS** 模块已经完成实际公开 GF180MCU D 版图、两套 DRC、
LVS、GDS 回读与完整 RC；电气性能需以 `evidence/nrz-reference-v2/` 的
同负载回归为准。物理通过不建立稳压、时序或可靠性通过。

## NRZ：电流伺服与稳压组合模块

- 输入：`layout/reference_v2/nrz-selected.json` 独立物理连接表，及
  `layout/reference_v2/nrz_bias_power-reference.spice` 独立电气参考。
- 结果入口：`nrz-summary.json`；完整小型成功证据：`nrz-r1/`。
- 实际版图尺寸：383.40 × 200.78 µm；面积 76,979.052 µm²。
- Magic / 独立 KLayout DRC 均 0；native、GDS 回读、full-RC collapse
  三次 LVS 均唯一匹配。19 MOS 的 W/L/AD/AS/PD/PS 与实际 GDS polygon
  一致，06v0 Dualgate mask 被独立核对。
- 全部 17 条网络抽取为 188 R、176 C，完整保留供电与体端路径。
  `.ext` 权威 C 总量 2.34895591366 pF；collapsed C matrix 最大误差
  8.08e-28 F。原 native 导出也保留，没有把 native C 重计数问题掩盖。
- 真实 GDS 中切断 VSET gate 和短接 VIN/VSS 后，LVS 两项均拒绝。
  它们仍可 DRC 通过，说明 DRC 不能替代连通性验证。
- `nrz-r1-validation.json` 独立只读复算 119 项 manifest 文件、完整 LVS
  日志、DRC XML、实际 mask 与负控差异。
- `nrz-r1-network-audit.json` 对所有 R 网络独立节点分析，确认每个
  MOS 端口连通。最远 VIN/VSS 端口有效电阻为 182.8614 / 171.4712 Ω；
  这是宽松教学布局的真实模型代价，电气仿真保留它们。分支电阻之和不是
  端到端有效电阻，substrate 结果只解释 Magic 导出图。
- `visuals/N-layout.svg` / `.png` 直接绘制真实 GDS，保持 XY 等比例；
  已进行视觉检查，未用示意矩形替代器件几何。

端口顺序：`VIN VSS VSET SENSE IOUT REGFB VREG IPB IN2 ICTRL LPB LN2 LCTRL`。
子电路名：`nrz_bias_power`。审计后 full-RC 是
`nrz-r1/N/full-rc/nrz_bias_power_rc.spice`，旁边保留 GEO、CAP、RCLUMP
控制与未修正 native 输出。

## 实现边界

旧 `hv-r2/B` 核心保持原物理身份。独立模块证据的模块间连接原为外部假设；
上方 21-MOS 顶层已增加实际 M4/M5 连线并整体提取。
精密 VSET、RSET、RBIAS、反馈分压、补偿与去耦属于明确外部器件，
不计入此 GDS 或片内 PEX。没有 pad、ESD、package EM、silicon 或光学结果。

## 复现

```sh
build/layout/venv/bin/python scripts/reference_v2_layout/run.py --spec layout/reference_v2/nrz-selected.json --run nrz-reproduction
build/layout/venv/bin/python scripts/reference_v2_layout/validate.py --run build/reference-v2-layout/nrz-reproduction --out build/reference-v2-layout/nrz-reproduction-validation.json
```

运行使用 `layout/pdk-lock.json` 锁定的完整物理 PDK 和本地 Magic/Netgen，
独立 KLayout DRC 通过现有 `asic` Lima 容器执行；旧证据不覆盖。
