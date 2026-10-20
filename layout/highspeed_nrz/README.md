# 单通道 NRZ 晶体管核心版图

本目录实现两种独立的 GF180MCU 3.3 V CMOS 核心，保留原始电路的 W/L。
它们用于比较电压驱动与电流转向的版图寄生影响，不是完整的可流片芯片。

| 路线 | 核心端口顺序 | MOS 数 | 实际核心外框 |
|---|---|---:|---:|
| A 电压驱动 | `DATA OUT VDD VH VL VSS` | 6 | 34.43 × 24.51 µm |
| B 电流转向 | `DATA OUT VDD VSS BIAS DUMMY` | 9 | 52.75 × 23.35 µm |

A 的 VH/VL 仍为核心外的理想双向电源；B 的 RREF 接 VDD–BIAS，
RDUMMY 接外部 VDUMMY–DUMMY。BIAS、DUMMY 必须作为真实核心端口，
不能在仿真封装中遗漏。B 的尾电流管宽度由 5.75895881652832 µm
取整至 5.760 µm，满足 0.005 µm 制造网格。此变化必须进入原理图控制。

布线采用 M1 器件接触、M2 源漏/体端引线、M3 短局部总线、M4 栅极跨线。
M4 用于避免最小沟道器件相邻源漏接触与栅极引线在 M2 上冲突。
实际使用四层金属；GF180D 工艺配置为五层金属，不代表芯片仅有四个物理材料层。
每只 MOS 使用独立扩散区，包含阱/衬底接触。该实现尚未优化面积和单端栅极接触电阻。

复现：

```sh
build/layout/venv/bin/python scripts/highspeed_nrz_layout/run.py --run <新的目录名>
build/layout/venv/bin/python scripts/highspeed_nrz_layout/correct_capacitance.py \
  --base build/highspeed-nrz-layout/<新的目录名> --run <修正模型目录名>
build/layout/venv/bin/python scripts/highspeed_nrz_layout/audit.py \
  build/highspeed-nrz-layout/<修正模型目录名> --negative-controls
build/layout/venv/bin/python scripts/highspeed_nrz_layout/publish.py \
  build/highspeed-nrz-layout/<修正模型目录名>
```

物理几何验证运行是 `build/highspeed-nrz-layout/r3`；经电容审计修正的模型在
`build/highspeed-nrz-layout/r4`，几何、全部电阻与 MOS 未改变。
失败的 r1 原始日志以及 r3 的错误原生电容输出均保留。
精简证据在 `evidence/highspeed-nrz-pex/physical/summary.json`。两个核心均通过
Magic DRC、独立 KLayout DRC、原生与 GDS 回读 LVS、RC 折叠拓扑 LVS。
真实 GDS 断线和电源短接反例均被 LVS 拒绝，即使这两类几何错误仍可能满足 DRC。

校验当前冻结交付，不重跑 EDA：

```sh
python3 scripts/highspeed_nrz_layout/validate_delivery.py
```

该校验器检查发布文件哈希、原执行脚本版本、10 个冻结模型/GDS、端口顺序、
R/MOS 保持、反例记录，并独立解析 `.ext` 核对 RC/C/RCLUMP 的电容矩阵。
C-only 导出保留 12 位有效数字，因此其校验允许相应的文本舍入误差；
RC/RCLUMP 保留 17 位。此步骤验证证据完整性，不替代重新运行 DRC/LVS。

`physical-contract.json` 保存真实 GDS 外框、层、端口坐标、每只器件中心和
D/G/S/B 接触坐标，以及原理图器件到提取实例和 RC 端子节点的逐一映射。
这些坐标可直接用于二维 GDS 可视化，不是概念示意坐标。

全 RC 网表包括体端、电源及信号网络，A 覆盖 8/8、B 覆盖 9/9 个网络。
采用公开的 Magic `res:drive` 属性补足默认提取范围，原始几何不变。
`geometry-only.spice`、`capacitance-only.spice` 从同一完整 RC 网表构造，
用于区分真实结几何、电容和电阻的作用，不能替代主 RC 模型。
实际 AD/AS/PD/PS 保留给 BSIM 模型计算结电容，不再叠加理想结电容。

审阅发现固定 Magic 版本的三个数值问题：层次导出器将 MOS 子电路误入电阻
π 模型分支，改变栅极电容的位置；电阻提取未读原节点对地电容、却将耦合电容
复制到两端；原节点保留使导出中又累加了这些复制电容。因此 r3 原生 C/RC
不能直接用作正式性能结论。

r4 直接以 GDS 回读 `.ext` 中的高精度对地/耦合电容为基准，保留全部 R/MOS。
对地电容采用 Magic 电阻网络简化后保留的归一化分配权重；耦合电容在原逻辑网
节点仅计入一次。权重最初来自几何面积，但网络简化可按电阻权重迁移电容，
所以不能称为独立的 GDS 面积实测或真实介质场中的电容分布。
折叠电阻后，r4 的逐节点对电容矩阵与 `.ext` 守恒；这证明数值记账正确，
不证明高频空间分布正确。`rc-lumped-capacitance.spice` 使用相同完整 R/MOS
和相同电容矩阵，将电容全部放在原网络节点，作为位置敏感性控制。

这不是三维电磁场求解，也没有提取封装电感。独立 DRC 使用 FEOL/BEOL、
连接与网格规则；未建立 dummy fill、整片密度、天线、EM/IR、ESD 和可靠性闭环。
后续必须把这些边界与电学仿真结果一起解读。
