"""Native-audit batch B: cfggameplay delta, spawn kit and infected leg zones.

Synthetic fixtures are explicit. Offline tests never establish DayZ behavior:
every runtime effect stays pending local acceptance. Tests that cite native
evidence read the locally installed caches and skip when they are absent.
"""
import copy
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import unittest

from tools.package import economy, gameplay, pbo

ROOT = Path(__file__).resolve().parents[2]
MISSION = ROOT / 'mission/hollow-country'
PROFILE = MISSION / 'gameplay-profiles/hollow-country-v1.json'
PRESET = MISSION / 'gear/hardscrabble.json'
CACHE = Path(os.environ.get('HC_CACHE', Path.home() / '.cache/hollow-country'))
MISSIONS = CACHE / 'wine-server-20261116/mpmissions'
ADDONS = CACHE / 'wine-server-20261116/addons'
WORKBOOK = CACHE / 'item-review-035-full-20261116/workbook.json'

# Synthetic copy of the observed vanilla curves (cfggameplay.json WorldsData).
# A cache-guarded test below asserts these equal the installed mission files.
CHERNARUS_MIN = [-3, -2, 0, 4, 9, 14, 18, 17, 13, 11, 9, 0]
CHERNARUS_MAX = [3, 5, 7, 14, 19, 24, 26, 25, 18, 14, 10, 5]
SAKHAL_MIN = [-6.5, -9.5, -6.5, -9.5, 2, 6, 9, 10, 6, 1, -5, -10]
SAKHAL_MAX = [-3, -5, -3, -5, 9, 14, 16, 17, 14, 8, 1, -3]
NASDARA_MIN = [3.4, 5.4, 7.4, 8.4, 9.4, 12.4, 14.4, 13.4, 11.4, 8.4, 7.4, 4.4]
NASDARA_MAX = [17.4, 19.4, 22.4, 25.4, 29.4, 34.4, 38.4, 37.4, 34.4, 28.4, 22.4, 18.4]


def synthetic_source(root):
    """Synthetic mission with a cfggameplay.json that has unknown keys and stamina."""
    root.mkdir(parents=True)
    data = {
        'version': 123,
        'GeneralData': {'disableBaseDamage': False},
        'PlayerData': {
            'disablePersonalLight': False,
            'StaminaData': {'sprintStaminaModifierErc': 1.0, 'staminaMax': 100.0,
                            'staminaKgToStaminaPercentPenalty': 1.75},
            'MovementData': {'allowStaminaAffectInertia': True},
            'DrowningData': {'staminaDepletionSpeed': 10.0},
            'WeaponObstructionData': {'staticMode': 1, 'dynamicMode': 1},
            'SyntheticFutureKey': {'kept': [1, 2, 3]},
        },
        'WorldsData': {
            'lightingConfig': 0, 'objectSpawnersArr': [],
            'environmentMinTemps': list(CHERNARUS_MIN),
            'environmentMaxTemps': list(CHERNARUS_MAX),
            'wetnessWeightModifiers': [1.0, 1.0, 1.33, 1.66, 2.0],
        },
        'UIData': {'use3DMap': False, 'HitIndicationData': {
            'hitDirectionOverrideEnabled': False, 'hitDirectionBehaviour': 1,
            'hitDirectionStyle': 0, 'hitDirectionIndicatorColorStr': '0xffbb0a1e',
            'hitDirectionMaxDuration': 2.0, 'hitDirectionBreakPointRelative': 0.2,
            'hitDirectionScatter': 10.0, 'hitIndicationPostProcessEnabled': True}},
        'SyntheticTopLevelFuture': {'a': 1},
    }
    (root / 'cfggameplay.json').write_text(json.dumps(data, indent='\t') + '\n')
    return data


def committed():
    return json.loads(PROFILE.read_text()), json.loads(PRESET.read_text())


def flat(value, prefix=()):
    if isinstance(value, dict):
        for k, v in value.items():
            yield from flat(v, prefix + (k,))
    else:
        yield prefix, value


def month_margins(low, high):
    return [h - l for l, h in zip(low, high)]


