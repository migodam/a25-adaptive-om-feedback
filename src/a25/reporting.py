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
SOURCES = ("[A24 冻结研究报告](https://github.com/migodam/a24-source-anchored-om-feedback/blob/ca80ca2a29867e1b03589061dd5c17688c9acbe0/A24_RESEARCH_REPORT_ZH.md)，"
           "[SOM-Net 原论文](https://arxiv.org/abs/2209.03567)，"
           "[A24 文献读取范围](theory/SOURCES_AND_READING_LEDGER.md)。")
ACTION_LEDGERS_ASSET = "https://github.com/migodam/a25-adaptive-om-feedback/releases/download/a25-v0.1.0/A25_COMPLETE_ACTION_LEDGERS.zip"
REPRODUCTION_DATA_ASSET = "https://github.com/migodam/a25-adaptive-om-feedback/releases/download/a25-v0.1.0/A25_REPRODUCTION_DATA.zip"
DEVELOPMENT_EXPERIMENTS = (
    {"id": "frozen_optimizer_repair", "label": "冻结协议：认证求解器重放", "tv_multiplier": 1.0,
     "amplitudes": (0.3, 1.2), "variants_per_parent": 8, "figure_prefix": "",
     "image_methods": ("L", "F", "R16", "R24", "R32", "TASK_R32"),
     "scope": "原TV权重、原32条件；仅修复同目标求解器"},
    {"id": "tv_multiplier_0p1", "label": "追加开发探索：TV×0.1", "tv_multiplier": 0.1,
     "amplitudes": (0.3, 1.2), "variants_per_parent": 8, "figure_prefix": "tv0p1_",
     "image_methods": ("L", "F", "TASK_R32"),
     "scope": "相同32观测；初始化与迭代共同降低TV权重，不改写原协议"},
    {"id": "amplitude_1p8", "label": "追加开发探索：振幅1.8", "tv_multiplier": 1.0,
     "amplitudes": (1.8,), "variants_per_parent": 4, "figure_prefix": "amplitude1p8_",
     "image_methods": ("L", "F", "TASK_R32"),
     "scope": "原TV权重；16条件、8个新增clean labels；仍是历史四parent"},
)


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


def _percent(value):
    number=_num({"value":value},"value")
    return f"{100*number:.4f}%" if number is not None else "未记录 / 未定义"


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
    failure_tables = [root/"results/a25/development"/spec["id"]/"METRICS.csv"
                      for spec in DEVELOPMENT_EXPERIMENTS]
    failure_tables.append(root/"results/a25/development/prospective_regime_validation/CHECKPOINT_METRICS.csv")
    failure_tables.append(root/"results/a25/learning/locked_evaluation/cases.csv")
    for path in failure_tables:
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
    if set(groups) != {int(parent) for parent in parents}:
        return None
    for parent in parents:
        items = groups.get(int(parent), [])
        if (len(items) != variants or len({r.get("case_id") for r in items}) != variants
                or any(r.get("status") != "OK" or _num(r, metric) is None for r in items)):
            return None
        values.append(float(np.mean([_num(r, metric) for r in items])))
    return float(np.mean(values)) if values else None


def _development_summary(rows, config, *, experiment=None, checkpoints=(3, 6, 12)):
    summary = []
    parents = config.get("parents", [2401, 2402, 2403, 2404])
    spec = experiment or DEVELOPMENT_EXPERIMENTS[0]
    variants = spec["variants_per_parent"]
    for method in sorted({r.get("method", "") for r in rows}):
        for k in checkpoints:
            subset = [r for r in rows if r.get("method") == method and _num(r, "K") == k]
            row = {"experiment": spec["id"], "tv_multiplier": spec["tv_multiplier"],
                   "amplitudes": list(spec["amplitudes"]), "method": method, "K": k, "observed_rows": len(subset),
                   "ok_rows": sum(r.get("status") == "OK" for r in subset),
                   "expected_rows": len(parents)*variants,
                   "quality_hits": sum(str(r.get("quality_target_hit")).lower() == "true" for r in subset)}
            for metric in ("delta_nrmse", "material_nrmse", "delta_real_nrmse", "delta_imag_nrmse",
                           "real_nrmse", "imag_nrmse", "edge_nrmse", "support_iou",
                           "full_data_relative_residual", "online_s",
                           "shared_setup_s", "method_setup_s"):
                row[metric] = _parent_means(subset, metric, parents=parents, variants=variants)
            row["complete"] = row["delta_nrmse"] is not None
            row["independent_cold_s"] = (sum(row[m] for m in ("online_s", "shared_setup_s", "method_setup_s"))
                                         if all(row[m] is not None for m in ("online_s", "shared_setup_s", "method_setup_s")) else None)
            summary.append(row)
    return summary


def _regime_summary(experiment, config):
    """Descriptive K12 parent pairs; no new independent validation or gate."""
    output = []
    parents = config.get("parents", [2401, 2402, 2403, 2404])
    rows = experiment["rows"]
    for background in ("weak", "ring"):
        for amplitude in experiment["amplitudes"]:
            base = [r for r in rows if r.get("background") == background and _num(r, "amplitude") == amplitude
                    and _num(r, "K") == 12]
            record = {"experiment": experiment["id"], "tv_multiplier": experiment["tv_multiplier"],
                      "background": background, "amplitude": amplitude, "K": 12,
                      "expected_parents": len(parents), "expected_conditions_per_method": 2*len(parents)}
            for method in ("L", "F", "TASK_R32"):
                selected = [r for r in base if r.get("method") == method]
                record[method+"_delta"] = _parent_means(selected, "delta_nrmse", parents=parents, variants=2)
            gains = []
            for parent in parents:
                means = {}
                for method in ("L", "F"):
                    selected = [r for r in base if r.get("method") == method and _num(r, "parent_id") == parent]
                    means[method] = _parent_means(selected, "delta_nrmse", parents=[parent], variants=2)
                if means["L"] is None or means["F"] is None or means["L"] <= 0:
                    gains = [];break
                gains.append((means["L"]-means["F"])/means["L"])
            record["parent_gains"] = gains
            record["F_relative_parent_mean_gain"] = float(np.mean(gains)) if len(gains) == len(parents) else None
            record["paired_complete"] = record["F_relative_parent_mean_gain"] is not None
            output.append(record)
    return output


def _pareto_points(summary):
    """Observed nondominated points within each experiment and equal K only."""
    result = []
    for row in summary:
        if not row["complete"] or row["independent_cold_s"] is None:
            continue
        peers = [other for other in summary if other["K"] == row["K"] and other["complete"]
                 and other["independent_cold_s"] is not None]
        dominated = any(other["independent_cold_s"] <= row["independent_cold_s"]
                        and other["delta_nrmse"] <= row["delta_nrmse"]
                        and (other["independent_cold_s"] < row["independent_cold_s"]
                             or other["delta_nrmse"] < row["delta_nrmse"]) for other in peers)
        result.append({**row, "observed_nondominated_at_same_K": not dominated})
    return result


