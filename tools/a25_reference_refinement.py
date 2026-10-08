"""One explicit, paid reference precision retry on the unchanged frozen QP."""
import argparse,json,shutil
from pathlib import Path
import numpy as np
from a25.budget import charged_job,write_json
from a25.prox import ProxProblem,solve_prox
from a25.socp_reference import solve_socp_reference
from a24.contracts import active_ledger
p=argparse.ArgumentParser();p.add_argument('--job',required=True);args=p.parse_args()
root=Path(__file__).resolve().parents[1];cfg=json.loads((root/'configs/a25/campaign.json').read_text())
out=root/'results/a25/development/phase0';case='ring_2404_1.2_snr20'
with charged_job(root,args.job,config=cfg,metadata={'stage':'reference_precision_retry'}) as b,active_ledger(b):
    with np.load(out/'inputs'/f'{case}.npz') as f:
        problem=ProxProblem(f['v'],f['background'],float(f['weight']),tuple(f['grid_shape']),float(f['volume']),
            {**cfg,'prox_algorithm':'extended_pdhg','reference_refinement':True},case)
    candidate=solve_prox(problem,budget=b);reference=solve_socp_reference(problem,budget=b,comparison=candidate)
    result={'case_id':case,'reference':reference.metadata,'candidate':candidate.metadata,'unchanged_objective':True,
            'internal_reference_precision_tightened':True,'external_tolerance_changed':False}
    write_json(out/'REFERENCE_REFINEMENT_001.json',result)
    np.savez_compressed(out/'reference'/f'{case}_refinement_001.npz',x=reference.x,p=reference.p,
                        lower_dual=reference.lower_dual,upper_dual=reference.upper_dual)
    accepted=(reference.converged and reference.metadata.get('objective_agreement_passed') and
              reference.metadata.get('robust_primal_distance_agreement'))
    if accepted:
        decision=json.loads((out/'DECISION.json').read_text())
        shutil.copy2(out/'DECISION.json',out/'DECISION_INITIAL.json')
        old=json.loads((out/'INDEPENDENT_REFERENCE.json').read_text())
        assert all(r['comparison_agrees'] for r in old if r['case_id']!=case)
        decision.update(status='HEALTHY',independent_agreement=True,reference_precision_retry=args.job,
                        original_independent_failure_retained=True)
        write_json(out/'DECISION.json',decision)
    print(json.dumps({'accepted':bool(accepted),'raw_status':reference.metadata.get('solver_status'),
          'strict_certificate':reference.metadata.get('strict_external_reference_certificate_passed'),
          'kkt':reference.metadata.get('kkt_residual'),'comparison':reference.metadata.get('robust_primal_distance_agreement')}))
