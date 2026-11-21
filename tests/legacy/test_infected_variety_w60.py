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
