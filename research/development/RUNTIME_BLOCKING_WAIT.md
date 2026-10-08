# CUDA等待策略的单因素补充

Hypothesis: 默认CUDA调度在同步等待时消耗host CPU；blocking synchronization可以减少无用忙等。
Motivating evidence: batch finite guard后，500更新完整11模型仍预测CPU8432秒，无法容纳；GPU预计8972秒可容纳。
Proposed modification: 在全新进程的primary context初始化前设置blocking wait，仅改变CPU等待方式；不移除任何同步/预算/有限性检查，不改变physics、dtype、core门槛或网络。
Development experiment: 和上一版本相同七拓扑完整known-background health；两次重复，计费包含整个GPU占用和真实process CPU。
Observed result: PENDING at registration.
Decision: PENDING；无法容纳500全矩阵则学习NOT_RUN。
New cost: 独立health job；旧尝试保留。
Validation eligibility: 运行时性能证据，不是成像或学习证据。

[NVIDIA primary-context官方API](https://docs.nvidia.com/cuda/cuda-driver-api/cuda_driver_api/group__CUDA__PRIMARY__CTX.html)说明blocking-sync等待GPU时阻塞CPU线程；数学求解不变。实现从不重置active context，不安装新CUDA或服务。
