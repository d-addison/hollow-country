"""HC-32: synthetic dependency/mission fixtures exercise the real CE composer.

These XML bytes are authored test doubles, never engine/runtime evidence.
Actual TDD command (RED then GREEN, 2026-11-18):
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest test_hc_travel_roster -v
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
                               'cfglimitsdefinition.xml': '<lists/>',
                               'cfgeventspawns.xml': '<eventposdef/>'}.items():
                put(mission, name, data)
            before = snapshot(mission)
            # RaG supplies tools, not a second CE source for native vehicles.
            rag, core = workshop / '3105330157', workshop / '3556131153'
            core.mkdir(parents=True)
            put(rag, 'types/rag_immersive_vehicles.xml', '<types><type name="Offroad_02">'
                '<nominal>2</nominal></type></types>')
            with self.assertRaisesRegex(ValueError, 'HC-32.*vehicle.*budget'):
                overlays.plan(workshop, mission, [rag, core])
            put(rag, 'types/rag_immersive_vehicles.xml', '<types><type name="rag_car_jack">'
                '<nominal>7</nominal><min>4</min></type></types>')
            candidate = overlays.plan(workshop, mission, [rag, core])
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
            self.assertEqual(caps['snake'], 0)  # Snake content is withdrawn
            self.assertLessEqual(max(caps.values()), 8)
            bad = dict(policy, snake_cap=49)
            with self.assertRaisesRegex(ValueError, 'ambient.*cap'):
                overlays.ambient_caps(bad)
            # Expansion additions extend native families; native trucks retain
            # stock repair templates within the combined HC event override.
            report = travel.roster()
            manifest = json.loads((travel.SOURCE / travel.EXPANSION_ROSTER).read_bytes())
            families = {name: set(variants) for name, variants in travel.NATIVE_FAMILIES.items()}
            for name, variants in manifest['families'].items():
                families.setdefault(name, set()).update(variants)
            self.assertEqual(report['vehicle_families'], len(families))
            native_trucks = set(travel.NATIVE_FAMILIES['VehicleTruck01'])
            self.assertEqual(report['authored_variants'],
                             sum(len(v) for v in families.values()) - len(native_trucks))
            for name, variants in families.items():
                self.assertEqual(set(report['families'][name]['variants']), variants)
            templates = ET.fromstring(travel.validate()['ce/travel-spawnabletypes.xml'])
            self.assertFalse(native_trucks & {t.get('name') for t in templates})
            source = root / 'source'
            for name, data in travel.validate().items():
                put(source, name, data)
            put(source, travel.EXPANSION_ROSTER,
                (travel.SOURCE / travel.EXPANSION_ROSTER).read_bytes())
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


class TravelRosterReviewFollowUp(unittest.TestCase):
    def test_unreviewed_event_is_a_named_hc32_refusal(self):
        import xml.etree.ElementTree as ET
        from tools.package import travel
        events = ET.fromstring(travel.validate()['ce/events.xml'])
        # A stray (childless) HC event passes the ownership set but has no reviewed family.
        ET.SubElement(ET.SubElement(events, 'event', name='HCStrayEvent'), 'children')
        with self.assertRaisesRegex(ValueError, 'HC-32 .*unreviewed.*event'):
            travel._roster(events, ET.fromstring('<spawnabletypes/>'))

    def test_bicycle_overlay_is_retired(self):
        source = (Path(__file__).resolve().parents[2] / 'tools/package/optional_overlays.py').read_text()
        self.assertNotIn('BICYCLE_ID', source)
        self.assertNotIn('vehicle_owners(', source)
