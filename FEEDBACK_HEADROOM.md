# 完整反馈的成像余量

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
