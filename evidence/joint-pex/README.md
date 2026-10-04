# v0.4 joint PEX 证据与安全重现

入口：[summary.json](summary.json)，[技术说明](../../docs/research/joint-pex.md)，[预设目标](../../docs/specifications/joint-pex-v0.4.md)。五个模型目录的文件已冻结；每个目录包含 `output_pixel_pex.spice`、端口/身份/边界 `summary.json` 及 `projection-ledger.json.gz`。`as_run_outputs_sha256` 对应 `as_run_output_directory` 的文件名；`public_artifacts_sha256` 对应当前公开文件名。ledger 解压后的 SHA 必须等于 as-run JSON SHA。

[extraction-method.json](extraction-method.json)包含真实 tool/PDK/input 身份、六次基线 extraction（hierarchy nominal + 五种 flat RC）和一次 fresh nominal 重现结果。[raw/](raw)包含完整 nominal hierarchy、flat nominal `.ext/.res.ext/SPICE`、fresh nominal raw 与实际命令/日志的压缩包。Gzip 只压缩字节，不归一数值；包内解压 SHA 与源路径明确记录。其他 RC corner raw 留 `build/joint-pex`，可从其 ledger 和公开小模型复算，并用实际脚本重提取。

当前环境使用已有 `build/layout/venv`、pinned 708-file physical PDK 和 native Magic 8.3.684。工具环境建立和 notices 沿用[analog layout 入口](../../docs/layout/README.md)、[physical notices](../physical/NOTICE.md)与 `scripts/layout/bootstrap_macos.sh`；这里不重置旧环境，也不覆盖旧 v0.3 evidence。以下命令实际实现 GDS读取、提取、归一和公开包构建，不是空脚手架。

使用新 run 名，保持冻结公共证据不变：

```sh
build/layout/venv/bin/python scripts/joint_pex/extract.py --run repro-hierarchy
build/layout/venv/bin/python scripts/joint_pex/extract_flat.py --run repro-nominal --rc-style nominal
build/layout/venv/bin/python scripts/joint_pex/export.py --run repro-nominal --hier-run repro-hierarchy --output build/joint-pex/repro-export-nominal
build/layout/venv/bin/python scripts/joint_pex/publish.py --export nominal=build/joint-pex/repro-export-nominal --output build/joint-pex/repro-package
build/layout/venv/bin/python scripts/joint_pex/verify_reproduction.py --run repro-nominal --model build/joint-pex/repro-package/nominal/output_pixel_pex.spice
```

重复 flat/export 命令，将 `nominal` 替换为 `hrhc/lrhc/hrlc/lrlc`，可实际生成其他四种 R/C。`--hier-run repro-hierarchy` 用于真实邻居 hierarchy 身份；模型不引用旧 analog RC 或旧 link。脚本拒绝复用已有 extraction/export 非空目录；publisher 对已存在模型文件要求字节相同，拒绝修改冻结文件。

本次实际 runs 为 `full-nominal-r1`、`flat-nominal-r3`、`flat-{hrhc,lrhc,hrlc,lrlc}-r2`；导出为 `export-nominal-r5` 与 `export-{style}-r1`。package/source hashes 见索引。`provenance.py` 是本次 as-run 原始包归档入口，固定指向这些 runs 和 `reproduce-nominal-r1`。独立 review 的命令及负对照见 `scripts/research/review_v04.py`。

[fresh 重现结果](reproduction.json)真实记录 raw/model 字节 hash 有差异：固定 seed 仍不能保证 `rnode .t0/.t1` 枚举稳定。重现 checker 用实际 `.res.ext` 的 `(physical net base,x,y)` 作可逆节点对应，严格比较 ordered ports/MOS properties、R/C 端点、数值和重数，没有数值容差。12MOS/45R/77C 电气图完全相同；交换端口、遗漏 C、微调 R 三种错误均被拒绝，旧公共 model 字节保持不变。

仅实际 signal cutout 经工程比较。完整 geometry 被读取，不代表全部芯片 nets 都以分布电阻求解，更不代表全数字 transient/IR/EM/substrate signoff。34 邻居端口及理想 PG 条件必须与模型一起保留。
