"""Synthetic whole-class policy/bounds, never CE-origin/runtime evidence."""
import copy
import unittest
from types import SimpleNamespace as N

from tests.legacy.test_group_server import EArray
from tests.legacy.test_search_economy import invoke, manifest


class EMap(dict):
    def Contains(self,key):return key in self
    def Set(self,key,value):self[key]=value


class SearchPolicyTests(unittest.TestCase):
    def setUp(self):
        self.env={'EMap':EMap}
        self.policy=N()
        for name in ('TextValid','PinValid','ManifestValid'):
            setattr(self.policy,name,lambda *a,n=name:invoke('HCSearchRules.c',n,self.env,N(),*a))
        self.env['HCSearchRules']=self.policy

    def test_valid_empty_and_arbitrary_native_class_assignments(self):
        for typ in ('SyntheticFood','SyntheticWeapon','SyntheticMagazine','SyntheticAmmo',
                    'SyntheticClothing','SyntheticMedical','SyntheticTool','SyntheticContainer'):
            m=manifest();m.Entries[0].ItemClass=typ
            self.assertTrue(self.policy.ManifestValid(m))
        m=manifest();m.Entries[0].SupplyId='';m.Entries[0].ItemClass=''
        self.assertTrue(self.policy.ManifestValid(m))

    def test_shared_supply_cannot_be_allocated_to_two_sites(self):
        m=manifest();entry=copy.deepcopy(m.Entries[0]);entry.SiteId='site_b'
        m.Entries.Insert(entry)
        self.assertFalse(self.policy.ManifestValid(m))
        entry.SupplyId='5_6_7_8';entry.SiteId='site_a'
        self.assertFalse(self.policy.ManifestValid(m))

    def test_manifest_versions_pins_bounds_and_half_empty_entries_fail_closed(self):
        for key,value in [('Version',0),('Epoch',0),('Epoch',1000001),('WorldName',''),
                          ('Build',''),('SourceId',''),('SourcePin','b'*63),('SourcePin','z'*64)]:
            with self.subTest(key=key,value=value):
                m=manifest();setattr(m,key,value)
                self.assertFalse(self.policy.ManifestValid(m))
        for field in ('SupplyId','ItemClass'):
            m=manifest();setattr(m.Entries[0],field,'')
            self.assertFalse(self.policy.ManifestValid(m))
        for value in ('\n','bad\tname','é'*20,'x'*769):
            m=manifest();m.Entries[0].SiteId=value
            self.assertFalse(self.policy.ManifestValid(m))

    def test_manifest_work_is_explicitly_bounded_not_silently_truncated(self):
        m=manifest();m.Entries=EArray()
        self.assertFalse(self.policy.ManifestValid(m))
        for index in range(4096):
            m.Entries.Insert(N(SiteId='site_'+str(index),SupplyId='',ItemClass=''))
        self.assertTrue(self.policy.ManifestValid(m))
        m.Entries.Insert(N(SiteId='overflow',SupplyId='',ItemClass=''))
        self.assertFalse(self.policy.ManifestValid(m))

    def test_candidate_policy_uses_native_capability_and_profile_not_item_names(self):
        env={'GetGame':lambda:N(IsServer=lambda:True),'GetCEApi':lambda:object()}
        item=N(IsInventoryItem=lambda:True,GetEconomyProfile=lambda:N(GetNominal=lambda:1),
               IsMan=lambda:False,IsAnimal=lambda:False,IsZombie=lambda:False)
        self.assertTrue(invoke('HCSearchNativeSupply.c','CandidateValid',env,N(),item))
        for inventory,profile in [(False,N(GetNominal=lambda:1)),(True,None),
                                  (True,N(GetNominal=lambda:0))]:
            item=N(IsInventoryItem=lambda:inventory,GetEconomyProfile=lambda:profile,
                   IsMan=lambda:False,IsAnimal=lambda:False,IsZombie=lambda:False)
            self.assertFalse(invoke('HCSearchNativeSupply.c','CandidateValid',env,N(),item))


if __name__=='__main__':
    unittest.main()
