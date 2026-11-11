# MicroLED A/B 有限驱动方法对照

本目录与前一阶段 `scripts/ab_improvement_20261111/` 分开；前一阶段源、网表和证据不修改。模拟使用同一 GF180 PDK 子集、LED I–V/200 fF、200 ps 光学一阶模型、1 GHz RX、25/100 µA DC 目标和完整 4096 payload bit 接收判据。

## 入口

- `micro_engine.py`：前一阶段受校验执行器的独立副本，BUILD 固定到本阶段；在导入时固定自身字节与 SHA，每个 case 保存执行源。新增 A 的 FF 节点导出不改变求解或接收。
- `micro_candidates.py`：A 阻尼前馈、B 低压匹配虚支路，以及 B 只降压控制。没有修改 MOS 类型或尺寸。
- `micro_run.py`：先过 DC 再执行指定速率；同一进程一次只运行一个 ngspice。
- `micro_holdout.py`：固定电路后测试预声明 0x4c2d 片段，仅允许数据源变化。
- `micro_verify_selected.py`：A2.0/B1.8 留出；若失败，保持电路不变，补验证预定低速工作点；最后补3.2目标诊断。所有失败保留。
- `micro_summary.py`、`micro_diagnostics.py`、`micro_figures.py`、`micro_validate.py`：生成紧凑证据、原生节点因果数据、图片和哈希/门槛/能量一致性检查。

## 重现顺序

先恢复前一阶段归档的 `build/ab-improvement-20261111/{a-rin1wide-core03-matched,B_wide_ff31p275}/` 以及 `build/blue-emitter-speed-review-20261110/microled/`。需要 ngspice47 与项目 NumPy/Matplotlib Python 环境。不得覆盖现有未完成 case；执行器 append-only，完成的相同 case 可做哈希验证后重用。

```sh
build/layout/venv/bin/python scripts/driver_methods_20261111/micro_run.py A_rcff31p275 --rates 1.6 2.0 2.4
build/layout/venv/bin/python scripts/driver_methods_20261111/micro_run.py B_vin3p3_dummy27p6k --rates 1.6 1.8 2.0 2.4
build/layout/venv/bin/python scripts/driver_methods_20261111/micro_run.py B_vin3p3_dummy50k_control --rates 1.6
build/layout/venv/bin/python scripts/driver_methods_20261111/micro_run.py A_rcff31p275 --skip-dc --rates 2.0 --steps 80
build/layout/venv/bin/python scripts/driver_methods_20261111/micro_run.py B_vin3p3_dummy27p6k --skip-dc --rates 1.8 --steps 80
build/layout/venv/bin/python scripts/driver_methods_20261111/micro_verify_selected.py
build/layout/venv/bin/python scripts/driver_methods_20261111/micro_diagnostics.py
build/layout/venv/bin/python scripts/driver_methods_20261111/micro_summary.py
build/layout/venv/bin/python scripts/driver_methods_20261111/micro_figures.py
build/layout/venv/bin/python scripts/driver_methods_20261111/micro_validate.py
```

参数相同、案例缓存存在时，不把重复读取叫作新仿真。每个 `result.json` 的 manifest/deck/执行源/原始波形 SHA 用于区分源和结果；本阶段 summary 同时引用上一阶段同速基线，并保留各自 SHA。

这里不宣称完成新布局/PEX、启动/独立关断、PVT、随机误码率或任何实物链路认证。详见 `evidence/driver-methods-20261111/micro-mechanisms.md`。