def _verdict(decision, key):
    aliases={"compression":"feedback_compression","depth":"depth_reduction"}
    gates=decision.get("gates",{})
    candidates=(key,aliases.get(key,key))
    value=next((source[candidate] for source in (gates,decision) if isinstance(source,dict)
                for candidate in candidates if candidate in source),{"status":"NOT_REVIEWED"})
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

    for experiment in evidence["experiments"]:
        prefix, label = experiment["figure_prefix"], experiment["label"]
        expected = len(config.get("parents", [2401,2402,2403,2404]))*experiment["variants_per_parent"]

        def convergence(experiment=experiment):
            chosen = [r for r in experiment["convergence_summary"] if r["complete"] and r["online_s"] is not None]
            if not chosen:return None
            fig, ax = plt.subplots(figsize=(9, 5))
            for method in sorted({r["method"] for r in chosen}):
                points = sorted([r for r in chosen if r["method"] == method], key=lambda r:r["K"])
                ax.plot([r["online_s"] for r in points], [r["delta_nrmse"] for r in points], marker=".", label=method)
            ax.set_xlabel("shared initialization + online trajectory (s)");ax.set_ylabel("equal-parent delta NRMSE")
            ax.set_title(experiment["label"]+"：完整条件的逐步收敛");ax.legend(fontsize=8)
            return fig
        _figure(root,prefix+"convergence_runtime.png",label+f"；K1–12实际输出，每点要求全部{expected}条件。",convergence,book,manifest)

        def pareto(experiment=experiment):
            chosen = _pareto_points(experiment["summary"])
            if not chosen:return None
            fig, axes = plt.subplots(1, 3, figsize=(16, 5.4), constrained_layout=True)
            methods = sorted({r["method"] for r in chosen})
            colors = {method:plt.get_cmap("tab10")(index % 10) for index,method in enumerate(methods)}
            for ax,k in zip(axes,(3,6,12)):
                points = [r for r in chosen if r["K"] == k]
                for r in points:
                    ax.scatter(r["independent_cold_s"],r["delta_nrmse"],color=colors[r["method"]],s=30,
                               label=r["method"])
                frontier = sorted([r for r in points if r["observed_nondominated_at_same_K"]],key=lambda r:r["independent_cold_s"])
                if frontier:
                    ax.plot([r["independent_cold_s"] for r in frontier],[r["delta_nrmse"] for r in frontier],
                            color="black",ls="--",lw=1,label="observed nondominated")
                if not points:ax.text(.5,.5,"NOT_RUN",transform=ax.transAxes,ha="center")
                ax.set_title(f"K={k}");ax.set_xlabel("independent setup + initialization + online (s)")
                ax.legend(fontsize=7,ncol=2,loc="upper center",bbox_to_anchor=(.5,-.19))
            axes[0].set_ylabel("equal-parent delta NRMSE")
            fig.suptitle(experiment["label"]+"：相同K的已观察质量—时间点；审计另计")
            return fig
        _figure(root,prefix+"quality_time_pareto.png",label+"；每个K单独标出已观察非劣点，不外推为部署速度保证。",pareto,book,manifest)

        def ranks(experiment=experiment):
            rows = experiment["task_rows"]
            methods = [m for m in ("R16","R24","R32","LOCAL_R16","TASK_R32","AFFINE_ROM32")
                       if any(r.get("method") == m for r in rows)]
            if not methods:return None
            keys = ("independent_transfer_error","independent_adjoint_error","gradient_cosine")
            if not any(r.get("status") == "OK" and any(_num(r,key) is not None for key in keys) for r in rows):
                return None
            fig, axes = plt.subplots(1, 3, figsize=(14, 4))
            labels = []
            for index, method in enumerate(methods):
                selected = [r for r in rows if r.get("method") == method and r.get("status") == "OK"]
                ranks_seen = sorted({int(value) for r in experiment["rows"] if r.get("method") == method
                                     and (value := _num(r,"current_rank")) is not None})
                labels.append(method+("\nr="+",".join(map(str,ranks_seen)) if ranks_seen else ""))
                for key, ax in zip(keys, axes):
                    values = [v for r in selected if (v := _num(r,key)) is not None]
                    ax.scatter([index]*len(values),values,s=15,alpha=.55)
            for ax, title, threshold in zip(axes,("forward task error","adjoint task error","gradient cosine"),(.05,.05,.99)):
                ax.axhline(threshold,color="black",ls="--",lw=1);ax.set_title(title)
                ax.set_xticks(range(len(methods)),labels,rotation=25)
            fig.suptitle(experiment["label"]+"：固定任务探针；实际rank单列")
            return fig
        _figure(root,prefix+"rank_task_error.png",label+"；实际forward/adjoint误差与梯度cosine，失败保留原表。",ranks,book,manifest)

        def images(experiment=experiment):
            directory = experiment["path"] / "images"
            amplitude = experiment["amplitudes"][-1]
            cases = (f"weak_2401_{amplitude}_snr20",f"ring_2401_{amplitude}_snr20",f"ring_2403_{amplitude}_snr20")
            methods = experiment["image_methods"]
            if not any((directory/f"{c}_{m}_K12.npz").exists() for c in cases for m in methods):return None
            fig, axes = plt.subplots(len(cases),len(methods)+1,figsize=(3*(len(methods)+1),8))
            for row, case in enumerate(cases):
                truth_drawn=False
                for col,method in enumerate(methods,1):
                    book.check()
                    ax=axes[row,col];path=directory/f"{case}_{method}_K12.npz"
                    records=[r for r in experiment["rows"] if r.get("case_id")==case and r.get("method")==method and _num(r,"K")==12]
                    if not path.exists() or len(records)!=1 or records[0].get("status")!="OK":
                        ax.text(.5,.5,"FAILED / NOT_RUN",ha="center",va="center");ax.set_axis_off();continue
                    with np.load(path,allow_pickle=False) as archive:
                        chi,truth,bg=(archive[key].copy() for key in ("chi","truth","background"))
                    grid=int(round(np.sqrt(len(chi))))
                    if grid*grid!=len(chi) or not all(np.isfinite(v).all() for v in (chi,truth,bg)):
                        ax.text(.5,.5,"INVALID_SAVED_ARRAY",ha="center");ax.set_axis_off();continue
                    limit=float(np.max(abs((truth-bg).real)))
                    if limit==0:limit=1.
                    ax.imshow((chi-bg).real.reshape(grid,grid),origin="lower",vmin=-.1*limit,vmax=limit,cmap="viridis")
                    ax.set_title(method);ax.set_axis_off()
                    if not truth_drawn:
                        axes[row,0].imshow((truth-bg).real.reshape(grid,grid),origin="lower",vmin=-.1*limit,vmax=limit,cmap="viridis")
                        axes[row,0].set_title(case+"\ntruth delta Re");axes[row,0].set_axis_off();truth_drawn=True
                if not truth_drawn:axes[row,0].text(.5,.5,"NOT_RUN",ha="center");axes[row,0].set_axis_off()
            fig.suptitle(experiment["label"]+"：固定已暴露样例，K12；每行共用色标")
            return fig
        _figure(root,prefix+"development_images.png",label+"；固定样例的材料增量实部，失败不换成成功对象。",images,book,manifest)

    prospective=evidence.get("prospective_regime")
    def prospective_family_gain():
        if prospective is None or prospective["artifact"]!="SUMMARY.json":return None
        details=prospective["details"]
        rows=details["family_rows"]
        if len(rows)!=4 or not all(row["paired_complete"] for row in rows):return None
        fig,ax=plt.subplots(figsize=(11,5))
        labels=[]
        for index,row in enumerate(rows):
            parents=sorted([item for item in details["parent_rows"] if item["family"]==row["family"]],key=lambda item:item["parent_id"])
            ax.scatter([index+offset for offset in (-.18,-.06,.06,.18)],
                       [item["paired_relative_F_gain"] for item in parents],s=28,alpha=.7,
                       label="paired parent gain" if index==0 else None)
            ax.scatter(index,row["mean_paired_relative_F_gain"],marker="_",s=260,color="black",
                       label="family mean; no family CI" if index==0 else None)
            labels.append(row["family"]+"\n4 parents")
        primary=prospective["record"].get("primary",{})
        point=_num(primary,"point_estimate")
        interval=primary.get("ci95",[])
        if point is not None and len(interval)==2 and all(_num({"x":value},"x") is not None for value in interval):
            ax.errorbar(4.5,point,yerr=[[point-interval[0]],[interval[1]-point]],fmt="o",color="black",capsize=5,
                        label="16-parent mean / saved bootstrap CI95")
            labels.append("overall\n16 parents")
            ticks=[0,1,2,3,4.5]
        else:ticks=list(range(4))
        ax.axhline(0,color="gray",lw=1);ax.axhline(.1,color="firebrick",ls="--",lw=1,label="10% hypothesis target")
        ax.set_xticks(ticks,labels,rotation=12)
        from matplotlib.ticker import PercentFormatter
        ax.yaxis.set_major_formatter(PercentFormatter(xmax=1))
        ax.set_ylabel("(L parent error - F parent error) / L parent error")
        ax.set_title("前瞻无NN窄范围验证：各family配对改善；validation现已暴露")
        ax.legend(fontsize=8)
        return fig
    _figure(root,"prospective_family_paired_gain.png",
            "四family各四parent；先平均clean/20dB，再计算parent改善。family只画实际点与均值，总体区间使用已保存bootstrap。",
            prospective_family_gain,book,manifest)

    def prospective_family_images():
        if prospective is None or prospective["artifact"]!="SUMMARY.json":return None
        families=prospective["details"]["family_rows"]
        if not families or any(row["first_parent"] is None for row in families):return None
        directory=prospective["path"]/"arrays"
        methods=("L","F","TASK_R32")
        cases=[f"p{row['first_parent']}_weak_a1_clean" for row in families]
        if not any((directory/f"{case}_{method}_K12.npz").is_file() for case in cases for method in methods):return None
        fig,axes=plt.subplots(4,4,figsize=(14,14),constrained_layout=True)
        for index,(family,case) in enumerate(zip(families,cases)):
            truth_drawn=False;image=None
            for column,method in enumerate(methods,1):
                ax=axes[index,column];path=directory/f"{case}_{method}_K12.npz"
                rows=[row for row in prospective["checkpoint_rows"] if row.get("case_id")==case and row.get("method")==method and _num(row,"K")==12]
                if not path.is_file() or len(rows)!=1 or rows[0].get("status")!="OK":
                    ax.text(.5,.5,"FAILED / NOT_RUN",ha="center");ax.set_axis_off();continue
                with book.span("report_saved_validation_array_load",report_saved_validation_arrays=1):
                    with np.load(path,allow_pickle=False) as archive:
                        chi,truth,background=(archive[key].copy() for key in ("chi","truth","background"))
                grid=int(round(np.sqrt(len(chi))))
                if grid*grid!=len(chi) or not all(np.isfinite(value).all() for value in (chi,truth,background)):
                    ax.text(.5,.5,"INVALID_SAVED_ARRAY",ha="center");ax.set_axis_off();continue
                limit=float(np.max(abs((truth-background).real)))
                if limit==0:limit=1.
                image=ax.imshow((chi-background).real.reshape(grid,grid),origin="lower",vmin=-.1*limit,vmax=limit,cmap="viridis")
                ax.set_title(method+"\ndelta NRMSE="+_fmt(_num(rows[0],"delta_nrmse")),fontsize=10);ax.set_axis_off()
                if not truth_drawn:
                    axes[index,0].imshow((truth-background).real.reshape(grid,grid),origin="lower",vmin=-.1*limit,vmax=limit,cmap="viridis")
                    axes[index,0].set_title(family["family"]+"\np"+str(family["first_parent"])+" clean / truth Δχ Re",fontsize=10)
                    axes[index,0].set_axis_off();truth_drawn=True
            if image is not None:fig.colorbar(image,ax=axes[index,:].tolist(),shrink=.7,label="Re(χ−χ_b)")
            if not truth_drawn:axes[index,0].text(.5,.5,"FAILED / NOT_RUN",ha="center");axes[index,0].set_axis_off()
        fig.suptitle("前瞻验证固定图像：每family最小parent ID，clean条件，K12；不按结果选择")
        return fig
    _figure(root,"prospective_fixed_family_images.png",
            "固定shell/asymmetric_piecewise/smooth/mixed_scale各首个parent，clean、K12；只读已保存离线arrays，不读取locked。",
            prospective_family_images,book,manifest)

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
            drawn=False
            for method in ("N0","N1","N2","N3"):
                b=4 if method=="N0" else 3
                selected=sorted([p for p in points if p["method"]==method and p["blocks"]==b and p["split"]=="locked_id"],key=lambda p:p["train"])
                if {p["train"] for p in selected}=={32,64}:
                    ax.plot([p["train"] for p in selected],[p["error"] for p in selected],marker="o",label=method);drawn=True
            if not drawn:plt.close(fig);return None
            ax.set_xlabel("independent training parents");ax.set_xticks([32,64]);ax.set_title("Locked ID sample efficiency; fixed depth per arm")
        else:
            selected=[p for p in points if (p["split"]=="locked_ood" if mode=="ood" else p["train"]==64 and p["split"]=="locked_id")]
            if mode=="ablation":
                paired_methods={method for method in ("N1","N2","N3")
                                if {p["blocks"] for p in selected if p["method"]==method}=={3,4}}
                selected=[p for p in selected if p["method"] in paired_methods]
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
    experiments, inputs = [], []
    for spec in DEVELOPMENT_EXPERIMENTS:
        path=root/"results/a25/development"/spec["id"]
        rows=_csv(path/"METRICS.csv")
        package={**spec,"path":path,"rows":rows,"task_rows":_csv(path/"TASK_AUDIT.csv"),
                 "histories":_json(path/"HISTORIES.json",[]),"preparations":_json(path/"PREPARATIONS.json",[]),
                 "saved_parent_summary":_csv(path/"PARENT_EQUAL_SUMMARY.csv")}
        package["summary"]=_development_summary(rows,config,experiment=spec)
        package["convergence_summary"]=_development_summary(rows,config,experiment=spec,checkpoints=range(1,13))
        package["regimes"]=_regime_summary(package,config)
        experiments.append(package)
        for filename in ("METRICS.csv","TASK_AUDIT.csv","HISTORIES.json","PREPARATIONS.json"):
            inputs.append({"experiment":spec["id"],"artifact":filename,
                           "path":(path/filename).relative_to(root).as_posix(),
                           "status":"PRESENT" if (path/filename).is_file() else "MISSING"})
        image_count=sum(1 for _ in (path/"images").glob("*.npz"))
        inputs.append({"experiment":spec["id"],"artifact":"images/*.npz","count":image_count,
                       "status":"PRESENT" if image_count else "MISSING",
                       "path":(path/"images").relative_to(root).as_posix()})
    original=experiments[0]
    learning=root/"results/a25/learning"
    health_attempts=[]
    for path in sorted((learning/"health_attempts").glob("*/GPU_HEALTH.json")):
        health_attempts.append({"job":path.parent.name,"source":path.relative_to(root).as_posix(),
                                "health":_json(path),"cost_selection":_json(path.parent/"COST_SELECTED_UPDATES.json")})
    health,updates,provenance=(_json(learning/name) for name in
                               ("GPU_HEALTH.json","COST_SELECTED_UPDATES.json","HEALTH_INDEX_PROVENANCE.json"))
    adopted=provenance.get("adopted_job",provenance.get("active_health_job",updates.get("health_job")))
    if adopted and not any(attempt["job"]==adopted for attempt in health_attempts):
        health_attempts.append({"job":adopted,"source":"results/a25/learning/GPU_HEALTH.json",
                                "health":health,"cost_selection":updates})
    locked_open=(learning/"LOCKED_OPEN.json").exists()
    prospective_directory=root/"results/a25/development/prospective_regime_validation"
    prospective=None
    for filename in ("SUMMARY.json","PROVENANCE.json"):
        path=prospective_directory/filename
        if path.is_file():
            prospective={"source":path.relative_to(root).as_posix(),"artifact":filename,"record":_json(path),
                         "path":prospective_directory,"provenance":_json(prospective_directory/"PROVENANCE.json"),
                         "review":_json(prospective_directory/"PARENT_REVIEW.json"),
                         "checkpoint_rows":_csv(prospective_directory/"CHECKPOINT_METRICS.csv"),
                         "task_rows":_csv(prospective_directory/"TASK_AUDIT.csv")}
            break
    if prospective is not None:
        prospective["details"]=_prospective_details(prospective)
        for filename in ("SUMMARY.json","PROVENANCE.json","PARENT_REVIEW.json","CHECKPOINT_METRICS.csv","TASK_AUDIT.csv"):
            path=prospective_directory/filename
            inputs.append({"experiment":"prospective_regime_validation","artifact":filename,
                           "path":path.relative_to(root).as_posix(),"status":"PRESENT" if path.is_file() else "MISSING"})
    for relative in ("results/a25/development/REGIME_HYPOTHESIS_FREEZE.json",
                     "results/a25/development/PAIRED_TV_AND_REGIME.json",
                     "results/a25/development/PAIRED_PARENT_BOOTSTRAP.json",
                     "results/a25/A25_GATE_DECISION.json","results/a25/learning/TRAINED_MODELS.json",
                     "results/a25/learning/MODEL_FREEZE.json","results/a25/learning/LOCKED_OPEN.json",
                     "results/a25/learning/locked_evaluation/cases.csv"):
        inputs.append({"artifact":Path(relative).name,"path":relative,
                       "status":"PRESENT" if (root/relative).is_file() else "NOT_RUN_OR_PENDING"})
    return {"phase0":_json(root/"results/a25/development/phase0/DECISION.json"),
        "phase0_initial":_json(root/"results/a25/development/phase0/DECISION_INITIAL.json"),
        "solver_rows":_csv(root/"results/a25/development/phase0/SOLVER_COMPARISON.csv"),
        "references":_json(root/"results/a25/development/phase0/INDEPENDENT_REFERENCE.json",[]),
        "refinement":_json(root/"results/a25/development/phase0/REFERENCE_REFINEMENT_001.json"),
        "experiments":experiments,"input_inventory":inputs,
        "regime_freeze":_json(root/"results/a25/development/REGIME_HYPOTHESIS_FREEZE.json"),
        "paired_tv_regime":_json(root/"results/a25/development/PAIRED_TV_AND_REGIME.json"),
        "development_bootstrap":_json(root/"results/a25/development/PAIRED_PARENT_BOOTSTRAP.json",[]),
        "prospective_regime":prospective,
        "development_path":development,"development_rows":original["rows"],
        "preparations":original["preparations"],
        "development_summary":original["summary"],"task_rows":original["task_rows"],
        "admission":_json(development/"NN_CLOSURE_ADMISSION.json"),
        "health":health,"health_attempts":health_attempts,"health_provenance":provenance,
        "profile":_json(root/"results/a25/jobs/a25-gpu-profile-retry-005/PROFILE_UPDATE.json"),
        "profile_receipt":_json(root/"results/a25/jobs/a25-gpu-profile-retry-005/job_receipt.json"),
        "profile_failed_receipt":_json(root/"results/a25/jobs/a25-gpu-profile-004/job_receipt.json"),
        "updates":updates,
        "models":_json(learning/"TRAINED_MODELS.json",[]),"freeze":_json(learning/"MODEL_FREEZE.json"),
        "locked_open":locked_open,
        "locked_summary":_json(locked/"summary.json") if locked_open else {"status":"NOT_RUN","truth_status":"CLOSED"},
        "locked_rows":_csv(locked/"cases.csv") if locked_open else [],
        "timing":_csv(locked/"timing.csv") if locked_open else [],
        "paired":_json(locked/"paired_bootstrap.json") if locked_open else {"status":"NOT_RUN"},
        "parent_summary":_json(locked/"parent_summary.json") if locked_open else {"status":"NOT_RUN"}}


