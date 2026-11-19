"""w43 #150/#202 behavioral trace. Explicit synthetic ports, no DayZ evidence.

Spec: assigned issue briefs; required central specification paths absent.
Plan/tasks: retain persisted four-week/default-on weather owner, allow configured
phase duration, fill four absent flora via finite native-class nodes and shared
sight veto; pin stock XML delegation to a receipt-backed install/rollback.
Deferred: white ground has no supported installed native port found; DayZDiag,
signed PBO/server, two-client sight/food/weather and 3-6-player costs pending.

Actual RED, PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_w43_seasons -v:
  AssertionError: Lists differ: ['AmanitaMushroom'] != ['SambucusBerry']
  AssertionError: None is not true : weather must be planned by default
Additional focused REDs in the same module:
  candidate must be outside every observer sight
  AssertionError: False is not true : configured phase duration must be accepted
GREEN command is the same module command; see worker report/commit message.
"""
import unittest
from unittest import mock
from tests.unit.test_local_test_session import SessionCase
from tests.unit.test_atmosphere import fixture
from tests.unit.test_hc_forage_round2 import SyntheticRuntime
from tools.setup import local_test_session as lts


class SeasonConfig(unittest.TestCase):
    def test_phase_duration_is_an_operator_setting_with_safe_cycle_arithmetic(self):
        from pathlib import Path
        from types import SimpleNamespace as N
        from tests.unit.test_event_runtime import translate
        source = (Path(__file__).resolve().parents[2] / 'mods/HollowCountry/scripts/4_World/Weather/HCVisualSeasons.c').read_text()
        config = N(SchemaVersion=1, PhaseSeconds=302400, CheckpointSeconds=60,
                   MaxUncheckpointedSeconds=120, MaxClockDeltaSeconds=10)
        valid = translate(source, 'HCValid', vars(config), 'HCVisualSeasonConfig', member=True)
        self.assertTrue(valid(config), 'configured phase duration must be accepted')
        for seconds in (0, -1, 536870912):
            valid.__globals__['PhaseSeconds'] = seconds
            self.assertFalse(valid(config))


class Flora(unittest.TestCase):
    def test_visible_candidate_cannot_materialize(self):
        runtime = SyntheticRuntime()
        runtime.players.Insert(runtime.player())
        runtime.hidden = False
        runtime.start()
        runtime.forage.OnTick(10)
        self.assertEqual([], runtime.created, 'candidate must be outside every observer sight')

    def test_four_routes_materialize_through_existing_finite_nodes(self):
        kinds = ('AmanitaMushroom', 'AuriculariaMushroom', 'CraterellusMushroom', 'PsilocybeMushroom')
        for roll, kind in enumerate(kinds, 1):
            runtime = SyntheticRuntime()
            runtime.roll = roll
            runtime.players.Insert(runtime.player())
            runtime.start()
            runtime.forage.m_SlotCursor = 2
            runtime.forage.OnTick(10)
            self.assertEqual([kind], [item.kind for item in runtime.created])
            self.assertEqual(1, len(runtime.forage.m_Nodes))
            runtime.forage.m_SlotCursor = 2
            runtime.forage.m_PlayerCursor = 0
            runtime.forage.OnTick(10)
            self.assertEqual(1, len(runtime.created), 'durable reservation must prevent duplicate grant')


class Weather(SessionCase):
    def setUp(self):
        super().setUp()
        self.original = fixture()  # synthetic vanilla-like weather, explicitly pinned only in this fixture
        self.weather = self.mission / 'cfgweather.xml'
        self.weather.write_bytes(self.original)
        patch = mock.patch.object(lts, 'WEATHER_STOCK_SHA256', lts.sha(self.original), create=True)
        patch.start()
        self.addCleanup(patch.stop)

    def test_default_installs_delegated_candidate_and_rollback_restores_bytes(self):
        args = lts.build_parser().parse_args(self.args())
        plan = lts.build_plan(args, self.repo)
        self.assertTrue(plan.get('weather'), 'weather must be planned by default')
        lts.apply_plan(plan, args)
        from tools.package.atmosphere import SCRIPT_XML_PREFIX
        self.assertTrue(self.weather.read_bytes().startswith(SCRIPT_XML_PREFIX))
        lts.rollback(self.server, self.repo)
        self.assertEqual(self.original, self.weather.read_bytes())

    def test_foreign_settings_and_opt_out_are_preserved(self):
        self.weather.write_bytes(self.original.replace(b'enable="0"', b'enable="1"'))
        before = self.weather.read_bytes()
        plan = lts.build_plan(lts.build_parser().parse_args(self.args()), self.repo)
        self.assertIsNone(plan['weather'])
        self.assertEqual(before, self.weather.read_bytes())
        self.assertIn('foreign', plan['weather_note'])
        args = lts.build_parser().parse_args(self.args())
        lts.apply_plan(plan, args)
        self.assertEqual(before, self.weather.read_bytes())
        lts.rollback(self.server, self.repo)
        self.assertEqual(before, self.weather.read_bytes())
        self.weather.write_bytes(self.original)
        plan = lts.build_plan(lts.build_parser().parse_args(self.args('plan', '--no-weather')), self.repo)
        self.assertIsNone(plan['weather'])

    def test_drift_refuses_rollback_before_other_session_changes(self):
        args = lts.build_parser().parse_args(self.args())
        plan = lts.build_plan(args, self.repo)
        self.assertTrue(plan.get('weather'), 'weather must be planned by default')
        lts.apply_plan(plan, args)
        self.weather.write_bytes(b'foreign edit')
        with self.assertRaisesRegex(lts.Refused, 'weather.*drift'):
            lts.rollback(self.server, self.repo)
        self.assertTrue(self.dest.is_dir())
