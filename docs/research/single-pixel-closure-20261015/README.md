# 单像素启动、保护与版图验证 · 2026-10-15

先读 [18页研究报告](report.pdf) 或 [HTML](report.html)。[二维版图查看器](layout/viewer.html)支持平移、缩放和图层选择；浏览器需通过本地HTTP打开，以加载真实GDS几何数据。

本轮最终电路为：r5完整RC模拟测试宏，39 MOS；外部VSET=0.5 V，RSET=5 kΩ，RBIAS/RRELEASE=100 kΩ，CCOMP=30 pF，SENSE附加电容预算30 pF，REFOUT→VSS放电10 MΩ。数字宏包含原PWM和保护恢复存储。电气模型仍为合成MicroLED，目标为100 µA。

| 完成的工作 | 可追溯入口 |
| --- | --- |
| 旧近零电荷数值问题；旧4.909%失败保留 | [修订判据与交叉求解证据](../../../evidence/startup-v3/numerical/README.md) |
| 新完整PEX参考/保护，270 DC、17瞬态、12 AC及扰动 | [模拟证据与复现](../../../evidence/analog-v3/README.md) / [最终选定17组](../../../evidence/analog-v3/final/summary.json) |
| r5模拟宏，39MOS、29/29网络RC、两套DRC和LVS | [摘要](../../../evidence/layout-v3/r5/summary.json) |
| 数字PWM+恢复存储，9角STA/SDF | [摘要](../../../evidence/control-v3/summary.json) |
| 实际SDF时间戳到r5完整RC回放 | [最低码、停钟故障与恢复](../../../evidence/control-v3/coupled-r5-bleed10/summary.json) |
| 共同GDS、DRC/LVS及完整6512网络提取 | [joint-r2摘要](../../../evidence/layout-v3/joint-r2/summary.json) |
| 外接元件和端口合同 | [external-circuit-v3.json](../../../layout/startup_v3/external-circuit-v3.json) |

最终启动最大|LED支路电流|0.656338 nA；最大故障关闭303.39 ns。共同顶层全部7277MOS的动态回归**尚未完成**，模拟宏完整RC加数字SDF回放不等同于它。数字STA输出负载仍为72.91 fF假设，尚未回灌共同顶层连线。

需要继续处理：VREF的10%快边沿扰动造成60.16–147.24 µA瞬态，完整电源顺序、FAULT异步释放、POR/欠压、外部元件容差、pad/ESD、封装及统计失配。尚无制造方接受、硅片或光学测量。

## 重建本报告

从仓库根目录执行。使用现有含numpy/matplotlib/markdown的`build/layout/venv/bin/python`，不要假定系统Python具备这些依赖。EDA原始运行在`build/`，不可删除它们后声称完整复现来源仍在。

```sh
build/layout/venv/bin/python scripts/closure_v3/figures.py
build/layout/venv/bin/python scripts/closure_v3/data_figures.py --analog-tag final
build/layout/venv/bin/python scripts/closure_v3/report.py --analog-tag final --joint-summary evidence/layout-v3/joint-r2/summary.json --new-numerical evidence/startup-v3/numerical/pex-r5-bleed10M-ff-probe/summary.json
node scripts/closure_v3/print.cjs
python3 -m http.server 8770 --bind 127.0.0.1 --directory docs/research/single-pixel-closure-20261015
```

访问 `http://127.0.0.1:8770/report.html` 或 `http://127.0.0.1:8770/layout/viewer.html`。版图查看器显示模拟宏；共同顶层的实际图在报告第17页及`figures/joint-overview.svg`。

原实验与失败均保留，包含r4耦合超标、welltap缺失、Via2尺寸错误、默认提取覆盖不足和粗首步数值尖峰。文档审计通过不等于新增芯片资格验证。