class DeltaContent(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='hc-synthetic-gameplay-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source'
        self.original = synthetic_source(self.source)
        self.profile, self.preset = committed()

    def generate(self, profile=None, preset=None):
        return gameplay.generate(self.source, profile or self.profile, preset or self.preset)

    def test_delta_contains_only_hc_owned_key_paths(self):
        delta = json.loads(self.generate()['cfggameplay.delta.json'])
        paths = {'.'.join(p) for p, _ in flat(delta)}
        self.assertEqual(paths, {
            'PlayerData.spawnGearPresetFiles',
            'PlayerData.WeaponObstructionData.staticMode',
            'PlayerData.WeaponObstructionData.dynamicMode',
            'WorldsData.environmentMinTemps', 'WorldsData.environmentMaxTemps',
            'WorldsData.wetnessWeightModifiers',
            *('UIData.HitIndicationData.' + k for k in (
                'hitDirectionOverrideEnabled', 'hitDirectionBehaviour', 'hitDirectionStyle',
                'hitDirectionIndicatorColorStr', 'hitDirectionMaxDuration',
                'hitDirectionBreakPointRelative', 'hitDirectionScatter',
                'hitIndicationPostProcessEnabled'))})
        self.assertNotIn('version', delta)

    def test_merge_keeps_version_unknown_keys_and_every_unowned_value(self):
        files = self.generate()
        merged = json.loads(files['cfggameplay.merged.json'])
        delta = json.loads(files['cfggameplay.delta.json'])
        self.assertEqual(merged['version'], 123)
        self.assertEqual(merged['SyntheticTopLevelFuture'], {'a': 1})
        self.assertEqual(merged['PlayerData']['SyntheticFutureKey'], {'kept': [1, 2, 3]})
        owned = {p for p, _ in flat(delta)}
        for path, value in flat(self.original):
            if path not in owned:
                node = merged
                for part in path:
                    node = node[part]
                self.assertEqual(node, value, path)
        self.assertEqual(list(merged), list(self.original))  # source key order kept
        # Source bytes are never modified by generation.
        self.assertEqual(json.loads((self.source / 'cfggameplay.json').read_text()), self.original)

    def test_stamina_keys_are_never_touched_and_single_owner_is_pinned(self):
        files = self.generate()
        merged = json.loads(files['cfggameplay.merged.json'])
        for section in ('StaminaData', 'MovementData', 'DrowningData'):
            self.assertEqual(merged['PlayerData'][section], self.original['PlayerData'][section])
        self.assertNotIn('StaminaData', json.loads(files['cfggameplay.delta.json']).get('PlayerData', {}))
        self.assertNotIn('StaminaData', json.dumps(self.profile))
        bad = copy.deepcopy(self.profile)
        bad['cfggameplay']['PlayerData']['StaminaData'] = {'sprintStaminaModifierErc': 0.5}
        with self.assertRaises(ValueError):
            self.generate(bad)
        for key in ('MovementData', 'DrowningData'):
            bad = copy.deepcopy(self.profile)
            bad['cfggameplay']['PlayerData'][key] = {}
            bad['cfggameplay']['PlayerData'][key]['x'] = 1
            with self.assertRaises(ValueError):
                self.generate(bad)

    def test_temperature_is_bounded_cold_but_not_harsh(self):
        merged = json.loads(self.generate()['cfggameplay.merged.json'])
        low = merged['WorldsData']['environmentMinTemps']
        high = merged['WorldsData']['environmentMaxTemps']
        self.assertEqual((len(low), len(high)), (12, 12))
        for month in range(12):
            self.assertTrue(-3 <= low[month] - CHERNARUS_MIN[month] <= 0, month)
            self.assertTrue(-2 <= high[month] - CHERNARUS_MAX[month] <= 0, month)
            self.assertLess(low[month], high[month])
        # Colder somewhere on both curves, but the summer stays comfortable.
        self.assertLess(sum(low), sum(CHERNARUS_MIN))
        self.assertLess(sum(high), sum(CHERNARUS_MAX))
        for month in (5, 6, 7):
            self.assertGreaterEqual(low[month], 12)
            self.assertGreaterEqual(high[month], 23)

    def assert_milder_than_sakhal(self, low, high):
        for month in range(12):
            self.assertGreaterEqual(low[month] - SAKHAL_MIN[month], 1.5, month)
            self.assertGreaterEqual(high[month] - SAKHAL_MAX[month], 3, month)
        self.assertGreaterEqual(sum(low) / 12 - sum(SAKHAL_MIN) / 12, 5)
        self.assertGreaterEqual(sum(high) / 12 - sum(SAKHAL_MAX) / 12, 7)

    def test_result_is_clearly_milder_than_sakhal_synthetic_fixture(self):
        merged = json.loads(self.generate()['cfggameplay.merged.json'])
        self.assert_milder_than_sakhal(merged['WorldsData']['environmentMinTemps'],
                                       merged['WorldsData']['environmentMaxTemps'])

    def test_nasdara_vanilla_curve_is_warm_not_cold_synthetic_fixture(self):
        # Observed evidence the owner should see: Nasdara's own vanilla curve is a
        # warm one (maximums 8+ C above vanilla Chernarus every month, lowest
        # minimum above Chernarus'), not a cold one.
        for month in range(12):
            self.assertGreaterEqual(NASDARA_MAX[month] - CHERNARUS_MAX[month], 8, month)
        self.assertGreater(min(NASDARA_MIN), min(CHERNARUS_MIN))
        self.assertGreater(sum(NASDARA_MIN), sum(CHERNARUS_MIN))

    def test_result_is_colder_than_the_warm_nasdara_curve_synthetic_fixture(self):
        merged = json.loads(self.generate()['cfggameplay.merged.json'])
        low = merged['WorldsData']['environmentMinTemps']
        high = merged['WorldsData']['environmentMaxTemps']
        for month in range(12):
            self.assertLess(high[month], NASDARA_MAX[month] - 8, month)
        self.assertLess(min(low), min(NASDARA_MIN))

    def test_temperature_profile_is_refused_when_out_of_bounds_or_malformed(self):
        for field, bad in (('min_delta', [-4] + [-2] * 11), ('max_delta', [-3] + [-1] * 11),
                           ('min_delta', [1] + [-2] * 11), ('max_delta', [0.5] + [-1] * 11),
                           ('min_delta', [-2] * 11), ('max_delta', [-1] * 13),
                           ('min_delta', [True] + [-2] * 11), ('max_delta', ['x'] + [-1] * 11)):
            profile = copy.deepcopy(self.profile)
            profile['temperature'][field] = bad
            with self.subTest(field=field, bad=bad), self.assertRaises(ValueError):
                self.generate(profile)
        data = copy.deepcopy(self.original)
        del data['WorldsData']['environmentMinTemps']
        (self.source / 'cfggameplay.json').write_text(json.dumps(data))
        with self.assertRaises(ValueError):
            self.generate()

    def test_fairness_values_match_native_enums_and_are_validated(self):
        merged = json.loads(self.generate()['cfggameplay.merged.json'])
        obstruction = merged['PlayerData']['WeaponObstructionData']
        self.assertEqual(obstruction, {'staticMode': 2, 'dynamicMode': 1})  # ALWAYS / ENABLED
        wet = merged['WorldsData']['wetnessWeightModifiers']
        native = [1.0, 1.0, 1.33, 1.66, 2.0]
        self.assertEqual(len(wet), 5)
        self.assertEqual(wet[0], 1.0)
        for new, old in zip(wet, native):
            self.assertTrue(old <= new <= old * 1.2 + 1e-9)
        self.assertEqual(wet, sorted(wet))
        self.assertGreater(sum(wet), sum(native))
        hit = merged['UIData']['HitIndicationData']
        self.assertIs(hit['hitDirectionOverrideEnabled'], True)  # without it every other key is ignored
        self.assertEqual(hit['hitDirectionBehaviour'], 2)  # HitDirectionModes.DYNAMIC
        self.assertGreater(hit['hitDirectionMaxDuration'], 2.0)
        self.assertLess(hit['hitDirectionScatter'], 10.0)
        self.assertIs(hit['hitIndicationPostProcessEnabled'], True)
        for path, bad in ((('PlayerData', 'WeaponObstructionData', 'staticMode'), 3),
                          (('PlayerData', 'WeaponObstructionData', 'dynamicMode'), True),
                          (('WorldsData', 'wetnessWeightModifiers'), [1.0, 1.0, 1.33, 1.66]),
                          (('WorldsData', 'wetnessWeightModifiers'), [1.1, 1.2, 1.5, 1.8, 2.2]),
                          (('WorldsData', 'wetnessWeightModifiers'), [1.0, 1.0, 1.0, 1.0, 1.0]),
                          (('WorldsData', 'wetnessWeightModifiers'), [1.0, 1.5, 1.4, 1.8, 2.3]),
                          (('WorldsData', 'wetnessWeightModifiers'), [1.0, 1.5, 2.5, 3.0, 4.0]),
                          (('UIData', 'HitIndicationData', 'hitDirectionStyle'), 3),
                          (('UIData', 'HitIndicationData', 'hitDirectionScatter'), 181),
                          (('UIData', 'HitIndicationData', 'hitDirectionIndicatorColorStr'), 'red'),
                          (('UIData', 'HitIndicationData', 'hitDirectionBreakPointRelative'), 1.5),
                          (('PlayerData', 'spawnGearPresetFiles'), ['../escape.json']),
                          (('PlayerData', 'spawnGearPresetFiles'), ['other/file.json'])):
            profile = copy.deepcopy(self.profile)
            node = profile['cfggameplay']
            for part in path[:-1]:
                node = node[part]
            node[path[-1]] = bad
            with self.subTest(path=path, bad=bad), self.assertRaises(ValueError):
                self.generate(profile)

    def test_hit_indication_requires_every_native_key(self):
        # Native loader: members absent from the JSON are treated as 0.
        profile = copy.deepcopy(self.profile)
        del profile['cfggameplay']['UIData']['HitIndicationData']['hitDirectionMaxDuration']
        with self.assertRaises(ValueError):
            self.generate(profile)

    def test_unowned_and_unknown_delta_keys_are_refused(self):
        for patch in ({'GeneralData': {'disableBaseDamage': True}}, {'version': 130},
                      {'WorldsData': {'bunkerBroadcastEnabled': True}},
                      {'PlayerData': {'disablePersonalLight': True}},
                      {'UIData': {'use3DMap': True}}):
            profile = copy.deepcopy(self.profile)
            for k, v in patch.items():
                if isinstance(v, dict) and isinstance(profile['cfggameplay'].get(k), dict):
                    profile['cfggameplay'][k].update(v)
                else:
                    profile['cfggameplay'][k] = v
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                self.generate(profile)
        profile = copy.deepcopy(self.profile)
        profile['extra'] = 1
        with self.assertRaises(ValueError):
            self.generate(profile)

    def test_source_must_keep_native_version_and_unique_keys(self):
        data = copy.deepcopy(self.original)
        del data['version']
        (self.source / 'cfggameplay.json').write_text(json.dumps(data))
        with self.assertRaises(ValueError):
            self.generate()
        (self.source / 'cfggameplay.json').write_text('{"version": 1, "version": 2}')
        with self.assertRaises(ValueError):
            self.generate()

    def test_generation_is_deterministic(self):
        self.assertEqual(self.generate(), self.generate())


class SpawnKit(unittest.TestCase):
    def setUp(self):
        self.profile, self.preset = committed()

    def classes(self):
        slots = {s['slotName']: [i['itemType'] for i in s['discreteItemSets']]
                 for s in self.preset['attachmentSlotItemSets']}
        cargo = [i['simpleChildrenTypes'] for i in self.preset['discreteUnsortedItemSets']]
        return slots, cargo

    def test_preset_follows_native_loader_schema(self):
        # PlayerSpawnPreset / PlayerSpawnPresetSlotData / ...DiscreteItemSetSlotData /
        # ...DiscreteCargoSetData in CfgPlayerSpawnDataJson.c (scripts-1.30.164289).
        self.assertEqual(set(self.preset), {'spawnWeight', 'name', 'characterTypes',
                                            'attachmentSlotItemSets', 'discreteUnsortedItemSets'})
        self.assertGreaterEqual(self.preset['spawnWeight'], 1)
        self.assertEqual(self.preset['characterTypes'], [])  # keep the player's chosen survivor
        for slot in self.preset['attachmentSlotItemSets']:
            self.assertEqual(set(slot), {'slotName', 'discreteItemSets'})
            self.assertTrue(slot['discreteItemSets'])
            for item in slot['discreteItemSets']:
                self.assertGreaterEqual(item['spawnWeight'], 1)
                self.assertEqual(item['quickBarSlot'], -1)
                self.assertTrue(item['itemType'])
                self.assertEqual(item['simpleChildrenTypes'], [])
                self.assertEqual(item['complexChildrenTypes'], [])
                self.assertEqual(set(item['attributes']),
                                 {'healthMin', 'healthMax', 'quantityMin', 'quantityMax'})
        for item in self.preset['discreteUnsortedItemSets']:
            self.assertGreaterEqual(item['spawnWeight'], 1)
            self.assertIs(item['simpleChildrenUseDefaultAttributes'], True)

    def test_worn_randomised_clothing_without_pristine_items(self):
        slots, _ = self.classes()
        self.assertEqual(set(slots), {'Body', 'Legs', 'Feet'})
        for names in slots.values():
            self.assertGreaterEqual(len(set(names)), 4)  # randomised, not a fixed outfit
            self.assertEqual(len(names), len(set(names)))
        for slot in self.preset['attachmentSlotItemSets']:
            for item in slot['discreteItemSets']:
                a = item['attributes']
                self.assertGreaterEqual(a['healthMin'], 0.5)
                self.assertLess(a['healthMin'], a['healthMax'])
                # Native DAMAGE_WORN_VALUE is 0.7 (constants.c): >= 0.7 reads as pristine.
                self.assertLessEqual(a['healthMax'], 0.69)
                self.assertGreaterEqual(a['healthMin'], 0.6)
                self.assertEqual((a['quantityMin'], a['quantityMax']), (0.0, 0.0))

    def test_every_set_holds_exactly_one_knife_one_bandage_and_one_small_item(self):
        # CfgPlayerSpawnHandler.c: SelectAndSpawnCargoSet picks ONE discrete set (lines 142-164) and
        # SpawnSimpleChildrenItems (234-268) spawns EVERY entry of the picked set, so a knife and a
        # bandage in every set are guaranteed on every spawn.
        _, cargo = self.classes()
        self.assertEqual(len(cargo), 7)
        allowed = re.compile(r'(Rag|Chemlight_(White|Yellow|Green)|(BakedBeans|Spaghetti|Tuna)Can)')
        families = set()
        for children in cargo:
            self.assertEqual(len(children), 3, children)
            self.assertEqual(children[:2], ['KitchenKnife', 'BandageDressing'])  # canonical order
            self.assertEqual(children.count('KitchenKnife'), 1)
            self.assertEqual(children.count('BandageDressing'), 1)
            self.assertRegex(children[2], allowed)
            families.add('rag' if children[2] == 'Rag' else 'chemlight' if 'Chemlight' in children[2] else 'can')
        self.assertEqual(families, {'rag', 'chemlight', 'can'})
        # Each of the three kinds is equally likely (weights sum per family).
        weights = {f: 0 for f in families}
        for item in self.preset['discreteUnsortedItemSets']:
            name = item['simpleChildrenTypes'][2]
            weights['rag' if name == 'Rag' else 'chemlight' if 'Chemlight' in name else 'can'] += item['spawnWeight']
        self.assertEqual(len(set(weights.values())), 1)
        # Default attributes keep full bandage quantity (native ApplyAttributes is skipped, line 257).
        self.assertTrue(all(i['simpleChildrenUseDefaultAttributes'] is True
                            for i in self.preset['discreteUnsortedItemSets']))
        text = json.dumps(self.preset).lower()
        for banned in ('ammo', 'mag_', 'rifle', 'pistol', 'weapon', 'shotgun', 'axe', 'bayonet', 'machete'):
            self.assertNotIn(banned, text)

    def test_validator_requires_the_knife_and_bandage_in_every_set(self):
        sets = len(self.preset['discreteUnsortedItemSets'])
        mutations = {
            'no knife': lambda c: c.remove('KitchenKnife'),
            'no bandage': lambda c: c.remove('BandageDressing'),
            'no small item': lambda c: c.pop(),
            'only the small item': lambda c: c.__delitem__(slice(0, 2)),
            'second knife': lambda c: c.insert(1, 'KitchenKnife'),
            'second bandage': lambda c: c.insert(2, 'BandageDressing'),
            'other knife': lambda c: c.__setitem__(0, 'SteakKnife'),
            'other weapon': lambda c: c.__setitem__(0, 'Hatchet'),
            'bandage swapped for a rag': lambda c: c.__setitem__(1, 'Rag'),
            'extra item': lambda c: c.append('Rag'),
            'wrong order': lambda c: c.reverse(),
        }
        for index in range(sets):
            for label, mutate in mutations.items():
                preset = copy.deepcopy(self.preset)
                mutate(preset['discreteUnsortedItemSets'][index]['simpleChildrenTypes'])
                with self.subTest(set=index, mutation=label), self.assertRaises(ValueError):
                    gameplay.validate_preset(preset)
        gameplay.validate_preset(self.preset)

    def test_kit_fits_every_allowed_clothing_option(self):
        # Native item sizes (cells, width x height) and worn-clothing cargo grids from the in-engine
        # item audit of build 1.30.164289 (experiments/compile-034/-032 native-item-audit). Items are
        # placed by CreateInInventory (CfgPlayerSpawnHandler.c:288) in any worn cargo, so the whole
        # kit needs only fit the combined Body + Legs grids; the worst case is also checked per piece.
        size = {'KitchenKnife': (1, 3), 'BandageDressing': (1, 2), 'Rag': (1, 3),
                'Chemlight_White': (1, 2), 'Chemlight_Yellow': (1, 2), 'Chemlight_Green': (1, 2),
                'BakedBeansCan': (2, 2), 'SpaghettiCan': (2, 2), 'TunaCan': (2, 1)}
        cargo = {'TShirt_Beige': (3, 3), 'TShirt_Blue': (3, 3), 'TShirt_Green': (3, 3),
                 'TShirt_Grey': (3, 3), 'TShirt_Black': (3, 3), 'Hoodie_Black': (5, 3),
                 'Hoodie_Brown': (5, 3), 'Hoodie_Grey': (5, 3), 'Jeans_Black': (4, 3),
                 'Jeans_Blue': (4, 3), 'Jeans_BlueDark': (4, 3), 'Jeans_Brown': (4, 3),
                 'Jeans_Grey': (4, 3), 'CargoPants_Black': (5, 4)}
        slots, kits = self.classes()
        self.assertEqual(set(cargo), set(slots['Body']) | set(slots['Legs']))
        worst = max(sum(w * h for w, h in (size[c] for c in kit)) for kit in kits)
        for name in slots['Body'] + slots['Legs']:
            w, h = cargo[name]
            self.assertLessEqual(worst, w * h, name)  # even a single piece holds the whole kit
            for kit in kits:
                self.assertTrue(all(max(size[c]) <= max(w, h) and min(size[c]) <= min(w, h) for c in kit))

    def test_validator_allowlists_items_and_worn_health(self):
        for slot, name in ((None, 'M4A1'), (None, 'Mag_STANAG_30Rnd'), (None, 'Rag_Extra'), (None, 'Apple')):
            preset = copy.deepcopy(self.preset)
            preset['discreteUnsortedItemSets'][0]['simpleChildrenTypes'][2] = name
            with self.subTest(cargo=name), self.assertRaises(ValueError):
                gameplay.validate_preset(preset)
        for slot, name in ((0, 'Jeans_Black'), (1, 'TShirt_Black'), (2, 'M4A1'), (0, 'PlateCarrierVest')):
            preset = copy.deepcopy(self.preset)
            preset['attachmentSlotItemSets'][slot]['discreteItemSets'][0]['itemType'] = name
            with self.subTest(clothing=name, slot=slot), self.assertRaises(ValueError):
                gameplay.validate_preset(preset)
        for key, bad in (('healthMax', 0.85), ('healthMax', 0.7), ('healthMin', 0.4), ('healthMax', 1.0)):
            preset = copy.deepcopy(self.preset)
            preset['attachmentSlotItemSets'][0]['discreteItemSets'][0]['attributes'][key] = bad
            with self.subTest(key=key, bad=bad), self.assertRaises(ValueError):
                gameplay.validate_preset(preset)
        gameplay.validate_preset(self.preset)

    def test_profile_points_at_the_preset_inside_the_managed_directory(self):
        files = self.profile['cfggameplay']['PlayerData']['spawnGearPresetFiles']
        self.assertEqual(files, [gameplay.GEAR_PATH])
        self.assertTrue(gameplay.GEAR_PATH.startswith(gameplay.MANAGED + '/'))
        self.assertNotEqual(gameplay.MANAGED, economy.MANAGED)  # never share economy's receipt directory

    @unittest.skipUnless(WORKBOOK.is_file(), 'item-review workbook cache absent')
    def test_every_class_exists_in_native_evidence_and_is_spawnable(self):
        classes = {c['name']: c for c in json.loads(WORKBOOK.read_text())['classes']
                   if c['root'] == 'CfgVehicles'}
        slots, cargo = self.classes()
        expected = {'Body': 'Clothing', 'Legs': 'Clothing', 'Feet': 'Clothing'}
        names = [n for names in slots.values() for n in names] + [c[0] for c in cargo]
        for slot, names_in_slot in slots.items():
            for name in names_in_slot:
                self.assertIn(expected[slot], classes[name]['config_ancestors'], name)
        for name in names:
            with self.subTest(name=name):
                self.assertIn(name, classes)
                self.assertEqual(classes[name]['review_status'], 'retain')
                self.assertEqual(classes[name]['definition_evidence'], [])  # not scope-hidden
                forbidden = {'Weapon_Base', 'Magazine_Base', 'Ammunition_Base', 'Edible_Base_Meat'}
                self.assertFalse(forbidden & set(classes[name]['config_ancestors']))


class InstallRollback(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='hc-synthetic-gameplay-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source'
        synthetic_source(self.source)
        self.profile, self.preset = committed()
        self.stage = self.root / 'delta'
        gameplay.write_delta(self.stage, gameplay.generate(self.source, self.profile, self.preset))
        self.target = self.root / 'private-copy'
        shutil.copytree(self.source, self.target)
        (self.target / 'init.c').write_text('// synthetic neighbour that must stay intact\n')
        self.original = (self.target / 'cfggameplay.json').read_bytes()

    def tree(self, base):
        return {p.relative_to(base).as_posix(): p.read_bytes() for p in sorted(base.rglob('*')) if p.is_file()}

    def test_dry_run_checks_everything_and_writes_nothing(self):
        before = self.tree(self.target)
        plan = gameplay.install(self.stage, self.target, dry_run=True)
        self.assertEqual(self.tree(self.target), before)
        self.assertTrue(plan['dry_run'])
        self.assertIn('cfggameplay.json', plan['would_replace'])
        self.assertIn(gameplay.GEAR_PATH, plan['would_create'])
        self.assertIn('enableCfgGameplayFile', plan['operator_requirement'])
        with self.assertRaises(ValueError):
            gameplay.rollback(self.target, dry_run=True)  # nothing installed yet
        self.assertEqual(self.tree(self.target), before)

    def test_install_then_rollback_is_byte_exact(self):
        before = self.tree(self.target)
        receipt = gameplay.install(self.stage, self.target)
        self.assertEqual(receipt['runtime_acceptance'], 'pending')
        installed = json.loads((self.target / 'cfggameplay.json').read_text())
        self.assertEqual(installed['PlayerData']['spawnGearPresetFiles'], [gameplay.GEAR_PATH])
        self.assertEqual(installed['version'], 123)
        self.assertEqual((self.target / gameplay.GEAR_PATH).read_bytes(),
                         (self.stage / 'gear/hardscrabble.json').read_bytes())
        self.assertEqual((self.target / 'init.c').read_bytes(), before['init.c'])
        with self.assertRaises(ValueError):
            gameplay.install(self.stage, self.target)  # no double install
        plan = gameplay.rollback(self.target, dry_run=True)
        self.assertTrue(plan['dry_run'])
        self.assertTrue((self.target / gameplay.MANAGED).is_dir())
        gameplay.rollback(self.target)
        self.assertEqual(self.tree(self.target), before)
        self.assertEqual((self.target / 'cfggameplay.json').read_bytes(), self.original)
        self.assertFalse((self.target / gameplay.MANAGED).exists())

    def test_install_refuses_unexpected_source_hash_and_leaves_target_alone(self):
        (self.target / 'cfggameplay.json').write_text(json.dumps(
            dict(json.loads(self.original), SyntheticOperatorEdit=1)))
        before = self.tree(self.target)
        with self.assertRaises(ValueError):
            gameplay.install(self.stage, self.target)
        self.assertEqual(self.tree(self.target), before)
        self.assertFalse((self.target / gameplay.MANAGED).exists())

    def test_install_refuses_tampered_stage_symlinks_steam_and_missing_target_file(self):
        (self.stage / 'gear/hardscrabble.json').write_text('{}')
        with self.assertRaises(ValueError):
            gameplay.install(self.stage, self.target)
        with self.assertRaises(ValueError):
            gameplay.install(self.stage, Path('/mnt/d/SteamLibrary/steamapps/common/DayZServer/mpmissions/dayzOffline.chernarusplus'))
        fresh = self.root / 'delta2'
        gameplay.write_delta(fresh, gameplay.generate(self.source, self.profile, self.preset))
        link = fresh / 'cfggameplay.merged.json'
        content = link.read_bytes()
        link.unlink()
        link.symlink_to(self.source / 'cfggameplay.json')
        with self.assertRaises(ValueError):
            gameplay.install(fresh, self.target)
        link.unlink()
        link.write_bytes(content)
        (self.target / 'cfggameplay.json').unlink()
        with self.assertRaises((ValueError, OSError)):
            gameplay.install(fresh, self.target)

    def test_delta_that_widens_the_bounds_is_refused_at_install(self):
        # A hand-edited stage must not smuggle in unowned or out-of-bound values,
        # even when its manifest checksums are regenerated.
        files = gameplay.generate(self.source, self.profile, self.preset)
        delta = json.loads(files['cfggameplay.delta.json'])
        delta['PlayerData']['StaminaData'] = {'staminaMax': 10.0}
        merged = json.loads(files['cfggameplay.merged.json'])
        merged['PlayerData']['StaminaData']['staminaMax'] = 10.0
        files['cfggameplay.delta.json'] = gameplay.encode(delta)
        files['cfggameplay.merged.json'] = gameplay.encode(merged)
        manifest = json.loads(files['delta-manifest.json'])
        manifest['files'] = {n: gameplay.sha(d) for n, d in files.items() if n != 'delta-manifest.json'}
        files['delta-manifest.json'] = gameplay.encode(manifest)
        evil = self.root / 'evil'
        gameplay.write_delta(evil, files)
        with self.assertRaises(ValueError):
            gameplay.install(evil, self.target)
        self.assertEqual((self.target / 'cfggameplay.json').read_bytes(), self.original)

    def test_rollback_refuses_drift_and_unexpected_files(self):
        gameplay.install(self.stage, self.target)
        config = self.target / 'cfggameplay.json'
        config.write_bytes(config.read_bytes() + b'\n')
        with self.assertRaises(ValueError):
            gameplay.rollback(self.target)
        self.assertTrue((self.target / gameplay.MANAGED / 'cfggameplay.backup').is_file())
        config.write_bytes(config.read_bytes()[:-1])
        (self.target / gameplay.MANAGED / 'notes.txt').write_text('operator file')
        with self.assertRaises(ValueError):
            gameplay.rollback(self.target)
        (self.target / gameplay.MANAGED / 'notes.txt').unlink()
        preset = self.target / gameplay.GEAR_PATH
        preset.write_text('{}')
        with self.assertRaises(ValueError):
            gameplay.rollback(self.target)
        preset.write_bytes((self.stage / 'gear/hardscrabble.json').read_bytes())
        gameplay.rollback(self.target)
        self.assertEqual(config.read_bytes(), self.original)

    def hardlink_to_outside(self, name):
        outside = self.root / 'outside-mission.txt'
        outside.write_bytes(b'unrelated file that must never be touched\n')
        os.link(outside, self.target / gameplay.MANAGED / name)
        return outside

    def test_rollback_never_writes_through_a_hard_linked_staging_file(self):
        gameplay.install(self.stage, self.target)
        outside = self.hardlink_to_outside('cfggameplay.next')
        before, config = outside.read_bytes(), (self.target / 'cfggameplay.json').read_bytes()
        for dry in (True, False):
            with self.subTest(dry_run=dry), self.assertRaises(ValueError):
                gameplay.rollback(self.target, dry_run=dry)
            self.assertEqual(outside.read_bytes(), before)
            self.assertEqual((self.target / 'cfggameplay.json').read_bytes(), config)
        self.assertTrue((self.target / gameplay.MANAGED / 'cfggameplay.backup').is_file())

    def test_rollback_refuses_other_hard_linked_managed_files_and_config(self):
        for name in ('cfggameplay.backup', 'receipt.json', 'gear/hardscrabble.json'):
            with self.subTest(name=name):
                gameplay.install(self.stage, self.target)
                managed = self.target / gameplay.MANAGED
                data = (managed / name).read_bytes()
                outside = self.root / ('outside-' + name.replace('/', '-'))
                os.link(managed / name, outside)
                with self.assertRaises(ValueError):
                    gameplay.rollback(self.target)
                self.assertEqual(outside.read_bytes(), data)
                outside.unlink()
                gameplay.rollback(self.target)
        gameplay.install(self.stage, self.target)
        outside = self.root / 'outside-config.json'
        os.link(self.target / 'cfggameplay.json', outside)
        merged = outside.read_bytes()
        with self.assertRaises(ValueError):
            gameplay.rollback(self.target)
        self.assertEqual(outside.read_bytes(), merged)
        outside.unlink()
        gameplay.rollback(self.target)

    def test_install_refuses_a_hard_linked_target_config_and_leaves_it_alone(self):
        outside = self.root / 'outside-config.json'
        os.link(self.target / 'cfggameplay.json', outside)
        with self.assertRaises(ValueError):
            gameplay.install(self.stage, self.target)
        self.assertEqual(outside.read_bytes(), self.original)
        self.assertFalse((self.target / gameplay.MANAGED).exists())

    def test_rollback_replaces_a_stale_unlinked_staging_file(self):
        gameplay.install(self.stage, self.target)
        (self.target / gameplay.MANAGED / 'cfggameplay.next').write_bytes(b'stale partial write')
        gameplay.rollback(self.target)
        self.assertEqual((self.target / 'cfggameplay.json').read_bytes(), self.original)

    def test_rollback_of_an_interrupted_install_restores_the_original(self):
        gameplay.install(self.stage, self.target)
        managed = self.target / gameplay.MANAGED
        # Simulate a crash before the atomic switch: managed files exist, config is original.
        (self.target / 'cfggameplay.json').write_bytes(self.original)
        gameplay.rollback(self.target)
        self.assertFalse(managed.exists())
        self.assertEqual((self.target / 'cfggameplay.json').read_bytes(), self.original)

    def test_gameplay_and_economy_installs_do_not_collide(self):
        self.assertNotIn('cfggameplay.json', economy.INPUTS)
        self.assertNotIn('db/globals.xml', economy.INPUTS)
        gameplay.install(self.stage, self.target)
        (self.target / 'hollow-country').mkdir()  # economy's managed directory may exist beside ours
        gameplay.rollback(self.target)
        self.assertTrue((self.target / 'hollow-country').is_dir())

    def test_installer_never_edits_server_configuration(self):
        (self.target / 'serverDZ.cfg').write_text('// synthetic server config\n')
        before = (self.target / 'serverDZ.cfg').read_bytes()
        gameplay.install(self.stage, self.target)
        self.assertEqual((self.target / 'serverDZ.cfg').read_bytes(), before)
        gameplay.rollback(self.target)

    def test_handoff_includes_the_authored_gameplay_files(self):
        with tempfile.TemporaryDirectory() as t:
            addon = Path(t) / 'addon'
            addon.mkdir()
            (addon / 'config.cpp').write_text('class CfgPatches{};')
            blob = pbo.handoff(addon, MISSION)
            import io
            import zipfile
            names = zipfile.ZipFile(io.BytesIO(blob)).namelist()
            self.assertIn('mission/hollow-country/gear/hardscrabble.json', names)
            self.assertIn('mission/hollow-country/gameplay-profiles/hollow-country-v1.json', names)
            self.assertIn('tools/package/gameplay.py', names)
            pbo.verify_handoff(blob)


class NativeEvidence(unittest.TestCase):
    """Cache-guarded checks against the locally installed vanilla files."""

    def mission(self, world):
        path = MISSIONS / f'dayzOffline.{world}/cfggameplay.json'
        if not path.is_file():
            self.skipTest('installed mission cache absent')
        return json.loads(path.read_text())['WorldsData']

    def test_synthetic_curves_equal_the_installed_vanilla_files(self):
        for world, low, high in (('chernarusplus', CHERNARUS_MIN, CHERNARUS_MAX),
                                 ('sakhal', SAKHAL_MIN, SAKHAL_MAX),
                                 ('nasdara', NASDARA_MIN, NASDARA_MAX)):
            data = self.mission(world)
            self.assertEqual(data['environmentMinTemps'], low, world)
            self.assertEqual(data['environmentMaxTemps'], high, world)

    def test_hc_curve_from_real_chernarus_stays_within_bound_and_beats_sakhal(self):
        path = MISSIONS / 'dayzOffline.chernarusplus/cfggameplay.json'
        if not path.is_file():
            self.skipTest('installed mission cache absent')
        with tempfile.TemporaryDirectory() as t:
            source = Path(t) / 'mission'
            source.mkdir()
            shutil.copy(path, source / 'cfggameplay.json')
            profile, preset = committed()
            merged = json.loads(gameplay.generate(source, profile, preset)['cfggameplay.merged.json'])
        vanilla = json.loads(path.read_text())
        self.assertEqual(merged['version'], vanilla['version'])
        sakhal, nasdara = self.mission('sakhal'), self.mission('nasdara')
        low, high = merged['WorldsData']['environmentMinTemps'], merged['WorldsData']['environmentMaxTemps']
        for month in range(12):
            self.assertTrue(-3 <= low[month] - vanilla['WorldsData']['environmentMinTemps'][month] <= 0)
            self.assertTrue(-2 <= high[month] - vanilla['WorldsData']['environmentMaxTemps'][month] <= 0)
            self.assertGreaterEqual(low[month] - sakhal['environmentMinTemps'][month], 1.5)
            self.assertGreaterEqual(high[month] - sakhal['environmentMaxTemps'][month], 3)
            self.assertLess(high[month], nasdara['environmentMaxTemps'][month] - 8)
        for key in ('StaminaData', 'MovementData', 'DrowningData'):
            self.assertEqual(merged['PlayerData'][key], vanilla['PlayerData'][key])

    def test_native_loader_defaults_match_the_vanilla_values_cited_in_the_profile(self):
        scripts = CACHE / 'native-scripts/scripts-1.30.164289'
        data = scripts / '3_Game/CfgGameplayDataJson.c'
        constants = scripts / '3_Game/constants.c'
        if not data.is_file() or not constants.is_file():
            self.skipTest('native script cache absent')
        text, const = data.read_text(), constants.read_text()
        for key in ('staticMode', 'dynamicMode', 'wetnessWeightModifiers', 'spawnGearPresetFiles',
                    'hitDirectionOverrideEnabled', 'hitDirectionBehaviour', 'hitDirectionStyle',
                    'hitDirectionIndicatorColorStr', 'hitDirectionMaxDuration',
                    'hitDirectionBreakPointRelative', 'hitDirectionScatter',
                    'hitIndicationPostProcessEnabled', 'environmentMinTemps', 'environmentMaxTemps'):
            self.assertIn(key, text)
        self.assertRegex(text, r'(?s)DISABLED\s*=\s*0.*ENABLED\s*=\s*1.*ALWAYS\s*=\s*2')
        self.assertRegex(const, r'enum HitDirectionModes\s*\{\s*DISABLED,\s*STATIC,\s*DYNAMIC')
        for name, value in (('DRY', '1.0'), ('DAMP', '1.0'), ('WET', '1.33'), ('SOAKING_WET', '1.66'), ('DRENCHED', '2.0')):
            self.assertRegex(const, rf'WEIGHT_{name}\s*=\s*{re.escape(value)}')
        self.assertEqual(gameplay.NATIVE_WETNESS_WEIGHTS, [1.0, 1.0, 1.33, 1.66, 2.0])


class CeGlobalsStaySubordinate(unittest.TestCase):
    """A14: no change to ZombieMaxCount/AnimalMaxCount; HC budgets stay below them."""

    VANILLA_ZOMBIE_MAX = 1000  # synthetic fixture; the guarded test reads the real globals.xml

    def test_hc_never_reads_or_writes_ce_globals(self):
        self.assertEqual(gameplay.INPUTS, ('cfggameplay.json',))
        code = (ROOT / 'tools/package/gameplay.py').read_text()
        for token in ('globals.xml', 'ZombieMaxCount', 'AnimalMaxCount'):
            self.assertNotIn(token, code)
        for path in MISSION.rglob('*'):
            if path.is_file() and path.suffix in {'.json', '.xml'}:
                text = path.read_text()
                self.assertNotIn('ZombieMaxCount', text, path)
                self.assertNotIn('AnimalMaxCount', text, path)

    def test_hc_horde_budget_is_below_the_native_zombie_cap(self):
        settings = json.loads((MISSION / 'operator/settings.json').read_text())
        source = (ROOT / 'mods/HollowCountry/scripts/3_Game/HCSettings.c').read_text()
        cap = int(re.search(r'MaxActiveHordeMembers > (\d+)', source).group(1))
        self.assertLessEqual(settings['MaxActiveHordeMembers'], cap)
        self.assertLess(cap, self.VANILLA_ZOMBIE_MAX)  # HC can never request more than the CE cap

    def test_vanilla_globals_still_supply_the_fixture_value(self):
        path = MISSIONS / 'dayzOffline.chernarusplus/db/globals.xml'
        if not path.is_file():
            self.skipTest('installed mission cache absent')
        text = path.read_text()
        self.assertIn(f'name="ZombieMaxCount" type="0" value="{self.VANILLA_ZOMBIE_MAX}"', text)
        self.assertIn('name="AnimalMaxCount" type="0" value="200"', text)


class WeightIsNative(unittest.TestCase):
    def test_hc_scripts_never_recompute_wet_weight(self):
        for path in (ROOT / 'mods/HollowCountry').rglob('*.c'):
            text = path.read_text()
            for token in ('GetWetWeightModifier', 'GetConfigWeightModified', 'm_ConfigWeight',
                          'GetWetnessWeightModifiers', 'wetnessWeightModifiers', 'GetWetLevel'):
                self.assertNotIn(token, text, f'{path.name} must read native weight, not recompute it')
        hud = (ROOT / 'mods/HollowCountry/scripts/5_Mission/Survival/HCStaminaHUD.c').read_text()
        self.assertIn('viewer.GetPlayerLoad()', hud)


class InfectedLegZones(unittest.TestCase):
    CONFIG = (ROOT / 'mods/HollowCountry/config.cpp').read_text()

    def squashed(self):
        return re.sub(r'\s+', '', self.CONFIG)

    def hand_written(self):
        # The generated inventory-size block (tools/package/inventory_sizes.py) holds item class
        # names such as Headtorch; the leg-zone rules apply to the hand-written config only.
        begin = self.CONFIG.index('// BEGIN HC inventory sizes')
        end = self.CONFIG.index('// END HC inventory sizes')
        return re.sub(r'\s+', '', self.CONFIG[:begin] + self.CONFIG[end:])

    def test_config_cpp_has_only_the_minimal_leg_zone_override(self):
        text = self.squashed()
        self.assertIn('classCfgVehicles{classDayZInfected;classZombieBase:DayZInfected{classDamageSystem{'
                      'classDamageZones{classLeftLeg{classHealth{hitpoints=' + str(gameplay.LEG_HITPOINTS) + ';};};};};};', text)
        self.assertEqual(1, text.count('classZombieBase:'))
        hand = self.hand_written()
        start = hand.index('classZombieBase:DayZInfected{')
        zombie = hand[start:hand.index('};};};};};', start)]
        for untouched in ('RightLeg', 'LeftFoot', 'RightFoot', 'GlobalHealth', 'Head', 'Torso'):
            self.assertNotIn(untouched, zombie)  # RightLeg inherits LeftLeg; other zones stay vanilla
        self.assertNotIn('Mummy', self.squashed())  # bosses that set their own zones stay vanilla
        generated = self.CONFIG[self.CONFIG.index('// BEGIN HC inventory sizes'):self.CONFIG.index('// END HC inventory sizes')]
        self.assertNotIn('DamageSystem', generated)
        self.assertNotIn('Zombie', generated)
        self.assertIn('"DZ_Characters_Zombies"', text)  # load after the addon that defines the class
        self.assertIn('classCfgPatches', text)
        self.assertIn('classCfgMods', text)
        self.assertLess(text.index('classCfgPatches'), text.index('classCfgVehicles'))

    def test_leg_hitpoints_are_a_bounded_reduction(self):
        self.assertTrue(20 <= gameplay.LEG_HITPOINTS < gameplay.VANILLA_LEG_HITPOINTS == 100)

    @unittest.skipUnless((ADDONS / 'characters_zombies.pbo').is_file(), 'installed addon cache absent')
    def test_vanilla_values_and_inheritance_from_the_installed_addon(self):
        from tests.unit import native_rap
        config = native_rap.load_config((ADDONS / 'characters_zombies.pbo').read_bytes())
        self.assertIn('DZ_Characters_Zombies', config['CfgPatches'])
        vehicles = config['CfgVehicles']
        base = vehicles['ZombieBase']
        self.assertEqual(base['__parent__'], 'DayZInfected')
        zones = base['DamageSystem']['DamageZones']
        self.assertEqual(zones['LeftLeg']['Health']['hitpoints'], gameplay.VANILLA_LEG_HITPOINTS)
        self.assertEqual(zones['RightLeg']['__parent__'], 'LeftLeg')  # inherits the patched value
        self.assertNotIn('Health', zones['RightLeg'])
        # Only the boss-like mummy sets its own leg health, so it stays unchanged.
        explicit = {n for n, c in vehicles.items() if isinstance(c, dict)
                    and 'Health' in c.get('DamageSystem', {}).get('DamageZones', {}).get('LeftLeg', {})}
        self.assertEqual(explicit, {'ZombieBase', 'ZmbM_Mummy'})
        self.assertEqual(vehicles['ZmbM_Mummy']['DamageSystem']['DamageZones']['LeftLeg']['Health']['hitpoints'], 1000)


class DocsNameSingleOwners(unittest.TestCase):
    DOC = (MISSION / 'INSTALL_AND_ROLLBACK.md').read_text()

    def test_doc_requires_the_native_switch_and_names_stamina_owners(self):
        self.assertIn('enableCfgGameplayFile = 1', self.DOC)
        self.assertIn('Gameplay settings', self.DOC)
        section = self.DOC[self.DOC.index('Gameplay settings'):]
        for needle in ('StaminaData', 'HCStaminaConfiguration', 'Hardscrabble', 'ZombieMaxCount',
                       'AnimalMaxCount', 'gameplay.py rollback', 'dry-run', 'pending'):
            self.assertIn(needle, section)


if __name__ == '__main__':
    unittest.main()
