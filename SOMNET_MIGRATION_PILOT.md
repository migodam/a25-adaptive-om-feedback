# SOM-Net迁移与匹配学习pilot

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


公开作业receipt链接指向不可变receipt的脱敏汇总，可按job ID查找；逐文件原件与PROFILE_UPDATE在账本Release ZIP的项目相对路径中。CSV和实验JSON仍可直接在仓库读取。
