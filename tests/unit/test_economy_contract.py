"""Synthetic CE mini-mission. Tests only offline generation/install behavior.

The synthetic stock has none of the datamined classes, so these tests generate with the datamined
switch off; the datamined rows are covered in test_datamined_items.
"""
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock
import xml.etree.ElementTree as ET

from tools.package import economy


def synthetic(root):
    (root / 'db').mkdir(parents=True)
    (root / 'db/types.xml').write_text('''<types><type name="SyntheticSupply">
<nominal>10</nominal><min>5</min><lifetime>1000</lifetime><restock>100</restock><quantmin>-1</quantmin><quantmax>-1</quantmax><cost>100</cost>
<flags count_in_cargo="0" count_in_hoarder="1" count_in_map="1" count_in_player="0" crafted="0" deloot="0"/>
<category name="tools"/><usage name="Village"/><value name="Tier2"/>
</type></types>''')
    (root / 'cfgeconomycore.xml').write_bytes(b'<?xml version="1.0"?><economycore><!--keep exactly--><classes/><defaults><default name="log_ce_lootspawn" value="false"/></defaults></economycore>')
    (root / 'cfglimitsdefinition.xml').write_text('<lists><usageflags><usage name="Village"/><usage name="Town"/></usageflags></lists>')
    (root / 'mapgroupproto.xml').write_text('<prototype><group name="SyntheticApartment" lootmax="0"><container name="loot"/></group><group name="SyntheticBarracks" lootmax="1"><container><point pos="0 0 0"/></container></group></prototype>')
    (root / 'mapgrouppos.xml').write_text('<map><group name="SyntheticApartment" pos="1 2 3"/><group name="SyntheticBarracks" pos="4 5 6"/></map>')
    return {'schema': 1, 'name': 'synthetic-pilot', 'add_usage': {'SyntheticSupply': ['Town']}, 'diagnostics': ['log_ce_lootspawn']}


