"""Paid public-destination preflight; reads no credentials or locked data."""
import json
from pathlib import Path
import subprocess
from a25.budget import charged_job,write_json
ROOT=Path(__file__).resolve().parents[1]
cfg=json.loads((ROOT/'configs/a25/campaign.json').read_text())
with charged_job(ROOT,'publication-preflight-001',config=cfg,metadata={'stage':'publication_preflight'}) as book:
    with book.span('public_destination_preflight'):
        login=subprocess.run(['gh','api','user','--jq','.login'],capture_output=True,text=True,timeout=30)
        if login.returncode or login.stdout.strip()!='migodam':
            raise RuntimeError('PUBLICATION_ACCOUNT_UNAVAILABLE_OR_NOT_REQUESTED_OWNER')
        repo=subprocess.run(['gh','api','repos/migodam/a25-adaptive-om-feedback','--jq','{name:.full_name,private:.private,url:.html_url}'],capture_output=True,text=True,timeout=30)
        result={'owner':'migodam','repository':'migodam/a25-adaptive-om-feedback',
                'status':'EXISTING' if repo.returncode==0 else 'CREATE_REQUIRED',
                'existing':json.loads(repo.stdout) if repo.returncode==0 else None}
        if repo.returncode and '404' not in repo.stderr:
            raise RuntimeError('GITHUB_PREFLIGHT_FAILED; private diagnostics suppressed')
        if result['existing'] and result['existing']['private']:
            raise RuntimeError('EXISTING_PRIVATE_REPO_REQUIRES_SEPARATE_SCOPE_REVIEW')
        write_json(ROOT/'publication/PREFLIGHT.json',result)
        print(json.dumps(result))
