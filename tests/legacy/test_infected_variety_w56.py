"""Manifest relationships derived from authored inputs; no Enforce translation."""
import unittest
from tools.audit import pbo_config
from tests.legacy.test_infected_variety_routes import ROOT, policy


class VariantManifestTests(unittest.TestCase):
    def test_substitutions_have_unique_destinations_without_donor_overlap(self):
        rows = policy()['substitutions']
        self.assertTrue(rows, 'a substitution policy must exercise at least one route')
        donors = {(r['event'], r['from']) for r in rows}
        destinations = [(r['event'], r['to']) for r in rows]
        self.assertEqual(len(destinations), len(set(destinations)))
        self.assertTrue(donors.isdisjoint(destinations))
        for row in rows:
            with self.subTest(event=row['event'], destination=row['to']):
                self.assertIs(type(row['share']), int)
                self.assertGreater(row['share'], 0)

    def test_destinations_are_selected_in_the_authored_manifest(self):
        doc = policy()
        selected = {r['class'].casefold() for r in doc['entries'] if r['selected']}
        authored = pbo_config.parse_text_config(
            (ROOT / 'mods/HollowCountryAnims/config.cpp').read_bytes(), ('CfgVehicles',))['CfgVehicles']
        admitted = selected | {name.casefold() for name in authored}
        for row in doc['substitutions']:
            self.assertIn(row['to'].casefold(), admitted)
