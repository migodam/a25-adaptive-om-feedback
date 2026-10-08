"""One owner, metered GPU stage; locked evaluation is never automatic."""
import time
IMPORT_WALL,IMPORT_CPU=time.perf_counter(),time.process_time()
import argparse,json,copy,gc,os
os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG',':4096:8')
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ.setdefault(key,'1')
from pathlib import Path
from a25.budget import charged_job,budget_history,write_json
from a24.contracts import active_ledger,ForbiddenAccess
from a25.training import (configure_torch,load_references,benchmark_health,select_update_budget,
                          ParentDataset,fit_normalizer,train_one)
p=argparse.ArgumentParser();p.add_argument('--stage',choices=['health','train','locked'],required=True)
p.add_argument('--job',required=True);p.add_argument('--device',default='cuda')
p.add_argument('--config',default='configs/a25/nn_admitted.json');args=p.parse_args()
root=Path(__file__).resolve().parents[1];cfg=json.loads((root/args.config).read_text())
if cfg.get('nn_physics_admitted') is not True:raise ForbiddenAccess('PHYSICS_CLOSURE_NOT_ADMITTED')
out=root/'results/a25/learning';out.mkdir(parents=True,exist_ok=True)
with charged_job(root,args.job,device=args.device,config=cfg,metadata={'stage':'learning_'+args.stage}) as book,active_ledger(book):
    book.started_wall=min(book.started_wall,IMPORT_WALL);book.started_cpu=min(book.started_cpu,IMPORT_CPU)
    configure_torch(cfg['master_seed'],args.device)
    refs=load_references({k:root/'data/background'/f'{k}.npz' for k in ('weak','ring')},book=book,config=cfg,device=args.device)
    if args.stage=='health':
        health=benchmark_health(refs,config=cfg,book=book,device=args.device,repeats=2)
        write_json(out/'GPU_HEALTH.json',health)
        wall,process,cpu=book.elapsed()
        # Keep explicit audit/report and validation reserves, alongside the
        # per-phase allocation. Only cost enters this choice.
        remaining_cpu=min(3000.,book.cpu_limit-book.prior_cpu-cpu-300.)
        remaining_gpu=min(9900.,book.gpu_limit-book.prior_gpu-wall-1800.)
        choice=select_update_budget(health,config=cfg,cpu_available=remaining_cpu,gpu_available=remaining_gpu)
        choice.update(available_cpu_seconds=remaining_cpu,available_gpu_seconds=remaining_gpu,
                      health_job=args.job,test_truth_opened=False)
        write_json(out/'COST_SELECTED_UPDATES.json',choice)
        print(json.dumps(choice))
    elif args.stage=='train':
        selection=json.loads((out/'COST_SELECTED_UPDATES.json').read_text())
        if selection.get('status')!='COST_SELECTED':raise ForbiddenAccess('MATCHED_UPDATE_BUDGET_NOT_ADMITTED')
        manifest=json.loads((root/'data/manifest.json').read_text())
        validation=ParentDataset.from_npz(root/'data/validation.npz',role='validation')
        trained=[]
        for size in (32,64):
            train=ParentDataset.from_npz(root/'data/train.npz',role='train',parent_ids=manifest['train'+str(size)])
            normalizer=fit_normalizer(refs,train,config=cfg,book=book,device=args.device)
            kinds=['N0','N1','N2','N3'];shift=(size//32-1)%4;kinds=kinds[shift:]+kinds[:shift]
            for kind in kinds:
                name=kind+'_train'+str(size)+'_b'+str(4 if kind=='N0' else 3)
                with book.scope(name):
                    record=train_one(kind,refs,train,validation,updates=selection['updates'],config=cfg,
                        out=out/name,book=book,blocks=4 if kind=='N0' else 3,normalizer=normalizer,device=args.device)
                trained.append(record);write_json(out/'TRAINED_MODELS.json',trained);gc.collect()
        for kind in ('N1','N2','N3'):
            name=kind+'_train64_b4'
            with book.scope(name):
                record=train_one(kind,refs,train,validation,updates=selection['updates'],config=cfg,
                    out=out/name,book=book,blocks=4,normalizer=normalizer,device=args.device)
            trained.append(record);write_json(out/'TRAINED_MODELS.json',trained);gc.collect()
        print(json.dumps({'status':'ALL_11_MATCHED_MODELS_TRAINED','updates':selection['updates']}))
    else:
        from a25.locked_evaluation import run_locked
        result=run_locked(root,cfg,book,device=args.device)
        print(json.dumps(result))
