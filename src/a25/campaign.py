"""A25 sequential experiments; evaluators never enter proposal interfaces."""
from __future__ import annotations
import csv, json, time, traceback, copy
from dataclasses import replace
from pathlib import Path
import numpy as np
from scipy import linalg as la
from a20.costs import BudgetExceeded, write_json, plain
from a24.contracts import OnlineObservation, mass_pack, mass_unpack, pack, online_config, NumericalFailure
from a24.physics import Physics2D
from a24.relative_feedback import ReferenceCache, RelativeFeedbackModel, LocalBlocks
from a24.pilot import prepare_background, loss_value, task_audit, evaluate_image, write_csv as _legacy_write_csv
from a24.cases import backgrounds, material_pattern, noisy_observation

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'results/a25/development'

def write_csv(path,rows):
    path=Path(path);temp=path.with_suffix(path.suffix+'.tmp')
    _legacy_write_csv(temp,rows);temp.replace(path)

def runtime_config(config):
    keys=('prox_algorithm','algorithm','prox_wall_limit_seconds','prox_feasibility_tolerance',
          'fgp_authorized','reference_refinement','rom_rank')
    return {**online_config(config),**{k:config[k] for k in keys if k in config}}

def failure(book, **row):
    row=plain(row)
    path=ROOT/'FAILURE_LEDGER.jsonl'
    with path.open('a') as f: f.write(json.dumps(row,allow_nan=False)+'\n')
    book.append({'event':'failure',**row})

def prox_problem(v, xb, weight, phys, config, owner):
    from .prox import ProxProblem
    return ProxProblem(v=v,background=xb,weight=weight,grid_shape=(phys.grid,)*2,
                       volume=phys.volume,config=runtime_config(config),owner_id=owner)

def initialize(cache, obs, prep, config, book, solver, owner, tv_multiplier=1.):
    from .prox import solve_prox
    xb=mass_pack(cache.chi_b,cache.physics.volume)
    lam=.01*(1+obs.sigma/prep['beta'])*tv_multiplier
    with book.span('common_initialization'):
        gradient=prep['J'].T@pack(cache.yb-obs.data)/prep['data_norm2']
        cfg={**config,'prox_algorithm':solver,'algorithm':solver}
        problem=prox_problem(xb-prep['step']*gradient,xb,prep['step']*lam,cache.physics,cfg,owner)
        result=solve_prox(problem,budget=book)
    if not result.metadata['converged']:
        e=NumericalFailure('A25_INITIALIZATION_NOT_CERTIFIED');e.meta=result.metadata;raise e
    return result.x,lam,result.warm_state,result.metadata

def trajectory(model,obs,x0,lam,warm0,prep,config,book,solver,owner):
    """Measurement/background only. All arms receive independent warm-state copies."""
    from .prox import solve_prox
    phys=model.physics;xb=mass_pack(model.cache.chi_b,phys.volume)
    x=x0.copy();warm=copy.deepcopy(warm0);states=[];history=[]
    before=book.snapshot();started=time.perf_counter()
    with book.span('online_trajectory'):
        state=model.forward(mass_unpack(x,phys.volume))
        for iteration in range(1,config['blocks']+1):
            book.check();old,dl,tv=loss_value(model,state,obs,prep,x,xb,lam,config)
            with book.span('material_gradient'):
                gradient=model.adjoint(state.chi,pack(state.data-obs.data),state)/prep['data_norm2']
            trials=[];accepted=False
            for retry in range(config['max_half_step_retry']+1):
                step=prep['step']/2**retry
                cfg={**config,'prox_algorithm':solver,'algorithm':solver}
                problem=prox_problem(x-step*gradient,xb,step*lam,phys,cfg,owner)
                result=solve_prox(problem,warm_state=warm,budget=book)
                if not result.metadata['converged']:
                    e=NumericalFailure('A25_PROX_NOT_CERTIFIED');e.meta=result.metadata;raise e
                trial=model.forward(mass_unpack(result.x,phys.volume))
                new,nd,nt=loss_value(model,trial,obs,prep,result.x,xb,lam,config)
                ok=new<=old+1e-12*max(1.,abs(old))
                trials.append({'retry':retry,'step':step,'objective':new,'data_loss':nd,'tv':nt,
                               'prox':result.metadata,'accepted':ok,'margins':trial.margins})
                if ok:
                    x=result.x;state=trial;warm=result.warm_state;accepted=True;break
            history.append({'iteration':iteration,'old_objective':old,'accepted':accepted,
                            'trials':trials,'online_elapsed_s':time.perf_counter()-started})
            states.append({'iteration':iteration,'chi':mass_unpack(x,phys.volume).copy(),
                           'online_s':time.perf_counter()-started,'accepted':accepted,
                           'cost':book.delta(before)})
    return states,history,time.perf_counter()-started

