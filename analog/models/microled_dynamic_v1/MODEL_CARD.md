# 黄色20µm MicroLED条件化幅频模型卡

**状态：仅对原测量整链的normalized magnitude作条件化拟合；物理动态联合校准未闭合，不能激活为器件瞬态模型。**

基于作者存档的30MHz–3GHz、25/50/60/80/100µA数据。保留原200fF/200ps/RX1GHz历史基线。静态I–V/P–I与S21是否来自同一颗像素，尚未建立。

| 偏置/µA | 选中模型 | 全频RMSE/峰误差 dB | ≤2.5GHz RMSE/峰误差 dB |
|---:|---|---:|---:|
| 25 | complex3p1z | 0.410 / 1.637 | 0.247 / 1.239 |
| 50 | complex3p1z | 0.273 / 1.365 | 0.145 / 0.591 |
| 60 | complex3p1z | 0.267 / 1.571 | 0.145 / 0.500 |
| 80 | complex3p1z | 0.262 / 1.251 | 0.161 / 0.508 |
| 100 | complex3p1z | 0.212 / 0.998 | 0.135 / 0.431 |

选阶最多4阶；3pole/1zero与最后4pole/2zero候选相比，误差收益小于0.03dB，采用较小模型。complex pair与zero是数学自由度，没有识别为LED复合、封装或检测器物理机制。80/100µA的zero触到100GHz边界，参数解释更弱。≤2.5GHz只是剔除近3GHz段后的残差，未证明该域的仪器SNR或绝对准确度。

频率验证含每5点留1、0.8–1.2GHz整段留出、2.6–3GHz边缘外推；另有逐偏置留出。选阶使用过完整曲线，因此频率验证只检验给定family的系数，不是nested model-selection validation。所有留出均来自同一份已处理数据，不能代替独立器件/温度/相位验证。

`coefficients.json`使用q=s/(2π×1GHz)，分子分母系数按升幂排列。归一化只固定30MHz幅值，DC增益是模型外推。数值检查覆盖LHP poles/zeros、strictly proper、30MHz归一和step终值；它们证明数学模型的稳定/因果结构，不能证明真实LED的phase、passivity或瞬态。

在明确假定source50Ω、detector3GHz、未知封装省略的替代整链中，C10/50/200/800fF与tau0/25/75/200ps共80组，没有一组满足描述性RMSE≤0.35dB且峰误差≤1.25dB。逐C重新选单一tau也不能解释全部曲线形状。此结果约束该简单模型族；不能据此断言真实LED的C或lifetime。

相同幅值可加100ps delay或稳定all-pass；相位与采样时刻仍不唯一。任意C也可通过修改稳定residual transfer保持同一整链拟合。因此缺失同器件complex S11/S21、RF幅度、校准面、RX/封装去嵌、温度与large-signal数据时，动态器件校准不闭合。

**禁止将整链Htotal叠加到已有电学RC、optical tau或RX后。不得把这些拟合系数宣称为实测C/lifetime、净3.2Gb/s BER或光链路资格。**

来源、hash、拟合与验证细节见model-card.json及evidence/microled-dynamic-v1/fit-*.json/CSV；原始失败候选和multistart日志在build/microled-dynamic-v1/calibration/。
