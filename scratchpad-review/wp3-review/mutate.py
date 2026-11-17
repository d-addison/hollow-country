import subprocess, sys, shutil, os, json
from pathlib import Path
root=Path('/code/hc-worktrees/wp3-integ/scratchpad-review/wp3-review/mut')
mod=root/'tools/setup/infected_competence_probe.py'
orig=mod.read_text()
muts=[
 ('V1 cleanup row spawned!=deleted', "if row['spawned'] != row['deleted']:", "if False:"),
 ('V2 totals spawned/deleted match', "if document.get('spawned') != spawned or document.get('deleted') != deleted:", "if False:"),
 ('V3 receipt hook sha', "if document.get('hook_sha256') != expected_sha:", "if False:"),
 ('V4 unknown kind', "row.get('kind') not in KINDS:", "False:"),
 ('V5 exact row field set', "if set(row) != {", "if False and set(row) != {"),
 ('V6 row count denominator', "len(rows) != len(plan['trials'])", "False"),
 ('V7 clients==0', "document.get('clients') != 0):", "False):"),
 ('V8 status complete', "if (document.get('status') != 'complete' or", "if (False or"),
 ('V9 sentinel', "!= b'status=complete':", "!= b'':"),
 ('V10 world', "str(document.get('world', '')).lower() != 'chernarusplus' or", "False or"),
 ('V11 build', "not re.search(r'(?<![\\d.])1\\.30\\.164289(?![\\d.])', str(document.get('version', '')))", "False"),
 ('V12 identity mismatch', "if any(row.get(key) != trial[key] for key in ('id', 'kind', 'support_state')):", "if False:"),
 ('C1 client: observed', "if (row['observed'] or row.get('status') != 'client_required' or row['spawned'] or", "if (False or row.get('status') != 'client_required' or row['spawned'] or"),
 ('C2 client: status', "row.get('status') != 'client_required' or row['spawned'] or", "False or row['spawned'] or"),
 ('C3 client: spawned', "or row['spawned'] or\n                    row['samples']", "or False or\n                    row['samples']"),
 ('C4 client: samples', "row['samples'] or row['doors'] or row['geometry'] or row['elapsed_ms']):", "row['doors'] or row['geometry'] or row['elapsed_ms']):"),
 ('C5 client: doors', "row['samples'] or row['doors'] or row['geometry'] or row['elapsed_ms']):", "row['samples'] or row['geometry'] or row['elapsed_ms']):"),
 ('C6 client: geometry', "row['samples'] or row['doors'] or row['geometry'] or row['elapsed_ms']):", "row['samples'] or row['doors'] or row['elapsed_ms']):"),
 ('C7 client: elapsed', "row['samples'] or row['doors'] or row['geometry'] or row['elapsed_ms']):", "row['samples'] or row['doors'] or row['geometry']):"),
 ('C8 client: reason', "if row['reason'] != trial['reason']:", "if False:"),
 ('C9 client whole branch', "        if client:\n            if (", "        if False:\n            if ("),
 ('D1 counts client_required', "counts['client_required'] += 1", "counts['client_required'] += 0"),
 ('D2 counts attempted', "counts['attempted'] += 1", "counts['attempted'] += 0"),
 ('D3 counts status', "counts[status] += 1", "counts['completed'] += 1"),
 ('D4 observed iff completed', "or row['observed'] != (status == 'completed')", ""),
 ('E1 completed spawned==1', "row['spawned'] != 1 or len(row['samples']) != 2", "len(row['samples']) != 2"),
 ('E2 completed 2 samples', "or len(row['samples']) != 2 or", "or"),
 ('E3 completed geometry clear', "or row['geometry'] != [0, 0, 0, 0] or", "or"),
 ('E4 completed elapsed>=per', "row['elapsed_ms'] < plan['probe']['per_trial_ms']", "False"),
 ('E5 door state needed', "if trial['kind'] == 'door_state' and not row['doors']:", "if False:"),
 ('E6 door outside door trial', "if trial['kind'] != 'door_state' and row['doors']:", "if False:"),
 ('E7 target/alive in completed', "if status == 'completed' and (sample['target'] or not sample['alive']):", "if False:"),
 ('E8 elapsed upper bound', "_integer(row.get('elapsed_ms'), 0, plan['probe']['per_trial_ms'] + 1000, 'trial elapsed')", "_integer(row.get('elapsed_ms'), 0, 10**9, 'trial elapsed')"),
 ('E9 array bounds', "if not isinstance(row.get(field), list) or len(row[field]) > maximum:", "if not isinstance(row.get(field), list):"),
 ('E10 reason bounded', "if not isinstance(row.get('reason'), str) or not 1 <= len(row['reason']) <= 256:", "if False:"),
 ('E11 limb range', "if not 0 <= _finite(sample.get(leg)) <= 10000:", "if False:"),
 ('E12 door index order', "door.get('index') != index or", ""),
 ('E13 config no-client', "if config != _no_clients_config(config) or", "if False or"),
 ('E14 init hash', "if not pinned_init or rt.sha256(init_bytes) != pinned_init['sha256']:", "if False:"),
 ('E15 init endswith hook', "if not init_bytes.endswith(hook):", "if False:"),
 ('E16 sidecar', "!= expected_sha.encode('ascii'):", "!= rt._read_bounded(root / HASH_RELATIVE, 64):"),
 ('S1 stage: registration check', "    _registration()  # Refuse", "    pass  # Refuse"),
 ('S2 stage: native verify', "evidence = verify_native(native_scripts)", "evidence = []"),
 ('S3 stage: lint', "if problems:\n        raise ValueError('generated hook violates", "if False:\n        raise ValueError('generated hook violates"),
 ('S4 check_trials spawn<=20m', "> 400:", "> 400000000:"),
 ('S5 check_trials fixture status', "if trial.get('fixture_status') not in", "if False and trial.get('fixture_status') not in"),
 ('S6 check_trials support mismatch', "if trial.get('support_state') != KINDS[trial['kind']][0]:", "if False:"),
 ('S7 check_trials reason canonical', "if trial.get('reason') != KINDS[trial['kind']][1]:", "if False:"),
 ('S8 dup trial id', "if trial['id'] in ids:", "if False:"),
 ('S9 max plus', "if rt.max_statement_plus(text) > 8:", "if False:"),
 ('S10 trial count cap', "not 1 <= len(trials) <= MAX_TRIALS", "not 1 <= len(trials)"),
 ('S11 bounds position', "raise ValueError('position outside Chernarus bounds')", "pass"),
 ('S12 max_spawned_entities', "max_spawned_entities=sum(t['support_state'] == 'server_observable' for t in trials)", "max_spawned_entities=0"),
 ('S13 wait_minutes', "wait_minutes=max(5,", "wait_minutes=max(50,"),
 ('S14 config maxPlayers 0', "'maxPlayers = 0;'", "'maxPlayers = 1;'"),
 # hook text mutations
 ('H1 hook: client_required skip', 'if (m_Trial.support_state == "client_required")', 'if (false)'),
 ('H2 hook: delete count receipt', "            m_Receipt.deleted = m_Receipt.deleted + 1;\n", ""),
 ('H3 hook: delete count trial', "                m_Trial.deleted = m_Trial.deleted + 1;\n", ""),
 ('H4 hook: ObjectDelete call', "            GetGame().ObjectDelete(m_Owned);\n", ""),
 ('H5 hook: cleanup in next', "    void HCICNext()\n    {\n        HCICCleanup();", "    void HCICNext()\n    {\n"),
 ('H6 hook: cleanup in finish', "        HCICCleanup();\n        m_Done = true;", "        m_Done = true;"),
 ('H7 hook: cleanup in mission finish', "    {\n        HCICCleanup();\n        if (m_Ready", "    {\n        if (m_Ready"),
 ('H8 hook: spawned count', "            m_Trial.spawned = 1;\n", ""),
 ('H9 hook: no-client abort', "if (identities.Count() != 0)", "if (identities.Count() != 99)"),
 ('H10 hook: cap check', "if (GetGame().GetTime() - m_Begin > @@CAP@@)", "if (false)"),
 ('H11 hook: output cap', "if (outputData.Length() > 262144)", "if (false)"),
 ('H12 hook: sentinel written first', "FPrintln(sentinelFile, \"status=\" + outcome);", "FPrintln(sentinelFile, \"status=complete\");"),
 ('H13 hook: door loop bound', "doorIndex < doorCount && doorIndex < 16", "doorIndex < doorCount"),
 ('H14 hook: owned deleted even if cast fails (m_Owned kept)', "        m_Owned = null;\n        m_Actor = null;\n    }", "        m_Actor = null;\n    }"),
 ('H15 hook: leg health bound', "if (legHealth <= 0 || legHealth > 10000)", "if (false)"),
 ('H16 hook: ray count', "rayIndex < 4", "rayIndex < 3"),
 ('H17 hook: ECE flags', "ECE_PLACE_ON_SURFACE|ECE_INITAI", "ECE_PLACE_ON_SURFACE"),
 ('H18 hook: watchdog', "CallLater(HCICWatchdog, @@WATCHDOG@@, false);", ""),
 ('H19 hook: query bound', "if (nearby.Count() > 128 || proxyCargos.Count() > 128)", "if (false)"),
 ('H20 hook: structure ambiguity', "if (matches != 1)", "if (matches < 1)"),
]
res=[]
for name,old,new in muts:
    if orig.count(old)!=1:
        res.append((name,'PATTERN_COUNT=%d'%orig.count(old))); continue
    mod.write_text(orig.replace(old,new))
    p=subprocess.run([sys.executable,'-B','-m','unittest','tests.unit.test_infected_competence'],cwd=root,capture_output=True,text=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
    res.append((name,'KILLED' if p.returncode else 'SURVIVED'))
mod.write_text(orig)
for r in res: print(*r)
print('survivors:',[n for n,s in res if s!='KILLED'])
