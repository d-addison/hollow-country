"""Read installed declarations and inspect generated text without starting DayZ."""
import hashlib
import json
from pathlib import Path
import re
from tools.setup import taped_light_probe as probe
from tools.setup import probe_runtime as rt

OUT = Path(__file__).resolve().parent
CACHE = Path.home() / '.cache/hollow-country/native-scripts/scripts-1.30.164289'
EXP = Path.home() / '.cache/hollow-country/experiments'
classification = json.loads((EXP / 'taped-light-probe-003/classification.json').read_text())
hook = probe.render_hook(probe.select_targets(classification)).decode('ascii')
(OUT / 'generated-hook.c').write_text(hook)
clean = rt._clean(hook)
print('Hook bytes:', len(hook.encode('ascii')))
print('Hook sha256:', hashlib.sha256(hook.encode('ascii')).hexdigest())
print('Lint with installed native type names and explicit_numbers:',
      probe.lint_hook(hook, native_types=probe.native_type_names(CACHE), explicit_numbers=True))
print('Maximum + per statement:', rt.max_statement_plus(hook))
print('CreateObjectEx call sites:', len(re.findall(r'\bCreateObjectEx\s*\(', clean)))
print('ObjectDelete call sites:', len(re.findall(r'\bObjectDelete\s*\(', clean)))
print('Non-HCTL call names:', ', '.join(sorted(set(re.findall(r'\b(\w+)\s*\(', clean))
      - set(re.findall(r'\b(HCTL\w+)\s*\(', clean)) - {'if', 'while', 'OnInit'})))
print('Loops:')
for line, text in enumerate(clean.splitlines(), 1):
    if re.search(r'\bwhile\s*\(', text):
        print(f'generated-hook.c:{line}: {text.strip()}')

symbols = set(re.findall(r'\b(\w+)\s*\(', clean)) - set(re.findall(r'\b(HCTL\w+)\s*\(', clean)) - {'if', 'while'}
print('\nInstalled declaration candidates (selected files, no vanilla source copies retained):')
paths = [
    '1_Core/proto/EnConvert.c', '1_Core/proto/EnScript.c', '1_Core/proto/EnString.c',
    '1_Core/proto/EnSystem.c', '1_Core/proto/EnDebug.c', '1_Core/proto/EnMath.c',
    '3_Game/gameplay.c', '3_Game/Global/Game.c', '3_Game/DayZGame.c', '3_Game/tools/utilityclasses.c',
    '3_Game/Entities/Object.c', '3_Game/Entities/Entity.c', '3_Game/Entities/EntityAI.c',
    '3_Game/Systems/Inventory/Inventory.c', '3_Game/Systems/Inventory/InventorySlots.c',
    '3_Game/tools/utilityclasses/ScriptCallQueue.c', '3_Game/CE/CentralEconomy.c',
    '5_Mission/mission/missionBase.c', '5_Mission/mission/missionServer.c',
]
# Discover exact path casing rather than assuming it for utility files.
paths = [path for path in paths if (CACHE / path).is_file()]
for path in CACHE.rglob('*.c'):
    if path.name.lower() in {'scriptcallqueue.c', 'utilityclasses.c'}:
        rel = str(path.relative_to(CACHE))
        if rel not in paths:
            paths.append(rel)
for relative in paths:
    for number, line in enumerate((CACHE / relative).read_text().splitlines(), 1):
        found = re.search(r'\b(\w+)\s*\(', line)
        if found and found.group(1) in symbols and re.search(r'\b(proto|override|void|bool|int|DayZGame|ScriptCallQueue|vector)\b', line):
            if line.strip().startswith(('//', '*')):
                continue
            # Keep prototypes/definitions, not call bodies.
            if re.match(r'\s*(?:(?:static|override|proto|native|external|owned)\s+)*(?:void|bool|int|string|float|vector|Object|EntityAI|GameInventory|DayZGame|ScriptCallQueue|Class|T)\s+\w+\s*\(', line):
                print(f'{relative}:{number}: {line.strip()}')
    if relative.endswith('CentralEconomy.c'):
        for number, line in enumerate((CACHE / relative).read_text().splitlines(), 1):
            if re.search(r'\b(ECE_IN_INVENTORY|ECE_NOPERSISTENCY_WORLD|ECE_NOLIFETIME)\b', line):
                print(f'{relative}:{number}: {line.strip()}')
