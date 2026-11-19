"""HC-32: synthetic dependency/mission fixtures exercise the real CE composer.

These XML bytes are authored test doubles, never engine/runtime evidence.
Actual TDD command (RED then GREEN, 2026-11-18):
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest test_hc_travel_roster -v
RED: AssertionError: ValueError not raised (mismatched bicycle wheel accepted).
GREEN: Ran 1 test; OK. Runtime acceptance remains PENDING.
"""
import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

from tools.package import optional_overlays as overlays, travel


def put(root, name, content):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content if isinstance(content, bytes) else content.encode())


def snapshot(root):
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for p in root.rglob('*') if p.is_file()}


class TravelRoster(unittest.TestCase):
    def test_vehicle_ownership_repair_pairs_caps_and_reversible_composition(self):
        with tempfile.TemporaryDirectory(prefix='hc32-synthetic-') as directory:
            root = Path(directory)
            mission, workshop = root / 'mission', root / 'workshop'
            for name, data in {'cfgeconomycore.xml': '<economycore/>',
                               'db/events.xml': '<events><event name="VehicleOffroad02"><children>'
                                   '<child type="Offroad_02"/></children></event></events>',
                               'db/types.xml': '<types/>',
                               'cfgspawnabletypes.xml': '<spawnabletypes/>',
                               'cfgeventspawns.xml': '<eventposdef/>'}.items():
                put(mission, name, data)
            bike = workshop / overlays.BICYCLE_ID
            put(bike, 'events.xml', '<events><event name="SyntheticBicycle"><nominal>20</nominal>'
                '<min>0</min><max>100</max><children><child type="Old_Bike" min="0" max="20"/>'
                '</children></event></events>')
            put(bike, 'cfgeventspawns_Chernarus.xml', '<events><event name="SyntheticBicycle">'
                '<pos x="11" z="11" a="0"/></event></events>')
            put(bike, 'types.xml', '<types><type name="Old_Bike"><nominal>0</nominal><min>0</min>'
                '</type><type name="bicycle_wheel"><nominal>8</nominal></type></types>')
            correct = ('<spawnabletypes><damage min="0.47" max="0.95"/>'
                       '<type name="Old_Bike"><attachments chance="1"><item name="bicycle_wheel" '
                       'chance="0.99"/></attachments><attachments chance="1">'
                       '<item name="bicycle_wheel" chance="0.99"/></attachments></type></spawnabletypes>')
            put(bike, 'spawnabletypes.xml', correct.replace('bicycle_wheel', 'ladybicycle_wheel'))
            before = snapshot(mission)
            with self.assertRaisesRegex(ValueError, 'HC-32.*incompatible.*wheel'):
                overlays.plan(workshop, mission, [bike])
            self.assertEqual(snapshot(mission), before)
            put(bike, 'spawnabletypes.xml', correct.replace('name="Old_Bike"', 'name="old_bike"').replace(
                'bicycle_wheel', 'ladybicycle_wheel'))
            with self.assertRaisesRegex(ValueError, 'HC-32.*incompatible.*wheel'):
                overlays.plan(workshop, mission, [bike])
            put(bike, 'spawnabletypes.xml', correct)
            candidate = overlays.plan(workshop, mission, [bike])
            generated = ET.fromstring(candidate['files'][overlays.MANAGED + '/events.xml'])
            self.assertEqual(generated[0].findtext('nominal'), '40')
            self.assertEqual([c.get('type') for c in generated.findall('.//child')], ['Old_Bike'])
            # A second event with a different name still doubles the same vehicle.
            stock = (mission / 'db/events.xml').read_bytes()
            put(mission, 'db/events.xml', '<events><event name="OtherOwner"><children>'
                '<child type="old_bike"/></children></event></events>')
            with self.assertRaisesRegex(ValueError, 'HC-32.*vehicle.*owner'):
                overlays.plan(workshop, mission, [bike])
            put(mission, 'db/events.xml', stock)
            # Positive loose-loot budgets must never create another vehicle source.
            types = (bike / 'types.xml').read_text()
            put(bike, 'types.xml', types.replace('<nominal>0</nominal>', '<nominal>2</nominal>'))
            with self.assertRaisesRegex(ValueError, 'HC-32.*vehicle.*budget'):
                overlays.plan(workshop, mission, [bike])
            put(bike, 'types.xml', types)
            # RaG supplies tools, not a second CE source for native vehicles.
            rag, core = workshop / '3105330157', workshop / '3556131153'
            core.mkdir()
            put(rag, 'types/rag_immersive_vehicles.xml', '<types><type name="Offroad_02">'
                '<nominal>2</nominal></type></types>')
            with self.assertRaisesRegex(ValueError, 'HC-32.*vehicle.*budget'):
                overlays.plan(workshop, mission, [bike, rag, core])
            put(rag, 'types/rag_immersive_vehicles.xml', '<types><type name="rag_car_jack">'
                '<nominal>7</nominal><min>4</min></type></types>')
            candidate = overlays.plan(workshop, mission, [bike, rag, core])
            installed = snapshot(workshop)
            overlays.install(candidate, mission)
            overlays.rollback(mission)
            self.assertEqual(snapshot(mission), before)
            self.assertEqual(snapshot(workshop), installed)
            # Installed schema has six independent ambient caps plus a snake event;
            # the six-species product alone is not the aggregate.
            policy = json.loads(overlays.POLICY.read_text())['ambient']
            caps = overlays.ambient_caps(policy)
            self.assertEqual(sum(caps.values()), 48)
            self.assertEqual(caps['snake'], 2)
            self.assertLessEqual(max(caps.values()), 8)
            bad = dict(policy, snake_cap=49)
            with self.assertRaisesRegex(ValueError, 'ambient.*cap'):
                overlays.ambient_caps(bad)
            # Authored native roster remains 25 variants / seven overrides; trucks
            # are an explicit eighth family retaining native stock repair/spawn.
            report = travel.roster()
            self.assertEqual(report['vehicle_families'], 8)
            self.assertEqual(report['authored_variants'], 25)
            self.assertEqual(report['families']['VehicleTruck01']['disposition'], 'native-stock')
            self.assertEqual(len(report['families']['VehicleTruck01']['variants']), 3)
            source = root / 'source'
            for name, data in travel.validate().items():
                put(source, name, data)
            path = source / 'ce/travel-spawnabletypes.xml'
            data = path.read_bytes()
            path.write_bytes(data.replace(b'name="CivSedanWheel"', b'name="HatchbackWheel"', 1))
            with self.assertRaisesRegex(ValueError, 'HC-32.*incompatible.*wheel'):
                travel.roster(source)
            with self.assertRaisesRegex(ValueError, 'HC-32.*incompatible.*wheel'):
                travel.install(source, mission)
            self.assertEqual(snapshot(mission), before)
            path.write_bytes(data)
            path.write_bytes(data.replace(b'</spawnabletypes>',
                b'<type name="Truck_01_Covered"/></spawnabletypes>'))
            with self.assertRaisesRegex(ValueError, 'HC-32.*truck.*native-stock'):
                travel.install(source, mission)
            path.write_bytes(data)
            # Reversing installer order cannot hide duplicate child ownership.
            put(mission, 'cfgeconomycore.xml', '<economycore><ce folder="other">'
                '<file name="events.xml" type="events"/></ce></economycore>')
            put(mission, 'other/events.xml', '<events><event name="DifferentEvent"><children>'
                '<child type="CivilianSedan"/></children></event></events>')
            collision = snapshot(mission)
            with self.assertRaisesRegex(ValueError, 'HC-32.*vehicle.*owner'):
                travel.install(source, mission)
            self.assertEqual(snapshot(mission), collision)
