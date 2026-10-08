# 数值验证与证据边界

`final-source-validation-001` 实际完成96项测试，errors=0、failures=0。保留A24的47项验证并新增49项A25验证，覆盖公共prox/SOCP证书、固定证书尺度、warm-state owner、费用及预算、Torch前向/伴随与高阶梯度、源/接收器置换、缓存失效和数据隔离。测试源码在 `tests/`；原始测试结果与不可变receipt放在[完整账本Release资产](https://github.com/migodam/a25-adaptive-om-feedback/releases/download/a25-v0.1.0/A25_COMPLETE_ACTION_LEDGERS.zip)的 `results/a25/jobs/final-source-validation-001/`。

这些测试验证公式和接口的一致性，不证明成像或学习优越性。实际二维TM成像证据来自冻结32条件、TV单因素32条件、振幅1.8的16条件，以及后续16-parent窄范围验证；独立压缩探针只覆盖相应K12端点。神经网络健康更新仅验证硬件及自动微分可执行，科学训练、样本效率、OOD与神经推理优势仍未运行。

报告导出第一次失败及第二次修复后的实际输出也留账。发布打包、数值元数据保留、敏感字段扫描及匿名访问核验均是交付验证，不能改变科学HOLD结论。
