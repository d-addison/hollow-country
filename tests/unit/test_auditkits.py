"""Kits issue spec/plan/tasks: keep role names and firearm scarcity; add >=4
mutually exclusive coherent outfits per role, worn items and scarce personal cargo.
RED first, then JSON-only implementation using Expansion's existing loader.

Provider evidence (read-only .banso-writer/xref/core/4_World/DayZExpansion_Core/):
Classes/Prefab/ExpansionPrefabObject.c:4-26 fields; :180-186 chance;
:230-235 health; :251-293 fractional quantity (0 resets magazines to full);
:336-362 one set per ClassName; :367-405 attachment alternatives;
:504-514 delayed cargo. ClassName on a set is a group label, not an item.
Tests inspect data/static installed vanilla types, never DayZ behaviour.
"""
import json
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
LOADOUTS = ROOT / 'mods/HollowCountryExpansionAI/data/defaults/loadouts'
ROLES = ('Holdout', 'Patrol', 'Raider', 'Scavenger', 'Traveller')
FIELDS = {'ClassName', 'Include', 'Chance', 'Quantity', 'Health',
          'InventoryAttachments', 'InventoryCargo', 'ConstructionPartsBuilt', 'Sets'}
MELEE = {'FirefighterAxe', 'BaseballBat', 'NailedBaseballBat', 'Shovel',
         'WoodAxe', 'Pitchfork', 'Pickaxe', 'Mace', 'Broom'}


def nodes(node, is_set=False):
    yield node, is_set
    for slot in node['InventoryAttachments']:
        for child in slot['Items']:
            yield from nodes(child)
    for child in node['InventoryCargo']:
        yield from nodes(child)
    for child in node['Sets']:
        yield from nodes(child, True)


class AuditKitsTests(unittest.TestCase):
    def kits(self):
        for role in ROLES:
            yield role, json.loads((LOADOUTS / f'HollowCountry_{role}.json').read_text())

    def test_every_role_has_four_coherent_exclusive_archetypes(self):
        for role, kit in self.kits():
            outfits = [s for s in kit['Sets'] if s['ClassName'] == 'ARCHETYPE']
            self.assertGreaterEqual(len(outfits), 4, role)
            signatures = set()
            for outfit in outfits:
                self.assertEqual(outfit['Chance'], 1, role)
                slots = {s['SlotName']: s['Items'] for s in outfit['InventoryAttachments']}
                self.assertTrue({'Body', 'Legs', 'Feet'} <= slots.keys(), role)
                signatures.add(tuple(i['ClassName'] for i in slots['Body']))
                self.assertTrue(outfit['InventoryCargo'], role)
            self.assertEqual(len(signatures), len(outfits), role)
            self.assertFalse(any(s['SlotName'] in {'Body', 'Legs', 'Feet', 'Back'}
                                 for s in kit['InventoryAttachments']), role)

    def test_loader_schema_quantities_and_bounded_cargo(self):
        for role, kit in self.kits():
            self.assertLess(len(json.dumps(kit, indent=4).encode()), 65536, role)
            for node, is_set in nodes(kit):
                self.assertEqual(set(node), FIELDS, (role, node['ClassName']))
                self.assertEqual(node['Include'], '')
                self.assertTrue(0 <= node['Chance'] <= 1)
                self.assertEqual(set(node['Quantity']), {'Min', 'Max'})
                self.assertTrue(0 <= node['Quantity']['Min'] <= node['Quantity']['Max'] <= 1)
                for health in node['Health']:
                    self.assertEqual(set(health), {'Min', 'Max', 'Zone'})
                    self.assertTrue(0 < health['Min'] <= health['Max'] < 1)
                for slot in node['InventoryAttachments']:
                    self.assertEqual(set(slot), {'SlotName', 'Items'})
                    self.assertTrue(slot['Items'])
                self.assertLessEqual(len(node['InventoryCargo']), 9)
                if node['ClassName'].startswith(('Mag_', 'Ammo_')):
                    self.assertTrue(0 < node['Quantity']['Min'] <= node['Quantity']['Max'] < 1,
                                    (role, node['ClassName']))

    def test_class_names_exist_in_vanilla_type_data(self):
        stock = (Path.home() / '.cache/hollow-country/wine-server-20261116/'
                 'mpmissions/dayzOffline.chernarusplus/db/types.xml')
        if not stock.is_file():
            self.skipTest('installed vanilla types absent; static class acceptance pending')
        known = {e.get('name') for e in ET.parse(stock).getroot()}
        known.update(r['class'] for r in json.loads(
            (ROOT / 'tools/package/datamined_items.json').read_text())['rows'])
        for role, kit in self.kits():
            for node, is_set in nodes(kit):
                if node['ClassName'] and not is_set:
                    self.assertIn(node['ClassName'], known, role)

    def test_original_firearm_odds_and_role_weapon_rosters_are_preserved(self):
        for role, kit in self.kits():
            # Read-only pre-variety mission template is the scarcity baseline.
            baseline = json.loads((ROOT / 'mission/hollow-country/ai/loadouts' /
                                   f'HollowCountry_{role}.json').read_text())
            weapons = [s for s in kit['Sets'] if s['ClassName'] == 'WEAPON']
            old = [s for s in baseline['Sets'] if s['ClassName'] == 'WEAPON']
            def roster(sets):
                return [[i['ClassName'] for slot in s['InventoryAttachments']
                         if slot['SlotName'] == 'Hands' for i in slot['Items']] for s in sets]
            self.assertEqual(roster(weapons), roster(old), role)
            self.assertTrue(all(s['Chance'] == 1 for s in weapons), role)
            for s in kit['Sets']:
                if s['ClassName'] != 'WEAPON':
                    self.assertFalse(any(n['ClassName'].startswith(('Mag_', 'Ammo_'))
                                         for n, _ in nodes(s)), role)

    def test_personal_cargo_varies_and_has_operator_opt_out(self):
        for role, kit in self.kits():
            cargo = kit['InventoryCargo']
            self.assertGreaterEqual(len(cargo), 5, role)
            self.assertTrue(all(0 < n['Chance'] < 1 for n in cargo), role)
            # Native loader CanSpawn: Chance=0 opts out of any optional cargo entry.
            self.assertTrue(any('Can' in n['ClassName'] for n in cargo), role)
