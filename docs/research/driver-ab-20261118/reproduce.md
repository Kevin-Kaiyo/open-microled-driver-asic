# 复现本轮 A/B 电路实验

本轮电路、网表生成器、实验结果和原始数据清单冻结于提交 `445863f722790d605654ed18bd77e864a79650d6`，对应版本标签 `driver-ab-20261118`。后续增加的传输工具、分段索引及报告来源链接勘误位于仓库 `main`。下面在新电脑上建立两个工作目录，分别保留恢复工具和冻结的科学代码。原始数据在 GitHub Release 公开发布后开放下载。草稿阶段的文件数量随传输进度变化，最终完整性以所有原始归档及成员的校验为准。[科学提交](https://github.com/Kevin-Kaiyo/open-microled-driver-asic/commit/445863f722790d605654ed18bd77e864a79650d6) · [本轮 Release](https://github.com/Kevin-Kaiyo/open-microled-driver-asic/releases/tag/driver-ab-20261118)

### 在新电脑建立复现工作区

准备 Git、已配置的 GitHub CLI 和 Python 3.12。重跑电路还需 NumPy、ngspice 47/KLU 及匹配的 GF180 模型。下列各段命令按顺序在同一个 shell 中运行。

```sh
git clone --branch main https://github.com/Kevin-Kaiyo/open-microled-driver-asic.git
cd open-microled-driver-asic
repo=Kevin-Kaiyo/open-microled-driver-asic
tag=driver-ab-20261118
science=445863f722790d605654ed18bd77e864a79650d6
work=../microled-ab-445863f
data=../driver-ab-20261118-download
canonical="evidence/$tag/raw-backup-manifest.json"
index="evidence/$tag/transport-v1.json"
git worktree add --detach "$work" "$science"
mkdir -p "$data/meta" "$data/archives" "$data/segments"
```

### 下载两种形式的数据

原始清单固定了 **55 个归档、9,956 个成员**。其中 44 卷以完整 `.tar.gz` 提供，另 11 卷按原归档的字节顺序分为 231 个 `.part-NNNN` 文件。每段为 32 MiB，每卷末段按实际长度保存。传输索引记录段的顺序、长度、SHA-256 以及对应整卷的 SHA-256。下载、拼回 11 卷并保留提取后的全部成员，数据目录和工作区合计约需 68.3 GB，另外还需给历史输入、模型和仿真留出空间。[传输恢复工具](../../../scripts/driver_ab_20261118/transport.py) · [分段索引](../../../evidence/driver-ab-20261118/transport-v1.json)

交付集合有 **277 个物理文件**，含 44 个整卷、231 段和两个 JSON 清单。建议用下面的 GitHub REST 命令分页列出文件名与资产 ID，每页最多 100 项。命令逐个将下载写入临时文件，下载成功后才改为正式文件名，可在中断后重跑。公开发布后可按标签查到 Release ID。[GitHub 发布资产与分页说明](https://docs.github.com/en/rest/releases/assets#list-release-assets)

```sh
(
  set -e
  rid=$(gh api "repos/$repo/releases/tags/$tag" --jq '.id')
  gh api --paginate "repos/$repo/releases/$rid/assets?per_page=100" \
    --jq '.[] | select(.state == "uploaded") | [.id, .name] | @tsv' \
    > "$data/meta/assets.tsv"
  test "$(wc -l < "$data/meta/assets.tsv" | tr -d ' ')" = 277
  while read -r asset_id name; do
    case "$name" in *[!A-Za-z0-9._-]*) exit 1 ;; esac
    case "$name" in
      "$tag-archive-manifest.json"|transport-v1.json) dest="$data/meta/$name" ;;
      *.tar.gz) dest="$data/archives/$name" ;;
      *.tar.gz.part-*) dest="$data/segments/$name" ;;
      *) exit 1 ;;
    esac
    if test -f "$dest"; then continue; fi
    gh api -H 'Accept: application/octet-stream' \
      "repos/$repo/releases/assets/$asset_id" > "$dest.partial"
    mv "$dest.partial" "$dest"
  done < "$data/meta/assets.tsv"
  cmp "$work/$canonical" "$data/meta/$tag-archive-manifest.json"
  cmp "$index" "$data/meta/transport-v1.json"
)
```

两条 `cmp` 均应返回 0，分别确认下载的原始清单与科学提交一致、下载的分段索引与 `main` 受版本控制的副本一致。如果后续校验指出某个文件长度或哈希有差异，可以先将它移出下载目录留存，再重跑上面的命令补齐。

GitHub CLI 也支持按名称下载单个已知对象。例如，下面这条命令可单取一个清单。整套验证以上述分页结果为准，避免受客户端所显示的资产数量限制。[GitHub CLI 下载命令](https://cli.github.com/manual/gh_release_download)

```sh
gh release download "$tag" --repo "$repo" --dir "$data/meta" \
  --skip-existing --pattern "$tag-archive-manifest.json"
```

### 重组 11 卷并校验全部 55 卷

以下命令从冻结工作区读取原始清单，从 `main` 运行恢复工具。先在内存中顺序校验各段及其整卷哈希，随后在已下载的 44 个整卷旁边补回 11 个标准文件名。最后逐卷校验整个集合，并打开每个归档检查成员。任一步报错，应先核对报错的文件再继续。

```sh
python3.12 scripts/driver_ab_20261118/transport.py verify \
  --canonical "$work/$canonical" --index "$index" --segments "$data/segments"
python3.12 scripts/driver_ab_20261118/transport.py assemble \
  --canonical "$work/$canonical" --index "$index" --segments "$data/segments" \
  --archives "$data/archives"
python3.12 scripts/backup/release_bundle.py verify \
  --manifest "$work/$canonical" --asset-dir "$data/archives"
python3.12 scripts/backup/release_bundle.py restore \
  --manifest "$work/$canonical" --asset-dir "$data/archives" --root "$work"
```

两个 `transport.py` 步骤的预期计数均为 **11 卷、231 段、7,641,889,654 字节**。集合校验覆盖 **55 卷、30,180,282,991 字节及 9,956 个成员**。本来就拥有全部 55 个整卷的读者，可以直接从 `release_bundle.py verify` 开始。科学提交中的清单 SHA-256 为 `14d0945eafbd210d53bf6e1157eb034a4896c2ae6edf0e0dd60b0e12ef7929b2`。[原始归档清单](../../../evidence/driver-ab-20261118/raw-backup-manifest.json)

### 恢复历史输入与 PDK

在冻结工作区内恢复上一阶段的输入，包括 `driver-interface-20261115` 的 B-protected_v6r，以及 `driver-pvt-20261117` 的 A 输入和 B 单位镜。恢复工具按 SHA-256 重建匹配的模型文件，并按记录的相对路径重建输入链接。如果目标已有不同内容，脚本会报告冲突并保留文件。下列 `/path/to/matching/MicroLED-PDK` 替换为本机匹配模型所在目录。后面的电路命令都在这个冻结工作区运行。[上一轮恢复说明](../driver-pvt-20261117/reproduce.html)

```sh
cd "$work"
python3.12 scripts/driver_ab_20261118/backup.py restore-inputs \
  --model-dir /path/to/matching/MicroLED-PDK
```

需要独立复算已归档的病例时，可另建工作区，仅恢复其输入及父阶段依赖，保留原始输出供逐项比较。

### 电路与接收评分

每个病例目录保留实际 SPICE 网表、输入码型、原生波形和执行日志。短窗检查命令边沿，完整帧按尺量接收幅度和采样时间两项余量。图中标明相对时间零点。所有能耗均覆盖网表内的七个独立源，A 的外部测量和数字校准功耗需要单独预算。

[返回图文报告](index.html)

### 复跑 A 与 B

A 的逐工况实际检测压降、量化读数、搜索路径和最终修调码可以从每个工况的证据追溯。留出工况的电压按实际网表与顶层 pvt 元组核对，沿用模板中的 rails_V 只描述来源。测流校准用外部算法和无源网络，附录列出模拟边界。[A 的执行顺序与误差说明](../../../evidence/driver-ab-20261118/a/methods.md) · [校准搜索独立审核](../../../evidence/driver-ab-20261118/a/calibration-audit.json)

B 先复跑 44 MOS 保护基线，再依次运行保护阻值、4/2 µm 合并版和最终 6/3 µm 版本。先生成 `merged220c10` 的九角 DC 与成对保护窗口及三个完整协议，之后从同名父网表生成 6/3 µm 版本。下列以慢热低压整段故障为例，需已恢复父输入与历史模型。如果从缓存重算，先在独立工作区生成同名输入。

```sh
python3.12 scripts/driver_ab_20261118/b/run.py merged220c10 --grid ss_hot_low --mode full
python3.12 scripts/driver_ab_20261118/b_final.py full ss_hot_low --variant unit6-r260-n4ff36
python3.12 scripts/driver_ab_20261118/b_final.py full ss_hot_low --variant unit6-r260-n4ff36 --steps 80
python3.12 scripts/driver_ab_20261118/b_final.py dc all --variant unit6-r260-n4ff36
python3.12 scripts/driver_ab_20261118/b_grid.py unit6-n4ff36 build/driver-ab-20261118/b_final/unit6-r260-n4ff36 --final-grid
```

每份故障网表的 DISABLE 在 0.64 µs 断言、1.28 µs 释放，到 5.12 µs 结束。采样算法在故障前训练，此后还需通过单侧 0.37 UI、7.5 µAeq 的持续余量检验。普通首帧长度为 2.56 µs。对数据修正过程中保留的不同拓扑，可查看原实验与独立计分的配对表。[B 支线结果](../../../evidence/driver-ab-20261118/b/full-frames.md) · [全帧复算说明](../../../evidence/driver-ab-20261118/b_review/README.md) · [最终电路所有端口与接收指标](../../../evidence/driver-ab-20261118/matched-frames.json)

### 检查模型与能耗

```sh
python3.12 scripts/driver_ab_20261118/verify.py --deep --final
python3.12 scripts/driver_ab_20261118/b_review/check_stage.py
python3.12 scripts/driver_ab_20261118/review_unit6.py
python3.12 scripts/driver_ab_20261118/metrics.py
python3.12 scripts/driver_ab_20261118/storage_ledger.py
```

独立评分直接读取原生时间点，以两个并联一阶滤波器的加权差重建等效级联响应。数字正确与全部余量合格分别核对。36 fF 前馈版本有一项继承自 31.275 fF 模板的电容首末储能诊断字段，随附修正表依实际网表电容和端点压差重新计算。七个源端口的积分独立读取实际 SPICE 电压、电流。[首末储能修正明细](../../../evidence/driver-ab-20261118/storage-ledger.json)

网页源文档为本目录的 README.md，使用 `scripts/driver_ab_20261118/render.py` 与 `print.mjs` 生成网页和 PDF，图表使用报告目录 assets 下的本地文件。

本轮审核了 484 个带病例清单的求解，包括 329 个直流、129 个短窗和 26 个完整帧或完整双帧病例，另核对 1494 个直流扫描点的网表、模型和原始电流。重复标定、单因素对照和失败结果均包含在内。最终 B 慢热工况用每 UI 40 与 80 个最大步长分段重算，第二帧时间余量差约 0.002 ps。全阶段原始文件分为 55 卷、9956 个归档成员，可依清单逐文件恢复。[完整性审核](../../../evidence/driver-ab-20261118/validation.json) · [最终慢热细步长独立评分](../../../evidence/driver-ab-20261118/b_final/unit6-r260-n4ff36-ss_hot_low-full-s80.json) · [原始归档清单](../../../evidence/driver-ab-20261118/raw-backup-manifest.json)
