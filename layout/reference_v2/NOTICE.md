# 来源与范围

项目独立电路/布线；公开 GF180MCU PCell 来自本地锁定完整 PDK，
原 PDK 及设计规则的 Apache-2.0 许可与来源声明保留原样。
版本、来源提交和规则文件 SHA-256 见 `layout/pdk-lock.json`。

新物理输入以电气候选明确冻结后生成的 JSON 为准。独立模块 GDS / DRC /
LVS / PEX 不是顶层芯片、pad/ESD/封装、硅测量或光学验证。

PDK 中存在固定 PNP/NPN primitive，尚未纳入此 MOS-only 新流程。
PNP 模型端口为 C/B/E，collector 接公共 p-substrate；NPN 为 C/B/E/S。
不能因为器件库存在就宣称完成 bandgap 或其版图验证。