class EconomyBehavior(unittest.TestCase):
    def test_minimal_delta_preserves_replaced_usage_list_and_stock_budgets(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            profile = synthetic(root)
            before = {p.name: p.read_bytes() for p in root.rglob('*') if p.is_file()}
            delta = economy.generate(root, profile, include_datamined=False)
            x = ET.fromstring(delta['ce/types.xml'])
            item = x.find('type')
            self.assertEqual(item.attrib, {'name': 'SyntheticSupply'})
            self.assertEqual([n.get('name') for n in item.findall('usage')], ['Town', 'Village'])
            stock = ET.parse(root / 'db/types.xml').getroot().find('type')
            self.assertEqual(set(n.tag for n in item), set(n.tag for n in stock))
            self.assertEqual(item.findtext('nominal'), stock.findtext('nominal'))
            self.assertEqual(item.findtext('lifetime'), stock.findtext('lifetime'))
            self.assertEqual(item.find('flags').attrib, stock.find('flags').attrib)
            self.assertEqual(item.find('value').attrib, stock.find('value').attrib)
            self.assertEqual(before, {p.name: p.read_bytes() for p in root.rglob('*') if p.is_file()})
            report = json.loads(delta['economy-report.json'])
            self.assertIsNone(report['engine_eligible_loot_points'])
            self.assertFalse(report['loot_fix_claim'])
            self.assertEqual(report['raw_geometry'][0]['raw_points'], 0)
            self.assertEqual(report['status'], 'offline-only-runtime-pending')
            self.assertEqual(report['engine_merge_semantics'], 'unobserved')
            self.assertEqual(delta, economy.generate(root, profile, include_datamined=False))

    def test_reject_unknown_item_usage_or_unsupported_policy_and_modular_conflicts(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            good = synthetic(root)
            for patch in [{'add_usage': {'MissingItem': ['Town']}},
                          {'add_usage': {'SyntheticSupply': ['InventedRoom']}},
                          {'nominal_multiplier': 5}, {'mapgroupproto': 'fake'},
                          {'diagnostics': ['dyn_radius']}, {'add_usage': {'SyntheticSupply': []}}]:
                with self.subTest(patch=patch), self.assertRaises(ValueError):
                    economy.generate(root, dict(good, **patch), include_datamined=False)
            core = root / 'cfgeconomycore.xml'
            core.write_text('<economycore><ce folder="other"><file name="types.xml" type="types"/></ce></economycore>')
            with self.assertRaises(ValueError):
                economy.generate(root, good, include_datamined=False)

    def test_baseline_has_no_economy_changes(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            synthetic(root)
            delta = economy.generate(root, {'schema': 1, 'name': 'baseline', 'add_usage': {}, 'diagnostics': []},
                                      include_datamined=False)
            self.assertEqual(len(ET.fromstring(delta['ce/types.xml'])), 0)
            self.assertEqual(len(ET.fromstring(delta['cfgeconomycore.append.xml'])), 0)

    def test_stage_install_and_rollback_preserve_stock_bytes_and_reject_drift(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            source = root / 'source'
            source.mkdir()
            profile = synthetic(source)
            original = (source / 'cfgeconomycore.xml').read_bytes()
            stage = root / 'delta'
            economy.write_delta(stage, economy.generate(source, profile, include_datamined=False))
            import shutil
            target = root / 'private-copy'
            shutil.copytree(source, target)
            economy.install(stage, target)
            installed = (target / 'cfgeconomycore.xml').read_bytes()
            self.assertIn(b'<!--keep exactly-->', installed)
            self.assertIn(b'folder="hollow-country/ce"', installed)
            self.assertIn(b'value="true"', installed)
            self.assertEqual((source / 'cfgeconomycore.xml').read_bytes(), original)
            with self.assertRaises(ValueError):
                economy.install(stage, target)
            economy.rollback(target)
            self.assertEqual((target / 'cfgeconomycore.xml').read_bytes(), original)
            self.assertFalse((target / 'hollow-country').exists())
            (target / 'db/types.xml').write_text('<types/>')
            with self.assertRaises(ValueError):
                economy.install(stage, target)

    def test_install_rejects_tamper_stock_target_and_symlinks(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            source = root / 'source'
            source.mkdir()
            profile = synthetic(source)
            stage = root / 'delta'
            economy.write_delta(stage, economy.generate(source, profile, include_datamined=False))
            (stage / 'ce/types.xml').write_text('<types/>')
            with self.assertRaises(ValueError):
                economy.install(stage, source)
            with self.assertRaises(ValueError):
                economy.install(stage, Path('/mnt/d/SteamLibrary/steamapps/common/DayZServer/mpmissions/dayzOffline.chernarusplus'))

    def test_committed_ce_defaults_are_noop(self):
        root = Path('mission/hollow-country')
        self.assertEqual(len(ET.parse(root / 'ce/types.xml').getroot()), 0)
        self.assertEqual(len(ET.parse(root / 'cfgeconomycore.append.xml').getroot()), 0)

    def test_targeted_type_must_have_valid_native_budget_and_complete_flags(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            profile = synthetic(root)
            source = root / 'db/types.xml'
            original = source.read_text()
            for bad in [original.replace('<nominal>10', '<nominal>-1'),
                        original.replace('<min>5', '<min>11'),
                        original.replace('count_in_map="1"', 'count_in_map="2"'),
                        original.replace(' count_in_cargo="0"', '')]:
                source.write_text(bad)
                with self.subTest(bad=bad), self.assertRaises(ValueError):
                    economy.generate(root, profile, include_datamined=False)

    def test_stage_symlink_and_modified_rollback_are_refused(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            source = root / 'source'
            source.mkdir()
            profile = synthetic(source)
            stage = root / 'delta'
            economy.write_delta(stage, economy.generate(source, profile, include_datamined=False))
            path = stage / 'ce/types.xml'
            content = path.read_bytes()
            path.unlink()
            path.symlink_to(source / 'db/types.xml')
            with self.assertRaises(ValueError):
                economy.install(stage, source)
            path.unlink()
            path.write_bytes(content)
            economy.install(stage, source)
            core = source / 'cfgeconomycore.xml'
            core.write_bytes(core.read_bytes() + b'<!--operator change-->')
            with self.assertRaises(ValueError):
                economy.rollback(source)
            self.assertTrue((source / 'hollow-country/core.backup').is_file())

    def test_authored_profiles_are_explicitly_opt_in_and_counts_are_unchanged(self):
        profiles = Path('mission/hollow-country/economy-profiles')
        baseline = json.loads((profiles / 'baseline.json').read_text())
        pilot = json.loads((profiles / 'contextual-pilot.json').read_text())
        self.assertEqual(baseline['add_usage'], {})
        self.assertGreaterEqual(len(pilot['add_usage']), 3)
        self.assertEqual(set(pilot), {'schema', 'name', 'add_usage', 'diagnostics'})
        self.assertEqual(pilot['diagnostics'], [])


if __name__ == '__main__':
    unittest.main()


def failing_write(real, fail_name, partial=0):
    """fresh_write wrapper that dies on fail_name (after writing `partial` bytes if asked), like a kill."""
    def write(root, name, data):
        if name == fail_name:
            if partial:
                real(root, name, data[:partial])
            raise OSError('injected write failure before ' + fail_name)
        return real(root, name, data)
    return write


class BootstrapRecovery(unittest.TestCase):
    """An install that dies before receipt.json must not strand the operator (rollback recovers it)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        source = root / 'source'
        source.mkdir()
        profile = synthetic(source)
        self.original = (source / 'cfgeconomycore.xml').read_bytes()
        self.stage = root / 'delta'
        economy.write_delta(self.stage, economy.generate(source, profile, include_datamined=False))
        self.target = root / 'private-copy'
        shutil.copytree(source, self.target)
        self.core = self.target / 'cfgeconomycore.xml'
        self.managed = self.target / economy.MANAGED

    def strand(self, partial=0):
        with mock.patch.object(economy, 'fresh_write', failing_write(economy.fresh_write, 'receipt.json', partial)):
            with self.assertRaises(OSError):
                economy.install(self.stage, self.target)
        self.assertTrue(self.managed.is_dir())

    def test_kill_before_receipt_is_recovered_by_rollback_and_reinstall_works(self):
        self.strand()
        with self.assertRaises(ValueError):
            economy.install(self.stage, self.target)
        self.assertEqual(economy.rollback(self.target), 'recovered_bootstrap')
        self.assertFalse(self.managed.exists())
        self.assertEqual(self.core.read_bytes(), self.original)
        economy.install(self.stage, self.target)
        economy.rollback(self.target)
        self.assertEqual(self.core.read_bytes(), self.original)

    def test_kill_in_the_middle_of_the_core_backup_is_recovered(self):
        with mock.patch.object(economy, 'fresh_write', failing_write(economy.fresh_write, 'core.backup.next', 20)):
            with self.assertRaises(OSError):
                economy.install(self.stage, self.target)
        self.assertEqual((self.managed / 'core.backup.next').read_bytes(), self.original[:20])
        self.assertFalse((self.managed / 'core.backup').exists())
        self.assertEqual(economy.rollback(self.target), 'recovered_bootstrap')
        self.assertFalse(self.managed.exists())
        self.assertEqual(self.core.read_bytes(), self.original)

    def test_kill_in_the_middle_of_the_receipt_is_recovered(self):
        self.strand(partial=10)
        self.assertEqual((self.managed / 'receipt.json').stat().st_size, 10)
        self.assertEqual(economy.rollback(self.target), 'recovered_bootstrap')
        self.assertFalse(self.managed.exists())
        self.assertEqual(self.core.read_bytes(), self.original)

    def test_changed_core_is_refused_and_nothing_changes(self):
        self.strand()
        edited = self.original + b'<!--operator edit-->'
        self.core.write_bytes(edited)
        before = {p.relative_to(self.target).as_posix(): p.read_bytes() for p in self.target.rglob('*') if p.is_file()}
        with self.assertRaises(ValueError):
            economy.rollback(self.target)
        self.assertEqual(before, {p.relative_to(self.target).as_posix(): p.read_bytes()
                                  for p in self.target.rglob('*') if p.is_file()})

    def test_unexpected_managed_content_without_a_receipt_is_refused(self):
        self.strand()
        (self.managed / 'ce').mkdir()
        (self.managed / 'ce/types.xml').write_bytes(b'<types/>')
        with self.assertRaises(ValueError):
            economy.rollback(self.target)
        (self.managed / 'ce/types.xml').unlink()
        (self.managed / 'ce').rmdir()
        (self.managed / 'surprise.txt').write_bytes(b'operator')
        with self.assertRaises(ValueError):
            economy.rollback(self.target)
        self.assertEqual((self.managed / 'surprise.txt').read_bytes(), b'operator')
        self.assertEqual(self.core.read_bytes(), self.original)
