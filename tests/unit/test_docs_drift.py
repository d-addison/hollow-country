"""Synthetic checks for tools.validate.docs_drift; every tool, document and rule here is invented."""
from pathlib import Path
import tempfile
import unittest

from tools.validate import docs_drift

TOOL = '''"""Synthetic tool."""
import argparse


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--alpha")
    parser.add_argument("--beta", action="store_true")
    return parser
'''

SUBCOMMAND_TOOL = '''import argparse
from tools.pkg import helper


def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("build")
    return parser
'''

HELPER = '''def parse(parser):
    parser.add_argument("--delegated")
'''


class DocsDriftTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="hc-synthetic-docs-drift-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.put("tools/pkg/tool.py", TOOL)
        self.put("tools/pkg/sub.py", SUBCOMMAND_TOOL)
        self.put("tools/pkg/helper.py", HELPER)
        self.put("tools/pkg/run.sh", "#!/bin/sh\n")

    def put(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def drift(self, text, name="docs/GUIDE.md"):
        return docs_drift.command_drift(self.root, {name: text})

    def test_current_flags_modules_and_scripts_pass(self):
        text = ("Run `python3 -B -m tools.pkg.tool --alpha x --beta` or `python3 tools/pkg/tool.py --beta`.\n"
                "Use `python3 -B -m tools.pkg.tool --help`, then tools/pkg/run.sh.\n")
        self.assertEqual([], self.drift(text))

    def test_removed_flag_in_inline_command_fails_with_its_line(self):
        text = "intro\nRun `python3 -B -m tools.pkg.tool --alpha --gone`.\n"
        self.assertEqual([("doc_command_flag", "docs/GUIDE.md", 2)], self.drift(text))

    def test_flag_on_a_continuation_line_of_a_fenced_command_is_checked(self):
        text = "```sh\npython3 -B -m tools.pkg.tool --alpha 1 \\\n  --gone\n```\n"
        self.assertEqual([("doc_command_flag", "docs/GUIDE.md", 2)], self.drift(text))
        ok = "```sh\npython3 -B -m tools.pkg.tool --alpha 1 \\\n  --beta\n```\n"
        self.assertEqual([], self.drift(ok))

    def test_flag_after_a_pipe_or_in_prose_after_the_code_span_is_not_attributed(self):
        text = ("```sh\npython3 -B -m tools.pkg.tool --alpha | grep --gone\n```\n"
                "Run `python3 -B -m tools.pkg.tool` which no longer takes --gone.\n")
        self.assertEqual([], self.drift(text))

    def test_inline_command_wrapped_over_lines_is_checked(self):
        text = "(`python3 -B -m tools.pkg.tool --alpha\n--gone x`)\n"
        self.assertEqual([("doc_command_flag", "docs/GUIDE.md", 1)], self.drift(text))

    def test_missing_module_and_missing_script_path_fail(self):
        text = "`python3 -B -m tools.pkg.absent --alpha`\n`python3 tools/pkg/absent.py`\nsee tools/pkg/old.sh\n"
        self.assertEqual([("doc_command_module", "docs/GUIDE.md", 1), ("doc_script_path", "docs/GUIDE.md", 2),
                          ("doc_script_path", "docs/GUIDE.md", 3)], self.drift(text))

    def test_flags_of_a_directly_imported_tools_module_count(self):
        self.assertEqual([], self.drift("`python3 -B -m tools.pkg.sub build --delegated`\n"))
        self.assertEqual([("doc_command_flag", "docs/GUIDE.md", 1)],
                         self.drift("`python3 -B -m tools.pkg.sub build --other`\n"))

    def test_unknown_subcommand_fails_only_for_tools_with_subcommands(self):
        self.assertEqual([("doc_command_subcommand", "docs/GUIDE.md", 1)],
                         self.drift("`python3 -B -m tools.pkg.sub retired --delegated`\n"))
        self.assertEqual([], self.drift("`python3 -B -m tools.pkg.tool server.RPT --alpha`\n"))

    def test_unknown_rule_id_in_a_document_fails_and_reserved_and_asset_ids_pass(self):
        documents = {"docs/RULES.md": "HC-E001 and HC-P003\nHC-E999 is invented\nThere is no HC-P002.\nHC-A011\n"}
        found = docs_drift.rule_drift(documents, {"HC-E001"}, {"HC-P003"}, {"HC-A011"})
        self.assertEqual([("doc_rule_unknown", "docs/RULES.md", 2)], found)

    def test_rule_without_any_document_fails_with_its_number(self):
        documents = {"docs/RULES.md": "HC-E001\n"}
        found = docs_drift.rule_drift(documents, {"HC-E001", "HC-E047"}, {"HC-P011"})
        self.assertEqual([("rule_undocumented", "tools/validate/enforce_lint.py", 47),
                          ("rule_undocumented", "tools/validate/enforce_perf.py", 11)], found)

    def test_calibration_line_must_exist_and_match_the_corpus_size(self):
        doc = docs_drift.CALIBRATION_DOC
        self.assertEqual([("doc_calibration", doc, 0)], docs_drift.calibration_drift({doc: "no line\n"}, 13))
        self.assertEqual([], docs_drift.calibration_drift({doc: "x\nCalibration status: 0/13\n"}, 13))
        self.assertEqual([("doc_calibration", doc, 2)],
                         docs_drift.calibration_drift({doc: "x\nCalibration status: 14/14\n"}, 13))
        self.assertEqual([], docs_drift.calibration_drift({}, 13))

    def test_corpus_total_counts_the_rows_in_source(self):
        self.put("tools/release/wb_calibrate.py", "CORPUS = (\n    ('a', 'x'),\n    ('b', 'y'),\n)\n")
        self.assertEqual(2, docs_drift.corpus_total(self.root))
        self.assertIsNone(docs_drift.corpus_total(self.root / "missing"))

    def test_the_checked_in_documents_have_no_drift(self):
        import subprocess
        names = subprocess.run(["git", "-C", str(docs_drift.ROOT), "ls-files", "*.md"], check=True,
                               capture_output=True, text=True).stdout.split("\n")
        documents = {name: (docs_drift.ROOT / name).read_text(encoding="utf-8")
                     for name in names if name and (docs_drift.ROOT / name).is_file()}
        self.assertEqual([], docs_drift.check(docs_drift.ROOT, documents))


if __name__ == "__main__":
    unittest.main()