def task_weighted(cache,config,book):
    """One frozen background-probe range; no test material or oracle information."""
    from scipy.ndimage import gaussian_filter
    rng=np.random.default_rng(config['master_seed']+537)
    with book.span('task_weighted_background_range'):
        probes=[]
        for _ in range(4):
            h=gaussian_filter(rng.standard_normal((cache.physics.grid,)*2),1.)
            h=h.reshape(-1);h/=la.norm(h)
            probes.append(h[:,None]*cache.eb)
        material=np.concatenate(probes,axis=1)
        loads=(rng.standard_normal((cache.physics.q,8))+1j*rng.standard_normal((cache.physics.q,8)))/np.sqrt(2)
        observed=cache.apply_db(loads,adjoint=True)
        Y=np.concatenate([cache.gb(material),cache.gb(observed)],axis=1)
        Q=la.qr(Y,mode='economic')[0]
        B=cache.gb(Q,adjoint=True).conj().T
        u,s,vh=la.svd(B,full_matrices=False)
        r=min(32,int(np.sum(s>s[0]*config['orthogonal_rank_rtol'])))
        model=RelativeFeedbackModel(cache,'R',rank=0,config=runtime_config(config))
        model.Ug=(Q@u[:,:r])*np.sqrt(s[:r]);model.Vg=vh[:r].conj().T*np.sqrt(s[:r])
        model.rank=model.actual_rank=r
        book.counts['task_weighted_material_probe_RHS']+=material.shape[1]
        book.counts['task_weighted_receiver_load_RHS']+=loads.shape[1]
    return model

def build_models(cache,config,book):
    definitions={'L':('L',16,False),'F':('F',16,False),'R16':('R',16,False),
        'R24':('R',24,False),'R32':('R',32,False),'LOCAL_R16':('R',16,True),
        'AFFINE_ROM32':('ROM',32,False),'BORN_TV':('BORN',16,False)}
    models={};setups={}
    for method in config['methods']:
        t=time.perf_counter();snap=book.snapshot()
        try:
            with book.scope('background_only_method_setup'):
                if method=='TASK_R32': model=task_weighted(cache,config,book)
                else:
                    kind,rank,local=definitions[method]
                    model=RelativeFeedbackModel(cache,kind,rank=rank,local=local,
                        seed=config['control_seed']+(cache.chi_b.real.max()>1),config=runtime_config(config))
            models[method]=model;setups[method]={'wall_s':time.perf_counter()-t,'cost':book.delta(snap)}
        except BudgetExceeded:raise
        except Exception as e:
            failure(book,phase='setup',method=method,error=repr(e));setups[method]={'status':'FAILED'}
    return models,setups

def augmented_metrics(phys,truth,chi,bg,full_state,obs,clean,config):
    from a24.material_updates import _gradient
    got=evaluate_image(phys,truth,chi,bg,full_state,obs,clean,config)
    delta=truth-bg;estimate=chi-bg
    got['delta_real_nrmse']=float(la.norm((estimate-delta).real)/max(la.norm(delta.real),1e-12))
    got['delta_imag_nrmse']=float(la.norm((estimate-delta).imag)/max(la.norm(delta.imag),1e-12))
    gt=_gradient(mass_pack(delta,phys.volume),(phys.grid,)*2)
    gp=_gradient(mass_pack(estimate,phys.volume),(phys.grid,)*2)
    got['edge_nrmse']=float(la.norm(gp-gt)/max(la.norm(gt),1e-12))
    region=config['quality_region']
    dataok=(got['full_data_white_residual']<=region['noisy_white_residual_max_factor']*np.sqrt(2*phys.q*phys.s)
            if obs.sigma>0 else got['full_data_relative_residual']<=region['noiseless_relative_residual_max'])
    got['quality_target_hit']=bool(got['material_nrmse']<=region['full_chi_nrmse_max'] and
        got['delta_nrmse']<=region['delta_nrmse_max'] and dataok)
    return got

