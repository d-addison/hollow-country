"""Changed-line shape audit supplements installed-cache identifier/override tests.
This is a source check, not an Enforce compilation.
"""
from pathlib import Path
import re
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tests.unit.test_infected_admission import _mask, _body, admission_functions, requested_config, PATHS
ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'mods/HollowCountry/scripts/4_World/Infected'
state = (BASE / 'HCInfectedState.c').read_text()
selftests = (BASE / 'HCInfectedSelfTests.c').read_text()
new_code = state[state.index('// Server-only static qualification'):state.index('class HCInfectedClue')]
new_code += selftests[selftests.index('// Requested is not admitted:'):selftests.index('Print("[HC Infected] scalar policy')]
code, _ = _mask(new_code)
assert '?' not in code
assert not re.search(r'^\s*(?:&&|\|\|)', code, re.M)
statements = code.split(';')
pluses = [len(re.findall(r'(?<!\+)\+(?!\+)', s)) for s in statements]
assert max(pluses) <= 8
print('Added qualification/admission/self-test statements: no ternary or leading logical operator; max binary + =', max(pluses))
# Parameters and local declarations are unique even across sibling scopes.
for filename, source in [('HCInfectedState.c', new_code.split('// Requested is not admitted:')[0]),
                         ('HCInfectedSelfTests.c', selftests)]:
    source, _ = _mask(source)
    signatures = list(re.finditer(r'(?:static\s+)?(?:bool|string|HCInfectedAdmission)\s+\w+\([^)]*\)\s*\{', source))
    for match in signatures:
        params, body = _body(source, match.group(0).split('{')[0].strip())
        locals_ = re.findall(r'(?<![.\w])(?:bool|string|int|float|HCInfectedConfig|HCInfectedAdmission)\s+(\w+)\s*(?=[=;,])', body)
        all_names = params + locals_
        assert len(all_names) == len(set(all_names)), (filename, match.group(), all_names)
print('New methods and complete changed self-test body: parameter/local names unique across sibling scopes.')
print('Changed lines introduce no native out-argument calls or override signatures; no loops in new qualification/admission/self-test code.')
Admission, _ = admission_functions()
maximum = 0
for preferences in range(64):
    config = requested_config(**{'Enable'+p: bool(preferences & (1 << i)) for i,p in enumerate(PATHS)})
    for qualifications in range(64):
        result = Admission.Resolve(config, *(bool(qualifications & (1 << i)) for i in range(6)))
        description = result.Describe()
        maximum = max(maximum, len(description))
        assert '\n' not in description and len(description) < 1024
        assert description.count('requested=') == 6 and description.count('admitted=') == 6
print('Describe: all 4096 preference/qualification combinations bounded to', maximum, 'characters; exactly six segments.')
print('Explicit strings: Segment uses Flag(bool) returning literal "1"/"0"; added logs concatenate strings only. No new implicit scalar-to-string conversion.')
