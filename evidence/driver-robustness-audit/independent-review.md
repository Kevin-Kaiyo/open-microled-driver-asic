# NRZ robustness 独立技术复核（2026-10-24）

**最终复核结论：已核验最终65个selected结果与计划一一对应，以及报告的数字、对比口径、来源和新旧DRM补正；当前未发现阻断性交付问题。此前列出的final来源与图形provenance两项待补均已关闭。下文保留较早运行中快照，以说明复核时间范围；最终结论见末节。**

本次为只读代码、冻结输入、实际 deck 和结果身份复核；未运行 ngspice，未改写 case、旧分析或冻结输入。复核时 selected 最终矩阵仍在计算，缺失的计划项不作为缺陷，也不据此宣称完整通过。此复核不替代 physical agent 的真实 GDS/DRC/LVS/PEX 复核。

## 结论

当前已完成的 selected case 中，未发现使其既有电路或电气结果失效的阻断性实现错误。现有证据支持以 A 0.4 Gb/s、B 0.5 Gb/s 表述离散验证点；不支持连续最高速率、全部供电组合、可靠性或光学/硅片结论。最终完成状态需等全部计划项和 numerical controls 结束后另行核对。

## 独立核验

- 从最终选型 RC 文件重新解析实际 MOS primitive、端子和 ports，逐 case 比较 result.devices、candidate_definition 和实际 testbench SHA-256。A 为 3 NFET + 3 PFET，均为 06v0；B 为 4 NFET06v0 + 2 PFET06v0 + 3 NFET03v3。所有 MOS 实际 D/G/S/B 对应波形列均存在；没有以 schematic 同名网替代 RC 内部端点。
- 最终 manifest 的 A/B RC SHA-256 与 `evidence/highspeed-nrz-robustness-layout/final-selection.json` 相同。selected 与旧 final-r4 的 LED、PDK、legacy run/analyze/metrics 六文件逐字节哈希相同，case 与 deck 保持 CLED=200 fF；未见 RX、阈值、span 或 PRBS 的隐式调参。
- `.lib` MOS corner 与 resistor corner 分开注入；PDK 的 `res_typical/res_ss/res_ff` 确实把高阻 poly 的 nominal sheet resistance 设为 1000/1200/800，温度项仍使用 `.temp`。此处只覆盖 PDK RIN，RREF/RDUMMY 及提取的理想金属 RC 不随该 corner 改变。
- 动态 VDD 的 rail energy 从实际 rail voltage vector 计算；tracking DATA 的能量通过串联零伏 VDATA 的电流乘 DATA 对 board-ground 的电位计入一次。VBIT 为无负载控制源。PG case 的 VDD 取 RL 前源端；VSS、各 MOS body 和 DATA 的参考选择与声明一致。
- 固定 sampler 的训练仅采用训练段；validation 只作评价和诊断 phase sweep，不选择新采样相位。诊断脚本准确说明垂直最优 plateau 的选择不是水平眼宽中心，因此 0.25/0.4/0.5 Gb/s 不单调不应改述为传统电路低频带宽失败。
- combined_screen_passed 对 transient 同时要求 device_specific_screen 和原 RX comparison screen；旧统一 3.63 V 字段保留用于比较，不能用它判定 06v0 新器件失败，也不能把统一 6 V 加到 B 的三个 03v3 器件。

## 报告与最终验证须保留的边界

1. independent resistor corner 的范围是片上 PDK RIN，不包含 B 的固定理想 RREF/RDUMMY 容差；LED 静态拟合也没有随温度变化。最终 selected 的动态 supply 项是 VDD +50 mV pulse tracking；aux ripple 位于旧 baseline，不能挪用成新布局已验证项目。
2. DC 的 `combined_screen_passed` 仅由 device terminal screen 决定，因为 DC 不执行 RX comparison screen。DC 电流偏差仍需单列；尤其 joint_SSmin_VLEDaux 不能由 DC 端子 screen pass 推导功能通过。
3. final manifest 内 `scope.stress_screen_V=3.63` 和 `data_fixed=3.6V` 是继承的通用旧元数据。最终限值必须取每份 analysis 的 `device_specific_screen`，PG final DATA 高电平应取 case 的 3.65 V，避免从旧 scope 文本生成错误图注。
4. `audit.py` 的 `all_checks_passed` 表示所见文件身份/读回检查；它不保证所有计划已计算，也不代表所有电气 screen pass。须同时核对 summary 的 missing、failed_simulations、screen_failures、numerical controls 数量和各控制的功能结果。numerical_audit 容差通过本身也不能掩盖控制点的功能 screen 失败。
5. 6 V 为保守项目端子差值 screen，非绝对最大额定值或寿命保证；A8 VSS/substrate 单端 body 返回模型的已记录局限仍需保留。

## 快照身份

- 复核记录时间：2026-10-24T17:33:32.001261
- 最终 run：`build/highspeed-nrz-robustness/selected-a8-b58-r4`
- manifest SHA-256：`188384a3866aaf2f903997d37375d6e2ac90152bf94edf7aff28dd7ea36a1a4b`
- 逐项完成 result 身份核验数：29（随后可能继续增加）
- 当前有效计划唯一名称数：62；同名不同 case 定义冲突数：0。PG 计划在主矩阵末尾才生成，因此当前计划总量不是最终总量。

