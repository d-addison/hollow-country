"""HC-13 explicit synthetic character IDs/store; no native lifecycle evidence.

Actual RED (2026-11-18):
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest test_hc_familiarity -v
  AssertionError: 0 != 2 : death retains score
GREEN: same command, Ran 1 test, OK. Native acceptance remains PENDING.
"""
import copy
import json
from pathlib import Path
import re
from types import SimpleNamespace as N
import unittest

from tests.unit.test_admin_test_kit import rewrite_tostring

from tests.unit.test_event_runtime import translate
from tests.unit.test_group_server import EArray
from tests.unit.test_hc_forage import bind

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'mods/HollowCountry/scripts/4_World/Progression/HCProgression.c'
POLICY = ROOT / 'mods/HollowCountry/scripts/4_World/Survival/HCSurvivalPolicy.c'


class FamiliarityLife(unittest.TestCase):
    def test_death_resets_generation_reconnect_retains_and_legacy_maps_once(self):
        self.now = 5000
        saved = []
        write_fails = [False]
        def save(*args):
            if write_fails[0]:
                return False
            saved.append(args[1])
            return True
        policy = N()
        env = dict(str=str, range=range, EArray=EArray, Print=lambda line: None,
                   HCGroupClock=N(Utc=lambda: self.now),
                   HCWorldLimits=N(Admit=lambda count, cap, name: count < cap),
                   HCSurvivalPolicy=policy,
                   HCSurvivalRuntime=N(HCIsServer=lambda: True, HCIdentityKey=lambda p: p.uid,
                                       HCCharacterKey=lambda p: p.life),
                   HCProgressionState=lambda: N(Version=2, Players=EArray()),
                   HCProgressionRow=lambda: N(Key='', CharacterKey='', Dead=False,
                                               LegacyDeferred=False, Forage=0, DecayUtc=0, GainUtc=0),
                   HCSaveJob=N(STEP_DONE=0, STEP_MORE=1, STEP_FAILED=2),
                   HCV2ThreatStore=N(Save=save, CanOpen=lambda path:True),
                   HCGroupIO=N(Read=lambda path,limit:json.dumps(module.m_State,default=vars),
                               WriteNew=lambda *args:save(None,copy.deepcopy(module.m_State),65536)),
                   PATH='synthetic/progression', LEGACY_PATH='synthetic/progression.v1.json',
                   FileExist=lambda path:False, HCPerfPlayers=N(HCGet=lambda:EArray()),
                   s_HCInstance=None)
        for name in ('DecayedFamiliarity', 'ForageDelay'):
            setattr(policy, name, translate(POLICY.read_text(), name, env, 'HCSurvivalPolicy'))
        # Explicit trusted native ports: server/account/character identity, not client fields.
        state = N(Version=2, Players=EArray())
        module = N(m_State=state, m_Healthy=True, m_Dirty=False, m_SaveUtc=self.now,
                   m_Revision=0, m_SnapshotRevision=0, m_SaveStage=0, m_Snapshot=None,
                   m_SaveJob=N(HCDirty=False, HCInFlight=False),
                   m_IdentityRefused=False, m_RowCap=128, m_Cursor=0, m_Status=N(HCPublish=lambda *args: None))
        module.HCFail = lambda: self.fail('unexpected authored store/clock refusal')
        names = ['HCDecay', 'HCAwardForage']
        for name in ('HCFail', 'HCReceipt', 'HCChanged', 'HCResetLife', 'HCIdentityRefusal', 'HCObserveDeath', 'HCFlush', 'HCStepCheckpoint', 'HCMigrate', 'HCLegacyCharacterKey', 'HCPruneRows'):
            if ' ' + name + '(' in SOURCE.read_text():
                names.append(name)
        # Generic store type is a syntax-only binding in the same restricted port.
        source = re.sub(r'if \(!HCGroupIO.Read\(([^,]+), ([^,]+), (\w+)\)\)',
                        r'\3 = HCGroupIO.Read(\1, \2); if (!\3)',SOURCE.read_text())
        bind(SOURCE, 'HCProgressionModule', module, env, names, source=source)
        def flush(job):
            for _ in range(16):
                step = module.HCStepCheckpoint()
                if step != 1:
                    job.HCDirty = False
                    return step == 0
            return False
        env['HCSaveScheduler'] = N(HCFlush=flush)
        # bind copies env, so supply scheduler before binding handlers.
        bind(SOURCE, 'HCProgressionModule', module, env, names, source=source)
        living = N(uid='p'+'61'*16, life='c:1:2:3:4', IsAlive=lambda: True)
        self.assertEqual(1, module.HCAwardForage(living))
        self.assertEqual(1, module.HCAwardForage(living))  # rate limit
        self.now += 60
        self.assertEqual(2, module.HCAwardForage(living))
        reconnect = N(**vars(living))
        self.assertEqual(2, module.HCAwardForage(reconnect))
        # Dispatch the authored death notification when present; before HC-13
        # there is no observer, and the actual authored award score stays 2.
        if hasattr(module, 'HCObserveDeath'):
            # An in-flight older image must never overwrite a death reset.
            self.assertEqual(1, module.HCStepCheckpoint())
            module.m_SaveJob.HCInFlight = True
            supers = []
            death_env = dict(env, HCProgressionModule=N(HCCharacterDied=module.HCObserveDeath),
                             super=N(EEKilled=lambda killer: supers.append(killer)))
            bind(SOURCE, 'PlayerBase', living, death_env, ('EEKilled',))
            living.EEKilled(None)
            self.assertEqual([None], supers)
        self.assertEqual(0, state.Players[0].Forage, 'death retains score')
        self.assertTrue(state.Players[0].Dead)
        self.assertTrue(saved, 'death must finish the durable barrier')
        self.assertEqual(0, saved[-1].Players[0].Forage)
        self.assertEqual(0, module.HCAwardForage(reconnect), 'old life tombstone cannot earn')
        # Restart consumes the same synthetic saved DTO through authored handlers.
        module.m_State = saved[-1]
        replacement = N(uid=living.uid, life='c:5:6:7:8', IsAlive=lambda: True)
        self.assertEqual(1, module.HCAwardForage(replacement))
        self.assertFalse(module.m_State.Players[0].Dead)
        self.assertEqual(replacement.life, module.m_State.Players[0].CharacterKey)
        self.assertEqual(1, module.HCAwardForage(N(**vars(replacement))))
        unknown = N(uid=living.uid, life='', IsAlive=lambda: True)
        self.assertEqual(0, module.HCAwardForage(unknown))
        # A late death notification for the old corpse cannot reset its replacement.
        module.HCObserveDeath(living)
        self.assertEqual(1, module.m_State.Players[0].Forage)
        # Unmapped account-wide rows are archived and deferred for the first living pickup.
        module.m_State = N(Version=1, Players=EArray([N(Key=living.uid,
            Forage=100, DecayUtc=self.now-100, GainUtc=self.now-60,
            CharacterKey='', Dead=False, LegacyDeferred=False)]))
        self.assertTrue(module.HCMigrate(self.now))
        self.assertEqual(2, module.m_State.Version)
        self.assertTrue(module.m_State.Players[0].LegacyDeferred)
        self.assertEqual(1, saved[-1].Version)
        self.assertEqual(100, saved[-1].Players[0].Forage)
        self.assertEqual(100, module.HCAwardForage(replacement))
        self.assertFalse(module.m_State.Players[0].LegacyDeferred)
        for _ in range(110):
            self.now += 60
            self.assertLessEqual(module.HCAwardForage(replacement), 100)
        self.assertEqual(100, module.m_State.Players[0].Forage)
        self.now += 86400
        module.HCDecay(module.m_State.Players[0], self.now)
        self.assertEqual(99, module.m_State.Players[0].Forage)
        # Execute the authored native-ID encoder. Only Enforce out-parameter
        # assignment is adapted; IDs here are explicitly synthetic native outputs.
        native = POLICY.read_text()
        native = native.replace('player.GetPersistentID(part1, part2, part3, part4);',
            'part1 = player.parts[0]; part2 = player.parts[1]; part3 = player.parts[2]; part4 = player.parts[3];')
        runtime = N(HCIsServer=lambda: True)
        encoder = translate(rewrite_tostring(native), 'HCCharacterKey',
                            dict(HCSurvivalRuntime=runtime, str=str), 'HCSurvivalRuntime')
        self.assertEqual('', encoder(N(parts=(0, 0, 0, 0))))
        self.assertEqual('c:1:2:3:4', encoder(N(parts=(1, 2, 3, 4))))
        self.assertNotEqual(encoder(N(parts=(1, 2, 3, 4))), encoder(N(parts=(1, 2, 3, 5))))
        write_fails[0] = True
        previous_writes = len(saved)
        module.HCObserveDeath(replacement)
        self.assertFalse(module.m_Healthy)
        self.assertEqual(0, module.HCAwardForage(replacement))
        self.assertEqual(2, module.HCStepCheckpoint())
        self.assertEqual(previous_writes, len(saved), 'faulted writer never retries/rewards')


if __name__ == '__main__':
    unittest.main()
