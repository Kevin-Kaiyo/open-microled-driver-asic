# 共同 top 的公开证据

[`summary.json`](summary.json) 是单像素 v0.3 共同 physical top 的入口：两冻结宏的实际 Metal/Via join、whole-top DRC/LVS、19 端口、label-free 金属连通图及真实物理负对照。[实现及重现说明](../../layout/integration/README.md)记录每项证明范围和首次失败原因。

[`pixel_integrated.gds`](pixel_integrated.gds) 为实际共同 GDS；[`pixel_integrated.spice`](pixel_integrated.spice) 是完整 GDS extraction。`pixel_integrated.ext` 保留 actual hierarchical merge records，便于复核供电/substrate 边界。数字 SC 内部 MOS 拓扑也在此 extraction/LVS 中；原 v0.2 digital abstract-LVS 证据保持原来的范围。

[`pwm_link_rc.raw.spice`](pwm_link_rc.raw.spice) 保留 route helper as-run node；[`pwm_link_rc.spice`](pwm_link_rc.spice) 为接口使用的四端 normalized 模型。`link-rc.json` 的 `outputs_sha256` 是 **run-directory 名字**，`public_artifacts_sha256` 是**公开文件名**；两者不能按同名混用。substrate 归一依据及仍采用 ideal substrate 的边界见 [`substrate-proof.json`](substrate-proof.json)。这不是完整 joint PEX。安全复现入口为 `scripts/integration/characterize_link.py`，先生成私有成果，再由 publisher 验证并公开；旧 `extract_link.py` 保持历史 as-run 身份。

`negative-controls/` 是有意制造的电气错误被成功拒绝的证据；prototype 非预期失败的 raw 日志保留于忽略的 `build/integration/`。独立复核及下游接口仿真由各自 evidence 入口给出，不升级 silicon/optical/制造状态。
