# NRZ 晶体管实验与存储记录

最新正式批次：`build/highspeed-nrz/run-0xqxvspp`。中文说明见 `docs/research/highspeed-nrz-20261019/index.html`。

- `summary.json` / `summary.csv`：统一比较；`analysis.json` 在原始批次中保留完整逐端子及逐电源结果。
- `numerical-diagnosis.json`：数值失败与修复；严格对照及失败日志保留。
- `numerical-comparison.json`：正式批次的步长/积分器交叉检查。
- `mechanism-check.json`：静态曲线、电荷与简化动态解析计算。
- `receiver-sensitivity.json`：相同电气波形下的假设光学/接收参数扫描。
- `window-check.json`：PRBS9 连续两周期能量敏感性。
- `storage-summary.json` / `cleanup-receipt.json`：用户授权的冗余生成物优化范围、哈希与实际空间记录。

## 2026-10-19 中间生成物优化

删除已被新版正式结果替代的旧预实验成功波形，保留旧输入、网表、日志、结果摘要和原始哈希。删除的波形需重新运行冻结网表才可重建；不是将新版波形当作旧版的字节一致备份。旧批次有 CLEANUP-NOTICE.md 标明文件可用性变化。

其余诊断、失败和原型波形无损压缩：完整解压后按原始 SHA-256 验证，再移除未压缩副本。正式结果、独立数值对照、窗口检查、PDK、Lima、版图与既有工程资料均保留。

大批次请先检查可用空间：建议留出至少 6 GiB，并以 1–2 个并行 worker 运行；极端工艺/温度/供电角落的自适应时间步可能生成很大的波形。原始 `.dat` 到 `.gz` 的转换需要临时空间。不要用递归清理整个 `build/` 的方式腾出空间。

- `analysis-audit.json`：独立结果审阅及低速采样边界的绝对时间复算。
- `delivery-validation.json`：交付数据、训练隔离、能量恒等式与报告链接检查。
- `delivery-manifest.json`：脚本、报告和紧凑证据的 SHA-256；后处理源码冻结在正式批次 `analysis-sources/`。
