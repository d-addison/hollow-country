"""Synthetic planning tests; these never establish DayZ acceptance."""
import copy
import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.testing.automation import ORIGINAL_IDS, plan
from tools.testing import automation


def catalog():
    def row(identifier, modes, requires):
        return {
            "id": identifier, "origin": "synthetic",
            "scenario": "Explicit synthetic scenario",
            "criterion": "Explicit synthetic acceptance criterion",
            "modes": modes, "requires": requires,
            "assertions": ["An actual execution must check this"],
            "evidence_requirements": ["Actual execution evidence"],
            "related_ids": [],
        }
    return {
        "schema_version": 1, "catalog_id": "synthetic",
        "sources": [], "coverage": {},
        "tests": [
            row(identifier, ["gameplay"], ["native.server"])
            for identifier in sorted(ORIGINAL_IDS)
        ] + [row("AV-001", ["unittest"], ["python"])],
    }


class AutomationTests(unittest.TestCase):
    def test_cli_emits_plan_without_executing_or_claiming_passes(self):
        output = io.StringIO()
        with patch.object(automation, 'load_catalog', return_value=catalog()) as loader:
            with contextlib.redirect_stdout(output):
                code = automation.main(['catalog.json', '--capability', 'python=available',
                                        '--select', 'AV-001'])
        loader.assert_called_once_with(Path('catalog.json'))
        report = json.loads(output.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(report['mode'], 'planning-only')
        self.assertEqual(report['counts']['PASS'], 0)
        self.assertEqual(report['acceptance'], 'not_evaluated')
        self.assertEqual(report['tests'][-1]['status'], 'NOTRUN')

    def test_cli_invalid_or_duplicate_capability_fails_without_report(self):
        for arguments in (['python=yes'], ['python=available', 'python=blocked']):
            output = io.StringIO()
            with patch.object(automation, 'load_catalog', return_value=catalog()):
                with contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit) as error:
                        automation.main(['catalog.json'] + [piece for value in arguments
                                                           for piece in ('--capability', value)])
            self.assertEqual(error.exception.code, 2)
            self.assertEqual(output.getvalue(), '')

    def test_full_supplied_ledger_preserved_without_acceptance(self):
        source = catalog()
        before = copy.deepcopy(source)
        result = plan(source, capabilities={
            "python": "available", "native.server": "available"})
        self.assertEqual(len(result["tests"]), 69)
        self.assertEqual(result["counts"],
                         {"PASS": 0, "FAIL": 0, "BLOCKED": 68, "NOTRUN": 1})
        self.assertEqual(result["acceptance"], "not_evaluated")
        self.assertEqual(result["tests"][0]["criterion"],
                         source["tests"][0]["criterion"])
        result["tests"][0]["assertions"].append("Modified result")
        self.assertEqual(source, before)

    def test_unknown_capability_blocks_and_matching_is_exact(self):
        for capabilities in ({}, {"python": "unknown"},
                             {"pythonish": "available"}):
            result = plan(catalog(), capabilities=capabilities)
            self.assertEqual(result["tests"][-1]["status"], "BLOCKED")
            self.assertEqual(result["tests"][-1]["missing_capabilities"],
                             ["python"])

    def test_unselected_is_notrun_and_original_offline_is_blocked(self):
        source = catalog()
        source["tests"][0]["modes"] = ["runtime"]
        result = plan(source, capabilities={"native.server": "available"},
                      selected=[source["tests"][0]["id"]])
        self.assertEqual(result["tests"][0]["status"], "BLOCKED")
        self.assertEqual(result["tests"][-1]["status"], "NOTRUN")
        self.assertEqual(set(result["adapters"]),
                         {"unittest", "bdd", "runtime", "hygiene"})

    def test_strict_schema(self):
        mutations = [
            lambda c: c.update(schema_version=True),
            lambda c: c.update(command="arbitrary"),
            lambda c: c["tests"].append(copy.deepcopy(c["tests"][0])),
            lambda c: c["tests"][0].update(criterion=" "),
            lambda c: c["tests"][0].update(argv=["arbitrary"]),
            lambda c: c["tests"][0].update(requires=["x", "x"]),
        ]
        for mutation in mutations:
            source = catalog()
            mutation(source)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                plan(source)
        with self.assertRaises(ValueError):
            plan(catalog(), selected=["absent"])

    def test_partial_catalog_does_not_invent_missing_original_rows(self):
        source = catalog()
        source["tests"] = source["tests"][-1:]
        result = plan(source)
        self.assertEqual(len(result["tests"]), 1)
        self.assertEqual(len(result["missing_original_ids"]), 68)
        self.assertEqual(result["counts"]["PASS"], 0)

    def test_aggregate_input_budget_is_checked_before_json_allocation(self):
        with patch.object(automation.json, 'dumps', side_effect=AssertionError('unbounded allocation')):
            with self.assertRaises(ValueError):
                automation._encoded(['x' * 524288] * 3)

    @unittest.skipUnless(hasattr(os, 'mkfifo'), 'host has no FIFO')
    def test_special_catalog_is_rejected_before_blocking_open(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / 'catalog.json'
            os.mkfifo(source)
            with patch.object(Path, 'open', side_effect=AssertionError('must not block opening FIFO')):
                with self.assertRaises(ValueError):
                    automation.load_catalog(source)
