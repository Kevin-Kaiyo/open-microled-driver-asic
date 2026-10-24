# 新参考模块的真实物理验证

`run.py --spec layout/reference_v2/<spec>.json --run <name>` 使用独立手写
物理连接配置和另一路电气 SPICE，生成新的公开 GF180MCU D 器件/布线。
新目录独占；不覆盖旧 PWM 39-MOS 或 NRZ hv-r2/B 核心。

- MOS 支持 `nfet/pfet_03v3/06v0`。长沟道器件采用至少 `L+12 µm`
  间距；按实际 W 抬高器件中心，确保下侧 guard/contact 与横向端口总线分开。
- GF180 PCell 仍直接来自锁定完整 PDK；6 V NMOS 四侧 guard 接触保留。
- 独立 Magic DRC、容器内公开 KLayout rule deck、Netgen LVS、GDS 回读
  LVS、每一逻辑网络 full-R、GDS polygon W/L/AD/AS/PD/PS、Dualgate mask
  交叉核验及实际 GDS 开/短路负控沿用已审计只读工具函数。
- C 使用 GDS 回读 `.ext` 的完整矩阵记账；R/MOS 不变。原 native RC
  完整保留，附 GEO / CAP / RCLUMP 控制。归一化 C 分配是显式空间近似，
  不是局部电磁场解；保留所有 body/supply R。
- 外部精密电压锚、偏置/设定/分压电阻、补偿及输出去耦由 `external_components`
  明示；它们不是此 GDS 内器件，也不计入片内 PEX。单独模块组合的模块间连线
  若只使用独立模块，模块间仍属于外部连接假设；`compose.py` 的联合 GDS
  则包含实际模块间布线，并从最终 GDS 重新执行完整提取。

`validate.py` 只读复核运行文件 SHA、完整 LVS 日志、独立 DRC XML、真实
GDS Dualgate 交集与负控多边形差异。`publish.py` 通过复核后逐字节发布
小型成功证据，拒绝覆盖内容不同的旧文件。

`compose.py --spec <frozen.json> --run <name>` 用真实已验证 GDS 拼接顶层，
不重画既有 B 核心高速布线。M4 竖向和 M5 横向桥包含实际 via3/via4，
经顶层重新 DRC/LVS/PEX。共享 net 只放一个标签，避免重复断开标签掩盖
真实断线；每条非 VSS 桥另做实际 GDS 开路负控。VSS 还通过公共 substrate
连接，单切金属并不必然导致 LVS 拒绝，因此不把它当作有效断地负控。
每个原模块的全部实际图形经平移后必须是最终 GDS 图形的子集，使用独立
KLayout region difference 检查。带 `pending` 状态的 spec 只允许
`--prepare-only`，不会执行最终 EDA。

`network_audit.py` 用独立节点导纳矩阵检查每个 R 分支和 MOS 端点的连通性，
也包括 PDK 电阻端点；给出端点到其命名网络锚的有效电阻，不用分支电阻之和替代。

`joint_audit.py` 独立检查原核心与参考的所有制造多边形保留，以及每个非布线
层合并图形严格相等。`compose.py` 保留 Magic 往返原件，将经审计丢失的 N+
拐角从原 GDS 原样恢复，然后从最终 GDS 执行 DRC/LVS/PEX，避免把格式转换
丢失当成允许修改原核心。datatype10 端口元数据单独重建，不是制造图形。

工具与模型来源、完整锁定值遵循 `layout/pdk-lock.json`。
