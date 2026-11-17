"""Export authored files only; all writes remain under this review directory."""
from pathlib import Path
import io, os, subprocess, tarfile, json

ROOT = Path(__file__).resolve().parent
(ROOT / 'tmp').mkdir(exist_ok=True)
for label, rev in [('head', '182db38'), ('parent', '73241f6')]:
    dest = ROOT / label
    if not dest.exists():
        dest.mkdir()
        data = subprocess.check_output(['git', 'archive', rev, 'tools', 'tests'], cwd=ROOT.parents[1])
        with tarfile.open(fileobj=io.BytesIO(data)) as archive:
            archive.extractall(dest, filter='data')
    print(label, rev, 'tools/tests exported')
prior = Path('/code/hc-worktrees/taped-light-review-4/scratchpad-review/r7')
for name in ['red_regressions', 'new_red_regressions', 'remaining_regressions', 'residual_race',
             'compile_audit', 'native_checks', 'all_api_audit', 'extended_guard_mutations']:
    text = (prior / (name + '.py')).read_text()
    if name == 'extended_guard_mutations':
        text = text.replace("view_selection=", "res_selection=")
        text = text.replace("item=dict(f.proxy(),selection=", "item=dict(f.proxy(res_selection='proxy:'+base+'/.p3d.001'),selection=")
        # dict contains a new unused res_selection key; explicit res_lods above is the evidence.
    (ROOT / (name + '.py')).write_text(text)
env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', TMPDIR=str(ROOT / 'tmp'))
argv = ['python3', '-B', '-m', 'unittest', 'tests.unit.test_probe_runtime',
        'tests.unit.test_ce_probe', 'tests.unit.test_diagnostic_mission',
        'tests.unit.test_flashlight_matrix', 'tests.unit.test_taped_light_probe',
        'tests.unit.test_taped_light_report', '-v']
result = subprocess.run(argv, cwd=ROOT / 'head', env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
(ROOT / 'focused-tests.log').write_text(result.stdout)
print(json.dumps(dict(argv=argv, cwd=str(ROOT / 'head'), exit=result.returncode)))
print('\n'.join(result.stdout.splitlines()[-4:]))
