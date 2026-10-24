# 阶段备份助手的原始副本

这些文件按实际执行的字节保存，用于审计本阶段操作。执行目录必须为仓库根目录下 `build/github-sync-reference-v2-20261024/`：先复制到该目录，再使用 `--help` 查看参数；不要直接在此源目录运行。固定范围、源提交、存储门槛和远端标签均有检查，禁止覆盖已有资产。

操作顺序：等待所有实验写入停止 → `prepare_selection.py --freeze-ack --source-commit <完整提交SHA>` → `pack.py --execute` → 推送指定提交与不可变标签、创建Release → `upload.py --execute` → `readback.py --execute` → 独立目录恢复与电路复跑。

`readback_parallel.py` 是保留的可选工具，不属于默认操作；其前提是独立控制与交接状态，不能直接作为首次回读命令。清单与回执在 `evidence/backups/`；它们说明实际执行范围。源码发布不意味着已备份被忽略的build、PDK或VM。
