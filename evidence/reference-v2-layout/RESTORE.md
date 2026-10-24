# 21-MOS 物理交付：验证与恢复

最终冻结结果是 `nrz-switched-keeper-joint-r1/`，不是 20-MOS 持续 keeper
失败对照。GDS SHA-256 为 `363e51112c60692538da2130c99664d22a24c15fa0ca9327c244494938b4065c`；
fullRC 为 `925b0e98ede116b7d3dc0c0f326aa1704fd08b84dd8cabe39cf03ae4ac4f3d6a`。

## 只读独立验证

在恢复后的仓库根目录执行。输入使用已发布完整证据，不依赖原 `build/`
位置、不调用 Magic/Netgen/Lima，也不重跑电气矩阵。只新增三个检查 JSON。

```sh
mkdir -p build/reference-v2-layout/restore-check
build/layout/venv/bin/python scripts/reference_v2_layout/validate.py --run evidence/reference-v2-layout/nrz-switched-keeper-joint-r1 --out build/reference-v2-layout/restore-check/artifacts.json
build/layout/venv/bin/python scripts/reference_v2_layout/network_audit.py --module evidence/reference-v2-layout/nrz-switched-keeper-joint-r1/J --out build/reference-v2-layout/restore-check/networks.json
build/layout/venv/bin/python scripts/reference_v2_layout/joint_audit.py --module evidence/reference-v2-layout/nrz-switched-keeper-joint-r1/J --out build/reference-v2-layout/restore-check/geometry.json
```

三项预期均 `passed:true`：123 manifest 文件与真实 mask/负控检查；638 R、
20 个连通网络；2 个宏图形保留、11 个非布线层严格相等。验证脚本的 SHA
另存于 `nrz-switched-keeper-delivery-manifest.json`。

验证环境实际为 Python 3.12.13、KLayout Python 0.30.12、NumPy；完整锁定
Python 依赖见 `scripts/layout/requirements.lock.txt`。跨目录不要直接依赖旧
venv 的绝对 shebang；可在新目录用 Python 3.12 重新建立环境：

```sh
uv venv --python 3.12 build/layout/venv
uv pip sync --python build/layout/venv/bin/python scripts/layout/requirements.lock.txt
```

## 最小重新执行物理流程

以下是 macOS / Apple Silicon 的现有执行路径，不是已验证的 Windows 原生
EDA 安装流程。所有命令从新仓库根目录执行，并使用未存在的新 run 名。

依赖：锁定完整 `build/layout/pdk/gf180mcuD`；Magic 8.3.684、Netgen 1.5.324
位于 `build/layout/tools/install/bin`；Python 环境；Lima `asic` / nerdctl；
公开 KLayout DRC 容器 `ghcr.io/librelane/librelane@sha256:f91b21d75f79871f9ccf37451020b5d2f7b3236881a997ff709c561e8280a30f`
（容器 KLayout 0.30.7）。`layout/pdk-lock.json` 固定 PDK 与工具版本。

原生工具和完整 PDK 可用 `bash scripts/layout/bootstrap_macos.sh` 重建；
其前提是 Homebrew、uv、Xcode SDK。重建或恢复后仍由 runner 检查 PDK SHA。
Lima 配置 `scripts/physical/lima.yaml` 原来固定挂载旧仓库绝对路径；跨目录时
须生成配置副本，将 `mounts[0].location` 改为新仓库绝对路径，并在项目自己的
`LIMA_HOME=$PWD/build/physical-flow/lima` 中创建/启动 `asic`。不要把旧路径的
VM 配置直接视为可移植。guest 镜像及容器 digest 已锁定。

