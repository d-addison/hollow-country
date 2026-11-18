"""Pressing the admin key must never fail silently (playtest: Pause showed nothing).

The server stays silent to non-admins by design, so the client has to say that
the key worked, and why no window opened when the server never answered.
Source-level checks only; offline tests never establish DayZ behaviour.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CLIENT = ROOT / 'mods/HollowCountry/scripts/5_Mission/Admin/HCAdminClient.c'


def method(source, name):
    start = source.index('    ' + name)
    brace = source.index('{', start)
    depth = 0
    for index in range(brace, len(source)):
        if source[index] == '{':
            depth += 1
        elif source[index] == '}':
            depth -= 1
            if depth == 0:
                return source[brace:index + 1]
    raise AssertionError(name + ' has no body')


class AdminKeyFeedback(unittest.TestCase):
    def setUp(self):
        self.source = CLIENT.read_text(encoding='utf-8')

    def test_pressing_the_key_says_the_request_was_sent_or_why_not(self):
        body = method(self.source, 'void HCOpen()')
        self.assertIn('HCNotify(', body)
        self.assertRegex(body, r'if \(m_OpenRequested\)[\s\S]*HCNotify\(')
        self.assertRegex(body, r'else[\s\S]*HCNotify\(')

    def test_an_unanswered_request_names_the_allowlist_before_giving_up(self):
        body = method(self.source, 'void HCTick()')
        timeout = re.search(r'else if \(now >= m_OpenUntil\)\s*\{([^}]*)\}', body)
        assert timeout is not None, 'open timeout branch missing'
        self.assertIn('HCNotify(', timeout.group(1))
        self.assertLess(timeout.group(1).index('HCNotify('), timeout.group(1).index('HCStop()'))
        message = re.search(r'HCNotify\("([^"]*)"', timeout.group(1))
        assert message is not None
        self.assertIn('admins.json', message.group(1))
        self.assertIn('EnableAdminMap', message.group(1))

    def test_notices_use_the_native_client_notification(self):
        body = method(self.source, 'void HCNotify(')
        self.assertIn('NotificationSystem.AddNotificationExtended(', body)
        self.assertIn('IsServer()', body)


if __name__ == '__main__':
    unittest.main()
