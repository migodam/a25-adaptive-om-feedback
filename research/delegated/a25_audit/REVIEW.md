# A25 实施审阅：数学尺度、信息边界与公平比较

审阅日期：2026-10-08；初稿资料截止 15:28 UTC。审阅期间其他 owner 正在修改实现，文中行号指当时读取的文件；后续修订应逐条关闭发现，不能把发现自动视为已验证修复。本 worker 只读代码、合同和已有结果，仅写本审阅，没有运行求解器、物理计算、单元测试、训练或实验，也没有修改实现、配置或历史结果。

执行合同是 `A25_IMPLEMENTATION_PLAN.md:3–30`。科学 gates、最终解释和是否可以继续，均由 parent Codex 决定。以下 P0/P1 是实施优先级，不是新的科学门槛。

## 必须处理的实施项

| 优先级 | 发现及影响 | 具体证据 | 最小修复/验证方向 |
|---|---|---|---|
| 原P0，已观察源码修复，生成前验证 | 唯一 admitted closure 是 **TASK_R32**；原生成器仅能构造普通 R。后次读取已调用同一个 task-weighted builder，并导出 closure provenance。不能用普通 R32替代。 | `results/a25/development/frozen_optimizer_repair/NN_CLOSURE_ADMISSION.json:3,28–36,49–63`；修复后 `src/a25/dataset.py:327–372`；builder `src/a25/campaign.py:85–108`。普通 R32 的 gradient cosine 是已记录的 0.9830193；TASK_R32 为 0.9922546。 | 继续验证 admitted builder/basis 一致，保存 requested 与 actual rank；checkpoint binding尚待下项。没有由本审阅运行数值验证。 |
| P0，质量判定前 | 新 helper 用 `||y||` 归一化 noiseless residual，冻结 A24 指标用 `||y-yb||`。强背景下总信号会掩盖扰动信号误差。新 locked evaluator 已把前者直接用于冻结 0.05 quality threshold。 | `src/a24/pilot.py:91–110`，尤其 98；`src/a25/metrics.py:52–59`；`src/a25/locked_evaluation.py:_full_audit`（读取时 187–219，quality 判定 215–218）。 | 质量门槛继续用差分信号分母；若还报告总场数据分母，另命名。白化 noisy residual 的 `sqrt(2)/sigma` 当前一致。补一个强背景、相同绝对误差但不同分母的机械 counterexample，并验证 undefined 差分分母不变成成功。 |
| P1，计时前 | 收紧 test observation loader 后，cold timing 的合法再次读取 online input 未传冻结上下文，会被拒绝，从而把所有 cold timing 记作失败。 | `src/a25/dataset.py:243–248`；`src/a25/locked_evaluation.py:_complete_timing` 的 `load_dataset(...locked_id.npz, role='online')`（读取时 282）。 | 传入已经验证的 freeze；继续只重读 online siblings，不重新打开 truth。验证合法已冻结 cold input 可读、冻结前不可读。 |
| P1，checkpoint freeze 前 | checkpoint 与 cache 的匹配只核对背景/几何 descriptor，没有绑定 Ug/Vg 的 closure/basis。普通 R32 与 TASK_R32 使用相同背景 descriptor 时可通过现有加载检查。 | `src/a24/relative_feedback.py:126–140`；`src/a25/training.py:46–59,413,438`；`src/a25/networks.py:300–308`（learned checkpoint 排除 references）；`src/a25/dataset.py:199–226`（当前 exported descriptor 不记录 builder）。 | 显式绑定 admitted closure 与冻结 cache identity/provenance，并校验实际 basis/配置一致；遵守不做 SHA256 的用户指令。已有 NPZ 不可变数组检查有帮助，但不能替代 checkpoint 与所用 basis 的匹配。 |
| P1，反馈物理主张前 | 准入的 5% task error / 0.99 cosine 只在历史四 parent 的无 NN 轨迹终点检查。CNN 可进入不同材料状态；box projection 和 core condition guard 不保证这些新状态仍满足准入精度。新 full audit 计算材料/电流残差，却没有同 estimate 的 F/R JVP/VJP 与 cosine。 | `src/a25/campaign.py:215–219`；`src/a24/pilot.py:113–132`；准入 JSON 明确 scope 是 exposed development trajectories；`src/a25/networks.py:228–241`；`src/a25/locked_evaluation.py:_full_audit`。 | parent 预先界定 learned-state fidelity 的审核范围。对指定 frozen NN 输出，在同一 estimate 上测 F/R task 与 gradient；若未测，明确 learned-state fidelity 为 NOT_RUN，不能把旧四对象准入推广为全 box/新 OOD 证书。完整材料/数据质量比较仍可单独判读。 |
| P1，完整推理成本解释 | 健康 benchmark 的 rate 不含 certified TV 初始化；locked 的 complete timing 已重新算 CPU TV，但 cold process timing从已制作的 G/J/Ug/Vg cache 出发，没有重新制作这些科学准备。 | `src/a25/training.py:293–349`；`src/a25/locked_evaluation.py:_complete_timing`；`src/a25/dataset.py:346–353`；`A25_IMPLEMENTATION_PLAN.md:28`。 | `cached_image`、`warm_complete`、`cold_process_complete`、一次独立 cache/geometry/J/basis 准备与实际共享成本分别列示。N=1/10/100 可组合真实 setup 与实测 complete image cost，但标记组成估算。不能把 cached rate 或 OS cache 未清空的 process cold 称作从零的完整部署提速。 |

