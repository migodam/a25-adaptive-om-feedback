"""Transparent equal-parent summaries and pre-training admission decisions."""
from __future__ import annotations
from pathlib import Path
import csv,json
import numpy as np
from a20.costs import write_json
from a24.pilot import write_csv
from .campaign import OUT,ROOT

def records(path):
    with Path(path).open() as f:return list(csv.DictReader(f))

def num(row,key):
    try:return float(row[key])
    except (KeyError,TypeError,ValueError):return float('nan')

def summarize(experiment='frozen_optimizer_repair'):
    path=OUT/experiment;rows=records(path/'METRICS.csv');table=[]
    for method in sorted({r['method'] for r in rows}):
        for k in (3,6,12):
            selected=[r for r in rows if r['method']==method and num(r,'K')==k]
            byparent={p:[r for r in selected if r['parent_id']==p] for p in sorted({r['parent_id'] for r in rows})}
            values={key:[] for key in ('delta_nrmse','material_nrmse','online_s','edge_nrmse','support_iou','full_data_relative_residual')}
            complete=all(len(v)==8 and all(r['status']=='OK' for r in v) for v in byparent.values())
            for p,v in byparent.items():
                for key in values:
                    a=[num(r,key) for r in v]
                    values[key].append(float(np.mean(a)) if len(a)==8 and all(np.isfinite(a)) else None)
            table.append({'method':method,'K':k,'paired_complete':complete,'cases':len(selected),
                'failed_or_missing':32-sum(r['status']=='OK' for r in selected),
                **{key:float(np.mean(v)) if all(x is not None for x in v) else None for key,v in values.items()},
                'quality_hits':sum(r.get('quality_target_hit')=='True' for r in selected)})
    write_csv(path/'PARENT_EQUAL_SUMMARY.csv',table);return table

def admission(config,experiment='frozen_optimizer_repair'):
    """Never infer admission from successful-only rows or transfer alone."""
    path=OUT/experiment;rows=records(path/'METRICS.csv');tasks=records(path/'TASK_AUDIT.csv')
    entries=[]
    for method in ('R16','R24','R32','LOCAL_R16','TASK_R32'):
        selected=[r for r in rows if r['method']==method and num(r,'K')==12]
        audits=[r for r in tasks if r['method']==method]
        image_ratios=[];times=[]
        for r in selected:
            matches=[f for f in rows if f['method']=='F' and f['case_id']==r['case_id'] and num(f,'K')==12]
            if r['status']=='OK' and len(matches)==1 and matches[0]['status']=='OK':
                image_ratios.append(num(r,'delta_nrmse')/num(matches[0],'delta_nrmse'))
                times.append(num(r,'online_s')/num(matches[0],'online_s'))
        complete=len(selected)==len(audits)==len(image_ratios)==32 and all(r['status']=='OK' for r in audits)
        transfer=max([num(r,'independent_transfer_error') for r in audits],default=float('inf'))
        adjoint=max([num(r,'independent_adjoint_error') for r in audits],default=float('inf'))
        cosine=min([num(r,'gradient_cosine') for r in audits],default=-float('inf'))
        degradation=max(image_ratios,default=float('inf'))
        # Cost does not grant acceleration. An admitted NN closure is bounded,
        # and its complete cost must remain subject to the GPU health benchmark.
        eligible=complete and transfer<=.05 and adjoint<=.05 and cosine>=.99 and degradation<=1.05
        entries.append({'method':method,'complete':complete,'max_transfer_error':transfer,'max_adjoint_error':adjoint,
            'min_gradient_cosine':cosine,'max_delta_image_ratio_vs_F':degradation,
            'median_online_time_ratio_vs_F':float(np.median(times)) if times else None,
            'eligible_physics':eligible,'deployment_acceleration':'NOT_ESTABLISHED'})
    admitted=[r for r in entries if r['eligible_physics']]
    winner=min(admitted,key=lambda r:(r['median_online_time_ratio_vs_F'],r['method']))['method'] if admitted else None
    decision={'status':'ADMITTED_PENDING_TORCH_HEALTH' if winner else 'NO_ADMITTED_CLOSURE',
        'selected':winner,'candidates':entries,'scope':'four exposed development parents, observed reconstruction trajectory',
        'truth_used_in_builder':False,'new_scene_generalization':'NOT_ESTABLISHED'}
    write_json(path/'NN_CLOSURE_ADMISSION.json',decision);return decision