| 脚本 | SHA-256 |
|---|---|
| `run.py` | `f90db76b5ed65b72c38209fb85410206e60bc0dc750428e7e69e507184a12c7c` |
| `validate.py` | `fdce5881bd94df3f5e5a59a0c13015eabca89b500d8290e218e71a1d923cf53b` |
| `final.py` | `58ef75af5b2557061f53903ffb9e0f316df9fe2f032793e99968a7685c4aad7b` |
| `selected_matrix.py` | `a76cf8423126350e6f15a4c95c5e9623af7b616a3767fa6b1f10e7e2a0823f25` |
| `supply_package.py` | `ccffb3c675a11dc3002a785e99b29d36648aa533eb7573ab9445da10986d90ad` |
| `sampler_diagnostic.py` | `0524bdde5b1e011a7a5eb5620be07dc855d5d83910d84dfc4437d1f7442c3ea1` |
| `numerical_audit.py` | `2c569752555edda1840f7ed595a22a7b758b3758fd6cc4c4064fa3002875e98f` |
| `audit.py` | `d1609e9975a359daa4a2587893279a4e7c62543382fb3396ae741d6789f0b9a7` |
| `reanalyze.py` | `2fc9bfb0c0dbbbfed2b669cd5e0b6c609bce01da5a9918fdec2db448dfa759e2` |
| `candidate.py` | `816338da31ac96d327a1c495ecd6a1f3b5bbd7375d2271d9e53e62fd9427e588` |
| `test_pipeline.py` | `526465ce45d97a23d62f5354eb0ecc4eb108c6e445d09b156e6256a03ace0c1a` |
| `resume.py` | `7e798f8f97c59e3a07427f87c8fab8f39b9d6317be850c997236f103d3655f8a` |
| `waveform_window.py` | `293754d1cb8f780517245837a56bb5b5dcb5ae537fc5a9c483f77a37575edb5b` |


## 主报告确定结论复核（最终审计段待补）

复核对象为 `docs/research/driver-robustness-20261024/report.md`、`scripts/driver_robustness_report/build_report.py`、`plots.py` 及旧报告补正。逐项直接读取旧 PVT summary、本轮 baseline summary、selected summary，未使用报告自身表格作为数值来源。没有改写任何仿真或分析。

- 原 A/B 最大端差分别 3.6206229291383303 / 3.6189426153999142 V，余量为 9.3770708617 / 11.0573846001 mV。供电曲线确实使用旧真实 RC 的 FF 条件，各路线分别保持旧目标速率 A 1、B 0.5 Gb/s；3.600 V 点单独来自 10月23日原记录，其余来自本轮，无重复点。
- FF/−40°C、同 VDD/DATA=3.65 V、同速率/LED/封装/边沿/电阻角等条件匹配无差异。A 峰值由 3.6706773839888 增至 3.71415824704795 V；B 由 3.669022502303427 增至 3.676085870694167 V。正向全部电源＋DATA能量增加 14.4653568% / 8.9830195%。正文将改进归因于实际 06v0 器件筛查范围，而非压低峰值，表述正确。
- 同 0.4 Gb/s 三组 A/B 成对比较的 corner、温度、VDD、DATA、CLED、R/L、边沿、res_corner、扰动设定逐项相同。六点均联合通过。TT 的 A/B 取能为 1308.233465 / 1540.520740 fJ；SS 为 986.320107 / 1354.735115 fJ；FF 为 1547.282436 / 1796.333780 fJ。报告说明实际电流不完全相同、不等同于相同光功率能效，范围准确。
- A 的两项 FF 单辅助电源失败确为 VLED+50 mV 与 VH/VL−50 mV，均零错误而 timing=0.09375 UI。SS 联合控制为 256/511 错误，DC I1=57.19573373 µA，低于固定62.5 µA阈值；正文没有把 DC combined_screen_passed=True 当作 RX 通过。B 对应联合控制为零错误，垂直0.1647470512、水平0.2421875 UI。
- A 的慢热1 Gb/s为75/511错误；0.25与0.4 Gb/s的右侧零错误时间均312.5 ps，对应0.078125/0.125 UI。sampler解释与真实冻结算法一致，没有由validation重新选相位。
- 已视觉检查三张定量 PNG：`nrz-common-energy`、`nrz-package-return`、`nrz-voltage-budget`。数值、轴单位、限值与图注一致，无关键文字或数据裁切。package图标明同一第二级PMOS的端对，未冒充全局最大栅极峰发生于该点。

### 官网依据与历史纠正

