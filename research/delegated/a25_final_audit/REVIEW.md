# A25 最终独立审计

审计方式：只读已保存结果、协议与代码，未执行任何求解器、训练、物理计算、测试、bootstrap 或远程访问，未修改源码、门槛或结果；只写本审计说明。不进行 hash 检查。下述判定是供父线程科学复核的建议。

**建议维持：公共 TV 求解器 HEALTHY（限已验证实例）；反馈收益仅为 development；TASK_R32 在公开声明的开发端点范围内 PASS；科学 NN 训练 / NN 优越性 / OOD / 完整推理加速均 NOT_RUN；locked 仍 CLOSED。** 没有发现可据以扩大这些结论的独立实验。以下八项是最终报告应保留的证据边界与可修复问题。

## 1. Phase 0 的数值健康成立，但需公开两种参考验收政策与原失败

`results/a25/development/phase0/DECISION.json:2–39` 记录 extended PDHG 14/14，旧 PDHG 2/14、accelerated PDHG 1/14；仅 extended 被选中。旧初始失败12个保留。最初独立参考未全部通过，因此 `DECISION_INITIAL.json` 仍为 UNHEALTHY；新判定明确引用 `independent-reference-refinement-001`，没有覆盖历史结果。

收紧内部精度后，`REFERENCE_REFINEMENT_001.json:8–19,73–101` 的 ring_2404_1.2_snr20 原始返回仍为 **AlmostSolved**，外部最大残差 **8.5824025e-12**、raw gap **9.6367901e-14**，符合额外严格外部证书；原始 x/p 未投影或 snap。原失败最大项实际是 **SOC primal feasibility 1.1665626e-11**，不是 epigraph dual stationarity：见 `INDEPENDENT_REFERENCE.json:724–735`。如报告解释失败字段，应使用这个准确名称。

验收政策必须明确区分：`socp_reference.py:216–240` 对 **Solved** 仍要求 frozen 外部 KKT/gap≤1e-6、physical material box≤1e-10；对 **AlmostSolved** 额外要求 stationarity/feasibility 项≤1e-11、gap/complementarity≤1e-10，并要求未超时。并非所有参考都通过严格1e-11政策。特别是 active_box 的 raw explicit stationarity约1.49e-15、最大外部项1.36e-10；它按 Solved+frozen certificate 接受，严格标志为false。其 legacy exact-active-bound 诊断约 **0.656263** 没有被悄悄修成通过（`INDEPENDENT_REFERENCE.json:1202–1273,1296–1320`）。这是近边界 IPM 点与原精确 active-set stationarity 诊断的差别，需要与 raw box multipliers 一并解释，不能宣称所有算法的旧诊断逐项相同。

可修复的报告要求：同时展示 solver_status、acceptance_reason、raw 外部证书、legacy 诊断和独立重试成本；将 AlmostSolved 的处理称为显式、父线程批准的协议实现解释。数值健康不等于成像质量或全状态统一保证。

## 2. TV 与证书尺度仍冻结；gap 不是材料误差本身

`prox.py:149–189,192–213` 固定 tolerance1e-6、feasibility1e-10、material scale1。材料质量坐标为

\[
x=\sqrt{v_c}\,[\Re\chi;\Im\chi],\quad
\min_{x\in B_{\rm mass}}\tfrac12\|x-z\|_2^2
+w\,\frac{v_c^{(d-1)/d}}{\sqrt{v_c}}
\sum_j\|D(x-x_b)_j\|_2.
\]

两条实/虚材料通道与所有空间方向共同进入每格 isotropic 范数；Neumann D 及 box 的质量变换继承 A24（`a24/material_updates.py:44–72`）。本24×24、side1的二维实例中 TV 系数为1、physical mass scale为1，但这不允许推广时丢掉体积系数。诊断仍使用 **tau=sigma=.350017856687341**，而非内部加速后增长的 sigma；`prox.py:210–212,312` 及保存的 `HISTORIES.json` 均明确该固定参考步。

强凸目标允许以 raw gap 导出条件性的 sqrt(2 gap) 质量坐标误差界，**gap≤1e-6不等于材料距离≤1e-6**。当原始 dual 仅有浮点微小越球时，应使用记录的 certificate-only feasible envelope 与 correction+gap allowance；不得据此接受投影后的求解输出。`socp_reference.py:319–370` 明确“conservative floating point allowance, not interval certification”。Phase0 当前比较使用 robust envelope（`phase0.py:73–79`），不要求非唯一 dual 向量相等。报告不可称其为区间算术严格物理证明。

## 3. TASK_R32 的 PASS 是32个K12端点，不是全轨迹或NN状态

