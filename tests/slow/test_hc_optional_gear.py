"""HC-61: explicit synthetic Workshop/PBO and mission fixtures; no runtime evidence."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

from tools.package import economy, snafu_optional as sf, tactical_flava_optional as tf
from tests.slow import test_snafu_optional as sf_fixture
from tests.slow import test_tactical_flava_optional as tf_fixture


try:
    from tests.unit import hash_cache_isolation
except ImportError:  # run as a script from tests/unit
    import hash_cache_isolation


def setUpModule():
    # #194: the whole-PBO hashing path reads/writes the hash cache; never the user's.
    hash_cache_isolation.enter()


def tearDownModule():
    hash_cache_isolation.leave()


class OptionalGear(unittest.TestCase):
    def test_optional_family_budget_pins_parts_and_rollback(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sf_fixture.patch_roster(self, root)
            for module, fixture in ((sf, sf_fixture), (tf, tf_fixture)):
                with self.subTest(pack=module.MANAGED):
                    mission = root / module.MANAGED
                    mission.mkdir()
                    tf_fixture.mission(mission)
                    installed = root / (module.MANAGED + '-dependency')
                    fixture.build_install(installed)
                    allow = (sf_fixture.allowlist(*sf_fixture.GOOD) if module is sf
                             else tf_fixture.allowlist(*tf_fixture.good()))
                    kwargs = {} if module is sf else {'vanilla': tf_fixture.VANILLA}
                    report = module.verify_install(installed, allow, **kwargs)
                    files = module.generate(mission, allow, report)
                    # A self-consistent transport manifest must not authorize extra supply.
                    changed = copy.deepcopy(files)
                    types = ET.fromstring(changed['ce/types.xml'])
                    types[0].find('nominal').text = '999'
                    changed['ce/types.xml'] = ET.tostring(types)
                    manifest = json.loads(changed['delta-manifest.json'])
                    manifest['files']['ce/types.xml'] = economy.sha(changed['ce/types.xml'])
                    changed['delta-manifest.json'] = economy.encode(manifest)
                    stage = root / (module.MANAGED + '-over-budget')
                    module.write_delta(stage, changed)
                    before = tf_fixture.files_of(mission)
                    with self.assertRaisesRegex(ValueError, 'HC61_FAMILY_BUDGET'):
                        module.install(stage, mission)
                    self.assertEqual(tf_fixture.files_of(mission), before)
                    # The untouched package still uses the existing byte-exact rollback protocol.
                    clean = root / (module.MANAGED + '-clean')
                    module.write_delta(clean, files)
                    module.install(clean, mission)
                    module.rollback(mission)
                    self.assertEqual(tf_fixture.files_of(mission), before)

                    # Explicit synthetic HC-61 policy, derived from invented fixture PBOs.
                    policy = {'schema': 1, 'members': [], 'family_budgets': [],
                              'dependency_pins': [{k: row[k] for k in ('name', 'size', 'sha256')}
                                                  for row in report['install']['pbos']],
                              'aggregate_weapon_budget': {'nominal': 62, 'min': 31},
                              'refusals': ['HC61_SUBSET_RUNTIME_PENDING']}
                    for entry in allow['entries']:
                        weight = 20 if entry['kind'] == 'ammo' else 1
                        policy['members'].append({
                            'class': entry['class'], 'family': entry['class'], 'unit_rounds': weight,
                            'parts': [{'class': name, 'route': 'native-carrier'}
                                      for name in entry.get('optic_requires', [])]})
                        policy['family_budgets'].append({
                            'family': entry['class'],
                            'kind': entry['kind'] if entry['kind'] in sf.KINDS else 'magazine',
                            **{field: entry['set'][field] * weight for field in ('nominal', 'min')}})
                    allow['hc61'] = policy
                    module.validate_allowlist(allow)
                    pinned = module.verify_install(installed, allow, **kwargs)
                    self.assertEqual(pinned['status'], 'verified')
                    approved_files = module.generate(mission, allow, pinned)
                    summary = json.loads(approved_files['economy-report.json'])['hc61']
                    self.assertEqual(summary['state'], 'off')
                    self.assertIsNone(summary['observed_families'])
                    self.assertIn('[HC Plan] HC-61 optional_families=', summary['diagnostic'])
                    with self.assertRaisesRegex(ValueError, 'HC61_FAMILY_BUDGET'):
                        module.generate(mission, allow, pinned, nominal_scale=4)
                    # Parts stay on the exact inspected M14-style native carrier seam.
                    bad_parts = copy.deepcopy(allow)
                    bad_parts['hc61']['members'][0]['parts'] = [
                        {'class': 'SyntheticGuessedMuzzle', 'route': 'native-carrier'}]
                    with self.assertRaisesRegex(ValueError, 'HC61_PART_ROUTE_UNSUPPORTED'):
                        module.validate_allowlist(bad_parts)
                    # A matching allowlist hash alone cannot substitute different PBO bytes.
                    stale = copy.deepcopy(pinned)
                    stale['install']['pbos'][0]['sha256'] = '0' * 64
                    with self.assertRaisesRegex(ValueError, 'HC61_DEPENDENCY_PIN_MISMATCH'):
                        module.generate(mission, allow, stale)
                    addon_folder = next(p for p in installed.iterdir() if p.name.lower() == 'addons')
                    pbo_path = next(addon_folder.glob('*.pbo'))
                    original_pbo = pbo_path.read_bytes()  # tiny invented fixture only
                    pbo_path.write_bytes(original_pbo[:-1] + bytes([original_pbo[-1] ^ 1]))
                    drift = module.verify_install(installed, allow, **kwargs)
                    self.assertEqual(drift['status'], 'unverified')
                    self.assertIn('HC61_DEPENDENCY_PIN_MISMATCH', drift['install']['problems'])
                    pbo_path.write_bytes(original_pbo)
                    pinned_stage = root / (module.MANAGED + '-pinned')
                    module.write_delta(pinned_stage, approved_files)
                    if module is tf:
                        # Unstated dependency_use (the real TF allowlist shape) must still install:
                        # the owner accepted the pack as a dependency.
                        self.assertEqual(allow['rights']['dependency_use'], 'unstated')
                        spawnable = ET.fromstring(approved_files[tf.SPAWNABLE])
                        self.assertEqual(spawnable.find('type/attachments/item').get('name'), 'SynAdapter')
                    module.install(pinned_stage, mission)
                    module.rollback(mission)
                    self.assertEqual(tf_fixture.files_of(mission), before)
                    if module is tf:
                        continue  # The recolour case below uses the SNAFU fixture shape.

                    # A recolour must split its parent's ceiling, never add a second full share.
                    recolour = copy.deepcopy(allow)
                    recolour['entries'].append(sf_fixture.entry('SynBaseModel', snafu_ammo=['SynAmmoA']))
                    recolour['hc61']['members'].append({
                        'class': 'SynBaseModel', 'family': 'SynWood', 'unit_rounds': 1, 'parts': []})
                    with self.assertRaisesRegex(ValueError, 'HC61_FAMILY_BUDGET'):
                        sf.validate_allowlist(recolour)
                    recolour['entries'][0]['set'].update(nominal=1, min=0)
                    recolour['entries'][-1]['set'].update(nominal=1, min=1)
                    split_report = sf.verify_install(installed, recolour)
                    self.assertEqual(split_report['status'], 'verified')
                    split = sf.generate(mission, recolour, split_report)
                    split_summary = json.loads(split['economy-report.json'])['hc61']
                    wood = next(row for row in split_summary['families'] if row['family'] == 'SynWood')
                    self.assertEqual(wood['candidate'], {'nominal': 2, 'min': 1})
                    # The maximum cartridge count of a box cannot be erased to buy extra items.
                    box = copy.deepcopy(allow)
                    box['entries'].append(sf_fixture.entry('SynAmmoBox', kind='ammo', role='support',
                                                            nominal=1, minimum=0))
                    box['hc61']['members'].append({
                        'class': 'SynAmmoBox', 'family': 'SynAmmoA', 'unit_rounds': 40, 'parts': []})
                    with self.assertRaisesRegex(ValueError, 'HC61_FAMILY_BUDGET'):
                        sf.validate_allowlist(box)
                    lied_units = copy.deepcopy(allow)
                    next(m for m in lied_units['hc61']['members'] if m['class'] == 'SynAmmoA')['unit_rounds'] = 1
                    unit_report = sf.verify_install(installed, lied_units)
                    self.assertEqual(unit_report['status'], 'unverified')
                    self.assertIn('HC61_AMMO_CAPACITY_UNVERIFIED:SynAmmoA', unit_report['install']['problems'])
                    # The aggregate cap is independent of a family's individual allowance.
                    capped = copy.deepcopy(allow)
                    capped['hc61']['aggregate_weapon_budget'] = {'nominal': 1, 'min': 1}
                    capped_report = sf.verify_install(installed, capped)
                    with self.assertRaisesRegex(ValueError, 'HC61_AGGREGATE_BUDGET_EXCEEDED'):
                        sf.generate(mission, capped, capped_report)
                    # Explicit synthetic second overlay: each pack fits alone, together they exceed it.
                    capped['hc61']['aggregate_weapon_budget'] = {'nominal': 6, 'min': 3}
                    companion = copy.deepcopy(capped)
                    names = {entry['class']: 'Other' + entry['class'] for entry in companion['entries']}
                    for entry in companion['entries']:
                        entry['class'] = names[entry['class']]
                        for field in ('snafu_ammo', 'magazines'):
                            if field in entry:
                                entry[field] = [names.get(name, name) for name in entry[field]]
                    for member in companion['hc61']['members']:
                        member['class'] = names[member['class']]
                    companion_xml = ET.Element('types')
                    for entry in companion['entries']:
                        companion_xml.append(sf._new_type(entry))
                    other_folder = mission / tf.MANAGED
                    (other_folder / 'ce').mkdir(parents=True)
                    (other_folder / 'ce/types.xml').write_bytes(ET.tostring(companion_xml))
                    (other_folder / 'verification.json').write_bytes(economy.encode({
                        'allowlist': companion, 'allowlist_sha256': sf.allowlist_sha256(companion)}))
                    core_path = mission / 'cfgeconomycore.xml'
                    core_path.write_bytes(core_path.read_bytes().replace(
                        b'</economycore>', b'<ce folder="hollow-country-tactical-flava/ce">'
                        b'<file name="types.xml" type="types"/></ce></economycore>'))
                    capped_report = sf.verify_install(installed, capped)
                    with self.assertRaisesRegex(ValueError, 'HC61_AGGREGATE_BUDGET_EXCEEDED'):
                        sf.generate(mission, capped, capped_report)