本次重新打开 [GF180 DRM14.1](https://gf180mcu-pdk.readthedocs.io/en/latest/physical_verification/design_manual/drm_14_1.html)、[Poly2规则](https://gf180mcu-pdk.readthedocs.io/en/latest/physical_verification/design_manual/drm_07_08.html) 和 [电阻器件支持表](https://gf180mcu-pdk.readthedocs.io/en/latest/analog/model_parameters/LV/LV_1_4_4.html)。它们支持报告的 DC gate-node 3.63 V／6 V 条款、6 V N/P最小长度0.70/0.55 µm及该poly无local statistical model。报告保留了 DC栅氧规定、全端对瞬态项目screen、寿命签核三者区别。

旧10月23日报告的 README、index.html、sources.json 与 `scripts/highspeed_nrz_pvt_report/build_report.py` 均含相同补正；没有只改渲染HTML而让生成器恢复旧表述。旧数值和历史覆盖未被新数据替代。

### 最终化前尚待核对

1. 当前 sources.json 的 final locator 是 `evidence/highspeed-nrz-robustness/summary-verified.json`，尚不存在；实际report-config读取 selected-a8-b58-r4-summary.json。最终应指向真实冻结文件或生成相应最终证据。
2. 当前 report-provenance 仅包含 `figures/*.svg`，未列 PWM 图形、plots.py、字体和 sampler/window 的图形源文件。建议最终化时补足这一可追溯记录，不能由当前manifest声称所有图形生成输入均已固定。
3. 最后PG、numerical/readback audit、VERIFY段及最终汇总数量仍由父代理完成；不把该运行中复核升级成完整覆盖通过。对每个 numerical control 仍需单独确认functional screen，不能仅看容差审计的all_passed。

复核快照时间：2026-10-24T17:55:07.523518；baseline rows=42；selected rows=65。

- `docs/research/driver-robustness-20261024/report.md` SHA-256：`695a5878e6d2a4323dd6e1d35e4681d6bb59c68f16123ff9be267941b739222c`
- `scripts/driver_robustness_report/build_report.py` SHA-256：`53d1297fc8c3d23e4a3296d0e2d2453ebb4b8efb88bd71317b2bc49053cedd31`
- `scripts/driver_robustness_report/plots.py` SHA-256：`17f50255d05f726b3cee0dfbf3dcc95e126f0e7e0aaa210089338106fba08cad`
- `docs/research/driver-robustness-20261024/report-config.json` SHA-256：`1ad38db205916eaa17c7de1fc1d1a1b8004004ab024d6f687efe53488f722c4a`

### 最终 selected case 身份与计划覆盖补查

已在全部65个result出现后，重新逐项核验 actual RC→result MOS端点、candidate定义、deck SHA、stimulus、冻结输入、执行脚本与analysis.result SHA。65个result、65个summary名称、65个未被supersede的唯一计划完全一致，无同名异定义。16个DC、49个transient；transient中42个联合通过、7个保留失败。此统计只适用于selected最终run，不含其他候选或PWM。6个数值控制均各自联合通过；numerical-audit记录完整6项通过。


## 最终报告复核收口

当前 report-config 已切换到实际存在的 `summary-verified.json`；其 selected 子对象与最终selected摘要完全一致。状态为 `verified_experiments_with_open_design_failures`，VERIFY段已填入42 baseline、65 selected、7保留接收失败、0器件筛查失败，未把DC误算成RX样本。6组numerical差值上限62.9334 µV、0.000166114垂直余量、0 UI水平余量、0.0140009%正向取能，与正文一致。PWM 101身份/98完成/3未收敛及5个观测修订重复的数量与其独立final-audit一致；本审阅不取代PWM代理的电路审计。

此前的两项报告来源问题均已关闭：最终provenance的22个输入、30个SVG/PNG图形文件、11份authoring script与HTML哈希全部现场复算一致，已覆盖PWM图形、字体、plots.py、sampler和package窗口来源。页面所有本地href/src目标均存在。当前报告明确把静态+50 mV比较与3.600 V供电封装比较拆开；前者峰值和能量升高，后者新版A峰值降至3.666489 V，前后口径不再混淆。

新增PG对比图的两份CSV/JSON确实使用相同中心149.0407364007132 ns和相同窗口；图已视觉检查。它显示同一数据事件且注明不保证包含新版全局峰，未将窄窗峰误当全时域峰。审阅没有新增仿真，也没有改变电路、RX或任何case。

备份工具另已准备在 `build/github-sync-driver-robustness-20261024/`，4项纯合成测试通过；未执行实际范围freeze、pack、upload或下载。实际里程碑备份仍由父代理在冻结后触发。本复核不预先宣称GitHub备份已完成。

最终复核时间：2026-10-24T18:02:49.814458

- `docs/research/driver-robustness-20261024/report.md` SHA-256：`7d1cf46c37978679b0e9a687b99e4dd082b50409be367b48e5d6ae1f69a42dfe`
- `docs/research/driver-robustness-20261024/index.html` SHA-256：`95847000f1d331226b864930fe14d2eed2bd5e40563b6efb4a667a095ec301e3`
- `docs/research/driver-robustness-20261024/report-provenance.json` SHA-256：`f14d668f789e4e93006a8c89468c75a89d7b83d44fb1f179e38afc52513f175d`
- `evidence/highspeed-nrz-robustness/summary-verified.json` SHA-256：`15427c836e91a4b1691ae78a32b57c125dd5b2123211722591a6b92fe99f7c86`
