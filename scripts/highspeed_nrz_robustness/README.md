# NRZ 电源／独立电阻角／封装鲁棒性实验（2026-10-24）

本目录仅新增实验，不修改上阶段 `highspeed-nrz-pvt/final-r4` 数据。先用真实 full-RC 提取模型复现供电失效，再考虑真实器件修改。所有实验冻结相同 MicroLED 静态曲线、200 fF intrinsic LED capacitance、20 ps 外部输入、PRBS 训练／511 bit 验证码型、200 ps optical proxy、1 GHz receiver、62.5 µA threshold 与采样方法。所有光学变量仍为假设，不是实测 BER。

## 预声明矩阵

`baseline-r1` 使用旧真实 RC 的 A 1 Gb/s、B 0.5 Gb/s。

- 最小失败复现：FF/−40°C，VDD=3.65 V。DATA high 跟随3.65 V与固定3.6 V分开记录，low均为0 V。
- 电阻独立角：SS/125°C/3 V与FF/−40°C/3.6 V分别改变为另外两种 `res_typical/res_ss/res_ff`。配对角已在旧阶段测过；新数据只声称新增交叉角，不是随机 mismatch 验证。
- 静态电源：FF VDD相对3.6 V偏移−50、−25、+25 mV；+50 mV由最小复现覆盖。VLED单独±50 mV；A的VH/VL共同±50 mV或B的VDUMMY±50 mV。这里VH/VL相关偏移，不声称所有独立双电源组合。
- 动态电源：VDD +50 mV pulse在第300 UI开始，1 UI上升／下降、32 UI宽、127 UI周期，DATA固定和实时跟随分别验证。另对VLED及A的VH/VL或B的VDUMMY同时注入10 MHz、±50 mV同相正弦。其余参数冻结。
- 封装：基准(1 Ω,0.5 nH)外，(0.25 Ω,0.1 nH)、(1 Ω,2 nH)、(4 Ω,0.5 nH)、(4 Ω,2 nH)。仅 lumped R/L，不是完整封装/PCB/EM模型。

各stage的case清单在执行前写入 `plan-*.json`。不是连续操作范围证明，也没有组合所有未知扰动。失败数据与日志保留。

## 电源能量与应力

全部电源与DATA都用其实际采样电压和电流 `v(t)*i(t)` 积分。实时跟随DATA使用无负载归一化码型源与behavioral amplitude source；串联零伏VDATA只测电流，能量用实际DATA节点电压计算，避免漏算或者重复计算。正向供能、回灌与净能量仍分别统计；上游电源生成损耗不包含。

保留旧全器件3.63 V指标作为可比数据。新增器件分类筛查：03v3所有六个端对3.63 V；06v0所有六对保守6.0 V。后者是研究用保守筛查，不将公开 gate DC限制扩张为全端对完整可靠性认证。官方条件来源应与项目报告中的source ledger共同读取，不能仅因06器件通过就称可量产。

## 可复现与存储

```sh
build/layout/venv/bin/python scripts/highspeed_nrz_robustness/test_pipeline.py
build/layout/venv/bin/python scripts/highspeed_nrz_robustness/validate.py --work build/highspeed-nrz-robustness/reproduction --freeze --stage minimal
build/layout/venv/bin/python scripts/highspeed_nrz_robustness/validate.py --work build/highspeed-nrz-robustness/reproduction --stage resistor
```

其他stage为 `supply`、`dynamic`、`package`。绝对路径变化请新建run，不改旧网表。旧receiver/analyzer模块以SHA256冻结；新增能量算法与执行代码也保存源字节。新波形立即gzip level6并逐字节SHA256回读验证后移除未压缩副本。新目录初始预算4 GiB，按新增真实版图／电源回路范围明确先扩到6 GiB，实测完整保留矩阵后扩到8 GiB（见scope-amendments.json及storage-budget-extension-8g.json），磁盘剩余4 GiB下拒绝仿真。初始通过 `/tmp/open-microled-ngspice.lock` 全局串行；资源复核后改为 `/tmp/open-microled-nrz-ngspice.lock`，NRZ内部仍只有一个ngspice，PWM与NRZ最多各一个（见lock-policy-change.json）。管理中止等待锁的案例保留并以新case名补跑。

