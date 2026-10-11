"""Run existing regressions without rewriting/reclassifying their assertions."""
import json, os, subprocess, sys
from pathlib import Path
root=Path(__file__).resolve().parents[2]
out=Path(os.environ.get('GUI03_EVIDENCE',root/'docs/gui03/evidence'))
out.mkdir(parents=True,exist_ok=True)
commands=[['bash','-n','bootstrap.sh'],[sys.executable,'setup.py','--help'],
 [sys.executable,'tests/f03/run.py','--json',str(out/'f03-results.json')],
 [sys.executable,'tests/f03/run.py','--no-xfail']]
scripts=['check_undefined_names','test_licensing','test_log_parsing','test_policy_block_authorization','test_security_command_pattern','test_security_rbac','test_security_secrets','test_security_ssh_hostkey','test_security_xss','test_public_metadata']
commands += [[sys.executable,'tests/'+s+'.py'] for s in scripts]
commands += [[sys.executable,p] for p in ['tests/gui03/test_accounting.py','tests/gui01/test_contract.py','tests/gui02/test_contract.py','tests/f03/atomic_postgres_integration.py','tests/f03/restoration_postgres_integration.py','tests/f03/external_postgres_integration.py','tests/f03/postgres_integration.py']]
commands += [['node',p] for p in ['tests/gui03/test_workspace.cjs','tests/f03/atomic_browser.cjs','tests/gui01/browser.cjs','tests/gui02/browser.cjs','tests/f03/restoration_browser.cjs']]
results=[]
for i,cmd in enumerate(commands):
    r=subprocess.run(cmd,cwd=root,capture_output=True,text=True,timeout=240)
    log=f'check-{i:02d}.log';(out/log).write_text(r.stdout+r.stderr)
    results.append(dict(command=cmd,returncode=r.returncode,log=log,tail=(r.stdout+r.stderr)[-1200:]))
    print(f'{r.returncode}: {" ".join(cmd)}',flush=True)
(out/'validation.json').write_text(json.dumps(results,indent=2)+'\n')
sys.exit(any(r['returncode'] != (1 if '--no-xfail' in r['command'] else 0) for r in results))