def _explorations(root):
    rows=[]
    for path in (Path(root)/"results/a25/EXPLORATION_LEDGER.jsonl",Path(root)/"results/a25/development/EXPLORATION_LEDGER.jsonl"):
        if path.exists():
            with path.open(encoding="utf-8") as handle:
                for line in handle:
                    try:rows.append(json.loads(line))
                    except ValueError:rows.append({"status":"UNREADABLE_EXPLORATION_RECORD"})
    return rows


def _experiment_table(experiment, *, timing=False):
    columns=(("method","方法"),("K","K"),("ok_rows","OK条件"),("expected_rows","应有条件"),
             ("complete","完整parent配对"),("delta_nrmse","增量NRMSE"))
    if timing:
        columns+=(("shared_setup_s","共享准备秒"),("method_setup_s","方法准备秒"),
                  ("online_s","初始化+online秒"),("independent_cold_s","单方法独立冷成本秒"),
                  ("quality_hits","质量命中数"))
    else:
        columns+=(("material_nrmse","完整χ NRMSE"),("edge_nrmse","边缘NRMSE"),
                  ("support_iou","支撑IoU"),("full_data_relative_residual","完整场相对残差"),
                  ("quality_hits","质量命中数"))
    directory="results/a25/development/"+experiment["id"]
    return ("### "+experiment["label"]+"\n\n"+experiment["scope"]+"。\n\n"+
            _table(experiment["summary"],columns)+"\n"
            f"原始逐步记录：[METRICS.csv]({directory}/METRICS.csv)、"
            f"[完整HISTORIES：A25_REPRODUCTION_DATA.zip]({REPRODUCTION_DATA_ASSET})"
            f"（压缩包内项目相对路径：`{directory}/HISTORIES.json`）；"
            f"报告等权导出：[{experiment['id']}_parent_equal.csv](results/a25/report/plot_data/{experiment['id']}_parent_equal.csv)。")


