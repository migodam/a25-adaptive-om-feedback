# A25 复现入口

读取 [中文研究报告](A25_RESEARCH_REPORT_ZH.md) 和 [最终裁决](A25_FINAL_RESEARCH_DECISION.md)，再运行代码。二维 TM、已知背景、同一全网格材料与联合实虚 TV 是固定条件；这些结果不能替代三维成像证据。

代码与历史 A24 对照在 Git 中。完整逐事件账本及大型材料/轨迹数组在 [A25 Release](https://github.com/migodam/a25-adaptive-om-feedback/releases/tag/a25-v0.1.0)，解压到独立克隆的仓库根目录，保持归档内相对路径。不要覆盖原始实验目录。ID/OOD 标签未公开，未运行的训练/锁定评估不能通过下载被伪造为已完成。

## 环境

原 CPU 科研环境使用 NumPy/SciPy、Clarabel 0.11.1、Matplotlib。Torch 是实坐标导数测试和可选学习入口所需。XINAN 实验复用了既有 Torch 2.6.0+cu124 和 RTX4060；没有安装新的 CUDA 或调度服务。

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-a25.txt
export PYTHONPATH=src
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1
```

## 数值验证与缓存证据

新的复现必须有独立作业 ID。费用账本不允许重置、删除失败记录或复用作业 ID。下列命令写入新的计费记录；历史参考和原结论应另外保留。

```bash
python -m a25.cli tests --job reproduction-tests-001
python tools/a25_report.py --job reproduction-saved-report-001
```

第二条命令只重新整理已有结果和图，不生成新的 Maxwell 标签。若重新运行物理比较，使用新的输出名称，并保证原始缓存已由 Release 恢复：

```bash
python -m a25.cli headroom --job reproduction-headroom-001 --experiment reproduction-original-tv
python -m a25.cli headroom --job reproduction-tv0p1-001 --experiment reproduction-tv0p1 --tv-multiplier 0.1
```

两条轨迹复现共享同一二维后端、数据、初始化规则与优化器。第二条改变共同 TV 权重，必须单独解释。`solver` 入口会生成同目标 SOCP 对照；应在独立工作副本运行，保留下载的原 Phase0 输入和证书。

## 学习与数据隔离

另一个冻结假设检查在 `configs/a25/regime_validation.json` 登记，仅使用16个validation parents的缓存弱背景、幅度1.2观测；其数值入口是 `python tools/a25_regime_validation.py --job <new-job-id>`。该入口默认拒绝覆盖已存在的结果目录，应先在独立复现副本归档下载的原 `results/a25/development/prospective_regime_validation/`。实际配对数据、逐步指标、材料数组和父线程解释均已保存。validation对象已因本检查暴露，不可再次充当未触碰的测试；ID/OOD仍关闭。

`tools/a25_gpu_driver.py` 提供 `health/train/locked` 的付费入口。当前费用预检查不允许完整最低训练矩阵启动，所以科学训练、样本效率、层数/OOD 和推理优越性为 NOT_RUN。训练入口不会自动打开测试；锁定入口要求 11 个完成并冻结的配对模型。执行 GPU 作业前须使用现有环境和共享锁，不可通过降低精度、删除对照或放宽证书规避预算。

`tools/a25_remote.py` 接收外部、忽略的连接配置。仓库不包含 SSH 私钥、登录配置或 token，公开下载也不需要这些凭据。`data/train.npz` 与 `data/validation.npz` 是 offline 监督输入；`data/background/` 只包含已知背景及合法固定探针因子。监督材料/电流不能传给 online 物理构建器。

所有阶段命令和环境记录以 Release 的逐作业元数据为准。父级 inclusive 时间与子事件 exclusive 时间不相加；物理动作计数不能替代真实 time-to-image。
