# A25 运行时审计：保持数学、精度与计费不变

审计范围：只读源代码与已保存的 `a25-gpu-health-001` 结果；未执行训练、物理计算、测试、性能探针或远程访问。本文件只提出候选修复，性能收益必须由父线程在独立计费作业中测量。代码仍在其他所有者修改；以下行号为审计读取时位置。

**当前阻塞是实际 CPU 预算，而不是 GPU 显存或神经网络精度结果。** 原始健康作业的完整费用为 wall/GPU occupation **40.8640207 s**、process CPU **34.9375 s**，共 **1497** 个账本事件、**21** 次更新（含收费的预热）。N2 三层更新记录为 wall **1.4122323 s**、CPU **1.328125 s**。完整 11 个训练作业、500 次更新及规定验证和 1.3 安全系数的预测为 CPU **8987.46875 s**、GPU **9507.5093671 s**，可用额度分别为 **3000 s / 9900 s**；`COST_SELECTED_UPDATES.json` 正确保持 `INSUFFICIENT_BUDGET`。要满足原分配，整体预测 CPU 费用需要下降约 67%，而 GPU 时间余量很小；小幅局部优化不能自动打开训练门。

证据：[健康结果](../../../results/a25/learning/GPU_HEALTH.json)、[费用选择](../../../results/a25/learning/COST_SELECTED_UPDATES.json)、[完整收据](../../../results/a25/jobs/a25-gpu-health-001/job_receipt.json)、[原始事件账本](../../../results/a25/jobs/a25-gpu-health-001/COST_LEDGER.jsonl)。实际远端环境的已保存元数据为 PyTorch **2.6.0+cu124**，本审计未重新连接远端。

## 按优先级排列的候选

| 优先级 | 直接证据 | 保持数学不变的修复候选 | 必须保留的边界 / 未知量 |
|---|---|---|---|
| 1：父线程已选的单因素探针 | `training.py:266–276`：梯度范数使用 `error_if_nonfinite=True`；原路径在 `optimizer.step()` 后逐参数把 GPU 的 `isfinite(...).all()` 转为 Python Boolean。多层 U-Net 有大量参数张量，因此每次更新会触发大量独立主机读取。 | 将所有逐参数 finite 标量在 GPU 上合并，只读取一次最终 Boolean。当前源码已出现默认关闭的 `batched_parameter_finiteness` 对照开关，父线程负责执行和验证。只合并标量，无需拼接全部参数。 | 保留更新后的所有参数检查；梯度范数检查不能代替它，因为优化器更新仍可能产生非有限参数。拒绝谓词保持“任一参数非有限即失败”。原健康费用与失败记录保留，新费用单独入账。收益目前 **NOT_MEASURED**。 |
| 2：同步等待 / 嵌套仪器 | `a20/costs.py:120–147` 每个 span 在入口和出口调用完整设备 `torch.cuda.synchronize()`（实现 `:73–76`）；`torch_physics.py:284–308, 417–440` 连很小的矩阵乘法和每次解算也使用 span。1497 事件意味着约三千次 span 同步调用，此外还有各类标量守卫。 | 第一种较小改动是 A25 专用的阻塞 completion event 等待，以减少可能的主机自旋。另一种是内部 span 记录提交、计数与 CUDA events，在明确的外层完成边界结算；把事件 GPU 时间与 host elapsed 清楚区分。 | 默认设备同步等待是否实际自旋、占多少 CPU，账本本身不能证明。事件只覆盖已记录流，不能直接替换“所有流完成”的语义；必须证明当前工作流依赖覆盖或在外层仍完整同步。不能使原来同步的费用字段变成未完成提交时间，又沿用原字段名称。完整作业 / 更新 / 基准边界继续等待所有相关工作，实际 wall 与 process CPU 全额收费。 |
| 3：每个反向 hook 的昂贵计费检查 | `torch_physics.py:273–281` 每个反向 hook 都执行 `book.check()`；`budget.py:166–191` 每次检查读锁文件、检查额度并调用继承的内存采样，每一秒还写 durable checkpoint；`a20/costs.py:84–103` 包括 psutil 与 GPU 内存查询。每个 span 还重复执行此检查。 | 将廉价额度检查与较昂贵内存、锁、checkpoint 采样区分；反向 hook 可以保留准确计数和廉价额度检查，在定义好的更新 / 求解边界执行完整检查。缓存设备静态属性、减少重复 Process 构造亦可独立考虑。 | 这会影响资源检查的频率，不能作为纯数学等价而自动采用。锁所有权、90% 显存停止、累计预算、停止储备、durable label reservation、未闭合作业与终结收据的保障必须保留；需要事先声明有限检查间隔和最坏超额界。不建议在第一项探针里同时改动。 |
| 4：物理守卫的多次标量往返 | `torch_physics.py:422–425` 同一 SVD 结果有多个独立 Boolean；`:494–501` material 域也有多个 Boolean；`:530–536` 的状态匹配使用 GPU `torch.equal`。`data_gradient` 再调用 VJP 时会再次做匹配。 | 一次性合并同一决策的 finite / 区间 / 条件数 flags；减少重复状态匹配，若使用同一张量身份快速路径，必须同时保护 shape、模型 owner 与版本/变更状态。 | 不删 SVD、域约束、finite 检查，不变阈值，也不能用对角近似替代奇异值。状态不能在材料改变后复用。守卫所用 detach 是诊断，不授权把数据梯度或求解图 detach。 |
| 5：解算与相同状态重用 | `torch_physics.py:435` 使用 `torch.linalg.solve`，官方文档说明 CUDA 会与 CPU 同步；同一非 Hermitian K 的正向/伴随解算分别调用该路径。 | 候选 `solve_ex(check_errors=False)` 可把 info 与 finite flags 合并检查，减少内部独立同步；或在同一材料状态内重用可微 LU，用正确 adjoint 解算。已知背景本身已经重用 LU（`:305`），不要重复声称新收益。 | 必须处理每个非零 info 和非有限输出，不把错误解当有效；保留 complex128/float64、完整非 Hermitian 伴随以及一阶/高阶导数。LU 重用的图与计数需重新验证，不缓存脱离 autograd 的材料依赖因子。PyTorch 2.6 的具体 API 与高阶导数能力要在父线程的新计费探针中确认；官方较新版文档不能代替运行版本验证。 |