本审阅没有给 TASK_R32 的新场景泛化或 NN 质量赋予 PASS，也没有把这些可修复问题判断成 Maxwell 恒等式失败。

## 已发现、期间修复的边界项

初次读取时，`tools/a25_remote.py:83` 把全部 `data/online/*.npz` 放进 training transfer；`dataset.load_dataset` 又免除 online paths 的 freeze 检查，因此 locked ID/OOD 的 observations 可在训练前到达学习主机。训练函数实际只用 train/validation，**没有发现已经使用 test 的证据**。

截止后次读取，transport 的 train scope 仅含 train/validation、manifest/geometry、background cache；locked online archives 已移至 evaluation scope，`src/a25/dataset.py:245–248` 对 locked truth 与 observations 均要求 freeze。属于源码修复已观察到，尚不能由本审阅声称测试已通过。还须处理上表 cold timing 的合法读取接口。

更后次读取还发现 `dataset.py:251–253` 增加 loaded split metadata 检查，防止正常路径名称之外的 locked split进入训练role。TASK_R32修复记录见上表；修复后 `dataset.py:355–372` 使用 admitted task builder，导出 builder/seed/background/basis identity。父线程已将 differential quality、合法cold freeze与exact cache binding交由 physics owner修复；本稿不将“已交办”写成已验证。

训练 TV 的早期实现是 full chi、裁掉 terminal row/column 后的均值；期间 owner 已改为 `delta_chi=chi-chi_b`，完整 Neumann 差分与物理积分。以下讨论基于更新后的 `training.py:145–173`，不把已替换版本继续列作当前 blocker。

## 数学目标和证书尺度

材料坐标是 `x=sqrt(V)[Re chi, Im chi]`，不是 source-wise currents，也不是未缩放的 chi。每个公共 proximal 解的是

\[
\min_{x\in C_M}\tfrac12\|x-v\|_2^2+
w\,c_V\sum_i\|(D(x-x_b))_i\|_2,
\qquad c_V=V^{(d-1)/d}/\sqrt V .
\]

`D` 对两个 real/imag 通道及全部空间方向联合取每格 isotropic norm，terminal differences 为零；`C_M` 是物理 box 乘 `sqrt(V)`。24×24 二维正方格中 `c_V=1`；对物理 chi 则同一 TV 为 `sqrt(V)*sum(norm(differences))`。相关代码：`src/a24/material_updates.py:75–120,155–205`；`src/a25/prox.py:171–239`。外层 `w=step*lambda`，`lambda=.01*(1+sigma/background_data_RMS)`；背景 mass 与 full material mass 的用法在 `campaign.py:38–49,51–83` 一致。

