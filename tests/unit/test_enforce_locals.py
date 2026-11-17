"""Enforce rejects a local name declared twice in one function, even in sibling blocks.

Text check over our own mod scripts only. The Expansion-stack Wine compile reported
"Multiple declaration of variable 'created'" (hcxaisites.c), and every later
JsonFileLoader/Param2 "Bad type" error cascaded from it. Establishes nothing about DayZ behaviour.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
DECL = re.compile(r'(?:^|[;{(]\s*|\bfor\s*\(\s*)(?:ref\s+|autoptr\s+)?'
                  r'(?:int|float|bool|string|vector|auto|[A-Z]\w*(?:<[\w<>, @]*>)?)\s+([a-z_]\w*)\s*(?==|;|:)')


def duplicate_locals(text):
    text = re.sub(r'//[^\n]*', '', text)
    text = re.sub(r'"(?:[^"\\]|\\.)*"', '""', text)
    found, depth, names = [], 0, None
    for line in text.split('\n'):
        for match in DECL.finditer(line.strip()):
            if depth >= 2 and names is not None:
                if match.group(1) in names:
                    found.append(match.group(1))
                names.add(match.group(1))
        for ch in line:
            if ch == '{':
                depth += 1
                if depth == 2:
                    names = set()
            elif ch == '}':
                depth -= 1
                if depth == 1:
                    names = None
    return found


class EnforceLocalsTests(unittest.TestCase):
    def test_the_checker_sees_a_sibling_block_redeclaration(self):
        src = 'class A\n{\n    void F()\n    {\n        if (x)\n        {\n            Row created = new Row();\n        }\n        int created = 0;\n    }\n}\n'
        self.assertEqual(duplicate_locals(src), ['created'])
        self.assertEqual(duplicate_locals(src.replace('Row created', 'Row newRow')), [])

    def test_no_function_in_our_mods_declares_a_local_twice(self):
        bad = {}
        for mod in ('HollowCountry', 'HollowCountryExpansionAI'):
            for path in sorted((ROOT / 'mods' / mod / 'scripts').rglob('*.c')):
                names = duplicate_locals(path.read_text(encoding='utf-8'))
                if names:
                    bad[path.relative_to(ROOT).as_posix()] = names
        self.assertEqual(bad, {})


if __name__ == '__main__':
    unittest.main()
