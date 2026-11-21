"""Config referential integrity, parsed as data; no source spelling assertions."""
import hashlib
import os
from pathlib import Path
import unittest

from tools.audit import pbo_config
from tests.legacy.test_infected_variety_routes import ROOT, policy


class VariantConfigTests(unittest.TestCase):
    def test_every_destination_is_defined_by_authored_or_pinned_stock_config(self):
        doc = policy()
        authored = pbo_config.parse_text_config(
            (ROOT / 'mods/HollowCountryAnims/config.cpp').read_bytes(), ('CfgVehicles',))['CfgVehicles']
        path = Path(os.environ.get('HC_STOCK_INFECTED_PBO',
            '/mnt/d/SteamLibrary/steamapps/common/DayZServer/addons/characters_zombies.pbo'))
        if not path.is_file():
            self.skipTest('set HC_STOCK_INFECTED_PBO to the pinned stock zombie addon')
        # External contract: addon SHA-256 identifies the native config snapshot.
        digest = hashlib.sha256()
        with path.open('rb') as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b''):
                digest.update(block)
        self.assertEqual(digest.hexdigest(), doc['evidence']['source_addon_sha256'])
        stock = pbo_config.read_configs(path, ('CfgVehicles',))['CfgVehicles']
        classes = {**stock, **authored}
        defined = {name.casefold() for name in classes}
        for row in doc['substitutions']:
            with self.subTest(destination=row['to']):
                self.assertIn(row['to'].casefold(), defined)


class GeneratedOutfitTests(unittest.TestCase):
    def test_pinned_stock_derives_complete_bounded_family_coverage(self):
        from tools.anim import ce_variants
        from tests.legacy.test_infected_variety_routes import stock_bytes
        from collections import Counter
        import xml.etree.ElementTree as ET
        doc = policy()
        stock = stock_bytes(self)
        path = Path(os.environ.get('HC_STOCK_INFECTED_PBO',
            '/mnt/d/SteamLibrary/steamapps/common/DayZServer/addons/characters_zombies.pbo'))
        if not path.is_file():
            self.skipTest('pinned stock zombie addon unavailable')
        classes, anim, baseline = ce_variants.stock_config(path.parent, doc)
        rows, coverage = ce_variants.derive(stock, doc, classes)
        self.assertEqual(rows, doc['substitutions'])
        self.assertEqual(coverage, doc['ce_pose_coverage'])
        events = {e.get('name'): e for e in ET.fromstring(stock)
                  if e.get('name').startswith('Infected')}
        self.assertEqual(coverage.keys(), events.keys())
        config = (ROOT / 'mods/HollowCountryAnims/config.cpp').read_text()
        self.assertEqual(ce_variants.render(config, doc, path.parent), config)
        authored = pbo_config.parse_text_config(config.encode(), ('CfgVehicles',))['CfgVehicles']
        for event, stats in coverage.items():
            variants = [r for r in rows if r['event'] == event and r['to'].startswith('HC_')]
            kinds = {r['to'].split('_', 3)[2] for r in variants}
            self.assertEqual(kinds, set(ce_variants.MODES))
            self.assertEqual(sum(r['share'] for r in variants), stats['weight'])
            self.assertLessEqual(stats['weight'], max(len(ce_variants.MODES), stats['stock_weight'] // 10))
            for row in variants:
                base = authored[row['to']]['parent']
                self.assertEqual(base.casefold(), row['from'].casefold())
                self.assertEqual(anim(base), baseline)
                self.assertEqual(doc['accessories']['explicit_classes'][row['to']], row['from'])
        females = Counter(r['to'].split('_', 3)[2] for r in rows
                          if r['to'].startswith('HC_') and r['from'].startswith('ZmbF_'))
        self.assertEqual(set(females), set(ce_variants.MODES))
        # A generated or stale policy may never silently reference a missing base.
        import copy
        broken = copy.deepcopy(doc)
        broken['substitutions'].append(dict(event=next(iter(events)),
            **{'from': 'ZmbF_Missing'}, to='HC_ZmbF_Sitter_ZmbF_Missing', share=1))
        with self.assertRaises(ValueError):
            ce_variants.render(config, broken, path.parent)
