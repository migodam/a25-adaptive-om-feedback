"""Independent, fixed-certificate solver repair on archived measurements."""
from __future__ import annotations
import dataclasses,json,time
from pathlib import Path
import numpy as np
from scipy import linalg as la
from a20.costs import write_json, BudgetExceeded
from a24.contracts import mass_pack,pack,online_config
from a24.physics import Physics2D
from a24.relative_feedback import ReferenceCache
from a24.cases import backgrounds
from a24.pilot import prepare_background,write_csv
from .campaign import ROOT,OUT,prox_problem,failure
from .prox import solve_prox

def run_phase0(config,book):
    from .socp_reference import solve_socp_reference
    out=OUT/'phase0';out.mkdir(parents=True,exist_ok=True)
    (out/'inputs').mkdir(exist_ok=True);(out/'reference').mkdir(exist_ok=True)
    oldfails=[json.loads(l) for l in (ROOT/'results/b0/FAILURE_LEDGER.jsonl').read_text().splitlines()]
    required=[d['case_id'] for d in oldfails if d.get('phase')=='common_initialization']
    controls=['weak_2401_0.3_zero'];selected_refs=['ring_2401_1.2_zero','ring_2402_1.2_snr20',
        'ring_2403_0.3_zero','ring_2404_1.2_snr20','weak_2401_0.3_zero','active_box']
    phys=Physics2D(grid=config['grid'],book=book,config=online_config(config));inputs={}
    for bgname,bg in backgrounds(phys.points,config).items():
        cache=ReferenceCache(phys,bg,book=book,config=online_config(config));prep=prepare_background(cache,book,config)
        xb=mass_pack(bg,phys.volume)
        for case in required+controls:
            if not case.startswith(bgname+'_'):continue
            with np.load(ROOT/'results/b0/data/online'/f'{case}.npz',allow_pickle=False) as f:
                measured=f['data'];sigma=float(f['sigma'])
            lam=.01*(1+sigma/prep['beta']);v=xb-prep['step']*prep['J'].T@pack(cache.yb-measured)/prep['data_norm2']
            inputs[case]=prox_problem(v,xb,prep['step']*lam,phys,config,case)
        if bgname=='weak':
            rng=np.random.default_rng(251008091)
            # Explicit synthetic optimizer control, never called Maxwell evidence.
            v=xb+np.sqrt(phys.volume)*np.r_[4.5+.2*rng.normal(size=phys.N),-.1+.2*rng.normal(size=phys.N)]
            inputs['active_box']=prox_problem(v,xb,.005,phys,config,'active_box')
    for case,problem in inputs.items():
        np.savez_compressed(out/'inputs'/f'{case}.npz',v=problem.v,background=problem.background,
                            weight=problem.weight,volume=problem.volume,grid_shape=problem.grid_shape)
    rows=[];solutions={};summary={}
    def run_method(method):
        successful=True;elapsed=0.
        for case,problem in inputs.items():
            cfg={**config,'prox_algorithm':method,'algorithm':method,'prox_max_iter':2000 if method=='old_pdhg' else 20000,
                 'prox_raise_on_failure':False,'fgp_authorized':method=='fgp'}
            p=dataclasses.replace(problem,config=cfg)
            result=solve_prox(p,budget=book);solutions[(method,case)]=result
            rows.append({'case_id':case,'algorithm':method,**result.metadata})
            successful&=result.converged;elapsed+=result.metadata['elapsed_seconds']
            write_csv(out/'SOLVER_COMPARISON.csv',rows)
            if not result.converged:
                failure(book,phase='solver_comparison',case=case,method=method,meta=result.metadata)
        summary[method]={'all_certified':bool(successful),'sum_prox_wall_s':elapsed,
                         'certified':sum(solutions[(method,c)].converged for c in inputs),'required':len(inputs)}
    run_method('old_pdhg');run_method('extended_pdhg');run_method('accelerated_pdhg')
    if not summary['extended_pdhg']['all_certified'] and not summary['accelerated_pdhg']['all_certified']:
        run_method('fgp')
    candidates=[m for m in summary if m!='old_pdhg' and summary[m]['all_certified']]
    if not candidates:
        decision={'status':'UNHEALTHY','solvers':summary,'required':required,'independent_reference':'NOT_RUN_NO_CERTIFIED_CANDIDATE'}
        write_json(out/'DECISION.json',decision);return decision
    winner=min(candidates,key=lambda m:(summary[m]['sum_prox_wall_s'],m))
    refs=[];allreference=True
    for case in selected_refs:
        problem=inputs[case];reference=solve_socp_reference(problem,budget=book,comparison=solutions[(winner,case)])
        meta=reference.metadata
        x=solutions[(winner,case)].x
        reference_obj=meta.get('objective',meta.get('primal_objective'))
        refgap=meta.get('normalized_gap',meta.get('primal_dual_gap',0.))
        distance=float(la.norm(x-reference.x))
        # Strong convexity yields a legitimate finite-accuracy comparison.
        allowance=meta.get('robust_primal_distance_allowance')
        agree=bool(reference.converged and allowance is not None and distance<=allowance
                   and meta.get('objective_agreement_passed'))
        allreference&=agree
        refs.append({'case_id':case,**meta,'comparison_distance':distance,'gap_distance_allowance':allowance,
                     'comparison_agrees':agree,'winner_objective':solutions[(winner,case)].metadata['objective']})
        arrays={'x':reference.x,'p':reference.p}
        for name in ('lower_dual','upper_dual','lower_multipliers','upper_multipliers'):
            if hasattr(reference,name):arrays[name]=getattr(reference,name)
        np.savez_compressed(out/'reference'/f'{case}.npz',**arrays)
        if not agree:failure(book,phase='independent_socp',case=case,meta=meta,distance=distance,allowance=allowance)
        write_json(out/'INDEPENDENT_REFERENCE.json',refs)
    decision={'status':'HEALTHY' if allreference else 'UNHEALTHY','solver':winner,'solvers':summary,
        'independent_agreement':allreference,'references':selected_refs,'old_initial_failures':len(required),
        'born_failures':'REPLAY_IN_PHASE1_REQUIRED','scope':'public TV prox numerical certification; physical strong pairs next',
        'tolerances_unchanged':True,'fixed_certificate_step':.99/(2*np.sqrt(2))}
    write_json(out/'DECISION.json',decision);return decision
