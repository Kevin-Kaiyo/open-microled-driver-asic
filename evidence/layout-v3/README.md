# 新单像素版图证据

- `r4/`：第一版39MOS教学布局，物理DRC/LVS通过，完整RC启动失败。根目录旧文件保留作为相同版本历史入口。
- `r5/`：局部走线与8µm宽VSS修订；同39MOS，真实29/29 RC网络。MOS尺寸未变，电气判断读`evidence/analog-v3`和`evidence/startup-v3`。
- `joint-r2/`：r5模拟宏与新数字PWM/恢复存储宏的实际共同顶层；Magic/KLayout DRC、层次LVS、真实断线/短路负控、6512/6512网络PEX与RC短接拓扑审查。

所有版本均为裸测试核心，外置VSET/RSET/RBIAS/CCOMP/RRELEASE/RREFBLEED，无pad ring、ESD、POR、封装。占用矩形不等于可流片裸片面积。所有物理检查通过都不自动升级为完整芯片电气、工艺签核或光学测量通过。
