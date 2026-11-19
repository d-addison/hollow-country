"""Synthetic authored-policy checks; no DayZ, RPC, or persistence acceptance."""
import copy
import json
from pathlib import Path
import re
from types import SimpleNamespace as NS
import unittest

from tests.unit.test_group_server import EArray
from tests.unit.test_map_layers import EStr, translate

ROOT = Path(__file__).resolve().parents[2]
PINS = ROOT / 'mods/HollowCountry/scripts/4_World/Groups/HCGroupPins.c'
DEATH = PINS.with_name('HCDeathPin.c')
INFO = ROOT / 'mods/HollowCountry/scripts/5_Mission/Groups/HCInfoLayers.c'


def string_calls(source):
    """Syntax only: native integer formatting has no policy in this fixture."""
    source = source.replace('m_State.Groups.Count().ToString()', 'str(m_State.Groups.Count())')
    source = re.sub(r'([\w.]+)\.ToString\(\)', r'str(\1)', source)
    source = re.sub(r'new array<[^>]+>(?!\()', 'EArray()', source)
    return re.sub(r'\barray<[^>]+> (\w+) =', r'EArray \1 =', source)


class DeathStoreFixture:
    """Explicit in-memory native filesystem; injected copy interruption, no disk IO."""
    path = '$profile:HollowCountry/Groups/death-pins.json'

    def __init__(self, files=None, copy_ok=True):
        self.files = dict(files or {})
        self.copies = []
        self.saves = []
        self.logs = []
        self.owner = NS(m_State=None)
        env = dict(FileExist=lambda path: path in self.files,
                   DeleteFile=self.delete, CopyFile=self.copy, Print=self.logs.append,
                   GetGame=lambda: NS(GetWorldName=lambda: 'chernarusplus'),
                   load=self.load, read=lambda path, limit: self.files.get(path),
                   save=self.save, direct_save=lambda *args: True,
                   str=str, HCGroupPlace=lambda: NS(),
                   HCDeathPinRow=lambda: NS(),
                   HCGroupClock=NS(Utc=lambda: 100),
                   HCGroupRules=NS(TextValid=lambda text, cap, empty: 0 < len(text) <= cap,
                                   PlaceValid=lambda pin: pin is not None,
                                   DeadlineFits=lambda now, delta: True))
        source = string_calls(DEATH.read_text()).replace('protected ', '')
        source = re.sub(r'HCGroupJson<HCDeathPinState>\.Load\(([^,]+), 131072, (\w+)\)',
                        r'((\2 := load(\1)) != null)', source)
        source = re.sub(r'HCGroupIO.Read\(([^,]+), 131072, (\w+)\)',
                        r'((\2 := read(\1, 131072)) != null)', source)
        source = source.replace('HCV2ThreatStore<HCDeathPinState>.Save(', 'save(')
        source = source.replace('JsonFileLoader<HCDeathPinState>.SaveFile(', 'direct_save(')
        source = source.replace('PATH', 'path')
        env['path'] = self.path
        names = ('HCValidState', 'HCPrune', 'HCPublish', 'HCReadState', 'HCRecoverPending')
        translate(source, 'HCDeathPins', env, only=names)
        for name in names:
            if name in env:
                setattr(self.owner, name, lambda *args, _name=name: env[_name](self.owner, *args))
        self.copy_ok = copy_ok

    @staticmethod
    def image(prefix='hc-death:', next_id=2):
        return json.dumps(dict(Version=1, WorldName='chernarusplus', NextId=next_id,
                              Rows=[dict(GroupId=1, Epoch=0, PlayerId='synthetic-player',
                                         Pin=dict(Id=prefix + '1', Name='Where Synthetic fell',
                                                  HCPinExpiresUtc=7300))]))

    def load(self, path):
        from tests.unit.json_loader_port import decode_json
        return decode_json(self.files.get(path, ''), 'HCDeathPinState', EArray, EStr)

    def delete(self, path):
        return self.files.pop(path, None) is not None

    def copy(self, source, target):
        self.copies.append((source, target))
        self.files[target] = self.files[source] if self.copy_ok else '{interrupted'
        return self.copy_ok

    def save(self, path, state, limit):
        # Deliberate boundary stub; shared-helper reuse is asserted below.
        self.saves.append((path, copy.deepcopy(state), limit))
        return True


