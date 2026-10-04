# 研究身份映射与独立复核

v0.3 新证据：[macro polygon identity](macro-identity.json)、[共同top独立检查与真实LVS负对照](integration-review.json)、[54+6瞬态与DC/AC/电荷独立复算](interface-review.json)。[Current manifest](current-manifest.json)记录当前交付hash；检查数量是artifact / identity核查，不能当作新增工程case数。

跨宏link的元件排序改变保留在[独立输入映射](../interface/input-mapping.json)：实际as-run与current字节hash分别保留，四端顺序及R/C类型、端点、数值、重数严格相同；错误图会被拒绝。它与下面旧TB的默认行为证明是两种独立映射，不能互相代替。

## 原测试台输入版本与默认行为证明

[input-mapping.json](input-mapping.json) 保留了一次明确的输入版本变化：`sim/rtl/tb_pixel_pwm.v` 新增可选 `TRACE_REALTIME`，默认值仍为 0。旧仿真实际使用的 TB hash 为 `ce23d247…d9ea`；现版本为 `f0fc5b99…2dbe`。RTL 本身未变。

旧 TB 从真实 20/4 RC 耦合运行的冻结输入复制，完整字节公开在 [旧源码快照](input-snapshots/ce23d247156ea1e28a0abaefa84ad018eade72c18f4c6d1e1093f4d5ca4ed9ea/sim/rtl/tb_pixel_pwm.v)，并检查其 SHA-256 与旧运行记录一致。新旧差异见 [diff](input-mapping-tb.diff)。没有修改历史 summary 中的 `source_hashes`。

独立运行旧/当前 TB：

- 10 组 duty/enable trace cases，各运行两版，共 20 次；每组 CSV 均逐字节相同。每组保留一份共同轨迹，路径及两侧 hash 位于 manifest。
- 两版各执行一次默认 exhaustive 检查，均为 **518 frames、133159 slot/value checks、543 known events**；日志分别保留在 [旧版](input-mapping-old-exhaustive.log) 和 [当前版](input-mapping-current-exhaustive.log)。
- 总计 **22 次 RTL 仿真**。这些结果只说明该 revision pair 的默认功能和整数时间 trace 行为相同，不把历史 SPICE 仿真改标为使用新 TB，也不声称 gate/SDF 或物理时序等价。

复现命令：

```sh
.venv/bin/python scripts/research/verify_input_mapping.py
```

脚本锁定本次旧 TB、当前 TB、RTL 三个版本，并在开始和结束检查 hash。如果未来任一版本变化，需要另做版本映射，不能覆盖本次记录的真实运行身份。原始编译、版本和逐项日志保留在 manifest 指向的 `build/research/` 目录。
