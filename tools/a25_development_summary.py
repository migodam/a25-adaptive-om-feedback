"""Metered descriptive analysis, no physics and no holdout reads."""
import json
from pathlib import Path
import numpy as np
from a25.budget import charged_job,write_json
from a25.analysis import summarize,records,num
r=Path(__file__).resolve().parents[1];cfg=json.loads((r/'configs/a25/campaign.json').read_text())
with charged_job(r,'development-summary-002',config=cfg) as b:
    result={}
    with b.span('paired_development_summary'):
        for experiment in ('frozen_optimizer_repair','tv_multiplier_0p1'):
            summary=summarize(experiment); rows=records(r/'results/a25/development'/experiment/'METRICS.csv')
            regimes=[]
            for bg in ('weak','ring'):
                for amp in (.3,1.2):
                    f=[x for x in rows if x['method']=='F' and x['background']==bg and num(x,'amplitude')==amp and num(x,'K')==12]
                    l=[x for x in rows if x['method']=='L' and x['background']==bg and num(x,'amplitude')==amp and num(x,'K')==12]
                    regimes.append({'background':bg,'amplitude':amp,'F_delta':float(np.mean([num(x,'delta_nrmse') for x in f])),
                      'L_delta':float(np.mean([num(x,'delta_nrmse') for x in l]))})
            result[experiment]={'summary':summary,'regimes':regimes}
        write_json(r/'results/a25/development/PAIRED_TV_AND_REGIME.json',result)
    print(json.dumps(result,allow_nan=False))
