# 同目标TV求解器修复与独立证书

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
