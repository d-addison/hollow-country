"""HC-41/#147 spec -> plan -> task: borrow one observed native incident once.

Execute authored Enforce handlers through existing restricted translation ports.
All handles, CE receipts, disk images and party leases here are SYNTHETIC.
No offline result establishes CE ownership, cleanup, inventory or restart behavior.

TDD command: PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest test_hc_native_incidents -v
Actual RED: AssertionError: True is not false : reappearing incident poisoned durable history
Actual lifecycle RED: AssertionError: 'closed' != 'leased' : live wreck alone does not prove a live native incident
GREEN: Ran 1 test ... OK (synthetic policy execution only).

Round 2 (#147): replace obsolete mint/permanent-refusal expectations with
existing physical stock and shared live-provider ports. Preserve finite stock,
no-refill, same-handle, no-delete and admission assertions. All fixtures synthetic.
"""
import copy
import re
from pathlib import Path
from types import MethodType, SimpleNamespace as N
import unittest

from tests.legacy.test_group_server import EArray
from tests.legacy.test_map_layers import EStr, methods, translate

ROOT = Path(__file__).resolve().parents[2]
EVENTS = ROOT / 'mods/HollowCountry/scripts/4_World/Events'


def fixture(image=None, enabled=True, qualified=True):
    source = (EVENTS / 'HCNativeIncidentLease.c').read_text().replace('    protected ', '    ')
    # Syntax-only constructor substitution at the existing verified store port.
    source = source.replace('new HCEncounterStore<HCNativeIncidentState>("hc41-native-incidents")',
                            'new SyntheticStore()')
    source = re.sub(r'array<[^>]+>(?= \w+ =)', 'HCArray', source)
    source = source.replace('retained.ToString()', 'str(retained)')
    images, logs, calls = [], [], []
    disk = N(image=copy.deepcopy(image), fail=False)
    def save(state):
        calls.append('save')
        if disk.fail:
            return False
        disk.image = copy.deepcopy(state)
        images.append(copy.deepcopy(state))
        return True
    def load(fresh, collection):
        calls.append('load')
        return copy.deepcopy(disk.image) if disk.image else fresh
    anchor = N(pid=EStr('synthetic-wreck-1'), deleted=False)
    anchor.IsPendingDeletion = lambda: anchor.deleted
    item = N(pid=EStr('synthetic-item-1'), deleted=False, owner=None, parent=None)
    item.IsPendingDeletion = lambda: item.deleted
    item.IsRuined = lambda: False
    item.GetHierarchyRootPlayer = lambda: item.owner
    item.GetHierarchyParent = lambda: item.parent
    receipt = N(Anchor=anchor, Stock=EArray([item]))
    observed = N(receipt=receipt, present=True)
    native = N(HCReady=lambda: qualified, HCRefusal=lambda: EStr('CE_INCIDENT_LIFECYCLE_UNEXPOSED'),
               HCObserve=lambda: calls.append('observe') or observed.receipt,
               HCPresent=lambda a: observed.present and a is anchor,
               HCContains=lambda a, stock: observed.present and a is anchor and stock is item)
    env = dict(str=str, GetGame=lambda: N(IsServer=lambda: True), Print=logs.append,
        HCV2Admission=N(Admitted=lambda preference: preference),
        HCEventDirector=N(TextValid=lambda value, cap: bool(value) and len(value) <= cap),
        HCSearchSupplyRegistry=N(PersistentId=lambda handle: handle.pid if handle else EStr('')),
        HCWorldMaterializer=N(HCIdentity=lambda lease: N() if lease == 'synthetic-party-lease' else None),
        HCNativeIncidentState=lambda: N(Version=1, Rows=EArray()),
        HCNativeIncidentReceipt=lambda: N(Anchor=None, Stock=EArray()),
        HCNativeIncidentRow=lambda: N(Id=EStr(''), LeaseId=EStr(''), Phase=EStr('leased'),
                                     StockIds=EArray(), IssuedIds=EArray()),
        SyntheticStore=lambda: N(Load=load, Save=save),
        HCOperationalStatus=lambda: N(HCPublish=lambda *args: calls.append(args)))
    table, _ = methods(source, 'HCNativeIncidentLease')
    translate(source, 'HCNativeIncidentLease', env)
    budget = N(HCReset=lambda cap: None, HCTake=lambda cost: True, HCContinue=lambda: True)
    owner = N(m_Source=None, m_Store=None, m_State=None, m_Receipt=None, m_Active=None,
              m_Enabled=False, m_Fault=False, m_Opened=False, m_Busy=False,
              m_Effective=EStr('off'), m_Reason=EStr('not_started'), m_Reports=0,
              m_Units=budget, m_Work=budget)
    for name, (static, _, _) in table.items():
        setattr(owner, name, env[name] if static else MethodType(env[name], owner))
    owner.HCOpen(native, enabled)
    return N(owner=owner, native=native, observed=observed, anchor=anchor, item=item,
             receipt=receipt, images=images, logs=logs, calls=calls, disk=disk)


