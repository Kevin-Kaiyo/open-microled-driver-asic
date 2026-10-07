# Frame experiment v0.1 证据

日期：2026-10-07。功能帧模型与实际单像素PWM、冻结nominal selected signal PEX连接。本轮没有新增接收器RTL、阵列、reference generator或物理提取。

- [summary.json](summary.json)：32个完整RTL frame／8,192 slots；正常7命令、47笔无效交易及timeout；3 transient、2 circuit DC、1 independent LED calibration。
- [frame-metrics.csv](frame-metrics.csv)：每个完整PWM frame的电荷、平均电流与量化分母。
- [validation.json](validation.json)：不导入runner或frame model的独立CRC、时序、raw积分与hash复算。

```sh
uv run python scripts/control/run.py --publish-evidence
uv run python scripts/control/validate.py
```

需要本项目已锁定的完整PDK路径 `build/layout/pdk/gf180mcuD` 与 `iverilog`、`vvp`、`ngspice`。`make setup`仅获取模拟model subset，不会单独完成physical PDK准备；已有完整环境与版本见[layout flow](../../docs/layout/README.md)。

raw与实际输入快照在summary声明的唯一 `build/control/frame-*`。每次执行创建新目录，成功摘要可更新；旧run及失败输出留在build。公开摘要含其hash，不包含完整长波形；独立数值复算需使用本机对应raw或重新运行。

47笔无效交易：bad CRC／截短complete transaction／duplicate／future timestamp／乱序各7笔；expired command5笔；partial timeout7笔。40笔交易被拒绝，7笔未结束的partial assembly超时丢弃；不混称47笔CRC失败。它们不刷新旧命令有效期。功能active帧和实际RTL事件与匹配正常路径一致，因此只共用一份相同电气输入的clean transient，不虚增fault transient数。

16个logical位置仅是4×4形状的Python功能数据，selected index=5只回放一个电气像素。12-bit command映射到duty0…256，最大误差界半slot；timeout在模型边界清零，实际PWM仍有声明的0.5µs输入等待。本轮typical／27°C／nominal RC、固定理想rails及邻居0V，不扩展既有物理/供电/负载模型适用范围。

工程解释见[进度报告](../../docs/research/control-experiment/progress.md)；先前v0.4证据保留原貌。
