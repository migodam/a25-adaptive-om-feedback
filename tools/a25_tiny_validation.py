"""Independent SOC/TV identity check; reruns are separate charged attempts."""
import argparse,json
from pathlib import Path
import numpy as np
from a25.budget import charged_job
from a25.prox import ProxProblem,solve_prox
from a25.socp_reference import solve_socp_reference,difference_matrix
from a24.material_updates import _gradient,_gradient_adjoint
from a24.contracts import active_ledger
from a20.costs import write_json
p=argparse.ArgumentParser();p.add_argument('--job',required=True);args=p.parse_args()
root=Path(__file__).resolve().parents[1];cfg=json.loads((root/'configs/a25/campaign.json').read_text())
with charged_job(root,args.job,config=cfg,metadata={'stage':'solver_validation'}) as b,active_ledger(b):
    rng=np.random.default_rng(25);n=9;x=rng.normal(size=2*n);dual=rng.normal(size=(3,3,2,2))
    D=difference_matrix((3,3),b)
    err=np.linalg.norm(D@x-_gradient(x,(3,3)).reshape(-1))
    dot=abs(np.dot(D@x,dual.reshape(-1))-np.dot(x,_gradient_adjoint(dual,(3,3))))
    assert err<1e-12 and dot<1e-12
    v=.05*rng.normal(size=18)+np.r_[np.full(9,.2),np.full(9,.1)]
    problem=ProxProblem(v,np.r_[np.full(9,.1),np.full(9,.04)],.01,(3,3),1/9,
                        {**cfg,'prox_algorithm':'extended_pdhg'},'tiny')
    candidate=solve_prox(problem,budget=b);ref=solve_socp_reference(problem,budget=b,comparison=candidate)
    result={'sparse_D_error':err,'adjoint_error':dot,'pdhg':candidate.metadata,'independent_reference':ref.metadata}
    write_json(root/'results/a25/jobs'/args.job/'result.json',result)
    assert candidate.converged and ref.converged
    print(json.dumps({'tiny':'PASS','kkt':candidate.metadata['kkt_residual'],
                      'reference_kkt':ref.metadata['kkt_residual'],'raw_status':ref.metadata['solver_status']}))