`candidate.py`的HV候选是新的器件假设：A所有MOS、B的四个inverter和两只steering MOS改为06v0；B REF/BASE/TAIL保留03v3。初试采用N L0.7 µm、P L0.55 µm，W/L近似保留。初始 `hv-r1`估计扩散长0.5 µm，在实际PCell读取前启动，明确为pre-layout；实际重提取模型优先于这个估计。它没有降低外部供电，也没有修改LED/RX来制造通过。

## 追加物理电源回路与诊断

在LED串联R/L之外，追加VDD lead与VSS return各1Ω/2nH的假设模型。VDD源在封装前采样能量，die VDD/VSS分别保存，DATA固定参考板级0V。此时PEX所有VSS节点与其参考电容随die VSS连接，不强行固定回地。供电源阻抗字段为`supply_package`，与LED回路的`r_pkg/l_pkg`分开记录。`waveform_window.py`从SHA核对后的原始波形提取最坏点附近CSV。

实际A8缩短RIN后，SS2.95V .5Gb/s仍以0.097873归一化threshold margin失败；bodytie版0.097738亦失败，均不因0/511误码而改判。A .25Gb/s又因冻结训练采样器的归一化timing margin失败；追加预声明中间点.4Gb/s在TT/SS2.95V/FF3.65V通过后，最终使用A .4Gb/s、B .5Gb/s作为离散压力测试点，并另外实跑两路同.4Gb/s的能耗比较。这不是连续速率上界。另保留SS低VLED/aux联合负控，供电差分导致的DC失效不能靠降速解决。

每个新分析进程import时冻结源码字节。早期逐case读取磁盘文件hash的来源弱点通过`reanalyze.py`独立重读原raw到`analysis-verified.json`补救，保留原analysis；`audit.py --full-waveforms`逐字节回读gzip并验证deck、输入、执行源与分析源。

## 冻结manifest的遗留字段解释

初次freeze继承的 `stress_screen_V: 3.63` 是旧03v3统一指标，不是新06v0器件门限。必须读取实际analysis的 `device_specific_screen`（03v3仍3.63 V，06v0保守6.0 V）及gate-specific峰值，不能修改旧manifest来抹去历史。`DATA fixed3.6V` 描述原FF控制；最终每个case的data_mode、data_high_V、rail_profiles及实际波形才是该case输入。DC的combined_screen仅表示器件端压，不是RX通过。独立电阻角覆盖PDK poly RIN，不覆盖B外置理想RREF/RDUMMY容差。

最终审计分别报告有效计划coverage（去除明确superseded计划与管理中止，补跑仍计入）、SPICE失败、分析失败、functional screen失败、device screen失败。`all_checks_passed` 只表示源身份与留存数据完整性，不能翻译为“全部电路通过”。

## 另一台电脑：只恢复本轮输入即可新仿真

先从本轮Release恢复选定run的 `inputs/`、`stimulus.json`、`manifest.json`，以及当前项目脚本与同版本ngspice/Python依赖。重新运行新的实验不需要恢复上阶段大raw，也不需要旧BASE目录。请用新目录，避免复用原绝对路径deck：

```sh
build/layout/venv/bin/python scripts/highspeed_nrz_robustness/reproduce.py \
  --source-work /path/to/restored-selected-inputs \
  --work build/highspeed-nrz-robustness/new-machine-run \
  --smoke-dc
```

这个入口核对本轮所有相对输入SHA，复制inputs/stimulus到全新目录并记录parent manifest SHA；不复制cases/raw、不覆盖已有目录，之后网表按新机器路径生成。恢复后的manifest里旧baseline/physical路径仅作历史来源，不再是执行依赖。该入口已从仅含本轮inputs/stimulus/manifest的恢复树实际运行一个FF3.65V DC点，证据在 `reproduction-smoke-r1/reproduction-check.json`。
