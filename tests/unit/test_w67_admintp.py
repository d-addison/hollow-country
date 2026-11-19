"""Authored teleport policy with explicit synthetic engine fixtures; no DayZ proof."""
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
from tests.unit.test_admin_test_kit import compile_authored, base_scope, Cell
from tests.unit.test_group_server import EArray

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'mods/HollowCountry/scripts/4_World/Admin/HCAdminTeleport.c'


class TeleportBehavior(unittest.TestCase):
    def build(self, authorized=True, vehicle=False, unconscious=False, restrained=False,
              enabled=True, controls=True, map_on=True, disabled=False, credit=True):
        self.moves = []
        self.probes = []
        self.player = NS(GetCommand_Vehicle=lambda: vehicle, IsUnconscious=lambda: unconscious,
                         IsRestrained=lambda: restrained, SetPosition=self.moves.append)
        self.admin = NS(HCAuthorized=lambda sender: authorized, HCOperatorControls=lambda: controls)
        self.sender = object()
        self.service = NS(m_Enabled=enabled, m_Complete=True, m_Config=NS(SearchAttempts=4),
                          m_Destinations=EArray([NS(Position=[10, 0, 20]), NS(Position=[30, 0, 40])]))
        self.service.HCGround = lambda anchor, player: self.probes.append(anchor) or [anchor[0], 17.2, anchor[2]]
        self.service.HCFindGround = lambda anchor, player: self.service.HCGround(anchor, player)
        game = NS(IsServer=lambda: True)
        server = NS(GetSettings=lambda: NS(EnableAdminMap=map_on),
                    HCTickWork=lambda: NS(HCTake=lambda cost: credit))
        scope = base_scope(GetGame=lambda: game, HCServer=NS(Get=lambda: server),
                           FileExist=lambda path: disabled, vector=NS(Zero=[0, 0, 0]))
        self.run_move = compile_authored(SOURCE, 'HCAdminTeleport', 'HCMove', scope,
                                        ('HCFindGround',), modded=False)

    def move(self, value=0):
        dest, reason = Cell(), Cell()
        result = self.run_move(self.service, self.admin, self.sender, self.player, value, dest, reason)
        return result, dest.value, reason.value

    def test_authorization_refusal_does_not_probe_or_move(self):
        self.build(authorized=False)
        self.assertEqual((False, -1, 'non-admin'), self.move())
        self.assertEqual([], self.moves + self.probes)

    def test_vehicle_unconscious_and_restraint_refuse(self):
        for flag, reason in (('vehicle', 'in-vehicle'), ('unconscious', 'unconscious'), ('restrained', 'restrained')):
            self.build(**{flag: True})
            self.assertEqual((False, -1, reason), self.move())
            self.assertEqual([], self.moves + self.probes)

    def test_destination_clamps_on_the_server_snapshot(self):
        for value, expected in ((-999, 0), (999, 1)):
            self.build()
            self.assertEqual((True, expected, 'admin-only; runtime=PENDING'), self.move(value))
            self.assertEqual([self.service.m_Destinations[expected].Position], self.probes)
            self.assertEqual(1, len(self.moves))

    def test_all_disable_paths_refuse_before_any_probe(self):
        for kwargs in ({'enabled': False}, {'controls': False}, {'map_on': False}, {'disabled': True}):
            self.build(**kwargs)
            self.assertEqual((False, -1, "teleport-disabled"), self.move())
            self.assertEqual([], self.moves + self.probes)

    def test_pending_empty_or_no_ground_never_moves(self):
        self.build()
        self.service.m_Complete = False
        self.assertFalse(self.move()[0])
        self.service.m_Complete = True
        self.service.m_Destinations.clear()
        self.assertFalse(self.move()[0])
        self.build()
        self.service.HCFindGround = lambda anchor, player: [0, 0, 0]
        self.assertFalse(self.move()[0])
        self.assertEqual([], self.moves)


