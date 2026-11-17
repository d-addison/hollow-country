"""Remove only generated authored exports, full-module mutant copies and synthetic fixtures in this review."""
from pathlib import Path
import shutil
ROOT=Path(__file__).resolve().parent
assert ROOT.name=='r7' and ROOT.parent.name=='scratchpad-review'
for name in ['head','parent','tmp']:
    path=ROOT/name
    if path.exists():shutil.rmtree(path)
(ROOT/'tmp').mkdir()
for name in ['delete_never_executes','watchdog_does_not_cleanup','census_scans_nothing','create_attachment_arguments_reversed','timeout_does_not_break','found_type_guard_disabled','handguard_untracked','live_after_release_zeroed']:
    (ROOT/(name+'.py')).unlink(missing_ok=True)
print('Removed authored exports, 8 full-module mutant copies and synthetic fixtures; reusable scripts and actual logs retained.')
