import subprocess, sys, os
from pathlib import Path
root=Path('/code/hc-worktrees/wp3-integ/scratchpad-review/wp3-review/mut')
mod=root/'tools/setup/infected_competence_probe.py'
orig=mod.read_text()
pairs={
 'V1+V2 cleanup lies (both removed)':[("if row['spawned'] != row['deleted']:", "if False:"),("if document.get('spawned') != spawned or document.get('deleted') != deleted:", "if False:")],
 'V4+V12 unknown kind (both removed)':[("row.get('kind') not in KINDS:", "False:"),("if any(row.get(key) != trial[key] for key in ('id', 'kind', 'support_state')):", "if False:")],
 'E14+E15 staged init (both removed)':[("if not pinned_init or rt.sha256(init_bytes) != pinned_init['sha256']:", "if False:"),("if not init_bytes.endswith(hook):", "if False:")],
 'C1+C2 client observed/status both removed':[("if (row['observed'] or row.get('status') != 'client_required' or row['spawned'] or", "if (False or row['spawned'] or")],
 'D4+C? observed flag mismatch (E: status completed but observed False)':[("or row['observed'] != (status == 'completed')", "")],
}
for name,ms in pairs.items():
    t=orig
    for o,n in ms:
        assert t.count(o)==1,(name,o); t=t.replace(o,n)
    mod.write_text(t)
    p=subprocess.run([sys.executable,'-B','-m','unittest','tests.unit.test_infected_competence'],cwd=root,capture_output=True,text=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
    print(name,'KILLED' if p.returncode else 'SURVIVED')
mod.write_text(orig)
