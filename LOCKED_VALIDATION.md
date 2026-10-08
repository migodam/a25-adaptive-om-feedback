# 一次locked ID/OOD验证

独立parents用于检验新材料是否仍满足共享物理和已观察到的学习收益。validation用于训练选择；ID/OOD truth在全部11个模型checkpoint冻结之前关闭。MODEL_FREEZE与results/a25/learning/LOCKED_OPEN.json的一次性记录控制开启；failed cases保留空指标，不再次打开挑选测试结果。

已保存locked状态：NOT_RUN；一次打开记录存在：False。父线程locked裁决：{"status": "CLOSED_NOT_RUN", "truth_opened": false}。

OOD裁决：{"status": "NOT_RUN"}；sample-efficiency/OOD/neural ablation没有实际完整输出时，图与结论保持NOT_RUN。

每parent先平均两背景、两对比度、两noise条件，再对parents等权；2000次paired bootstrap重采样parent，不把同一个parent的8个条件当8个独立对象。缺配对、失败和区间不足会阻止对应科学结论。

原始来源：[cases.csv](results/a25/learning/locked_evaluation/cases.csv)、[parent_summary.json](results/a25/learning/locked_evaluation/parent_summary.json)、[paired_bootstrap.json](results/a25/learning/locked_evaluation/paired_bootstrap.json)、[timing.csv](results/a25/learning/locked_evaluation/timing.csv)。未生成的来源为NOT_RUN。
