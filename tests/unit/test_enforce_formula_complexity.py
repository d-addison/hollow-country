"""Static guard for the Enforce "Formula too complex" compile error.

Evidence (native, not offline): boot 046 on 2026-11-18 failed to compile
HCWorldData.c Valid() with `Formula too complex` on one `if` whose condition
held 12 `||` and 17 calls (13 Count() calls plus 3 HCAILimits.Get() chains).
The same 13-term condition with 14 calls had compiled in every earlier boot.
This test caps conditional statements at the largest call count that has
compiled natively; it does not establish the engine's exact limit.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
MAX_CALLS = 14
CONDITIONAL = ('if', 'else if', 'while', 'return')


def calls(line):
    code = re.sub(r'"(\\.|[^"\\])*"', '""', line.split('//')[0])
    if not code.strip().startswith(CONDITIONAL):
        return 0
    return len(re.findall(r'\w\s*\(', code))


class FormulaComplexityTests(unittest.TestCase):
    def test_no_conditional_exceeds_natively_compiled_call_count(self):
        over = []
        for path in sorted((ROOT / 'mods').rglob('*.c')):
            for number, line in enumerate(path.read_text(errors='replace').split('\n'), 1):
                count = calls(line)
                if count > MAX_CALLS:
                    over.append(f'{path.relative_to(ROOT)}:{number} calls={count}')
        self.assertEqual([], over)

    def test_counter_sees_the_failing_shape(self):
        line = '        if (' + ' || '.join(['a.B().C() > D'] * 9) + ') { return false; }'
        self.assertGreater(calls(line), MAX_CALLS)


if __name__ == '__main__':
    unittest.main()
