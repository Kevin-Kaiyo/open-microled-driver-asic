# MicroLED driver ASIC 审查：实际操作与当前状态

**更新：2026-10-10。首版研究说明已完成；本轮只补过程可见性与入口，没有启动后续研究或仿真。**

## 去哪里看本任务

受支持的 Codex app 工具已核实以下两个条目，名称按应用返回原文记录：

| 条目 | 登记位置／状态 | 关系 |
| --- | --- | --- |
| **重写 MicroLED 驱动研究说明** | Tasks；task ID `01a11dba-1514-7652-ac26-4497d39e3092`；projectId为空，cwd为本仓库；本轮active | 本次审查与重写的过程、交付及这份补充说明所在任务 |
| **搭建 MicroLED Driver ASIC 学习平台** | 项目 `open-microled-driver-asic`；task ID `01a10098-3401-76f0-9b45-b37bfb7ccb61`；当前idle | 之前实现单像素与控制实验的任务；不是本次审查聊天 |

项目 `open-microled-driver-asic` 的登记 ID 为 `732919cb-5172-480b-9abc-24b15fcde97f`，登记路径为 `/Users/kimmy/Projects/open-microled-driver-asic`。项目归属来自 `list_projects/list_threads` 返回，**没有把文件目录直接当作侧栏项目**。2026-10-10 的 `navigate_to_codex_page` 已返回 `navigated=true`，打开的是“重写 MicroLED 驱动研究说明”。未做屏幕截图核验，也没有单独核验设备型号；没有读取私有会话数据库。

随后请求在本任务面板显示此日志，`open_in_codex` 返回`queued`；因此只确认请求已排队，尚未确认日志标签已在屏幕上显示。也可直接使用聊天中的文件链接阅读。

如果在项目下只看到“搭建…”任务，可在 Tasks 找“重写…”任务。两条记录使用同一工作目录，但应用登记的项目归属不同。

## 目标与任务要求

把难以理解的现有报告重写成研究论证：先说明具体问题、实际结论与证据等级，再解释电路和模型为何这样设置、参数来源／单位、软件与实际配置、实验输入／过程、结果图、失败／修正及下一验证。每个重要结论要能追到配置、输出和证据。

边界是只读审计原代码／结果，可新增文档和独立图表；不改电路、模型或实现代码，不安装工具，不实施硬件，不覆盖旧运行，不推送GitHub。静态I–V、假设动态、RTL、晶体管、物理检查、硅片与光学证据分别记录。

## 首版审查此前实际做了什么

以下是本任务已有操作与存档记录，**不是2026-10-10新运行的实验**：

1. 读取Git状态、HEAD、AGENTS.md及说明，建立commit `781ceb266eb1f1dc16780d806cdcd0d5005716ae` 基线；初始clean，保存649个tracked文件hash。仓库未找到额外`.agents/`、`.codex/`指令目录；相关memory只作历史背景，未写memory。
2. 并行只读核查LED／偏置、PWM→buffer→PEX路径、旧run身份与失败历史。读取实际SPICE、runner、PDK locks、source CSV／model-card、冻结testbench、原日志、summary和projection ledger；核对公开论文／数据定位。
3. 从现有CSV、summary和保存的最低码waveform独立生成五图：电路、I–V比较、PEX范围、波形、静态失败／延拓依赖。没有调用ngspice、Icarus或Magic重跑实验。
4. 写中文研究说明和10项疑点；使用已有Markdown／Chrome生成HTML和12页PDF。检查各节A4高度、横向溢出和部分页面视觉；核对本地链接、figure input与raw waveform hash。
5. 再审查纠正温度包络、面积分母和20pF延拓解释；更新两个阅读入口，保留原报告、原代码和原结果。本任务自身的Library上传尝试未获确认；随后仅核查受支持流程，没有再次传输附件。后来光链路任务成功保存同一PDF，父线程已交付用户，见下方更新。

具体存档：[初始hash快照](snapshot-inputs.json)、[图表输入与方法](deliverable-manifest.json)、[审查验证记录](audit-validation.json)。派生排版记录在`build/research-audit-20261008/`。

## 关键发现和已纠正的解释

