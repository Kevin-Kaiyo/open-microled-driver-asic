# Reference and controlled-startup implementation plan

**Goal:** 分别修复PWM参考动态/启动并实现NRZ B实际参考及供电，形成可核查的晶体管和物理证据。

**Architecture:** 既有核心及负载冻结为对照；两个电气分支独立实施，物理分支在候选通过最小诊断后布局，parent整合报告与独立复算。

**Tech Stack:** 固定GF180MCU、ngspice、Magic/Netgen/KLayout、Python、SVG/HTML。

**Spec:** `docs/superpowers/specs/2026-10-24-reference-v2-design.md`。

## 实施与验证

- [x] PWM根因：复现严格startup错误与reference step，定位错误时间和端点；预声明单变量诊断，保留原失败。文件：`scripts/pwm_reference_v2/`、`build/pwm-reference-v2/`、`evidence/pwm-reference-v2/`。
- [x] PWM修订：在`analog/pwm_reference_v2/`实现有明确机理的参考动态/受控启动；固定负载，验证DC/PVT、10%供电阶跃、启动/故障及最小码；关键结果至少两套数值配置对照。
- [x] NRZ B参考/供电：在`analog/nrz_reference_v2/`和`scripts/nrz_reference_v2/`实现晶体管伺服/稳压，保存一次名义校准及供电边界；确定独立RREF/RDUMMY或替代设定电阻的容差/TC、外部基准误差和输出阻抗。
- [x] NRZ B验证：同负载与RX，DC、TT/SS/FF、启动、0.5Gb/s、供电/封装扰动和容差最坏点；能量覆盖全部新增供电，功耗与基线比较；原始结果到`build/nrz-reference-v2/`，紧凑证据到`evidence/nrz-reference-v2/`。
- [x] 物理与接口：电气代理提交冻结SPICE/端口/尺寸；`scripts/reference_v2_layout/`独立生成/核对实际GDS、DRC/LVS/PEX与负控，发布到`evidence/reference-v2-layout/`。明确片内和片外边界，选定新PEX回送两电气分支复验。
- [x] 报告：独立PWM和NRZ中文HTML入口、标准器件原理图、实际GDS图层和同条件波形/指标，结论均有案例及哈希；旧报告保留并加新阶段入口。
- [x] 审计：独立复算电流/电荷/端压/恢复及RX/能量，检查新模块DC/启动、真实物理对应、失败覆盖、图文单位及浏览器显示。
- [x] 备份：审阅并提交公共源/紧凑证据，增量原始数据归档、逐成员SHA与远端回读、小输入新目录恢复；只清理经过验证的本次暂存副本。

## 跨任务接口与重点

- 电气→物理：明确MOS类型/真实W/L、外部R/C清单、端口连接和独立schematic；物理→电气：实际GDS身份、fullRC、提取边界和运行清单。
- 启动允许时序必须记录，不把单独数值补丁或外部FAULT前提包装成自动POR完成。
- 外部精密电压基准误差与片内反馈误差分开；实际供电headroom、输出阻抗和全部新静态功耗必须计入。
- 不为过关更改LED、RX采样器、阈值、码型或积分窗口；不同证据层次分别下结论。
- 本轮属于用户已授权的持续研发。routine工程选择由证据决定，遇到无法在当前条件下完成的实际阻碍如实记录，不反复请求已授予的开发权限。

## 本轮实际边界

PWM 最终15nF为限定27点与3局部AC；复用144点DC需按等效/极值复测边界解读。高速最终21MOS+RIN实际PEX，138个电气案例与7AC；保留4电流精度失败、提前释放过压，以及残余电源重启0.747V体结正向偏置。自主ready/POR、完整外部参考IC、pad/ESD、光学和生产签核仍未完成。所有原候选与失败证据保留。