## 如何解释账本，避免“免费加速”

`COST_LEDGER.jsonl:79–80` 给出一个明确例子：backward CPU **0.21875 s** 是 enclosing update CPU **0.703125 s** 的组成部分，不能相加成总 CPU。健康 span 的 CPU **33.546875 s** 也已经包含更新子 span；权威累计值是完整 job receipt 的 **34.9375 s**。Windows 事件级 CPU 读数在此记录中可见 1/64 s 的量化，因此极小事件的 CPU 归因不可靠。

`exclusive_wall_seconds` 在 `CostBook.span` 中仅扣除嵌套 child wall；它仍是主机 elapsed 与同步后的等待组合，**不是 CUDA kernel time**。入口的 check/synchronize 在该子 span 的 start 之前执行，通常计入外层或完整作业；append 文件 I/O 也在子 span 的 wall 截止之后执行，但完整作业仍收取。故不能只加这些 exclusive 列推断全部仪器开销、忙等比例或优化后的真实 CPU 费用。当前 CPU 接近 wall 与过多同步/标量读取的解释一致，但也可包含主机 kernel launch、自动微分、内存/锁/JSON I/O；尚无 profiler 证据分离它们。

父线程已选择**只先测逐参数 finite 合并**，这是恰当的因果隔离：同一拓扑、batch、参数/数据、优化器、精度、确定性设置、损失、物理守卫和更新次数；比较带预热的独立收费作业、完整 update 与完整 job CPU/GPU wall。后续若考虑 blocking events 或仪器重构，单独作业、单因素，重新执行原 cost-only 更新数选择。所有额外探针与 warmup 都消耗既有总额度。未达到全部 11 作业、规定最小更新与验证的预测预算条件时，继续保持预算不足；不以单个 N2 的局部改善推断全体可训练。

不在候选范围内：AMP / 降精度、减少网络层/参数或模型、隐藏 stop-gradient、删共享输入/梯度/当前特征、改变物理数据损失或 TV / KKT 尺度、减少 frozen 更新或验证、换门槛、把真实主机忙等费用从 CPU 账本剔除。以上均不能靠“优化仪器”名义实施。

## API 依据（原始官方资料）

- [PyTorch 2.6.0 CUDA streams / Event 源码](https://raw.githubusercontent.com/pytorch/pytorch/v2.6.0/torch/cuda/streams.py)：Event 支持 blocking 参数，record 默认使用当前流，synchronize 等待该 event 覆盖的工作；stream wait 本身不等待主机。
- [NVIDIA CUDA Event 文档](https://docs.nvidia.com/cuda/cuda-runtime-api/cuda_runtime_api/group__CUDART__EVENT.html)：`cudaEventBlockingSync` 让调用 event synchronize 的主机线程阻塞；它没有声称自动覆盖设备所有流。
- [PyTorch solve 文档](https://docs.pytorch.org/docs/2.10/generated/torch.linalg.solve.html)、[solve_ex 文档](https://docs.pytorch.org/docs/2.10/generated/torch.linalg.solve_ex.html)：普通 solve 的 CUDA 主机同步与 solve_ex 的 check_errors 行为；后者仍需读取/处理 info，且文档将其标记为 experimental。这里用于候选依据，执行环境为 2.6.0，应在独立收费验证中确认版本能力。

结论：可修复的首要工程风险是**大量 host scalar 读取与嵌套同步/检查**；是否足以跨过 CPU 分配界限仍 **NOT_MEASURED**。没有新的训练、精度或科学成功结论。
