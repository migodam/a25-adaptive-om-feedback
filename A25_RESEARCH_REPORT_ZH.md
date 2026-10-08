# A25：自适应OM反馈研究报告

数学与接口的96项测试全部通过；实际成像、压缩、学习与部署仍分别按各自门槛裁决，详见[数值验证与证据边界](NUMERICAL_VERIFICATION.md)。复现环境和逐阶段入口见[REPRODUCING_A25.md](REPRODUCING_A25.md)。

逆散射研究希望从有限的接收数据恢复空间材料。理解这一问题，先要从场的传播和多次散射出发：每个照明源激发的电流受同一材料控制，电流又通过内部传播改变局部场。已知强背景会重塑这条反馈链。材料图准确、满足完整波动方程、以及获得部署速度，是三个需要各自证据的问题。

A25保持24×24二维TM、8个源和32个接收点。材料是576个复数单元，真实材料坐标1152维；每个场景有512个实数观测。所有方法使用同一全网格材料、box约束和TV先验。二维证据不扩展为三维vector-Maxwell结论。

原始记录、失败和未运行项是报告的一部分。历史四parent2401–2404是公开development对象；它们不提供新场景盲测。训练/validation与一次locked ID/OOD各自标注，理论表达、数值认证、成像结果、学习收益和部署结论分别裁决。冻结协议重放、TV×0.1单因素探索、振幅1.8追加检验各自保留，不将后两项重新命名为原协议。