class GroundBehavior(unittest.TestCase):
    def ground(self, candidate=None, collision=False, water=False, surface=lambda x, z: 17):
        game = NS(GetWorld=lambda: NS(GetWorldSize=lambda: 1000), SurfaceY=surface,
                  SurfaceIsSea=lambda x, z: water, SurfaceIsPond=lambda x, z: False,
                  IsBoxColliding=lambda *args: collision)
        config = NS(BoundaryMarginM=2, GroundOffsetM=.2, ClearanceWidthM=1,
                    ClearanceHeightM=2, MaxSlopeDeltaM=.4)
        scope = base_scope(GetGame=lambda: game, vector=NS(Zero=[0, 0, 0]),
                           Vector=lambda x, y, z: [x, y, z], array=EArray)
        fn = compile_authored(SOURCE, 'HCAdminTeleport', 'HCGround', scope, modded=False)
        return fn(NS(m_Config=config), candidate or [10, 999, 20], object())

    def test_safe_y_uses_surface_not_authored_altitude(self):
        self.assertEqual([10, 17.2, 20], self.ground())

    def test_water_building_bounds_and_steep_ground_refuse(self):
        for kwargs in ({'collision': True}, {'water': True}, {'candidate': [1001, 0, 20]},
                       {'surface': lambda x, z: x * 10}):
            self.assertEqual([0, 0, 0], self.ground(**kwargs))




class ConfigAndBudgetBehavior(unittest.TestCase):
    def config(self):
        import re
        text = SOURCE.read_text().split('class HCAdminTeleportConfig', 1)[1].split('class HCAdminTeleportSite', 1)[0]
        fields = re.findall(r'^    (int|float|bool) (\w+) = ([\w.]+);', text, re.M)
        values = {name: (value == 'true' if kind == 'bool' else int(value) if kind == 'int' else float(value)) for kind, name, value in fields}
        return NS(**values), tuple(values)

    def test_config_defaults_on_and_missing_json_fields_keep_defaults(self):
        config, fields = self.config()
        apply = compile_authored(SOURCE, 'HCAdminTeleportConfig', 'HCApply',
            base_scope(HCJsonFields=NS(Has=lambda encoded, field: field in encoded)),
            modded=False, fields=fields)
        decoded = NS(**dict.fromkeys(fields, 0))  # explicit native zero-fill fixture
        apply(config, decoded, set())
        self.assertTrue(config.Enabled)
        self.assertEqual(.2, config.GroundOffsetM)
        decoded.RowsPerTick = 3
        apply(config, decoded, {'RowsPerTick'})
        self.assertEqual(3, config.RowsPerTick)
        valid = compile_authored(SOURCE, 'HCAdminTeleportConfig', 'HCValid', base_scope(),
                                 modded=False, fields=fields)
        self.assertTrue(valid(config))
        for field, value in (('RowsPerTick', 0), ('PageSize', 65), ('MaxDestinations', 257),
                             ('GroundOffsetM', float('nan')), ('ClearanceHeightM', 0)):
            bad = NS(**vars(config))
            setattr(bad, field, value)
            self.assertFalse(valid(bad), field)

    def test_ground_search_stops_when_shared_budget_refuses(self):
        config, _ = self.config()
        calls, credits = [], [0]
        work = NS(HCReset=lambda count: credits.__setitem__(0, count),
                  HCContinue=lambda: True)
        scope = base_scope(HCServer=NS(Get=lambda: NS(HCTickWork=lambda: NS(HCTake=lambda cost: False))),
                           vector=NS(Zero=[0, 0, 0]))
        fn = compile_authored(SOURCE, 'HCAdminTeleport', 'HCFindGround', scope, ('HCGround',), modded=False)
        owner = NS(m_Config=config, m_Work=work, HCGround=lambda *args: calls.append(args))
        self.assertEqual([0, 0, 0], fn(owner, [10, 0, 20], object()))
        self.assertEqual([], calls)

    def test_destination_builder_resumes_one_shared_row_per_tick(self):
        config, _ = self.config()
        remaining = [0]
        def take(cost):
            if remaining[0] < cost:
                return False
            remaining[0] -= cost
            return True
        camp = NS(Position=[100, 0, 200])
        home = NS(HousePos=[300, 0, 400])
        scope = base_scope(HCServer=NS(Get=lambda: NS(HCTickWork=lambda: NS(HCTake=take))),
            HCCampModule=NS(Get=lambda: NS(HCEncounterCount=lambda: 1, HCEncounterTarget=lambda i, now: camp)),
            HCHoldouts=NS(Get=lambda: NS(Count=lambda: 1, Snapshot=lambda i: home)),
            HCWorldClock=NS(UTC=lambda: 100))
        fn = compile_authored(SOURCE, 'HCAdminTeleport', 'HCStep', scope, ('HCAdd', 'HCRefuse'), modded=False)
        owner = NS(m_CatalogStarted=True, m_Enabled=True, m_Complete=False, m_Config=config,
                   m_Work=NS(HCReset=lambda count: None, HCContinue=lambda: True),
                   m_Destinations=EArray(), m_Stage=0, m_Cursor=0, m_NameCount=0,
                   m_Sites=NS(Sites=EArray([NS(Id='synthetic-site', Waypoints=EArray([[20, 0, 30]]))])))
        owner.HCAdd = lambda label, pos: owner.m_Destinations.append((label, pos))
        owner.HCRefuse = lambda reason: self.fail(reason)
        for tick in range(12):
            before = len(owner.m_Destinations)
            remaining[0] = 1
            fn(owner)
            self.assertLessEqual(len(owner.m_Destinations) - before, 1)
            if owner.m_Complete:
                break
        self.assertTrue(owner.m_Complete)
        self.assertEqual(['AI synthetic-site', 'Camp 1', 'Holdout 1'], [r[0] for r in owner.m_Destinations])


