# 重建与证据边界

本轮是器件文献研究、原理图解、解析计算与待执行联合验证计划；不是新的器件/Driver 性能实验。旧模型和旧仿真结果保持原身份。

## 环境与命令

在仓库根目录运行。现有项目解释器路径为 `build/layout/venv/bin/python`；新机器可以自建 Python 3 环境并安装 `numpy matplotlib markdown`。CJK 绘图需要可用的中文字体，见绘图脚本。HTML 本身使用 PingFang SC 及系统回退字体。

```sh
build/layout/venv/bin/python scripts/microled_device_codesign_20261029/calculations.py
build/layout/venv/bin/python scripts/microled_device_codesign_20261029/figures.py
build/layout/venv/bin/python scripts/microled_device_codesign_20261029/report.py
build/layout/venv/bin/python scripts/microled_device_codesign_20261029/validate.py
```

第一项只计算解析示例；第二项绘制原创机制图；第三项由模板和证据 JSON 生成 `README.md` 与 `index.html`，并绘制同一研究内的前后数据；第四项检查单位、吞吐、统计边界、图文引用、来源和文件哈希。未运行 ngspice、TCAD、DRC、LVS 或 PEX。

本地预览：运行 `python3 scripts/microled_device_codesign_20261029/preview.py`，打开 `http://127.0.0.1:8772/docs/research/microled-device-codesign-20261029/index.html`。服务只绑定本机环回地址，只提供 docs/evidence 文件，拒绝 build/私有原文和目录列表；端口占用时用 `--port` 指定空闲端口。

## 公开与私有内容

- `evidence/microled-device-codesign-20261029/`：事实台账、计算、图台账和验证回执。
- `docs/research/microled-device-codesign-20261029/`：中文报告、原创图和验证方案。
- `build/microled-device-codesign-20261029/literature/`：本机核查用原文与原始页面；许可未逐图确认，不进入公开 Git/Release。下载 URL、定位与哈希见原文核查记录；新机器从公开原始站点按许可重新获取。
- 已有 Lin 数值表与派生图复用自 `evidence/microled-dynamic-20261029/`，其源数据许可、哈希和既有 Release 不变。没有再次上传整套历史波形。

本轮没有大型新原始仿真数据需要归档；公开文件经检查后按阶段同步到既有 GitHub 仓库。Git 备份范围不包含上述私有原文、Python 环境、完整 PDK、仪器或硬件样品。

## 什么不算复现成功

能够生成结构图和重新计算 pJ/bit，不能证明净 3.2 Gb/s 光链路通过。新负载模型需单独编号，完成 IV/PI、复数阻抗/幅相、留出条件和大信号验证；之后再启动完整 A/B/C 回归。硬件 BER、制造成本与良率依然需要实际测试及工艺方数据。