`NN_CLOSURE_ADMISSION.json:50–63`：完整32条件，最大 independent transfer **2.3648839%**、adjoint **2.2280626%**、最小 gradient cosine **0.99225463**、最大差分图像误差比 F **1.00486795**；这些满足声明的 task/图像阈值。R16、R24不满足误差/余弦条件，普通R32虽误差<5%，余弦最小 **0.9830193** 仍失败；不能把 TASK_R32 的通过外借给普通R32或R16。

关键范围：`campaign.py:216–219` 只在 `states[-1]['chi']` 调用 task_audit；`a24/pilot.py:113–132` 在同一估计材料处、独立于 builder 的固定随机 probes/loads 中比较。因此 PASS 覆盖 **每条件K12端点**，并非每个中间K3/K6/迭代状态，更不覆盖未训练NN的状态或新112-parent数据。随机有限 probes 的集合误差也不是全 Jacobian operator norm 的统一上界。

Builder 只使用已知背景与固定 background probes，未使用材料 truth（`campaign.py:85–108`）；但选 TASK_R32 已使用四个历史开发 parent 的表现。故“无oracle builder”与“选择已暴露”应同时报告。`new_scene_generalization=NOT_ESTABLISHED` 仍正确。

## 4. 同 prior 的局部反馈迹象可报告；TV×0.1是另一开发实验

两个32条件实验的九臂K3/6/12表都标记完整、零失败/缺失；`PARENT_EQUAL_SUMMARY.csv` 是先在 parent 内对8条件等权、再对四parent等权（`analysis.py:17–33`），未使用成功图筛选。K12保存的总体数值如下，均为开发描述量：

| TV multiplier | 方法 | delta NRMSE | full material NRMSE | 差分数据 relative residual | joint quality hits /32 |
|---|---|---:|---:|---:|---:|
| 1.0 | L | .803725 | .361993 | .417489 | 0 |
| 1.0 | F | .757917 | .328058 | .328440 | 0 |
| 1.0 | TASK_R32 | .758536 | .328449 | .328913 | 0 |
| .1 | L | .723377 | .349951 | .283176 | 0 |
| .1 | F | .670086 | .313911 | .168927 | 1 |
| .1 | TASK_R32 | .670983 | .314384 | .169490 | 1 |

证据为 `development/{frozen_optimizer_repair,tv_multiplier_0p1}/PARENT_EQUAL_SUMMARY.csv`。TV减小在 ring 上改变重建，而在 weak 幅度.3并无同方向改善；不能从表中得出“反馈在全部背景改善≥10%”。`REGIME_HYPOTHESIS_FREEZE.json:19–62,79–123` 记录的 parent 平均 F/L gain：weak/amp1.2为原TV **15.8861%**、TV×.1 **16.0267%**；ring/amp1.2分别 **4.72468% / 8.31618%**。weak/amp1.2的原四parent gain中有 **8.8355%**，因此均值>10%不等于每parent>10%，也不等于已获得≥10%的独立置信区间。

`TV_SINGLE_FACTOR_PREREGISTRATION.md:7–17` 明确所有臂共同改变TV与初始化中的TV，NN独立协议仍使用原TV1.0。TV×.1不能改写 A24 frozen prior 或从中择优拼接正式同-prior比较。冻结的 regime 内容是下一独立实验的假设，仍缺独立确认。幅度1.8补充也已暴露；future contrast OOD包含1.8时只能说新parent/结构泛化，不能说首次见到该幅度。

## 5. 报告必须区分三种归一化与代理物理数据损失

无NN更新的目标数据项使用背景范数 ||yb||²，TV按共同lambda；质量审核使用真正完整离散TM Maxwell重新求解的 prediction，并以差分观测 ||y-yb|| 作相对残差分母（`a24/pilot.py:97–111`、`campaign.py:204–211`），有噪声时另用真实白化范数。不得把该 residual称为除以 ||y|| 的总场残差，也不得把 clean_prediction_relative_error 列当作差分残差。

NN设计的监督权重与训练 normalizer 相同，不意味着各臂数据/当前物理项是同一个函数：`networks.py:154–156` 的 N2 使用 R，其他材料臂使用L；`training.py:183–202` 用各臂 result.data/current 与完整标签构造同权重损失。未来若训练，必须明确“匹配损失形式/权重，模型自身物理prediction不同”，并以共同完整Maxwell审核比较终值；不能用自身 surrogate residual宣布物理一致性已相同。当前训练未运行，不能把这项实现设计转为结果。

## 6. Paid runtime改善仍不支持全矩阵训练或完整加速