class DispatchBehavior(unittest.TestCase):
    def test_only_authorized_sender_enters_the_existing_command_dispatch(self):
        module = SOURCE.with_name('HCAdminModule.c')
        calls, denials = [], []
        scope = base_scope(HCAdminWire=NS(HCIsLootMap=lambda command: False))
        fn = compile_authored(module, 'HCAdminModule', 'HCDispatch', scope,
                             ('HCAuthorized', 'HCRefused', 'HCCommand'), modded=False)
        owner = NS(HCAuthorized=lambda sender: sender == 'admin', HCRefused=denials.append,
                   HCCommand=lambda *args: calls.append(args) or True)
        for command in ('tp', 'tplist', 'tprefresh'):
            self.assertFalse(fn(owner, 'outsider', command, 5, 1))
            self.assertTrue(fn(owner, 'admin', command, 5, 1))
        self.assertEqual(['outsider'] * 3, denials)
        self.assertEqual([('admin', cmd, 5, 1) for cmd in ('tp', 'tplist', 'tprefresh')], calls)


class DestinationListingBehavior(unittest.TestCase):
    def test_pages_clamp_and_keep_snapshot_indices(self):
        fn = compile_authored(SOURCE, 'HCAdminTeleport', 'HCList', base_scope(), modded=False)
        owner = NS(m_Enabled=True, m_Complete=True, m_Config=NS(PageSize=2),
                   m_Destinations=EArray(NS(Label='fixture-' + str(i)) for i in range(5)))
        for requested, expected in ((-99, ['0: fixture-0', '1: fixture-1']),
                                    (999, ['4: fixture-4'])):
            reply = NS(Lines=EArray())
            self.assertTrue(fn(owner, reply, requested))
            self.assertEqual(expected, reply.Lines)
            self.assertIn('pages=3', reply.Notice)
        owner.m_Complete = False
        reply = NS(Lines=EArray())
        self.assertFalse(fn(owner, reply, 0))
        self.assertEqual([], reply.Lines)

    def test_refresh_invalidates_indices_until_builder_completes_and_off_is_noop(self):
        fn = compile_authored(SOURCE, 'HCAdminTeleport', 'HCRefresh', base_scope(), modded=False)
        owner = NS(m_Enabled=True, m_CatalogStarted=True, m_Destinations=EArray([1]),
                   m_Complete=True, m_Stage=4, m_Cursor=99)
        self.assertTrue(fn(owner))
        self.assertEqual(([], False, 0, 0), (owner.m_Destinations, owner.m_Complete, owner.m_Stage, owner.m_Cursor))
        owner.m_Enabled = False
        owner.m_Destinations.append(1)
        self.assertFalse(fn(owner))
        self.assertEqual([1], owner.m_Destinations)


if __name__ == "__main__":
    unittest.main()