def _task_summary(experiment, config):
    output=[]
    parents=config.get("parents",[2401,2402,2403,2404])
    for method in sorted({r.get("method","") for r in experiment["task_rows"]}):
        rows=[r for r in experiment["task_rows"] if r.get("method")==method]
        valid=[r for r in rows if r.get("status")=="OK"]
        item={"experiment":experiment["id"],"method":method,"observed_rows":len(rows),"ok_rows":len(valid),
              "expected_rows":len(parents)*experiment["variants_per_parent"]}
        keys=("independent_transfer_error","independent_adjoint_error","gradient_cosine","independent_state_data_error")
        for key in keys:
            values=[v for r in valid if (v:=_num(r,key)) is not None]
            item[("min_" if key=="gradient_cosine" else "max_")+key]=(min(values) if key=="gradient_cosine" else max(values)) if values else None
        item["complete"] = all(_parent_means(rows,key,parents=parents,variants=experiment["variants_per_parent"]) is not None for key in keys)
        item["actual_ranks"] = sorted({int(value) for r in experiment["rows"] if r.get("method")==method
                                       and (value:=_num(r,"current_rank")) is not None})
        output.append(item)
    return output


def _history_summary(experiment, config):
    histories=experiment["histories"] if isinstance(experiment["histories"],list) else []
    expected=len(config.get("parents",[2401,2402,2403,2404]))*experiment["variants_per_parent"]
    output=[]
    for method in sorted({r.get("method","") for r in experiment["rows"]}):
        records=[r for r in histories if r.get("method")==method]
        steps=[step for r in records for step in r.get("history",[])]
        output.append({"experiment":experiment["id"],"method":method,"saved_trajectories":len(records),
                       "expected_trajectories":expected,"saved_steps":len(steps),
                       "accepted_steps":sum(step.get("accepted") is True for step in steps),
                       "unaccepted_steps":sum(step.get("accepted") is False for step in steps),
                       "retried_steps":sum(len(step.get("trials",[]))>1 for step in steps),
                       "complete_12_step_histories":len(records)==expected and len({r.get("case_id") for r in records})==expected
                           and all(len(r.get("history",[]))==12 for r in records)})
    return output


def _prospective_details(prospective):
    """Summarize saved parent errors; never bootstrap anew or open labels."""
    summary,provenance=prospective["record"],prospective["provenance"]
    parents=sorted(int(parent) for parent in provenance.get("parent_ids",[]))
    families=provenance.get("parent_families",{})
    records={}
    for row in summary.get("parent_equal",[]):
        records[(row.get("method"),row.get("K"),row.get("metric"))]=row
    parent_rows=[]
    for parent in parents:
        values={method:_num(records.get((method,12,"delta_nrmse"),{}).get("parent_values",{}),str(parent))
                for method in ("L","F","TASK_R32")}
        gain=(values["L"]-values["F"])/values["L"] if values["L"] is not None and values["L"]>0 and values["F"] is not None else None
        parent_rows.append({"parent_id":parent,"family":families.get(str(parent)),
                            "L_delta":values["L"],"F_delta":values["F"],"TASK_R32_delta":values["TASK_R32"],
                            "paired_relative_F_gain":gain})
    family_rows=[]
    for family in ("shell","asymmetric_piecewise","smooth","mixed_scale"):
        selected=[row for row in parent_rows if row["family"]==family]
        complete=len(selected)==4 and all(row["paired_relative_F_gain"] is not None for row in selected)
        row={"family":family,"parents":[item["parent_id"] for item in selected],"parent_count":len(selected),
             "paired_complete":complete,"mean_paired_relative_F_gain":float(np.mean([item["paired_relative_F_gain"] for item in selected])) if complete else None,
             "first_parent":min((item["parent_id"] for item in selected),default=None)}
        for method in ("L","F","TASK_R32"):
            values=[item[method+"_delta"] for item in selected]
            row[method+"_delta"]=float(np.mean(values)) if len(values)==4 and all(value is not None for value in values) else None
        family_rows.append(row)
    endpoints=[]
    for method in ("L","F","TASK_R32"):
        delta=records.get((method,12,"delta_nrmse"),{})
        material=records.get((method,12,"material_nrmse"),{})
        rows=[row for row in prospective["checkpoint_rows"] if row.get("method")==method and _num(row,"K")==12]
        endpoints.append({"method":method,"complete_parents":delta.get("complete_parents"),
                          "coverage_complete":delta.get("coverage_complete"),
                          "delta_nrmse":delta.get("parent_equal_mean"),"material_nrmse":material.get("parent_equal_mean"),
                          "quality_hits":sum(row.get("status")=="OK" and str(row.get("quality_target_hit")).lower()=="true" for row in rows),
                          "conditions":len(rows)})
    return {"parent_rows":parent_rows,"family_rows":family_rows,"endpoints":endpoints}


