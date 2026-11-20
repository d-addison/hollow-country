"""#150 read-only consumer contract; synthetic ports execute authored methods.

Spec/plan/tasks: issue-audit #150 -> read active owner's persisted clock without
calendar/forage writes -> unavailable/refusal/phase-boundary/recovery coverage.
Native acceptance remains pending; these fixtures never run DayZ.
"""
from pathlib import Path
from types import SimpleNamespace as N
import functools
import re
import unittest

from tests.legacy.test_event_runtime import translate

ROOT = Path(__file__).resolve().parents[2]
CLOCK = ROOT / 'mods/HollowCountry/scripts/4_World/Weather/HCVisualSeasons.c'


class ConsumerPhase(unittest.TestCase):
    def harness(self):
        # Explicit synthetic owner/store/status/native mission; no engine evidence.
        self.seconds = 0
        self.healthy = True
        self.status = N(HCPublish=lambda state, reason: setattr(self, 'receipt', (state, reason)))
        self.clock = N(m_Running=True, m_Paused=False,
                       m_Config=N(PhaseSeconds=10, EnableVisualSeasons=True),
                       m_Store=N(HCElapsed=lambda: self.seconds, HCHealthy=lambda: self.healthy),
                       m_Status=self.status)
        self.data = N(HCWinterTerrainSeasons=lambda: self.clock)
        self.mission = N(GetWorldData=lambda: self.data)
        self.server = True
        env = dict(GetGame=lambda: N(IsServer=lambda: self.server, GetMission=lambda: self.mission),
                   HCEventPort=N(Cast=lambda data: data), HCSeasonVisualPolicy=N(
                       HCPhaseName=lambda code: ['spring', 'summer', 'autumn', 'winter'][code] if code >= 0 else 'unavailable'))
        source = CLOCK.read_text()
        # Syntax-only type aliases; actual method bodies make all decisions.
        source = re.sub(r'\b(?:Mission|ChernarusPlusData|HCVisualSeasons|HCOperationalStatus)\b', 'HCEventPort', source)
        for name in ('HCElapsed', 'HCPhase', 'HCActive', 'HCReadActivePhase', 'HCGetOperationalStatus'):
            method = translate(source, name, env, 'HCEventPort', member=True)
            setattr(self.clock, name, functools.partial(method, self.clock))
        resolver = translate(source, 'HCReadOwnerPhase', env, 'auditseason_Phase')
        env['auditseason_Phase'] = N(HCReadOwnerPhase=resolver)
        return translate(source, 'HCReadPhase', env, 'HCEventPort')

    def test_consumers_read_boundaries_from_the_existing_owner_without_advancing_it(self):
        read = self.harness()
        for elapsed, phase in ((0, 0), (9, 0), (10, 1), (20, 2), (30, 3), (40, 0)):
            self.seconds = elapsed
            self.assertEqual(phase, read())
            self.assertEqual(phase, read(), 'reading must not advance the persisted clock')
            self.assertIs(self.status, self.clock.HCGetOperationalStatus())
            self.assertEqual(('ready', 'active_clock'), self.receipt)

    def test_off_paused_missing_unhealthy_and_nonserver_never_look_like_spring(self):
        read = self.harness()
        self.clock.m_Running = False
        self.assertEqual(-1, read())
        self.clock.HCGetOperationalStatus()
        self.assertEqual(('off', 'clock_inactive'), self.receipt)
        self.clock.m_Running = True
        self.clock.m_Paused = True
        self.assertEqual(-1, read())
        self.clock.HCGetOperationalStatus()
        self.assertEqual(('refused', 'clock_paused'), self.receipt)
        self.clock.m_Paused = False
        self.healthy = False
        self.assertEqual(-1, read())
        self.clock.HCGetOperationalStatus()
        self.assertEqual(('refused', 'store_unhealthy'), self.receipt)
        self.healthy = True
        self.assertEqual(0, read())
        self.clock.m_Config.EnableVisualSeasons = False
        self.assertEqual(-1, read())
        self.clock.m_Config.EnableVisualSeasons = True
        self.clock.m_Store = None
        self.assertEqual(-1, read())
        self.clock.m_Store = N(HCHealthy=lambda: True, HCElapsed=lambda: 20)
        self.server = False
        self.assertEqual(-1, read())
        self.server = True
        self.data = None
        self.assertEqual(-1, read())
        self.mission = None
        self.assertEqual(-1, read())

    def test_start_logs_leaf_asset_boundary_once_without_blocking_clock(self):
        from tests.legacy.test_hc_visual_seasons import VisualSeasonBehavior
        fixture = VisualSeasonBehavior()
        clock, store, config = fixture.harness()
        self.assertTrue(clock.HCActive())
        self.assertTrue(clock.HCStart(True))
        self.assertEqual(1, sum('synthetic admission runtime=PENDING' in line
                                for line in fixture.logs))

    def test_leaf_record_has_exact_native_lifecycle_and_honest_pending_boundary(self):
        path = ROOT / 'mods/HollowCountry/scripts/5_Mission/Weather/auditleaves_Client.c'
        self.assertTrue(path.is_file(), 'falling-leaf implementation missing')
        text = path.read_text()
        for evidence in ('ParticleList.c:399', 'Particle.c:158', ':245 StopParticle',
                         ':340 GetParticleCount', 'runtime=PENDING',
                         'HCSeasonVisualClient.HCGetPhase', 'HCStopEmitter', 'HCDrain'):
            self.assertIn(evidence, text)