def headroom(config,book,solver,*,experiment='frozen_optimizer_repair',retry=None,tv_multiplier=1.,extra=False):
    """Single-factor experiments only; frozen background step/prior by default."""
    out=OUT/experiment;out.mkdir(parents=True,exist_ok=True)
    (out/'images').mkdir(exist_ok=True)
    cfg={**config,'max_half_step_retry':config['max_half_step_retry'] if retry is None else retry}
    rows=[];tasks=[];histories=[];preparations=[]
    phys=Physics2D(grid=cfg['grid'],book=book,config=online_config(cfg))
    for bi,(bgname,bg) in enumerate(backgrounds(phys.points,cfg).items()):
        begin=time.perf_counter()
        cache=ReferenceCache(phys,bg,book=book,config=online_config(cfg));prep=prepare_background(cache,book,cfg)
        shared_s=time.perf_counter()-begin;phys._evaluation_yb=cache.yb
        models,setups=build_models(cache,cfg,book)
        preparations.append({'background':bgname,'shared_s':shared_s,'methods':setups})
        for parent in cfg['parents']:
            for amp in ([1.8] if extra else cfg['amplitudes']):
                lp=ROOT/'results/b0/data/offline'/f'{bgname}_{parent}_{amp}.npz'
                if extra:
                    lp=OUT/'extra_clean'/lp.name;lp.parent.mkdir(exist_ok=True)
                    if not lp.exists():
                        book.reserve('new_clean_labels',456)
                        truth=bg+amp*material_pattern(phys.points,parent,cfg)
                        clean=phys.full_state(truth).data
                        np.savez_compressed(lp,truth=truth,clean=clean)
                with book.span('offline_cache_load'):
                    with np.load(lp,allow_pickle=False) as f:truth=f['truth'];clean=f['clean']
                for ni,noise in enumerate(cfg['noise_snr_db']):
                    case=f'{bgname}_{parent}_{amp}_{"zero" if noise is None else "snr20"}'
                    if not extra:
                        with np.load(ROOT/'results/b0/data/online'/f'{case}.npz',allow_pickle=False) as f:
                            obs=OnlineObservation(f['data'],float(f['sigma']),case)
                    else:
                        data,sigma,_=noisy_observation(clean,cache.yb,noise,
                            np.random.default_rng(np.random.SeedSequence([cfg['master_seed'],bi,parent,180,ni])))
                        obs=OnlineObservation(data,sigma,case)
                    try:
                        t=time.perf_counter();x0,lam,warm,initial=initialize(cache,obs,prep,cfg,book,solver,case,tv_multiplier)
                        init_s=time.perf_counter()-t
                    except BudgetExceeded:raise
                    except Exception as e:
                        failure(book,phase='headroom_initial',case=case,experiment=experiment,error=repr(e),meta=getattr(e,'meta',None))
                        for method in cfg['methods']:
                            for k in cfg['checkpoints']:
                                rows.append({'case_id':case,'parent_id':parent,'background':bgname,'amplitude':amp,
                                    'noise_db':noise,'method':method,'K':k,'status':'COMMON_INITIALIZATION_FAILED'})
                        write_csv(out/'METRICS.csv',rows);continue
                    order=list(cfg['methods']);shift=(parent+ni+bi)%len(order);order=order[shift:]+order[:shift]
                    for method in order:
                        base={'case_id':case,'parent_id':parent,'background':bgname,'amplitude':amp,'noise_db':noise,
                              'method':method,'tv_multiplier':tv_multiplier,'max_half_step_retry':cfg['max_half_step_retry']}
                        if method not in models:
                            rows.extend([{**base,'K':k,'status':'SETUP_FAILED'} for k in cfg['checkpoints']]);continue
                        model=models[method]
                        try:
                            method_owner=case+':'+method
                            forked=replace(copy.deepcopy(warm),owner_id=method_owner)
                            states,history,elapsed=trajectory(model,obs,x0,lam,forked,prep,cfg,book,solver,method_owner)
                            histories.append({**base,'history':history,'initial':initial})
                            for record in states:
                                with book.scope('offline_image_audit'):
                                    full=phys.full_state(record['chi'])
                                    metrics=augmented_metrics(phys,truth,record['chi'],bg,full,obs,clean,cfg)
                                row={**base,**metrics,'K':record['iteration'],'status':'OK',
                                    'online_s':init_s+record['online_s'],'shared_setup_s':shared_s,
                                    'method_setup_s':setups[method]['wall_s'],'accepted':record['accepted'],
                                    'accepted_total':sum(h['accepted'] for h in history[:record['iteration']]),
                                    'current_rank':model.actual_rank,'cost':record['cost']}
                                rows.append(row)
                                if record['iteration'] in cfg['checkpoints']:
                                    np.savez_compressed(out/'images'/f'{case}_{method}_K{record["iteration"]}.npz',
                                        chi=record['chi'],truth=truth,background=bg,data=obs.data,clean=clean)
                            if model.kind in ('R','ROM'):
                                with book.scope('offline_fidelity_admission'):
                                    audit=task_audit(model,models['F'],states[-1]['chi'],obs,cfg,book)
                                tasks.append({**base,**audit,'status':'OK'})
                        except BudgetExceeded:raise
                        except Exception as e:
                            failure(book,phase='trajectory',experiment=experiment,**base,error=repr(e),meta=getattr(e,'meta',None))
                            rows.extend([{**base,'K':k,'status':'FAILED','error':repr(e)} for k in cfg['checkpoints']])
                        write_csv(out/'METRICS.csv',rows);write_csv(out/'TASK_AUDIT.csv',tasks)
                        write_json(out/'HISTORIES.json',histories);write_json(out/'PREPARATIONS.json',preparations)
    return {'status':'COMPLETE','experiment':experiment,'rows':len(rows),'tasks':len(tasks)}
