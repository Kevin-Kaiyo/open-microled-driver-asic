# MicroLED 调制带宽：原始文献核验札记

核验日期：2026-10-29。用途：实验性 R&D 方法与教学；单通道 **NET 3.2 Gb/s** 是共同设计目标。本文件记录原作者实验与本次阅读，不代表本项目完成器件、硅后或光学测量。机器可读记录见 [literature.json](literature.json)。

## 读取深度与可支持的结论

这是按设计问题整理的独立事实表。各行的器件、偏置、接收机与带宽定义不同，不能按 GHz/Gb/s 排名。“摘要”行没有提升为全文级证据。

| ID / 主问题 | 原始来源与精确定位 | 核验深度及关键边界 |
|---|---|---|
| L01-RAJABI2018：薄 QW / QCSE | [DOI](https://doi.org/10.1364/OE.26.024985)，[原始摘要](https://pubmed.ncbi.nlm.nih.gov/30469606/)，OE 26(19),24985–24991 | 摘要。蓝光 c-plane；QW/barrier 同时改成 1/3 nm；214→536 MHz，报告 J=2.5 kA/cm²。尺寸、EQE、温度及完整响应定义未核验；不能单独归因于井厚。 |
| L02-XU2023-SEMIPOLAR：晶向 / 低 J | [DOI](https://doi.org/10.1109/JPHOT.2023.3235108)，[公开原始全文](https://www.researchgate.net/publication/367062823_High_Bandwidth_Semi-Polar_InGaNGaN_Micro-LEDs_With_Low_Current_Injection_for_Visible_Light_Communication)，Sec II/III, Figs2–4,6 | IEEE 原文全文文字；与 Crossref 元数据及文内 CC BY 4.0 一致。直径60 μm，绿光>500 MHz@43.8 A/cm²、>1 GHz@120.6 A/cm²；APD 标称1 GHz，作者明确最大值受探测器限制。最高链路速率是 OFDM；净开销未核验。 |
| L03-LI2023-QD：QD / RC 与复合 | [DOI](https://doi.org/10.1109/LED.2023.3256422)，EDL44(5),785–788，publisher abstract | 摘要。蓝/绿约3.6/1.4 GHz，J<1 kA/cm²；RC/复合分离为模型解释。125°C可工作与这些峰值带宽的温度条件不能合并。 |
| L04-LI2024-NANOACTIVE：纳米有源区 / 链路 | [DOI](https://doi.org/10.1109/JLT.2024.3444324)，JLT42(24),8760–8770，publisher abstract | 摘要。>2.6 GHz明确写作 **E-E −3 dB**；单通道 real-time NRZ-OOK 为自由空间3.07 / 石英光纤2.60 Gb/s。四通道12.00/15.05 Gb/s为aggregate。没有已核验的单通道NET3.2证据。 |
| L05-LI2025-THINWELL：速度与效率反例 | [arXiv v1](https://arxiv.org/abs/2502.21302)，pp2–4/Table1/Fig1, pp8–10/Fig5；[正式DOI](https://doi.org/10.1063/5.0258108)，[经同行评审的accepted manuscript](https://www.osti.gov/servlets/purl/2551797) | 两份全文；原图已核验。固定19% In、18 nm barrier、井厚2.1–3.6 nm，颜色随井厚改变。约2.7 nm是该系列效率折中；不适合作通用最佳井厚。低J带宽回升含carrier escape作用。 |
| L06-ZHU2024-ELECTRODE：电极 / 深刻蚀 | [DOI](https://doi.org/10.1364/OE.539321)，[原始摘要](https://pubmed.ncbi.nlm.nih.gov/39573804/)，OE32(22),39974–39983 | 摘要。203→249.8 MHz@4 kA/cm²；electrode capacitance减少24.9 pF是阻抗模型拟合提取，不能当成独立直接测得的总电容。 |
| L07-WANG2019-PHC：光提取 / 刻蚀代价 | [DOI](https://doi.org/10.3390/mi10110767)，[全文](https://pmc.ncbi.nlm.nih.gov/articles/PMC6915634/)，Sec2/3,Figs6/7 | 全文与原图。PC60为半径60 μm，212 MHz@1 kA/cm²；PC30半径30 μm，285 MHz@2 kA/cm²。同尺寸PhC实测输出光功率较低。FDTD LEE68%不是实测EQE。 |
| L08-FERREIRA2016：尺寸 / 接触 / 完整链路 | [DOI](https://doi.org/10.1109/LPT.2016.2581318)，[作者机构PDF](https://eprints.gla.ac.uk/129061/1/129061.pdf)，pp2023–2026,SecII–IV,Figs2–5 | 全文与原图。A/B分别435/1369 μm²，最高833/397 MHz；Fig5高阶链路使用B。正文给出PAM4净3.5与OFDM净5 Gb/s，含作者7%FEC扣除；离线处理、完整协议/真实FEC实现未建立。 |
| L09-FAN2022-RED-SIZE：AlGaInP缩小代价 | [DOI](https://doi.org/10.1016/j.rinp.2022.105449)，[publisher abstract](https://www.sciencedirect.com/science/article/pii/S2211379722002029)，Results in Physics36,105449 | 摘要。Si上red vertical，边长160→10 μm；峰值EQE下降、series resistance升高，但高J droop可改善。没有带宽实验。摘要波长漂移段的“smaller >80 μm”存在不一致，本札记不使用该尺寸阈值。 |

## 原始证据定位与解释

原始图像与PDF保存在被忽略的 `build/`，**不随公开 Git 文档提交**。本公开文件仅列私有路径、图号、rights、SHA-256及解释；JSON的 `original_asset_ledger` 保留变换和核验记录。包含原图嵌入的本机阅读文件为 `build/microled-device-codesign-20261029/literature/private-evidence.md`。公开文章只使用独立事实表及自己的计算/机制图，不复制私有原图。

### A01：薄井效率不是单调改善

**原始证据（私有）**：`build/microled-device-codesign-20261029/literature/li2025-fig1-private.png`；图号定位：arXiv v1 p4 Fig1；rights：`private_review_only; public_reuse_not_cleared`；SHA-256：`326da15ad2e50b6c73aeb46d88cccdcaece609a72fa39cb8b6c408ee2c57ae8a`。核验记录见公开台账 `original_asset_ledger` 的 `A01-LI2025-FIG1`；含原图的本机阅读文件为 `build/microled-device-codesign-20261029/literature/private-evidence.md`。

原始证据：Li等，*Impact of quantum well thickness on efficiency loss in InGaN/GaN LEDs: Challenges for thin-well designs*，arXiv2502.21302v1 p4 Fig1。原坐标、图例和caption已保留；注入效率与IQE为百分比，辐射效率轴为a.u.；横轴J为对数轴。IQE来自已知LEE下的EQE，辐射效率由IQE/注入效率得到，属于测量结合提取。条件：19% In、18 nm barrier、六种井厚；不同井厚同时改变发射波长。温度和横向几何在所读全文未明确。版权：arXiv仅nonexclusive distribution许可，尚无公开图像复用授权；**private review only**。

本次解释：低J时2.1/2.4 nm不优于约2.7 nm，井越薄越高效不是这组数据支持的规律；没有从图中数字化任意精确值。此反例不否定其他外延/颜色下1 nm器件的速度收益。

### A02：低J带宽提高可能来自逃逸

**原始证据（私有）**：`build/microled-device-codesign-20261029/literature/li2025-fig5-private.png`；图号定位：arXiv v1 p10 Fig5；rights：`private_review_only; public_reuse_not_cleared`；SHA-256：`e9be1abebc499287ba0abc0c02b3a2c0bcb5a8ae5643a1dddcd6fc1e9adc5918`。核验记录见公开台账 `original_asset_ledger` 的 `A02-LI2025-FIG5`；含原图的本机阅读文件为 `build/microled-device-codesign-20261029/literature/private-evidence.md`。

原始证据：同文arXiv v1 p10 Fig5；a为MHz带宽/J，b为秒单位的微分复合寿命/J，c为寿命比/J，d为B(n)n /载流子密度。坐标、图例与caption已保留。a是SSEL响应；b–d依赖模型提取。版权同A01；**private review only**。

本次解释：2.1/2.4 nm低J带宽上翘不能直接写成辐射复合更快；应结合p9 Eqs2–3与Fig1检查escape和效率。归一化响应快不保证绝对光学调制幅度、接收SNR或pJ/bit更好。作者也保留薄井效率下降的内在/缺陷机制争议。

### A03：尺寸更小的最高带宽不能与另一像素最高数据率拼接

**原始证据（私有）**：`build/microled-device-codesign-20261029/literature/ferreira2016-fig3-private.png`；图号定位：p2025 Fig3；rights：`CC_BY3.0; local_review_only_in_this_package`；SHA-256：`dc0b53fbfc0b46d95cc4eb67cf5750f17f322507119bc705ec509bfef20d8c2b`。核验记录见公开台账 `original_asset_ledger` 的 `A03-FERREIRA2016-FIG3`；含原图的本机阅读文件为 `build/microled-device-codesign-20261029/literature/private-evidence.md`。

原始证据：Ferreira等，*High Bandwidth GaN-Based Micro-LEDs for Multi-Gb/s Visible Light Communications*，p2025 Fig3。横轴kA/cm²、纵轴E-O MHz；A/B标记、caption的833/397 MHz与电流范围保留。E-O测量用1.4 GHz PD、片上RF探针与few-mV小信号；450 nm c-plane flip-chip；未装heat-sink；结温未报告。版权：原文首页明确[CC BY3.0](https://creativecommons.org/licenses/by/3.0/)，本包仅本地保留。

本次解释：工艺同时改Pd contact、deep mesa etch和形状，不能只归因于某一项。最高带宽A不等于Fig5的高阶传输B。正文PAM4约3.8 gross→作者net3.5 Gb/s，DFE；OFDM5.37 gross→作者net5 Gb/s，FFT512、CP5；0.75m、1GHz PD、5V DC、offline MATLAB。作者的net主要体现所述7%FEC扣除，没有证明完整系统净率/能耗。摘要3.4与正文3.5不一致，采用正文并明确该差异。

### A04 / A05：PhC带宽收益不能全部归因于Purcell

**原始证据（私有）**：`build/microled-device-codesign-20261029/literature/wang2019-fig6.jpg`；图号定位：Fig6(a,b)；rights：`CC_BY4.0; local_review_only_in_this_package`；SHA-256：`84c336144494a4ea2537bd702e5f1939126d7a950cf60d6dbcc1bda6920b4810`。核验记录见公开台账 `original_asset_ledger` 的 `A04-WANG2019-FIG6`；含原图的本机阅读文件为 `build/microled-device-codesign-20261029/literature/private-evidence.md`。

原始证据：Wang等，*Study on Modulation Bandwidth and Light Extraction Efficiency of Flip-Chip Light-Emitting Diode with Photonic Crystals*，Fig6(a,b)；图注定位见[原文Fig6](https://pmc.ncbi.nlm.nih.gov/articles/PMC6915634/#micromachines-10-00767-f006)。左为PC-FCLED、右为未加PhC的FCLED；两面板右纵轴光功率上限不同。应按同一mesa半径与相同注入电流比较。IV/P是实测；温度未报告。版权：[CC BY4.0](https://creativecommons.org/licenses/by/4.0/)已在原文核验，本包仅本地保留。

**原始证据（私有）**：`build/microled-device-codesign-20261029/literature/wang2019-fig7.jpg`；图号定位：Fig7(a,b)；rights：`CC_BY4.0; local_review_only_in_this_package`；SHA-256：`b83036479d0da255020a9390ea50984bee4ea3e1c020fe253fbcd19d0bf34d1f`。核验记录见公开台账 `original_asset_ledger` 的 `A05-WANG2019-FIG7`；含原图的本机阅读文件为 `build/microled-device-codesign-20261029/literature/private-evidence.md`。

原始证据：同文Fig7(a,b)；图注定位见[原文Fig7](https://pmc.ncbi.nlm.nih.gov/articles/PMC6915634/#micromachines-10-00767-f007)。a为归一化频响及−3dB线，30/60/90 μm半径分别用50/100/150mA；b以J比较光学f−3dB。不同半径的50/100/150mA不是相同J控制。探测器去嵌和dB计量细节未充分建立。版权同A04。

本次解释：原文Sec3将较低功率与减小发光面积、ICP damage联系，并明确Purcell不能完全解释带宽提升。这个结果支持同时测量bandwidth、absolute OMA、EQE/WPE和nonradiative loss；不能把FDTD的LEE68%直接写成实物效率改善。

## 跨来源判读规则及缺口

1. **bandwidth定义**：保留source所写E-O、E-E、optical f−3dB与cut-off，未统一log/归一化/去嵌前不换算。单器件本征响应不等于包含接收器的E-E链路响应。小信号带宽也不等于大信号NRZ净吞吐。
2. **bias与效率**：峰值EQE、最大光功率、最高带宽及最大数据率往往在不同J；没有相同工况数据，不合成一个“最佳器件”。薄井、非辐射复合或carrier escape可加快归一化响应，同时损失光子。
3. **system与制造**：论文中低J、GHz、mW不建立系统pJ/bit、寿命、良率、可订购性或MPW。制造相关推断独立标在JSON中；没有设计定案或architecture preselection。

优先待补：同波长/同温度QW与QD对照的S11/S21+EQE+OMA；接触/深刻蚀/sidewall与封装去嵌；完整driver–LED–optics–PD/TIA的BER与NET开销/总功耗；加速老化与分布/良率。它们比继续收集最高速率摘要更能改变NET3.2方案判断。

## 获取状态与本地复核

- 元数据：6篇Crossref DOI registry原始响应在build中；其余作者/日期用原文或PubMed核对。网络获取时间为2026-10-29，不据旧记忆补齐未知条件。
- Optica的Rajabi/Zhu下载为脚本挑战页，已命名`.blocked.html`，没有把它们当PDF。IEEE直接下载遇418/robot保护；Xu通过公开原始全文文字核验，原PDF未获取。Li2023/Li2024只核验publisher abstract。
- 原始文件与图像hash见build中的`private-asset-manifest.json`及公开JSON内的局部asset ledger。未对他人论文曲线做数值拟合或digitization；没有虚构温度、器件数或误差条。
