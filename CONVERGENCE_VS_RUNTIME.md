# 收敛、相同K与完整推理时间

一个更准的单次反馈动作不保证更快得到合格材料。比较先固定K，再观察达到共同质量目标所需的完整时间。online_s包含共同初始化和在线迭代；独立冷成本再加入一次已知背景准备与方法准备。离线完整场质量审核另列，不混入普通部署推理。共享试验真正只付一次的准备成本与单方法独立成本同时报告。

### 冻结协议：认证求解器重放

原TV权重、原32条件；仅修复同目标求解器。

| 方法 | K | OK条件 | 应有条件 | 完整parent配对 | 增量NRMSE | 共享准备秒 | 方法准备秒 | 初始化+online秒 | 单方法独立冷成本秒 | 质量命中数 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| AFFINE_ROM32 | 3 | 32 | 32 | True | 0.873807 | 0.017399 | 0.00590473 | 0.910359 | 0.933663 | 0 |
| AFFINE_ROM32 | 6 | 32 | 32 | True | 0.871495 | 0.017399 | 0.00590473 | 1.17736 | 1.20066 | 0 |
| AFFINE_ROM32 | 12 | 32 | 32 | True | 0.875988 | 0.017399 | 0.00590473 | 1.43109 | 1.45439 | 0 |
| BORN_TV | 3 | 32 | 32 | True | 0.966036 | 0.017399 | 8.0229e-05 | 1.17225 | 1.18973 | 0 |
| BORN_TV | 6 | 32 | 32 | True | 0.963621 | 0.017399 | 8.0229e-05 | 1.33182 | 1.3493 | 0 |
| BORN_TV | 12 | 32 | 32 | True | 0.963609 | 0.017399 | 8.0229e-05 | 1.5342 | 1.55168 | 0 |
| F | 3 | 32 | 32 | True | 0.815692 | 0.017399 | 5.82495e-05 | 0.73256 | 0.750017 | 0 |
| F | 6 | 32 | 32 | True | 0.784086 | 0.017399 | 5.82495e-05 | 0.981828 | 0.999285 | 0 |
| F | 12 | 32 | 32 | True | 0.757917 | 0.017399 | 5.82495e-05 | 1.40949 | 1.42695 | 0 |
| L | 3 | 32 | 32 | True | 0.832328 | 0.017399 | 0.000221855 | 0.682819 | 0.70044 | 0 |
| L | 6 | 32 | 32 | True | 0.815147 | 0.017399 | 0.000221855 | 0.914057 | 0.931678 | 0 |
| L | 12 | 32 | 32 | True | 0.803725 | 0.017399 | 0.000221855 | 1.22114 | 1.23876 | 0 |
| LOCAL_R16 | 3 | 32 | 32 | True | 0.816932 | 0.017399 | 0.0567004 | 1.08555 | 1.15965 | 0 |
| LOCAL_R16 | 6 | 32 | 32 | True | 0.786229 | 0.017399 | 0.0567004 | 1.63892 | 1.71302 | 0 |
| LOCAL_R16 | 12 | 32 | 32 | True | 0.760833 | 0.017399 | 0.0567004 | 2.67284 | 2.74694 | 0 |
| R16 | 3 | 32 | 32 | True | 0.816649 | 0.017399 | 0.00410002 | 0.715501 | 0.737 | 0 |
| R16 | 6 | 32 | 32 | True | 0.785835 | 0.017399 | 0.00410002 | 0.944621 | 0.96612 | 0 |
| R16 | 12 | 32 | 32 | True | 0.760412 | 0.017399 | 0.00410002 | 1.30937 | 1.33087 | 0 |
| R24 | 3 | 32 | 32 | True | 0.816385 | 0.017399 | 0.00483942 | 0.71475 | 0.736988 | 0 |
| R24 | 6 | 32 | 32 | True | 0.78531 | 0.017399 | 0.00483942 | 0.940187 | 0.962425 | 0 |
| R24 | 12 | 32 | 32 | True | 0.759635 | 0.017399 | 0.00483942 | 1.26474 | 1.28698 | 0 |
| R32 | 3 | 32 | 32 | True | 0.816068 | 0.017399 | 0.00589781 | 0.713033 | 0.736329 | 0 |
| R32 | 6 | 32 | 32 | True | 0.784754 | 0.017399 | 0.00589781 | 0.943379 | 0.966676 | 0 |
| R32 | 12 | 32 | 32 | True | 0.75887 | 0.017399 | 0.00589781 | 1.30795 | 1.33124 | 0 |
| TASK_R32 | 3 | 32 | 32 | True | 0.815919 | 0.017399 | 0.019665 | 0.7139 | 0.750964 | 0 |
| TASK_R32 | 6 | 32 | 32 | True | 0.784513 | 0.017399 | 0.019665 | 0.941671 | 0.978735 | 0 |
| TASK_R32 | 12 | 32 | 32 | True | 0.758536 | 0.017399 | 0.019665 | 1.31092 | 1.34799 | 0 |

