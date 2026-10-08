# GPU host开销单因素检查

Hypothesis: optimizer后逐parameter CUDA布尔读取引入过多同步；集中读取同一有限性predicate可降低实际host成本。
Motivating evidence: 首轮health最低500更新的11模型预计CPU8987秒，预算不能容纳；N2 update wall1.41秒/CPU1.33秒。
Proposed modification: 所有parameter的isfinite/all仍执行，GPU上stack/all后只读取一次布尔；梯度clip仍error_if_nonfinite=True；模型、物理精度、优化器和cost ledger同步规则不变。
Development experiment: 完整七拓扑known-background health，两次重复；不训练、不读取test。
Observed result: PENDING at registration.
Decision: PENDING；仅成本可以选择训练更新档。
New cost: 新GPU/host CPU job，旧成本保留。
Validation eligibility: 数值运行时改进；不构成学习或成像收益。
