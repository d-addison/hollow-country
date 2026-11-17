"""Search prompt geometry, RPC limits and cache over explicit SYNTHETIC adapters.

Executes authored Enforce policy through the existing House translator. Native
output arguments are adapted mechanically; these tests are not DayZ/network proof.
Task contract: class geometry only, no loot/player disclosure; runtime acceptance
(DayZDiag, normal PBO/server, two clients and CAP-09) remains pending.
"""
import math
import re
import unittest
from types import SimpleNamespace as N

from tests.unit import test_search_economy_houses as houses
from tests.unit.test_enforce_locals import duplicate_locals

SCRIPTS = houses.SCRIPTS
SOURCE = SCRIPTS / '4_World/Interiors/HCSearchPreviewSites.c'
LIFECYCLE = SCRIPTS / '5_Mission/Interiors/HCSearchPreviewLifecycle.c'
ACTION = SCRIPTS / '4_World/Interiors/HCInteriorAction.c'


def method(source, name):
    match = re.search(r'\b(?:static )?bool ' + name + r'\([^)]*\)\s*\{', source)
    if not match:
        raise AssertionError('missing authored method ' + name)
    end = houses.match_brace(source, match.end() - 1)
    return source[match.start():end + 1]


class NativeSyntax(houses.Translator):
    def expr(self, text, names):
        code = super().expr(text, names)
        # ParamsReadContext.Read(out value): tuple adapter, no policy supplied.
        return re.sub(r'ctx.Read\((\w+)\)',
                      r'((_read := ctx.read()) and ((_read[0] and ((\1 := _read[1]) is not None))))', code)


class CacheMap(houses.HMap):
    def Get(self, key): return self.get(key)


class Wire:
    def __init__(self, sent): self.values, self.sent = [], sent
    def Write(self, value): self.values.append(value); return True
    def Send(self, *args): self.sent.append((self.values, args))


class Context:
    def __init__(self, *values): self.values = iter(values)
    def read(self):
        try: return True, next(self.values)
        except StopIteration: return False, None


class Harness:
    def __init__(self, case, pack=None, require_sites=True):
        base = houses.Harness(pack=pack)
        self.env = dict(base.env)
        self.house = houses.FakeHouse(houses.SYNTH, [100., 0., 100.])
        self.player = base.player(position=[100., 1., 101.])
        self.sent = []
        self.game = N(now=10., server=False)
        self.game.GetTickTime = lambda: self.game.now
        self.game.IsServer = lambda: self.game.server
        self.game.GetPlayer = lambda: self.player
        self.listeners = []
        self.env.update(
            GetGame=lambda: self.game, HMap=CacheMap,
            ScriptRPC=lambda: Wire(self.sent),
            PlayerBase=N(Cast=lambda p: p),
            DayZGame=N(Event_OnRPC=N(Insert=self.listeners.append, Remove=self.listeners.remove)),
            MiscGameplayFunctions=N(GetPlayerHeadPosition=lambda p: p.GetPosition()),
        )
        if require_sites:
            case.assertTrue(SOURCE.exists(), 'missing class-site RPC/cache implementation')
            for code in NativeSyntax(SOURCE.read_text()).classes():
                exec(code, self.env)
            self.client = self.env['HCSearchPreviewSites']()
            self.env['HCSearchPreviewSites'].s_Instance = self.client
            self.client.Start()
        else:
            self.env['HCSearchPreviewSites'] = N(Get=lambda: N(Matches=lambda *args: False))
        preview = 'class PreviewHarness\n{\n' + method(ACTION.read_text(), 'Preview') + '\n}'
        for code in NativeSyntax(preview).classes(): exec(code, self.env)

    def target(self, local=(0., 1., 0.), parent=False):
        obj = N(GetType=lambda: 'SyntheticChild') if parent else self.house
        target = houses.FakeTarget(obj, self.house.ModelToWorld(local), self.house if parent else None)
        target.GetComponentIndex = lambda: 0
        return target

    def preview(self, target=None):
        return self.env['PreviewHarness'].Preview(self.player, target or self.target())

    def receive(self, *values, sender=None, target=None):
        self.client.OnRPC(sender, target or self.player, 4853902, Context(*values))