完整 child receipt保留：attempt001 CPU/GPU **34.9375/40.8640 s**；finite-batch002 **30.84375/33.3289 s**；blocking003 **24.0625/28.7765 s**；profile004为 INTERRUPTED **1.234375/2.05392 s**；profile005 **4.3125/5.40198 s**。对应 controller/import/stop tail 亦有单独 **exclusive** receipt，不能漏掉或再与其完整父时间重复相加。失败和预热均已收费。

003的原始 `COST_SELECTED_UPDATES.json` 在 `transport_variants/0487aad8c8c5487480c9b27633c4a052/results/a25/learning/`（另有同内容副本）记录11作业、500更新 CPU **6682.8125 s**、GPU **7655.19606 s**；相对于frozen NN allowance **3000/9900 s**，CPU仍失败。审计读取时49份完整job receipt共收费CPU约 **1505.04 s**，整体7200 cap剩约 **5694.96 s**，也小于6682.81；该快照随后续报告作业追加而变化。不能把已付开发费作为额外额度，不能仅训练一个N2或删必需模型来声称完成冻结比较。

profile005明确 HEALTH_ONLY、科学训练false、test未读；其单次N2b3 CPU **1.125 s**、含最终同步wall **1.1963356 s**。cProfile 的 one_update累计wall **1.1891406 s**，budget.check累计 **.2552305 s**（70 calls；`pstats_cumulative_top60.csv:2,15–16`）；继承 CostBook.check的.1832072是其子项，**不能加在.2552305上**。累计wall不是CPU归因、不是无仪器对照，也不是全部11拓扑长训练率；删除它后仍需真实计费复测、所有guard/owner/资源保障及全矩阵预测。不支持“去掉telemetry就能容纳”或隐藏CPU成本。

同理，原 TASK_R32 median online/F **.8900843**（约11% online减少）排除了准备与离线审核，且原先joint quality为0；不能声称达到20%完整相同质量提速。TV×.1更快的prox时间与不同prior/另一次作业绑定，不证明rank32的通用冷启动加速。NN推理、冷/温N部署、完整训练成本收益均 NOT_RUN。

## 7. 可修复的最新结果索引风险

审计读取时，`learning/HEALTH_INDEX_PROVENANCE.json:2–3` 与根 `COST_SELECTED_UPDATES.json` 仍指002，CPU预测 **8432.125**。003原始记录在 transport variants，根结果尚未切到它；`reporting.py:594–598,626–628` 只收 health_attempts与根索引，因此最终报告若仅运行现有入口，可能漏003或以002作为latest。需要由所有者在最终报告前明确映射003，保留001/002/004/005、来源与所有费用，不按最优拓扑/单样本拼接rate。本审计不修改索引。若父线程随后完成修复，这项标为已修复即可，不必重跑任何物理计算。

## 8. NN NOT_RUN / locked CLOSED成立，但只对应未做科学评价

`NN_SOURCE_FREEZE.json` 是 **FROZEN_BEFORE_TRAINING** 的源码/方法冻结、selected_closure TASK_R32、locked_test_inputs_read=false；它不等于模型候选已训练并冻结。审计时未发现 TRAINED_MODELS.json、MODEL_FREEZE.json、LOCKED_OPEN.json。`locked_evaluation.py:56–81` 强制11个完成训练且同更新数的模型与精确checkpoint集合；`:84–98` 一次性open reservation保留失败/中断暴露。`dataset.py:244–255` 对路径与split元数据均拒绝未获freeze的locked输入。本审计只读取公共 manifest/元数据，没有读取任何locked arrays或truth。

`dataset/GENERATION.json` 表明448标签、896观测已生成且初始化失败列表为空；生成并存储locked truth是计划的一部分，并不等于锁定科学评价已打开。112parent数据的4类ID以及8结构组合/8contrast OOD manifest只是设计与数据准备。known-background health中确实有 optimizer.step，报告应写“已付费健康更新，未启动科学训练”，避免字面“从未运行NN/更新”。不能提出样本效率、N2独立增量、层数收益、OOD性能或NN质量失败；其状态应为未运行、成本门未获准。

物理范围仍为24×24二维TM、8source/32receiver、给定被动复相位与两种已知背景；完整离散Maxwell残差是数值审核，不能外推三维vector-Maxwell、普适能量/光学定理或未知背景恢复。A24原失败与G2反例不因A25求解器修复而改写。

## 交付判断

科学结论保持上述有限状态是安全且有证据支持的。优先修复 **003索引** 与 **TASK_R32端点范围措辞**；其余属于必须公开的数值政策、prior、测量与泛化限制，不需要为这份结论补跑实验或改变门槛。若最终报告已修复这些问题，当前证据没有理由把NN未运行改成成功或失败，也没有理由打开locked split。
