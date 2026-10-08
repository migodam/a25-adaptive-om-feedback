# A25 单因素 TV 探索（输出前登记）

Hypothesis: 固定 TV 权重对差分信号过强；共同降低到0.1倍可能改善边缘和材料恢复。

Motivating evidence: 认证求解器的32条件冻结重放全部更新接受；K12材料误差仍约0.76，边缘误差接近1。未观察到回溯拒绝瓶颈。

Proposed modification: 仅 TV 权重乘0.1，L/F/R/ROM/Born同时改变；背景、步长、初始化算法、box、12次更新及噪声不变。初始化也使用同一新TV权重。

Development experiment: 四个已暴露parents，32共同观测，原九臂；同轨迹K3/6/12；完整Maxwell离线审核每轮。

Observed result: PENDING at registration.

Decision: PENDING;无网络开发探索，不修改已冻结训练协议或A24结论。

New cost: 使用新独立job receipt，失败及审核一并计费；新增clean labels为0。

Validation eligibility: 仅development证据；当前NN独立实验仍使用原TV权重。任何新的无NN泛化结论需要后续独立验证。
