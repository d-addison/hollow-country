"""Tiny authored-body smoke checks; synthetic ports, no DayZ/audio evidence."""
import copy
from pathlib import Path
from types import SimpleNamespace as N
import unittest

from tests.legacy.test_event_runtime import translate

ROOT = Path(__file__).resolve().parents[2] / 'mods/HollowCountry/scripts'


class PolishSmoke(unittest.TestCase):
    def test_hint_spacing_and_character_memory(self):
        path = ROOT / '5_Mission/Polish/HCHints.c'
        self.assertTrue(path.is_file(), 'missing HCHints.c')
        source = path.read_text()
        notifications, disk = [], []
        env = dict(NotificationSystem=N(AddNotificationExtended=lambda *a: notifications.append(a)))
        offer = translate(source, 'Offer', env, 'HCHints', member=True)

        def client(state):
            return N(m_State=state, m_Fault=False, m_Shown=0,
                     Save=lambda: disk.append(copy.deepcopy(state)) or True)

        a = client(N(ShownBits=0, PlayedSeconds=30, NextHintSecond=30))
        self.assertTrue(offer(a, 0, 'synthetic search hint'))
        a.m_State.PlayedSeconds = 209
        self.assertFalse(offer(a, 1, 'synthetic menu hint'))
        # Reconnect reads the same character's saved record; clock is local playtime.
        reconnect = client(copy.deepcopy(disk[-1]))
        reconnect.m_State.PlayedSeconds = 210
        self.assertFalse(offer(reconnect, 0, 'synthetic search hint'))
        self.assertTrue(offer(reconnect, 1, 'synthetic menu hint'))
        # A different character owns a distinct record, so guidance starts again.
        other = client(N(ShownBits=0, PlayedSeconds=30, NextHintSecond=30))
        self.assertTrue(offer(other, 0, 'synthetic search hint'))
        self.assertEqual(3, len(notifications))

    def test_environment_spacing_and_cleanup(self):
        path = ROOT / '5_Mission/Atmosphere/HCEnvSound.c'
        self.assertTrue(path.is_file(), 'missing HCEnvSound.c')
        source = path.read_text()
        destroyed = []
        env = dict(SEffectManager=N(DestroyEffect=destroyed.append))
        allowed = translate(source, 'CanPlay', env)
        stop = translate(source, 'StopSound', env, 'HCEnvSound', member=True)
        self.assertFalse(allowed(179, 180, False))
        self.assertFalse(allowed(180, 180, True))
        self.assertTrue(allowed(180, 180, False))
        handle = object()
        state = N(m_Sound=handle)
        stop(state)
        stop(state)
        self.assertEqual([handle], destroyed)
        self.assertIsNone(state.m_Sound)


if __name__ == '__main__':
    unittest.main()