验收质量：固定 reference `tau=sigma=.99/(2sqrt(d))`，不随 accelerated optimizer 的 tau/sigma 变化；KKT 与 normalized gap 上限仍为 1e-6，physical box 上限 1e-10，normalization 为 `material_scale*sqrt(NV)`，material_scale=1。证书同时报告 stationarity、primal/dual fixed point、dual feasibility、TV/box complementarity，绝非迭代次数足够就成功。`prox.py:149–168,192–239,311–369`。Warm owner 与 book lock owner 分离；新外层 objective 可重用 x/p，但相同 objective 延续共用 wall/iteration allowance（`prox.py:120–125,242–260,299–321,404–413`）。

**1e-6 normalized gap 不是 1e-6 的材料误差承诺。** 在强凸性和 primal/dual 可行的条件下，mass primal-distance bound 是 `sqrt(2*raw_gap)`；归一化到物理 RMS 再除 `sqrt(NV)`。原始 dual 有 roundoff 越界时不能直接引用该界。独立 reference 的 feasible envelope 不改变 raw x/p，给出 correction distance + gap-derived bound；它注明是保守浮点 allowance，不是 interval-certified proof（`socp_reference.py:319–370,373–420`）。

Reference policy 需在最终报告写清：`Solved` 当前用生产 1e-6 KKT/gap + 1e-10 physical box 验收；`AlmostSolved` 只有 external stationarity/feasibility 1e-11、gap/complementarity 1e-10 才接受，cap/error 永不成功（`socp_reference.py:216–251`）。Parent已明确确认这个按status分支的数值验收政策。报告须逐点保留原始残差、solver status和acceptance reason，不能把所有点描述为同一个1e-11 external KKT标准，也不能用backend status替代该分支下必须评估的证书。最初independent失败仍保留。

## N0 与 N1/N2/N3 的可比性

| 比较 | 实现核对 | 可支持的解释边界 |
|---|---|---|
| N1 vs N2 | 相同10-channel source-symmetric features、full material state、three/four同深度 CNN、相同 prior increment scale、相同 box projection；只把 L closure换成 R closure，物理产生的 features自然随之改变。`networks.py:101–113,136–170,228–242,321–328`。 | 这是相同 learned capacity 的 closure intervention；还需匹配训练 schedule、冻结 cache 和完整质量/成本证据。 |
| N1 vs N3 | 同一 L features/梯度输入，N3去掉显式 `-step*gradient`，保留 learned material increment。`networks.py:201–241`。 | N3仍读取 gradient channel，因此是“去显式梯度步的通用 recurrence”对照，不能称为完全不使用物理/梯度的纯 CNN。 |
| N0 vs N2 | N0四个独立 current CNN、按源共享、receiver SVD rank15、精确 G-field与共同解析 material ratio；N0 width64，N1–3 width32；N0输入4channels，N1–3输入10channels。`networks.py:116–122,147–170,250–279`。 | N0是公开披露的 SOM-Net迁移方法 anchor，不是匹配容量的机制隔离对照，也不是官方作者代码或原实验复现。 |

