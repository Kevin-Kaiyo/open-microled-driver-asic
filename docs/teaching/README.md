# 教学资料入口

先读[最新研究前提检阅](../review/README.md) / [10 页 PDF](../review/single-pixel-audit.pdf)，再按整体架构、数字 PWM、六 MOS、LED 模型和版图的顺序学习：

- [28 页 PowerPoint](open-microled-single-pixel-teaching-v2.pptx)
- [中文技术讲义 PDF](open-microled-single-pixel-report.pdf) / [HTML](report.html)
- [教学内容与练习](content-plan.md)

PPT 和讲义保留为 2026-10-03 全面检阅之前的教学快照，本轮没有重写这两个二进制文件。以下解释以新检阅为准：pA 关断电流受数值 GMIN 影响；稳态小纹波和峰值尚未形成物理指标；版图前后 transient 差异包含 diffusion geometry 和 wiring RC；名义 RC 电流相对 100 µA 有 +1.2365% 偏差；理想参考支路关闭 LED 后仍消耗约 330 µW。下一步优先真实 LED 数据、精度/功耗预算与同一像素的边界验证。

当前证据层级仍为 RTL 仿真、晶体管仿真和 standalone 模拟 cell 的公开物理流程；完整数字物理集成、硅片和光学测量尚未完成。
