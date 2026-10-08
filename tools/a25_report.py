"""Parent-invoked, charged Chinese report/figure export from saved results."""
from __future__ import annotations
import time
_PROCESS_WALL, _PROCESS_CPU = time.perf_counter(), time.process_time()
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]


def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument("--root",default=str(ROOT))
    parser.add_argument("--job",required=True)
    parser.add_argument("--config",default="configs/a25/campaign.json")
    parser.add_argument("--decision",default="results/a25/A25_GATE_DECISION.json")
    parser.add_argument("--no-plots",action="store_true")
    args=parser.parse_args(argv)
    root=Path(args.root).resolve()
    sys.path.insert(0,str(root/"src"))
    from a25.budget import charged_job,write_json
    from a25.reporting import generate_report
    config=json.loads((root/args.config).read_text())
    with charged_job(root,args.job,device="cpu",config=config,metadata={"stage":"report"}) as book:
        # Include this script's import/preparation tail in its own measurements.
        book.started_wall=min(book.started_wall,_PROCESS_WALL)
        book.started_cpu=min(book.started_cpu,_PROCESS_CPU)
        result=generate_report(root,book,config,decision_path=root/args.decision,plots=not args.no_plots)
        write_json(root/"results/a25/jobs"/args.job/"result.json",result)
        print(json.dumps(result,ensure_ascii=False,allow_nan=False))


if __name__=="__main__":
    main()
