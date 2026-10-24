# NRZ 鲁棒性物理实验：实际 6 V 器件

本次把满摆幅路径迁移到真实公开 GF180 6 V MOS，并保留完整旧 LV 证据。
本目录中的电学 reference 独立于手写 physical-spec，最终 LVS 对照连接、型号和 W/L。
GDS/DRC/LVS/PEX 通过与电路接收性能、供电鲁棒性、寿命结论分开记录。

| 配置 | 实际运行 | 状态 |
|---|---|---|
| A 全 6 V / RIN 48 µm；B 混合 6 V/3.3 V / RIN 58 µm | `hv-r2` | 全部物理检查通过；A48 慢端性能边界保留 |
| A 全 6 V / RIN 8 µm | `hv-A8-r3` | 全部物理检查通过；独立电气评估 |
| A8 + 恢复长衬底接触条 + NMOS 上下 guard contacts | `hv-A8-ties-r5` | 全部物理检查通过；体端网络改善假设未成立 |

运行目录前缀为 `build/highspeed-nrz-robustness-layout/`，精简公开副本在
`evidence/highspeed-nrz-robustness-layout/`。公开证据包括实际 GDS、源 MAG、独立参考网表、
GEOM/C/RC/RCLUMP、原始/校正提取、日志、独立规则报告、脚本快照与 SHA-256。
最终 `selected-design.json` 对应 A8（`hv-A8-r3/A`）与 B58（`hv-r2/B`），物理 SHA 和入口见
`evidence/highspeed-nrz-robustness-layout/final-selection.json`；电气速率/压力结论另见 NRZ 报告。
初始 A48/B58 配置保留于 `selected-initial-A48-B58-r1.json`，接触增强候选保存于 `selected-A8-ties-r4.json`。

```sh
# 保留已有目录；--run 使用新名字。
build/layout/venv/bin/python scripts/highspeed_nrz_robustness_layout/run.py \
  --spec layout/highspeed_nrz_robustness/selected-A8-r3.json --run reproduce-A8-01

build/layout/venv/bin/python scripts/highspeed_nrz_robustness_layout/validate.py \
  --run build/highspeed-nrz-robustness-layout/hv-A8-r3 \
  --out build/highspeed-nrz-robustness-layout/recheck-A8.json
```

独立 KLayout DRC 使用现有 `asic` Lima VM 和固定容器镜像，实际版本 0.30.7。
若 VM 停止，可按原项目配置启动；原 `hv-r1` 失败日志记录该环境问题。
`hv-A8-ties-r4` 记录一次生成器 Tcl 括号错误，修复后在全新 r5 运行，没有覆盖失败输出。

完整提取包含每个电气网络（A9/B10）并保留完整器件内部模型。
实际 GDS 的 Dualgate 55/0 与沟道交集独立确认 A 的 6 个 6 V MOS、B 的 6 个 6 V + 3 个 3.3 V MOS。
所有新核心的断栅与电源短接反例都通过实际 GDS 修改，且均被 LVS 拒绝。

A8 的 VSS R-network 诊断表明，RIN.SUB 与 XN2.B 是不同坐标的不同节点；后者为单支路叶节点，
导致只向 RIN 体端注入 DC 时两者电位相等。此提取图不能替代独立三维衬底提取。
新增真实接触孔没有改变此关键关系，所以不宣称 body-return 修复。
详见 `body-path-audit.json` 与中文物理章节。

公开约束：薄氧 DC gate-node 3.63 V、真实 6 V 器件采用本项目保守 6.0 V 筛查。
瞬态全端子对筛查不等同 foundry lifetime signoff；package、pad/ESD、EM/IR、全芯片密度/天线、
硅片和光学实测仍未闭合。原始来源与许可见 [NOTICE.md](NOTICE.md)。
