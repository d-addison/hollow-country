"""Authored native transfer port with explicit fake engine entities/locations."""
import unittest
from types import SimpleNamespace as N

from tests.unit.test_group_server import EArray
from tests.unit.test_search_economy import invoke


class Location:
    def __init__(self):self.parent=None;self.signature=None;self.item=None
    def IsValid(self):return self.signature is not None
    def GetParent(self):return self.parent
    def GetType(self):return 0 if self.parent is None else 2
    def CompareLocationOnly(self,other):return self.signature==other.signature


class SearchNativeTests(unittest.TestCase):
    def setUp(self):
        self.calls=[];self.native_result=True;self.move=True;self.change_quantity=False
        self.actor=N(IsAlive=lambda:True,IsUnconscious=lambda:False,GetPosition=lambda:[0,0,0])
        self.actor.GetIdentity=lambda:N(GetId=lambda:'actor',GetPlayer=lambda:self.actor)
        self.actor.GetInventory=lambda:N(FindFreeLocationFor=self.destination,TakeToDst=self.take)
        self.port=N(m_Opened=True,m_Sealed=False,m_Transferring=False,m_RetirePending=False,m_Owner=None,m_Entries=EArray())
        self.env={'str':str,'GetGame':lambda:N(IsServer=lambda:True),'GetCEApi':lambda:object(),
                  'InventoryLocation':Location,'InventoryLocationType':N(GROUND=0,CARGO=2),
                  'FindInventoryLocationType':N(CARGO=2),'InventoryMode':N(SERVER=1),
                  's_Registered':EArray(),'HCSearchRules':N(TextValid=lambda s,n:bool(s) and len(s)<=n),
                  'HCSearchOwnedSupply':lambda:N(Attempted=False),
                  'vector':N(DistanceSq=lambda a,b:sum((x-y)**2 for x,y in zip(a,b))),
                  'Print':self.calls.append}
        self.env['HCSearchSupplyRegistry']=N(PersistentId=lambda item:self.call('PersistentId',item))
        for name in ('Find','Unchanged','CandidateValid','CanTransfer'):
            setattr(self.port,name,lambda *a,n=name:self.call(n,*a))
        # invoke() rewrites only its fixed method list to self.X; the authored split of
        # Transfer/CanTransfer into guarded wrappers + Preflight/Move is bound as globals.
        for name in ('Move','Preflight','Retire','Owning'):
            self.env[name]=lambda *a,n=name:self.call(n,*a)
        self.item=self.item_fixture((1,2,3,4))
        self.assertTrue(self.call('RegisterOwned',self.item,'record_a'))
        self.entry=N(SupplyId='1_2_3_4',ItemClass='SyntheticClass')

    def call(self,name,*args):
        return invoke('HCSearchNativeSupply.c',name,self.env,self.port,*args)

    def item_fixture(self,pid):
        item=N(parent=None,quantity=5.,position=[1,0,0],
               GetPersistentID=lambda:pid,GetType=lambda:'SyntheticClass',
               IsInventoryItem=lambda:True,IsMan=lambda:False,IsAnimal=lambda:False,IsZombie=lambda:False,
               IsTakeable=lambda:True,GetEconomyProfile=lambda:N(GetNominal=lambda:1))
        item.GetQuantity=lambda:item.quantity
        item.GetPosition=lambda:item.position
        item.GetHierarchyRootPlayer=lambda:item.parent
        def current(location):
            location.item=item;location.parent=item.parent
            location.signature=(id(item.parent),tuple(item.position))
            return True
        item.GetInventory=lambda:N(GetCurrentInventoryLocation=current)
        return item

    def destination(self,item,flags,location):
        location.parent=self.actor;location.item=item;location.signature=('destination',)
        return True

    def take(self,mode,source,destination):
        self.calls.append('move')
        self.assertEqual(1,mode)
        if self.move:source.item.parent=self.actor
        if self.change_quantity:source.item.quantity+=1
        return self.native_result

    def test_source_transfer_preserves_same_entity_quantity_and_refuses_replay(self):
        self.assertEqual(2,self.call('Transfer',self.entry,self.actor))
        self.assertIs(self.actor,self.item.parent)
        self.assertEqual(5.,self.item.quantity)
        self.assertEqual(4,self.call('Transfer',self.entry,self.actor))
        self.assertEqual(['move'],self.calls)

    def test_native_false_unchanged_source_is_retained_not_refunded_or_retried(self):
        self.native_result=False;self.move=False
        self.assertEqual(4,self.call('Transfer',self.entry,self.actor))
        self.assertIsNone(self.item.parent)
        self.assertEqual(5.,self.item.quantity)
        self.assertEqual(4,self.call('Transfer',self.entry,self.actor))
        self.assertEqual(['move'],self.calls)

    def test_false_but_moved_or_changed_quantity_is_uncertain_and_never_compensated(self):
        for event in ('false_moved','quantity'):
            with self.subTest(event=event):
                self.setUp()
                if event=='false_moved':self.native_result=False
                else:self.change_quantity=True
                self.assertEqual(3,self.call('Transfer',self.entry,self.actor))
                self.assertIs(self.actor,self.item.parent)
                self.assertEqual(1,self.calls.count('move'))
                self.assertEqual(4,self.call('Transfer',self.entry,self.actor))

    def test_external_movement_or_quantity_change_never_acquires_player_loot(self):
        for event in ('position','quantity','player'):
            with self.subTest(event=event):
                self.setUp()
                if event=='position':self.item.position=[1.1,0,0]
                if event=='quantity':self.item.quantity=4.
                if event=='player':self.item.parent=N()
                self.assertFalse(self.call('CanTransfer',self.entry,self.actor))
                self.assertNotIn('move',self.calls)

    def test_zero_persistent_id_and_duplicate_handle_or_provenance_record_are_rejected(self):
        self.assertFalse(self.call('RegisterOwned',self.item,'different_record'))
        self.assertFalse(self.call('RegisterOwned',self.item_fixture((0,0,0,0)),'record_b'))
        self.assertFalse(self.call('RegisterOwned',self.item_fixture((5,6,7,8)),'record_a'))

    def test_native_capacity_callback_cannot_invalidate_actor_or_source_then_move(self):
        for change in ('death','quantity','identity'):
            with self.subTest(change=change):
                self.setUp();count=[]
                def destination(item,flags,location):
                    count.append(1)
                    if len(count)==2:
                        if change=='death':self.actor.IsAlive=lambda:False
                        if change=='quantity':self.item.quantity=4.
                        if change=='identity':self.actor.GetIdentity=lambda:N(GetPlayer=lambda:self.actor,GetId=lambda:'other')
                    return self.destination(item,flags,location)
                self.actor.GetInventory=lambda:N(FindFreeLocationFor=destination,TakeToDst=self.take)
                self.assertEqual(4,self.call('Transfer',self.entry,self.actor))
                self.assertNotIn('move',self.calls)


if __name__=='__main__':
    unittest.main()