class SearchPreviewSitesTests(unittest.TestCase):
    def test_arbitrary_house_without_cached_site_never_previews(self):
        h = Harness(self, require_sites=False)
        self.assertFalse(h.preview(), 'a nearby arbitrary House must not show Search storage')

    def test_one_request_in_flight_and_no_preview_until_reply(self):
        h = Harness(self)
        for _ in range(20): self.assertFalse(h.preview())
        self.assertEqual(len(h.sent), 1)
        self.assertEqual(h.sent[0], ([houses.SYNTH], (None, 4853901, True)))
        h.game.now += 3.1  # A server-throttled/dropped request can recover.
        self.assertFalse(h.preview())
        self.assertEqual(len(h.sent), 2)
        h.receive(houses.SYNTH, 1, [0., 1., 0.], 1.)
        self.assertTrue(h.preview())

    def test_cached_geometry_matches_resolve_boundaries_parent_and_tilt(self):
        h = Harness(self)
        h.preview()
        h.receive(houses.SYNTH, 1, [0., 1., 0.], 1.)
        self.assertTrue(h.preview(h.target(parent=True)))
        for hit, standing, expected in (
            ((1., 1., 0.), (0., 1., 2.5), True),
            ((1.001, 1., 0.), (0., 1., 1.), False),
            ((0., 1., 0.), (0., 1., 2.501), False),
        ):
            h.player.position = h.house.ModelToWorld(standing)
            # Invoke the geometry gate directly: native CCTCursor is an extra restriction.
            self.assertEqual(expected, h.client.Matches(h.player, h.target(hit), h.house))
        h.player.position = h.house.ModelToWorld([0., 1., 1.])
        self.assertTrue(h.preview())
        h.house.tilt = .011
        self.assertFalse(h.preview())
        h.house.GetOrientation = lambda: [0., 0., -.011]
        self.assertFalse(h.preview())

    def test_rotated_house_uses_model_hit_and_world_standing(self):
        h = Harness(self)
        # Synthetic exact 90-degree yaw, unlike the older translation-only fake.
        h.house.GetOrientation = lambda: [90., 0., 0.]
        h.house.ModelToWorld = lambda p: [100. + p[2], p[1], 100. - p[0]]
        h.house.WorldToModel = lambda p: [100. - p[2], p[1], p[0] - 100.]
        h.player.position = h.house.ModelToWorld([2., 1., 0.])
        h.preview(h.target([2., 1., 0.]))
        h.receive(houses.SYNTH, 1, [2., 1., 0.], .5)
        self.assertTrue(h.preview(h.target([2., 1., 0.])))
        self.assertFalse(h.preview(h.target([0., 1., 0.])))

    def test_pilot_props_keep_existing_preview_without_requests(self):
        h = Harness(self)
        catalog = (SCRIPTS / '4_World/Interiors/HCInteriorCatalog.c').read_text()
        pilot_type = re.findall(r'"(\w+)"', method(catalog, 'SearchType'))[0]
        h.house.cls = pilot_type
        self.assertTrue(h.preview())
        self.assertEqual(h.sent, [])
        h.player.position = [500., 0., 500.]
        self.assertFalse(h.preview())

    def test_reply_sites_use_loaded_covered_shape_filter_and_first_24_rows(self):
        h = Harness(self)
        h.game.server = True
        collect = h.env['HCSearchPreviewSites'].Collect
        self.assertEqual([(s.Center, s.Radius) for s in collect(houses.SYNTH)],
                         [(list(s.Center), s.Radius) for s in (houses.SITE_A, houses.SITE_B, houses.SITE_C)])
        self.assertEqual(collect('SyntheticMissing'), [])
        for pack in (houses.Pack(loaded=False), houses.Pack(search='excluded')):
            h.env['HCInteriorTemplates'] = pack.api()
            self.assertEqual(collect(houses.SYNTH), [])
        invalid = N(Center=houses.EArray([0., 1., 0.]), Radius=9., Groups=houses.EArray(['g']))
        missing_groups = N(Center=houses.EArray([0., 1., 0.]), Radius=1., Groups=houses.EArray())
        pack = houses.Pack(sites=[invalid, missing_groups] + [houses.SITE_A] * 22 + [houses.SITE_B])
        h.env['HCInteriorTemplates'] = pack.api()
        sites = collect(houses.SYNTH)
        self.assertEqual(len(sites), 22)  # Resolve caps examined rows, not accepted rows.
        self.assertTrue(all(s.Center == list(houses.SITE_A.Center) for s in sites))
        self.assertIn('HCSearchHouses.SiteShapeValid(site)', SOURCE.read_text())
        h.env['HCInteriorTemplates'] = houses.Pack(sites=[houses.SITE_A] * 25).api()
        self.assertEqual(len(collect(houses.SYNTH)), 24)

    def test_server_bounds_per_sender_requests_and_peer_storage(self):
        h = Harness(self)
        h.game.server = True
        server = h.env['HCSearchPreviewServer']()
        server.Start()
        identity = N(GetPlayer=lambda: h.player)
        h.player.GetIdentity = lambda: identity
        for _ in range(20): server.OnRPC(identity, None, 4853901, Context(houses.SYNTH))
        self.assertEqual(len(h.sent), 4)
        self.assertEqual(h.sent[0][0], [houses.SYNTH, 3, [0., 1., 0.], 1., [20., 1., 0.], 1., [40., 1., 0.], 1.])
        self.assertEqual(h.sent[0][1], (h.player, 4853902, True, identity))
        h.game.now += 1.
        server.OnRPC(identity, None, 4853901, Context(houses.SYNTH))
        self.assertEqual(len(h.sent), 5)
        for _ in range(120):
            peer_player = N()
            peer_id = N(GetPlayer=lambda p=peer_player: p)
            peer_player.GetIdentity = lambda i=peer_id: i
            server.OnRPC(peer_id, None, 4853901, Context(houses.SYNTH))
        self.assertLessEqual(server.m_Peers.Count(), 90)
        server.Stop()
        self.assertEqual(server.m_Peers.Count(), 0)

    def test_cache_bounds_include_pending_and_empty_replies(self):
        h = Harness(self)
        for index in range(300):
            h.client.EntryFor('SyntheticClass' + str(index))
            h.game.now += .5
        self.assertEqual(h.client.m_Cache.Count(), 256)
        self.assertEqual(len(h.sent), 256)
        h.receive('SyntheticClass0', 0)
        for _ in range(20): h.client.EntryFor('SyntheticClass0')
        self.assertEqual(len(h.sent), 256)
        h.client.Stop()
        self.assertEqual(h.client.m_Cache.Count(), 0)
        self.assertEqual(h.listeners, [])

    def test_invalid_unsolicited_and_wrong_sender_replies_do_not_enable_prompt(self):
        for values in ((houses.SYNTH, 25), (houses.SYNTH, -1),
                       (houses.SYNTH, 1, [0., 1., 0.], 9.),
                       (houses.SYNTH, 1, [math.nan, 1., 0.], 1.),
                       (houses.SYNTH, 1, [0., 1., 0.]),
                       ('SyntheticUnrequested', 0)):
            with self.subTest(reply=values):
                h = Harness(self)
                h.preview()
                h.receive(*values)
                self.assertFalse(h.preview())
                self.assertEqual(h.client.m_Cache.Count(), 1)
        h = Harness(self)
        h.preview()
        h.receive(houses.SYNTH, 1, [0., 1., 0.], 1., sender=object())
        self.assertFalse(h.preview())
        h.receive(houses.SYNTH, 0)
        self.assertFalse(h.preview())

    def test_rpc_registration_lifecycle_ids_and_enforce_locals(self):
        self.assertTrue(SOURCE.exists(), 'missing RPC/cache source')
        self.assertTrue(LIFECYCLE.exists(), 'missing mission-owned RPC lifetime')
        source = SOURCE.read_text()
        lifecycle = LIFECYCLE.read_text()
        self.assertEqual(source.count('DayZGame.Event_OnRPC.Insert(OnRPC)'), 2)
        self.assertEqual(source.count('DayZGame.Event_OnRPC.Remove(OnRPC)'), 2)
        for owner in ('MissionServer', 'MissionGameplay'):
            block = lifecycle.split('modded class ' + owner, 1)[1].split('modded class', 1)[0]
            for token in ('OnInit', '.Start()', 'OnMissionFinish', '.Stop()', 'super.OnInit()', 'super.OnMissionFinish()'):
                self.assertIn(token, block)
        ids = []
        for path in SCRIPTS.parents[1].rglob('*.c'):
            text = re.sub(r'//[^\n]*', '', path.read_text())
            ids.extend(int(v) for v in re.findall(r'\bRPC_\w+\s*=\s*(\d+)', text))
        self.assertIn(4853901, ids)
        self.assertIn(4853902, ids)
        self.assertEqual(len(ids), len(set(ids)))
        for path in (SOURCE, LIFECYCLE, ACTION):
            self.assertEqual(duplicate_locals(path.read_text()), [], path.name)


if __name__ == '__main__':
    unittest.main()
