# 冻结假设的有界无网络检查

| 字段 | 记录 |
|---|---|
| Hypothesis | 弱背景、幅度1.2、共同TV×0.1、K12，F相对L的parent平均相对delta误差收益至少10%。 |
| Motivating evidence | 四个历史development parents的该regime平均收益16.03%；这仅用于提出假设。 |
| Proposed modification | 不改变求解器或物理；复用新数据集中16个validation parents，固定L/F/TASK_R32及原噪声。 |
| Development experiment | configs/a25/regime_validation.json在运行前冻结；32观测×3臂×12，零新clean labels，50.31685CPU秒。 |
| Observed result | 16parents完整。F/L平均相对收益10.517%，95%区间6.594%–15.316%；TASK_R32最小梯度余弦0.975687，未过0.99。 |
| Decision | 正向窄regime收益支持；至少10%仍PARTIAL，压缩新范围FAIL，无NN/部署结论；不自动扩大。 |
| New cost | 复用已计费标签，新估计材料full-wave审核、构基、prox、I/O与bootstrap全部在prospective-regime-validation-001收费；本审阅另计。 |
| Validation eligibility | validation已暴露并成为开发证据。ID/OOD保持关闭；这些对象不能再次称为untouched test。 |

原始文件：results/a25/development/prospective_regime_validation/SUMMARY.json、PARENT_REVIEW.json、EXPOSURE.json。主统计为逐parent相对收益的均值；均值误差比另为9.418%，两者不混用。
