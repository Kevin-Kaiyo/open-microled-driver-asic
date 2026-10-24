# PWM参考动态与受控启动复现

固定的最终候选以`analog/pwm_reference_v2/final-network.json`为描述，以每个case的`testbench.spice`、`result.json`和不可变input manifest为执行依据。是否满足全部本轮门槛，以`evidence/pwm-reference-v2/20261024/validation.json`的`selected_acceptance`为准。历史失败不会被删除或计入最终通过。

## 跨目录 / 另一台电脑的最小入口

需要本轮的`build/pwm-reference-v2/20261024/inputs/`、要复跑的case目录里的`testbench.spice`、`result.json`，以及startup/fault/pwm case的`rtl-events.csv`。**不需要下载旧Oct15或上一轮的大波形，也不需要运行旧freeze入口。** 本轮input manifest引用的文件必须齐全，包括`executed_sources/`和`manifests/`。

环境：Python + NumPy、ngspice（本机47）、Icarus Verilog/vvp。在仓库根目录运行，目标目录必须不存在：

```sh
.venv/bin/python scripts/pwm_reference_v2/reproduce.py \
  --case c15_dc \
  --destination build/pwm-reference-v2/reproduction-c15-dc
```

可将`--case`换为其它已完成case，如`c15_step`或`c15_pwm`；也可用`--source`指定恢复后的本轮数据目录。入口先核验所有输入SHA，再复制到新空目录，只重定位include/lib绝对路径；重新编译冻结RTL，涉及数字事件时核对事件CSV字节，最后运行SPICE并gzip回读校验。原case不被修改。`reproduction.json`记录原/新deck SHA、输入SHA、工具版本及raw字节是否与原件一致。跨平台不承诺位级一致；不同版本需要另做数值对照。

## 生成与审计入口

- `run.py`：本轮研究生成器，发展环境中复用上一轮冻结输入，所有改变必须用新case名字。`--reuse`仅复用完全相同deck。该入口不代替上面的无旧依赖复现入口。
- `loop.py` / `final_loops.py`：三点局部两注入估计，保留闭环/电压/电流注入OP和AC。它不是严格Tian全多环路签核；最终记录包含自身源、helper源及manifest身份。
- `validate.py`：核验全部case的deck/log/raw/执行源/manifest SHA，枚举历史身份例外与未执行排队deck，计算两方法/两步长数值差异。
- `report.py`：生成中文图、紧凑图数据、`final-summary.json`和图源SHA。
- `archive_raw.py`：对已结束case的残留raw做gzip回读校验，保存归档映射；小AC/OP表保留原件便于独立审阅。

```sh
.venv/bin/python scripts/pwm_reference_v2/validate.py
.venv/bin/python scripts/pwm_reference_v2/report.py
```

全局PWM锁为`/tmp/open-microled-pwm-reference-v2-ngspice.lock`，每路最多一个ngspice。新case受1.5GiB分支预算和5GiB剩余磁盘门槛约束。结果中的`elapsed_ngspice_s`不含锁等待；早期`elapsed_s`包含等待，不能直接比较求解速度。

受控启动只验证VSAFE/VBUF/VLED及外部FAULT先建立、随后VREF上升的既定顺序。原LED参数、20µs FAULT保持、1MHz/256µs PWM及全部电流/电荷窗口不变。VSET仍是外部0.5V边界，非已验证片内带隙或自主POR。原39MOS真实PEX未修改；新的PCB电容/阻尼与封装R/L工程模型不产生新片内GDS。
