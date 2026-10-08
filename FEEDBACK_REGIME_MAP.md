# 反馈适用范围与证据域

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
