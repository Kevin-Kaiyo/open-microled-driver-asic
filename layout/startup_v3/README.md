# 单像素测试宏：参考源、保护与像素的真实版图

这个宏包含 **39 只 MOS**：参考源10、TG隔离5、独立故障门10、LED并联夹紧2、像素6、官方`buf_2`6。另加官方`filltie`把缓冲器的阱/衬底接入电源。原始PDK库和Apache-2.0许可仍保留在锁定PDK中。

所有模拟器件都是现有尺寸；这轮主要修正实际物理互连。`startup_test_macro.spice`是LVS参考，`contract.json`包含每只器件D/G/S/B与尺寸、外部端口、版图位置、源文件哈希。

## 外部被动边界

| 器件 | 接法 | 名义值/状态 |
|---|---|---|
| VSET | VSET→VSS | 外部0.5V精密基准 |
| RSET | SENSE→VSS | 5kΩ，外部 |
| RBIAS | PB→VSS | 100kΩ，外部 |
| CCOMP | N2↔CTRL | 参数化外部补偿；原3pF，新电气评估30pF候选 |
| RRELEASE | LED_A↔FAULT_HB | 100kΩ，外部 |

这些外部引出端口**没有pad/ESD/封装/PCB模型**。因此外部3/30pF不是版图里已经制造的MIM电容；需要继续限定引脚总电容、串联电阻和板级环路。当前PDK确实提供`ppolyf_u_1k_6p0`与`cap_mim_2p0fF` PCell，片上化将引入工艺偏差、温漂、面积与寄生，不能继承当前理想外接元件的精度。

## 修订与失败

- `build/layout-v3/r1`：官方缓冲器VBUF/PWM_DRIVE的M2列距不足；调整列距。
- `r2`：DRC0但LVS失败：官方缓冲器单元本身不含阱接触，PMOS bulk浮置。相邻加入官方`filltie`后恢复。
- `r4`：DRC/LVS/GDS回读及独立KLayout DRC通过，但电气启动失败。所有信号贯穿664µm形成不必要耦合；REFOUT↔LED_K抽取8.24068fF，完整RC启动约0.5µA，超过1nA。
- `r5`：信号总线缩到真实端点范围；REFOUT和LED_K不再并排贯穿；VSS改8µm宽并在中部定义供电锚点，参考充电回流不再经过像素地支路。实际PEX REFOUT↔LED_K为0、LED_K↔VSS由54.26149降到15.86925fF。完整电气结果请读`evidence/analog-v3`，物理检查通过不能替代电气结果。

## 复现与审查

```sh
build/layout/venv/bin/python scripts/layout_v3/run.py --run your-new-run-name
build/layout/venv/bin/python scripts/layout_v3/negative_controls.py build/layout-v3/your-new-run-name
```

当前物理证据在`evidence/layout-v3/r5`，保留旧`evidence/layout-v3`根目录的r4资料。r5为39MOS、R/C数量以summary为准、29/29网络RC抽取，包括VSS/VREF/VSAFE/VBUF及器件bulk连接。原型没有pad ring、ESD、POR、封装或制造方接受的sign-off；KLayout main DRC不能独自证明密度、天线或流片资格。

最终外接电路的独立记录为`external-circuit-v3.json`：CCOMP候选改为30pF，并增加REFOUT→VSS的10MΩ泄放电阻，消除未上电节点浮置；这些变化不改变本宏GDS。最终数值结论以对应电气证据为准。

共同顶层在`evidence/layout-v3/joint-r2`：新RTL恢复存储/PWM宏与r5模拟宏已经实际接线；包含真实Metal4/Metal5公共电源及RAW_PWM、FAULT、PERMIT互连。该顶层先由Magic与KLayout分别检查，再由Netgen对独立PNL及模拟原理图做LVS。

联合全扁平PEX包含7277只MOS，其中很多来自官方`fillcap`去耦填充单元。默认网络电阻提取只展开242/6512节点；使用Magic的`res:drive`属性、在每个已有节点坐标指定提取起点后展开6512/6512。原GDS及原始器件没有修改，`pex-audit.json`记录属性完整性和把RC短接回源拓扑后的独立LVS结果。完整RC模型保留36588只电阻和30230只电容。这个拓扑审查不替代完整共同顶层瞬态、电迁移或封装验证。
