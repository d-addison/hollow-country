"""Read and hash audit inputs, retaining no full native source copies."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CACHE = Path('/home/david/.cache/hollow-country/native-scripts/scripts-1.30.164289')
previous = json.loads((HERE/'INPUTS.json').read_text())
for row in previous:
    assert hashlib.sha256(Path(row['path']).read_bytes()).hexdigest() == row['sha256'], row['path']
print(f'Previously pinned original inputs unchanged: {len(previous)}.')
paths = set((ROOT/'mods/HollowCountry/scripts/4_World/Infected').glob('*.c'))
paths |= set((ROOT/'tests/unit').glob('test_infected*.py'))
for rel in ['AGENTS.md', '.issues-b04.md', 'docs/RUNTIME_IMPLEMENTATION_CONTRACT.md',
            'docs/MODULE_STATUS.md', 'README.md', '.github/workflows/static.yml',
            'mods/HollowCountry/config.cpp', 'mods/HollowCountry/scripts/3_Game/HCSettings.c',
            'mods/HollowCountry/scripts/4_World/Core/HCModule.c',
            'mods/HollowCountry/scripts/4_World/Core/HCServer.c',
            'mods/HollowCountry/scripts/5_Mission/HCMissionServer.c',
            'tools/validate/bdd.py', 'tools/setup/infected_death_probe.py',
            'tools/setup/death_selection_probe.py', 'tools/setup/diagnostic_mission.py',
            'tools/setup/wine_compile_probe.py', 'tools/setup/native_startup_probe.py',
            'tools/setup/fuel_siphon_probe.py', 'tools/package/pbo.py',
            'tools/validate/runtime.py', 'tests/unit/test_fuel_siphon_probe.py',
            'tests/features/offline.feature',
            'tests/features/runtime.feature', 'tests/catalog.json', 'tests/capabilities.json',
            'tests/unit/test_room_catalog_completion.py', 'tests/unit/test_observer_transition.py',
            'tests/unit/test_death_selection_probe.py', 'tests/unit/test_core_lifecycle.py',
            'tests/unit/test_diagnostic_mission.py', 'tests/unit/test_bdd_bindings.py',
            'tests/unit/test_runtime_settings.py', 'tests/unit/test_script_syntax.py',
            'tests/unit/test_script_identifiers.py', 'tests/unit/test_wine_compile_probe.py',
            'tests/fixtures/runtime/infected-policy.json',
            'tests/fixtures/runtime/infected-completion-scenarios.json']:
    paths.add(ROOT/rel)
for rel in ['docs/SPECIFICATION.md','docs/specs/001-survival-overhaul/spec.md',
            'docs/specs/001-survival-overhaul/plan.md',
            'docs/specs/001-survival-overhaul/completion-plan.md']:
    paths.add(Path('/code/dayzsa_mods')/rel)
for rel in ['3_Game/AI/AIWorld.c','3_Game/AI/AIGroup.c','3_Game/AI/AIGroupBehaviour.c',
            '3_Game/AI/AIAgent.c','3_Game/Entities/DayZInfected.c',
            '3_Game/Entities/DayZInfectedInputController.c',
            '3_Game/Entities/DayZCreatureAIInputController.c',
            '3_Game/Entities/DayZAnimal.c','3_Game/Entities/Building.c',
            '3_Game/Entities/EntityAI.c','3_Game/Global/Game.c','3_Game/Global/DayZPhysics.c',
            '3_Game/CE/CentralEconomy.c','3_Game/Noise.c','3_Game/human.c',
            '3_Game/dayzplayer.c','1_Core/proto/EnPhysics.c',
            '4_World/Entities/Creatures/Infected/ZombieBase.c']:
    paths.add(CACHE/rel)
manifest = []
for path in sorted(paths):
    data=path.read_bytes()
    manifest.append(dict(path=str(path),bytes=len(data),lines=len(data.splitlines()),
                         sha256=hashlib.sha256(data).hexdigest()))
(HERE/'INPUTS.json').write_text(json.dumps(manifest,indent=2)+'\n')
copies=list((HERE/'isolated-source').rglob('*'))
checked=0
for copy in copies:
    if copy.is_file():
        original=ROOT/copy.relative_to(HERE/'isolated-source')
        assert original.read_bytes()==copy.read_bytes(), str(copy)
        checked+=1
print(f'Hashed {len(manifest)} reviewed inputs; unchanged authored scratch copies verified: {checked}.')
for path in ['docs/SPECIFICATION.md','docs/specs/001-survival-overhaul/spec.md']:
    print(f'{ROOT/path}: ABSENT; read /code/dayzsa_mods/{path} instead')
for row in manifest:
    if '/code/dayzsa_mods/docs/' in row['path']:
        print(row['path']+': '+row['sha256'])
