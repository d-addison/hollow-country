"""Independently selected mutations of round-2 defenses in the exported scratch snapshot."""
import os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent;HEAD=ROOT/'head';OUT=ROOT/'new-mutants';OUT.mkdir(exist_ok=True)
mutants=[
('complexity_bound_disabled','tools/setup/probe_runtime.py','if count > MAX_STATEMENT_PLUS:','if False:'),
('numeric_concat_disabled','tools/setup/probe_runtime.py','if explicit_numbers:','if False:'),
('consecutive_dot_rule_removed','tools/setup/probe_runtime.py','return bool(NAME_RULE.fullmatch(name)) and ".." not in name','return bool(NAME_RULE.fullmatch(name))'),
('ancestor_nofollow_removed','tools/setup/diagnostic_mission.py','return os.open(name, _DIRECTORY_FLAGS, dir_fd=parent_fd)','return os.open(name, os.O_RDONLY | os.O_DIRECTORY, dir_fd=parent_fd)'),
('leaf_nofollow_removed','tools/setup/diagnostic_mission.py','flags | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)','flags | getattr(os, "O_CLOEXEC", 0)'),
('mission_final_inventory_removed','tools/setup/diagnostic_mission.py','    _require_staged_tree(destination, manifest)','    # mutation removes final check'),
('linux_only_requirement_removed','tools/setup/diagnostic_mission.py','not sys.platform.startswith("linux") or not hasattr(os, "O_DIRECTORY")','False or not hasattr(os, "O_DIRECTORY")'),
('host_nested_invalidation_removed','tools/audit/taped_light_report.py','        _invalidate(base["lights"], invalidating, "host_evidence_invalid", ("qualified", "geometry_missing"))','        pass'),
('probe_nested_invalidation_removed','tools/audit/taped_light_report.py','    _invalidate(record["lights"], ("probe_integrity_failed",), "probe_integrity_failed", verdicts)','    pass'),
('slot_nested_invalidation_removed','tools/audit/taped_light_report.py','if slot["verdict"] in verdicts:','if False:'),
('control_preflight_ignored','tools/audit/taped_light_report.py','    if preflight is MISSING:\n        return {"control_preflight_missing"}','    if preflight is MISSING:\n        return set()'),
('control_failed_spawn_ignored','tools/audit/taped_light_report.py','    if problem == "light_not_spawned":\n        return {"control_light_not_spawned"}','    if problem == "light_not_spawned":\n        return set()'),
('variant_guard_identity_ignored','tools/audit/taped_light_report.py','if attached and not (found == label == PREREQUISITE_HANDGUARDS.get(slot) and rail):','if False:'),
('variant_guard_occupancy_ignored','tools/audit/taped_light_report.py','if occupied != attached:','if False:'),
('variant_fit_conflict_ignored','tools/audit/taped_light_report.py','if attempt["light_fits"] != preflight["fits"][name]:','if False:'),
('attach_contradiction_ignored','tools/audit/taped_light_report.py','if values["attach_ok"] and not values["can_add"]:','if False:'),
('counter_ranges_ignored','tools/audit/taped_light_report.py','if min(values.values()) < 0:','if False:'),
('census_ranges_ignored','tools/audit/taped_light_report.py','elif not 0 <= scanned <= total or scanned > CENSUS_SCAN_LIMIT:','elif False:'),
('variant_readback_skipped','tools/setup/taped_light_probe.py','readBack = variantHost.GetInventory().FindAttachment(slotId);','readBack = null;'),
]
env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',TMPDIR=str(ROOT/'tmp'))
mods=['tests.unit.test_probe_runtime','tests.unit.test_ce_probe','tests.unit.test_diagnostic_mission','tests.unit.test_flashlight_matrix','tests.unit.test_taped_light_probe','tests.unit.test_taped_light_report']
for name,relative,before,after in mutants:
    path=HEAD/relative;source=path.read_text();assert source.count(before)==1,(name,source.count(before))
    try:
        path.write_text(source.replace(before,after))
        result=subprocess.run([sys.executable,'-m','unittest',*mods,'-q'],cwd=HEAD,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    finally:path.write_text(source)
    (OUT/(name+'.log')).write_text(result.stdout)
    summaries=[s for s in result.stdout.splitlines() if s.startswith(('Ran ','FAILED','OK'))]
    print(name+': '+('SURVIVED' if result.returncode==0 else 'KILLED')+'; '+'; '.join(summaries),flush=True)