class NativeIncidentBehavior(unittest.TestCase):
    def test_one_lease_finite_native_stock_and_durable_disappearance_refusal(self):
        run = fixture()
        self.assertFalse(run.owner.HCBorrow('forged-party'))
        self.assertTrue(run.owner.HCBorrow('synthetic-party-lease'))
        self.assertFalse(run.owner.HCBorrow('synthetic-party-lease'), 'same incident leased twice')
        self.assertIsNone(run.owner.HCTakeStock('not-observed'))
        self.assertIs(run.item, run.owner.HCTakeStock(run.item.pid))
        self.assertEqual(['synthetic-item-1'], run.images[-1].Rows[0].IssuedIds)
        self.assertIsNone(run.owner.HCTakeStock(run.item.pid), 'no second stock issue/refill')
        run.owner.HCComplete()
        self.assertFalse(run.owner.HCBorrow('synthetic-party-lease'), 'completed wreck reappeared')
        self.assertFalse(run.owner.m_Fault, 'reappearing incident poisoned durable history')
        self.assertEqual(1, len(run.owner.m_State.Rows), 'duplicate lease intent appended')
        restarted = fixture(run.disk.image)
        self.assertFalse(restarted.owner.HCBorrow('synthetic-party-lease'))

        missing = fixture()
        self.assertTrue(missing.owner.HCBorrow('synthetic-party-lease'))
        missing.anchor.deleted = True
        missing.owner.HCStep()
        self.assertEqual('closed', missing.disk.image.Rows[0].Phase)
        missing.anchor.deleted = False
        self.assertFalse(missing.owner.HCBorrow('synthetic-party-lease'))
        self.assertTrue(any('NATIVE_INCIDENT_DISAPPEARED' in line for line in missing.logs))
        ended = fixture()
        self.assertTrue(ended.owner.HCBorrow('synthetic-party-lease'))
        ended.observed.present = False  # Native lifecycle ended; anchor still exists.
        ended.owner.HCStep()
        self.assertEqual('closed', ended.disk.image.Rows[0].Phase,
                         'live wreck alone does not prove a live native incident')
        overflow = fixture()
        overflow.receipt.Stock = EArray([overflow.item] * 17)
        self.assertFalse(overflow.owner.HCBorrow('synthetic-party-lease'))
        self.assertEqual([], overflow.images)
        duplicate = fixture()
        duplicate.receipt.Stock = EArray([duplicate.item, duplicate.item])
        self.assertFalse(duplicate.owner.HCBorrow('synthetic-party-lease'))
        self.assertEqual([], duplicate.images)
        full = fixture()
        full.owner.m_State.Rows = EArray(N(Id=EStr('synthetic-old-' + str(index)),
            LeaseId=EStr('synthetic-party-lease'), Phase=EStr('closed'),
            StockIds=EArray(), IssuedIds=EArray()) for index in range(64))
        self.assertFalse(full.owner.HCBorrow('synthetic-party-lease'))
        self.assertNotIn('observe', full.calls, 'full history refuses before provider work')
        invalid = fixture(N(Version=1, Rows=EArray([None])))
        self.assertFalse(invalid.owner.m_Enabled)
        self.assertTrue(invalid.owner.m_Fault)
        self.assertEqual([], invalid.images, 'corrupt state never overwritten')
        # Restart from an active intent quarantines observation; never rebind.
        crashed = fixture(run.images[0])
        self.assertEqual('closed', crashed.disk.image.Rows[0].Phase)
        self.assertFalse(crashed.owner.HCBorrow('synthetic-party-lease'))

        raced = fixture()
        self.assertTrue(raced.owner.HCBorrow('synthetic-party-lease'))
        raced.item.owner = N(synthetic_player=True)
        self.assertIsNone(raced.owner.HCTakeStock(raced.item.pid))
        self.assertIsNotNone(raced.item.owner, 'player stock remains untouched')
        # Same coordinates/classes with a different handle never substitute stock.
        raced.item.owner = None
        replacement = N(**vars(raced.item))
        raced.receipt.Stock = EArray([replacement])
        raced.item.deleted = True
        self.assertIsNone(raced.owner.HCTakeStock(replacement.pid))

        barrier = fixture()
        barrier.disk.fail = True
        self.assertFalse(barrier.owner.HCBorrow('synthetic-party-lease'))
        self.assertIsNone(barrier.owner.HCTakeStock(barrier.item.pid))
        self.assertTrue(barrier.owner.m_Fault)
        spend = fixture()
        spend.owner.HCBorrow('synthetic-party-lease')
        spend.disk.fail = True
        self.assertIsNone(spend.owner.HCTakeStock(spend.item.pid))
        self.assertTrue(spend.owner.m_Fault)
        stopped = fixture()
        stopped.owner.HCBorrow('synthetic-party-lease')
        stopped.owner.HCClose()
        count = len(stopped.calls)
        stopped.owner.HCStep()
        stopped.owner.HCClose()
        self.assertEqual(count, len(stopped.calls))
        self.assertIsNone(stopped.owner.m_Receipt)

        for enabled, qualified in ((False, True), (True, False)):
            refused = fixture(enabled=enabled, qualified=qualified)
            refused.owner.HCStep()
            self.assertFalse(refused.owner.HCBorrow('synthetic-party-lease'))
            self.assertEqual([], refused.calls, 'off/unsupported does no scan or disk work')
        # Shipping CE callback registry, synthetic native cargo and server ports.
        registry = N(s_Crashes=EArray(), s_AdmissionPrinted=False,
                     s_StockPendingPrinted=False, s_Cursor=0)
        env = dict(FileExist=lambda path: False, GetGame=lambda: N(IsServer=lambda: True),
                   HCW38SituationPolicy=N(HCGet=lambda: N(MaxIncidents=64, MaxIncidentItems=16)),
                   HCV2Admission=N(Line=lambda *args: 'synthetic admission runtime=PENDING'),
                   Print=lambda line: None, registry=registry, CrashBase=N(Cast=lambda value: value))
        source = (EVENTS/'HCNativeIncidentLease.c').read_text()
        for field in vars(registry):
            source = source.replace(field, 'registry.' + field)
        translate(source, 'HCNativeIncidentSource', env)
        provider = N()
        for name in ('HCReady', 'HCRefusal', 'HCObserve', 'HCPresent', 'HCContains'):
            setattr(provider, name, MethodType(env[name], provider))
        self.assertTrue(provider.HCReady())
        self.assertIsNone(provider.HCObserve(), 'admitted callback source invents no incident')
        anchor = N(IsPendingDeletion=lambda: False)
        self.assertFalse(provider.HCPresent(anchor), 'unregistered anchor is not CE provenance')
        env['HCRegister'](anchor)
        self.assertTrue(provider.HCPresent(anchor))
        item = N(IsPendingDeletion=lambda: False, IsRuined=lambda: False,
                 GetHierarchyRootPlayer=lambda: None, GetHierarchyParent=lambda: anchor)
        self.assertTrue(provider.HCContains(anchor, item))
        item.GetHierarchyParent = lambda: None
        self.assertFalse(provider.HCContains(anchor, item), 'nearby loose loot is never attributed')
        env['HCRemove'](anchor)
        self.assertFalse(provider.HCPresent(anchor))
        self.assertEqual('CE_CRASH_CALLBACK_PENDING', provider.HCRefusal())
        env['HCNativeIncidentSource'] = lambda: provider
        translate((EVENTS/'HCEventNativeObserver.c').read_text(), 'HCEventNativeObserver', env,
                  only=('HCIncidentSource',))
        observer = N(HCIncidentSource=lambda: env['HCIncidentSource'](N()))
        translate((EVENTS/'HCEventWorldBinding.c').read_text(), 'HCEventWorldBinding', env,
                  only=('BindNativeIncident',))
        integration = fixture(enabled=False)
        integration.owner.m_Opened = False
        self.assertTrue(env['BindNativeIncident'](integration.owner, observer, True))
        self.assertEqual(['load'], integration.calls)
        self.assertTrue(any('HC-41 native_incident=synthetic-wreck-1 lease=leased stock_owner=native' in line
                            and 'runtime=PENDING' in line for line in run.logs))


if __name__ == '__main__':
    unittest.main()