def _sections(evidence, decision, costs, config, figures, sanitizer):
    phase=evidence["phase0"];admission=evidence["admission"]
    solver_table=_table([dict(algorithm=k,**v) for k,v in phase.get("solvers",{}).items()],
        (("algorithm","算法"),("certified","证书通过"),("required","同目标问题数"),("sum_prox_wall_s","prox wall秒")))
    references=evidence["references"] if isinstance(evidence["references"],list) else []
    reference_table=_table(references,(("case_id","对象/优化器控制"),("solver_status","Clarabel原始status"),
        ("strict_external_reference_certificate_passed","严格外部证书"),("acceptance_reason","验收原因"),
        ("kkt_residual","KKT"),("normalized_gap","normalized gap"),("comparison_agrees","同目标对照")))
    candidate_table=_table(admission.get("candidates",[]),(("method","候选"),("complete","完整配对"),
        ("max_transfer_error","forward任务误差"),("max_adjoint_error","adjoint任务误差"),
        ("min_gradient_cosine","梯度cosine"),("max_delta_image_ratio_vs_F","最大成像比值/F"),
        ("eligible_physics","开发域准入")))
    verdicts=[]
    for key in ("solver_health","feedback_imaging","compression","learning","sample_efficiency","OOD","depth","locked_validation","deployment"):
        verdict=sanitizer(_verdict(decision,key))
        verdicts.append({"question":key,**verdict,
                         "parent_notes":{name:value for name,value in verdict.items() if name!="status"}})
    verdict_table=_table(verdicts,(("question","独立问题"),("status","父线程裁决"),("parent_notes","父线程原始范围与说明")))
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
    quality_tables="\n\n".join(_experiment_table(experiment) for experiment in evidence["experiments"])
    timing_tables="\n\n".join(_experiment_table(experiment,timing=True) for experiment in evidence["experiments"])
    history_rows=[row for experiment in evidence["experiments"] for row in _history_summary(experiment,config)]
    regime_rows=[row for experiment in evidence["experiments"] for row in experiment["regimes"]]
    regime_table=_table(regime_rows,(("experiment","实验"),("tv_multiplier","TV倍数"),("background","背景"),
        ("amplitude","振幅"),("paired_complete","四parent配对"),("L_delta","L增量NRMSE"),
        ("F_delta","F增量NRMSE"),("TASK_R32_delta","TASK_R32增量NRMSE"),
        ("F_relative_parent_mean_gain","F相对L改善，0.1=10%"),("parent_gains","四parent各自改善")))
    bootstrap=evidence["development_bootstrap"] if isinstance(evidence["development_bootstrap"],list) else []
    bootstrap_table=_table(bootstrap,(("experiment","实验"),("K","K"),("parent_count","独立cluster数"),
        ("parent_mean_relative_F_gain","先算各parent改善再平均"),
        ("paired_parent_bootstrap_95_percent","已保存95% bootstrap区间"),("scope","原始范围")))
    health_rows=[]
    health_costs=[]
    for attempt in evidence["health_attempts"]:
        health_rows.extend({"job":attempt["job"],**row} for row in attempt["health"].get("rows",[]))
        selection=attempt["cost_selection"]
        health_costs.extend({"job":attempt["job"],"selection_status":selection.get("status"),
                             **row} for row in selection.get("candidates",[]))
    health_table=_table(sanitizer(health_rows),(("job","health尝试"),("method","拓扑"),("blocks","层数"),
        ("status","原始status"),("update_wall_seconds","一次update wall秒"),
        ("update_cpu_seconds","一次update host CPU秒"),("parameter_count","参数数")))
    health_cost_table=_table(health_costs,(("job","health尝试"),("updates","计划每模型更新数"),
        ("projected_cpu_seconds","完整11模型CPU预测秒"),("projected_gpu_seconds","完整11模型GPU预测秒"),
        ("fits","符合该分配"),("selection_status","成本选择原始状态")))
    figure_links="\n".join(f"- [{name}]({row['path']})：{row['caption']}" if row["status"]=="GENERATED"
                           else f"- {name}：NOT_RUN，{row['reason']}。" for name,row in figures.items())
    budget_text=(f"已接受作业 CPU计费 {_fmt(costs['accepted_cpu_seconds'])} 秒 /7200秒；GPU占用 "
                 f"{_fmt(costs['accepted_gpu_seconds'])} 秒 /14400秒。报告自身仍在运行的尾部单独记为 provisional；"
                 "完整截止作业清单见 results/a25/report/COST_SUMMARY.json，最终资源以不可变 job_receipt.json 为准。"
                 f"[完整动作账本压缩包]({ACTION_LEDGERS_ASSET})包含项目相对路径 `COST_LEDGER.jsonl`"
                 "及各作业的 `results/a25/jobs/<job>/COST_LEDGER.jsonl`；大文件通过Release提供，"
                 "公开CSV、图表和小型metadata仍保留在Git。")
    background=("逆散射研究希望从有限的接收数据恢复空间材料。理解这一问题，先要从场的传播和多次散射出发："
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
        "理论表达、数值认证、成像结果、学习收益和部署结论分别裁决。冻结协议重放、TV×0.1单因素探索、"
        "振幅1.8追加检验各自保留，不将后两项重新命名为原协议。\n\n"+SOURCES)
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
        "验收分两类：Solved按冻结KKT/normalized gap≤1e-6、box feasibility≤1e-10验收；"
        "AlmostSolved除冻结检查外，还要求原始stationarity/feasibility≤1e-11及gap/complementarity≤1e-10。"
        "不能写成所有参考都通过1e-11严格标准。active_box的strict标志为false，但Solved与冻结证书通过；"
        "其legacy exact-active diagnostic约0.656263仍保留，不替代现行冻结验收。\n\n"
        "ring_2404、振幅1.2、20dB的原始失败包含SOC primal feasibility约1.16656e-11；"
        "同一QP经内部refinement后，原始最大残差约8.5824e-12、gap约9.63679e-14。"
        "修复收紧独立参考的内部数值精度，目标、box与对外容差保持原样。"
        "在已声明的可行性与强凸假设下，导出的√(2gap)是mass坐标中的距离界；"
        "gap阈值1e-6不等于材料误差已达到1e-6。CPU软件环境版本按SOURCE/REPRODUCING的Python3.13.13记录。\n\n"
        "原始来源：[SOLVER_COMPARISON.csv](results/a25/development/phase0/SOLVER_COMPARISON.csv)、"
        "[INDEPENDENT_REFERENCE.json](results/a25/development/phase0/INDEPENDENT_REFERENCE.json)、"
        "[refinement](results/a25/development/phase0/REFERENCE_REFINEMENT_001.json)。")
    sections["FEEDBACK_HEADROOM.md"]=("# 完整反馈的成像余量\n\n"+theory+"\n\n"
        "在已公开开发对象上，L/F/R固定材料先验、共同初始化和K=3/6/12。"
        "完整χ误差可能被大背景掩盖，因此同时报告增量、实虚部、边缘、支撑IoU及完整场残差。"
        "相同观测下某个方法失败时保留其位置，不把成功图单独拼成配对。\n\n"+quality_tables+
        "\n\n三组记录采用不同的实验范围：TV×0.1同时改变所有方法的初始化与TV惩罚，振幅1.8保持原TV权重。"
        "追加探索不能替代冻结32条件的成像余量结果，也不修改神经网络原TV×1训练协议。\n\n"+
        bootstrap_table+"\nbootstrap只重采样四个已暴露parent cluster，区间是该开发集合的描述；"
        "不是独立holdout置信保证。聚合均值的相对改善和先算各parent相对改善再平均是不同统计量，分别保留。"
        "[原始parent bootstrap](results/a25/development/PAIRED_PARENT_BOOTSTRAP.json)。\n"+
        f"\n成像裁决来自父线程：{_fmt(_verdict(decision,'feedback_imaging'))}。\n\n"
        "原始来源：[METRICS.csv](results/a25/development/frozen_optimizer_repair/METRICS.csv)；"
        "图像是固定开发样例，不能当作新的ID/OOD泛化。")
    sections["CONVERGENCE_VS_RUNTIME.md"]=("# 收敛、相同K与完整推理时间\n\n"
        "一个更准的单次反馈动作不保证更快得到合格材料。比较先固定K，再观察达到共同质量目标所需的完整时间。"
        "online_s包含共同初始化和在线迭代；独立冷成本再加入一次已知背景准备与方法准备。"
        "离线完整场质量审核另列，不混入普通部署推理。共享试验真正只付一次的准备成本与单方法独立成本同时报告。\n\n"+
        timing_tables+"\n没有共同命中质量区域时，质量—时间散点只作描述。图中的非劣线只连接同一实验、同一K的"
        "已观察完整配对点，不是所有算法的最优速度边界。GPU缓存训练初始化"
        "不能作为部署已经免除初始化；完整cold/warm计时要实际加载缓存、重置状态、重算或单列初始化时间。\n\n"+
        _table(evidence['timing'],(("model_id","模型"),("mode","计时模式"),("status","原始status"),
            ("complete_image_seconds","完整秒"),("complete_image_cpu_seconds","完整host CPU秒"),
            ("certified_initialization_seconds","初始化秒"),
            ("file_read_and_model_cache_setup_seconds","读取与模型缓存准备秒"),
            ("image_only_seconds","仅网络图像秒"),("offline_audit_seconds","审计秒")))+
        f"\n部署裁决：{_fmt(_verdict(decision,'deployment'))}。")
    preparations=[]
    for experiment in evidence["experiments"]:
        for preparation_background in experiment["preparations"] if isinstance(experiment["preparations"],list) else []:
            if not isinstance(preparation_background,dict):continue
            for method,record in preparation_background.get("methods",{}).items():
                preparations.append({"experiment":experiment["id"],"background":preparation_background.get("background"),"method":method,
                                     "shared_s":preparation_background.get("shared_s"),"method_s":record.get("wall_s"),
                                     "status":record.get("status","RECORDED")})
    sections["CONVERGENCE_VS_RUNTIME.md"]+=("\n\n已知背景准备成本：\n\n"+
        _table(preparations,(("experiment","实验"),("background","背景"),("method","方法"),("shared_s","共享准备秒"),
                             ("method_s","方法准备秒"),("status","原始状态")))+
        "\n准备、online、offline audit的原始phase动作墙钟见[phase_costs.csv](results/a25/report/plot_data/phase_costs.csv)。"
        "phase未由上游单列的动作保持原标签；这些exclusive诊断时间不再次加到inclusive CPU/GPU资源费用。\n\n"
        "轨迹接受与重试统计来自原始HISTORIES，不从图像改善倒推优化成功：\n\n"+
        _table(history_rows,(("experiment","实验"),("method","方法"),("saved_trajectories","保存轨迹"),
            ("expected_trajectories","应有轨迹"),("saved_steps","保存更新"),("accepted_steps","接受更新"),
            ("unaccepted_steps","未接受更新"),("retried_steps","发生重试"),
            ("complete_12_step_histories","完整12步记录"))))
    sections["FEEDBACK_COMPRESSION_EXPLORATION.md"]=("# 压缩反馈准入与固定候选\n\n"
        "压缩的目的在于保留材料扰动到观测的合法传递。单看G_b的谱误差不足以知道图像会否丢失重要方向，"
        "需要独立forward、精确adjoint任务探针、梯度方向与同先验成像配对。R16/R24/R32、local和task-weighted是不同候选。\n\n"+
        candidate_table+f"\n开发准入原始状态：{admission.get('status','NOT_RUN')}；选择：{admission.get('selected','NOT_RUN')}。\n\n"
        "覆盖纠正：原协议TASK_AUDIT只检查32个历史开发case的K12终点，并未覆盖所有中间轨迹状态。"
        "TV×0.1检查其32个K12终点；振幅1.8检查16个K12终点。原始准入artifact中较宽的历史scope文字保留，"
        "实际builder状态、learned状态与OOD状态覆盖均为NOT_ESTABLISHED。\n\n"
        "开发域通过仍需Torch健康检查与独立新场景验证；只有父线程裁决决定进入学习的候选范围。"
        "探针构造使用已知背景，未知truth不进入因子构建；失败不因rank增加而抹去。\n\n"
        "原始来源：[TASK_AUDIT.csv](results/a25/development/frozen_optimizer_repair/TASK_AUDIT.csv)、"
        "[NN_CLOSURE_ADMISSION.json](results/a25/development/frozen_optimizer_repair/NN_CLOSURE_ADMISSION.json)。")
    for experiment in evidence["experiments"]:
        sections["FEEDBACK_COMPRESSION_EXPLORATION.md"]+=("\n\n### "+experiment["label"]+"的K12任务检查\n\n"+
            _table(_task_summary(experiment,config),(("method","候选"),("actual_ranks","实际rank"),
                ("ok_rows","OK终点"),("expected_rows","应有终点"),("complete","完整配对"),
                ("max_independent_transfer_error","最大forward误差"),
                ("max_independent_adjoint_error","最大adjoint误差"),
                ("min_gradient_cosine","最小梯度cosine"),
                ("max_independent_state_data_error","最大state-data误差")))+
            "追加探索的任务表描述本组终点，不重新选择NN closure或拓宽准入范围。")
    sections["FEEDBACK_REGIME_MAP.md"]=("# 反馈适用范围与证据域\n\n"
        "反馈强弱取决于已知背景、材料增量及观测方向的组合。以弱背景/ring背景、0.3/1.2对比度和clean/20dB"
        "组织开发记录，可以定位已观察到的适用范围；这张地图不外推到不同频率、网格、源顺序或三维模型。\n\n"
        "较大材料变化、背景重塑的参考场与TV平滑的影响，需要分别观察。以下每行先在同一parent内平均"
        "clean/20dB两条件，再对四个parent等权；F相对L的改善也先按parent计算，不以背景主导的完整χ误差替代增量误差。\n\n"+
        regime_table+"\n\n已保存的冻结假设："+_fmt(sanitizer(evidence["regime_freeze"].get("hypothesis","NOT_RUN")))+"。\n\n"
        "冻结范围："+_fmt(sanitizer(evidence["regime_freeze"].get("scope","NOT_RUN")))+"；限制："+
        _fmt(sanitizer(evidence["regime_freeze"].get("limits","NOT_RUN")))+"。"
        "这个regime来自已暴露开发对象，只构成需要独立匹配无NN实验检验的假设；不能先写成已验证泛化收益。\n\n"
        "来源：[REGIME_HYPOTHESIS_FREEZE.json](results/a25/development/REGIME_HYPOTHESIS_FREEZE.json)、"
        "[原始TV配对汇总](results/a25/development/PAIRED_TV_AND_REGIME.json)。\n\n"
        f"父线程压缩范围：{_fmt(_verdict(decision,'compression'))}。\n\n"
        "开发的额外1.8对比度标签与学习OOD的独立parents分别标注。训练64、validation16、ID16、OOD16"
        "各自按shell/asymmetric_piecewise/smooth/mixed_scale平衡；OOD每族两对象改变结构组合，另两对象"
        "保留ID几何分布而将对比度设为1.5/1.8。1.8幅度已用于历史开发探索，后续OOD报告不得称它为从未暴露的物理幅度。"
        "全部几何在manifest先冻结，未完成项标记NOT_RUN。")
    prospective=evidence.get("prospective_regime")
    if prospective is not None and prospective["artifact"]=="SUMMARY.json":
        summary,review=prospective["record"],prospective["review"]
        primary=summary.get("primary",{})
        interval=primary.get("ci95",[])
        interval_text="["+", ".join(_percent(value) for value in interval)+"]" if len(interval)==2 else "未记录"
        family_table=_table([{**row,"mean_gain_percent":_percent(row["mean_paired_relative_F_gain"])}
                            for row in prospective["details"]["family_rows"]],
            (("family","family"),("parent_count","parent数"),("paired_complete","完整配对"),
             ("L_delta","L增量NRMSE"),("F_delta","F增量NRMSE"),("TASK_R32_delta","TASK_R32增量NRMSE"),
             ("mean_gain_percent","平均parent配对改善")))
        compression=review.get("compression",{})
        prospective_compression_table=_table([compression],(("status","父线程范围裁决"),
            ("max_transfer_error","最大forward transfer误差"),("max_adjoint_error","最大adjoint误差"),
            ("min_gradient_cosine","最小梯度cosine；门槛0.99"),
            ("max_material_error_ratio_to_F","最大材料误差比TASK_R32/F"),("scope","实际覆盖")))
        interpretation=("父线程审阅支持这个限定条件下的正向改善，但没有确认最小10%改善；"
                        "它不是formal≥10%通过，也不是NN盲测PASS。"
                        if review.get("positive_improvement_supported") is True and review.get("minimum_10_percent_improvement_confirmed") is False
                        else "改善和阈值的最终解释以PARENT_REVIEW与最终gate decision为准。")
        compression_interpretation=("新范围的TASK_R32压缩gate失败：尽管forward transfer、adjoint与成像比值接近F，"
                                   "最小gradient cosine低于冻结0.99门槛。历史32个K12终点的通过记录仍保留，"
                                   "不能将它外推为本次validation范围通过，更不能外推到中间、learned或OOD状态。"
                                   if str(compression.get("status","")).startswith("FAIL") else "压缩范围以PARENT_REVIEW的原始status为准。")
        sections["FEEDBACK_REGIME_MAP.md"]+=("\n\n## 前瞻无NN验证补充：validation/development复用\n\n"
            "这项追加检验使用已生成validation16中的弱背景、振幅1.2、TV×0.1条件，比较L/F/TASK_R32。"
            "它复用validation/development数据，不属于锁定ID/OOD、神经网络测试或样本效率证据。"
            f"实际状态：{summary.get('status','NOT_RUN')}；完整parent数{primary.get('paired_parents','未记录')}，"
            f"条件数{summary.get('expected_conditions','未记录')}，OK逐步指标行{summary.get('observed_ok_rows','未记录')}。"
            "新增clean labels为0；这些labels此前已付费，新的估计审核、初始化、I/O和bootstrap均在新作业中计费。\n\n"
            "主指标先在各parent内平均clean/20dB误差，再计算F相对L改善，最后对16个parent等权。"
            f"其点估计为{_percent(primary.get('point_estimate'))}，已保存2000次parent bootstrap的95%区间为{interval_text}。"
            f"原始点目标状态{summary.get('hypothesis_point_target_status','NOT_RUN')}；区间相对10%目标为"
            f"{summary.get('ci95_vs_target','NOT_RUN')}。{interpretation}\n\n"
            f"次指标是两个parent等权误差均值的比值改善，为{_percent(review.get('ratio_of_parent_equal_mean_gain'))}。"
            "它与平均parent配对改善采用不同统计量，不能互换或用较大的一个替代另一个。\n\n"+
            _table(prospective["details"]["endpoints"],(("method","方法"),("complete_parents","完整parent"),
                ("coverage_complete","覆盖完整"),("delta_nrmse","增量NRMSE"),("material_nrmse","完整χ NRMSE"),
                ("quality_hits","共同质量命中"),("conditions","条件数")))+"\n\n"+
            family_table+"\n每family只有四parent；图中保留每个实际parent与均值，不生成未计算的family置信区间。"
            "重建图固定取每family最小parent ID的clean条件、K12，不按误差或视觉效果选图。\n\n"+
            prospective_compression_table+"\n"+compression_interpretation+"\n\n"
            "父线程保存的共同质量命中数："+_fmt(review.get("joint_quality_hits_out_of_32",{}))+"。"
            "三臂在32条件中均为0，仍不授予部署加速；online时间只作描述，不能当作匹配cold/warm速度证据。"
            "validation现在已暴露；NN仍NOT_RUN，locked ID/OOD仍CLOSED。\n\n"
            f"原始来源：[{prospective['artifact']}]({prospective['source']})、"
            "[PROVENANCE.json](results/a25/development/prospective_regime_validation/PROVENANCE.json)、"
            "[PARENT_REVIEW.json](results/a25/development/prospective_regime_validation/PARENT_REVIEW.json)、"
            "[CHECKPOINT_METRICS.csv](results/a25/development/prospective_regime_validation/CHECKPOINT_METRICS.csv)、"
            "[TASK_AUDIT.csv](results/a25/development/prospective_regime_validation/TASK_AUDIT.csv)、"
            "[八字段探索结果](research/development/PROSPECTIVE_REGIME_RESULT.md)。\n\n"
            f"[保存的重建arrays压缩包]({REPRODUCTION_DATA_ASSET})中的项目相对路径为"
            "`results/a25/development/prospective_regime_validation/arrays/*.npz`；图只读这些离线数组，不读取locked。")
        sections["FEEDBACK_COMPRESSION_EXPLORATION.md"]+=("\n\n## 新validation范围：梯度方向门槛失败\n\n"+
            prospective_compression_table+"\n"+compression_interpretation+
            "\n这次只增加弱背景、振幅1.2、TV×0.1的32个K12终点检查；旧历史范围的原始准入artifact保持原样。"
            "完整parent、family与图像记录见[前瞻regime补充](FEEDBACK_REGIME_MAP.md)。")
    elif prospective is not None:
        sections["FEEDBACK_REGIME_MAP.md"]+=("\n\n## 前瞻无NN验证来源登记\n\n"
            f"已保存[{prospective['artifact']}]({prospective['source']})，尚无SUMMARY；结果保持NOT_RUN。"
            "这项计划使用validation/development复用，不属于locked ID/OOD或神经网络证据。")
    sections["SOMNET_MIGRATION_PILOT.md"]=("# SOM-Net迁移与匹配学习pilot\n\n"
        "SOM-Net将电流更新展开为网络，再结合物理场和跨源材料更新。A25的N0是原文四层结构的迁移复现，"
        "不声称官方代码逐项复现。N1/N2/N3以共同材料、同一decoder和监督组成匹配实验："
        "N1采用L背景线性信息与明确梯度步，N2采用获准的R反馈closure与相同梯度步，"
        "N3使用L特征做generic learned recurrence，省去明确梯度步。N2不写成原生完整F，N3不写成压缩物理闭合。\n\n"
        "材料与current/data一致性同时计算；CNN为float32，物理为complex128/float64，"
        "状态相关物理梯度不默认detach。训练32为64的固定平衡子集；四parent batch各取一个固定seed抽取的条件，"
        "AdamW、学习率、监督权重、更新数和validation选择规则共享。更新数从500/1000/2000按实际GPU成本选定，"
        "不能通过看locked质量决定更新数。共同初始化由认证TV求解器完成；CNN块中的box与smooth-TV loss"
        "不构成原nonsmooth-TV目标的prox certificate，不能称网络各块已经数值认证。\n\n"+model_table+
        f"\nGPU健康原始状态：{evidence['health'].get('status','NOT_RUN')}；成本选择：{_fmt(sanitizer(evidence['updates']))}。\n\n"
        "health执行的是known-background硬件与自动微分检查；其更新、loss或有限性不构成训练、成像质量或样本效率证据。"
        f"已保存训练模型记录数：{len(model_rows)}；没有模型记录时训练为NOT_RUN。\n\n"+
        health_table+"\n\n"+health_cost_table+"\n\n"
        "采用的health索引及旧尝试保留依据："+_fmt(sanitizer(evidence["health_provenance"]))+"。\n\n"
        "两项已登记的runtime修改分别是集中读取parameter有限性predicate和CUDA blocking-sync等待策略；"
        "它们保持物理、网络、精度、同步检查和冻结容差，改善运行时的假设不转换成学习质量结论。"
        "[finite-guard登记](research/development/RUNTIME_PREREGISTRATION.md)、"
        "[blocking-wait登记](research/development/RUNTIME_BLOCKING_WAIT.md)。\n\n"
        "attempt005仅profile一次N2b3的known-background update；原始profile与receipt见"
        "[PROFILE_UPDATE.json](results/a25/jobs/a25-gpu-profile-retry-005/PROFILE_UPDATE.json)。"
        "budget.check的cProfile cumulative项是不可相加的主机WALL诊断，不是CPU费用组成，"
        "不能从完整耗时减去它宣称潜在提速。父线程保存的profile摘要："+
        _fmt(sanitizer(decision.get("runtime_profile",{"status":"NOT_RECORDED"})))+"。"
        "attempt004的一次SystemError与已计费终止记录保留；不将单次异常归因到模型、CUDA等待策略或有限性guard。"
        "[attempt004 receipt](results/a25/jobs/a25-gpu-profile-004/job_receipt.json)。\n\n"
        "已生成数据的原始状态："+_fmt(sanitizer(decision.get("physical_2d_data",{"status":"NOT_RECORDED"})))+"；"
        "累计新增clean labels："+_fmt(decision.get("new_clean_labels"))+" /456。"
        "生成112个独立parent及448个学习clean states不等于已经训练；另外8个开发state耗尽标签额度，"
        "失败与未用数据也计费。locked truth在实际评估前不公开。\n\n"
        f"学习裁决：{_fmt(_verdict(decision,'learning'))}；样本效率：{_fmt(_verdict(decision,'sample_efficiency'))}；"
        f"层数：{_fmt(_verdict(decision,'depth'))}。\n\n"+SOURCES)
    sections["EXPLORATION_LEDGER.md"]=("# 探索与失败账本\n\n"
        "探索记录需要同时说明假设、唯一变化、保持冻结的条件、预期指标、资源上限、实际结果、裁决和下一步。"
        "若有原始八字段记录，完整复制到报告数据，不能在探索结束后重写成主实验。缺少记录的计划写NOT_RUN；"
        "已有METRICS的追加开发实验则明确呈现真实输出，不因单独JSONL登记缺失而抹去。\n\n"+
        _table([{"experiment":experiment["id"],"scope":experiment["scope"],"saved_metric_rows":len(experiment["rows"]),
                 "saved_cases":len({r.get("case_id") for r in experiment["rows"]}),
                 "record_status":"SAVED_OUTPUTS" if experiment["rows"] else "NOT_RUN"}
                for experiment in evidence["experiments"]],
               (("experiment","实验"),("scope","唯一变化与冻结范围"),("saved_metric_rows","保存逐步指标行"),
                ("saved_cases","保存case数"),("record_status","记录状态")))+
        "\nTV与高振幅在输出前分别登记："
        "[TV单因素登记](research/development/TV_SINGLE_FACTOR_PREREGISTRATION.md)、"
        "[振幅登记](research/development/AMPLITUDE_PREREGISTRATION.md)。登记中的PENDING是历史原文，"
        "实际输出与裁决由对应结果和父线程decision另列，不改写登记。\n\n"
        f"当前失败账本保留{costs['failure_records']}个去重记录，来源位置随记录保存；"
        "所有FAILED、BUDGET_STOP和INTERRUPTED作业均计费。修复后的测试通过不删除早期失败，也不自动产生科学GO。\n\n"
        "来源：[FAILURE_LEDGER.jsonl](FAILURE_LEDGER.jsonl)、[探索原始导出](results/a25/report/plot_data/exploration.json)。")
    sections["LOCKED_VALIDATION.md"]=("# 一次locked ID/OOD验证\n\n"
        "独立parents用于检验新材料是否仍满足共享物理和已观察到的学习收益。validation用于训练选择；"
        "ID/OOD truth在全部11个模型checkpoint冻结之前关闭。MODEL_FREEZE与"
        "results/a25/learning/LOCKED_OPEN.json的一次性记录控制开启；"
        "failed cases保留空指标，不再次打开挑选测试结果。\n\n"
        f"已保存locked状态：{evidence['locked_summary'].get('status','NOT_RUN')}；"
        f"一次打开记录存在：{evidence['locked_open']}。父线程locked裁决：{_fmt(_verdict(decision,'locked_validation'))}。\n\n"
        f"OOD裁决：{_fmt(_verdict(decision,'OOD'))}；sample-efficiency/OOD/neural ablation没有实际完整输出时，图与结论保持NOT_RUN。\n\n"
        "每parent先平均两背景、两对比度、两noise条件，再对parents等权；2000次paired bootstrap重采样parent，"
        "不把同一个parent的8个条件当8个独立对象。缺配对、失败和区间不足会阻止对应科学结论。\n\n"
        "原始来源：[cases.csv](results/a25/learning/locked_evaluation/cases.csv)、"
        "[parent_summary.json](results/a25/learning/locked_evaluation/parent_summary.json)、"
        "[paired_bootstrap.json](results/a25/learning/locked_evaluation/paired_bootstrap.json)、"
        "[timing.csv](results/a25/learning/locked_evaluation/timing.csv)。未生成的来源为NOT_RUN。")
    sections["A25_FINAL_RESEARCH_DECISION.md"]=("# A25最终研究裁决\n\n"
        "最终判断由父线程写入[A25_GATE_DECISION.json](results/a25/A25_GATE_DECISION.json)。"
        "本报告逐项呈现该文件，不从单幅图、单元测试、任务误差或某个成功子集自动生成GO。\n\n"+
        f"父线程总体状态：{decision.get('status','NOT_REVIEWED')}。\n\n"+verdict_table+
        f"\n下一步：{_fmt(sanitizer(decision.get('next_step',decision.get('next_stage','NOT_REVIEWED'))))}。\n\n"+
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
        _write_csv(root/"results/a25/report/plot_data/input_inventory.csv",evidence["input_inventory"])
        for experiment in evidence["experiments"]:
            destination=root/"results/a25/report/plot_data"
            name=experiment["id"]
            _write_csv(destination/(name+"_parent_equal.csv"),experiment["summary"])
            _write_csv(destination/(name+"_convergence.csv"),experiment["convergence_summary"])
            _write_csv(destination/(name+"_pareto.csv"),_pareto_points(experiment["summary"]))
            _write_csv(destination/(name+"_regimes.csv"),experiment["regimes"])
            _write_csv(destination/(name+"_task_raw.csv"),sanitizer(experiment["task_rows"]))
            _write_csv(destination/(name+"_history_summary.csv"),_history_summary(experiment,config))
        write_json(root/"results/a25/report/plot_data/development_bootstrap.json",sanitizer(evidence["development_bootstrap"]))
        write_json(root/"results/a25/report/plot_data/regime_hypothesis_freeze.json",sanitizer(evidence["regime_freeze"]))
        write_json(root/"results/a25/report/plot_data/health_attempts.json",sanitizer(evidence["health_attempts"]))
        prospective=evidence.get("prospective_regime")
        if prospective is not None:
            for name,key in (("prospective_parent_paired","parent_rows"),("prospective_family_paired","family_rows"),
                             ("prospective_K12_endpoints","endpoints")):
                _write_csv(root/"results/a25/report/plot_data"/(name+".csv"),prospective["details"][key])
            _write_csv(root/"results/a25/report/plot_data/prospective_task_raw.csv",sanitizer(prospective["task_rows"]))
            write_json(root/"results/a25/report/plot_data/prospective_parent_review.json",sanitizer(prospective["review"]))
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
            f"[最终裁决](A25_FINAL_RESEARCH_DECISION.md) · [完整动作账本Release压缩包]({ACTION_LEDGERS_ASSET}) · "
            "[失败](FAILURE_LEDGER.jsonl)\n\n"+
            _table([{"question":k,**_verdict(decision,k)} for k in ('solver_health','feedback_imaging','compression','learning','sample_efficiency','OOD','depth','locked_validation','deployment')],
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
            "parent_gate_schema":"nested gates with compression/depth aliases; top-level legacy fallback",
            "development_experiments":[spec["id"] for spec in DEVELOPMENT_EXPERIMENTS],
            "task_probe_state_scope":"historically exposed K12 endpoints only; no learned/OOD-state claim",
            "locked_truth_public_before_evaluation":False,
            "scientific_verdict_generated_by_reporter":False,"plots_use_only_saved_arrays":True}
        write_json(root/"results/a25/report/ARTIFACT_AUDIT.json",audit)
    return {"status":"REPORT_WRITTEN", "documents":list(DOCUMENTS)+["README.md","A25_RESEARCH_REPORT_ZH.md"],
            "cost_ledger":"COST_LEDGER.jsonl","failure_ledger":"FAILURE_LEDGER.jsonl",
            "accepted_cpu_seconds":costs['accepted_cpu_seconds'],"accepted_gpu_seconds":costs['accepted_gpu_seconds'],
            "figures":figures,"decision_source":audit['parent_decision_source'],
            "pending_inputs":[row for row in evidence["input_inventory"] if row["status"]!="PRESENT"],
            "limitations":["parent scientific verdict only","live report tail provisional until accepted receipt"]}


report = generate_report
