"""Mutation checks modify only the disposable copy, restoring every change."""
from pathlib import Path
import json
import os
import subprocess
import sys
ROOT = Path(__file__).resolve().parent
COPY = ROOT / 'source-copy'
SOURCE = COPY / 'mods/HollowCountry/scripts/4_World/Infected/HCInfectedModule.c'
original = SOURCE.read_text()
tests = 'tests.unit.test_infected_admission.UnqualifiedPathsPerformNoMutation.'
cases = [
 ('ce_adoption', '!m_Admission.CEAdoption', 'false', 'test_ce_adoption_requested_but_unadmitted_does_not_reserve_save_capture_or_transfer'),
 ('native_pack_start', 'bool attempted = m_Admission.NativePackRoutes;', 'bool attempted = true;', 'test_native_pack_routes_unadmitted_never_start_a_pack_even_with_ce_adoption_admitted'),
 ('investigation', 'MayInvestigate(m_Admission.Investigation,', 'MayInvestigate(true,', 'test_investigation_requested_but_unadmitted_routes_nothing'),
 ('visual_sampling', 'if (m_Admission.Investigation && m_ObservationsRemaining', 'if (true && m_ObservationsRemaining', 'test_investigation_visual_sampling_is_gated_by_admission'),
 ('native_emission', 'if (m_Admission.SupplementaryChains)', 'if (true)', 'test_supplementary_chains_requested_but_unadmitted_emit_no_relay'),
 ('member_recovery', 'm_Hordes && m_Admission.MemberRecovery &&', 'm_Hordes && true &&', 'test_member_recovery_requested_but_unadmitted_performs_no_reconciliation'),
 ('relay_processing', 'm_Chains && m_Admission.SupplementaryChains && work', 'm_Chains && true && work', 'test_chain_relay_processing_requested_but_unadmitted_performs_no_relay'),
 ('cohort_retarget', 'if (m_Admission.HordeStimulusRoutes)', 'if (true)', 'test_stimulus_routes_requested_but_unadmitted_never_reach_retarget'),
]
env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', TMPDIR=str(ROOT / 'tmp'), PYTHONPATH=str(ROOT / 'guard'))
results = []
try:
    baseline = subprocess.run([sys.executable, '-m', 'unittest', 'tests.unit.test_infected_admission', '-v'],
        cwd=COPY, env=env, capture_output=True, text=True)
    (ROOT / 'mutation-baseline.log').write_text(baseline.stdout + baseline.stderr)
    assert baseline.returncode == 0, baseline.stderr
    for name, before, after, test in cases:
        assert original.count(before) == 1, (name, original.count(before))
        SOURCE.write_text(original.replace(before, after))
        command = [sys.executable, '-m', 'unittest', tests + test, '-v']
        result = subprocess.run(command, cwd=COPY, env=env, capture_output=True, text=True)
        output = result.stdout + result.stderr
        (ROOT / ('mutation-' + name + '.log')).write_text(output)
        killed = result.returncode == 1 and 'FAIL:' in output and 'ERROR:' not in output
        results.append(dict(name=name, killed=killed, command=command, exit=result.returncode))
        SOURCE.write_text(original)
finally:
    SOURCE.write_text(original)
(ROOT / 'mutation-results.json').write_text(json.dumps(results, indent=2) + '\n')
for r in results: print(r['name'] + ': ' + ('KILLED (assertion failure)' if r['killed'] else 'NOT KILLED'))
print(f'{sum(r["killed"] for r in results)}/{len(results)} guard-removal mutants killed; original source untouched.')
sys.exit(not all(r['killed'] for r in results))
