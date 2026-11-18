"""One smoke of authored decisions, using explicit synthetic DTOs.

Uses the existing translator unchanged; no engine/replication acceptance.
RED before implementation: AssertionError: False is not true : missing Enforce
lead implementation. Ran 1 test; FAILED (failures=1).
GREEN: PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_v2_leads -v
Ran 1 test; OK.
"""
from pathlib import Path
from types import SimpleNamespace as N
import re
import string
import unittest

from tests.unit.test_event_runtime import Handle, translate

ROOT = Path(__file__).resolve().parents[2]
LEADS = ROOT / 'mods/HollowCountry/scripts/4_World/Leads/HCLeadModule.c'
NOTES = LEADS.with_name('HCNoteLedger.c')


class LeadsSmoke(unittest.TestCase):
    def test_solo_identity_keys_are_token_safe_in_both_delivery_paths(self):
        # Explicit synthetic identities/group service; execute authored key and
        # routing decisions. No native identity or persistence proof.
        source = LEADS.read_text()
        limits = (ROOT / 'mods/HollowCountry/scripts/3_Game/World/HCWorldData.c').read_text()
        alphabet = re.search(r'string alphabet = "([^"]+)";', limits)[1]
        policy = N()
        env = {'HCLeadPolicy': policy, 'Print': lambda message: None}
        policy.SoloGroup = translate(source, 'SoloGroup', env, 'HCLeadPolicy')
        for uid in ('base64+/identity==', 'existing_token-.:/42', string.printable):
            expected = 'solo:' + ''.join(c if c in alphabet else '_' for c in uid)
            self.assertEqual(expected, policy.SoloGroup(uid))
            self.assertEqual(policy.SoloGroup(uid), policy.SoloGroup(uid))
        uid = 'base64+/identity=='
        key = policy.SoloGroup(uid)
        self.assertTrue(1 <= len(key) <= 96)
        self.assertTrue(all(c in alphabet for c in key))
        # Only adapt local DTO type syntax, using the existing translator.
        adapted = source.replace('HCGroupService groups', 'HCEventGroupService groups')
        adapted = adapted.replace('HCGroupRecord group', 'HCEventGroupRecord group')
        env['HCGroupRules'] = N(FindGroup=lambda state, identity: None)
        resolve = translate(adapted, 'HCLeadGroup', env, member=True)
        groups = N(m_Healthy=True, m_State=N())
        groups.HCLeadGroup = lambda player: resolve(groups, player)
        service = N(Get=lambda: None)
        env['HCGroupService'] = service
        receive = translate(adapted, 'ReceivePlayer', env, 'HCLeadModule', member=True)
        deliveries = []
        owner = N(Receive=lambda offer, group, origin: deliveries.append((group, origin)))
        player = Handle(identity=uid)
        receive(owner, N(), player, 'news')
        service.Get = lambda: groups
        receive(owner, N(), player, 'note')
        self.assertEqual([(key, 'news'), (key, 'note')], deliveries)
        # Existing group membership remains authoritative; unhealthy service
        # and absent identities still refuse delivery.
        env['HCGroupRules'].FindGroup = lambda state, identity: N(Id=17)
        receive(owner, N(), player, 'radio')
        self.assertEqual(('group-17', 'radio'), deliveries[-1])
        groups.m_Healthy = False
        receive(owner, N(), player, 'news')
        receive(owner, N(), Handle(identity=''), 'news')
        self.assertEqual(3, len(deliveries))

    def test_scene_without_facts_creates_one_fallback_note(self):
        # Explicit synthetic paper/storage ports; no engine or translator changes.
        env = {'HCLeadPolicy': N(), 'HCWorldLimits': N(NOTES=10)}
        source = LEADS.read_text()
        prepare = translate(source, 'PrepareSceneLead', env, 'HCLeadPolicy')
        env['HCLeadPolicy'].PrepareSceneLead = prepare
        env['HCLeadPolicy'].KnownPlace = lambda place: place == 'kamenka'
        env['HCLeadPolicy'].Valid = lambda lead: bool(lead.Kind)
        admit = translate(NOTES.read_text(), 'CanCreate', env, 'HCNoteLedger')
        papers = {}

        def create(scene, position, lead):
            if not admit(len(papers), int(scene in papers)):
                return None
            papers[scene] = N(position=position, lead=vars(lead).copy())
            return papers[scene]

        scene_source = (LEADS.parent.parent / 'Scenes/HCScenesModule.c').read_text()
        offer = translate(scene_source, 'SceneNote', env)
        ledger = N(Create=create)
        empty_lead = N(Kind='', TargetPlaceId='', Expires=0, TextId='', Source='')
        self.assertTrue(offer(ledger, empty_lead, 'scene-kamenka', 'kamenka', [0, 0, 7], 10000))
        self.assertEqual(('PLACE', 'kamenka', 'scene_started'),
                         tuple(papers['scene-kamenka'].lead[k] for k in ('Kind', 'TargetPlaceId', 'TextId')))
        self.assertFalse(offer(ledger, empty_lead, 'scene-kamenka', 'kamenka', [0, 0, 7], 10001))
        self.assertEqual(1, len(papers))
        self.assertIn('SceneNote(notes, lead, chain.Id, placeId, notePosition, HCWorldClock.UTC())', scene_source)

    def test_delayed_place_only_lead_and_world_note_cap(self):
        self.assertTrue(LEADS.is_file(), 'missing Enforce lead implementation')
        env = {'HCLeadPolicy': N(), 'HCWorldLimits': N(NOTES=10)}
        build = translate(LEADS.read_text(), 'Build', env, 'HCLeadPolicy')
        # Position is a synthetic live signal deliberately attached to the fact.
        fact = N(Kind='SHOTS_HEARD', PlaceId='stary-sobor', At=10000,
                 Expires=30000, Position=[6123, 42, 7799])
        lead = N()
        self.assertFalse(build(fact, lead, 'stary-sobor', 'DANGER', 11799))
        self.assertTrue(build(fact, lead, 'stary-sobor', 'DANGER', 11800))
        self.assertEqual('stary-sobor', lead.TargetPlaceId)
        self.assertFalse(hasattr(lead, 'Position'))
        self.assertEqual({'Kind', 'TargetPlaceId', 'Expires', 'TextId'}, set(vars(lead)))
        self.assertFalse(build(fact, N(), '', 'DANGER', 11800))
        self.assertFalse(build(fact, N(), 'stary-sobor', 'DANGER', 30000))
        admit = translate(NOTES.read_text(), 'CanCreate', env, 'HCNoteLedger')
        self.assertTrue(admit(9, 0))
        self.assertFalse(admit(10, 0))
        self.assertFalse(admit(11, 0))
        self.assertFalse(admit(0, 1))


if __name__ == '__main__':
    unittest.main()
