"""Audit source call shapes against the pinned installed script cache.

Print declarations and aggregate metadata only; do not copy native source trees,
native observations, profiles, or the generated full hook into the review.
"""
import hashlib
import json
from pathlib import Path
import re
import sys
from unittest import mock

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "head"))
from tools.setup import taped_light_probe as p, probe_runtime as rt
from tests.unit import test_taped_light_probe as pf

CACHE = Path('/home/david/.cache/hollow-country/native-scripts/scripts-1.30.164289')
declarations = {
    '3_Game/gameplay.c': r'^\s*(class (Selection|LOD)|.*(GetName\(|GetVertexCount\(|GetLODVertexIndex\(|GetVertexPosition\(|GetSelections\(|GetSelectionCount\(|NAME_VIEW\s))',
    '3_Game/Entities/Object.c': r'^\s*(.*GetLODS\(|LOD GetLODByName\(|proto native void GetSelectionList\()',
    '3_Game/Global/Game.c': r'proto (?:native)?.*(ConfigGetText\(|ConfigGetTextArray\(|ConfigIsExisting\()',
}
for relative, pattern in declarations.items():
    path = CACHE / relative
    if not path.exists():
        candidates = list(CACHE.rglob(Path(relative).name))
        assert len(candidates) == 1, (relative, candidates)
        path = candidates[0]
    for n, line in enumerate(path.read_text().splitlines(), 1):
        if re.search(pattern, line):
            print(f'{path.relative_to(CACHE)}:{n}: {line.strip()}')

classification = json.loads(Path('/home/david/.cache/hollow-country/experiments/taped-light-probe-003/classification.json').read_text())
full = p.render_hook(p.select_targets(classification))
native_names = rt.native_type_names(CACHE)
added_out_calls = (("GetSelections", (0,)), ("GetLODS", (0,)), ("ConfigGetText", (1,)), ("ConfigGetTextArray", (1,)))
with mock.patch.object(rt, '_OUT_CALLS', rt._OUT_CALLS + added_out_calls):
    problems = rt.lint_hook(full.decode(), native_types=native_names, explicit_numbers=True)
print('HOOK', json.dumps({'bytes': len(full), 'sha256': hashlib.sha256(full).hexdigest(),
                         'max_plus': rt.max_statement_plus(full.decode()), 'native_type_names': len(native_names),
                         'methods': len(list(rt._function_bodies(rt._clean(full.decode())))),
                         'lint_with_added_out_calls': problems}, sort_keys=True))
assert not problems
assert rt.max_statement_plus(full.decode()) <= 8

# Check successful, absent, empty, capped and missing-vertex view branches all
# release the gameplay objects in the synthetic engine. Engine-owned LOD and
# Selection objects are not deleted by script (their constructors/destructors
# are private in gameplay.c); these new methods spawn no gameplay objects.
for name, changes in (
    ('positive', {}), ('no_lod', {'view': None}), ('empty', {'view': ()}),
    ('getselections_false', {'view_unlisted': True}),
    ('missing_vertex', {'view_no_vertex': pf.view_of(pf.LIGHT_UNIVERSAL_PROXY)}),
    ('capped', {'view': tuple('unrelated%d' % n for n in range(300)) + pf.view_of(pf.LIGHT_UNIVERSAL_PROXY)}),
):
    types = pf.proxy_types()
    types['AK74'].update(changes)
    world = pf.World(types=types)
    pf.run_hook(world, slots=pf._NoSelectionSlots)
    obs = pf.observations_of(world)
    assert not world.live(), (name, world.live())
    print('CLEANUP', json.dumps({'case': name, 'live': len(world.live()),
                                'spawned': obs['counters']['spawned'], 'deleted': obs['counters']['deleted'],
                                'status': obs['status']}))
