# GitHub 小输入恢复验证记录

源提交 9d84753bae099e497a813f9097b1ce6eeb2f2df7；Release driver-robustness-20261024。
六组资产真实从 GitHub 下载，archive 与每个成员 SHA256 校验后，恢复到同机新 checkout。

- NRZ FF −40°C / 3.65V high DC：108.566138350767 µA，与归档 analysis/result 一致。
- PWM dc_board100n DC：99.733511476514 µA，与归档 result 一致。
- physical hv-A8-r3 和 hv-r2：已有证据回读分别105与205个成员通过；未重跑 EDA。

fresh/ 保存两个新DC的结果、分析、网表、日志、约1.1KB合计的新DC压缩波形，以及物理回读JSON。
archived-reference/ 保存从Release恢复并验证的参考JSON；没有历史原始波形和大模型副本。
commands/ 保存完整实际命令日志，命令数组与退出码在 recovery.json。
同机共享原工作区Python环境和系统ngspice/iverilog；未证明另一台干净机器的依赖安装。
NRZ仅在进程中重定向生成摘要到build/recovery-checks；没有更改电路、模型、判据或已提交脚本。
manifest.json逐文件列出该紧凑证据包SHA；recovery.json作为上层回执另行封存，不参与递归自hash。
