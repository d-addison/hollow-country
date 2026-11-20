"""HC-50 authored refusal receipt through explicitly synthetic HC-6/server ports.

This tests reporting behavior, never terrain feasibility, licensing or DayZ.
"""
from pathlib import Path
from types import SimpleNamespace as N
import unittest

from tests.legacy.test_event_runtime import translate

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'mods/HollowCountry/scripts/4_World/Weather/HCWinterTerrainAdmission.c'


class WinterTerrainAdmissionBehavior(unittest.TestCase):
    def test_no_verified_dependency_cannot_report_supported_even_in_winter(self):
        self.assertTrue(SOURCE.is_file(), 'missing authored HC-50 fail-closed admission receipt')
        lines = []
        server = N(IsServer=lambda: True)
        env = dict(Print=lines.append, GetGame=lambda: server)
        policy = N()
        env['HCWinterTerrainAdmission'] = policy
        source = SOURCE.read_text()
        for method in ('HCLine', 'HCReport'):
            setattr(policy, method, translate(source, method, env, 'HCWinterTerrainAdmission'))

        # Explicitly synthetic HC-6 observation port. Inactive clock's phase
        # must not be read as effective spring/winter.
        def unavailable_phase():
            self.fail('inactive clock phase was consumed')

        inactive = N(HCActive=lambda: False, HCSeason=unavailable_phase)
        for clock in (None, inactive):
            policy.HCReport(clock)
            self.assertIn('white_terrain=refused', lines[-1])
            self.assertIn('season=unavailable', lines[-1])
        self.assertIn('reason=HC6_UNAVAILABLE', lines[0])
        self.assertIn('reason=HC6_NOT_ADMITTED', lines[1])

        for season in ('spring', 'summer', 'autumn', 'winter'):
            clock = N(HCActive=lambda: True, HCSeason=lambda: season)
            policy.HCReport(clock)
            self.assertIn('white_terrain=pending', lines[-1])
            self.assertIn('season=' + season, lines[-1])
            self.assertIn('reason=NO_VERIFIED_TERRAIN_SOURCE_OR_RIGHTS', lines[-1])
        for line in lines:
            self.assertIn('dependency=none boundary=stopped-server-restart', line)
            self.assertIn('effective=off admitted=0 observed=unknown runtime=PENDING', line)
            self.assertIn('refusal=DYNAMIC_TERRAIN_API_UNPROVEN', line)
            self.assertNotIn('white_terrain=supported', line)

        count = len(lines)
        server = N(IsServer=lambda: False)
        policy.HCReport(None)
        server = None
        policy.HCReport(None)
        self.assertEqual(count, len(lines), 'clients/absent game must be cheap no-ops')
