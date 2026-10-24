# 供电、电阻角与封装扰动：研究报告与复现

[中文研究报告](index.html) · [真实GDS分层查看器](layout-viewer.html) · [报告文字源](report.md) · [来源](sources.json)

## 先读结论与范围

旧高速核心的9–11 mV余量不足。新真实厚栅氧核心提高了相对器件筛查门限的余量，但A电压驱动的辅助电源扰动接收仍失败；B电流转向在所测范围较稳健。显示PWM独立保留39MOS/合成LED模型，板侧参考滤波降低电流扰动，恢复速度及启动数值闭合仍有限制。所有结果为声明模型下的电学实验，不是实测光学BER、产品规格或制造接受。

A选定实际版图为 `hv-A8-r3/A`，B为 `hv-r2/B`。原版、被否决候选、求解失败及管理中止记录保留。不要把缺失计划、仿真失败、RX失败、电压筛查失败和完整性核验合并成一个通过率。

## 查看与重建报告

```sh
python3 -m http.server 8772 --bind 127.0.0.1
# 浏览 http://127.0.0.1:8772/docs/research/driver-robustness-20261024/index.html

build/layout/venv/bin/python scripts/driver_robustness_report/draw_voltage.py
build/layout/venv/bin/python scripts/driver_robustness_report/draw_steering.py
build/layout/venv/bin/python scripts/driver_robustness_report/draw_supply.py
build/layout/venv/bin/python scripts/driver_robustness_report/plots.py
build/layout/venv/bin/python scripts/driver_robustness_report/build_report.py
```

绘图需NumPy、Matplotlib，HTML需Python Markdown；字体使用本轮report-support归档中的公开Noto Sans CJK SC，许可随附。电路SVG按实际连接绘制且校验器件表；版图SVG来自真实GDS。箭头用于解释电路，不是电磁场或电流密度测量。

## 电气小输入复跑

从本轮Release恢复相对目录，再使用相同ngspice47、NumPy及Icarus Verilog环境。可以只恢复小型inputs/metadata，不必下载所有历史原始波形。新机器必须用全新run目录，脚本会重建绝对路径；不能改写原冻结网表使其假装来自另一台机器。

```sh
build/layout/venv/bin/python scripts/highspeed_nrz_robustness/reproduce.py \
  --source-work build/highspeed-nrz-robustness/selected-a8-b58-r4 \
  --work build/highspeed-nrz-robustness/new-machine-run --smoke-dc

.venv/bin/python scripts/pwm_robustness/reproduce.py \
  --inputs build/pwm-robustness/20261024/inputs \
  --manifest evidence/pwm-robustness/20261024/input-manifest.json \
  --case-file evidence/pwm-robustness/20261024/dc_board100n.json
```

[NRZ详细运行入口](../../../scripts/highspeed_nrz_robustness/README.md)和[PWM详细入口](../../../scripts/pwm_robustness/README.md)说明完整矩阵、数值控制、不可覆盖的case身份和数据重分析。DC smoke只验证新目录可运行，不能替代全部瞬态复跑。

## 物理复核与原始证据

```sh
build/layout/venv/bin/python scripts/highspeed_nrz_robustness_layout/validate.py \
  --run build/highspeed-nrz-robustness-layout/hv-A8-r3 \
  --out build/verify-restored-A.json
build/layout/venv/bin/python scripts/highspeed_nrz_robustness_layout/validate.py \
  --run build/highspeed-nrz-robustness-layout/hv-r2 \
  --out build/verify-restored-AB.json
```

这些是原始交付的只读独立复核，包含GDS层结构、连接报告和哈希；不是重新执行全部EDA。完整重跑需要[固定full-PDK/tool环境](../../../layout/pdk-lock.json)，模型subset不能替代物理PDK。互连C的空间分配与衬底电阻图仍有提取近似。

原始证据在 `build/highspeed-nrz-robustness/`、`build/highspeed-nrz-robustness-layout/`、`build/pwm-robustness/`，未进入普通Git；相应compact evidence已进Git。备份范围、归档逐成员SHA、远程回读和新目录恢复见[跨机交接](../../development-handoff.md)。
