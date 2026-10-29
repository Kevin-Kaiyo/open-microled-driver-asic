# MicroLED 动态证据包：独立恢复与复现

本目录只复核公开数值数据、绘制参考面示意和保存证据账本。**不会运行 SPICE，不会改变历史 MicroLED 模型，不会产生新的 BER、接收余量或能耗结论。**

## 1. 恢复范围和依赖

从项目已验证里程碑对应的 Git commit 恢复本目录、`evidence/microled-dynamic-20261029/`、研究章节及以下既有文件：

```text
analog/models/measured-led/model-card.json
analog/models/measured-led/lin2026-yellow20-diamond-iv.csv
analog/models/measured-led/source-lock.json
analog/models/measured-led/NOTICE.md
docs/research/vcsel-reference-microled-dynamics-20261029/microled-dynamic-evidence.md
```

计算读取前两项；后两项保留静态数据的来源和许可证。无需完整物理 PDK、ngspice、Blender、Excel、pandas、openpyxl 或 SciPy。XLSX 用 Python 标准库 ZIP/XML 解析。

本轮实际运行环境：Python **3.12.13**、NumPy **2.5.3**、Matplotlib **3.11.2**。使用已有 `build/layout/venv/bin/python` 或单独创建 Python 3.12 虚拟环境；不要修改系统 Python。

```sh
python3.12 -m venv .venv-microled-evidence
.venv-microled-evidence/bin/python -m pip install numpy==2.5.3 matplotlib==3.11.2
```

以下命令全部在**项目根目录**运行。Windows 可使用等价的虚拟环境 `Scripts/python.exe`；脚本内部使用 `pathlib`。

## 2. 原始数据：一个 ZIP 输入，四个工作簿审计副本

公开原始数据子包以 [release-allowlist.json](../../evidence/microled-dynamic-20261029/release-allowlist.json) 的 `files` 为唯一打包入口，按原仓库相对路径解包。

当前 `extract.py` **验证并读取完整源 ZIP**，不能仅凭四个已提取的工作簿运行。完整 ZIP 已是历史研究输入，本轮小子包不重复放入；可从既有已校验归档恢复，或直接从作者 Zenodo 下载一次：

