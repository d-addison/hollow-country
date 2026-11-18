"""Enforce rejects a local name declared twice in one function, even in sibling blocks.

Text check over our own mod scripts only. The Expansion-stack Wine compile reported
"Multiple declaration of variable 'created'" (hcxaisites.c), and every later
JsonFileLoader/Param2 "Bad type" error cascaded from it. Establishes nothing about DayZ behaviour.
"""
from pathlib import Path
import re
import unittest

from tools.validate import enforce_source as es

ROOT = Path(__file__).resolve().parents[2]
DECL = re.compile(r'(?:^|[;{(]\s*|\bfor\s*\(\s*)(?:ref\s+|autoptr\s+)?'
                  r'(?:int|float|bool|string|vector|auto|[A-Z]\w*(?:<[\w<>, @]*>)?)\s+([a-z_]\w*)\s*(?==|;|:)')


def duplicate_locals(text):
    source = text if isinstance(text, es.Source) else es.Source(Path('<text>'), text)
    found = []
    for method in source.methods:
        names = set()
        # DECL is the legacy declaration policy, not a second lexer or scope scanner.
        for line in source.body(method).splitlines():
            for match in DECL.finditer(line.strip()):
                if match.group(1) in names:
                    found.append(match.group(1))
                names.add(match.group(1))
    return found


class EnforceLocalsTests(unittest.TestCase):
    def test_the_checker_sees_a_sibling_block_redeclaration(self):
        src = 'class A\n{\n    void F()\n    {\n        if (x)\n        {\n            Row created = new Row();\n        }\n        int created = 0;\n    }\n}\n'
        self.assertEqual(duplicate_locals(src), ['created'])
        self.assertEqual(duplicate_locals(src.replace('Row created', 'Row newRow')), [])

    def test_no_function_in_our_mods_declares_a_local_twice(self):
        bad = {}
        for source in es.mod_sources(ROOT, mods=('HollowCountry', 'HollowCountryExpansionAI')):
            names = duplicate_locals(source)
            if names:
                bad[source.rel] = names
        self.assertEqual(bad, {})


if __name__ == '__main__':
    unittest.main()
