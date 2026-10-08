# A25 逐项八字段探索记录

本文是依据既有冻结配置、输出前登记、源代码、保存结果与不可变作业 receipt 作出的**事后忠实整合**，不是新的 preregistration，也不把登记原文的 PENDING 改写为当时已经知道的结果。没有单独八字段登记的固定候选，其假设与动机按运行前配置和实现目标说明，不声称存在未找到的事前登记。

最终解释沿用[父线程 gate decision](../../results/a25/A25_GATE_DECISION.json)：总体 HOLD；求解器健康 PASS；反馈成像 PARTIAL；压缩为 PARTIAL_DEVELOPMENT_PASS_VALIDATION_FAIL；NN、样本效率和层数实验 NOT_RUN，locked ID/OOD CLOSED_NOT_RUN，部署优势 NOT_ESTABLISHED。旧历史范围通过和新范围失败分别保留。

下列成本直接引用已接受 receipt，不重新汇总。CPU-only 作业计费为 max(wall, process CPU)；GPU作业分别记录 host CPU 与 GPU occupied wall。同一共享作业在多个候选条目出现时只是重复引用，不能重复相加；controller/transport/失败费用仍保留在全局账本。prox子步骤时间与cProfile累计时间是诊断量，不是可再加总的资源费用。

公开小型元数据与CSV通过下列相对链接读取；完整动作账本见[Release账本压缩包](https://github.com/migodam/a25-adaptive-om-feedback/releases/download/a25-v0.1.0/A25_COMPLETE_ACTION_LEDGERS.zip)，完整历史与重建数组见[Release复现数据压缩包](https://github.com/migodam/a25-adaptive-om-feedback/releases/download/a25-v0.1.0/A25_REPRODUCTION_DATA.zip)，包内采用项目相对路径。

## 1. extended PDHG：提高同目标求解的迭代上限

| 字段 | 记录 |
| --- | --- |
| Hypothesis | 原TV prox失败可能来自迭代上限不足与dual fixed-point收敛慢；增加求解工作量可以达到原证书，不需要放宽容差。 |
| Motivating evidence | 历史12个共同初始化失败及原算法14个同目标问题仅2个通过；这是优化器证据，不先归因于物理反馈。 |
| Proposed modification | 使用extended_pdhg与较大迭代上限，保持目标、mass坐标、box、TV与外部KKT/gap 1e-6、feasibility 1e-10；见[冻结campaign](../../configs/a25/campaign.json)及[prox实现](../../src/a25/prox.py)。 |
| Development experiment | phase0共14个同目标问题，包括12个历史失败、一个弱背景成功控制和active_box优化器控制；另有6个独立参考。 |
| Observed result | extended_pdhg 14/14认证，原算法2/14；保存的prox wall诊断为9.406780秒。随后同原先验的32条件九臂重放保存3456行逐步指标。见[DECISION](../../results/a25/development/phase0/DECISION.json)、[原始初始decision](../../results/a25/development/phase0/DECISION_INITIAL.json)。 |
| Decision | 父线程选择extended_pdhg，solver_health PASS；证书只认证凸prox子问题，不等于完整材料恢复或CNN块认证。 |
| New cost | 与旧算法、accelerated候选及最初参考共用[solver-certification-001 receipt](../../publication/A25_TERMINAL_RECEIPTS.json)，charged CPU 39.926064542秒；后续共享成像重放另见[repaired-optimizer-headroom-001 receipt](../../publication/A25_TERMINAL_RECEIPTS.json)，charged CPU 576.643647458秒。不把这些共享费用独立分摊后再次相加。 |
| Validation eligibility | 数值求解健康成立于声明的目标和证书。历史成像对象已暴露；独立新材料、NN与部署结论须分别有证据。 |

## 2. accelerated PDHG：固定证书下的加速候选

| 字段 | 记录 |
| --- | --- |
| Hypothesis | 强凸prox的加速更新可能比固定步长PDHG更快达到相同外部证书。 |
| Motivating evidence | 原迭代上限下的慢收敛促使比较已知加速算法；这是固定候选比较，不预设加速必然更好。 |
| Proposed modification | 仅替换prox更新为accelerated_pdhg；仍以冻结参考步长、相同gap/KKT与box门槛验收，不改目标或接受阈值。依据[phase0记录](../../results/a25/development/phase0/DECISION.json)与[实现](../../src/a25/prox.py)。 |
| Development experiment | 与extended/old算法比较同一14个问题，保留每次失败与实际求解时间。 |
| Observed result | 仅1/14认证；保存prox wall诊断26.332181秒，既未完整通过，也不是最快合格方案。见[SOLVER_COMPARISON.csv](../../results/a25/development/phase0/SOLVER_COMPARISON.csv)。 |
| Decision | 不选择accelerated候选；父线程solver_health PASS对应已选extended算法，不能移给这个候选。 |
| New cost | 已包含于[solver-certification-001 receipt](../../publication/A25_TERMINAL_RECEIPTS.json)的39.926064542 charged CPU秒；26.332181秒是该候选prox诊断，不另作资源加总。 |
| Validation eligibility | 只支持这组同目标数值比较；没有加速成像、学习或部署收益证据。 |

## 3. 独立SOCP参考的内部精度refinement

| 字段 | 记录 |
| --- | --- |
| Hypothesis | 一项独立参考的原始SOC可行性略超严格门槛，可能需要同目标内部精度收紧，而非改变材料或放宽外部验收。 |
| Motivating evidence | ring_2404、振幅1.2、20dB参考原SOC primal feasibility约1.16656e-11；原失败与DECISION_INITIAL保留。 |
| Proposed modification | 收紧Clarabel内部求解与迭代refinement精度，保持同一受约束TV/SOCP目标及原primal/dual；不做求解后primal投影。见[REFERENCE_REFINEMENT_001](../../results/a25/development/phase0/REFERENCE_REFINEMENT_001.json)。 |
| Development experiment | 仅重算该固定参考，比较原始stationarity、SOC/box可行性、gap/complementarity与extended结果；不是重新搜索问题或阈值。 |
| Observed result | refinement raw最大残差8.582402537e-12、gap9.636790064e-14，同目标对照通过。Solved按冻结KKT/gap 1e-6、box 1e-10验收；AlmostSolved额外要求raw stationarity/feasibility 1e-11、gap/complementarity 1e-10。active_box strict标志false但Solved/frozen通过，legacy exact-active diagnostic约0.656263保留。 |
| Decision | 父线程接受该同目标数值refinement，容差未放宽，原AlmostSolved不改写为Solved。可行性与强凸假设下的sqrt(2gap)是mass坐标距离界，不是1e-6材料误差保证；浮点包络不是区间严格证明。 |
| New cost | [independent-reference-refinement-001 receipt](../../publication/A25_TERMINAL_RECEIPTS.json)：charged CPU 0.838772917秒。原参考工作仍在此前receipt内，不删除或抵扣。 |
| Validation eligibility | 支持固定prox的独立数值一致性；不认证完整逆散射、CNN块或新场景成像。 |

## 4. R16：固定低秩背景反馈

| 字段 | 记录 |
| --- | --- |
| Hypothesis | 16维背景反馈因子可能保留足够材料到观测的任务信息，同时降低在线成本。 |
| Motivating evidence | 原背景线性L忽略返回反馈，原生F需要完整求解；研究目标是检查压缩反馈的实际任务保真，而非仅谱近似。 |
| Proposed modification | 使用冻结列表中的R16，因子只从已知背景构造；保持共同全网格材料、先验、初始化与12步。见[campaign候选](../../configs/a25/campaign.json)、[构模source](../../src/a25/campaign.py)。 |
| Development experiment | 历史四parent、两背景、两振幅、两噪声共32条件；独立任务探针只在各case K12终点运行。 |
| Observed result | 最大transfer 0.0774547、adjoint 0.0735810，最小cosine 0.886872，最大delta成像比/F 1.02011；eligible_physics=false。见[原始准入表](../../results/a25/development/frozen_optimizer_repair/NN_CLOSURE_ADMISSION.json)。 |
| Decision | 不进入NN候选准入。较接近的图像不能替代forward/adjoint与0.99梯度方向门槛。 |
| New cost | 背景构基、任务探针、成像和full-wave审核共享[repaired-optimizer-headroom-001 receipt](../../publication/A25_TERMINAL_RECEIPTS.json)：charged CPU 576.643647458秒；没有独立R16免费试验或重新分配费用。 |
| Validation eligibility | 历史32个K12终点范围；中间、builder、learned及OOD状态覆盖NOT_ESTABLISHED，部署提速NOT_ESTABLISHED。 |

## 5. R24：固定rank扩展候选

| 字段 | 记录 |
| --- | --- |
| Hypothesis | 固定提高rank至24可能减少R16丢失的任务方向。 |
| Motivating evidence | 冻结候选列表预先包含rank比较，用任务误差、adjoint与cosine检验rank增加是否足够；不是测试集驱动调rank。 |
| Proposed modification | 只采用R24背景因子；其余条件与同作业R16/F保持一致，依据[冻结campaign](../../configs/a25/campaign.json)。 |
| Development experiment | 同32历史条件与K3/6/12成像检查；任务审核仍只覆盖32个K12终点。 |
| Observed result | 最大transfer 0.0543111、adjoint 0.0516117，最小cosine 0.954986，最大delta比/F 1.01487；eligible_physics=false。见[原始准入表](../../results/a25/development/frozen_optimizer_repair/NN_CLOSURE_ADMISSION.json)。 |
| Decision | rank增加改善部分任务诊断，但R24仍未准入，不自动把更高rank称为成功。 |
| New cost | 同[repaired-optimizer-headroom-001 receipt](../../publication/A25_TERMINAL_RECEIPTS.json)的共享576.643647458 charged CPU秒；不再次加总。 |
| Validation eligibility | 仅已暴露开发终点；无learned/OOD保真或完整推理提速结论。 |

## 6. R32：普通背景低秩候选

| 字段 | 记录 |
| --- | --- |
| Hypothesis | 普通R32可能在固定rank上限内同时满足传递、adjoint、方向与成像准入。 |
| Motivating evidence | 固定rank16/24/32列表用于检验容量变化；任务方向门槛独立于谱误差。 |
| Proposed modification | 使用普通背景R32因子；不改成task-weighted构造，不读取未知truth构基。见[冻结campaign](../../configs/a25/campaign.json)。 |
| Development experiment | 同32历史case的成像轨迹与K12任务探针，保留完整配对。 |
| Observed result | transfer 0.0361694、adjoint 0.0347274、最小cosine 0.983019、最大delta比/F 1.00660；虽传递误差较低，cosine仍低于0.99，eligible_physics=false。见[准入表](../../results/a25/development/frozen_optimizer_repair/NN_CLOSURE_ADMISSION.json)。 |
| Decision | 普通R32不准入；不能与后述TASK_R32混称同一候选。 |
| New cost | 共享[repaired-optimizer-headroom-001 receipt](../../publication/A25_TERMINAL_RECEIPTS.json)，576.643647458 charged CPU秒包含全部固定候选与审核。 |
| Validation eligibility | 历史终点比较；不支持泛化、NN或部署PASS。 |

## 7. LOCAL_R16：局部块加低秩反馈

| 字段 | 记录 |
| --- | --- |
| Hypothesis | 局部块项可能补足普通低秩因子遗漏的局部相互作用。 |
| Motivating evidence | 局部传播与全局返回可能有不同压缩需求；该候选在冻结列表内独立于普通R16。 |
| Proposed modification | LOCAL_R16加入背景局部块与原rank16返回，保留原局部/core安全检查、材料先验和步长；见[campaign](../../configs/a25/campaign.json)与[feedback source](../../src/a24/relative_feedback.py)。 |
| Development experiment | 与F/普通R使用同32历史条件、同K检查点，任务只在K12终点审核。 |
| Observed result | 最大transfer 0.0769862、adjoint 0.0742762、最小cosine 0.903447，最大delta比/F 1.02316；eligible_physics=false。保存median online比/F为2.95360，是描述性时间比。 |
| Decision | 不准入，也不把局部项更复杂等同于更准或更快；完整部署优势仍NOT_ESTABLISHED。 |
| New cost | 共享[repaired-optimizer-headroom-001 receipt](../../publication/A25_TERMINAL_RECEIPTS.json)，576.643647458 charged CPU秒；局部构基、在线guard及失败均已计入，不另宣称免费。 |
| Validation eligibility | 原历史K12终点；无中间、learned或OOD覆盖，不由描述性时间比推断cold/warm部署速度。 |

## 8. TASK_R32：任务加权构基及新范围反证

| 字段 | 记录 |
| --- | --- |
| Hypothesis | 在同rank32预算内，用已知背景的材料/观测任务信息构基，可能比普通R32保留更重要的梯度方向。 |
| Motivating evidence | 固定候选需要同时满足forward、adjoint与cosine，而不是只看背景算子的谱误差。source与[原准入artifact](../../results/a25/development/frozen_optimizer_repair/NN_CLOSURE_ADMISSION.json)声明truth_used_in_builder=false。 |
| Proposed modification | TASK_R32使用固定背景任务加权因子；保持共享材料、先验、decoder设计与监督权利，不由locked质量选择rank。见[获准NN配置](../../configs/a25/nn_admitted.json)。 |
| Development experiment | 先检查历史32个K12终点；后来另行登记并运行窄范围validation16检查，该检查不是原准入的隐含覆盖。 |
| Observed result | 历史最大transfer 0.0236488、adjoint 0.0222806，最小cosine 0.992255、最大delta比/F 1.00487，eligible=true。新32个窄validation终点transfer 0.0178222、adjoint 0.0168199，但cosine最小0.975687，最大材料比/F 1.01382；见[PARENT_REVIEW](../../results/a25/development/prospective_regime_validation/PARENT_REVIEW.json)。 |
| Decision | 旧PASS_DECLARED_DEVELOPMENT_SCOPE原样保留；新范围FAIL_FIXED_K12_ENDPOINTS；父线程总体压缩PARTIAL_DEVELOPMENT_PASS_VALIDATION_FAIL。NN仍NOT_RUN，不能继续外推历史准入。 |
| New cost | 历史比较共享[headroom receipt](../../publication/A25_TERMINAL_RECEIPTS.json)，charged CPU 576.643647458秒；新检验共享[prospective receipt](../../publication/A25_TERMINAL_RECEIPTS.json)，charged CPU 50.316845750秒。后者在第14项再次引用，不重复相加。 |
| Validation eligibility | 两次任务审核均只覆盖各自K12终点。validation现已暴露；builder、中间、learned与OOD范围仍NOT_ESTABLISHED。 |

## 9. TV×0.1：共同降低正则权重

| 字段 | 记录 |
| --- | --- |
| Hypothesis | 原TV权重可能压制材料增量；共同降为0.1倍可能改善材料与边缘恢复。 |
| Motivating evidence | [输出前TV登记](TV_SINGLE_FACTOR_PREREGISTRATION.md)记录原32条件更新均接受、K12增量误差仍约0.76、边缘误差接近1；未见回溯拒绝瓶颈。 |
| Proposed modification | 所有九臂的初始化和迭代共同用TV×0.1，其余背景、噪声、box、步长、求解器及12步保持原样；不修改冻结NN的TV×1协议。 |
| Development experiment | 四历史parent、32共同观测、九臂；保存各步full-wave审核及K3/6/12图像。 |
| Observed result | 保存3456行逐步指标；弱背景振幅1.2的F相对L平均parent改善0.1602673，ring振幅1.2为0.0831618；F在32条件中共同质量命中1例，尚非完整配对质量区域。见[regime freeze](../../results/a25/development/REGIME_HYPOTHESIS_FREEZE.json)。 |
| Decision | 保留为单因素开发探索与窄regime假设；不替代原协议的aggregate改善约5.699%，也不直接授予NN或部署PASS。 |
| New cost | [tv-shrinkage-exploration-001 receipt](../../publication/A25_TERMINAL_RECEIPTS.json)：charged CPU 337.139667000秒；新增clean labels为0，估计审核与I/O仍收费。 |
| Validation eligibility | 当时仅四个已暴露parent的开发证据；后续独立窄范围检查单列，不将这组重新命名为blind test。 |

## 10. 振幅1.8：固定高幅度检验

| 字段 | 记录 |
| --- | --- |
| Hypothesis | 更大的相对材料变化可能扩大同背景下完整F相对线性L的收益。 |
| Motivating evidence | [输出前振幅登记](AMPLITUDE_PREREGISTRATION.md)引用历史高幅度差异及TV0.1的开发迹象；聚合证据仍不足。 |
| Proposed modification | 仅增加振幅1.8，保持原TV×1，比较L/F/TASK_R32；几何与种子不变。见[固定配置](../../configs/a25/development_amp1p8.json)。 |
| Development experiment | 四历史parent×两背景×clean/20dB，16条件；生成8个新增clean states，K12及K3/6检查点。 |
| Observed result | 保存576行逐步指标；F/L平均parent改善弱背景0.1928916、ring背景0.0831723。见[regime freeze](../../results/a25/development/REGIME_HYPOTHESIS_FREEZE.json)与[原始METRICS](../../results/a25/development/amplitude_1p8/METRICS.csv)。 |
| Decision | 只保留高幅度开发结果；不是原TV0.1实验，也不用于locked选rank。112独立parent的448个学习clean states加这8个state已经用完456新增标签额度；学习未启动。 |
| New cost | [high-amplitude-development-001 receipt](../../publication/A25_TERMINAL_RECEIPTS.json)：charged CPU 88.657146125秒，8个新clean states计入共享quota；不另外生成替补标签。 |
| Validation eligibility | 已暴露开发对象；1.8物理幅度已经暴露，后续OOD不能宣称它从未出现过。无三维或部署结论。 |

## 11. batched finite guard：集中读取有限性predicate

| 字段 | 记录 |
| --- | --- |
| Hypothesis | optimizer后逐parameter CUDA布尔读取可能引入多次同步；集中读取同一predicate可能降低host成本。 |
| Motivating evidence | [运行前登记](RUNTIME_PREREGISTRATION.md)与保留health001成本选择显示11模型×500更新预测CPU 8987.46875秒、GPU 9507.509367秒，无法容纳冻结CPU分配。 |
| Proposed modification | 所有parameter的isfinite/all照常执行，GPU上stack/all后只读一次布尔；clip仍error_if_nonfinite=True，不改网络、物理、精度或ledger检查。见[nn_batched_checks](../../configs/a25/nn_batched_checks.json)。 |
| Development experiment | known-background七拓扑、每种两次health重复；不做科学训练、不读取test。 |
| Observed result | health002完整；11模型×500成本预测CPU 8432.125秒、GPU 8971.716533秒，成本选择仍INSUFFICIENT_BUDGET。这是预测与health结果，不是训练收益。 |
| Decision | 作为runtime-only修改保留；不据此宣称成像、样本效率或参数效率提升，NN保持NOT_RUN。 |
| New cost | [health002 receipt](../../publication/A25_TERMINAL_RECEIPTS.json)：host CPU 30.84375秒、GPU占用33.328902500秒。基线[health001 receipt](../../publication/A25_TERMINAL_RECEIPTS.json)的host CPU 34.9375秒、GPU40.864020700秒保留；controller/transport另在全局receipt中，不抵扣或重复计算。 |
| Validation eligibility | 数值运行时与known-background健康证据；不是训练、validation质量或locked结果。 |

## 12. blocking wait：改变CUDA等待方式

| 字段 | 记录 |
| --- | --- |
| Hypothesis | 默认同步等待可能消耗host CPU；blocking-sync可能减少等待时的CPU成本。 |
| Motivating evidence | [运行前等待策略登记](RUNTIME_BLOCKING_WAIT.md)说明batched guard后最低11模型×500预测仍超过CPU分配，而GPU预测可以容纳。 |
| Proposed modification | 仅在全新进程primary context初始化前配置blocking wait；保留全部同步、预算、finite与core检查，不改physics、dtype、网络或容差。见[nn_blocking_wait](../../configs/a25/nn_blocking_wait.json)。 |
| Development experiment | 与此前相同七拓扑、两次known-background health重复，分别测真实process CPU及GPU占用。 |
| Observed result | health003完成且被[HEALTH_INDEX_PROVENANCE](../../results/a25/learning/HEALTH_INDEX_PROVENANCE.json)明确采用；11×500预测CPU 6682.8125秒、GPU 7655.196060秒。相对冻结host CPU allowance 3000秒仍不符合，updates=null、INSUFFICIENT_BUDGET。 |
| Decision | 父线程learning NOT_RUN，科学训练更新0、checkpoint0；GPU健康不等于公平11模型研究已经启动，也不自动扩预算。 |
| New cost | [health003 receipt](../../publication/A25_TERMINAL_RECEIPTS.json)：host CPU 24.0625秒、GPU占用28.776479800秒；前两次及controller费用保留。预测训练费用不是已发生训练费用。 |
| Validation eligibility | runtime-only health与成本准入；不能作为NN质量、OOD或部署速度证据。 |

## 13. 单次update profiler与保留的中断尝试

| 字段 | 记录 |
| --- | --- |
| Hypothesis | 用profile定位完整可微update的host耗时，有助于判断下一步优化方向；不先假设某项telemetry就是全部瓶颈。 |
| Motivating evidence | blocking wait后完整匹配矩阵仍不符合CPU分配，需要保存实际update及检查开销，而不是从GPU可达性推断可训练。 |
| Proposed modification | 在known-background health条件下对N2b3做一次warmup及一次profiled update，保留原同步和成本检查。见[PROFILE_UPDATE](https://github.com/migodam/a25-adaptive-om-feedback/releases/download/a25-v0.1.0/A25_COMPLETE_ACTION_LEDGERS.zip)。此条按已执行source与结果事后整理，不声称新增独立事前八字段登记。 |
| Development experiment | attempt004遭遇一次SystemError并终止；attempt005独立重试完成。没有科学训练或test读取。 |
| Observed result | attempt005被profile的N2b3 update wall 1.196335600秒、process CPU 1.125秒；budget.check的cProfile cumulative WALL为0.2552305秒，是非可加诊断，不是CPU费用组成。attempt004 receipt为INTERRUPTED。 |
| Decision | 不从完整时间减去该cProfile项宣称潜在提速；没有“移除telemetry便足以容纳全矩阵”的证据。SystemError保留，不因单次异常归因于模型、blocking wait或guard。 |
| New cost | [attempt004 receipt](../../publication/A25_TERMINAL_RECEIPTS.json)：host CPU 1.234375秒、GPU2.053922900秒；[attempt005 receipt](../../publication/A25_TERMINAL_RECEIPTS.json)：host CPU 4.3125秒、GPU5.401983000秒。失败、warmup、profile与controller皆保留，不只收取1.125秒被profile更新。 |
| Validation eligibility | 仅profile/health运行时诊断；无NN质量、训练、成像加速或locked证据。 |

## 14. prospective validation16：冻结窄regime的无NN检查

| 字段 | 记录 |
| --- | --- |
| Hypothesis | 弱背景、振幅1.2、共同TV×0.1、K12下，F相对L的parent平均相对delta误差改善至少10%。 |
| Motivating evidence | 四个历史开发parent在该regime平均改善约16.03%；这只提出假设。原假设见[REGIME_HYPOTHESIS_FREEZE](../../results/a25/development/REGIME_HYPOTHESIS_FREEZE.json)。 |
| Proposed modification | 不改变source优化器/physics；只复用新数据集中先前未使用的16个validation parent，固定L/F/TASK_R32、既存clean/20dB观测和seed。见[输出前冻结config](../../configs/a25/regime_validation.json)及[原八字段结果](PROSPECTIVE_REGIME_RESULT.md)。 |
| Development experiment | 四family各4个parent；32条件×3臂×12步，2000次paired parent bootstrap；最多300秒CPU wall；无新增clean labels，只做新的估计full-wave审核。 |
| Observed result | 16parents完整；主指标平均配对改善10.5170393%，CI95为[6.5943542%,15.3156867%]；次指标均值误差比改善9.4180840%，两者不可互换。family改善：asymmetric 3.8877133%、mixed 8.2909457%、shell 6.7308322%、smooth 23.1586661%。TASK_R32 transfer最大1.7822204%、adjoint最大1.6819885%，但cosine最小0.975687<0.99，材料误差/F最大1.0138213；L/F/TASK共同质量命中均0/32。见[SUMMARY](../../results/a25/development/prospective_regime_validation/SUMMARY.json)、[PARENT_REVIEW](../../results/a25/development/prospective_regime_validation/PARENT_REVIEW.json)。 |
| Decision | 父线程支持正向窄regime改善；点估计达到10%，但区间下界未达到10%，故不确认formal最小10%收益。新范围压缩FAIL_FIXED_K12_ENDPOINTS；整体成像PARTIAL/压缩PARTIAL，NN NOT_RUN、加速NOT_ESTABLISHED，不自动扩大。 |
| New cost | [prospective-regime-validation-001 receipt](../../publication/A25_TERMINAL_RECEIPTS.json)：charged CPU 50.316845750秒；复用标签早已在数据生成作业付费，构基、prox、全部估计审核、I/O与bootstrap在本新作业收费。父线程审阅另在其独立receipt中。 |
| Validation eligibility | 这是prospective no-NN validation/development复用，现已暴露；不是locked ID/OOD或NN blind test，不能再次称这16个对象为untouched test。固定family首parent图片不是质量挑选。 |

## 15. 8次backtracking：未运行方向

| 字段 | 记录 |
| --- | --- |
| Hypothesis | 若更新失败来自回溯机会不足，更多半步重试可能有帮助；这是待检验可能性，不是已证实修复机制。 |
| Motivating evidence | 原冻结配置max_half_step_retry=1；[TV登记](TV_SINGLE_FACTOR_PREREGISTRATION.md)反而记录认证重放更新均接受，未见回溯拒绝瓶颈，不能把现有成像误差先归因为重试次数。 |
| Proposed modification | 待测方向是把最多半步重试由1提高至8，并对全部匹配臂共同改变。未找到已执行的新8次配置或输出前独立登记；本条不创建或启用它。 |
| Development experiment | NOT_RUN；[原campaign](../../configs/a25/campaign.json)仍冻结1次retry、12步，没有8-backtracks运行、参数搜索或标签生成。 |
| Observed result | NOT_RUN；没有可引用的8-backtracks误差、速度、成功率或receipt，不能以其他探索的结果代替。 |
| Decision | 保持NOT_RUN，不改当前协议、源码、预算与父线程HOLD裁决；不把未执行思路列为实验成功。 |
| New cost | 无对应8-backtracks实验receipt或已发生实验成本；不制造0成本成功记录，也不把本Markdown整理计成已执行数值探索。 |
| Validation eligibility | 无验证资格；未来若获准，需要独立输出前登记、匹配条件与实际计费。本文件不是该未来登记。 |

以上整合没有修改任何结果、原冻结MD/config、source模型、求解器或gate，也没有重跑计算。原始失败与原始登记仍是可复核证据的一部分。


公开作业receipt链接指向不可变receipt的脱敏汇总，可按job ID查找；逐文件原件与PROFILE_UPDATE在账本Release ZIP的项目相对路径中。CSV和实验JSON仍可直接在仓库读取。
