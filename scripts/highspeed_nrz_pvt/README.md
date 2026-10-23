# NRZ PVT 修复实验（2026-10-23）

本目录沿用原 NRZ 实验的 MicroLED 静态模型、动态假设、20 ps 外部输入边沿、训练/验证码型、接收阈值及采样算法。最终选择不改变任何 MOS 尺寸：A 在输入增加 48 × 1 µm 的 `ppolyf_u_1k_6p0`；B 使用 58 × 1 µm，并将原 RREF 改接已经存在的固定 3.3 V `VDUMMY` 电源。参考电阻仍为 88.386106 kΩ；这不是已设计的稳压器或温度补偿参考源。

最终实际电路在 `analog/highspeed_nrz_pvt/`，实际版图和提取模型在 `build/highspeed-nrz-pvt-layout/final-r4/`。物理检查和模型版本由独立的版图流程保存。本流程针对包含真实 R/C 网络的晶体管级模型运行仿真；器件模型中已经包含的电容不会人工再加一次。

## 可复现执行

使用本项目布局 Python 环境（包含 NumPy），不要把虚拟环境 Python 符号链接解析为系统解释器。

```sh
build/layout/venv/bin/python scripts/highspeed_nrz_pvt/test_pipeline.py

# 新目录冻结输入，不覆盖已有 run。完整 PDK、ngspice 与历史基线 raw 需先按开发交接说明恢复。
build/layout/venv/bin/python scripts/highspeed_nrz_pvt/formal.py \
  --work build/highspeed-nrz-pvt/reproduction \
  --freeze build/highspeed-nrz-pvt-layout/final-r4 \
  --baseline-extension build/highspeed-nrz-pvt/formal-poly58-r1 \
  --stage targets

build/layout/venv/bin/python scripts/highspeed_nrz_pvt/formal.py --work build/highspeed-nrz-pvt/reproduction --stage grid
build/layout/venv/bin/python scripts/highspeed_nrz_pvt/formal.py --work build/highspeed-nrz-pvt/reproduction --stage dc
build/layout/venv/bin/python scripts/highspeed_nrz_pvt/formal.py --work build/highspeed-nrz-pvt/reproduction --variants GEOM,C --stage targets
build/layout/venv/bin/python scripts/highspeed_nrz_pvt/formal.py --work build/highspeed-nrz-pvt/reproduction --variants AFTER --stage numerical
build/layout/venv/bin/python scripts/highspeed_nrz_pvt/formal.py --work build/highspeed-nrz-pvt/reproduction --variants AFTER --stage integration
build/layout/venv/bin/python scripts/highspeed_nrz_pvt/validate.py --work build/highspeed-nrz-pvt/reproduction
```

默认逐一执行。可将 `--routes A` 与 `--routes B` 分为两个进程，最多同时运行两个 ngspice。默认速率网格为 0.1、0.25、0.5、1、2、4、8 Gb/s；三个组合条件为 TT/27°C/3.3 V、SS/125°C/3.0 V、FF/−40°C/3.6 V。多晶硅电阻的 res_typical、res_ss、res_ff 分别与 MOS 同名角配对；这不是独立电阻角和 MOS 角的全组合验证。

`numerical` 对选定工作点（A 1 Gb/s、B 0.5 Gb/s）的三条件运行 UI/80；`integration` 对 TT 与 FF 运行 Trap、UI/200。默认采用 Gear、UI/40。单次工作点的判定、整个速率离散网格、完整 PVT 覆盖与真实 BER 是不同的证据。

## 证据与缓存

- 每次实际运行保存实际网表、仿真日志、源代码字节、冻结输入散列、全部 MOS D/G/S/B 和新增三端电阻端电压。
- 电源能量包含所有供电端及理想 DATA 源，正向供能、返回能量与净能量分别统计。B 的 RREF 改接 VDUMMY 后，由该电源端的电流计入能耗。
- `BEFORE` 中 26 点来自上阶段；另 16 点由本阶段在 `formal-poly58-r1` 实跑补齐。最终 run 引用这 42 点，不复制大型波形，也不称为本次重新运行。
- 旧的 23 个探索案例没有在执行时都记录完整候选定义身份。`candidate-ledger.json` 是明确标注日期范围的事后网表检查，不把事后核对冒充当时的冻结记录。最终 run 使用完整输入身份。
- 缓存若发现网表、include 文件、候选定义、码型或接收模块变化会拒绝复用。跨机器的绝对网表路径变化时，请创建新的 reproduction run；不要手工改旧证据以消除报错。
- 新波形压缩后逐字节 SHA-256 回读验证，再移除该波形的未压缩副本。保留所有失败仿真与不达筛查标准的案例。原有工程数据不删除。

## 诊断控制的边界

`controls.py --length 58` 只把首版电阻第三端直接接理想地，用来隔离体端回路；`--length 40` 还改变其长度。`--local --length 48` 在第三版 RC 网络中只改变电阻长度，其余旧 R/C 不变。这些是定位机理的干预，不能视为新芯片的最终 PEX 结果。最终结论只能读取 `final-r4` 实际重新提取的模型。A 的 48 µm 电阻长度是在 r3 的寄生结果指导下选择的；最终 manifest 的 `no_retune_after_pex` 仅表示 final-r4 冻结之后没有再改模型或校准电流，不表示整个设计过程没有利用 PEX 迭代。

3.63 V 是本项目统一端电压筛查线，不是晶圆厂可靠性签核。RC 网络和 lumped 三端电阻的衬底端响应不等于 3D 衬底电磁/TCAD 验证。还需要独立电阻角、失配、LED 动态实测、封装、真实电源、接收器与硅后光学验证。