| 发现／纠正 | 实际支持范围 |
| --- | --- |
| 4×4是16个logical positions；电气／物理仍单像素 | 完整帧功能模型不等于16像素晶体管或阵列版图验证 |
| 公开实测来源只导入一条静态I–V曲线 | 100µA插值约3.768V；项目没有同器件动态、温度或光学模型。原论文另有高速／光学实验，未赋给本电路 |
| actual joint PEX是12 MOS signal cutout | 包含真实末级六MOS和模拟六MOS；PG/body、34邻居仍简化，非完整芯片PDN |
| 假设RLED=10kΩ下88.266µA，失败±5% | 数值求解完成不能改称工程性能通过；这是边界探针，非实测线阻 |
| 假设20pF最低码面积通过仍依赖未测域 | 约18.455%的signed conduction charge在低端正向延拓；该case未进入reverse，不构成真实dynamic qualification |
| robustness面积分母与control不同 | robustness取同条件duty256 transient平均；control才取独立full DC，不能笼统写DC分母 |
| synthetic `.temp`同时改变MOS和diode | 三温度包络不是MOS-only温漂；真实静态表则固定未知温度曲线 |

还核查并保留了历史入口位置修正、signed C投影、slew超限／OOM和窗口终点ULP失败。它们是既有历史，不是本轮新修电路；未证实的归因及建议在报告中另标。数据发布日期混淆也在新说明中纠正，原model-card保留。

## 完成输出与阅读入口

- [12页研究说明PDF](report.pdf)／[HTML](report.html)／[Markdown](report.md)：问题→模型／配置→方法→结果→失败／修正→下一验证。
- [10项技术疑点](questions.md)：每项列已证实事实、可能原因和能区分原因的下一验证。
- [本目录说明](README.md)及仓库[README](../../../README.md)、[研究入口](../README.md)。

PDF本轮重新核对：**1,907,480 bytes**，SHA-256 `4099b3ee69b3cd90ad18016fdd6070462371725df69057863949ee13ab4fc3ef`，12个page objects；文件内容未变。首版版面验证来自已有记录，本轮没有重新排版。

## 2026-10-10 本轮补充动作与未解决项

本轮读取当前Git状态／HEAD、现有说明与验证记录；重新比对649个原tracked文件hash、读取PDF字节数／hash／page对象。HEAD仍为`781ceb2`，相对原基线仅两个既有阅读入口变化。通过受支持app接口核实任务／项目登记、读取本任务与旧搭建任务的可见记录，并导航到审查任务。新增这一份过程／状态日志，更新两处阅读入口；没有新建任务、修改报告内容、运行研究实验或推送。

**未解决的研究项**：真实reference／compliance与startup、独立fault关断、完整PG/body／邻居网络、同器件动态／低电流／温度及光学测量、物理阵列。报告中的下一验证和复现命令均是建议／入口，尚未由本审查实施。

**附件交付状态（2026-10-10纠正）**：同一Mac的光链路任务后来已成功保存本PDF，文件名`MicroLED_Driver_ASIC_研究说明.pdf`，Library ID为`libfile_8166351935c481919177889dff3e2678`。[保存回执](/Users/kimmy/Projects/microled-optical-link/reports/model-audit/2026-10-08/external-attachments/asic-library-save-result.json)的`status=succeeded`，字节数和SHA-256与本仓库PDF一致，本轮已核对。父线程确认已于2026-10-09交付用户，交付消息为`Sentinel_506f5579a120819197cbe4b66b2b60ba`；交付日期和消息标识来自父线程，保存回执本身只确认Library保存。此前聊天中“Library仍无保存确认ID”的整体交付状态已过时。

**本任务上传能力限制**：本任务自身的上传尝试仍未成功，当前受支持helper未提供接收父线程已准备session的独立传输入口。这一限制不影响后来已确认的附件保存与交付；本轮无需重新上传，也未操作共享UI导航。

**运行状态**：首版审查已结束。当前任务的active来自补说明；本任务没有启动后续研究、EDA仿真、硬件开发或定时跟进。应用返回旧搭建任务idle；这不是对电脑上所有进程或其他任务的全面监控。