class V2PinsSmoke(unittest.TestCase):
    def test_death_label_is_plain_and_expires_without_a_new_snapshot(self):
        env = {}
        translate(INFO.read_text(), 'HCInfoMapPins', env, only=('Label',))
        pin = NS(Id=EStr('hc-death:1'), Name='Where Synthetic fell', HCPinExpiresUtc=200)
        self.assertEqual('Where Synthetic fell', env['Label'](pin, 100))
        for utc in (0, 200, 201):
            self.assertEqual('', env['Label'](pin, utc))
        pin.Id = EStr('hc-lead:1')
        self.assertEqual('lead: Where Synthetic fell', env['Label'](pin, 100))

    def test_death_counts_are_separate_on_client_and_server(self):
        places = EArray([NS(Id=EStr(prefix + '1'), Name='Synthetic', HCPinExpiresUtc=200)
                         for prefix in ('hc-death:', 'hc-lead:', 'hc-found:')])
        for side in ('client', 'server'):
            with self.subTest(side=side):
                logs = []
                env = dict(Print=logs.append, str=str,
                           GetGame=lambda: NS(GetTickTime=lambda: 100),
                           HCGroupPlace=lambda: NS())
                if side == 'client':
                    env['clock'] = NS(last=-60)
                    source = INFO.read_text().replace('s_HCLastLog', 'clock.last')
                    translate(string_calls(source), 'HCInfoMapPins', env,
                              only=('Label', 'Log'))
                    env['Log'](NS(Places=places), 100)
                else:
                    group = NS()
                    owner = NS(m_Healthy=True, m_State=NS(Groups=EArray([group])),
                               m_Config=NS(MaxDiscoveries=48))
                    source = re.sub(r'\b(m_Healthy|m_State|m_Config)\b', r'self.\1', string_calls(PINS.read_text()))
                    translate(source, 'HCGroupService', env,
                              only=('HCPinsLog',))
                    collector = NS(Collect=lambda group, cap, output: output.extend(places))
                    env['HCPinsLog'](owner, collector)
                self.assertIn('trail=1 leads=1 deaths=1', logs[-1])

    def test_publish_uses_own_kind_and_shared_staged_save(self):
        fixture = DeathStoreFixture()
        fixture.owner.m_State = NS(NextId=1, Rows=EArray())
        group = NS(Id=1, Epoch=1, Members=EArray(['synthetic-player']))
        self.assertTrue(fixture.owner.HCPublish(group, 'synthetic-player', 'Synthetic', [1, 0, 2]))
        self.assertEqual('hc-death:1', fixture.owner.m_State.Rows[0].Pin.Id)
        self.assertEqual(7300, fixture.owner.m_State.Rows[0].Pin.HCPinExpiresUtc)
        self.assertEqual(1, len(fixture.saves))
        self.assertEqual((fixture.path, 131072), (fixture.saves[0][0], fixture.saves[0][2]))
        self.assertNotIn('SaveFile(', DEATH.read_text())

    def test_interrupted_promotion_recovers_valid_pending_image_and_retries(self):
        fixture = DeathStoreFixture({DeathStoreFixture.path: '{partial',
                                    DeathStoreFixture.path + '.tmp': DeathStoreFixture.image()},
                                   copy_ok=False)
        self.assertTrue(hasattr(fixture.owner, 'HCRecoverPending'), 'pending recovery is missing')
        self.assertFalse(fixture.owner.HCRecoverPending())
        self.assertIn(fixture.path + '.tmp', fixture.files)
        fixture.copy_ok = True
        self.assertTrue(fixture.owner.HCRecoverPending())
        self.assertNotIn(fixture.path + '.tmp', fixture.files)
        self.assertIsNotNone(fixture.owner.HCReadState(fixture.path))

    def test_partial_staging_preserves_valid_primary_and_invalid_files_fail_closed(self):
        fixture = DeathStoreFixture({DeathStoreFixture.path: DeathStoreFixture.image(),
                                    DeathStoreFixture.path + '.tmp': '{partial'})
        self.assertTrue(hasattr(fixture.owner, 'HCRecoverPending'), 'pending recovery is missing')
        before = fixture.files[fixture.path]
        self.assertTrue(fixture.owner.HCRecoverPending())
        self.assertEqual(before, fixture.files[fixture.path])
        self.assertEqual([], fixture.copies)
        fixture.files[fixture.path] = '{invalid'
        fixture.files[fixture.path + '.tmp'] = '{partial'
        before = dict(fixture.files)
        self.assertFalse(fixture.owner.HCRecoverPending())
        self.assertEqual(before, fixture.files)

    def test_legacy_death_ids_migrate_only_in_the_validated_death_store(self):
        fixture = DeathStoreFixture({DeathStoreFixture.path: DeathStoreFixture.image('hc-lead:death:')})
        self.assertTrue(hasattr(fixture.owner, 'HCReadState'), 'validated store reader is missing')
        loaded = fixture.owner.HCReadState(fixture.path)
        self.assertIsNotNone(loaded)
        self.assertEqual('hc-death:1', loaded.Rows[0].Pin.Id)
        fixture.files[fixture.path] = DeathStoreFixture.image('hc-lead:third-party:')
        self.assertIsNone(fixture.owner.HCReadState(fixture.path))

    def test_unplaced_shelter_yields_no_trail_pin(self):
        env = {'HCGroupRules': NS(PlaceValid=lambda pin: True),
               'HCGroupPlace': lambda: NS()}
        translate(PINS.read_text(), 'HCGroupPinPolicy', env, only=('TrailPin',))
        shelter = NS(Name=EStr('Synthetic refuge'), Position=[100, 0, 200],
                     History=EStr('A walker rested here.'), Placed=False)
        self.assertIsNone(env['TrailPin'](shelter))
        shelter.Placed = True
        self.assertIsNotNone(env['TrailPin'](shelter))

    def test_named_place_lead_and_group_trail_cap(self):
        self.assertTrue(PINS.exists(), 'Map pin implementation is missing')
        source = PINS.read_text()
        named = NS(Name=EStr('Synthetic town'), Position=[100, 0, 200])
        env = {'HCLeadPolicy': NS(Place=lambda key: named if key == 'town' else None),
               'HCGroupRules': NS(PlaceValid=lambda pin: True),
               'HCGroupPlace': lambda: NS(), 'EArray': EArray}
        translate(source, 'HCGroupPinPolicy', env, only=('LeadPin', 'AddTrail'))
        lead = NS(Id=EStr('received'), TargetPlaceId='town', Expires=200,
                  Position=[9999, 0, 9999])  # Poison actor position is ignored.
        pin = env['LeadPin'](lead, 100)
        self.assertEqual(named.Position, pin.Position)
        self.assertEqual('Synthetic town', pin.Name)
        self.assertEqual(200, pin.HCPinExpiresUtc)
        self.assertIsNone(env['LeadPin'](lead, 200))
        lead.TargetPlaceId = 'unknown'
        self.assertIsNone(env['LeadPin'](lead, 100))
        group = NS(HCTrailPlaceIds=EArray())
        other_group = NS(HCTrailPlaceIds=EArray())
        for index in range(60):
            env['AddTrail'](group, EStr('synthetic-shelter-%d' % index))
        self.assertEqual(48, len(group.HCTrailPlaceIds))
        self.assertFalse(env['AddTrail'](group, group.HCTrailPlaceIds[0]))
        self.assertEqual([], other_group.HCTrailPlaceIds)


if __name__ == '__main__':
    unittest.main()
