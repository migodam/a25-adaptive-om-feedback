"""Saved-evidence Chinese reports and standalone figures, under a parent book.

This module performs no forward solve, training, test opening or gate decision.
Parent A25_GATE_DECISION.json supplies every scientific verdict.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import csv
import json
import math
from pathlib import Path
import re
import time
import numpy as np

from .budget import budget_history, plain, write_json

DOCUMENTS = (
    "A25_START_HERE.md", "SOLVER_REPAIR_REPORT.md", "FEEDBACK_HEADROOM.md",
    "CONVERGENCE_VS_RUNTIME.md", "FEEDBACK_COMPRESSION_EXPLORATION.md",
    "FEEDBACK_REGIME_MAP.md", "SOMNET_MIGRATION_PILOT.md", "EXPLORATION_LEDGER.md",
    "LOCKED_VALIDATION.md", "A25_FINAL_RESEARCH_DECISION.md")
SOURCES = ("[A24 研究报告](https://github.com/migodam/a24-source-anchored-om-feedback/blob/main/A24_RESEARCH_REPORT_ZH.md)，"
           "[SOM-Net 原论文](https://arxiv.org/abs/2209.03567)，"
           "[A24 文献读取范围](theory/SOURCES_AND_READING_LEDGER.md)。")


class Sanitizer:
    """Numerical values stay unchanged; private diagnostics never propagate."""
    def __init__(self, root):
        self.root = str(Path(root).resolve())
        self.redactions = Counter()

    def __call__(self, value):
        if isinstance(value, dict):
            output = {}
            for key, item in value.items():
                if re.search(r"token|password|credential|secret|ssh_target|ssh_key|private_config|argv|stderr|stdout|command", str(key), re.I):
                    self.redactions["sensitive_field"] += 1
                    output[str(key)] = "[REDACTED]"
                else:
                    output[str(key)] = self(item)
            return output
        if isinstance(value, (list, tuple)):
            return [self(x) for x in value]
        if isinstance(value, str):
            original = value
            value = value.replace(self.root, "<PROJECT_ROOT>")
            value = re.sub(r"(?:/Users/|/Volumes/|/home/|/private/|/tmp/|/var/)[^\s\"'<>]*", "<LOCAL_PATH>", value)
            value = re.sub(r"\b[A-Za-z]:[\\/][^\s\"'<>]*", "<HOST_PATH>", value)
            value = re.sub(r"\b[A-Za-z0-9_.-]+@(?:[A-Za-z0-9_.-]+)", "<PRIVATE_ENDPOINT>", value)
            value = re.sub(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "<PRIVATE_ENDPOINT>", value)
            value = re.sub(r"\b(?:sk-|ghp_|github_pat_|AKIA)[A-Za-z0-9_-]{12,}", "<REDACTED_TOKEN>", value)
            if value != original:
                self.redactions["path_or_credential_text"] += 1
            return value
        return plain(value)


def _json(path, default=None):
    path = Path(path)
    if not path.exists():
        return {"status": "NOT_RUN", "source_missing": path.name} if default is None else default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"status": "UNREADABLE_SAVED_ARTIFACT", "source": path.name}


def _csv(path):
    path = Path(path)
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _num(row, key):
    try:
        value = float(row.get(key))
        return value if math.isfinite(value) else None
    except (TypeError, ValueError):
        return None


def _fmt(value):
    if value is None or value == "":
        return "未记录 / 未定义"
    if isinstance(value, float):
        return f"{value:.6g}" if math.isfinite(value) else "未定义"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value).replace("|", "\\|").replace("\n", " ")


def _table(rows, columns):
    if not rows:
        return "NOT_RUN：没有对应的已保存原始记录。\n"
    output = ["| " + " | ".join(label for key, label in columns) + " |",
              "| " + " | ".join("---" for _ in columns) + " |"]
    output.extend("| " + " | ".join(_fmt(row.get(key)) for key, label in columns) + " |" for row in rows)
    return "\n".join(output) + "\n"


def _write_csv(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    keys = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(plain(value), ensure_ascii=False) if isinstance(value, (dict, list)) else value
                             for key, value in row.items()})


def _failure_key(payload):
    payload = dict(payload)
    for key in ("sources", "record_id", "source_job", "source_line", "source_file", "owner_id"):
        payload.pop(key, None)
    if payload.get("event") == "failure":
        payload.pop("event")
        payload.pop("job", None)
    return json.dumps(plain(payload), sort_keys=True, allow_nan=False, separators=(",", ":"))


def merge_accounting(root, book, *, sanitizer=None):
    """Stream accepted action ledgers; totals come only from immutable receipts."""
    root = Path(root)
    sanitizer = sanitizer or Sanitizer(root)
    history = budget_history(root)
    accepted = {row["job"]: row for row in history["receipts"]}
    failures, counts, walls, phase_walls = {}, Counter(), Counter(), Counter()
    job_rows, action_records = [], 0
    cost_path = root / "COST_LEDGER.jsonl"
    temporary = cost_path.with_name(cost_path.name + ".report-tmp")

    def keep_failure(payload, source):
        clean = sanitizer(payload.get("payload", payload))
        key = _failure_key(clean)
        if key not in failures:
            failures[key] = {"record_id": len(failures) + 1, "payload": clean, "sources": []}
        sources = payload.get("sources", []) + [source]
        for item in sources:
            if item not in failures[key]["sources"]:
                failures[key]["sources"].append(item)

    # Read the prior root ledger before replacing it; wrapped records are
    # normalized so report retries do not recursively duplicate failures.
    root_failure = root / "FAILURE_LEDGER.jsonl"
    if root_failure.exists():
        with root_failure.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                try:
                    keep_failure(json.loads(line), {"file": "FAILURE_LEDGER.jsonl", "line": line_number})
                except ValueError:
                    keep_failure({"status": "UNREADABLE_FAILURE_RECORD", "line": line_number},
                                 {"file": "FAILURE_LEDGER.jsonl", "line": line_number})
    def visit_failures(value, source, location="$", parent_failed=False):
        if isinstance(value, dict):
            failed = value.get("status") in {"FAILED", "BUDGET_STOP", "INTERRUPTED", "INITIALIZATION_FAILED"}
            if failed and not parent_failed:
                keep_failure(value, {"file": source, "json_location": location})
            for key, item in value.items():
                visit_failures(item, source, location + "." + str(key), parent_failed or failed)
        elif isinstance(value, list):
            for index, item in enumerate(value):
                visit_failures(item, source, location + f"[{index}]", parent_failed)
    failure_json = {p for p in (root / "results/a25").rglob("*.json")
                    if "fail" in p.name.lower() and "report" not in p.relative_to(root).parts}
    failure_json.update(p for p in (root/"results/a25/learning/TRAINED_MODELS.json",
                                   root/"results/a25/dataset/GENERATION.json") if p.exists())
    for path in sorted(failure_json):
        visit_failures(_json(path),path.relative_to(root).as_posix())
    for path in (root/"results/a25/development/frozen_optimizer_repair/METRICS.csv",
                 root/"results/a25/learning/locked_evaluation/cases.csv"):
        for index,row in enumerate(_csv(path),2):
            if row.get("status") not in {"OK",None,""}:
                keep_failure(row,{"file":path.relative_to(root).as_posix(),"line":index})
    with temporary.open("w", encoding="utf-8") as output:
        for job, receipt in sorted(accepted.items()):
            book.check()
            directory = root / "results/a25/jobs" / job
            path = directory / "COST_LEDGER.jsonl"
            if path.exists():
                with path.open(encoding="utf-8") as source:
                    for line_number, line in enumerate(source, 1):
                        if line_number % 1000 == 0:
                            book.check()
                        try:
                            row = json.loads(line)
                        except ValueError:
                            row = {"event": "UNREADABLE_ACTION_RECORD", "status": "FAILED"}
                        safe = sanitizer(row)
                        output.write(json.dumps({"record_type": "ACTION", "source_job": job,
                            "source_line": line_number, "payload": safe}, ensure_ascii=False, allow_nan=False) + "\n")
                        action_records += 1
                        exclusive = _num(row,"exclusive_wall_seconds")
                        if exclusive is not None:
                            phase_walls[str(row.get("phase","UNDECLARED"))] += exclusive
                        if row.get("event") == "failure" or row.get("status") in {"FAILED", "BUDGET_STOP", "INTERRUPTED"}:
                            keep_failure(row, {"file": f"results/a25/jobs/{job}/COST_LEDGER.jsonl", "line": line_number})
            output.write(json.dumps({"record_type": "ACCEPTED_JOB_RECEIPT", "source_job": job,
                                     "payload": sanitizer(receipt)}, ensure_ascii=False, allow_nan=False) + "\n")
            counts.update(receipt.get("counts", {}))
            walls.update(receipt.get("exclusive_walls", {}))
            job_rows.append(sanitizer({key: receipt.get(key) for key in ("job", "stage", "status", "device",
                "wall_seconds", "process_cpu_seconds", "charged_cpu_seconds", "gpu_occupation_seconds",
                "gpu_host_only", "raw_monitor_wall_seconds", "measurement_role", "durable_reservations")}))
            if receipt["status"] in {"FAILED", "BUDGET_STOP", "INTERRUPTED"}:
                keep_failure({"kind": "JOB_TERMINAL_FAILURE", "job": job, "status": receipt["status"],
                              "error": receipt.get("error")}, {"file": f"results/a25/jobs/{job}/job_receipt.json"})
    temporary.replace(cost_path)
    failure_path = root / "FAILURE_LEDGER.jsonl"
    temp = failure_path.with_name(failure_path.name + ".report-tmp")
    with temp.open("w", encoding="utf-8") as output:
        for row in failures.values():
            output.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
    temp.replace(failure_path)
    current = str(book.metadata.get("job", ""))
    unresolved = [j for j in history["unresolved_jobs"] if j != current]
    summary = {"accepted_cpu_seconds": history["cpu_seconds"], "accepted_gpu_seconds": history["gpu_seconds"],
               "accepted_jobs": sorted(accepted), "action_records": action_records, "failure_records": len(failures),
               "reservations": history["reservations"], "counts": dict(counts), "exclusive_walls": dict(walls),
               "declared_phase_exclusive_walls":dict(phase_walls),
               "phase_cost_caveat":"declared phase diagnostic wall; never summed as CPU/GPU resource charge",
               "unresolved_prior_jobs": unresolved, "report_job_live_snapshot": sanitizer(book.receipt()),
               "cutoff": "accepted receipts at report generation; live report tail is provisional",
               "cpu_rule": "CPU-only max(wall,processCPU); CUDA host processCPU",
               "gpu_rule": "remote occupied wall; local CUDA monitor GPUoccupation zero"}
    write_json(root / "results/a25/report/COST_SUMMARY.json", summary)
    _write_csv(root / "results/a25/report/plot_data/job_costs.csv", job_rows)
    _write_csv(root / "results/a25/report/plot_data/phase_costs.csv",
               [{"declared_phase":phase,"exclusive_action_wall_seconds":wall} for phase,wall in sorted(phase_walls.items())])
    _write_csv(root / "results/a25/report/plot_data/failures.csv", list(failures.values()))
    return summary, job_rows


def _parent_means(rows, metric, *, parents, variants=8):
    groups = defaultdict(list)
    for row in rows:
        try:
            groups[int(row["parent_id"])].append(row)
        except (KeyError, TypeError, ValueError):
            return None
    values = []
    for parent in parents:
        items = groups.get(int(parent), [])
        if len(items) != variants or any(r.get("status") != "OK" or _num(r, metric) is None for r in items):
            return None
        values.append(float(np.mean([_num(r, metric) for r in items])))
    return float(np.mean(values)) if values else None


def _development_summary(rows, config):
    summary = []
    parents = config.get("parents", [2401, 2402, 2403, 2404])
    for method in sorted({r.get("method", "") for r in rows}):
        for k in (3, 6, 12):
            subset = [r for r in rows if r.get("method") == method and _num(r, "K") == k]
            row = {"method": method, "K": k, "observed_rows": len(subset),
                   "ok_rows": sum(r.get("status") == "OK" for r in subset),
                   "expected_rows": 32, "quality_hits": sum(str(r.get("quality_target_hit")) == "True" for r in subset)}
            for metric in ("delta_nrmse", "material_nrmse", "edge_nrmse", "support_iou", "online_s",
                           "shared_setup_s", "method_setup_s"):
                row[metric] = _parent_means(subset, metric, parents=parents)
            row["complete"] = row["delta_nrmse"] is not None
            row["independent_cold_s"] = (sum(row[m] for m in ("online_s", "shared_setup_s", "method_setup_s"))
                                         if all(row[m] is not None for m in ("online_s", "shared_setup_s", "method_setup_s")) else None)
            summary.append(row)
    return summary


def _verdict(decision, key):
    value = decision.get(key, {"status": "NOT_REVIEWED"})
    return value if isinstance(value, dict) else {"status": value}


def _figure(root, filename, caption, function, book, manifest):
    path = Path(root) / "results/a25/report/figures" / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    with book.span("saved_evidence_figure", report_figure_attempts=1):
        result = function()
        if result is None:
            manifest[filename] = {"status": "NOT_RUN", "reason": "no complete saved evidence", "caption": caption}
            return
        result.savefig(path, dpi=220, bbox_inches="tight")
        result.savefig(path.with_suffix(".pdf"), bbox_inches="tight")
        book.counts["report_figures_generated"] += 1
        from matplotlib import pyplot as plt
        plt.close(result)
        manifest[filename] = {"status": "GENERATED", "path": path.relative_to(root).as_posix(),
                              "pdf": path.with_suffix(".pdf").relative_to(root).as_posix(), "caption": caption}


def generate_figures(root, evidence, config, book):
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib import pyplot as plt
    from matplotlib import font_manager
    available = {font.name for font in font_manager.fontManager.ttflist}
    font = next((f for f in ("Arial Unicode MS", "PingFang SC", "Microsoft YaHei", "Noto Sans CJK SC") if f in available), "DejaVu Sans")
    plt.rcParams.update({"font.family": font, "axes.unicode_minus": False, "axes.grid": True,
                         "grid.alpha": .2, "figure.dpi": 120})
    root = Path(root)
    manifest = {}
    dev = evidence["development_rows"]
    summary = evidence["development_summary"]

    def solver_figure():
        rows = evidence["solver_rows"]
        if not rows:
            return None
        methods = sorted({r.get("algorithm", "") for r in rows})
        fig, axes = plt.subplots(1, 2, figsize=(11, 4))
        for index, method in enumerate(methods):
            chosen = [r for r in rows if r.get("algorithm") == method]
            for key, axis in (("kkt_residual", axes[0]), ("normalized_gap", axes[1])):
                values = [_num(r, key) for r in chosen if _num(r, key) is not None and _num(r, key) > 0]
                if values:
                    axis.scatter([index]*len(values), values, s=18, alpha=.6)
        for ax in axes:
            ax.set_yscale("log");ax.axhline(1e-6, color="black", ls="--", lw=1)
            ax.set_xticks(range(len(methods)), methods, rotation=20);ax.set_ylabel("raw certificate residual")
        axes[0].set_title("KKT certificate");axes[1].set_title("normalized primal-dual gap")
        fig.suptitle("Phase 0: identical objective, external tolerance unchanged")
        return fig
    _figure(root, "solver_certificates.png", "同目标 prox 的原始外部证书；不是完整逆散射成像性能。", solver_figure, book, manifest)

    def convergence():
        if not dev:
            return None
        fig, ax = plt.subplots(figsize=(9, 5));drawn = False
        parents = config.get("parents", [2401,2402,2403,2404])
        for method in sorted({r.get("method") for r in dev}):
            points = []
            for k in range(1, 13):
                rows = [r for r in dev if r.get("method") == method and _num(r, "K") == k]
                error = _parent_means(rows, "delta_nrmse", parents=parents)
                seconds = _parent_means(rows, "online_s", parents=parents)
                if error is not None and seconds is not None:
                    points.append((seconds, error, k))
            if points:
                ax.plot([p[0] for p in points], [p[1] for p in points], marker=".", label=method);drawn=True
        if not drawn:
            plt.close(fig);return None
        ax.set_xlabel("shared initialization + online trajectory (s)");ax.set_ylabel("equal-parent delta NRMSE")
        ax.set_title("Development convergence: complete 32-condition pairs only");ax.legend(fontsize=8)
        return fig
    _figure(root, "convergence_runtime.png", "四个已公开开发 parent；每个点要求32条件齐全，缺失不作成功条件均值。", convergence, book, manifest)

    def pareto():
        chosen = [r for r in summary if r["complete"] and r["independent_cold_s"] is not None]
        if not chosen:
            return None
        fig, ax = plt.subplots(figsize=(9, 5))
        for method in sorted({r["method"] for r in chosen}):
            rows = [r for r in chosen if r["method"] == method]
            ax.scatter([r["independent_cold_s"] for r in rows], [r["delta_nrmse"] for r in rows], label=method)
            for r in rows:ax.annotate(f"K{r['K']}",(r["independent_cold_s"],r["delta_nrmse"]),fontsize=7)
        ax.set_xlabel("independent preparation + initialization + online (s)")
        ax.set_ylabel("equal-parent delta NRMSE");ax.legend(fontsize=8)
        ax.set_title("Equal-K quality-time points; audit cost separate")
        return fig
    _figure(root, "quality_time_pareto.png", "相同 K 的质量—时间点；尚未共同命中质量目标时不能宣称部署提速。", pareto, book, manifest)

    def ranks():
        rows = evidence["task_rows"]
        methods = [m for m in ("R16","R24","R32","LOCAL_R16","TASK_R32") if any(r.get("method") == m for r in rows)]
        if not methods:
            return None
        fig, axes = plt.subplots(1, 3, figsize=(14, 4))
        for index, method in enumerate(methods):
            selected = [r for r in rows if r.get("method") == method and r.get("status") == "OK"]
            for key, ax in zip(("independent_transfer_error","independent_adjoint_error","gradient_cosine"), axes):
                values = [v for r in selected if (v := _num(r,key)) is not None]
                ax.scatter([index]*len(values),values,s=15,alpha=.55)
        for ax, title, threshold in zip(axes,("forward task error","adjoint task error","gradient cosine"),(.05,.05,.99)):
            ax.axhline(threshold,color="black",ls="--",lw=1);ax.set_title(title)
            ax.set_xticks(range(len(methods)),methods,rotation=30)
        fig.suptitle("Observed development task probes; all failures retained in raw table")
        return fig
    _figure(root, "rank_task_error.png", "固定候选的独立任务探针；只画有限的实际值，失败留在原始表中。", ranks, book, manifest)

    def images():
        directory = evidence["development_path"] / "images"
        cases = ("weak_2401_1.2_snr20","ring_2401_1.2_snr20","ring_2403_1.2_snr20")
        methods = ("L","F","R16","R24","R32")
        if not any((directory/f"{c}_{m}_K12.npz").exists() for c in cases for m in methods):
            return None
        fig, axes = plt.subplots(len(cases),len(methods)+1,figsize=(16,8))
        for row, case in enumerate(cases):
            truth_drawn=False
            for col,method in enumerate(methods,1):
                ax=axes[row,col];path=directory/f"{case}_{method}_K12.npz"
                if not path.exists():ax.text(.5,.5,"NOT_RUN",ha="center",va="center");ax.set_axis_off();continue
                with np.load(path,allow_pickle=False) as archive:
                    chi,truth,bg=(archive[key].copy() for key in ("chi","truth","background"))
                grid=int(round(np.sqrt(len(chi))))
                limit=float(np.max(abs((truth-bg).real)))
                if limit==0:limit=1.
                ax.imshow((chi-bg).real.reshape(grid,grid),origin="lower",vmin=-.1*limit,vmax=limit,cmap="viridis")
                ax.set_title(method);ax.set_axis_off()
                if not truth_drawn:
                    axes[row,0].imshow((truth-bg).real.reshape(grid,grid),origin="lower",vmin=-.1*limit,vmax=limit,cmap="viridis")
                    axes[row,0].set_title(case+"\ntruth delta Re");axes[row,0].set_axis_off();truth_drawn=True
            if not truth_drawn:axes[row,0].text(.5,.5,"NOT_RUN",ha="center");axes[row,0].set_axis_off()
        fig.suptitle("Fixed exposed development examples, K12; identical per-case color scale")
        return fig
    _figure(root, "development_images.png", "预先固定开发样例的增量实部；相同场景共用色标，缺失面板明确标记。", images, book, manifest)

    locked=evidence["locked_rows"]
    def learning_summary_figure(mode):
        if not locked or not evidence["locked_open"]:
            return None
        points=[]
        models=sorted({r.get("model_id",r.get("model","")) for r in locked})
        for model in models:
            match=re.fullmatch(r"(N[0-3])_train(32|64)_b([34])",model)
            if not match:continue
            for split in ("locked_id","locked_ood"):
                selected=[r for r in locked if r.get("model_id",r.get("model"))==model and r.get("split")==split]
                parents=sorted({int(r["parent_id"]) for r in selected})
                mean=_parent_means(selected,"delta_nrmse",parents=parents) if len(parents)==16 else None
                if mean is not None:points.append(dict(model=model,method=match[1],train=int(match[2]),blocks=int(match[3]),split=split,error=mean))
        if not points:return None
        fig,ax=plt.subplots(figsize=(10,5))
        if mode=="sample":
            for method in ("N0","N1","N2","N3"):
                b=4 if method=="N0" else 3
                selected=sorted([p for p in points if p["method"]==method and p["blocks"]==b and p["split"]=="locked_id"],key=lambda p:p["train"])
                if selected:ax.plot([p["train"] for p in selected],[p["error"] for p in selected],marker="o",label=method)
            ax.set_xlabel("independent training parents");ax.set_xticks([32,64]);ax.set_title("Locked ID sample efficiency; fixed depth per arm")
        else:
            selected=[p for p in points if (p["split"]=="locked_ood" if mode=="ood" else p["train"]==64 and p["split"]=="locked_id")]
            if not selected:plt.close(fig);return None
            labels=[p["model"] for p in selected]
            ax.bar(range(len(selected)),[p["error"] for p in selected])
            ax.set_xticks(range(len(selected)),labels,rotation=40,ha="right")
            ax.set_title("Locked OOD: structural + contrast" if mode=="ood" else "Matched decoder/depth ablation: locked ID")
        ax.set_ylabel("equal-parent delta NRMSE");ax.legend(fontsize=8) if mode=="sample" else None
        return fig
    for name,mode,caption in (("nn_sample_efficiency.png","sample","32/64独立训练 parent；只使用一次 locked ID 的完整记录。"),
                             ("ood_quality.png","ood","结构组合与额外对比度组成的 OOD；不是开发对象重新命名。"),
                             ("matched_ablation.png","ablation","匹配 decoder、数据、训练更新及层数的实际 locked 指标。")):
        _figure(root,name,caption,lambda mode=mode:learning_summary_figure(mode),book,manifest)

    def locked_images():
        if not evidence["locked_open"]:
            return None
        directory=root/"results/a25/learning/locked_evaluation/images"
        models=("N0_train64_b4","N1_train64_b3","N2_train64_b3","N3_train64_b3")
        splits=("locked_id","locked_ood")
        if not any((directory/f"{model}_{split}.npz").exists() for model in models for split in splits):
            return None
        fig,axes=plt.subplots(2,5,figsize=(14,6))
        for row,split in enumerate(splits):
            truth_drawn=False;case=None
            for column,model in enumerate(models,1):
                ax=axes[row,column];path=directory/f"{model}_{split}.npz"
                if not path.exists():ax.text(.5,.5,"NOT_RUN",ha="center");ax.set_axis_off();continue
                with np.load(path,allow_pickle=False) as archive:
                    ids=np.asarray(archive["case_id"]).astype(str)
                    if case is None:case=sorted(ids)[0]
                    matching=np.flatnonzero(ids==case)
                    if len(matching)!=1:ax.text(.5,.5,"MISSING_CASE",ha="center");ax.set_axis_off();continue
                    index=int(matching[0])
                    if "status" in archive and str(archive["status"][index])!="OK":
                        ax.text(.5,.5,"FAILED",ha="center");ax.set_axis_off();continue
                    chi,truth,bg=(archive[key][index].copy() for key in ("chi","truth","chi_b"))
                grid=int(round(np.sqrt(len(chi))));limit=float(np.max(abs((truth-bg).real)))
                if limit==0:limit=1.
                ax.imshow((chi-bg).real.reshape(grid,grid),origin="lower",vmin=-.1*limit,vmax=limit,cmap="viridis")
                ax.set_title(model);ax.set_axis_off()
                if not truth_drawn:
                    axes[row,0].imshow((truth-bg).real.reshape(grid,grid),origin="lower",vmin=-.1*limit,vmax=limit,cmap="viridis")
                    axes[row,0].set_title(split+"\n"+case);axes[row,0].set_axis_off();truth_drawn=True
            if not truth_drawn:axes[row,0].text(.5,.5,"NOT_RUN / FAILED",ha="center");axes[row,0].set_axis_off()
        fig.suptitle("Locked images: lexicographically first saved case; no success selection")
        return fig
    _figure(root,"locked_images.png","一次开启后保存的固定首个ID/OOD场景；失败不替换为另一成功场景。",locked_images,book,manifest)
    write_json(root/"results/a25/report/FIGURE_MANIFEST.json",manifest)
    return manifest


def _gather(root, config):
    root=Path(root);development=root/"results/a25/development/frozen_optimizer_repair"
    locked=root/"results/a25/learning/locked_evaluation"
    rows=_csv(development/"METRICS.csv")
    return {"phase0":_json(root/"results/a25/development/phase0/DECISION.json"),
        "phase0_initial":_json(root/"results/a25/development/phase0/DECISION_INITIAL.json"),
        "solver_rows":_csv(root/"results/a25/development/phase0/SOLVER_COMPARISON.csv"),
        "references":_json(root/"results/a25/development/phase0/INDEPENDENT_REFERENCE.json",[]),
        "refinement":_json(root/"results/a25/development/phase0/REFERENCE_REFINEMENT_001.json"),
        "development_path":development,"development_rows":rows,
        "preparations":_json(development/"PREPARATIONS.json",[]),
        "development_summary":_development_summary(rows,config),"task_rows":_csv(development/"TASK_AUDIT.csv"),
        "admission":_json(development/"NN_CLOSURE_ADMISSION.json"),
        "health":_json(root/"results/a25/learning/GPU_HEALTH.json"),
        "updates":_json(root/"results/a25/learning/COST_SELECTED_UPDATES.json"),
        "models":_json(root/"results/a25/learning/TRAINED_MODELS.json",[]),
        "freeze":_json(root/"results/a25/learning/MODEL_FREEZE.json"),
        "locked_open":(root/"results/a25/learning/LOCKED_OPEN.json").exists(),
        "locked_summary":_json(locked/"summary.json"),"locked_rows":_csv(locked/"cases.csv"),
        "timing":_csv(locked/"timing.csv"),"paired":_json(locked/"paired_bootstrap.json"),
        "parent_summary":_json(locked/"parent_summary.json")}


def _explorations(root):
    rows=[]
    for path in (Path(root)/"results/a25/EXPLORATION_LEDGER.jsonl",Path(root)/"results/a25/development/EXPLORATION_LEDGER.jsonl"):
        if path.exists():
            with path.open(encoding="utf-8") as handle:
                for line in handle:
                    try:rows.append(json.loads(line))
                    except ValueError:rows.append({"status":"UNREADABLE_EXPLORATION_RECORD"})
    return rows


def _sections(evidence, decision, costs, config, figures, sanitizer):
    phase=evidence["phase0"];admission=evidence["admission"]
    solver_table=_table([dict(algorithm=k,**v) for k,v in phase.get("solvers",{}).items()],
        (("algorithm","算法"),("certified","证书通过"),("required","同目标问题数"),("sum_prox_wall_s","prox wall秒")))
    references=evidence["references"] if isinstance(evidence["references"],list) else []
    reference_table=_table(references,(("case_id","对象/优化器控制"),("solver_status","Clarabel原始status"),
        ("strict_external_reference_certificate_passed","严格外部证书"),("acceptance_reason","验收原因"),
        ("kkt_residual","KKT"),("normalized_gap","normalized gap"),("comparison_agrees","同目标对照")))
    dev_table=_table(evidence["development_summary"],(("method","方法"),("K","K"),("ok_rows","OK/32"),
        ("complete","完整parent配对"),("delta_nrmse","增量NRMSE"),("material_nrmse","完整χ NRMSE"),
        ("online_s","初始化+online秒"),("independent_cold_s","独立准备+online秒"),("quality_hits","质量命中/32")))
    candidate_table=_table(admission.get("candidates",[]),(("method","候选"),("complete","完整配对"),
        ("max_transfer_error","forward任务误差"),("max_adjoint_error","adjoint任务误差"),
        ("min_gradient_cosine","梯度cosine"),("max_delta_image_ratio_vs_F","最大成像比值/F"),
        ("eligible_physics","开发域准入")))
    verdicts=[{"question":k,**sanitizer(_verdict(decision,k))} for k in
        ("solver_health","feedback_imaging","compression","learning","sample_efficiency","depth","deployment")]
    verdict_table=_table(verdicts,(("question","独立问题"),("status","父线程裁决"),("scope","证据范围"),("limitations","限制")))
    models=evidence["models"] if isinstance(evidence["models"],list) else []
    model_rows=[]
    for model in models:
        row=dict(model)
        size=len(row.get("train_parents",[])) or row.get("train_size")
        row["train_size"]=size
        row["planned_updates"]=row.get("updates")
        if not row.get("model_id") and size and row.get("method") and row.get("blocks"):
            row["model_id"]=f"{row['method']}_train{size}_b{row['blocks']}"
        model_rows.append(row)
    model_table=_table(sanitizer(model_rows),(("model_id","模型"),("status","原始status"),("method","结构"),
        ("train_size","parent数"),("blocks","层数"),("parameter_count","参数数"),
        ("completed_updates","实际完成更新"),("planned_updates","计划更新")))
    figure_links="\n".join(f"- [{name}]({row['path']})：{row['caption']}" if row["status"]=="GENERATED"
                           else f"- {name}：NOT_RUN，{row['reason']}。" for name,row in figures.items())
    budget_text=(f"已接受作业 CPU计费 {_fmt(costs['accepted_cpu_seconds'])} 秒 /7200秒；GPU占用 "
                 f"{_fmt(costs['accepted_gpu_seconds'])} 秒 /14400秒。报告自身仍在运行的尾部单独记为 provisional；"
                 "完整截止作业清单见 report/COST_SUMMARY.json，最终资源以不可变 job_receipt.json 为准。")
    background=("从最开始最基础的 literature review 和 background，逆散射要从有限接收数据恢复空间材料。"
        "每个照明源激发的电流受同一材料控制，电流又通过内部传播改变局部场。已知强背景会重塑这条反馈链。"
        "材料图准确、满足完整波动方程、以及获得部署速度，是三个需要各自证据的问题。\n\n"
        "A25保持24×24二维TM、8个源和32个接收点。材料是576个复数单元，真实材料坐标1152维；"
        "每个场景有512个实数观测。所有方法使用同一全网格材料、box约束和TV先验。"
        "二维证据不扩展为三维vector-Maxwell结论。" )
    theory=("已知背景产生参考场 e_b。材料变化 h 首先产生 h e_b 的强迫，再由内部反馈反复传播。"
        "L只保留背景线性响应；F在当前材料处重算完整反馈；R以固定已知背景构造的因子近似回传。"
        "简写为 w=(I-diag(h)G_b)^{-1}diag(h)e_b、y=y_b+D_bw。"
        "这些表达式说明每个源共享同一材料，不能把单源current拟合自动视为合法完整材料图。"
        "source anchor处forcing-P消失属于特定代数恒等式，保留下来的反馈耦合及其任务误差仍需要检验。")
    common=("原始记录、失败和未运行项是报告的一部分。历史四parent2401–2404是公开development对象；"
        "它们不提供新场景盲测。训练/validation与一次locked ID/OOD各自标注，"
        "理论表达、数值认证、成像结果、学习收益和部署结论分别裁决。\n\n"+SOURCES)
    sections={}
    sections["A25_START_HERE.md"]=("# A25：从物理问题到可复核证据\n\n"+background+"\n\n"+verdict_table+
        "\n主报告见 [A25_RESEARCH_REPORT_ZH.md](A25_RESEARCH_REPORT_ZH.md)。最先读取求解器证书、成像配对和独立压缩任务误差，再读取学习及部署报告。\n\n"+common)
    sections["SOLVER_REPAIR_REPORT.md"]=("# 同目标TV求解器修复与独立证书\n\n"
        "求解器未完成一个受约束凸子问题时，下一幅图像的差异混合了物理模型与优化误差。"
        "先认证相同目标，才能讨论完整反馈是否有成像收益。这里的证书针对TV prox，不等于完整逆散射已恢复正确材料。\n\n"
        f"已保存 phase0 状态：{phase.get('status','NOT_RUN')}；选择算法：{phase.get('solver','NOT_RUN')}。\n\n"+
        solver_table+"\n"+reference_table+
        "\n外部 normalized gap/KKT目标保持1e-6，box feasibility保持1e-10；加速算法仍按固定原始参考步长验收。"
        "Clarabel原始 solver_status 单列保留，AlmostSolved 不改写成 Solved。独立参考内部精度收紧"
        "属于同目标 numerical refinement，未降低外部容差。原始失败、DECISION_INITIAL及REFERENCE_REFINEMENT_001同时保留。"
        "严格独立参考证书、虚拟可行包络和原始primal/dual输出各自保留；浮点包络不表述为区间严格证明。\n\n"
        "原始来源：[SOLVER_COMPARISON.csv](results/a25/development/phase0/SOLVER_COMPARISON.csv)、"
        "[INDEPENDENT_REFERENCE.json](results/a25/development/phase0/INDEPENDENT_REFERENCE.json)、"
        "[refinement](results/a25/development/phase0/REFERENCE_REFINEMENT_001.json)。")
    sections["FEEDBACK_HEADROOM.md"]=("# 完整反馈的成像余量\n\n"+theory+"\n\n"
        "在已公开开发对象上，L/F/R固定材料先验、共同初始化和K=3/6/12。"
        "完整χ误差可能被大背景掩盖，因此同时报告增量、实虚部、边缘、支撑IoU及完整场残差。"
        "相同观测下某个方法失败时保留其位置，不把成功图单独拼成配对。\n\n"+dev_table+
        f"\n成像裁决来自父线程：{_fmt(_verdict(decision,'feedback_imaging'))}。\n\n"
        "原始来源：[METRICS.csv](results/a25/development/frozen_optimizer_repair/METRICS.csv)；"
        "图像是固定开发样例，不能当作新的ID/OOD泛化。")
    sections["CONVERGENCE_VS_RUNTIME.md"]=("# 收敛、相同K与完整推理时间\n\n"
        "一个更准的单次反馈动作不保证更快得到合格材料。比较先固定K，再观察达到共同质量目标所需的完整时间。"
        "online_s包含共同初始化和在线迭代；独立冷成本再加入一次已知背景准备与方法准备。"
        "离线完整场质量审核另列，不混入普通部署推理。共享试验真正只付一次的准备成本与单方法独立成本同时报告。\n\n"+
        dev_table+"\n没有共同命中质量区域时，质量—时间散点只作描述。GPU缓存训练初始化"
        "不能作为部署已经免除初始化；完整cold/warm计时要实际加载缓存、重置状态、重算或单列初始化时间。\n\n"+
        _table(evidence['timing'],(("model_id","模型"),("mode","计时模式"),("status","原始status"),
            ("complete_image_seconds","完整秒"),("complete_image_cpu_seconds","完整host CPU秒"),
            ("certified_initialization_seconds","初始化秒"),
            ("file_read_and_model_cache_setup_seconds","读取与模型缓存准备秒"),
            ("image_only_seconds","仅网络图像秒"),("offline_audit_seconds","审计秒")))+
        f"\n部署裁决：{_fmt(_verdict(decision,'deployment'))}。")
    preparations=[]
    for background in evidence.get("preparations",[]):
        if not isinstance(background,dict):continue
        for method,record in background.get("methods",{}).items():
            preparations.append({"background":background.get("background"),"method":method,
                                 "shared_s":background.get("shared_s"),"method_s":record.get("wall_s"),
                                 "status":record.get("status","RECORDED")})
    sections["CONVERGENCE_VS_RUNTIME.md"]+=("\n\n已知背景准备成本：\n\n"+
        _table(preparations,(("background","背景"),("method","方法"),("shared_s","共享准备秒"),
                             ("method_s","方法准备秒"),("status","原始状态")))+
        "\n准备、online、offline audit的原始phase动作墙钟见[phase_costs.csv](results/a25/report/plot_data/phase_costs.csv)。"
        "phase未由上游单列的动作保持原标签；这些exclusive诊断时间不再次加到inclusive CPU/GPU资源费用。")
    sections["FEEDBACK_COMPRESSION_EXPLORATION.md"]=("# 压缩反馈准入与固定候选\n\n"
        "压缩的目的在于保留材料扰动到观测的合法传递。单看G_b的谱误差不足以知道图像会否丢失重要方向，"
        "需要独立forward、精确adjoint任务探针、梯度方向与同先验成像配对。R16/R24/R32、local和task-weighted是不同候选。\n\n"+
        candidate_table+f"\n开发准入原始状态：{admission.get('status','NOT_RUN')}；选择：{admission.get('selected','NOT_RUN')}。\n\n"
        "开发域通过仍需Torch健康检查与独立新场景验证；只有父线程裁决决定进入学习的候选范围。"
        "探针构造使用已知背景，未知truth不进入因子构建；失败不因rank增加而抹去。\n\n"
        "原始来源：[TASK_AUDIT.csv](results/a25/development/frozen_optimizer_repair/TASK_AUDIT.csv)、"
        "[NN_CLOSURE_ADMISSION.json](results/a25/development/frozen_optimizer_repair/NN_CLOSURE_ADMISSION.json)。")
    sections["FEEDBACK_REGIME_MAP.md"]=("# 反馈适用范围与证据域\n\n"
        "反馈强弱取决于已知背景、材料增量及观测方向的组合。以弱背景/ring背景、0.3/1.2对比度和clean/20dB"
        "组织开发记录，可以定位已观察到的适用范围；这张地图不外推到不同频率、网格、源顺序或三维模型。\n\n"
        f"父线程压缩范围：{_fmt(_verdict(decision,'compression'))}。\n\n"
        "开发的额外1.8对比度标签与学习OOD的独立parents分别标注。训练64、validation16、ID16、OOD16"
        "各自按shell/asymmetric_piecewise/smooth/mixed_scale平衡；OOD每族两对象改变结构组合，另两对象"
        "保留ID几何分布而将对比度设为1.5/1.8。全部几何在manifest先冻结，未完成项标记NOT_RUN。")
    sections["SOMNET_MIGRATION_PILOT.md"]=("# SOM-Net迁移与匹配学习pilot\n\n"
        "SOM-Net将电流更新展开为网络，再结合物理场和跨源材料更新。A25的N0是原文四层结构的迁移复现，"
        "不声称官方代码逐项复现。N1/N2/N3以共同材料、同一decoder和监督组成匹配实验："
        "N1采用背景线性信息，N2采用完整材料反馈，N3采用明确获准的压缩闭合。\n\n"
        "材料与current/data一致性同时计算；CNN为float32，物理为complex128/float64，"
        "状态相关物理梯度不默认detach。训练32为64的固定平衡子集；四parent batch各取一个固定seed抽取的条件，"
        "AdamW、学习率、监督权重、更新数和validation选择规则共享。更新数从500/1000/2000按实际GPU成本选定，"
        "不能通过看locked质量决定更新数。\n\n"+model_table+
        f"\nGPU健康原始状态：{evidence['health'].get('status','NOT_RUN')}；成本选择：{_fmt(sanitizer(evidence['updates']))}。\n\n"
        f"学习裁决：{_fmt(_verdict(decision,'learning'))}；样本效率：{_fmt(_verdict(decision,'sample_efficiency'))}；"
        f"层数：{_fmt(_verdict(decision,'depth'))}。\n\n"+SOURCES)
    sections["EXPLORATION_LEDGER.md"]=("# 探索与失败账本\n\n"
        "探索记录需要同时说明假设、唯一变化、保持冻结的条件、预期指标、资源上限、实际结果、裁决和下一步。"
        "已有原始八字段记录完整复制到报告数据，不能在探索结束后重写成主实验。缺少记录的计划写NOT_RUN。\n\n"
        f"当前失败账本保留{costs['failure_records']}个去重记录，来源位置随记录保存；"
        "所有FAILED、BUDGET_STOP和INTERRUPTED作业均计费。修复后的测试通过不删除早期失败，也不自动产生科学GO。\n\n"
        "来源：[FAILURE_LEDGER.jsonl](FAILURE_LEDGER.jsonl)、[探索原始导出](results/a25/report/plot_data/exploration.json)。")
    sections["LOCKED_VALIDATION.md"]=("# 一次locked ID/OOD验证\n\n"
        "独立parents用于检验新材料是否仍满足共享物理和已观察到的学习收益。validation用于训练选择；"
        "ID/OOD truth在全部11个模型checkpoint冻结之前关闭。MODEL_FREEZE与"
        "results/a25/learning/LOCKED_OPEN.json的一次性记录控制开启；"
        "failed cases保留空指标，不再次打开挑选测试结果。\n\n"
        f"已保存locked状态：{evidence['locked_summary'].get('status','NOT_RUN')}；"
        f"一次打开记录存在：{evidence['locked_open']}。父线程locked_status：{decision.get('locked_status','NOT_RUN')}。\n\n"
        "每parent先平均两背景、两对比度、两noise条件，再对parents等权；2000次paired bootstrap重采样parent，"
        "不把同一个parent的8个条件当8个独立对象。缺配对、失败和区间不足会阻止对应科学结论。\n\n"
        "原始来源：[cases.csv](results/a25/learning/locked_evaluation/cases.csv)、"
        "[parent_summary.json](results/a25/learning/locked_evaluation/parent_summary.json)、"
        "[paired_bootstrap.json](results/a25/learning/locked_evaluation/paired_bootstrap.json)、"
        "[timing.csv](results/a25/learning/locked_evaluation/timing.csv)。未生成的来源为NOT_RUN。")
    sections["A25_FINAL_RESEARCH_DECISION.md"]=("# A25最终研究裁决\n\n"
        "最终判断由父线程写入[A25_GATE_DECISION.json](results/a25/A25_GATE_DECISION.json)。"
        "本报告逐项呈现该文件，不从单幅图、单元测试、任务误差或某个成功子集自动生成GO。\n\n"+
        verdict_table+f"\n下一步：{_fmt(sanitizer(decision.get('next_step','NOT_REVIEWED')))}。\n\n"+
        budget_text+"\n\n理论恒等式、优化器数值健康、反馈成像收益、匹配学习收益与完整部署收益分别成立或未成立。"
        "任一局部PASS只对应其声明范围。" )
    return sections,figure_links,budget_text,background,common


def generate_report(root, book, config=None, *, decision_path=None, plots=True):
    root=Path(root).resolve()
    config=dict(config or _json(root/"configs/a25/campaign.json",{}))
    sanitizer=Sanitizer(root)
    with book.span("report_saved_evidence_read"):
        evidence=_gather(root,config)
        decision=sanitizer(_json(decision_path or root/"results/a25/A25_GATE_DECISION.json"))
        exploration=sanitizer(_explorations(root))
        _write_csv(root/"results/a25/report/plot_data/development_parent_equal.csv",evidence['development_summary'])
        _write_csv(root/"results/a25/report/plot_data/development_task_raw.csv",sanitizer(evidence['task_rows']))
        write_json(root/"results/a25/report/plot_data/exploration.json",exploration)
    figures=generate_figures(root,evidence,config,book) if plots else {"all_figures":{"status":"NOT_RUN","reason":"plots disabled by parent"}}
    with book.span("report_accounting_merge"):
        costs,job_rows=merge_accounting(root,book,sanitizer=sanitizer)
    sections,figure_links,budget_text,background,common=_sections(evidence,decision,costs,config,figures,sanitizer)
    with book.span("chinese_report_document_export"):
        for name,content in sections.items():
            (root/name).write_text(content.rstrip()+"\n",encoding="utf-8")
        contents="\n".join(f"- [{name}]({name})" for name in DOCUMENTS)
        full=("# A25：自适应OM反馈研究报告\n\n"+background+"\n\n"+common+
              "\n\n## 阅读与证据入口\n\n"+contents+"\n\n"+
              "\n\n".join(sections[name].replace("# ","## ",1) for name in DOCUMENTS[1:])+
              "\n\n## 实际图表\n\n"+figure_links+"\n\n## 资源与复核边界\n\n"+budget_text)
        (root/"A25_RESEARCH_REPORT_ZH.md").write_text(full+"\n",encoding="utf-8")
        readme=("# A25：自适应OM反馈\n\n"+background+"\n\n"
            "[从这里开始](A25_START_HERE.md) · [完整中文研究报告](A25_RESEARCH_REPORT_ZH.md) · "
            "[最终裁决](A25_FINAL_RESEARCH_DECISION.md) · [成本](COST_LEDGER.jsonl) · [失败](FAILURE_LEDGER.jsonl)\n\n"+
            _table([{"question":k,**_verdict(decision,k)} for k in ('solver_health','feedback_imaging','compression','learning','sample_efficiency','depth','deployment')],
                   (("question","问题"),("status","父线程裁决")))+
            "\n"+budget_text+"\n\n## 报告与原始证据\n\n"+contents+
            "\n\n图表和plot_data均从保存的真实输出生成。NOT_RUN项目不绘制虚拟数据。"
            "完整数据和checkpoint发布位置由父线程最终publication记录提供，发布前不声称匿名链接已经可访问。\n\n"+SOURCES)
        (root/"README.md").write_text(readme+"\n",encoding="utf-8")
        audit={"status":"SANITIZED_REPORT_ARTIFACTS", "redactions":dict(sanitizer.redactions),
            "raw_private_or_process_logs_copied":False,"credential_values_read":False,
            "generated_documents":list(DOCUMENTS)+["README.md","A25_RESEARCH_REPORT_ZH.md"],
            "accepted_cost_job_cutoff":costs['accepted_jobs'],"figures":figures,
            "parent_decision_source":"results/a25/A25_GATE_DECISION.json",
            "scientific_verdict_generated_by_reporter":False,"plots_use_only_saved_arrays":True}
        write_json(root/"results/a25/report/ARTIFACT_AUDIT.json",audit)
    return {"status":"REPORT_WRITTEN", "documents":list(DOCUMENTS)+["README.md","A25_RESEARCH_REPORT_ZH.md"],
            "cost_ledger":"COST_LEDGER.jsonl","failure_ledger":"FAILURE_LEDGER.jsonl",
            "accepted_cpu_seconds":costs['accepted_cpu_seconds'],"accepted_gpu_seconds":costs['accepted_gpu_seconds'],
            "figures":figures,"decision_source":audit['parent_decision_source'],
            "limitations":["parent scientific verdict only","live report tail provisional until accepted receipt"]}


report = generate_report
