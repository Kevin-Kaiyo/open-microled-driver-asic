# NRZ PVT 修改的物理实现与交付入口

最终设计、复现步骤、检查范围与限制见
[`layout/highspeed_nrz_pvt/README.md`](../../layout/highspeed_nrz_pvt/README.md)。
该入口在独立新目录内复用既有的 GF180D PCell、Magic、Netgen 和 KLayout 流程，
不修改 2026-10-20 的脚本和基线版图。选定配置是独立手写的物理连接，LVS 的
电学参考另外读取 `analog/highspeed_nrz_pvt/`，并非从同一份连接表生成两边自证。

| 脚本 | 作用 |
|---|---|
| `run.py` | 独立物理配置、6 V 高阻多晶硅 PCell、DI 局部布线、衬底接触条、完整 DRC/LVS/PEX 与 GDS 反例 |
| `audit.py` | 全网络 R 提取覆盖、MOS/三端电阻区分、RC 折叠 LVS、逐器件几何与端子映射 |
| `correct_capacitance.py` | 以 GDS 回读 `.ext` 为权威数据显式组装 C；保留全部互连 R 和完整 PDK 器件 |
| `substrate_transfer.py` | 在提取的 VSS 电阻网络上计算体端自阻和对 MOS 体端的转移电阻 |
| `summarize.py` | 实际 GDS 的接触孔计数、DI 电容、面积、完整 PDK 电阻 DC 表和数量级计算 |
| `publish.py` | 按白名单发布精简证据；逐字节复制；拒绝覆盖不同内容；不复制完整 PDK |
| `validate_delivery.py` | 独立解析 `.ext`、RC/C/RCLUMP，读取实际 GDS 核对几何和反例，并验证哈希/日志 |

`--skip-klayout` 仅用于候选探索。最终 `final-r4` 未使用该参数。
该批次原执行脚本在 `build/highspeed-nrz-pvt-layout/final-r4/source_scripts/`，
公开副本位于 `evidence/highspeed-nrz-pvt/physical/scripts/`。

探索记录保留在 `build/highspeed-nrz-pvt-layout/`：

- `poly58-r1`：两路 58 µm 电阻，长 DI 和高阻体端返回路径；物理规则检查通过，但电学失败。
- `poly58-guard-r1`：只增加电阻上、下保护环接触；未充分降低与逻辑体端的共用衬底返回阻抗。
- `poly58-local-r2`：短 DI、连续衬底接触条；校正器因 DATA 无权重停止，保留失败输出。
- `poly58-local-r3`：DATA 的精确对地 C 显式落在 DATA；A58 仍未通过慢热接收余量筛查。
- `final-r4`：A48 / B58 的实际新 GDS 和新提取；包括独立 KLayout DRC。

修复校正器的依据是 DATA 网的耦合电容和 Magic 分配权重都为 0，而原 `.ext`
对地电容非零（两路均 0.513794 fF）。这里显式在 DATA 放置该完整对地 C，
没有创造分配权重。RC/RCLUMP 的逐节点对矩阵守恒仅证明记账，不能证明空间分布准确。
