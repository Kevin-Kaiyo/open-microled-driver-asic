# 备份与恢复助手只读复审

独立物理审查代理在本轮冻结后，只读审查 `recover.py` 和 `cleanup_staging.py`。未运行清理或修改实验。精确脚本字节由 `scripts/backup/reference-v2-20261024/source-identity.json` 记录。

- 普通模式要求完整远端读回与 DC 恢复成功。显式 `--after-files-restored` 模式用于解除 5 GiB 仿真存储门槛：必须先验证全部 29 个远端资产的读回 SHA、当前 asset ID/state/size/hash，重新验证原始 5760 文件 inventory、六组 4801 已恢复文件、576 相对链接、10 下载项和 Git HEAD/tree，以及下载/解包/建链接的成功日志。
- 删除集合仅为本阶段 `staging/assets` 内与清单完全相等的 22 个常规 tar.gz；逐个核对本地 SHA 和路径，随后移除空目录。保留活动原始输入、波形、失败、完整 PDK、恢复检出目录及下载副本。
- 早清理回执标注 `files_restored_DC_pending` 与 `dc_recovery_passed_at_cleanup=false`。恢复重试另建 retry1 输出和日志，保存首次存储门槛失败；所有 DC 与物理回读成功后才写最终回执。
- 审查未发现阻断项。必须使用普通 Python，不能以 `-O` 禁用 assertion。恢复口径为同一 macOS 主机、复用现有工具、六个小分组和两个 DC；无全矩阵、全波形恢复、新 EDA 或其他操作系统资格结论。
