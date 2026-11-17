"""Portable data/planner checks; no native acceptance is inferred."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

from tools.testing.automation import load_catalog, plan

ROOT = Path(__file__).resolve().parents[2]
# Independently pinned from the 68 original design-table rows at intake.
EXPECTED_CRITERIA_SHA256 = "59927132a049875aac540b7a101dbb0aa0efc8fc36fb9774ac8eccbf1b052825"
ORIGINAL = {
    f"{p}-{n:03d}"
    for p, count in (("AI", 12), ("AUD", 7), ("CE", 12), ("CRF", 7),
                     ("HOR", 11), ("INT", 11), ("NET", 8))
    for n in range(1, count + 1)
}


class PortableCatalogTests(unittest.TestCase):
    def setUp(self):
        self.catalog = load_catalog(ROOT / "tests/catalog.json")
        self.manifest = json.loads(
            (ROOT / "tests/capabilities.json").read_text(encoding="utf-8"))
        self.caps = self.manifest["capabilities"]

    def test_original_ids_and_pinned_normalized_criteria(self):
        rows = [r for r in self.catalog["tests"] if r["origin"] == "original"]
        self.assertEqual(len(rows), 68)
        self.assertEqual({r["id"] for r in rows}, ORIGINAL)
        normalized = sorted(
            [r["id"], r["scenario"], r["criterion"]] for r in rows)
        digest = hashlib.sha256(json.dumps(
            normalized, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")).hexdigest()
        self.assertEqual(digest, EXPECTED_CRITERIA_SHA256)
        self.assertEqual(self.catalog["coverage"]["extensions"]["mapped_count"],
                         len(self.catalog["tests"]) - 68)

    def test_prerequisites_never_create_pass_and_evidence_is_preserved(self):
        self.assertEqual(self.manifest["catalog_id"], self.catalog["catalog_id"])
        self.assertEqual(set(self.caps.values()), {"unknown"})
        self.assertEqual(set(self.caps),
                         {c for r in self.catalog["tests"] for c in r["requires"]})
        for state in ("unknown", "available"):
            report = plan(self.catalog, capabilities={c: state for c in self.caps})
            self.assertEqual(report["acceptance"], "not_evaluated")
            self.assertEqual(report["missing_original_ids"], [])
            self.assertEqual(report["counts"]["PASS"], 0)
            self.assertEqual(report["counts"]["FAIL"], 0)
            if state == "unknown":
                self.assertEqual(report["counts"]["BLOCKED"], len(report["tests"]))
            for source, result in zip(self.catalog["tests"], report["tests"]):
                self.assertEqual({k: result[k] for k in source}, source)

    def test_fuel_and_flashlight_required_constraints_remain(self):
        criteria = [r["criterion"].lower() for r in self.catalog["tests"]]
        for needle, terms in (
            ("siphon gasoline", ("finite", "capacity", "source/destination",
                                "interruption", "concurrent", "restart/recovery")),
            ("flashlight", ("guns/backpacks/helmets", "duct-tape",
                            "power/switch/beam", "conservation", "persistence",
                            "replicated", "unsupported geometry", "remove by hand",
                            "tape consumed", "fresh tape")),
        ):
            with self.subTest(feature=needle):
                self.assertTrue(any(needle in c and all(t in c for t in terms)
                                    for c in criteria))

    def test_two_file_export_plans_without_source_documents(self):
        expected = plan(self.catalog, capabilities=self.caps)
        with tempfile.TemporaryDirectory() as directory:
            export = Path(directory).resolve()
            for name in ("catalog.json", "capabilities.json"):
                (export / name).write_bytes((ROOT / "tests" / name).read_bytes())
            previous = Path.cwd()
            try:
                os.chdir(export)
                catalog = load_catalog("catalog.json")
                caps = json.loads(Path("capabilities.json").read_text(
                    encoding="utf-8"))["capabilities"]
                for source in catalog["sources"]:
                    self.assertFalse(Path(source["path"]).exists())
                self.assertEqual(plan(catalog, capabilities=caps), expected)
            finally:
                os.chdir(previous)

    def test_human_ai_recovery_exception_does_not_replace_infected_contract(self):
        rows = [r for r in self.catalog["tests"] if r["origin"] == "phase2"]
        terms = ("human pve ai", "built-in stuck recovery", "visible reposition",
                 "infected/horde", "finite ammunition", "damage", "cleanup")
        self.assertTrue(any(all(term in r["criterion"].lower() for term in terms)
                            for r in rows))
        scope = self.catalog["coverage"]["contract"].get("human_ai_recovery", "")
        self.assertIn("reviewed provider", scope)
        self.assertIn("original infected/horde criteria", scope)
