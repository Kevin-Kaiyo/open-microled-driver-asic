# 阶段备份助手的原始副本

这些文件按实际执行的字节保存，用于审计本阶段操作。执行目录必须为仓库根目录下 `build/github-sync-reference-v2-20261024/`：先复制到该目录，再使用 `--help` 查看参数；不要直接在此源目录运行。固定范围、源提交、存储门槛和远端标签均有检查，禁止覆盖已有资产。

操作顺序：等待所有实验写入停止 → `prepare_selection.py --freeze-ack --source-commit <完整提交SHA>` → `pack.py --execute` → 推送指定提交与不可变标签、创建Release → `upload.py --execute` → `readback.py --execute` → 独立目录恢复与电路复跑。

`readback_parallel.py` 是保留的可选工具，不属于默认操作；其前提是独立控制与交接状态，不能直接作为首次回读命令。清单与回执在 `evidence/backups/`；它们说明实际执行范围。源码发布不意味着已备份被忽略的build、PDK或VM。

本次恢复执行 `recover.py`。首次小分组下载、4801 文件和 576 内部链接恢复成功，但 NRZ runner 因可用磁盘不足 5 GiB 在仿真前停止；该失败保留在恢复回执中，未降低存储门槛。为解除压缩暂存副本占用，增加显式流程：

1. `recover.py --verify-restored` 重新验证六组下载 SHA、当前恢复文件、相对链接及检出身份。
2. 仅在所有 29 个远端资产流式回读完成后，`cleanup_staging.py --after-files-restored` 预览，再加 `--execute` 清理 22 个归档暂存副本。此时回执明确为 `files_restored_DC_pending`，不表示电路复跑完成。
3. `recover.py --resume` 在 `retry1` 新目录重跑，保留首次失败日志；所有 DC 与物理证据回读完成后才生成最终 `recovery.json`。

不得使用 Python `-O`，因为守卫使用 assertion。清理工具从不删除原始实验、失败、PDK、恢复检出目录或下载目录。该操作说明描述的是实际阶段交付流程，不是通用定时清理器。
