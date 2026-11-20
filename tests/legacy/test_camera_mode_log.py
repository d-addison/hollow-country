"""The server logs its camera rule once at startup so the local session can confirm
first person on foot / third person in vehicles (owner rule 2026-11-17)."""
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
MISSION = ROOT / 'mods/HollowCountry/scripts/5_Mission/HCMissionServer.c'


def mission_text():
    return MISSION.read_text(encoding='utf-8')


def start_body():
    text = mission_text()
    start = text.index('void HCLogCameraMode()')
    end = text.index('override void OnMissionFinish()')
    return text[start:end]


class CameraModeLog(unittest.TestCase):
    def test_start_reads_native_view_mode_after_initialization(self):
        self.assertIn('GetGame().GetWorld().GetThirdPersonViewMode()', start_body())
        text = mission_text()
        on_init = text[text.index('override void OnInit()'):text.index('void HCLogCameraMode()')]
        self.assertLess(on_init.index('HCServer.Get().Start();'), on_init.index('HCLogCameraMode();'))

    def test_every_native_mode_has_a_readable_name(self):
        body = start_body()
        for name, label in (('ENABLED', 'third person'), ('DISABLED', 'first person only'),
                            ('VEHICLES_ONLY', 'first person on foot, third person in vehicles')):
            self.assertRegex(body, r'ThirdPersonMode\.' + name + r'\)[^;]*\n?[^"]*"' + re.escape(label) + '"')
        self.assertIn('[HollowCountry] Camera mode: ', body)

    def test_other_modes_warn_operator_with_the_server_config_fix(self):
        # W6 friend report: the mode comes from serverDZ.cfg (no script setter in
        # 3_Game/Global/World.c:177), so a wrong mode must name the exact fix once.
        body = start_body()
        self.assertRegex(body, r'if \(viewMode != ThirdPersonMode\.VEHICLES_ONLY\)\s*Print\(')
        self.assertIn('[HollowCountry] Camera mode WARNING: owner rule is first person on foot, third person in vehicles; '
                      'set thirdPersonView = 2; and disable3rdPerson = 0; in serverDZ.cfg and restart', body)
        self.assertEqual(2, body.count('Print('))

    def test_missing_world_is_tolerated(self):
        self.assertIn('if (!GetGame() || !GetGame().GetWorld()) return;', start_body())


if __name__ == '__main__':
    unittest.main()
