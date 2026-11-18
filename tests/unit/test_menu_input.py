"""Source contracts for HC scripted menus (playtest 2026-11-18: the admin window let the mouse
turn the character, and Escape did nothing). Offline checks; they do not establish DayZ input."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / 'mods/HollowCountry/scripts'
HELPER = SCRIPTS / '5_Mission/Polish/HCMenuInput.c'


def strip(text):
    return re.sub(r'//[^\n]*', '', re.sub(r'/\*.*?\*/', '', text, flags=re.S))


def body(text, name):
    m = re.search(r'override\s+\w+\s+' + name + r'\s*\([^)]*\)\s*\{', text)
    if not m:
        return None
    depth, i = 1, m.end()
    while depth:
        depth += {'{': 1, '}': -1}.get(text[i], 0)
        i += 1
    return text[m.end():i - 1]


def menus():
    found = []
    for path in sorted(SCRIPTS.rglob('*.c')):
        text = strip(path.read_text())
        if re.search(r'class\s+\w+\s*(?::|extends)\s*UIScriptedMenu\b', text):
            found.append((path, text))
    return found


class MenuInput(unittest.TestCase):
    def test_helper_uses_the_native_menu_input_exclude_and_back_input(self):
        text = strip(HELPER.read_text())
        self.assertIn('AddActiveInputExcludes({"menu"})', text.replace(' ', '').replace('{"menu"}', '{"menu"}'))
        self.assertIn('RemoveActiveInputExcludes({"menu"},true)', text.replace(' ', ''))
        self.assertIn('GetInputByID(UAUIBack)', text.replace(' ', ''))
        self.assertIn('LocalPress()', text)

    def test_every_hc_menu_locks_on_show_unlocks_on_hide_and_closes_on_back(self):
        found = menus()
        self.assertEqual(3, len(found), [p.name for p, _ in found])
        for path, text in found:
            with self.subTest(menu=path.name):
                show, hide, update = body(text, 'OnShow'), body(text, 'OnHide'), body(text, 'Update')
                self.assertIsNotNone(show)
                self.assertIn('HCMenuInput.Lock()', show)
                self.assertIsNotNone(hide)
                self.assertIn('HCMenuInput.Unlock()', hide)
                self.assertIsNotNone(update)
                self.assertRegex(update, r'if\s*\(\s*HCMenuInput\.BackPressed\(\)\s*\)\s*\{\s*Close\(\);\s*return;\s*\}')


class AdminSenderMatch(unittest.TestCase):
    def test_admin_server_matches_the_sender_player_by_identity_id(self):
        text = strip((SCRIPTS / '4_World/Admin/HCAdminModule.c').read_text())
        m = re.search(r'PlayerBase HCPlayer\(PlayerIdentity sender\)\s*\{(.*?)\n    \}', text, re.S)
        self.assertIsNotNone(m)
        # Playtest: "kit" and "list" were refused as live-sender-unavailable for a live admin.
        self.assertNotIn('GetIdentity() == sender', m.group(1))
        self.assertIn('GetId() == sender.GetId()', m.group(1))


if __name__ == '__main__':
    unittest.main()