```sh
build/layout/venv/bin/python - <<'PY'
from pathlib import Path
import yaml
root = Path.cwd()
config = yaml.safe_load((root / 'scripts/physical/lima.yaml').read_text())
config['mounts'][0]['location'] = str(root)
out = root / 'build/reference-v2-layout/restore-lima.yaml'
out.parent.mkdir(parents=True, exist_ok=True)
assert not out.exists()
out.write_text(yaml.safe_dump(config, sort_keys=False))
PY
LIMA_HOME="$PWD/build/physical-flow/lima" limactl start --tty=false --name=asic build/reference-v2-layout/restore-lima.yaml
LIMA_HOME="$PWD/build/physical-flow/lima" limactl shell asic nerdctl pull ghcr.io/librelane/librelane@sha256:f91b21d75f79871f9ccf37451020b5d2f7b3236881a997ff709c561e8280a30f
uv pip install --target build/physical-flow/linux-python -r scripts/physical/requirements.txt
build/layout/venv/bin/python scripts/reference_v2_layout/run.py --spec layout/reference_v2/vi-switched-keeper-pg-selected.json --run restore-module-check
build/layout/venv/bin/python - <<'PY'
from pathlib import Path
import json, shutil
root = Path.cwd()
published = root / 'evidence/reference-v2-layout/nrz-switched-keeper-joint-r1/J/source'
core = root / 'build/reference-v2-layout/restore-core-input'
(core / 'generate').mkdir(parents=True, exist_ok=False)
shutil.copyfile(published / 'C.gds', core / 'generate/hs_steering_robust.gds')
shutil.copyfile(published / 'C-physical-contract.json', core / 'physical-contract.json')
spec = json.loads((root / 'layout/reference_v2/nrz-switched-keeper-composition-selected.json').read_text())
spec['modules'][0]['folder'] = str(core.relative_to(root))
spec['modules'][1]['folder'] = 'build/reference-v2-layout/restore-module-check/V'
out = root / 'build/reference-v2-layout/restore-composition.json'
assert not out.exists()
out.write_text(json.dumps(spec, indent=2) + '\n')
PY
build/layout/venv/bin/python scripts/reference_v2_layout/compose.py --spec build/reference-v2-layout/restore-composition.json --run restore-joint-check
```

最后将上面的三条独立验证命令改为新 `build/reference-v2-layout/restore-joint-check`
输入即可。原 B 只需原样恢复 GDS / physical-contract；已发布顶层 `source/`
保留这两个输入。不要直接执行旧 `generate.tcl`，其中含当时的绝对路径。
新 runner 会依据当前仓库路径重建脚本。新 GDS 时间戳、日志和 RC provenance
路径可使字节哈希不同；原档案应逐字节验证，新执行应验证实际几何、连接与
DRC/LVS/PEX，不宣称未经比较的 bit-for-bit 重现。

## 必须保留的源文件

- `layout/reference_v2/vi-switched-keeper-pg-selected.json`
- `layout/reference_v2/vi_reference_switched_keeper-reference.spice`
- `layout/reference_v2/nrz-switched-keeper-composition-selected.json`
- `analog/nrz_reference_v2/vi_reference_switched_keeper.spice`（独立电气来源）
- `layout/highspeed_nrz_robustness/steering_driver-reference.spice`（原 B 独立电气来源）
- `scripts/reference_v2_layout/{run,generate,power_routes,compose,correct_capacitance,validate,network_audit,joint_audit,publish}.py`
- 图像复现：同目录 `{render,render_joint}.py`；10-MOS 对照还需 `{compare_power,render_power_comparison}.py`。
- 只读共享依赖：`scripts/highspeed_nrz_robustness_layout/{run,generate,audit,correct_capacitance}.py` 及 `scripts/highspeed_nrz_layout/run.py`。
- `layout/pdk-lock.json`、`scripts/layout/{bootstrap_macos.sh,requirements.lock.txt}`、
  `scripts/physical/{lima.yaml,requirements.txt}` 与所有公开来源许可证/NOTICE。

备份应保留完整 `layout/reference_v2/`、`scripts/reference_v2_layout/`、
`evidence/reference-v2-layout/`；`build/reference-v2-layout/` 包括未发布失败
证据，应另存原始资产。PDK、工具及 VM 是运行依赖，不被 compact 证据替代。

2026-10-24 12:10 UTC 收尾检查：host 没有本任务的 layout runner、Magic、
Netgen 或 KLayout 运行进程；项目 Lima 的 `nerdctl ps` 为空。所有本任务
物理输出写入进程已停止，未再执行版图或电气矩阵。
