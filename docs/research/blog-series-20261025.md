# MicroLED 驱动研究过程：个人博客发布记录

日期：2026-10-25。研究资料截止：2026-10-24。**本阶段为既有研究的整理与发布，没有新增电路、RTL、版图或光学实验。**

发布状态：**已发布并完成线上回读**。Cloudflare Pages 对博客提交 `6dccf85` 的检查为 success；实际回读 52 个生产页面，以及 21 份图表、数据、说明页与来源索引，资源字节 SHA-256 与本地审阅版本一致。[部署与回读回执](../../evidence/publication/20261025/deployment-validation.json)。

## 阅读入口与内容

- [个人博客主页](https://kaiyo-blog.pages.dev/zh/)已增加研究系列入口。
- [完整系列](https://kaiyo-blog.pages.dev/zh/microled-driver-series/)包括十篇研究记录与三篇既有电路原理文章。
- [选定数据下载](https://kaiyo-blog.pages.dev/research/microled-driver-lab/data/index.html)与[公开来源/哈希索引](https://kaiyo-blog.pages.dev/research/microled-driver-lab/evidence-index.json)提供图表和数据身份。

| 顺序 | 内容 | 博客路径 |
|---|---|---|
| R00 | 研究起点、两主线与实际里程碑 | `microled-lab-00-research-journey` |
| R01 | Mac 原生工具、Linux 物理环境、安装与版本 | `microled-lab-01-environment` |
| R02 | 硅 CMOS、LED 材料、公开静态 I–V 与动态假设 | `microled-lab-02-materials-models` |
| R03 | 六 MOS、RTL/PWL、实际 joint signal PEX | `microled-lab-03-display-pixel` |
| R04 | 电流范围、headroom、最低码、参考源失败与替代 | `microled-lab-04-current-reference` |
| R05 | 保护、TG、39 MOS 实际版图、补偿与受控启动 | `microled-lab-05-display-startup` |
| R06 | NRZ 电压驱动与电流转向、共同接收和能量合同 | `microled-lab-06-nrz-architectures` |
| R07 | NRZ PVT、实际寄生、体端回流及供电/封装扰动 | `microled-lab-07-nrz-physical` |
| R08 | 高速 B 真实参考、21 MOS 宏、取能和重启风险 | `microled-lab-08-nrz-reference` |
| R09 | 实验对照、数值一致性、失败分层与数据恢复 | `microled-lab-09-method-reproduction` |

完整文章 URL 为 `https://kaiyo-blog.pages.dev/zh/blog/<路径>/`。中文为原文；英文/日文保留本地化界面，不计为三份独立研究内容。

## 固定版本与公开边界

- 研究依据为本仓库 `a7becbec086c1c660b501c230b317682aa3f849b`；原始 Release 和既有输入没有改写。
- 博客正文与资源提交为 [6dccf85cfdde33eb73c4b71f59ef6378275147b4](https://github.com/Kevin-Kaiyo/kaiyo-blog/commit/6dccf85cfdde33eb73c4b71f59ef6378275147b4)。博客仓库保留文章、十张原样项目图、一张原创研究路线图、数据与检查脚本。
- 来源核验覆盖 91 个固定版本文件。七个数据/署名下载文件中，六份逐字节复制既有资料，一份 PWM CSV 筛选原摘要中的八项标量；没有重新计算电路结果。
- LED 数值曲线保持 Lin 等作者署名、CC BY 4.0 与处理声明；没有复制论文原图，没有上传 ignored 私人原图卡、凭据、雇主资料或无关个人记录。公开文章与资产不含私人绝对路径。
- 合成 LED 与公开静态负载分开；显示 27 个选定电气 case 包含 12 个动态点；NRZ 的 0/511、四个 DC 精度失败、提前释放负控与残余重启体结风险均保留。

## 实际检查范围

本地 `npm run build` 退出 0，生成 467 个静态页面；聚焦核验 52 个页面的链接/资源/锚点、相邻阅读顺序、metadata、图表与数据哈希。桌面检查宽度 1280 px；十篇文章在 390 px 宽度下图片全部加载，document 未横向溢出；数据页有七个下载链接。旧文章仅增加历史日期说明和新系列入口，原 URL 保留。

Git 对该系列生成式 SVG 与 CSV 采用局部 `-text -whitespace` 属性，保留源空格、CRLF 和 SHA-256 字节身份。实际索引中的 18 个图/数据资产已比对 Git 暂存内容。该属性不修改源文件。

具体记录见[发布清单](../../evidence/publication/20261025/manifest.json)；博客仓库的 `docs/research-publication/2026-10-25/` 保留独立审查修订、静态检查与浏览器检查范围。网页构建和发布验收不能替代电路矩阵重跑、全新机器安装或硅片/光学验证。
