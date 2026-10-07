# 独立帧与原子提交实验合同 v0.1

日期：2026-10-07。实现：[frame_model.py](../../scripts/control/frame_model.py)；独立对照：[test_frame_model.py](../../tests/test_frame_model.py)。

本合同定义一个可复现实验功能模型。logical pixel 数量仅表示 Python 数组长度；receiver、CRC、timeout 和整帧 buffer 当前均为功能模型。现有 RTL 仍承担单像素 PWM 回放，functional commit 与实际 PWM 生效边沿分别记录。

## 研究假设与时钟

假设：完整且有效的命令只在声明的边界一次性成为 active state；注入无效交易不改变同一正常输入的 commit 序列。partial 和 malformed 输入不能把局部 code 混入 active。

所有时间为一个明确声明的、单调不减的实验时钟，单位为整数 ns。`timestamp_ns` 是命令生成时刻，`accept_time_ns` 是完整接收并校验的时刻，`commit_time_ns` 是整帧状态生效时刻；RTL PWM 边沿属于独立回放证据。时间为实验定义，不代表真实车载总线或同步时钟测量。

边界集合：`boundary_origin_ns + k × boundary_period_ns`，k≥0。默认 origin=0；回放可显式设为 2000 ns、period=256000 ns。accept 恰逢边界时推迟到下一边界；接受时间早于 origin 时可在 origin 提交。对于既有 RTL 第一 PWM frame=2500 ns 的回放设置，functional commit→PWM frame 有 500 ns 显式延迟；两者不得合并。

## 自定义实验帧

本项目独立定义这一数据格式。所有多字节整数为 big-endian，payload 按 logical row-major index 排列；geometry 与 selected index 在 run 配置中记录。

| offset / bytes | 字段 | 约束 |
| --- | --- | --- |
| 0 / 4 | magic | ASCII `MLEX` |
| 4 / 1 | version | 1 |
| 5 / 1 | code width | 12 |
| 6 / 2 | logical count | 1…65535，必须等于 receiver 配置 |
| 8 / 4 | frame ID | unsigned 32-bit，session 中严格递增 |
| 12 / 8 | timestamp_ns | unsigned 64-bit，不得晚于完整到达时间 |
| 20 / 4 | payload byte length | `ceil(logical count × 12 / 8)` |
| 24 / L | payload | 每 code=0…4095，MSB-first紧密打包，尾部 padding 必须为 0 |
| 24+L / 4 | CRC32 | IEEE reflected CRC-32，覆盖 header+payload |

CRC 多项式反射值 `0xEDB88320`，初值 `0xFFFFFFFF`，最终 xor `0xFFFFFFFF`。固定外部检查向量 `123456789 → 0xCBF43926`；标准库 `zlib.crc32` 实现与测试中的逐 bit 复算分别执行。

固定实验帧：N=1、ID=1、timestamp=0、code=16，wire hex：

```text
4d4c4558010c000100000001000000000000000000000002010001568c54
```

header=24 B、payload=2 B、CRC=4 B，共 30 B。N=16 时 payload=24 B、整帧=52 B。这些 overhead 必须与纯 payload 预算分别报告。

## 状态与错误政策

状态包括：一个 partial assembly、一个完整 validated pending frame、一个 active frame。初始 active codes 全 0，active frame ID=None。payload SHA-256 表示 code 内容；wire SHA-256 另含 ID、时间戳和 CRC，二者不得互换。

| 输入 / 事件 | 预定义动作 | active 影响 |
| --- | --- | --- |
| 完整、新 ID、CRC 与长度正确、未过期 | 写 pending，安排严格晚于 accept 的首个边界 | commit 前保持；commit 时整帧替换 |
| 新有效帧在同一边界前到达 | 替换 pending，记录 superseded ID | 只有最新完整帧在边界生效 |
| partial fragment，没有 transaction end | 仅积累 assembly；完整字节到齐也要 end 后校验 | 保持 |
| partial / extra / 错长度 / 错 width / CRC / nonzero padding | 拒绝并记录确切原因 | 保持；已有 pending 也保持 |
| ID 等于最近 accepted ID | `duplicate_id` | 保持 |
| ID 小于最近 accepted ID | `out_of_order_id` | 保持 |
| future timestamp | `future_timestamp` | 保持 |
| timestamp+command_timeout ≤ 候选 commit | `expired_before_commit` | 拒绝；保持 |
| assembly 起始时间+receive_timeout 到期 | 丢弃 assembly，记录 partial_timeout | 保持 |
| active 的 timestamp+command_timeout 到期 | 在首个 ≥deadline 的边界清零 | 边界清零，active ID=None |
| 老 active timeout 与新 valid pending commit 同边界 | 新 commit 优先，取消老 expiry | 一次替换，无中间 clear |

timeout 不延续命令时间戳，坏帧不刷新期限。到期后 last accepted ID 仍保留，因此旧 ID 无法重放；ID wrap 不支持，要通过新 receiver session 明确重置。新 session 初始 active 全 0。这是身份与顺序规则，没有真实 transport retry、authentication 或 fault circuit 证据。

partial assembly 的期限从首个非空 fragment 起算，续片不延长。`receive(wire, now_ns)` 是完整交易快捷入口，已有 partial assembly 时返回 `receiver_busy`，避免把另一笔交易混入 assembly。`receive_chunk(data, now_ns, end=True)` 结束该 assembly 并校验；到期后的残留 fragment 被视为新交易数据，仍必须独立完整校验。

## 12-bit code 到现有 PWM

```text
duty = floor((code × 256 + 2047) / 4095)
electrical command fraction = duty / 256
requested logical fraction = code / 4095
```

这是 nearest rounding，code=0 保持 off，code=4095 保持 full-on。code=16/1024/2048/4079 分别映射 duty=1/64/128/255。整个 4096-code 域单调，误差 `|duty/256 - code/4095| ≤ 1/512`；现有 electrical PWM 仍只有 0…256 的 257 种 duty 命令状态。logical 12-bit command 不建立 12-bit PWM，也不建立 12-bit 光学灰阶。

## 复现与退出门槛

```sh
python3 -m unittest discover -s tests -p 'test_frame_model.py' -v
```

必须覆盖固定 wire/CRC、所有 4096 个 code 的独立分数量化复算、header/payload 每个 single-bit error、预定义长短帧与 padding 错误、partial timeout、duplicate/乱序、严格边界、pending supersede、同边界 timeout/commit 优先级，以及 dirty/clean commit 序列一致性。测试不调用仿真工具，不修改旧模型/RTL/PDK 或既有 evidence。

集成 runner 另记录 seed、geometry、selected index、每笔 wire/accept/commit/hash、PWM edge、Analog case 固定条件、失败原因与退出门槛。电气结果需通过现有模型单独回放取得；功能测试通过仅支持本合同的状态行为。
