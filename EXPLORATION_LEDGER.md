# 探索与失败账本

探索记录需要同时说明假设、唯一变化、保持冻结的条件、预期指标、资源上限、实际结果、裁决和下一步。若有原始八字段记录，完整复制到报告数据，不能在探索结束后重写成主实验。缺少记录的计划写NOT_RUN；已有METRICS的追加开发实验则明确呈现真实输出，不因单独JSONL登记缺失而抹去。

| 实验 | 唯一变化与冻结范围 | 保存逐步指标行 | 保存case数 | 记录状态 |
| --- | --- | --- | --- | --- |
| frozen_optimizer_repair | 原TV权重、原32条件；仅修复同目标求解器 | 3456 | 32 | SAVED_OUTPUTS |
| tv_multiplier_0p1 | 相同32观测；初始化与迭代共同降低TV权重，不改写原协议 | 3456 | 32 | SAVED_OUTPUTS |
| amplitude_1p8 | 原TV权重；16条件、8个新增clean labels；仍是历史四parent | 576 | 16 | SAVED_OUTPUTS |

TV与高振幅在输出前分别登记：[TV单因素登记](research/development/TV_SINGLE_FACTOR_PREREGISTRATION.md)、[振幅登记](research/development/AMPLITUDE_PREREGISTRATION.md)。登记中的PENDING是历史原文，实际输出与裁决由对应结果和父线程decision另列，不改写登记。

当前失败账本保留100个去重记录，来源位置随记录保存；所有FAILED、BUDGET_STOP和INTERRUPTED作业均计费。修复后的测试通过不删除早期失败，也不自动产生科学GO。

来源：[FAILURE_LEDGER.jsonl](FAILURE_LEDGER.jsonl)、[探索原始导出](results/a25/report/plot_data/exploration.json)。

逐项八字段及原登记、保存结果和不可变成本来源见[完整探索记录](research/development/A25_EXPLORATION_RECORDS.md)。该文是事后忠实整合，不是新的预登记。
