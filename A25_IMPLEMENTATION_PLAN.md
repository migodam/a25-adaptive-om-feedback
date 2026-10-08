# A25 实施合同

冻结来源为 A24 `ca80ca2a29867e1b03589061dd5c17688c9acbe0`；继承的文件是 frozen controls，A25 结果只写入 `results/a25`。本项目是 24×24 二维 TM，不能作为三维 vector-Maxwell 证据。

顺序为公共 TV 求解器认证 → 旧四对象无 NN 开发与反馈任务审核 → 新 parent 数据及小型学习成本 benchmark → 匹配训练 → 一次 locked validation → 科学复核与公开发布。A24 的门槛及失败不改写。

## 冻结条件

- CPU 累计上限 7200 秒；CPU-only 按 wall/process CPU 较大者。CUDA 作业的 host CPU 单列计入 CPU，GPU 占用上限 14400 秒。
- TV/KKT 与 normalized gap 仍为 1e-6，物理 box feasibility 1e-10；外部证书固定原始 PDHG 步长，内部加速不影响验收尺度。
- 每个新 prox 最多 20000 迭代、2秒；独立 Clarabel0.11.1 SOCP 最多200迭代、5秒。
- 四个历史 parent 2401–2404 仅作 development。开发新标签最多8个（幅度1.8），新学习标签448个；总上限456。
- N1/N2/N3 使用相同 decoder、共同材料图、输入权限和监督；主比较3blocks，64-parent档追加4blocks；N0为原文四层的迁移复现，不是官方代码。
- AdamW lr1e-3、wd1e-5、parent batch4、clip1；根据成本 benchmark 从500/1000/2000选最高可完成必需配对的更新数。每100更新验证。
- 物理 complex128/float64，CNN float32；不默认 detach 状态相关梯度。
- ID/OOD test 在全部候选及 checkpoints 冻结前拒读；最终仅统一打开一次。未运行项目明确 NOT_RUN。

## A25 独立 gates

求解器健康需要独立同目标参考、原失败的可靠证书，以及有效强背景 L/F/R 配对。

NN closure 在声明范围内要求独立 forward/adjoint task误差≤5%、gradient cosine≥0.99、同 prior 材料质量相对F恶化≤5%，并有可接受成本；F/L低于10%不单独阻止学习实验。

学习/OOD收益要求≥10%，N2必须相对N1和N3有独立增量；材料质量非劣界5%。样本效率、层数、数据一致性分别裁决。相同质量的完整推理提速要求≥20%。parent等权及2000次paired bootstrap；缺配对、失败或区间不足时HOLD。

## 输出及执行边界

每个作业有持久 manifest、成本和失败记录，失败与重跑累计；不按成功图筛选统计。独立准备成本与共享实际成本同时报告，冷/温计时重置材料和递归状态。所有探索保留八字段 ledger。没有共同质量命中时不给 acceleration GO。

公开仓库 `migodam/a25-adaptive-om-feedback`；大型数据及 checkpoints放Release。最终提供实际远端commit、研究报告和匿名raw链接。不执行SHA256检查；不自动扩到128train、3D或大型网络。