| 项目 | 固定值 |
|---|---|
| DOI | [10.5281/zenodo.20034288](https://doi.org/10.5281/zenodo.20034288) |
| 官方下载 | `https://zenodo.org/api/records/20034288/files/source_data.zip/content` |
| 本地路径 | `build/led-fit/lin2026-source-data.zip` |
| 字节数 | 86,472,338 |
| SHA-256 | `4873cfd00f6ffa7e9c75e425e4e41d230a7100e43e9e74bb67225e37ea09c3ee` |
| 作者发布的 MD5 | `755accbc45603195c376ffc70a776bc5` |
| 数据许可 | CC BY 4.0；保留本包 NOTICE |

以下下载示例不覆盖已有输入；已有文件也必须通过 SHA 检查。网络错误、校验失败均应停止，不用另一份未知数据“凑齐”。

```sh
.venv-microled-evidence/bin/python - <<'PY'
from pathlib import Path
import hashlib, urllib.request
p = Path('build/led-fit/lin2026-source-data.zip')
expected = '4873cfd00f6ffa7e9c75e425e4e41d230a7100e43e9e74bb67225e37ea09c3ee'
if not p.exists():
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix('.download')
    urllib.request.urlretrieve('https://zenodo.org/api/records/20034288/files/source_data.zip/content', tmp)
    assert tmp.stat().st_size == 86472338
    assert hashlib.sha256(tmp.read_bytes()).hexdigest() == expected
    tmp.replace(p)
assert p.stat().st_size == 86472338
assert hashlib.sha256(p.read_bytes()).hexdigest() == expected
print('PASS: source archive')
PY
```

从本轮 raw-data Release 子包恢复 `build/microled-dynamic-20261029/zenodo-metadata.json`。本轮快照 SHA-256 为 `4ac7ce5a2c509b91491845db071f871b84da0c261578f08545fe4a7f90599640`。不要用实时网页默默替换冻结快照。若快照缺失，可另存 [官方 API](https://zenodo.org/api/records/20034288) 为新的版本并记录改变，但它不再是同一份逐字节恢复。

日期字段分别为：`publication_date=2026-05-05`；`created=2026-06-18T10:05:25.310369+00:00`；`updated=2026-06-18T10:05:25.539819+00:00`。创建日期不等于发布日期。

## 3. 中文图形字体

两个绘图脚本使用：

```text
build/fair-driver-v1/report-font/NotoSansCJKsc-Regular.otf
build/fair-driver-v1/report-font/LICENSE.txt
```

这是项目已有的共享字体依赖，**不在本轮原始数值数据 allowlist 中**。从此前字体依赖归档恢复；若没有，可从 [Noto 官方字体文件](https://github.com/notofonts/noto-cjk/blob/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf)下载，并保存其 [SIL OFL 许可证](https://github.com/notofonts/noto-cjk/blob/main/Sans/LICENSE)。目标字体 SHA-256 必须为 `2c76254f6fc379fddfce0a7e84fb5385bb135d3e399294f6eeb6680d0365b74b`；上游 main 分支可能变化，哈希不符时应恢复旧依赖，不能声称图片完全复现。当前许可证副本 SHA-256 为 `6a73f9541c2de74158c0e7cf6b0a58ef774f5a780bf191f2d7ec9cc53efe2bf2`。

SVG 使用真实文字；PNG 通过 Matplotlib 和显式 Noto 字体生成。无需 CairoSVG、Quick Look 或浏览器截图。

## 4. 顺序运行三个脚本

```sh
.venv-microled-evidence/bin/python scripts/microled_dynamic_20261029/extract.py
.venv-microled-evidence/bin/python scripts/microled_dynamic_20261029/make_evidence.py
.venv-microled-evidence/bin/python scripts/microled_dynamic_20261029/finish_ledger.py
```

1. `extract.py` 验证 ZIP，提取四本未修改工作簿，生成选定 S21/P–I/BW CSV，复算截止点并对照独立工作簿。成功标准：2001 点/曲线、所选 5 个偏置、截止重算差异 `<1e-8 MHz`，100 µA 两工作簿曲线一致。
2. `make_evidence.py` 使用既有静态 CSV 求局部 `rd`，生成电流源/电压源参考面原理图、纯 RC 说明计算及模型输入契约。200 fF、50 Ω 是假设，不是拟合参数。
3. `finish_ledger.py` 写来源账本和 manifest。**public-only 恢复不需要论文 PDF、原文图片或 HTML**：若这些私人原件缺失，脚本从 Git 中冻结的 `source-ledger.json` 保留已记录哈希，并明确记为“本机未重新核验”。若原件与冻结 ledger 都不存在则失败；不能伪造来源哈希。它不会联网下载论文，也不把保留哈希标成新读回。

数值 CSV 可按冻结 SHA 逐字节比对。SVG 可能包含生成时间与随机 ID；跨平台字体渲染也可能变化，故新图应核对轴、单位、连线与数值，不能强求所有图像字节相同。`validation.json` 是**原里程碑的验证记录**，三个脚本不会把历史人工视觉核查自动升级成新机器的完成状态；新恢复测试应另存日志。

先校验下载的 Release 与 Git 中冻结 manifest，再运行重建；重建会改写派生图和 manifest。不要用“重建后的新 manifest”证明此前下载的包正确。

```sh
.venv-microled-evidence/bin/python - <<'PY'
from pathlib import Path
import json, hashlib
m = json.loads(Path('evidence/microled-dynamic-20261029/manifest.json').read_text())
for path, item in m['public_files'].items():
    assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == item['sha256'], path
for path, item in m['raw_inputs'].items():
    if item['public_release'] == 'allowlisted':
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == item['sha256'], path
print('PASS: public source/evidence and allowlisted raw inputs')
PY
```

## 5. 公共 Release 精确 include / exclude

只将下列 **5 个文件**作为本轮 raw-data 子包成员，不递归打包整个 `build/`：

```text
build/microled-dynamic-20261029/yellow20_s21_bandwidths.xlsx
build/microled-dynamic-20261029/bandwidth.xlsx
build/microled-dynamic-20261029/frequency_response_low_current.xlsx
build/microled-dynamic-20261029/diamond-optical-power.xlsx
build/microled-dynamic-20261029/zenodo-metadata.json
```

前四本属于作者 CC BY 4.0 数值数据；最后一项是数据源身份、日期与许可的公开元数据快照。工作簿合计约 1.47 MB。完整源 ZIP 和共享字体是上述外部恢复依赖，不因未列入这 5 项就变成“不需要”。

以下现有文件明确排除，未来任何未列入 include 的新增文件也排除：

```text
build/microled-dynamic-20261029/lin2026-figure4-original.jpg
build/microled-dynamic-20261029/li2023-multiple-lifetime-v1.pdf
build/microled-dynamic-20261029/li2023-page4-private.png
build/microled-dynamic-20261029/private-evidence.md
build/microled-dynamic-20261029/reference-planes.svg.png
build/microled-dynamic-20261029/fontconfig.xml
build/led-fit/lin2026-article.html
build/led-fit/lin2026-article.txt
```

还排除 `__pycache__`、字体缓存、临时恢复 smoke 目录、Python 虚拟环境及下载失败临时文件。论文原图/PDF与数据许可证不同；“可从官网阅读”不等于可随项目再发布。

Git 另行保存本目录三个 `.py` 与本 README、研究章节，以及 `evidence/microled-dynamic-20261029/` 的以下确定清单；这不是 raw-data Release 的目录通配符授权：

```text
NOTICE.md
extraction-checks.json
manifest.json
power-and-old-proxy.png
power-and-old-proxy.svg
reference-plane-calculation.json
reference-plane-response.png
reference-plane-response.svg
reference-planes.png
reference-planes.svg
release-allowlist.json
response-contract.json
source-cell-extract.json
source-cell-extract.png
source-ledger.json
source-response.png
source-response.svg
validation.json
yellow20-bandwidth.csv
yellow20-optical-power.csv
yellow20-s21-selected.csv
```

## 6. 报告嵌入与来源定位

研究章节中的相对图/数据链接统一从 `docs/research/vcsel-reference-microled-dynamics-20261029/` 指向 `../../../evidence/microled-dynamic-20261029/`。因此可原样嵌入**同目录**的 `index.html` 或其他报告。若嵌入不同深度目录、博客或改变 HTML `<base>`，必须改写链接；不能直接复制相对地址。外部来源使用 HTTPS DOI/官网链接；私人原图只在 `build/.../private-evidence.md` 中。

来源定位：Lin 主文 Fig. 4a–d、Methods / Measurement method；Zenodo `yellow20_s21_bandwidths.xlsx` 的 `Bandwidths A1:D46` 和 `Shifted_Curves A1:AT2002`。25/50/100 µA 曲线位于 B/E/H 列；该表单位为 A，不能与历史 I–V 源表 mA 混用。Li 预印本页 3 Fig. 1、页 4 Fig. 2、页 6 Fig. 3、页 8 Fig. 5；Zhu 本轮只核对作者摘要，保留此证据深度限制。
