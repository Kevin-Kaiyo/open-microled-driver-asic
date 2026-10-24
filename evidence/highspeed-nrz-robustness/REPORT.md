# NRZ电源、独立电阻角与封装：验证记录

本轮真实改变MOS电压类别并重新生成GDS/DRC/LVS/PEX，MicroLED、RX、固定阈值与训练方法保持冻结。所有通过结论都是声明条件下的离散点；失败和管理中止记录保留。

## 最重要的边界

- 旧03v3电路的9–11mV端压余量不足以覆盖+25/+50mV供电扰动；外源保持3.6V时，VDD/VSS各1Ω+2nH也触发项目端压筛查失败。0/511误码不代替器件筛查。
- 新A采用06v0及8µm输入poly，B将inverter/steering改06v0而保留03v3电流参考/镜像。A48、A8与bodytie真实提取的前后记录均保留；bodytie没有改善已观察到的SS .5Gb/s临界点。
- A .25/.4/.5Gb/s在冻结sampler下不单调：.25可因归一化水平裕量失败，.5可因垂直裕量失败。报告.4Gb/s是选定离散点，不声称连续速率上界。

- A .4Gb/s的独立VLED+50mV或VH/VL共同−50mV在FF仍有timing=.09375UI失败；联合SS负控进一步出现静态high低于RX阈值。因此本轮没有闭合A的完整独立辅助电源包络。

## 执行与判定分开

旧基线有效计划42/42完成：求解/分析失败0，功能筛查失败0，器件筛查失败12。最终有效计划65/65完成：求解/分析失败0，器件筛查失败0，功能筛查失败7（均为保留的A诊断／边界案例）。全部身份审计通过不等于全部电路通过。

## 同速率能量（所有电源＋DATA正向供能）

| 条件 | A .4Gb/s fJ/gross bit | B .4Gb/s fJ/gross bit | 两路筛查均通过 |
|---|---:|---:|---|
|TT|1308.233|1540.521|True|
|SSminus50|986.320|1354.735|True|
|FFplus50|1547.282|1796.334|True|

## 联合低压负控

| 路线/状态 | 值（DC为µA，否则为错误数） | threshold margin | timing UI | 结论 |
|---|---:|---:|---:|---|
|A / 0.4G|256|-0.09019803059363277|0|False|
|A / DC0|16.541|—|—|DC threshold feasible=True|
|A / DC1|57.196|—|—|DC threshold feasible=False|
|B / 0.5G|0|0.16474705119216224|0.2421875|True|
|B / DC0|23.148|—|—|DC threshold feasible=True|
|B / DC1|89.96|—|—|DC threshold feasible=True|

联合负控A为SS125°C、VDD2.95V、VLED4.95V、VH/VL各+50mV；B为同VDD/VLED条件且VDUMMY−50mV。DC high若低于62.5µA，降低数据速率不能解决静态阈值不足。该测试不代表所有独立电源角的穷举。

## 可追溯文件

- 总索引：`evidence/highspeed-nrz-robustness/summary.json` 与 `all-cases.csv`。
- 最终真实full-RC输入：`build/highspeed-nrz-robustness/selected-a8-b58-r4/manifest.json`。
- Sampler证据：`sampler-diagnostic.json`；数值控制：`numerical-audit.json`。
- 电源/回地窗口：`baseline-A-supply-return-window-global.csv`与`final-A-supply-return-window-matched.csv`（同FF3.6V、1Gb/s、同149.040736ns中心），JSON内记录原raw/deck/result SHA与精确器件。
- 已声明矩阵及管理范围调整均保留在每个run的plan/selection/superseded记录；不能把管理中止等同于SPICE数值失败。

03v3保持3.63V六对端压筛查，06v0使用保守6.0V六对筛查，同时单列gate-specific peak。它们不是foundry全可靠性签核；静态LED拟合没有温度模型，动态LED/optical/RX及封装R/L为假设，substrate RC不等于独立验证的3D衬底模型。
