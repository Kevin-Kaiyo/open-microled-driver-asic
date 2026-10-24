# 来源与许可证

本目录是 open-microled-driver-asic 的独立实验实现；项目代码适用仓库根目录 MIT 许可证。
版图脚本从本仓库已经审计的 `scripts/highspeed_nrz_pvt_layout/` 与
`scripts/highspeed_nrz_layout/` 派生，原文件和原 `final-r4` 输出保留不变。

使用的 GF180MCU D PCell、模型、DRC/LVS deck 来自 `layout/pdk-lock.json` 固定的公开 PDK，
保留 Apache-2.0 通知。本目录不再分发完整 PDK，也不改变上游 PCell。
`LICENSE-APACHE-2.0.txt` 为相关上游依赖许可副本。

新增 6 V 器件必须实际使用 `nfet_06v0` / `pfet_06v0` PCell，不能只改变 SPICE model 名称。
其真实 GDS 重新提取后独立对照电学源进行 LVS；物理来源和脚本 SHA-256 随新 run 保存。
