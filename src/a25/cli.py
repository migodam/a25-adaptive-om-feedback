"""A25 metered entry points: no hidden expansion or automatic locked test."""
from __future__ import annotations
import argparse, contextlib, io, json, os, platform, sys, traceback, unittest
from pathlib import Path
from a20.costs import plain, write_json
from a24.contracts import active_ledger
from .budget import charged_job, budget_history
ROOT=Path(__file__).resolve().parents[2]

def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument('command',choices=['tests','solver','headroom','generate','health','train','locked','report'])
    p.add_argument('--job',required=True);p.add_argument('--config',default='configs/a25/campaign.json')
    p.add_argument('--experiment',default='frozen_optimizer_repair');p.add_argument('--retry',type=int)
    p.add_argument('--tv-multiplier',type=float,default=1.);p.add_argument('--extra',action='store_true')
    p.add_argument('--device',default='cpu',choices=['cpu','cuda']);p.add_argument('--test-pattern',default='test*.py')
    args=p.parse_args(argv);config=json.loads((ROOT/args.config).read_text())
    try:
        with charged_job(ROOT,args.job,device=args.device,config=config,metadata={'stage':args.command}) as book:
            with active_ledger(book):
                job=ROOT/'results/a25/jobs'/args.job
                write_json(job/'config.json',config)
                write_json(job/'environment.json',{'python':platform.python_version(),'argv':sys.argv,
                    'threads':{k:os.environ.get(k) for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS')}})
                if args.command=='tests':
                    log=io.StringIO()
                    with book.span('unit_validation'):
                        tests=unittest.TextTestRunner(stream=log,verbosity=2).run(
                            unittest.defaultTestLoader.discover(str(ROOT/'tests'),pattern=args.test_pattern,top_level_dir=str(ROOT)))
                    (job/'TESTS.log').write_text(log.getvalue())
                    result={'tests':tests.testsRun,'errors':len(tests.errors),'failures':len(tests.failures),'passed':tests.wasSuccessful()}
                    write_json(job/'result.json',result)
                    if not tests.wasSuccessful(): raise RuntimeError('UNIT_VALIDATION_FAILED')
                elif args.command=='solver':
                    from .phase0 import run_phase0
                    result=run_phase0(config,book)
                elif args.command=='headroom':
                    from .campaign import headroom
                    health=json.loads((ROOT/'results/a25/development/phase0/DECISION.json').read_text())
                    if health.get('status')!='HEALTHY': raise RuntimeError('SOLVER_HEALTH_NOT_PASSED')
                    result=headroom(config,book,health['solver'],experiment=args.experiment,
                        retry=args.retry,tv_multiplier=args.tv_multiplier,extra=args.extra)
                elif args.command=='generate':
                    from .dataset import generate_dataset
                    health=json.loads((ROOT/'results/a25/development/phase0/DECISION.json').read_text())
                    if health.get('status')!='HEALTHY':raise RuntimeError('SOLVER_HEALTH_NOT_PASSED')
                    result=generate_dataset(ROOT,config,book,solver=health['solver'])
                else:
                    raise RuntimeError('ENTRY_NOT_READY:'+args.command)
                write_json(job/'result.json',result)
                print(json.dumps(plain(result),allow_nan=False))
    except BaseException:
        job=ROOT/'results/a25/jobs'/args.job;job.mkdir(parents=True,exist_ok=True)
        (job/'ERROR.log').write_text(traceback.format_exc())
        print(json.dumps({'status':'FAILED','job':args.job,'error_log':str(job/'ERROR.log')}));raise

if __name__=='__main__': main()
