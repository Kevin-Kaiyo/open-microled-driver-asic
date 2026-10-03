# 项目名称

Open MicroLED Driver ASIC<br>
暂定仓库名：`open-microled-driver-asic`

## 1. 项目背景

希望建立一个完整的开源 MicroLED Driver ASIC 学习和研究平台。

项目不以直接设计车规量产芯片为第一目标，也不希望复刻任何商业 MicroLED Driver。

核心目标是通过实际设计，完整理解：

**Digital Logic<br>
+ Mixed Signal<br>
+ Transistor Circuit<br>
+ Physical Design**

最终真正走通：

**Concept<br>
→ Circuit<br>
→ Simulation<br>
→ RTL<br>
→ Layout<br>
→ DRC / LVS<br>
→ Extraction<br>
→ GDS**

如果条件允许，长期进一步探索真实 MPW Tape-out。

---

# 2. 项目核心目标

从一个极小的 MicroLED Pixel Driver 开始。

例如：

**1 Pixel**

先实现：

**Digital PWM<br>
→ MOS Switching<br>
→ Current Driver<br>
→ MicroLED Model**

并能够观察：

- LED Current
- PWM Waveform
- Average Current
- Brightness Relationship

之后逐步扩展到：

- 4×4
- 8×8
- 16×16

未来再考虑更大阵列。

项目第一阶段的重点不是像素数量，而是把完整 ASIC Design Flow 跑通。

---

# 3. 总体系统概念

长期可以形成：

**Serial Interface<br>
→ Command Decoder<br>
→ Register Bank<br>
→ Pixel Memory<br>
→ PWM / Gray Scale Engine<br>
→ Pixel Driver Cell<br>
→ MicroLED Array**

ASIC 内部需要同时研究数字和模拟部分。

---

# 4. Digital Domain

数字部分可以研究：

- Serial Interface
- SPI / QSPI-like Protocol
- Command Decoder
- Register Bank
- Pixel Memory
- PWM Generator
- Frame Timing
- Row / Column Control
- Test Pattern
- Status / Diagnostic Logic

所有协议和寄存器都必须由本项目独立设计。

不要复制商业产品协议。

---

# 5. Analog / Mixed-Signal Domain

重点研究真正驱动 MicroLED 的 Pixel Driver。

需要理解：

- MOS Switch
- Constant Current Source
- Current Sink
- Current Mirror
- Cascode
- Programmable Current
- Current DAC
- PWM Control

核心问题包括：

**LED Vf 发生变化时，如何尽量维持稳定 LED Current。**

以及：

**如何通过 PWM 和 Current Amplitude 控制 MicroLED Brightness。**

---

# 6. Pixel Driver

请从最简单可工作的 Pixel Driver 开始。

不要第一版直接追求高精度或者复杂补偿。

Codex 可以调研并比较：

- Resistor Current Limiting
- Simple Current Mirror
- Cascode Current Mirror
- Programmable Current Sink
- Current DAC

然后自主选择适合作为第一版 Baseline 的方案。

重点是得到可以解释、可以仿真、可以版图实现的设计。

---

# 7. MicroLED Model

建立一个简化 MicroLED 电气模型。

可以研究：

- Forward Voltage
- I-V Characteristic
- Dynamic Resistance
- Parasitic Capacitance
- Transient Behavior

第一阶段模型可以简化。

重点是验证 Driver，而不是建立完整器件物理模型。

---

# 8. PWM / Gray Scale

研究：

- PWM Frequency
- PWM Resolution
- Per-pixel Brightness
- Global Brightness
- Duty Cycle
- Gray Scale
- Frame Refresh

之后再研究更高级的：

- Hybrid PWM + Current DAC
- Calibration
- Gamma
- Compensation

---

# 9. Pixel Array

建议扩展顺序：

**1 Pixel<br>
→ 4×4<br>
→ 8×8<br>
→ 16×16**

阵列设计中逐渐研究：

- Pixel Replication
- Routing
- Clock Distribution
- Power Distribution
- Ground
- IR Drop
- Area
- Array Scaling

不要一开始设计数万像素。

---

# 10. 开源 EDA 工具链

该项目希望尽量使用免费和开源工具。

开发机器：

**Mac mini**

必要时通过 Docker / Linux Container 建立稳定环境。

请 Codex 调研当前成熟工具组合，而不是机械采用固定方案。

可以重点研究：

### Schematic / Analog

- Xschem
- ngspice

### Digital RTL

- Verilog / SystemVerilog
- Verilator
- Icarus Verilog
- Yosys

### Physical Design

- OpenROAD
- OpenLane
- LibreLane
- Magic
- KLayout