[A24 冻结研究报告](https://github.com/migodam/a24-source-anchored-om-feedback/blob/ca80ca2a29867e1b03589061dd5c17688c9acbe0/A24_RESEARCH_REPORT_ZH.md)，[SOM-Net 原论文](https://arxiv.org/abs/2209.03567)，[A24 文献读取范围](theory/SOURCES_AND_READING_LEDGER.md)。

## 阅读与证据入口

- [A25_START_HERE.md](A25_START_HERE.md)
- [SOLVER_REPAIR_REPORT.md](SOLVER_REPAIR_REPORT.md)
- [FEEDBACK_HEADROOM.md](FEEDBACK_HEADROOM.md)
- [CONVERGENCE_VS_RUNTIME.md](CONVERGENCE_VS_RUNTIME.md)
- [FEEDBACK_COMPRESSION_EXPLORATION.md](FEEDBACK_COMPRESSION_EXPLORATION.md)
- [FEEDBACK_REGIME_MAP.md](FEEDBACK_REGIME_MAP.md)
- [SOMNET_MIGRATION_PILOT.md](SOMNET_MIGRATION_PILOT.md)
- [EXPLORATION_LEDGER.md](EXPLORATION_LEDGER.md)
- [LOCKED_VALIDATION.md](LOCKED_VALIDATION.md)
- [A25_FINAL_RESEARCH_DECISION.md](A25_FINAL_RESEARCH_DECISION.md)

## 同目标TV求解器修复与独立证书

求解器未完成一个受约束凸子问题时，下一幅图像的差异混合了物理模型与优化误差。先认证相同目标，才能讨论完整反馈是否有成像收益。这里的证书针对TV prox，不等于完整逆散射已恢复正确材料。

已保存 phase0 状态：HEALTHY；选择算法：extended_pdhg。

| 算法 | 证书通过 | 同目标问题数 | prox wall秒 |
| --- | --- | --- | --- |
| old_pdhg | 2 | 14 | 2.99712 |
| extended_pdhg | 14 | 14 | 9.40678 |
| accelerated_pdhg | 1 | 14 | 26.3322 |

| 对象/优化器控制 | Clarabel原始status | 严格外部证书 | 验收原因 | KKT | normalized gap | 同目标对照 |
| --- | --- | --- | --- | --- | --- | --- |
| ring_2401_1.2_zero | AlmostSolved | True | strict_external_reference_certificate | 4.1516e-12 | 4.09729e-14 | True |
| ring_2402_1.2_snr20 | Solved | True | solver_solved_and_external_certificate | 6.93213e-11 | 7.85229e-12 | True |
| ring_2403_0.3_zero | AlmostSolved | True | strict_external_reference_certificate | 8.3513e-12 | 9.98414e-14 | True |
| ring_2404_1.2_snr20 | AlmostSolved | False | REFERENCE_STATUS_OR_EXTERNAL_CERTIFICATE_FAILED | 1.16656e-11 | 7.39207e-13 | False |
| weak_2401_0.3_zero | Solved | True | solver_solved_and_external_certificate | 1.55369e-11 | 2.07555e-12 | True |
| active_box | Solved | False | solver_solved_and_external_certificate | 1.35576e-10 | 7.69156e-11 | True |

外部 normalized gap/KKT目标保持1e-6，box feasibility保持1e-10；加速算法仍按固定原始参考步长验收。Clarabel原始 solver_status 单列保留，AlmostSolved 不改写成 Solved。独立参考内部精度收紧属于同目标 numerical refinement，未降低外部容差。原始失败、DECISION_INITIAL及REFERENCE_REFINEMENT_001同时保留。严格独立参考证书、虚拟可行包络和原始primal/dual输出各自保留；浮点包络不表述为区间严格证明。

验收分两类：Solved按冻结KKT/normalized gap≤1e-6、box feasibility≤1e-10验收；AlmostSolved除冻结检查外，还要求原始stationarity/feasibility≤1e-11及gap/complementarity≤1e-10。不能写成所有参考都通过1e-11严格标准。active_box的strict标志为false，但Solved与冻结证书通过；其legacy exact-active diagnostic约0.656263仍保留，不替代现行冻结验收。

ring_2404、振幅1.2、20dB的原始失败包含SOC primal feasibility约1.16656e-11；同一QP经内部refinement后，原始最大残差约8.5824e-12、gap约9.63679e-14。修复收紧独立参考的内部数值精度，目标、box与对外容差保持原样。在已声明的可行性与强凸假设下，导出的√(2gap)是mass坐标中的距离界；gap阈值1e-6不等于材料误差已达到1e-6。CPU软件环境版本按SOURCE/REPRODUCING的Python3.13.13记录。

原始来源：[SOLVER_COMPARISON.csv](results/a25/development/phase0/SOLVER_COMPARISON.csv)、[INDEPENDENT_REFERENCE.json](results/a25/development/phase0/INDEPENDENT_REFERENCE.json)、[refinement](results/a25/development/phase0/REFERENCE_REFINEMENT_001.json)。

## 完整反馈的成像余量

已知背景产生参考场 e_b。材料变化 h 首先产生 h e_b 的强迫，再由内部反馈反复传播。L只保留背景线性响应；F在当前材料处重算完整反馈；R以固定已知背景构造的因子近似回传。简写为 w=(I-diag(h)G_b)^{-1}diag(h)e_b、y=y_b+D_bw。这些表达式说明每个源共享同一材料，不能把单源current拟合自动视为合法完整材料图。source anchor处forcing-P消失属于特定代数恒等式，保留下来的反馈耦合及其任务误差仍需要检验。

在已公开开发对象上，L/F/R固定材料先验、共同初始化和K=3/6/12。完整χ误差可能被大背景掩盖，因此同时报告增量、实虚部、边缘、支撑IoU及完整场残差。相同观测下某个方法失败时保留其位置，不把成功图单独拼成配对。

### 冻结协议：认证求解器重放

原TV权重、原32条件；仅修复同目标求解器。

| 方法 | K | OK条件 | 应有条件 | 完整parent配对 | 增量NRMSE | 完整χ NRMSE | 边缘NRMSE | 支撑IoU | 完整场相对残差 | 质量命中数 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| AFFINE_ROM32 | 3 | 32 | 32 | True | 0.873807 | 0.398876 | 0.993047 | 0.291806 | 0.576527 | 0 |
| AFFINE_ROM32 | 6 | 32 | 32 | True | 0.871495 | 0.396001 | 0.996805 | 0.313122 | 0.595102 | 0 |
| AFFINE_ROM32 | 12 | 32 | 32 | True | 0.875988 | 0.398292 | 1.00698 | 0.304866 | 0.618642 | 0 |
| BORN_TV | 3 | 32 | 32 | True | 0.966036 | 0.425338 | 0.99335 | 0.232317 | 0.91205 | 0 |
| BORN_TV | 6 | 32 | 32 | True | 0.963621 | 0.424445 | 0.993896 | 0.256051 | 0.901933 | 0 |
| BORN_TV | 12 | 32 | 32 | True | 0.963609 | 0.424681 | 0.994627 | 0.266498 | 0.900258 | 0 |
| F | 3 | 32 | 32 | True | 0.815692 | 0.364403 | 0.983554 | 0.321119 | 0.449714 | 0 |
| F | 6 | 32 | 32 | True | 0.784086 | 0.344344 | 0.978488 | 0.353823 | 0.382794 | 0 |
| F | 12 | 32 | 32 | True | 0.757917 | 0.328058 | 0.973595 | 0.341296 | 0.32844 | 0 |
| L | 3 | 32 | 32 | True | 0.832328 | 0.376773 | 0.985863 | 0.329775 | 0.476476 | 0 |
| L | 6 | 32 | 32 | True | 0.815147 | 0.367389 | 0.983538 | 0.342781 | 0.43874 | 0 |
| L | 12 | 32 | 32 | True | 0.803725 | 0.361993 | 0.981927 | 0.333811 | 0.417489 | 0 |
| LOCAL_R16 | 3 | 32 | 32 | True | 0.816932 | 0.365301 | 0.983942 | 0.318909 | 0.450869 | 0 |
| LOCAL_R16 | 6 | 32 | 32 | True | 0.786229 | 0.345871 | 0.979277 | 0.350573 | 0.384715 | 0 |
| LOCAL_R16 | 12 | 32 | 32 | True | 0.760833 | 0.330038 | 0.974827 | 0.337411 | 0.330904 | 0 |
| R16 | 3 | 32 | 32 | True | 0.816649 | 0.365125 | 0.9838 | 0.321202 | 0.450587 | 0 |
| R16 | 6 | 32 | 32 | True | 0.785835 | 0.345624 | 0.97906 | 0.349484 | 0.384422 | 0 |
| R16 | 12 | 32 | 32 | True | 0.760412 | 0.329764 | 0.974565 | 0.336796 | 0.330835 | 0 |
| R24 | 3 | 32 | 32 | True | 0.816385 | 0.364893 | 0.9838 | 0.320655 | 0.450335 | 0 |
| R24 | 6 | 32 | 32 | True | 0.78531 | 0.345202 | 0.978991 | 0.351061 | 0.383839 | 0 |
| R24 | 12 | 32 | 32 | True | 0.759635 | 0.32922 | 0.974426 | 0.338337 | 0.329749 | 0 |
| R32 | 3 | 32 | 32 | True | 0.816068 | 0.364655 | 0.983649 | 0.320858 | 0.450083 | 0 |
| R32 | 6 | 32 | 32 | True | 0.784754 | 0.344782 | 0.978732 | 0.352803 | 0.38337 | 0 |
| R32 | 12 | 32 | 32 | True | 0.75887 | 0.328656 | 0.974068 | 0.33986 | 0.329031 | 0 |
| TASK_R32 | 3 | 32 | 32 | True | 0.815919 | 0.364561 | 0.983641 | 0.32077 | 0.449898 | 0 |
| TASK_R32 | 6 | 32 | 32 | True | 0.784513 | 0.344637 | 0.978661 | 0.353243 | 0.383149 | 0 |
| TASK_R32 | 12 | 32 | 32 | True | 0.758536 | 0.328449 | 0.973873 | 0.340625 | 0.328913 | 0 |

原始逐步记录：[METRICS.csv](results/a25/development/frozen_optimizer_repair/METRICS.csv)、[完整HISTORIES：A25_REPRODUCTION_DATA.zip](https://github.com/migodam/a25-adaptive-om-feedback/releases/download/a25-v0.1.0/A25_REPRODUCTION_DATA.zip)（压缩包内项目相对路径：`results/a25/development/frozen_optimizer_repair/HISTORIES.json`）；报告等权导出：[frozen_optimizer_repair_parent_equal.csv](results/a25/report/plot_data/frozen_optimizer_repair_parent_equal.csv)。

### 追加开发探索：TV×0.1

相同32观测；初始化与迭代共同降低TV权重，不改写原协议。

| 方法 | K | OK条件 | 应有条件 | 完整parent配对 | 增量NRMSE | 完整χ NRMSE | 边缘NRMSE | 支撑IoU | 完整场相对残差 | 质量命中数 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| AFFINE_ROM32 | 3 | 32 | 32 | True | 0.840405 | 0.393669 | 0.991805 | 0.416553 | 0.507555 | 0 |
| AFFINE_ROM32 | 6 | 32 | 32 | True | 0.831108 | 0.391526 | 1.00171 | 0.436124 | 0.494691 | 0 |
| AFFINE_ROM32 | 12 | 32 | 32 | True | 0.832631 | 0.397732 | 1.02574 | 0.446579 | 0.488177 | 0 |
| BORN_TV | 3 | 32 | 32 | True | 0.962867 | 0.424673 | 0.990846 | 0.256673 | 0.914244 | 0 |
| BORN_TV | 6 | 32 | 32 | True | 0.966821 | 0.425253 | 0.993145 | 0.299705 | 0.909899 | 0 |
| BORN_TV | 12 | 32 | 32 | True | 0.97129 | 0.426652 | 0.995374 | 0.3232 | 0.9094 | 0 |
| F | 3 | 32 | 32 | True | 0.761705 | 0.355206 | 0.97126 | 0.448762 | 0.345742 | 0 |
| F | 6 | 32 | 32 | True | 0.71344 | 0.3326 | 0.96168 | 0.540867 | 0.250725 | 0 |
| F | 12 | 32 | 32 | True | 0.670086 | 0.313911 | 0.951956 | 0.564382 | 0.168927 | 1 |
| L | 3 | 32 | 32 | True | 0.78115 | 0.368493 | 0.974212 | 0.450696 | 0.380512 | 0 |
| L | 6 | 32 | 32 | True | 0.749456 | 0.357175 | 0.967985 | 0.525052 | 0.322234 | 0 |
| L | 12 | 32 | 32 | True | 0.723377 | 0.349951 | 0.962857 | 0.561668 | 0.283176 | 0 |
| LOCAL_R16 | 3 | 32 | 32 | True | 0.763119 | 0.356157 | 0.971756 | 0.448626 | 0.34711 | 0 |
| LOCAL_R16 | 6 | 32 | 32 | True | 0.715943 | 0.334245 | 0.962703 | 0.537919 | 0.252987 | 0 |
| LOCAL_R16 | 12 | 32 | 32 | True | 0.67366 | 0.316124 | 0.953728 | 0.55629 | 0.171993 | 1 |
| R16 | 3 | 32 | 32 | True | 0.7628 | 0.355969 | 0.971566 | 0.449788 | 0.346814 | 0 |
| R16 | 6 | 32 | 32 | True | 0.715503 | 0.33397 | 0.962343 | 0.536657 | 0.252739 | 0 |
| R16 | 12 | 32 | 32 | True | 0.673152 | 0.31578 | 0.953104 | 0.558535 | 0.172114 | 1 |
| R24 | 3 | 32 | 32 | True | 0.762504 | 0.355727 | 0.971577 | 0.448543 | 0.346445 | 0 |
| R24 | 6 | 32 | 32 | True | 0.714846 | 0.333512 | 0.962305 | 0.539114 | 0.251869 | 0 |
| R24 | 12 | 32 | 32 | True | 0.672098 | 0.315156 | 0.953013 | 0.55878 | 0.17043 | 1 |
| R32 | 3 | 32 | 32 | True | 0.762202 | 0.35549 | 0.971427 | 0.448367 | 0.346201 | 0 |
| R32 | 6 | 32 | 32 | True | 0.714327 | 0.333099 | 0.962054 | 0.538949 | 0.251419 | 0 |
| R32 | 12 | 32 | 32 | True | 0.67138 | 0.314611 | 0.952652 | 0.560595 | 0.169686 | 1 |
| TASK_R32 | 3 | 32 | 32 | True | 0.762018 | 0.355389 | 0.971407 | 0.448427 | 0.345981 | 0 |
| TASK_R32 | 6 | 32 | 32 | True | 0.71404 | 0.332943 | 0.96198 | 0.539142 | 0.251155 | 0 |
| TASK_R32 | 12 | 32 | 32 | True | 0.670983 | 0.314384 | 0.952457 | 0.562018 | 0.16949 | 1 |

原始逐步记录：[METRICS.csv](results/a25/development/tv_multiplier_0p1/METRICS.csv)、[完整HISTORIES：A25_REPRODUCTION_DATA.zip](https://github.com/migodam/a25-adaptive-om-feedback/releases/download/a25-v0.1.0/A25_REPRODUCTION_DATA.zip)（压缩包内项目相对路径：`results/a25/development/tv_multiplier_0p1/HISTORIES.json`）；报告等权导出：[tv_multiplier_0p1_parent_equal.csv](results/a25/report/plot_data/tv_multiplier_0p1_parent_equal.csv)。

### 追加开发探索：振幅1.8

原TV权重；16条件、8个新增clean labels；仍是历史四parent。

| 方法 | K | OK条件 | 应有条件 | 完整parent配对 | 增量NRMSE | 完整χ NRMSE | 边缘NRMSE | 支撑IoU | 完整场相对残差 | 质量命中数 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| F | 3 | 16 | 16 | True | 0.833663 | 0.564424 | 0.985378 | 0.320061 | 0.46195 | 0 |
| F | 6 | 16 | 16 | True | 0.784475 | 0.529032 | 0.977541 | 0.445479 | 0.378338 | 0 |
| F | 12 | 16 | 16 | True | 0.728679 | 0.489046 | 0.967044 | 0.532825 | 0.287485 | 0 |
| L | 3 | 16 | 16 | True | 0.87109 | 0.594307 | 0.989949 | 0.322588 | 0.507821 | 0 |
| L | 6 | 16 | 16 | True | 0.856925 | 0.586518 | 0.989261 | 0.407428 | 0.477907 | 0 |
| L | 12 | 16 | 16 | True | 0.846886 | 0.582154 | 0.990582 | 0.400662 | 0.45779 | 0 |
| TASK_R32 | 3 | 16 | 16 | True | 0.834089 | 0.56474 | 0.985533 | 0.313421 | 0.462196 | 0 |
| TASK_R32 | 6 | 16 | 16 | True | 0.785492 | 0.529777 | 0.977951 | 0.445147 | 0.379057 | 0 |
| TASK_R32 | 12 | 16 | 16 | True | 0.730703 | 0.490478 | 0.967986 | 0.527131 | 0.289034 | 0 |

原始逐步记录：[METRICS.csv](results/a25/development/amplitude_1p8/METRICS.csv)、[完整HISTORIES：A25_REPRODUCTION_DATA.zip](https://github.com/migodam/a25-adaptive-om-feedback/releases/download/a25-v0.1.0/A25_REPRODUCTION_DATA.zip)（压缩包内项目相对路径：`results/a25/development/amplitude_1p8/HISTORIES.json`）；报告等权导出：[amplitude_1p8_parent_equal.csv](results/a25/report/plot_data/amplitude_1p8_parent_equal.csv)。

三组记录采用不同的实验范围：TV×0.1同时改变所有方法的初始化与TV惩罚，振幅1.8保持原TV权重。追加探索不能替代冻结32条件的成像余量结果，也不修改神经网络原TV×1训练协议。

| 实验 | K | 独立cluster数 | 先算各parent改善再平均 | 已保存95% bootstrap区间 | 原始范围 |
| --- | --- | --- | --- | --- | --- |
| frozen_optimizer_repair | 12 | 4 | 0.0581456 | [0.03379912836964016, 0.08678879364513253] | descriptive four exposed development parents; no formal holdout claim |
| tv_multiplier_0p1 | 12 | 4 | 0.0762556 | [0.0414069924058032, 0.11110421494317446] | descriptive four exposed development parents; no formal holdout claim |
| amplitude_1p8 | 12 | 4 | 0.139575 | [0.09724783762924646, 0.18163889342941575] | descriptive four exposed development parents; no formal holdout claim |

bootstrap只重采样四个已暴露parent cluster，区间是该开发集合的描述；不是独立holdout置信保证。聚合均值的相对改善和先算各parent相对改善再平均是不同统计量，分别保留。[原始parent bootstrap](results/a25/development/PAIRED_PARENT_BOOTSTRAP.json)。

成像裁决来自父线程：{"aggregate_relative_gain": 0.056994635108287506, "independent_validation": "COMPLETE_PROSPECTIVE_NO_NN_REGIME_CHECK; validation/development, not locked NN test", "original_K12_equal_parent_F_delta_nrmse": 0.7579170985655044, "original_K12_equal_parent_L_delta_nrmse": 0.8037251184170493, "prospective_regime": {"F_vs_L_parent_mean_relative_gain": 0.10517039318291257, "K": 12, "NN": "NOT_RUN", "amplitude": 1.2, "background": "weak", "ci95": [0.06594354225582005, 0.1531568670883614], "compression": {"max_adjoint_error": 0.01681988547545252, "max_material_error_ratio_to_F": 1.0138212782922529, "max_state_data_error": 0.005546922815827388, "max_transfer_error": 0.017822203763375438, "min_gradient_cosine": 0.9756874777116267, "scope": "32 weak-background amplitude1.2 K12 estimates; not intermediate or neural/OOD states", "status": "FAIL_FIXED_K12_ENDPOINTS"}, "estimands_distinguished": "primary mean of paired parent-relative gains; secondary ratio of mean errors", "family_parent_mean_relative_gains": {"asymmetric_piecewise": 0.03887713264553941, "mixed_scale": 0.08290945726778401, "shell": 0.06730832178347762, "smooth": 0.23158666103484926}, "joint_quality_hits_out_of_32": {"F": 0, "L": 0, "TASK_R32": 0}, "locked_ID_OOD": "CLOSED", "minimum_10_percent_improvement_confirmed": false, "new_clean_labels": 0, "paired_parents": 16, "parent_equal_delta_nrmse": {"F": 0.6808303573685768, "L": 0.7516184108592043, "TASK_R32": 0.6820771392205673}, "point_target_status": "PASS", "positive_improvement_supported": true, "ratio_of_parent_equal_mean_gain": 0.09418084026135942, "role": "previously unused validation parents, prospective no-NN regime check; NOT locked validation", "source": "development/prospective_regime_validation/SUMMARY.json", "speed_advantage": "NOT_ESTABLISHED; descriptive per-image times are not matched cold/warm evidence", "status": "POSITIVE_NARROW_REGIME_PARTIAL_THRESHOLD_CONFIRMATION", "tv_multiplier": 0.1, "validation_now_exposed": true}, "regime_confirmation": "POSITIVE_IMPROVEMENT; mean10percent point target met; CI does not establish minimum10percent", "status": "PARTIAL", "threshold": 0.1, "weak_background_amplitude1p2_parent_mean_gain": 0.1588612407424314}。

原始来源：[METRICS.csv](results/a25/development/frozen_optimizer_repair/METRICS.csv)；图像是固定开发样例，不能当作新的ID/OOD泛化。

## 收敛、相同K与完整推理时间

一个更准的单次反馈动作不保证更快得到合格材料。比较先固定K，再观察达到共同质量目标所需的完整时间。online_s包含共同初始化和在线迭代；独立冷成本再加入一次已知背景准备与方法准备。离线完整场质量审核另列，不混入普通部署推理。共享试验真正只付一次的准备成本与单方法独立成本同时报告。

### 冻结协议：认证求解器重放

原TV权重、原32条件；仅修复同目标求解器。

| 方法 | K | OK条件 | 应有条件 | 完整parent配对 | 增量NRMSE | 共享准备秒 | 方法准备秒 | 初始化+online秒 | 单方法独立冷成本秒 | 质量命中数 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| AFFINE_ROM32 | 3 | 32 | 32 | True | 0.873807 | 0.017399 | 0.00590473 | 0.910359 | 0.933663 | 0 |
| AFFINE_ROM32 | 6 | 32 | 32 | True | 0.871495 | 0.017399 | 0.00590473 | 1.17736 | 1.20066 | 0 |
| AFFINE_ROM32 | 12 | 32 | 32 | True | 0.875988 | 0.017399 | 0.00590473 | 1.43109 | 1.45439 | 0 |
| BORN_TV | 3 | 32 | 32 | True | 0.966036 | 0.017399 | 8.0229e-05 | 1.17225 | 1.18973 | 0 |
| BORN_TV | 6 | 32 | 32 | True | 0.963621 | 0.017399 | 8.0229e-05 | 1.33182 | 1.3493 | 0 |
| BORN_TV | 12 | 32 | 32 | True | 0.963609 | 0.017399 | 8.0229e-05 | 1.5342 | 1.55168 | 0 |
| F | 3 | 32 | 32 | True | 0.815692 | 0.017399 | 5.82495e-05 | 0.73256 | 0.750017 | 0 |
| F | 6 | 32 | 32 | True | 0.784086 | 0.017399 | 5.82495e-05 | 0.981828 | 0.999285 | 0 |
| F | 12 | 32 | 32 | True | 0.757917 | 0.017399 | 5.82495e-05 | 1.40949 | 1.42695 | 0 |
| L | 3 | 32 | 32 | True | 0.832328 | 0.017399 | 0.000221855 | 0.682819 | 0.70044 | 0 |
| L | 6 | 32 | 32 | True | 0.815147 | 0.017399 | 0.000221855 | 0.914057 | 0.931678 | 0 |
| L | 12 | 32 | 32 | True | 0.803725 | 0.017399 | 0.000221855 | 1.22114 | 1.23876 | 0 |
| LOCAL_R16 | 3 | 32 | 32 | True | 0.816932 | 0.017399 | 0.0567004 | 1.08555 | 1.15965 | 0 |
| LOCAL_R16 | 6 | 32 | 32 | True | 0.786229 | 0.017399 | 0.0567004 | 1.63892 | 1.71302 | 0 |
| LOCAL_R16 | 12 | 32 | 32 | True | 0.760833 | 0.017399 | 0.0567004 | 2.67284 | 2.74694 | 0 |
| R16 | 3 | 32 | 32 | True | 0.816649 | 0.017399 | 0.00410002 | 0.715501 | 0.737 | 0 |
| R16 | 6 | 32 | 32 | True | 0.785835 | 0.017399 | 0.00410002 | 0.944621 | 0.96612 | 0 |
| R16 | 12 | 32 | 32 | True | 0.760412 | 0.017399 | 0.00410002 | 1.30937 | 1.33087 | 0 |
| R24 | 3 | 32 | 32 | True | 0.816385 | 0.017399 | 0.00483942 | 0.71475 | 0.736988 | 0 |
| R24 | 6 | 32 | 32 | True | 0.78531 | 0.017399 | 0.00483942 | 0.940187 | 0.962425 | 0 |
| R24 | 12 | 32 | 32 | True | 0.759635 | 0.017399 | 0.00483942 | 1.26474 | 1.28698 | 0 |
| R32 | 3 | 32 | 32 | True | 0.816068 | 0.017399 | 0.00589781 | 0.713033 | 0.736329 | 0 |
| R32 | 6 | 32 | 32 | True | 0.784754 | 0.017399 | 0.00589781 | 0.943379 | 0.966676 | 0 |
| R32 | 12 | 32 | 32 | True | 0.75887 | 0.017399 | 0.00589781 | 1.30795 | 1.33124 | 0 |
| TASK_R32 | 3 | 32 | 32 | True | 0.815919 | 0.017399 | 0.019665 | 0.7139 | 0.750964 | 0 |
| TASK_R32 | 6 | 32 | 32 | True | 0.784513 | 0.017399 | 0.019665 | 0.941671 | 0.978735 | 0 |
| TASK_R32 | 12 | 32 | 32 | True | 0.758536 | 0.017399 | 0.019665 | 1.31092 | 1.34799 | 0 |

原始逐步记录：[METRICS.csv](results/a25/development/frozen_optimizer_repair/METRICS.csv)、[完整HISTORIES：A25_REPRODUCTION_DATA.zip](https://github.com/migodam/a25-adaptive-om-feedback/releases/download/a25-v0.1.0/A25_REPRODUCTION_DATA.zip)（压缩包内项目相对路径：`results/a25/development/frozen_optimizer_repair/HISTORIES.json`）；报告等权导出：[frozen_optimizer_repair_parent_equal.csv](results/a25/report/plot_data/frozen_optimizer_repair_parent_equal.csv)。

### 追加开发探索：TV×0.1

相同32观测；初始化与迭代共同降低TV权重，不改写原协议。

| 方法 | K | OK条件 | 应有条件 | 完整parent配对 | 增量NRMSE | 共享准备秒 | 方法准备秒 | 初始化+online秒 | 单方法独立冷成本秒 | 质量命中数 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| AFFINE_ROM32 | 3 | 32 | 32 | True | 0.840405 | 0.0223016 | 0.00643775 | 0.108299 | 0.137039 | 0 |
| AFFINE_ROM32 | 6 | 32 | 32 | True | 0.831108 | 0.0223016 | 0.00643775 | 0.154729 | 0.183468 | 0 |
| AFFINE_ROM32 | 12 | 32 | 32 | True | 0.832631 | 0.0223016 | 0.00643775 | 0.230003 | 0.258742 | 0 |
| BORN_TV | 3 | 32 | 32 | True | 0.962867 | 0.0223016 | 8.35e-05 | 0.0733144 | 0.0956995 | 0 |
| BORN_TV | 6 | 32 | 32 | True | 0.966821 | 0.0223016 | 8.35e-05 | 0.111201 | 0.133586 | 0 |
| BORN_TV | 12 | 32 | 32 | True | 0.97129 | 0.0223016 | 8.35e-05 | 0.169006 | 0.191391 | 0 |
| F | 3 | 32 | 32 | True | 0.761705 | 0.0223016 | 7.5e-05 | 0.124396 | 0.146773 | 0 |
| F | 6 | 32 | 32 | True | 0.71344 | 0.0223016 | 7.5e-05 | 0.191705 | 0.214082 | 0 |
| F | 12 | 32 | 32 | True | 0.670086 | 0.0223016 | 7.5e-05 | 0.314468 | 0.336844 | 1 |
| L | 3 | 32 | 32 | True | 0.78115 | 0.0223016 | 0.000321167 | 0.0894127 | 0.112035 | 0 |
| L | 6 | 32 | 32 | True | 0.749456 | 0.0223016 | 0.000321167 | 0.136873 | 0.159495 | 0 |
| L | 12 | 32 | 32 | True | 0.723377 | 0.0223016 | 0.000321167 | 0.217448 | 0.240071 | 0 |
| LOCAL_R16 | 3 | 32 | 32 | True | 0.763119 | 0.0223016 | 0.0604254 | 0.499199 | 0.581926 | 0 |
| LOCAL_R16 | 6 | 32 | 32 | True | 0.715943 | 0.0223016 | 0.0604254 | 0.871875 | 0.954602 | 0 |
| LOCAL_R16 | 12 | 32 | 32 | True | 0.67366 | 0.0223016 | 0.0604254 | 1.62477 | 1.7075 | 1 |
| R16 | 3 | 32 | 32 | True | 0.7628 | 0.0223016 | 0.00552108 | 0.0997944 | 0.127617 | 0 |
| R16 | 6 | 32 | 32 | True | 0.715503 | 0.0223016 | 0.00552108 | 0.148384 | 0.176206 | 0 |
| R16 | 12 | 32 | 32 | True | 0.673152 | 0.0223016 | 0.00552108 | 0.238782 | 0.266605 | 1 |
| R24 | 3 | 32 | 32 | True | 0.762504 | 0.0223016 | 0.00616519 | 0.102687 | 0.131154 | 0 |
| R24 | 6 | 32 | 32 | True | 0.714846 | 0.0223016 | 0.00616519 | 0.150713 | 0.17918 | 0 |
| R24 | 12 | 32 | 32 | True | 0.672098 | 0.0223016 | 0.00616519 | 0.239334 | 0.267801 | 1 |
| R32 | 3 | 32 | 32 | True | 0.762202 | 0.0223016 | 0.0072506 | 0.103292 | 0.132844 | 0 |
| R32 | 6 | 32 | 32 | True | 0.714327 | 0.0223016 | 0.0072506 | 0.150947 | 0.1805 | 0 |
| R32 | 12 | 32 | 32 | True | 0.67138 | 0.0223016 | 0.0072506 | 0.237371 | 0.266923 | 1 |
| TASK_R32 | 3 | 32 | 32 | True | 0.762018 | 0.0223016 | 0.023046 | 0.0974215 | 0.142769 | 0 |
| TASK_R32 | 6 | 32 | 32 | True | 0.71404 | 0.0223016 | 0.023046 | 0.146283 | 0.191631 | 0 |
| TASK_R32 | 12 | 32 | 32 | True | 0.670983 | 0.0223016 | 0.023046 | 0.22932 | 0.274667 | 1 |

原始逐步记录：[METRICS.csv](results/a25/development/tv_multiplier_0p1/METRICS.csv)、[完整HISTORIES：A25_REPRODUCTION_DATA.zip](https://github.com/migodam/a25-adaptive-om-feedback/releases/download/a25-v0.1.0/A25_REPRODUCTION_DATA.zip)（压缩包内项目相对路径：`results/a25/development/tv_multiplier_0p1/HISTORIES.json`）；报告等权导出：[tv_multiplier_0p1_parent_equal.csv](results/a25/report/plot_data/tv_multiplier_0p1_parent_equal.csv)。

### 追加开发探索：振幅1.8

原TV权重；16条件、8个新增clean labels；仍是历史四parent。

| 方法 | K | OK条件 | 应有条件 | 完整parent配对 | 增量NRMSE | 共享准备秒 | 方法准备秒 | 初始化+online秒 | 单方法独立冷成本秒 | 质量命中数 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| F | 3 | 16 | 16 | True | 0.833663 | 0.01745 | 5.95e-05 | 0.957478 | 0.974987 | 0 |
| F | 6 | 16 | 16 | True | 0.784475 | 0.01745 | 5.95e-05 | 1.23317 | 1.25068 | 0 |
| F | 12 | 16 | 16 | True | 0.728679 | 0.01745 | 5.95e-05 | 1.93063 | 1.94814 | 0 |
| L | 3 | 16 | 16 | True | 0.87109 | 0.01745 | 0.000123083 | 0.809464 | 0.827037 | 0 |
| L | 6 | 16 | 16 | True | 0.856925 | 0.01745 | 0.000123083 | 1.09535 | 1.11292 | 0 |
| L | 12 | 16 | 16 | True | 0.846886 | 0.01745 | 0.000123083 | 1.69451 | 1.71208 | 0 |
| TASK_R32 | 3 | 16 | 16 | True | 0.834089 | 0.01745 | 0.0186199 | 0.91202 | 0.94809 | 0 |
| TASK_R32 | 6 | 16 | 16 | True | 0.785492 | 0.01745 | 0.0186199 | 1.17837 | 1.21444 | 0 |
| TASK_R32 | 12 | 16 | 16 | True | 0.730703 | 0.01745 | 0.0186199 | 1.83754 | 1.87361 | 0 |

原始逐步记录：[METRICS.csv](results/a25/development/amplitude_1p8/METRICS.csv)、[完整HISTORIES：A25_REPRODUCTION_DATA.zip](https://github.com/migodam/a25-adaptive-om-feedback/releases/download/a25-v0.1.0/A25_REPRODUCTION_DATA.zip)（压缩包内项目相对路径：`results/a25/development/amplitude_1p8/HISTORIES.json`）；报告等权导出：[amplitude_1p8_parent_equal.csv](results/a25/report/plot_data/amplitude_1p8_parent_equal.csv)。
没有共同命中质量区域时，质量—时间散点只作描述。图中的非劣线只连接同一实验、同一K的已观察完整配对点，不是所有算法的最优速度边界。GPU缓存训练初始化不能作为部署已经免除初始化；完整cold/warm计时要实际加载缓存、重置状态、重算或单列初始化时间。

NOT_RUN：没有对应的已保存原始记录。

部署裁决：{"original_conditions": 32, "original_quality_hits": 0, "prospective_joint_quality_hits": {"F": 0, "L": 0, "TASK_R32": 0}, "reason": "no complete paired common-quality regime; no trained-network endpoint latency", "status": "NOT_ESTABLISHED", "tv0p1_F_quality_hits": 1, "tv0p1_conditions": 32}。

已知背景准备成本：

| 实验 | 背景 | 方法 | 共享准备秒 | 方法准备秒 | 原始状态 |
| --- | --- | --- | --- | --- | --- |
| frozen_optimizer_repair | weak | L | 0.0183282 | 0.000338834 | RECORDED |
| frozen_optimizer_repair | weak | F | 0.0183282 | 6.2791e-05 | RECORDED |
| frozen_optimizer_repair | weak | R16 | 0.0183282 | 0.00447642 | RECORDED |
| frozen_optimizer_repair | weak | R24 | 0.0183282 | 0.00500742 | RECORDED |
| frozen_optimizer_repair | weak | R32 | 0.0183282 | 0.00611404 | RECORDED |
| frozen_optimizer_repair | weak | LOCAL_R16 | 0.0183282 | 0.0552577 | RECORDED |
| frozen_optimizer_repair | weak | TASK_R32 | 0.0183282 | 0.0333231 | RECORDED |
| frozen_optimizer_repair | weak | AFFINE_ROM32 | 0.0183282 | 0.00589875 | RECORDED |
| frozen_optimizer_repair | weak | BORN_TV | 0.0183282 | 7.4916e-05 | RECORDED |
| frozen_optimizer_repair | ring | L | 0.0164698 | 0.000104875 | RECORDED |
| frozen_optimizer_repair | ring | F | 0.0164698 | 5.3708e-05 | RECORDED |
| frozen_optimizer_repair | ring | R16 | 0.0164698 | 0.00372363 | RECORDED |
| frozen_optimizer_repair | ring | R24 | 0.0164698 | 0.00467142 | RECORDED |
| frozen_optimizer_repair | ring | R32 | 0.0164698 | 0.00568158 | RECORDED |
| frozen_optimizer_repair | ring | LOCAL_R16 | 0.0164698 | 0.058143 | RECORDED |
| frozen_optimizer_repair | ring | TASK_R32 | 0.0164698 | 0.00600692 | RECORDED |
| frozen_optimizer_repair | ring | AFFINE_ROM32 | 0.0164698 | 0.00591071 | RECORDED |
| frozen_optimizer_repair | ring | BORN_TV | 0.0164698 | 8.5542e-05 | RECORDED |
| tv_multiplier_0p1 | weak | L | 0.0255124 | 0.00050675 | RECORDED |
| tv_multiplier_0p1 | weak | F | 0.0255124 | 8.2333e-05 | RECORDED |
| tv_multiplier_0p1 | weak | R16 | 0.0255124 | 0.00671954 | RECORDED |
| tv_multiplier_0p1 | weak | R24 | 0.0255124 | 0.00718562 | RECORDED |
| tv_multiplier_0p1 | weak | R32 | 0.0255124 | 0.00788058 | RECORDED |
| tv_multiplier_0p1 | weak | LOCAL_R16 | 0.0255124 | 0.0598274 | RECORDED |
| tv_multiplier_0p1 | weak | TASK_R32 | 0.0255124 | 0.0399127 | RECORDED |
| tv_multiplier_0p1 | weak | AFFINE_ROM32 | 0.0255124 | 0.00649142 | RECORDED |
| tv_multiplier_0p1 | weak | BORN_TV | 0.0255124 | 8.2292e-05 | RECORDED |
| tv_multiplier_0p1 | ring | L | 0.0190908 | 0.000135583 | RECORDED |
| tv_multiplier_0p1 | ring | F | 0.0190908 | 6.7667e-05 | RECORDED |
| tv_multiplier_0p1 | ring | R16 | 0.0190908 | 0.00432262 | RECORDED |
| tv_multiplier_0p1 | ring | R24 | 0.0190908 | 0.00514475 | RECORDED |
| tv_multiplier_0p1 | ring | R32 | 0.0190908 | 0.00662062 | RECORDED |
| tv_multiplier_0p1 | ring | LOCAL_R16 | 0.0190908 | 0.0610234 | RECORDED |
| tv_multiplier_0p1 | ring | TASK_R32 | 0.0190908 | 0.00617925 | RECORDED |
| tv_multiplier_0p1 | ring | AFFINE_ROM32 | 0.0190908 | 0.00638408 | RECORDED |
| tv_multiplier_0p1 | ring | BORN_TV | 0.0190908 | 8.4708e-05 | RECORDED |
| amplitude_1p8 | weak | L | 0.0170473 | 0.000127334 | RECORDED |
| amplitude_1p8 | weak | F | 0.0170473 | 6.1375e-05 | RECORDED |
| amplitude_1p8 | weak | TASK_R32 | 0.0170473 | 0.0305479 | RECORDED |
| amplitude_1p8 | ring | L | 0.0178527 | 0.000118833 | RECORDED |
| amplitude_1p8 | ring | F | 0.0178527 | 5.7625e-05 | RECORDED |
| amplitude_1p8 | ring | TASK_R32 | 0.0178527 | 0.00669187 | RECORDED |

准备、online、offline audit的原始phase动作墙钟见[phase_costs.csv](results/a25/report/plot_data/phase_costs.csv)。phase未由上游单列的动作保持原标签；这些exclusive诊断时间不再次加到inclusive CPU/GPU资源费用。

轨迹接受与重试统计来自原始HISTORIES，不从图像改善倒推优化成功：

| 实验 | 方法 | 保存轨迹 | 应有轨迹 | 保存更新 | 接受更新 | 未接受更新 | 发生重试 | 完整12步记录 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| frozen_optimizer_repair | AFFINE_ROM32 | 32 | 32 | 384 | 384 | 0 | 0 | True |
| frozen_optimizer_repair | BORN_TV | 32 | 32 | 384 | 377 | 7 | 7 | True |
| frozen_optimizer_repair | F | 32 | 32 | 384 | 347 | 37 | 37 | True |
| frozen_optimizer_repair | L | 32 | 32 | 384 | 352 | 32 | 34 | True |
| frozen_optimizer_repair | LOCAL_R16 | 32 | 32 | 384 | 349 | 35 | 35 | True |
| frozen_optimizer_repair | R16 | 32 | 32 | 384 | 349 | 35 | 35 | True |
| frozen_optimizer_repair | R24 | 32 | 32 | 384 | 361 | 23 | 24 | True |
| frozen_optimizer_repair | R32 | 32 | 32 | 384 | 353 | 31 | 32 | True |
| frozen_optimizer_repair | TASK_R32 | 32 | 32 | 384 | 348 | 36 | 36 | True |
| tv_multiplier_0p1 | AFFINE_ROM32 | 32 | 32 | 384 | 384 | 0 | 0 | True |
| tv_multiplier_0p1 | BORN_TV | 32 | 32 | 384 | 384 | 0 | 0 | True |
| tv_multiplier_0p1 | F | 32 | 32 | 384 | 384 | 0 | 0 | True |
| tv_multiplier_0p1 | L | 32 | 32 | 384 | 384 | 0 | 0 | True |
| tv_multiplier_0p1 | LOCAL_R16 | 32 | 32 | 384 | 384 | 0 | 0 | True |
| tv_multiplier_0p1 | R16 | 32 | 32 | 384 | 384 | 0 | 0 | True |
| tv_multiplier_0p1 | R24 | 32 | 32 | 384 | 384 | 0 | 0 | True |
| tv_multiplier_0p1 | R32 | 32 | 32 | 384 | 384 | 0 | 0 | True |
| tv_multiplier_0p1 | TASK_R32 | 32 | 32 | 384 | 384 | 0 | 0 | True |
| amplitude_1p8 | F | 16 | 16 | 192 | 192 | 0 | 0 | True |
| amplitude_1p8 | L | 16 | 16 | 192 | 192 | 0 | 0 | True |
| amplitude_1p8 | TASK_R32 | 16 | 16 | 192 | 192 | 0 | 0 | True |


## 压缩反馈准入与固定候选

压缩的目的在于保留材料扰动到观测的合法传递。单看G_b的谱误差不足以知道图像会否丢失重要方向，需要独立forward、精确adjoint任务探针、梯度方向与同先验成像配对。R16/R24/R32、local和task-weighted是不同候选。

| 候选 | 完整配对 | forward任务误差 | adjoint任务误差 | 梯度cosine | 最大成像比值/F | 开发域准入 |
| --- | --- | --- | --- | --- | --- | --- |
| R16 | True | 0.0774547 | 0.073581 | 0.886872 | 1.02011 | False |
| R24 | True | 0.0543111 | 0.0516117 | 0.954986 | 1.01487 | False |
| R32 | True | 0.0361694 | 0.0347274 | 0.983019 | 1.0066 | False |
| LOCAL_R16 | True | 0.0769862 | 0.0742762 | 0.903447 | 1.02316 | False |
| TASK_R32 | True | 0.0236488 | 0.0222806 | 0.992255 | 1.00487 | True |

开发准入原始状态：ADMITTED_PENDING_TORCH_HEALTH；选择：TASK_R32。

覆盖纠正：原协议TASK_AUDIT只检查32个历史开发case的K12终点，并未覆盖所有中间轨迹状态。TV×0.1检查其32个K12终点；振幅1.8检查16个K12终点。原始准入artifact中较宽的历史scope文字保留，实际builder状态、learned状态与OOD状态覆盖均为NOT_ESTABLISHED。

开发域通过仍需Torch健康检查与独立新场景验证；只有父线程裁决决定进入学习的候选范围。探针构造使用已知背景，未知truth不进入因子构建；失败不因rank增加而抹去。

原始来源：[TASK_AUDIT.csv](results/a25/development/frozen_optimizer_repair/TASK_AUDIT.csv)、[NN_CLOSURE_ADMISSION.json](results/a25/development/frozen_optimizer_repair/NN_CLOSURE_ADMISSION.json)。

### 冻结协议：认证求解器重放的K12任务检查

| 候选 | 实际rank | OK终点 | 应有终点 | 完整配对 | 最大forward误差 | 最大adjoint误差 | 最小梯度cosine | 最大state-data误差 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| AFFINE_ROM32 | [32] | 32 | 32 | True | 0.793236 | 0.810561 | -0.223849 | 0.311445 |
| LOCAL_R16 | [16] | 32 | 32 | True | 0.0769862 | 0.0742762 | 0.903447 | 0.0224345 |
| R16 | [16] | 32 | 32 | True | 0.0774547 | 0.073581 | 0.886872 | 0.0247686 |
| R24 | [24] | 32 | 32 | True | 0.0543111 | 0.0516117 | 0.954986 | 0.0180739 |
| R32 | [32] | 32 | 32 | True | 0.0361694 | 0.0347274 | 0.983019 | 0.00900039 |
| TASK_R32 | [32] | 32 | 32 | True | 0.0236488 | 0.0222806 | 0.992255 | 0.00655778 |
追加探索的任务表描述本组终点，不重新选择NN closure或拓宽准入范围。

### 追加开发探索：TV×0.1的K12任务检查

| 候选 | 实际rank | OK终点 | 应有终点 | 完整配对 | 最大forward误差 | 最大adjoint误差 | 最小梯度cosine | 最大state-data误差 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| AFFINE_ROM32 | [32] | 32 | 32 | True | 0.780988 | 0.80121 | -0.196654 | 0.302981 |
| LOCAL_R16 | [16] | 32 | 32 | True | 0.0793069 | 0.0798303 | 0.888095 | 0.0225975 |
| R16 | [16] | 32 | 32 | True | 0.0786803 | 0.0748809 | 0.867737 | 0.0252138 |
| R24 | [24] | 32 | 32 | True | 0.0549428 | 0.0523096 | 0.950322 | 0.0184363 |
| R32 | [32] | 32 | 32 | True | 0.0368514 | 0.0378931 | 0.979621 | 0.00912003 |
| TASK_R32 | [32] | 32 | 32 | True | 0.0239827 | 0.0226562 | 0.990073 | 0.00670451 |
追加探索的任务表描述本组终点，不重新选择NN closure或拓宽准入范围。

### 追加开发探索：振幅1.8的K12任务检查

| 候选 | 实际rank | OK终点 | 应有终点 | 完整配对 | 最大forward误差 | 最大adjoint误差 | 最小梯度cosine | 最大state-data误差 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| TASK_R32 | [32] | 16 | 16 | True | 0.0332154 | 0.0301265 | 0.991506 | 0.00777198 |
追加探索的任务表描述本组终点，不重新选择NN closure或拓宽准入范围。

## 新validation范围：梯度方向门槛失败

| 父线程范围裁决 | 最大forward transfer误差 | 最大adjoint误差 | 最小梯度cosine；门槛0.99 | 最大材料误差比TASK_R32/F | 实际覆盖 |
| --- | --- | --- | --- | --- | --- |
| FAIL_FIXED_K12_ENDPOINTS | 0.0178222 | 0.0168199 | 0.975687 | 1.01382 | 32 weak-background amplitude1.2 K12 estimates; not intermediate or neural/OOD states |

新范围的TASK_R32压缩gate失败：尽管forward transfer、adjoint与成像比值接近F，最小gradient cosine低于冻结0.99门槛。历史32个K12终点的通过记录仍保留，不能将它外推为本次validation范围通过，更不能外推到中间、learned或OOD状态。
这次只增加弱背景、振幅1.2、TV×0.1的32个K12终点检查；旧历史范围的原始准入artifact保持原样。完整parent、family与图像记录见[前瞻regime补充](FEEDBACK_REGIME_MAP.md)。

## 反馈适用范围与证据域

反馈强弱取决于已知背景、材料增量及观测方向的组合。以弱背景/ring背景、0.3/1.2对比度和clean/20dB组织开发记录，可以定位已观察到的适用范围；这张地图不外推到不同频率、网格、源顺序或三维模型。

较大材料变化、背景重塑的参考场与TV平滑的影响，需要分别观察。以下每行先在同一parent内平均clean/20dB两条件，再对四个parent等权；F相对L的改善也先按parent计算，不以背景主导的完整χ误差替代增量误差。

| 实验 | TV倍数 | 背景 | 振幅 | 四parent配对 | L增量NRMSE | F增量NRMSE | TASK_R32增量NRMSE | F相对L改善，0.1=10% | 四parent各自改善 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| frozen_optimizer_repair | 1 | weak | 0.3 | True | 0.683618 | 0.663891 | 0.663998 | 0.0320615 | [0.010581214987929417, 0.014411946575092104, 0.0790551756935403, 0.024197854663235832] |
| frozen_optimizer_repair | 1 | weak | 1.2 | True | 0.796524 | 0.671217 | 0.67247 | 0.158861 | [0.08835500932878551, 0.10742442343933288, 0.28353504635826515, 0.1561304838433422] |
| frozen_optimizer_repair | 1 | ring | 0.3 | True | 0.926322 | 0.925913 | 0.925901 | 0.000447223 | [0.0001638227423944729, 0.0011425296258322029, -0.00031079179977244064, 0.0007933328689934078] |
| frozen_optimizer_repair | 1 | ring | 1.2 | True | 0.808437 | 0.770648 | 0.771775 | 0.0472468 | [0.007554614329556348, 0.04816975567161301, 0.05758748299281496, 0.07567531267667857] |
| tv_multiplier_0p1 | 0.1 | weak | 0.3 | True | 0.68595 | 0.666908 | 0.667074 | 0.0306446 | [0.010702995168885733, 0.013725281563380206, 0.07464292140511133, 0.023507068643839345] |
| tv_multiplier_0p1 | 0.1 | weak | 1.2 | True | 0.796919 | 0.670423 | 0.67175 | 0.160267 | [0.08802348696454844, 0.1107999251260057, 0.28353012108359105, 0.1587157195854566] |
| tv_multiplier_0p1 | 0.1 | ring | 0.3 | True | 0.684575 | 0.675989 | 0.676368 | 0.0128926 | [0.0017452528525166724, 0.010766202646215441, 0.010324720205639303, 0.02873403204325314] |
| tv_multiplier_0p1 | 0.1 | ring | 1.2 | True | 0.726065 | 0.667025 | 0.668739 | 0.0831618 | [0.027499402404042098, 0.058654607621212405, 0.1079577883503323, 0.13853555405323706] |
| amplitude_1p8 | 1 | weak | 1.8 | True | 0.866384 | 0.698643 | 0.70085 | 0.192892 | [0.12050280210933415, 0.16224896027938687, 0.2816921186376188, 0.20712244769513188] |
| amplitude_1p8 | 1 | ring | 1.8 | True | 0.827389 | 0.758715 | 0.760556 | 0.0831723 | [0.030025858875554305, 0.07556885461271629, 0.11169412165572794, 0.11540035531642368] |


已保存的冻结假设：At K12 with shared TV multiplier0.1, weak background and amplitude1.2 show >=10% mean delta-material benefit of F over L; require independent matched no-NN validation.。

冻结范围：four historically exposed development parents only；限制：Not independent confirmation; noisy/background effects and fixed passive complex phase remain part of the scope.。这个regime来自已暴露开发对象，只构成需要独立匹配无NN实验检验的假设；不能先写成已验证泛化收益。

来源：[REGIME_HYPOTHESIS_FREEZE.json](results/a25/development/REGIME_HYPOTHESIS_FREEZE.json)、[原始TV配对汇总](results/a25/development/PAIRED_TV_AND_REGIME.json)。

父线程压缩范围：{"deployment_acceleration": "NOT_ESTABLISHED", "historical_development_status": "PASS_DECLARED_DEVELOPMENT_SCOPE", "learned_state_or_OOD_accuracy": "NOT_ESTABLISHED", "prospective_fixed_endpoint_check": {"max_adjoint_error": 0.01681988547545252, "max_material_error_ratio_to_F": 1.0138212782922529, "max_state_data_error": 0.005546922815827388, "max_transfer_error": 0.017822203763375438, "min_gradient_cosine": 0.9756874777116267, "scope": "32 weak-background amplitude1.2 K12 estimates; not intermediate or neural/OOD states", "status": "FAIL_FIXED_K12_ENDPOINTS"}, "scope_correction": "task audits cover 32 historically exposed K12 endpoints only, not all intermediate trajectory states", "selected": "TASK_R32", "source": "development/frozen_optimizer_repair/NN_CLOSURE_ADMISSION.json", "status": "PARTIAL_DEVELOPMENT_PASS_VALIDATION_FAIL"}。

开发的额外1.8对比度标签与学习OOD的独立parents分别标注。训练64、validation16、ID16、OOD16各自按shell/asymmetric_piecewise/smooth/mixed_scale平衡；OOD每族两对象改变结构组合，另两对象保留ID几何分布而将对比度设为1.5/1.8。1.8幅度已用于历史开发探索，后续OOD报告不得称它为从未暴露的物理幅度。全部几何在manifest先冻结，未完成项标记NOT_RUN。

## 前瞻无NN验证补充：validation/development复用

这项追加检验使用已生成validation16中的弱背景、振幅1.2、TV×0.1条件，比较L/F/TASK_R32。它复用validation/development数据，不属于锁定ID/OOD、神经网络测试或样本效率证据。实际状态：COMPLETE；完整parent数16，条件数32，OK逐步指标行1152。新增clean labels为0；这些labels此前已付费，新的估计审核、初始化、I/O和bootstrap均在新作业中计费。

主指标先在各parent内平均clean/20dB误差，再计算F相对L改善，最后对16个parent等权。其点估计为10.5170%，已保存2000次parent bootstrap的95%区间为[6.5944%, 15.3157%]。原始点目标状态PASS；区间相对10%目标为CROSSES_TARGET。父线程审阅支持这个限定条件下的正向改善，但没有确认最小10%改善；它不是formal≥10%通过，也不是NN盲测PASS。

次指标是两个parent等权误差均值的比值改善，为9.4181%。它与平均parent配对改善采用不同统计量，不能互换或用较大的一个替代另一个。

| 方法 | 完整parent | 覆盖完整 | 增量NRMSE | 完整χ NRMSE | 共同质量命中 | 条件数 |
| --- | --- | --- | --- | --- | --- | --- |
| L | 16 | True | 0.751618 | 0.619928 | 0 | 32 |
| F | 16 | True | 0.68083 | 0.562957 | 0 | 32 |
| TASK_R32 | 16 | True | 0.682077 | 0.563928 | 0 | 32 |


| family | parent数 | 完整配对 | L增量NRMSE | F增量NRMSE | TASK_R32增量NRMSE | 平均parent配对改善 |
| --- | --- | --- | --- | --- | --- | --- |
| shell | 4 | True | 0.797438 | 0.744292 | 0.74501 | 6.7308% |
| asymmetric_piecewise | 4 | True | 0.844814 | 0.813571 | 0.81394 | 3.8877% |
| smooth | 4 | True | 0.596553 | 0.461005 | 0.46462 | 23.1587% |
| mixed_scale | 4 | True | 0.767668 | 0.704453 | 0.704738 | 8.2909% |

每family只有四parent；图中保留每个实际parent与均值，不生成未计算的family置信区间。重建图固定取每family最小parent ID的clean条件、K12，不按误差或视觉效果选图。

| 父线程范围裁决 | 最大forward transfer误差 | 最大adjoint误差 | 最小梯度cosine；门槛0.99 | 最大材料误差比TASK_R32/F | 实际覆盖 |
| --- | --- | --- | --- | --- | --- |
| FAIL_FIXED_K12_ENDPOINTS | 0.0178222 | 0.0168199 | 0.975687 | 1.01382 | 32 weak-background amplitude1.2 K12 estimates; not intermediate or neural/OOD states |

新范围的TASK_R32压缩gate失败：尽管forward transfer、adjoint与成像比值接近F，最小gradient cosine低于冻结0.99门槛。历史32个K12终点的通过记录仍保留，不能将它外推为本次validation范围通过，更不能外推到中间、learned或OOD状态。

父线程保存的共同质量命中数：{"F": 0, "L": 0, "TASK_R32": 0}。三臂在32条件中均为0，仍不授予部署加速；online时间只作描述，不能当作匹配cold/warm速度证据。validation现在已暴露；NN仍NOT_RUN，locked ID/OOD仍CLOSED。

原始来源：[SUMMARY.json](results/a25/development/prospective_regime_validation/SUMMARY.json)、[PROVENANCE.json](results/a25/development/prospective_regime_validation/PROVENANCE.json)、[PARENT_REVIEW.json](results/a25/development/prospective_regime_validation/PARENT_REVIEW.json)、[CHECKPOINT_METRICS.csv](results/a25/development/prospective_regime_validation/CHECKPOINT_METRICS.csv)、[TASK_AUDIT.csv](results/a25/development/prospective_regime_validation/TASK_AUDIT.csv)、[八字段探索结果](research/development/PROSPECTIVE_REGIME_RESULT.md)。

[保存的重建arrays压缩包](https://github.com/migodam/a25-adaptive-om-feedback/releases/download/a25-v0.1.0/A25_REPRODUCTION_DATA.zip)中的项目相对路径为`results/a25/development/prospective_regime_validation/arrays/*.npz`；图只读这些离线数组，不读取locked。

## SOM-Net迁移与匹配学习pilot

SOM-Net将电流更新展开为网络，再结合物理场和跨源材料更新。A25的N0是原文四层结构的迁移复现，不声称官方代码逐项复现。N1/N2/N3以共同材料、同一decoder和监督组成匹配实验：N1采用L背景线性信息与明确梯度步，N2采用获准的R反馈closure与相同梯度步，N3使用L特征做generic learned recurrence，省去明确梯度步。N2不写成原生完整F，N3不写成压缩物理闭合。

材料与current/data一致性同时计算；CNN为float32，物理为complex128/float64，状态相关物理梯度不默认detach。训练32为64的固定平衡子集；四parent batch各取一个固定seed抽取的条件，AdamW、学习率、监督权重、更新数和validation选择规则共享。更新数从500/1000/2000按实际GPU成本选定，不能通过看locked质量决定更新数。共同初始化由认证TV求解器完成；CNN块中的box与smooth-TV loss不构成原nonsmooth-TV目标的prox certificate，不能称网络各块已经数值认证。

NOT_RUN：没有对应的已保存原始记录。

GPU健康原始状态：HEALTH_ONLY；成本选择：{"available_cpu_seconds": 3000.0, "available_gpu_seconds": 9900.0, "candidates": [{"fits": false, "projected_cpu_seconds": 6682.8125, "projected_gpu_seconds": 7655.196060142014, "updates": 500}, {"fits": false, "projected_cpu_seconds": 13365.625, "projected_gpu_seconds": 15310.392120284028, "updates": 1000}, {"fits": false, "projected_cpu_seconds": 26731.25, "projected_gpu_seconds": 30620.784240568057, "updates": 2000}], "complete_jobs": 11, "health_job": "a25-gpu-health-blocking-003", "safety_factor": 1.3, "selection_basis": "cost only; no training/validation/test quality", "status": "INSUFFICIENT_BUDGET", "test_truth_opened": false, "updates": null}。

health执行的是known-background硬件与自动微分检查；其更新、loss或有限性不构成训练、成像质量或样本效率证据。已保存训练模型记录数：0；没有模型记录时训练为NOT_RUN。

| health尝试 | 拓扑 | 层数 | 原始status | 一次update wall秒 | 一次update host CPU秒 | 参数数 |
| --- | --- | --- | --- | --- | --- | --- |
| a25-gpu-health-001 | N0 | 4 | HEALTH_ONLY | 0.726442 | 0.71875 | 7464200 |
| a25-gpu-health-001 | N1 | 3 | HEALTH_ONLY | 1.00753 | 0.9375 | 1409574 |
| a25-gpu-health-001 | N2 | 3 | HEALTH_ONLY | 1.41223 | 1.32812 | 1409574 |
| a25-gpu-health-001 | N3 | 3 | HEALTH_ONLY | 0.966031 | 0.90625 | 1409574 |
| a25-gpu-health-001 | N1 | 4 | HEALTH_ONLY | 1.24867 | 1.21875 | 1879432 |
| a25-gpu-health-001 | N2 | 4 | HEALTH_ONLY | 1.96349 | 1.85938 | 1879432 |
| a25-gpu-health-001 | N3 | 4 | HEALTH_ONLY | 1.23055 | 1.1875 | 1879432 |
| a25-gpu-health-batched-002 | N0 | 4 | HEALTH_ONLY | 0.719312 | 0.703125 | 7464200 |
| a25-gpu-health-batched-002 | N1 | 3 | HEALTH_ONLY | 0.856695 | 0.796875 | 1409574 |
| a25-gpu-health-batched-002 | N2 | 3 | HEALTH_ONLY | 1.2635 | 1.125 | 1409574 |
| a25-gpu-health-batched-002 | N3 | 3 | HEALTH_ONLY | 0.909859 | 0.875 | 1409574 |
| a25-gpu-health-batched-002 | N1 | 4 | HEALTH_ONLY | 1.26728 | 1.15625 | 1879432 |
| a25-gpu-health-batched-002 | N2 | 4 | HEALTH_ONLY | 1.95932 | 1.85938 | 1879432 |
| a25-gpu-health-batched-002 | N3 | 4 | HEALTH_ONLY | 1.18266 | 1.17188 | 1879432 |
| a25-gpu-health-blocking-003 | N0 | 4 | HEALTH_ONLY | 0.639619 | 0.609375 | 7464200 |
| a25-gpu-health-blocking-003 | N1 | 3 | HEALTH_ONLY | 0.796589 | 0.734375 | 1409574 |
| a25-gpu-health-blocking-003 | N2 | 3 | HEALTH_ONLY | 1.10855 | 1 | 1409574 |
| a25-gpu-health-blocking-003 | N3 | 3 | HEALTH_ONLY | 0.780827 | 0.6875 | 1409574 |
| a25-gpu-health-blocking-003 | N1 | 4 | HEALTH_ONLY | 1.04384 | 0.84375 | 1879432 |
| a25-gpu-health-blocking-003 | N2 | 4 | HEALTH_ONLY | 1.59048 | 1.23438 | 1879432 |
| a25-gpu-health-blocking-003 | N3 | 4 | HEALTH_ONLY | 1.00689 | 0.890625 | 1879432 |


| health尝试 | 计划每模型更新数 | 完整11模型CPU预测秒 | 完整11模型GPU预测秒 | 符合该分配 | 成本选择原始状态 |
| --- | --- | --- | --- | --- | --- |
| a25-gpu-health-001 | 500 | 8987.47 | 9507.51 | False | INSUFFICIENT_BUDGET |
| a25-gpu-health-001 | 1000 | 17974.9 | 19015 | False | INSUFFICIENT_BUDGET |
| a25-gpu-health-001 | 2000 | 35949.9 | 38030 | False | INSUFFICIENT_BUDGET |
| a25-gpu-health-batched-002 | 500 | 8432.12 | 8971.72 | False | INSUFFICIENT_BUDGET |
| a25-gpu-health-batched-002 | 1000 | 16864.2 | 17943.4 | False | INSUFFICIENT_BUDGET |
| a25-gpu-health-batched-002 | 2000 | 33728.5 | 35886.9 | False | INSUFFICIENT_BUDGET |
| a25-gpu-health-blocking-003 | 500 | 6682.81 | 7655.2 | False | INSUFFICIENT_BUDGET |
| a25-gpu-health-blocking-003 | 1000 | 13365.6 | 15310.4 | False | INSUFFICIENT_BUDGET |
| a25-gpu-health-blocking-003 | 2000 | 26731.2 | 30620.8 | False | INSUFFICIENT_BUDGET |


采用的health索引及旧尝试保留依据：{"adopted_job": "a25-gpu-health-blocking-003", "cost_source": "results/a25/learning/COST_SELECTED_UPDATES.json", "health_source": "results/a25/learning/GPU_HEALTH.json", "old_attempts_retained": true, "reason": "explicit adoption of completed runtime-only attempt"}。

两项已登记的runtime修改分别是集中读取parameter有限性predicate和CUDA blocking-sync等待策略；它们保持物理、网络、精度、同步检查和冻结容差，改善运行时的假设不转换成学习质量结论。[finite-guard登记](research/development/RUNTIME_PREREGISTRATION.md)、[blocking-wait登记](research/development/RUNTIME_BLOCKING_WAIT.md)。

attempt005仅profile一次N2b3的known-background update；原始profile与receipt见[PROFILE_UPDATE.json](https://github.com/migodam/a25-adaptive-om-feedback/releases/download/a25-v0.1.0/A25_COMPLETE_ACTION_LEDGERS.zip)。budget.check的cProfile cumulative项是不可相加的主机WALL诊断，不是CPU费用组成，不能从完整耗时减去它宣称潜在提速。父线程保存的profile摘要：{"budget_check_cumulative_profile_wall_seconds": 0.2552305, "cProfile_times_non_additive_and_not_CPU_component": true, "known_background_only": true, "profiled_N2b3_cpu_seconds": 1.125, "profiled_N2b3_wall_seconds": 1.1963355999905616, "source": "jobs/a25-gpu-profile-retry-005/PROFILE_UPDATE.json", "telemetry_removal_alone_has_no_evidence_for_complete_matrix_fit": true}。attempt004的一次SystemError与已计费终止记录保留；不将单次异常归因到模型、CUDA等待策略或有限性guard。[attempt004 receipt](publication/A25_TERMINAL_RECEIPTS.json)。

已生成数据的原始状态：{"extra_development_states": 8, "new_labels_have_fixed_passive_complex_phase": true, "new_shared_clean_states": 448, "new_train_validation_ID_OOD_parents": 112, "training_labels_not_used_for_learning": true}；累计新增clean labels：456 /456。生成112个独立parent及448个学习clean states不等于已经训练；另外8个开发state耗尽标签额度，失败与未用数据也计费。locked truth在实际评估前不公开。

学习裁决：{"GPU_healthy": true, "additional_numerical_constraint": "prospective TASK_R32 gradient cosine fails0.99; this candidate is not admitted in the newly checked range", "checkpoint_count": 0, "host_cpu_allowance_seconds": 3000.0, "minimum_updates": 500, "projected_cpu_seconds": 6682.8125, "projected_gpu_seconds": 7655.196060142014, "reason": "complete matched 11-model minimum-500-update CPU projection exceeds frozen allowance and total remaining CPU", "scientific_training_updates": 0, "status": "NOT_RUN"}；样本效率：{"status": "NOT_RUN"}；层数：{"status": "NOT_RUN"}。

[A24 冻结研究报告](https://github.com/migodam/a24-source-anchored-om-feedback/blob/ca80ca2a29867e1b03589061dd5c17688c9acbe0/A24_RESEARCH_REPORT_ZH.md)，[SOM-Net 原论文](https://arxiv.org/abs/2209.03567)，[A24 文献读取范围](theory/SOURCES_AND_READING_LEDGER.md)。

## 探索与失败账本

探索记录需要同时说明假设、唯一变化、保持冻结的条件、预期指标、资源上限、实际结果、裁决和下一步。若有原始八字段记录，完整复制到报告数据，不能在探索结束后重写成主实验。缺少记录的计划写NOT_RUN；已有METRICS的追加开发实验则明确呈现真实输出，不因单独JSONL登记缺失而抹去。

| 实验 | 唯一变化与冻结范围 | 保存逐步指标行 | 保存case数 | 记录状态 |
| --- | --- | --- | --- | --- |
| frozen_optimizer_repair | 原TV权重、原32条件；仅修复同目标求解器 | 3456 | 32 | SAVED_OUTPUTS |
| tv_multiplier_0p1 | 相同32观测；初始化与迭代共同降低TV权重，不改写原协议 | 3456 | 32 | SAVED_OUTPUTS |
| amplitude_1p8 | 原TV权重；16条件、8个新增clean labels；仍是历史四parent | 576 | 16 | SAVED_OUTPUTS |

TV与高振幅在输出前分别登记：[TV单因素登记](research/development/TV_SINGLE_FACTOR_PREREGISTRATION.md)、[振幅登记](research/development/AMPLITUDE_PREREGISTRATION.md)。登记中的PENDING是历史原文，实际输出与裁决由对应结果和父线程decision另列，不改写登记。

当前失败账本保留100个去重记录，来源位置随记录保存；所有FAILED、BUDGET_STOP和INTERRUPTED作业均计费。修复后的测试通过不删除早期失败，也不自动产生科学GO。

来源：[FAILURE_LEDGER.jsonl](FAILURE_LEDGER.jsonl)、[探索原始导出](results/a25/report/plot_data/exploration.json)。

## 一次locked ID/OOD验证

独立parents用于检验新材料是否仍满足共享物理和已观察到的学习收益。validation用于训练选择；ID/OOD truth在全部11个模型checkpoint冻结之前关闭。MODEL_FREEZE与results/a25/learning/LOCKED_OPEN.json的一次性记录控制开启；failed cases保留空指标，不再次打开挑选测试结果。

已保存locked状态：NOT_RUN；一次打开记录存在：False。父线程locked裁决：{"status": "CLOSED_NOT_RUN", "truth_opened": false}。

OOD裁决：{"status": "NOT_RUN"}；sample-efficiency/OOD/neural ablation没有实际完整输出时，图与结论保持NOT_RUN。

每parent先平均两背景、两对比度、两noise条件，再对parents等权；2000次paired bootstrap重采样parent，不把同一个parent的8个条件当8个独立对象。缺配对、失败和区间不足会阻止对应科学结论。

原始来源：[cases.csv](results/a25/learning/locked_evaluation/cases.csv)、[parent_summary.json](results/a25/learning/locked_evaluation/parent_summary.json)、[paired_bootstrap.json](results/a25/learning/locked_evaluation/paired_bootstrap.json)、[timing.csv](results/a25/learning/locked_evaluation/timing.csv)。未生成的来源为NOT_RUN。

## A25最终研究裁决

最终判断由父线程写入[A25_GATE_DECISION.json](results/a25/A25_GATE_DECISION.json)。本报告逐项呈现该文件，不从单幅图、单元测试、任务误差或某个成功子集自动生成GO。

父线程总体状态：HOLD。

| 独立问题 | 父线程裁决 | 父线程原始范围与说明 |
| --- | --- | --- |
| solver_health | PASS | {"cause": "old iteration ceiling / slow dual fixed-point convergence; accelerated candidate not fastest", "certified_problems": 14, "independent_references": 6, "required_problems": 14, "selected": "extended_pdhg", "tolerances_unchanged": true} |
| feedback_imaging | PARTIAL | {"aggregate_relative_gain": 0.056994635108287506, "independent_validation": "COMPLETE_PROSPECTIVE_NO_NN_REGIME_CHECK; validation/development, not locked NN test", "original_K12_equal_parent_F_delta_nrmse": 0.7579170985655044, "original_K12_equal_parent_L_delta_nrmse": 0.8037251184170493, "prospective_regime": {"F_vs_L_parent_mean_relative_gain": 0.10517039318291257, "K": 12, "NN": "NOT_RUN", "amplitude": 1.2, "background": "weak", "ci95": [0.06594354225582005, 0.1531568670883614], "compression": {"max_adjoint_error": 0.01681988547545252, "max_material_error_ratio_to_F": 1.0138212782922529, "max_state_data_error": 0.005546922815827388, "max_transfer_error": 0.017822203763375438, "min_gradient_cosine": 0.9756874777116267, "scope": "32 weak-background amplitude1.2 K12 estimates; not intermediate or neural/OOD states", "status": "FAIL_FIXED_K12_ENDPOINTS"}, "estimands_distinguished": "primary mean of paired parent-relative gains; secondary ratio of mean errors", "family_parent_mean_relative_gains": {"asymmetric_piecewise": 0.03887713264553941, "mixed_scale": 0.08290945726778401, "shell": 0.06730832178347762, "smooth": 0.23158666103484926}, "joint_quality_hits_out_of_32": {"F": 0, "L": 0, "TASK_R32": 0}, "locked_ID_OOD": "CLOSED", "minimum_10_percent_improvement_confirmed": false, "new_clean_labels": 0, "paired_parents": 16, "parent_equal_delta_nrmse": {"F": 0.6808303573685768, "L": 0.7516184108592043, "TASK_R32": 0.6820771392205673}, "point_target_status": "PASS", "positive_improvement_supported": true, "ratio_of_parent_equal_mean_gain": 0.09418084026135942, "role": "previously unused validation parents, prospective no-NN regime check; NOT locked validation", "source": "development/prospective_regime_validation/SUMMARY.json", "speed_advantage": "NOT_ESTABLISHED; descriptive per-image times are not matched cold/warm evidence", "status": "POSITIVE_NARROW_REGIME_PARTIAL_THRESHOLD_CONFIRMATION", "tv_multiplier": 0.1, "validation_now_exposed": true}, "regime_confirmation": "POSITIVE_IMPROVEMENT; mean10percent point target met; CI does not establish minimum10percent", "threshold": 0.1, "weak_background_amplitude1p2_parent_mean_gain": 0.1588612407424314} |
| compression | PARTIAL_DEVELOPMENT_PASS_VALIDATION_FAIL | {"deployment_acceleration": "NOT_ESTABLISHED", "historical_development_status": "PASS_DECLARED_DEVELOPMENT_SCOPE", "learned_state_or_OOD_accuracy": "NOT_ESTABLISHED", "prospective_fixed_endpoint_check": {"max_adjoint_error": 0.01681988547545252, "max_material_error_ratio_to_F": 1.0138212782922529, "max_state_data_error": 0.005546922815827388, "max_transfer_error": 0.017822203763375438, "min_gradient_cosine": 0.9756874777116267, "scope": "32 weak-background amplitude1.2 K12 estimates; not intermediate or neural/OOD states", "status": "FAIL_FIXED_K12_ENDPOINTS"}, "scope_correction": "task audits cover 32 historically exposed K12 endpoints only, not all intermediate trajectory states", "selected": "TASK_R32", "source": "development/frozen_optimizer_repair/NN_CLOSURE_ADMISSION.json"} |
| learning | NOT_RUN | {"GPU_healthy": true, "additional_numerical_constraint": "prospective TASK_R32 gradient cosine fails0.99; this candidate is not admitted in the newly checked range", "checkpoint_count": 0, "host_cpu_allowance_seconds": 3000.0, "minimum_updates": 500, "projected_cpu_seconds": 6682.8125, "projected_gpu_seconds": 7655.196060142014, "reason": "complete matched 11-model minimum-500-update CPU projection exceeds frozen allowance and total remaining CPU", "scientific_training_updates": 0} |
| sample_efficiency | NOT_RUN | {} |
| OOD | NOT_RUN | {} |
| depth | NOT_RUN | {} |
| locked_validation | CLOSED_NOT_RUN | {"truth_opened": false} |
| deployment | NOT_ESTABLISHED | {"original_conditions": 32, "original_quality_hits": 0, "prospective_joint_quality_hits": {"F": 0, "L": 0, "TASK_R32": 0}, "reason": "no complete paired common-quality regime; no trained-network endpoint latency", "tv0p1_F_quality_hits": 1, "tv0p1_conditions": 32} |

下一步：{"automatic_expansion": false, "decision": "HOLD_LEARNING_AND_DEPLOYMENT_CLAIMS", "recommendation": "Feedback has a reproducible positive narrow-regime imaging signal. Retain PARTIAL/HOLD for uniform ten-percent, learning and deployment claims. TASK_R32 fails the new-range gradient-cosine gate: repair and validate this before a new NN pilot, and separately reduce full differentiated host-CPU cost. Do not reopen exposed validation as untouched test."}。

已接受作业 CPU计费 1640.92 秒 /7200秒；GPU占用 116.575 秒 /14400秒。报告自身仍在运行的尾部单独记为 provisional；完整截止作业清单见 results/a25/report/COST_SUMMARY.json，最终资源以不可变 job_receipt.json 为准。[完整动作账本压缩包](https://github.com/migodam/a25-adaptive-om-feedback/releases/download/a25-v0.1.0/A25_COMPLETE_ACTION_LEDGERS.zip)包含项目相对路径 `COST_LEDGER.jsonl`及各作业的 `results/a25/jobs/<job>/COST_LEDGER.jsonl`；大文件通过Release提供，公开CSV、图表和小型metadata仍保留在Git。

逐项八字段及原登记、保存结果和不可变成本来源见[完整探索记录](research/development/A25_EXPLORATION_RECORDS.md)。该文是事后忠实整合，不是新的预登记。

理论恒等式、优化器数值健康、反馈成像收益、匹配学习收益与完整部署收益分别成立或未成立。任一局部PASS只对应其声明范围。

## 实际图表

- [solver_certificates.png](results/a25/report/figures/solver_certificates.png)：同目标 prox 的原始外部证书；不是完整逆散射成像性能。
- [convergence_runtime.png](results/a25/report/figures/convergence_runtime.png)：冻结协议：认证求解器重放；K1–12实际输出，每点要求全部32条件。
- [quality_time_pareto.png](results/a25/report/figures/quality_time_pareto.png)：冻结协议：认证求解器重放；每个K单独标出已观察非劣点，不外推为部署速度保证。
- [rank_task_error.png](results/a25/report/figures/rank_task_error.png)：冻结协议：认证求解器重放；实际forward/adjoint误差与梯度cosine，失败保留原表。
- [development_images.png](results/a25/report/figures/development_images.png)：冻结协议：认证求解器重放；固定样例的材料增量实部，失败不换成成功对象。
- [tv0p1_convergence_runtime.png](results/a25/report/figures/tv0p1_convergence_runtime.png)：追加开发探索：TV×0.1；K1–12实际输出，每点要求全部32条件。
- [tv0p1_quality_time_pareto.png](results/a25/report/figures/tv0p1_quality_time_pareto.png)：追加开发探索：TV×0.1；每个K单独标出已观察非劣点，不外推为部署速度保证。
- [tv0p1_rank_task_error.png](results/a25/report/figures/tv0p1_rank_task_error.png)：追加开发探索：TV×0.1；实际forward/adjoint误差与梯度cosine，失败保留原表。
- [tv0p1_development_images.png](results/a25/report/figures/tv0p1_development_images.png)：追加开发探索：TV×0.1；固定样例的材料增量实部，失败不换成成功对象。
- [amplitude1p8_convergence_runtime.png](results/a25/report/figures/amplitude1p8_convergence_runtime.png)：追加开发探索：振幅1.8；K1–12实际输出，每点要求全部16条件。
- [amplitude1p8_quality_time_pareto.png](results/a25/report/figures/amplitude1p8_quality_time_pareto.png)：追加开发探索：振幅1.8；每个K单独标出已观察非劣点，不外推为部署速度保证。
- [amplitude1p8_rank_task_error.png](results/a25/report/figures/amplitude1p8_rank_task_error.png)：追加开发探索：振幅1.8；实际forward/adjoint误差与梯度cosine，失败保留原表。
- [amplitude1p8_development_images.png](results/a25/report/figures/amplitude1p8_development_images.png)：追加开发探索：振幅1.8；固定样例的材料增量实部，失败不换成成功对象。
- [prospective_family_paired_gain.png](results/a25/report/figures/prospective_family_paired_gain.png)：四family各四parent；先平均clean/20dB，再计算parent改善。family只画实际点与均值，总体区间使用已保存bootstrap。
- [prospective_fixed_family_images.png](results/a25/report/figures/prospective_fixed_family_images.png)：固定shell/asymmetric_piecewise/smooth/mixed_scale各首个parent，clean、K12；只读已保存离线arrays，不读取locked。
- nn_sample_efficiency.png：NOT_RUN，no complete saved evidence。
- ood_quality.png：NOT_RUN，no complete saved evidence。
- matched_ablation.png：NOT_RUN，no complete saved evidence。
- locked_images.png：NOT_RUN，no complete saved evidence。

## 资源与复核边界

已接受作业 CPU计费 1640.92 秒 /7200秒；GPU占用 116.575 秒 /14400秒。报告自身仍在运行的尾部单独记为 provisional；完整截止作业清单见 results/a25/report/COST_SUMMARY.json，最终资源以不可变 job_receipt.json 为准。[完整动作账本压缩包](https://github.com/migodam/a25-adaptive-om-feedback/releases/download/a25-v0.1.0/A25_COMPLETE_ACTION_LEDGERS.zip)包含项目相对路径 `COST_LEDGER.jsonl`及各作业的 `results/a25/jobs/<job>/COST_LEDGER.jsonl`；大文件通过Release提供，公开CSV、图表和小型metadata仍保留在Git。


公开作业receipt链接指向不可变receipt的脱敏汇总，可按job ID查找；逐文件原件与PROFILE_UPDATE在账本Release ZIP的项目相对路径中。CSV和实验JSON仍可直接在仓库读取。