原始逐步记录：[METRICS.csv](results/a25/development/frozen_optimizer_repair/METRICS.csv)、[完整HISTORIES：A25_REPRODUCTION_DATA.zip](https://github.com/migodam/a25-adaptive-om-feedback/releases/download/a25-v0.1.0/A25_REPRODUCTION_DATA.zip)（压缩包内项目相对路径：`results/a25/development/frozen_optimizer_repair/HISTORIES.json`）；报告等权导出：[frozen_optimizer_repair_parent_equal.csv](results/a25/report/plot_data/frozen_optimizer_repair_parent_equal.csv)。

### 追加开发探索：TV×0.1

相同32观测；初始化与迭代共同降低TV权重，不改写原协议。

| 方法 | K | OK条件 | 应有条件 | 完整parent配对 | 增量NRMSE | 共享准备秒 | 方法准备秒 | 初始化+online秒 | 单方法独立冷成本秒 | 质量命中数 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| AFFINE_ROM32 | 3 | 32 | 32 | True | 0.840405 | 0.0223016 | 0.00643775 | 0.108299 | 0.137039 | 0 |
| AFFINE_ROM32 | 6 | 32 | 32 | True | 0.831108 | 0.0223016 | 0.00643775 | 0.154729 | 0.183468 | 0 |
| AFFINE_ROM32 | 12 | 32 | 32 | True | 0.832631 | 0.0223016 | 0.00643775 | 0.230003 | 0.258742 | 0 |
| BORN_TV | 3 | 32 | 32 | True | 0.962867 | 0.0223016 | 8.35e-05 | 0.0733144 | 0.0956995 | 0 |
| BORN_TV | 6 | 32 | 32 | True | 0.966821 | 0.0223016 | 8.35e-05 | 0.111201 | 0.133586 | 0 |
| BORN_TV | 12 | 32 | 32 | True | 0.97129 | 0.0223016 | 8.35e-05 | 0.169006 | 0.191391 | 0 |
| F | 3 | 32 | 32 | True | 0.761705 | 0.0223016 | 7.5e-05 | 0.124396 | 0.146773 | 0 |
| F | 6 | 32 | 32 | True | 0.71344 | 0.0223016 | 7.5e-05 | 0.191705 | 0.214082 | 0 |
| F | 12 | 32 | 32 | True | 0.670086 | 0.0223016 | 7.5e-05 | 0.314468 | 0.336844 | 1 |
| L | 3 | 32 | 32 | True | 0.78115 | 0.0223016 | 0.000321167 | 0.0894127 | 0.112035 | 0 |
| L | 6 | 32 | 32 | True | 0.749456 | 0.0223016 | 0.000321167 | 0.136873 | 0.159495 | 0 |
| L | 12 | 32 | 32 | True | 0.723377 | 0.0223016 | 0.000321167 | 0.217448 | 0.240071 | 0 |
| LOCAL_R16 | 3 | 32 | 32 | True | 0.763119 | 0.0223016 | 0.0604254 | 0.499199 | 0.581926 | 0 |
| LOCAL_R16 | 6 | 32 | 32 | True | 0.715943 | 0.0223016 | 0.0604254 | 0.871875 | 0.954602 | 0 |
| LOCAL_R16 | 12 | 32 | 32 | True | 0.67366 | 0.0223016 | 0.0604254 | 1.62477 | 1.7075 | 1 |
| R16 | 3 | 32 | 32 | True | 0.7628 | 0.0223016 | 0.00552108 | 0.0997944 | 0.127617 | 0 |
| R16 | 6 | 32 | 32 | True | 0.715503 | 0.0223016 | 0.00552108 | 0.148384 | 0.176206 | 0 |
| R16 | 12 | 32 | 32 | True | 0.673152 | 0.0223016 | 0.00552108 | 0.238782 | 0.266605 | 1 |
| R24 | 3 | 32 | 32 | True | 0.762504 | 0.0223016 | 0.00616519 | 0.102687 | 0.131154 | 0 |
| R24 | 6 | 32 | 32 | True | 0.714846 | 0.0223016 | 0.00616519 | 0.150713 | 0.17918 | 0 |
| R24 | 12 | 32 | 32 | True | 0.672098 | 0.0223016 | 0.00616519 | 0.239334 | 0.267801 | 1 |
| R32 | 3 | 32 | 32 | True | 0.762202 | 0.0223016 | 0.0072506 | 0.103292 | 0.132844 | 0 |
| R32 | 6 | 32 | 32 | True | 0.714327 | 0.0223016 | 0.0072506 | 0.150947 | 0.1805 | 0 |
| R32 | 12 | 32 | 32 | True | 0.67138 | 0.0223016 | 0.0072506 | 0.237371 | 0.266923 | 1 |
| TASK_R32 | 3 | 32 | 32 | True | 0.762018 | 0.0223016 | 0.023046 | 0.0974215 | 0.142769 | 0 |
| TASK_R32 | 6 | 32 | 32 | True | 0.71404 | 0.0223016 | 0.023046 | 0.146283 | 0.191631 | 0 |
| TASK_R32 | 12 | 32 | 32 | True | 0.670983 | 0.0223016 | 0.023046 | 0.22932 | 0.274667 | 1 |

原始逐步记录：[METRICS.csv](results/a25/development/tv_multiplier_0p1/METRICS.csv)、[完整HISTORIES：A25_REPRODUCTION_DATA.zip](https://github.com/migodam/a25-adaptive-om-feedback/releases/download/a25-v0.1.0/A25_REPRODUCTION_DATA.zip)（压缩包内项目相对路径：`results/a25/development/tv_multiplier_0p1/HISTORIES.json`）；报告等权导出：[tv_multiplier_0p1_parent_equal.csv](results/a25/report/plot_data/tv_multiplier_0p1_parent_equal.csv)。

### 追加开发探索：振幅1.8

原TV权重；16条件、8个新增clean labels；仍是历史四parent。

| 方法 | K | OK条件 | 应有条件 | 完整parent配对 | 增量NRMSE | 共享准备秒 | 方法准备秒 | 初始化+online秒 | 单方法独立冷成本秒 | 质量命中数 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| F | 3 | 16 | 16 | True | 0.833663 | 0.01745 | 5.95e-05 | 0.957478 | 0.974987 | 0 |
| F | 6 | 16 | 16 | True | 0.784475 | 0.01745 | 5.95e-05 | 1.23317 | 1.25068 | 0 |
| F | 12 | 16 | 16 | True | 0.728679 | 0.01745 | 5.95e-05 | 1.93063 | 1.94814 | 0 |
| L | 3 | 16 | 16 | True | 0.87109 | 0.01745 | 0.000123083 | 0.809464 | 0.827037 | 0 |
| L | 6 | 16 | 16 | True | 0.856925 | 0.01745 | 0.000123083 | 1.09535 | 1.11292 | 0 |
| L | 12 | 16 | 16 | True | 0.846886 | 0.01745 | 0.000123083 | 1.69451 | 1.71208 | 0 |
| TASK_R32 | 3 | 16 | 16 | True | 0.834089 | 0.01745 | 0.0186199 | 0.91202 | 0.94809 | 0 |
| TASK_R32 | 6 | 16 | 16 | True | 0.785492 | 0.01745 | 0.0186199 | 1.17837 | 1.21444 | 0 |
| TASK_R32 | 12 | 16 | 16 | True | 0.730703 | 0.01745 | 0.0186199 | 1.83754 | 1.87361 | 0 |

原始逐步记录：[METRICS.csv](results/a25/development/amplitude_1p8/METRICS.csv)、[完整HISTORIES：A25_REPRODUCTION_DATA.zip](https://github.com/migodam/a25-adaptive-om-feedback/releases/download/a25-v0.1.0/A25_REPRODUCTION_DATA.zip)（压缩包内项目相对路径：`results/a25/development/amplitude_1p8/HISTORIES.json`）；报告等权导出：[amplitude_1p8_parent_equal.csv](results/a25/report/plot_data/amplitude_1p8_parent_equal.csv)。
没有共同命中质量区域时，质量—时间散点只作描述。图中的非劣线只连接同一实验、同一K的已观察完整配对点，不是所有算法的最优速度边界。GPU缓存训练初始化不能作为部署已经免除初始化；完整cold/warm计时要实际加载缓存、重置状态、重算或单列初始化时间。

NOT_RUN：没有对应的已保存原始记录。

部署裁决：{"original_conditions": 32, "original_quality_hits": 0, "prospective_joint_quality_hits": {"F": 0, "L": 0, "TASK_R32": 0}, "reason": "no complete paired common-quality regime; no trained-network endpoint latency", "status": "NOT_ESTABLISHED", "tv0p1_F_quality_hits": 1, "tv0p1_conditions": 32}。

已知背景准备成本：

| 实验 | 背景 | 方法 | 共享准备秒 | 方法准备秒 | 原始状态 |
| --- | --- | --- | --- | --- | --- |
| frozen_optimizer_repair | weak | L | 0.0183282 | 0.000338834 | RECORDED |
| frozen_optimizer_repair | weak | F | 0.0183282 | 6.2791e-05 | RECORDED |
| frozen_optimizer_repair | weak | R16 | 0.0183282 | 0.00447642 | RECORDED |
| frozen_optimizer_repair | weak | R24 | 0.0183282 | 0.00500742 | RECORDED |
| frozen_optimizer_repair | weak | R32 | 0.0183282 | 0.00611404 | RECORDED |
| frozen_optimizer_repair | weak | LOCAL_R16 | 0.0183282 | 0.0552577 | RECORDED |
| frozen_optimizer_repair | weak | TASK_R32 | 0.0183282 | 0.0333231 | RECORDED |
| frozen_optimizer_repair | weak | AFFINE_ROM32 | 0.0183282 | 0.00589875 | RECORDED |
| frozen_optimizer_repair | weak | BORN_TV | 0.0183282 | 7.4916e-05 | RECORDED |
| frozen_optimizer_repair | ring | L | 0.0164698 | 0.000104875 | RECORDED |
| frozen_optimizer_repair | ring | F | 0.0164698 | 5.3708e-05 | RECORDED |
| frozen_optimizer_repair | ring | R16 | 0.0164698 | 0.00372363 | RECORDED |
| frozen_optimizer_repair | ring | R24 | 0.0164698 | 0.00467142 | RECORDED |
| frozen_optimizer_repair | ring | R32 | 0.0164698 | 0.00568158 | RECORDED |
| frozen_optimizer_repair | ring | LOCAL_R16 | 0.0164698 | 0.058143 | RECORDED |
| frozen_optimizer_repair | ring | TASK_R32 | 0.0164698 | 0.00600692 | RECORDED |
| frozen_optimizer_repair | ring | AFFINE_ROM32 | 0.0164698 | 0.00591071 | RECORDED |
| frozen_optimizer_repair | ring | BORN_TV | 0.0164698 | 8.5542e-05 | RECORDED |
| tv_multiplier_0p1 | weak | L | 0.0255124 | 0.00050675 | RECORDED |
| tv_multiplier_0p1 | weak | F | 0.0255124 | 8.2333e-05 | RECORDED |
| tv_multiplier_0p1 | weak | R16 | 0.0255124 | 0.00671954 | RECORDED |
| tv_multiplier_0p1 | weak | R24 | 0.0255124 | 0.00718562 | RECORDED |
| tv_multiplier_0p1 | weak | R32 | 0.0255124 | 0.00788058 | RECORDED |
| tv_multiplier_0p1 | weak | LOCAL_R16 | 0.0255124 | 0.0598274 | RECORDED |
| tv_multiplier_0p1 | weak | TASK_R32 | 0.0255124 | 0.0399127 | RECORDED |
| tv_multiplier_0p1 | weak | AFFINE_ROM32 | 0.0255124 | 0.00649142 | RECORDED |
| tv_multiplier_0p1 | weak | BORN_TV | 0.0255124 | 8.2292e-05 | RECORDED |
| tv_multiplier_0p1 | ring | L | 0.0190908 | 0.000135583 | RECORDED |
| tv_multiplier_0p1 | ring | F | 0.0190908 | 6.7667e-05 | RECORDED |
| tv_multiplier_0p1 | ring | R16 | 0.0190908 | 0.00432262 | RECORDED |
| tv_multiplier_0p1 | ring | R24 | 0.0190908 | 0.00514475 | RECORDED |
| tv_multiplier_0p1 | ring | R32 | 0.0190908 | 0.00662062 | RECORDED |
| tv_multiplier_0p1 | ring | LOCAL_R16 | 0.0190908 | 0.0610234 | RECORDED |
| tv_multiplier_0p1 | ring | TASK_R32 | 0.0190908 | 0.00617925 | RECORDED |
| tv_multiplier_0p1 | ring | AFFINE_ROM32 | 0.0190908 | 0.00638408 | RECORDED |
| tv_multiplier_0p1 | ring | BORN_TV | 0.0190908 | 8.4708e-05 | RECORDED |
| amplitude_1p8 | weak | L | 0.0170473 | 0.000127334 | RECORDED |
| amplitude_1p8 | weak | F | 0.0170473 | 6.1375e-05 | RECORDED |
| amplitude_1p8 | weak | TASK_R32 | 0.0170473 | 0.0305479 | RECORDED |
| amplitude_1p8 | ring | L | 0.0178527 | 0.000118833 | RECORDED |
| amplitude_1p8 | ring | F | 0.0178527 | 5.7625e-05 | RECORDED |
| amplitude_1p8 | ring | TASK_R32 | 0.0178527 | 0.00669187 | RECORDED |

准备、online、offline audit的原始phase动作墙钟见[phase_costs.csv](results/a25/report/plot_data/phase_costs.csv)。phase未由上游单列的动作保持原标签；这些exclusive诊断时间不再次加到inclusive CPU/GPU资源费用。

轨迹接受与重试统计来自原始HISTORIES，不从图像改善倒推优化成功：

| 实验 | 方法 | 保存轨迹 | 应有轨迹 | 保存更新 | 接受更新 | 未接受更新 | 发生重试 | 完整12步记录 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| frozen_optimizer_repair | AFFINE_ROM32 | 32 | 32 | 384 | 384 | 0 | 0 | True |
| frozen_optimizer_repair | BORN_TV | 32 | 32 | 384 | 377 | 7 | 7 | True |
| frozen_optimizer_repair | F | 32 | 32 | 384 | 347 | 37 | 37 | True |
| frozen_optimizer_repair | L | 32 | 32 | 384 | 352 | 32 | 34 | True |
| frozen_optimizer_repair | LOCAL_R16 | 32 | 32 | 384 | 349 | 35 | 35 | True |
| frozen_optimizer_repair | R16 | 32 | 32 | 384 | 349 | 35 | 35 | True |
| frozen_optimizer_repair | R24 | 32 | 32 | 384 | 361 | 23 | 24 | True |
| frozen_optimizer_repair | R32 | 32 | 32 | 384 | 353 | 31 | 32 | True |
| frozen_optimizer_repair | TASK_R32 | 32 | 32 | 384 | 348 | 36 | 36 | True |
| tv_multiplier_0p1 | AFFINE_ROM32 | 32 | 32 | 384 | 384 | 0 | 0 | True |
| tv_multiplier_0p1 | BORN_TV | 32 | 32 | 384 | 384 | 0 | 0 | True |
| tv_multiplier_0p1 | F | 32 | 32 | 384 | 384 | 0 | 0 | True |
| tv_multiplier_0p1 | L | 32 | 32 | 384 | 384 | 0 | 0 | True |
| tv_multiplier_0p1 | LOCAL_R16 | 32 | 32 | 384 | 384 | 0 | 0 | True |
| tv_multiplier_0p1 | R16 | 32 | 32 | 384 | 384 | 0 | 0 | True |
| tv_multiplier_0p1 | R24 | 32 | 32 | 384 | 384 | 0 | 0 | True |
| tv_multiplier_0p1 | R32 | 32 | 32 | 384 | 384 | 0 | 0 | True |
| tv_multiplier_0p1 | TASK_R32 | 32 | 32 | 384 | 384 | 0 | 0 | True |
| amplitude_1p8 | F | 16 | 16 | 192 | 192 | 0 | 0 | True |
| amplitude_1p8 | L | 16 | 16 | 192 | 192 | 0 | 0 | True |
| amplitude_1p8 | TASK_R32 | 16 | 16 | 192 | 192 | 0 | 0 | True |
