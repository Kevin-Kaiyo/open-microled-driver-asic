# 新实验报告独立复核：MicroLED 与交付链接

结论：最终渲染的 MicroLED 数值、分层图和眼图与冻结源一致；未发现把代理筛查升级成实测带宽、光学 BER 或新物理实现的表述。全部本地链接与 report-manifest 哈希核对通过，本审计范围内无未解决项。未编辑父任务脚本、报告或 build 数据。

## 已核对

- 九行 TT/SS/FF 主表的错误数、最小有符号裕量、时序、能量及最大体结正偏，与 `microled-summary.json` 在全部显示精度上逐项相等。9/9 基线 gzip SHA-256 与原 v2 receiver 源 SHA-256 重新核对通过。
- TT 200/0 fF 对照及理想 sink 对照的阶段来源正确；电气导电电流排除了外接电容位移电流，旁路阶段分别训练，未把错误数按层相减。
- 使用只拦截 `save()` 的方式调用父 `microled()` 渲染函数，检查两个分层图面板的所有数据数组与 JSON 完全相等；不写父任务文件。眼图每路线 128 个验证符号，横轴 −0.5 至 1.5 symbol UI，按各自冻结相位显示，保留 NRZ/PAM4 不同 UI。两张已保存 PNG 已视觉检查，图例、轴标签和阈值可读。
- 4096/4736=32/37、3.7 Gb/s 线路率、NRZ270.27 ps、PAM4540.54 ps 与 1.28 µs 帧时长一致。能量分母为尝试发送的4096个payload bit，未宣称错误帧为有效交付能效。
- 体结数据正确：TT C约0.858 V，FF C约0.935 V，CAP0 A约0.731 V。正文明确端间压差screen不等于体结/可靠性资格。
- `rd×C≈2.15ns` 被限定为当前静态曲线的局部负载关系，并明确不是载流子寿命测量或电压驱动统一极限。零C、固定光学/RX代理、有限确定性帧、无新布局/PEX边界均保留。

## 审计中发现并反馈

1. “MicroLED全部12点最佳训练裕量为负”须限定为**完整代理阶段**；CAP0 B的electrical/RX-only训练幅度并非负值。父脚本、最终README与HTML均已补充该限定。
2. 从A在CAP0下变差直接归因为“输出振铃”证据不足；父脚本与最终文档已改成“移除外接C不足以解决电路动态与波形问题”，未将具体机理作为已证明因果。
3. 理想sink表的“格式”原为A/C；父脚本与最终文档已映射为NRZ/PAM4，并明确MicroLED角落：TT27°C/3.3V、SS125°C/2.95V、FF−40°C/3.65V，防止误读成VCSEL的不同供电/温度条件。

## 最终链接与交付身份

- 最终HTML共21个唯一相对链接/媒体引用；全部目标存在，无坏HTML锚点。`reproduce.md`已生成并复核可达。
- 最终报告未使用`report-sources`目标，因此不存在该类待检查链接。
- 审计建议已反映在最终README/HTML；全部`report-manifest.json`登记文件重新计算SHA-256，无漂移。
- VCSEL模型、v3和holdout的数值内容由另一独立审计负责；此处只核对其与MicroLED不可直接排名的证据边界。

## 复核方法

Python解析Markdown表并与JSON逐项比较；重新计算源/压缩波形SHA-256；HTMLParser提取href/src并解析本地目标与锚点；拦截父渲染器save检查Matplotlib线数据；读取两张PNG做视觉核查。未重新运行SPICE，未编辑旧MicroLED源码、门槛或证据。

## 最终复核身份

时间：2026-10-27T23:18:16.224583+09:00

- `scripts/three_gbps_experiment/report.py`：`bd57a783fe3cb514a1f99a385648965faa3030373fdc606205da97fc05a48b94`
- `docs/research/three-gbps-experiment-20261027/README.md`：`0319fb9426a1aff08fec960c61a9bf4d5dd8f81d0412482732ed5f3a54b2242d`
- `docs/research/three-gbps-experiment-20261027/index.html`：`1d059654cee1e4cdbf9c3473371365b8b19023c3e142a2a276a43dea474554b3`
- `docs/research/three-gbps-experiment-20261027/reproduce.md`：`3fdc2e1eb89ba1d008d1e098fdcfac5261653578795ddf5459ecd7ebd90bd9e7`
- `evidence/three-gbps-experiment-20261027/report-manifest.json`：`bd9864f701395c3d63fe5f387e4fd2d8afa8f3a39316bf131336e6ba24d7c917`
- `evidence/three-gbps-experiment-20261027/microled-summary.json`：`ad7ec973e87d8642ee6d9cd25c54dd4d5a80f2c670d67e152a4f06f77fa62de6`
- `evidence/three-gbps-experiment-20261027/microled-validation.json`：`d1d0908281c793c899af9a0081bd94b41614ccf2c9c8e0c2fcb542db97566ef6`
- `evidence/three-gbps-experiment-20261027/microled-training-feasibility.json`：`cfed874b09fa0e3f88cf5e802857f625150c33d15ddaf31799abc9d403349bee`
- `docs/research/three-gbps-experiment-20261027/figures/microled-stages.png`：`d82ca694537c204c609d92aafed49de41fcd8e83ba445f870eb41c4ba6241504`
- `docs/research/three-gbps-experiment-20261027/figures/microled-eyes.png`：`4a26b2a3c5bc4012d12e5cf72070bccdc6c49365ef1f7c41747027153feeaa63`