### PDK

重点比较：

- SKY130
- GF180MCU

比较因素：

- Analog Device Support
- MOS Options
- Supply Voltage
- Documentation
- Open-source Tool Compatibility
- Community
- MPW Availability
- Mixed-signal Suitability
- LED Driver Suitability

不要预先指定最终 PDK。

先调研，再做选择。

---

# 11. Mixed-Signal Verification

这是项目的重要目标之一。

希望最终能够让：

**RTL-generated PWM**

真正控制：

**Transistor-level MOS Driver**

再驱动：

**MicroLED Electrical Model**

而不仅仅分别做两个独立仿真。

需要研究适合的：

- Mixed-signal Co-simulation
- Behavioral Model
- Verilog-A / equivalent approach
- Python orchestration
- SPICE + RTL integration

Codex 应自主寻找最现实的开源方案。

---

# 12. Physical Design

长期目标需要真正进入版图阶段。

逐渐完成：

- Schematic
- Layout
- DRC
- LVS
- Parasitic Extraction
- Post-layout Simulation
- Standard Cell Integration
- Floorplan
- Placement
- Clock Tree
- Routing
- Power Planning
- GDS Generation

对于模拟 Pixel Driver，应真正进行晶体管级 Layout，而不是只停留在原理图。

---

# 13. Tape-out 愿景

长期目标：

**Tape-out Ready**

并不要求项目马上真正投片。

但设计流程和输出应逐渐接近可以送入 MPW Shuttle 的状态。

需要长期研究：

- Open PDK Foundry Options
- MPW Shuttle
- Package
- Pad Ring
- ESD
- IO
- Power
- Design Rules
- DRC / LVS Sign-off
- Post-layout Verification

如果未来存在成本和条件都合理的 MPW，则可以进一步考虑真实流片。

---

# 14. 与 FPGA 项目的关系

ASIC 项目与 FPGA 项目保持两个独立 Repo。

但系统层最终可以形成：

**Host<br>
→ FPGA Controller<br>
→ MicroLED Driver ASIC<br>
→ MicroLED Array**

FPGA 负责：

- Frame
- Mapping
- Scheduling
- System Control
- High-level Communication

ASIC 负责：

- Local Data Reception
- Pixel Data
- PWM
- Current Driver
- Physical LED Drive

两边的接口未来由双方共同定义。

---

# 15. 开源与信息边界

项目必须完全基于：

- Public Datasheet
- Academic Paper
- Patent
- Open-source Design
- Public PDK
- Public EDA Tool
- Independent Design

不得使用：

- 非公开商业 Register Map
- 非公开 ASIC Schematic
- 非公开 Layout
- 内部协议
- 企业内部文档
- Proprietary RTL

如果项目参考论文、专利或现有开源设计，应在 Repo 中记录出处。

---

# 16. 长期研究方向

当基础 Driver 跑通以后，可以逐渐探索：

- High-precision Current Driver
- Current DAC
- PWM Architecture
- Hybrid PWM + Amplitude Modulation
- Current Calibration
- Pixel Non-uniformity Compensation
- Temperature Compensation
- Aging Compensation
- Open / Short Detection
- ADC
- Temperature Sensor
- Fault Diagnostics
- High Pixel Count Architecture
- Automotive Lighting Driver
- High-speed MicroLED Driver
- Optical Communication Driver

项目应该被设计成一个可以长期升级的研究平台，而不是一次性 Demo。

---

# 17. Codex 第一阶段任务

请不要第一步就尝试设计完整 16×16 ASIC。

首先完成：

1. 调研公开 LED / MicroLED Driver ASIC 项目。
2. 调研开源 Mixed-Signal ASIC 项目。
3. 调研相关论文、专利和公开参考设计。
4. 比较 SKY130 和 GF180MCU。
5. 比较当前主流开源 ASIC Flow。
6. 建立推荐开发环境。
7. 建立 GitHub Repo。
8. 建立 README。
9. 建立项目目录。
10. 设计系统 Block Diagram。
11. 设计第一个 1-Pixel Driver。
12. 建立 MicroLED 简化模型。
13. 完成 transistor-level simulation。
14. 加入数字 PWM。
15. 实现 Digital PWM → MOS → Current → LED 的闭环仿真。
16. 自动生成关键波形和结果。
17. 记录设计假设、限制和下一步研究方向。

第一阶段最关键的成果是：

**Digital PWM<br>
→ Pixel Driver<br>
→ MicroLED Model**

完整跑通，并且能够看到和解释真实的 LED Current Waveform。

在此基础上，再逐步进入阵列、版图和最终 GDS。
