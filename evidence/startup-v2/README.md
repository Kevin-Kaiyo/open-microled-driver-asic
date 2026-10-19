# 单像素参考启动与保护完善：TG隔离候选

日期：2026-10-14。定位：实验性研发方法验证与教学。JSON中的 `passed=false` 是真实结果，不能只读取功能通过字段后宣称所有启动验证已经完成。

## 本轮解决的问题与未解决的问题

旧 reference rail 在100 ns内从0升至3.3 V，logic与LED rail已有有效电压；外部 fault保持高20 µs。reference输出建立使像素BIAS变化，寄生耦合到LED_K；数字PWM已为低，LED branch仍出现5.7914 nA，超过原1 nA全启动峰守卫，几乎全为电容位移分量。原Trap积分器晚期交替纹波又污染了极小正向电荷。

本轮在REFOUT→BIAS增加真实CMOS transmission gate，并在fault高时钳BIAS到VSS。匹配对照两者均用finite-junction servo、Gear2、相同100 ns reference ramp，仅改变隔离路径：峰由4.8374 nA降到0.04775 nA。该修复压低了真实端口峰，未改成只看导电分量。原zero-junction/Trap 5.7914 nA失败也重新跑出并保留。

| 项目 | 仿真结果 | 判断 |
|---|---:|---|
| TG TT / 27°C / logic3.3 V / LED5 V 全开 | 99.97693 µA | 原±5%目标通过 |
| TG SS / 85°C / logic2.97 V / LED4.5 V 全开 | 97.73869 µA | 原±5%目标通过；开关压差代价约−2.26% |
| TG FF / 0°C / logic3.63 V / LED5.5 V 全开 | 100.85480 µA | 原±5%目标通过 |
| 三实验包络×100 ns/1 µs/10 µs reference ramp | 最大启动branch峰0.05110 nA | 9个启动峰守卫通过 |
| TT d1最低PWM码，maxstep10/2 ns | −0.0428654% / −0.0428428% | 原2%面积目标及0.2%收敛通过 |
| TT / SS / FF停钟fault→稳定1 nA以下 | 202.216 / 299.222 / 153.500 ns | 原1 µs目标通过 |
| TT / SS / FF首1 µs Q+ | 0.41056 / 0.47583 / 0.32245 pC | 原10 pC目标通过 |
| TT / SS / FF首1 µs Q− | −7.35756 / −6.95135 / −7.56276 pC | 教学20 pC预算通过 |
| TT startup Q+，10/2 ns | 4.9162e−21 / 5.1576e−21 C | 原0.2%相对收敛仍失败，差4.909% |

最后一项没有改验收线。正向电荷绝对差为2.4134e−22 C，约为故障10 pC预算的2.41e−11，仅用于数值规模诊断。SPICE电荷是连续量；折算电子数不能作为归零依据、物理真假判据或仪器分辨率。报告保留overall false；需要后续定义有意义的数值分辨能力与真实LED测量条件。

## 恢复是另一项实验

fault在20 µs解除、permit仍低到21.5 µs、rawPWM到22.5 µs才允许第一段高电平。TG恢复带来BIAS过冲约1.991 V，约20.53 ns进入最终BIAS的±1%范围；恢复前约1.48 µs有充足模型settling间隔。端口电流短负峰−4.838 µA，Q−约−0.009711 pC，模型导电峰4.855 fA，protectedPWM仍低。无隔离的匹配对照也有−4.765 µA释放峰，因LED shunt撤销本来存在位移电流；不能把全部峰归因于TG。停钟场景检查fault去除后仍不恢复，只有reset/raw低/显式recover/有效clock后恢复。

## 候选失败与数值失败均保留

- 四MOS单NMOS方案完整失败：[4mos-trial/summary.json](4mos-trial/summary.json)。SS全开仅68.05 µA；没有选定。
- 最终TG方案：[summary.json](summary.json)。21 transient、12 DC，134检查；`functional_contract_passed=true`、`legacy_startup_relative_convergence_passed=false`、`passed=false`。
- 独立数学/哈希审计：[validation.json](validation.json)。审计通过不升级实验失败。
- 早期极严OP、UIC、KLU及更细步长诊断记录在 [failure-ledger.json](failure-ledger.json) 和raw目录中；它们不是额外签核证据。

## 可复现命令

```sh
build/layout/venv/bin/python scripts/startup_v2/run.py --publish-evidence
build/layout/venv/bin/python scripts/startup_v2/validate.py
```

第一条预期返回2，因为原startup Q+相对收敛还没通过；summary保留功能/legacy分离字段。第二条通过表示来源哈希、原始波形、方向电荷、积分及失败标志复核一致。

源见 [reference_isolator_tg.spice](../../analog/startup_v2/reference_isolator_tg.spice)，参考源使用 [vset_servo_with_junctions.spice](../../analog/reference/vset_servo_with_junctions.spice)。各case存完整启动/fault/recovery CSV和RTL事件；normal d1的compact CSV用于展示，精确积分审计使用`raw_directory`里的full-resolution `.dat`。冻结输入、网表、ngspice日志和工具版本都在raw目录。

## 证据边界

本轮没有验证全芯片电源先后顺序。logic与LED电源始终有效，只测试reference rail ramp及VSET延迟；没有实现POR、brownout、fault sensor或物理恢复寄存器。新增5MOS隔离、10MOS参考源、10MOS保护gate和2MOS LED clamp均未做布局；只有旧12MOS selected signal PEX复用，真实PG/body/邻居活动未包含。单像素3.3 V CMOS控制接口、外部VSET/RSET、合成LED与理想被动元件仍有条件假设。端压捕获不能替代SOA、ESD、latchup、HCI、TDDB、温升、硅测量或光学extinction验证。下一步先实现可验证的上电/欠压状态合同与安全enable，再推进单像素完整布局。
