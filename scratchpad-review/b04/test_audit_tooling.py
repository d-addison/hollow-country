"""Static authored dependency check; no engine imports or process launch."""
import ast
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]


class AuditTooling(unittest.TestCase):
    def test_b04_probe_dependencies_use_standard_library_or_authored_tools(self):
        pending = [ROOT / name for name in (
            'tools/setup/infected_death_probe.py',
            'tools/setup/death_selection_probe.py',
            'tools/setup/wine_compile_probe.py', 'tools/validate/bdd.py')]
        seen = set()
        while pending:
            path = pending.pop()
            if path in seen:
                continue
            seen.add(path)
            tree = ast.parse(path.read_text(), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    self.assertEqual(0, node.level, str(path))
                    names = [node.module]
                    if node.module.startswith('tools'):
                        names.extend(node.module + '.' + alias.name for alias in node.names)
                else:
                    continue
                for name in names:
                    root = name.split('.')[0]
                    self.assertIn(root, sys.stdlib_module_names | {'tools'}, (str(path), name))
                    if root == 'tools':
                        candidate = ROOT / (name.replace('.', '/') + '.py')
                        if candidate.is_file():
                            pending.append(candidate)
        self.assertGreaterEqual(len(seen), 8)


if __name__ == '__main__':
    unittest.main(verbosity=2)
