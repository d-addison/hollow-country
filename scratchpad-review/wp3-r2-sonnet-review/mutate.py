import shutil, subprocess, sys, os, re
from concurrent.futures import ThreadPoolExecutor
ROOT='/code/hc-worktrees/wp3-integ'
OUT=ROOT+'/scratchpad-review/wp3-r2-sonnet-review/mut'
SRC='tools/setup/infected_competence_probe.py'
orig=open(f'{ROOT}/{SRC}').read()
M=[
('V01 completed-leg-fall >= -> >', "if _finite(row['samples'][1]['left']) >= _finite(row['samples'][0]['left']):", "if _finite(row['samples'][1]['left']) > _finite(row['samples'][0]['left']):"),
('V02 completed elapsed upper +1000 -> +100000', "_integer(row.get('elapsed_ms'), 0, plan['probe']['per_trial_ms'] + 1000, 'trial elapsed')", "_integer(row.get('elapsed_ms'), 0, plan['probe']['per_trial_ms'] + 100000, 'trial elapsed')"),
('V03 inconclusive cap +30000 -> +30000000', "cap = len(plan['trials']) * (plan['probe']['per_trial_ms'] + 1100) + 30000\n", "cap = len(plan['trials']) * (plan['probe']['per_trial_ms'] + 1100) + 30000000\n"),
('V04 completed lower bound dropped', "row['elapsed_ms'] < plan['probe']['per_trial_ms']):", "row['elapsed_ms'] < 0):"),
('V05 spawned==deleted dropped', "if row['spawned'] != row['deleted']:", "if False:"),
('V06 client elapsed check dropped', "row['samples'] or row['doors'] or row['geometry'] or row['elapsed_ms']):", "row['samples'] or row['doors'] or row['geometry']):"),
('V07 authored Y tol 0.01 -> 1000', "abs_tol=0.01)", "abs_tol=1000)"),
('V08 surface_y finite check dropped', "            _finite(row[prefix + '_surface_y'])\n", "            pass\n"),
('V09 clients != 0 -> < 0', "document.get('clients') != 0):", "document.get('clients') < 0):"),
('V10 sample exact keys dropped', "if set(sample) != {'mind', 'target', 'crawling', 'alive', 'left', 'right', 'position'}:", "if False:"),
('V11 door index check dropped', "door.get('index') != index or any(", "False or any("),
('V12 geometry must be clear dropped', " or row['geometry'] != [0, 0, 0, 0] or", " or"),
('V13 two samples -> >=1', "len(row['samples']) != 2", "len(row['samples']) < 1"),
('V14 version lookbehind dropped', "(?<![\\d.])1\\.30\\.164289", "1\\.30\\.164289"),
('V15 completed target/alive contamination dropped', "if status == 'completed' and (sample['target'] or not sample['alive']):", "if False:"),
('V16 per-row doors outside door-state dropped', "if trial['kind'] != 'door_state' and row['doors']:", "if False:"),
('V17 document key set exact dropped', "if set(document) != {'schema', 'kind', 'hook_sha256', 'status', 'world', 'version',\n                         'clients', 'spawned', 'deleted', 'trials'}:", "if False:"),
('V18 limb range <=10000 -> 10**9', "<= _finite(sample.get(leg)) <= 10000", "<= _finite(sample.get(leg)) <= 10**9"),
('V19 total spawned/deleted check dropped', "if document.get('spawned') != spawned or document.get('deleted') != deleted:", "if False:"),
('V20 receipt hook sha check dropped', "if document.get('hook_sha256') != expected_sha:", "if False:"),
('V21 config staged==source check dropped', "plan['config_treatment']['staged_sha256'] != plan['config_treatment']['source_sha256'] or", ""),
('V22 sidecar mismatch dropped', "if rt._read_bounded(root / HASH_RELATIVE, 64) != expected_sha.encode('ascii'):", "if False:"),
('V23 client reason mismatch dropped', "if row['reason'] != trial['reason']:", "if False:"),
('V24 client terrain-obs-empty dropped', "if any(row[field] != '' for field in ('anchor_authored_y', 'anchor_surface_y',\n                                                'spawn_authored_y', 'spawn_surface_y')):", "if False:"),
('H01 spawn SurfaceY dropped', "        spawnPoint[1] = GetGame().SurfaceY(spawnPoint[0], spawnPoint[2]);\n", ""),
('H02 anchor SurfaceY dropped', "        anchor[1] = GetGame().SurfaceY(anchor[0], anchor[2]);\n", ""),
('H03 query radius 5.0 -> 2.0', "GetObjectsAtPosition3D(anchor, 5.0,", "GetObjectsAtPosition3D(anchor, 2.0,"),
('H04 matches != 1 -> < 1', "if (matches != 1)", "if (matches < 1)"),
('H05 observe time budget +1000 -> +100000', "if (elapsed > @@PER_TRIAL@@ + 1000)", "if (elapsed > @@PER_TRIAL@@ + 100000)"),
('H06 client elapsed zero branch removed', '''        if (m_Trial.support_state == "client_required")
            m_Trial.elapsed_ms = 0;
        else
            m_Trial.elapsed_ms = GetGame().GetTime() - m_TrialBegin;''', '''        m_Trial.elapsed_ms = GetGame().GetTime() - m_TrialBegin;'''),
('H07 leg fall >= -> >', "if (currentLegHealth >= m_LegBefore)", "if (currentLegHealth > m_LegBefore)"),
('H08 DecreaseHealth stimulus removed', '            m_Actor.DecreaseHealth("LeftLeg", "Health", legHealth);\n', ''),
('H09 cleanup m_Owned=null removed', "        m_Owned = null;\n        m_Actor = null;", "        m_Actor = null;"),
('H10 ray count 4 -> 3', "rayIndex < 4", "rayIndex < 3"),
('H11 initial leg health guard dropped', "if (legHealth <= 0 || legHealth > 10000)", "if (false)"),
('H12 no-client identity abort dropped', "if (identities.Count() != 0)", "if (identities.Count() > 100000)"),
('H13 trial CAP check removed', "if (GetGame().GetTime() - m_Begin > @@CAP@@)", "if (false)"),
('H14 deleted-count in cleanup dropped', "            m_Receipt.deleted = m_Receipt.deleted + 1;\n", ""),
('H15 door budget guard 16 -> 1600', "if (doorCount < 1 || doorCount > 16)", "if (doorCount < 1 || doorCount > 1600)"),
('H16 ECE flag ECE_INITAI dropped', "ECE_PLACE_ON_SURFACE|ECE_INITAI", "ECE_PLACE_ON_SURFACE"),
('H17 ray height 0.8 -> 8.0', "Vector(0, 0.8, 0)", "Vector(0, 8.0, 0)"),
('H18 target presence ends sample false dropped', "        if (sampleRow.target)\n            return false;\n", ""),
('S01 staged config hash differs from source', "    config = context['source']['config_bytes']\n    built", "    config = context['source']['config_bytes'] + b'\\n'\n    built"),
('S02 survey x offset sin->cos', "position[0] + spawn_offset_m * math.sin(yaw)", "position[0] + spawn_offset_m * math.cos(yaw)"),
('S03 survey class sort dropped', "selected = sorted(placements if classes is None else classes)[:class_limit]", "selected = list(placements if classes is None else classes)[:class_limit]"),
('S04 survey offset max 10 -> 1000', "or not 1 <= spawn_offset_m <= 10:", "or not 1 <= spawn_offset_m <= 1000:"),
('S05 survey ambiguous rpy check dropped', "if key in rotations and rotations[key] != rotation:", "if False:"),
('S06 spawn within 20m 400 -> 40000', "for a, b in zip(trial['position'], trial['structure_position'])) > 400:", "for a, b in zip(trial['position'], trial['structure_position'])) > 40000:"),
('S07 wait_minutes +40000 -> +0', "(per_trial_ms + 1100) + 40000)", "(per_trial_ms + 1100) + 0)"),
('S08 registration refusal dropped', "    _registration()  # Refuse", "    # Refuse"),
('S09 fixture limitation text dropped', "if fixture_counts.get('unqualified-candidate'):", "if False:"),
('S10 path label swapped', "paths.add('leg_health_only' if row['kind']", "paths.add('spawn_state_geometry_door_reads' if row['kind']"),
('S11 stock-derived requires provenance dropped', "and fixture_survey is None:\n        raise ValueError('stock-derived", "and False:\n        raise ValueError('stock-derived"),
('S12 hash sidecar written wrong', "hash_data = rt.sha256(hook).encode('ascii')", "hash_data = rt.sha256(hook + b' ').encode('ascii')"),
('S13 start delay lower bound 5 -> 0', "_integer(start_delay_s, 5, 600, 'start delay')", "_integer(start_delay_s, 0, 600, 'start delay')"),
]
def run(i):
    name,old,new=M[i]
    d=f'{OUT}/m{i:02}'
    shutil.rmtree(d,ignore_errors=True); os.makedirs(d)
    shutil.copytree(f'{ROOT}/tools',f'{d}/tools',ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copytree(f'{ROOT}/tests',f'{d}/tests',ignore=shutil.ignore_patterns('__pycache__'))
    if old not in orig: return name,'NOMATCH'
    if old==new: 
        return name,'NOOP'
    p=f'{d}/{SRC}'
    open(p,'w').write(orig.replace(old,new,1))
    r=subprocess.run(['python3','-m','unittest','tests.unit.test_infected_competence'],cwd=d,capture_output=True,text=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'),timeout=300)
    status='SURVIVED' if r.returncode==0 else 'killed'
    detail=''
    if r.returncode:
        m=re.findall(r'^(?:FAIL|ERROR): (\S+)',r.stderr,re.M); detail=','.join(m[:2])+(f' (+{len(m)-2})' if len(m)>2 else '')
    shutil.rmtree(d,ignore_errors=True)
    return name,status+' '+detail
if __name__=='__main__':
    os.makedirs(OUT,exist_ok=True)
    with ThreadPoolExecutor(4) as ex:
        res=list(ex.map(run,range(len(M))))
    with open(f'{ROOT}/scratchpad-review/wp3-r2-sonnet-review/mutation_results.txt','w') as f:
        for n,s in res:
            f.write(f'{n}: {s}\n'); print(f'{n}: {s}')
