# NRZ 供电/电阻角/封装鲁棒性：独立物理工具

此目录仅处理真实核心 GDS、DRC/LVS/PEX、器件与衬底网络审计。
电气 stress 矩阵、接收判据和能耗由 `scripts/highspeed_nrz_robustness/` 处理；
物理通过本身不建立电气通过或寿命结论。

- `run.py`：独立物理连接配置与独立电学 reference；公开 03v3/06v0 PCell；完整 Magic/KLayout/Netgen 检查和实际 GDS 故障反例。
- `generate.py`：支持真实 3.3/6 V 器件类型并强制 6 V N/P 最小 L=0.70/0.55 µm。A 15.715 µm 宽 PMOS 取 15.72 µm，以保持对称节点在 5 nm 网格上。
- `audit.py`、`correct_capacitance.py`：完整 R/器件保留；以 GDS 回读 `.ext` 为 C 记账依据；保留未校正 native RC 和 RCLUMP 控制。
- `validate.py`：只读重算逐文件 SHA、实际 GDS channel/Dualgate 交集、负控多边形差异、LVS 完整日志和独立 DRC XML。
- `audit_pdk.py`：独立电阻角×温度 DC 与本体/端部电阻公式交叉校验；与主仿真用显式 `flock` 协调。
- `summarize.py`：从实际 GDS/PEX读取面积、C、体接触切孔及纯 VSS 网络转移阻。
- `body_path_audit.py`：独立解析实际 VSS 电阻图、节点坐标和器件几何，解释 A8 自阻=转移阻的叶节点关系，明确其非场解边界。
- `publish.py`：逐字节发布小型物理运行；白名单后缀，拒绝覆盖不同内容，保留来源与排除项。
- `render_layout.py`：以实际 GDS 多边形生成 PNG/SVG、保持 XY 真实比例，并标出 6 V / 3.3 V 器件。

执行依赖与原始来源见 `layout/pdk-lock.json`、`layout/highspeed_nrz_robustness/NOTICE.md`。
老 `scripts/highspeed_nrz_{layout,pvt_layout}/`、`final-r4` 均不改变；新工具仅复用旧 EDA 命令包装与指标读取。
所有核心的 package R/L/C 属于独立外部假设，不能作为手工追加的 on-chip PEX 寄生。
