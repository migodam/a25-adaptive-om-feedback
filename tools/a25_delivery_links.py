"""Metered final adjustment of report links for Release-only metadata."""
import argparse
import json
from pathlib import Path
import re
from a25.budget import charged_job,write_json

ROOT=Path(__file__).resolve().parents[1]
ASSET='https://github.com/migodam/a25-adaptive-om-feedback/releases/download/a25-v0.1.0/A25_COMPLETE_ACTION_LEDGERS.zip'

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--job',required=True)
    args=parser.parse_args()
    config=json.loads((ROOT/'configs/a25/campaign.json').read_text())
    with charged_job(ROOT,args.job,config=config,metadata={'stage':'public_report_link_adjustment'}) as book:
        names=('SOMNET_MIGRATION_PILOT.md','A25_RESEARCH_REPORT_ZH.md','research/development/A25_EXPLORATION_RECORDS.md')
        count=0
        for name in names:
            path=ROOT/name;text=path.read_text()
            receipts='../../publication/A25_TERMINAL_RECEIPTS.json' if path.parent!=ROOT else 'publication/A25_TERMINAL_RECEIPTS.json'
            text,n=re.subn(r'\]\((?:\.\./)*results/a25/jobs/[^)]+/job_receipt\.json\)',']('+receipts+')',text)
            count+=n
            text,n=re.subn(r'\]\((?:\.\./)*results/a25/jobs/[^)]+/PROFILE_UPDATE\.json\)',']('+ASSET+')',text)
            count+=n
            text+='\n\n公开作业receipt链接指向不可变receipt的脱敏汇总，可按job ID查找；逐文件原件与PROFILE_UPDATE在账本Release ZIP的项目相对路径中。CSV和实验JSON仍可直接在仓库读取。\n'
            path.write_text(text)
        write_json(ROOT/'results/a25/jobs'/args.job/'result.json',{'status':'PUBLIC_REPORT_LINKS_ADJUSTED','links':count,'scientific_results_changed':False})
        print(json.dumps({'status':'PUBLIC_REPORT_LINKS_ADJUSTED','links':count}))

if __name__=='__main__':main()
