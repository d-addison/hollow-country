import sys,re
sys.path.insert(0,'/code/hc-worktrees/wp3-integ')
from tools.setup import infected_competence_probe as m, probe_runtime as rt
h=m.render_hook().decode()
open('/code/hc-worktrees/wp3-integ/scratchpad-review/wp3-r2-sonnet-review/hook_default.c','w').write(h)
nt=rt.native_type_names(m.DEFAULT_NATIVE)
print(rt.lint_hook(h,native_types=nt,explicit_numbers=True))
print('maxplus',rt.max_statement_plus(h))
for i,l in enumerate(h.splitlines(),1):
    s=l.strip()
    if s.startswith(('||','&&')) or re.search(r'\?[^"]*:',re.sub(r'"[^"]*"','',l)) : print('flag',i,l)