原文 [SOM-Net, arXiv:2209.03567](https://arxiv.org/abs/2209.03567) 的3个输入 channel 是 current Re/Im 加材料图，BP材料初值、四个subnetwork、G-field与跨源ratio构成原方法流。A25增加 lossy material imag channel，换公共 certified TV 初值、8源/24×24、已知背景、current normalization和共同训练loss。上述 adaptation 在 `research/delegated/learning/README.md:54–79` 与 model metadata 中已披露。原文证据从本地提取文本 `../../delegated/a12_literature/text/liu_2022_som_net.txt:173–299,591–603` 读取；这里未重新下载或运行任何论文代码。未标注的 U-Net bottom width=256 是实现推断，不应写作原文已明确给定。

## Loss、梯度与全物理评价

更新后的 matched training loss 是 material/current 用相应 train-only RMS平方归一化，data用 background data norm平方，SSIM固定实/虚范围4.5/.5，TV作用于共同 delta material；四个臂相同权重和合法标签（`training.py:158–177,180–223`）。训练 data项没有冻结物理目标中的 `.5`，所以 `.1*training_data` 等于 `.2*normalized_physical_half_squared_loss`；这是共同的学习损失定义，不能把训练 total 叫原冻结物理 objective。

各臂的 data loss同样测 `S*returned_current` 与 observation：N0返回自由学到的 current；N1/N3返回 `cb+Rb*w_L`；N2返回 `cb+Rb*w_R`。其原生 material-to-data map和constraint不同，**相同权重不等于同一个 full-Maxwell material data loss**（`networks.py:269–289`；`torch_physics.py:308–323,428–445`）。训练同样获得 current labels消除了监督权限差，但不能消除近似forward的偏差。因此最终比较必须从相同 final chi 各自重新 full solve，而不能只用 model data loss或学到的 current数据拟合度。

新增 `locked_evaluation.py:_full_audit` 已在 model返回之后调用 `Physics2D.full_state(chi)`，分别记录 full/model data loss、exact TV与原物理 objective，检查 learned/approximate current 对 full current误差、`j-chi(Ei+Gj)`、field closure discrepancy、full solver residual。这是正确的 offline位置；一次 full解的 backward残差只能说明该 full解算得准，不能替代 NN returned current的物理一致性。

未发现训练状态的隐藏 stop-gradient。`TorchRelativeModel.vjp_complex/data_gradient` 的 field、h、K和非Hermitian solve仍参与autograd；guard矩阵的detach只用于离散拒绝决定；ratio阈值detach也只影响拒绝判断。见 `torch_physics.py:298–306,340–363,390–409,481–496`。`networks.py:193–199` 的初始化clone为可微恒等。training.normalizer_fit/validation的no_grad是合法统计/评估权限。需要 parent测试验证 higher derivative；已有 `tests/test_a25_torch.py:51–85` 针对JVP/VJP、显式梯度和Hessian-direction。

训练 TV是固定平滑 surrogate `sqrt(squared+1e-12)-1e-6`，去掉零状态常数，仍与 exact nonsmooth TV不同；NN block只是CNN增量/显式梯度/box projection，**没有继承公共 proximal的KKT证书**。metadata已准确写明该点（`networks.py:170`）。

## 数据、失败与成本边界

112-parent manifest实现64train/16validation/16ID/16OOD；四family各自均衡；train32是train64内每family前8个parent。OOD各family包含2 structural-combination和2 contrast parents，合计8+8；contrast幅度1.5/1.8，其他.3/1.2。两背景×两幅度形成每parent4个full-state标签，两噪声给8 observations：448标签、896 observations；不能把噪声views称作896独立物理标签。`dataset.py:14–20,50–117,127–186`。新 parents为独立抽样身份，非历史四parent的view拆分；泛化范围仍仅固定phase、背景、频率、孔径和网格的这些families/几何或contrast偏移，不是新物理域或3D。

正常训练函数和normalizer只读取train/validation。train-only features来自公共L initial状态；材料/current RMS可使用合法train labels且各臂共享。4parent batch每parent只抽一个condition，所有方法相同seed/schedule；validation每parent先均值再等权，checkpoint只按validation image NRMSE选择。`training.py:65–124,180–223,250–276,387–447`。validation的full-chi NRMSE可能较少反映强背景上的delta质量，因此最后必须共同报告full chi与delta，不能单凭selection score说扰动恢复通过。

`parent_equal`保留显式失败并只在完整时提供官方mean；paired bootstrap重采样parent均值，2000次。新locked evaluator给定manifest的16 expected parents，并先验证每parent8conditions，所有models复用同一arrays循环，修补了“两个方法同时漏掉parent会缩小统计宇宙”的调用风险。一般helper如果省略expected_parent_ids仍可能只在现存parent集合上宣告complete，且没有自行核对两个arm的case_id集合；未来使用须传完整manifest、匹配case identities（`metrics.py:76–133`；`locked_evaluation.py:_validate_split,_statistics`）。所有质量失败可保留status=OK但quality_target_hit=False，这表示输出成功、质量失败，两者不能混淆。

`BudgetLedger`从A25 terminal receipts累积失败和重跑；CPU-only=max(wall,processCPU)，CUDA=hostCPU + occupation wall单列；未闭合作业拒绝新job，label aliases合并至456上限，owner/lock被核验（`budget.py:46–101,166–229,233–303`）。更新数只按完成全部11个model配对的cost选择，不按quality选择；startup/warmup/normalization/checkpoint I/O在inclusive receipt中，不能在最终成本表删除（`training.py:293–384`）。投影、正向、adjoint与backward调用计数不替代真实wall。

缺配对、NaN、初始化失败、数值失败、quality未命中及NOT_RUN应各自保留；不能对“成功图”做官方parentmean。`campaign.py:183–225`与dataset失败行已有保留逻辑。若trajectory后段失败，当前实现把该方法各K checkpoint都标FAILED，较早有效prefix未交付；属于保守缺失和诊断信息损失，不能因此宣称更早checkpoint已通过。最终locked opening标记应保持不可删除；`validate_freeze_record`要求11个完整model和同更新数，failed opening同样暴露。

## 已有证据和未运行边界

- 最新 phase0 `DECISION.json`记录 extended PDHG 14/14，old 2/14，accelerated 1/14；原12个common initialization失败被同目标数值证书恢复，但Born replay/物理质量由后续结果另判。tight reference retry的原失败保留，当前decision为HEALTHY，不能删除 `DECISION_INITIAL.json`。
- `REFERENCE_REFINEMENT_001.json:8–20,70–81`保存 ring2404_1.2_snr20 的更严原始reference残差及AlmostSolved严格external acceptance。没有投影输出代替原始解。
- `results/a25/jobs/frozen-controls-tests-002/result.json`是47tests PASS；`differentiable-physics-tests-002/result.json`是10tests PASS。旧 `new-guards-and-prox-tests-002/result.json`仍为34tests/1setup error、旧 differentiable001失败也保留；不能把34-run历史文件写成整个run PASS。parent随后重跑的科学/机械结果应引用各自准确receipt。
- `repaired-optimizer-headroom-001/result.json`已保存3456metric rows/192task rows。最新admission选择TASK_R32，但scope只限四个exposed development parents且GPU health仍pending。此审阅没有做任何均值、gain、bootstrap或质量gate计算。
- 本次读取时尚无学习dataset目录、trained11-model freeze或locked results。因此学习收益、样本效率、OOD、完整推理提速与3D都不能从这些源码/单元验证获得GO。新增locked evaluator在本审阅中只做静态阅读，未执行。

## parent可安排的最小验证

1. 生成前：同一admitted Task builder/basis贯穿NumPy export、Torch cache、checkpoint和locked load；验证普通R32替代时拒绝。
2. 无physics机械guards：train transport无locked inputs；冻结前拒绝truth与online test，冻结后合法cold observation读取成功；完整11models/缺一个/重复一个/更新数不匹配的freeze边界。
3. 指标桥接：差分denominator、noiseless undefined值、已知Gaussian实虚方差sigma²/2白化、exact delta TV与surrogate声明；保留quality failure。
4. Parent aggregation：双臂同时少一个parent、不同condition集合、一个失败/NaN、一个duplicate，都不能形成官方PASS平均/CI。
5. 已注册budget内的physics验证：已有higher-gradient测试结果、exactfull audit和指定learned-state F/R task误差；每项缺失明确NOT_RUN，禁止用unit PASS代替learning/OOD质量证据。

以上只给审阅建议；不修改冻结科学门槛、预算、A24旧失败或准入结果。
