# 固定高幅度检验

Hypothesis: 更大的相对材料变化会扩大同背景下F相对L的材料恢复改善。
Motivating evidence: 固定12步，较高幅度下F/L差异更明显；弱背景TV0.1开发条件已有约15.9%改善，聚合证据仍不足。
Proposed modification: 只增加幅度1.8，仍用原TV1.0。四历史parents、两背景、无噪声/20dB；L/F/TASK_R32。
Development experiment: 最多8个新增clean labels，参数及种子由已冻结几何与master seed确定；12步及K3/6/12。
Observed result: PENDING before generation.
Decision: PENDING;不用于选择NNrank或test场景。
New cost: 新job计费，和448个学习labels合计不能超过456。
Validation eligibility: 已暴露development对象；1.8不得在后续OOD报告中宣称全新物理幅度。此regime结论仍需独立无NN验证。
