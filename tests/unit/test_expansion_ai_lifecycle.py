"""Behavior of authored journal/marker bodies; synthetic IO, no DayZ claims."""
import copy
from pathlib import Path
from types import SimpleNamespace as N
import unittest

from tests.unit.test_expansion_ai_adapter import A, Authored, declarations

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / 'mods/HollowCountryExpansionAI/scripts/4_World'


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.saved=[]
        self.ok=True
        self.env=dict(A=A,Print=lambda *a:None)
        declarations(self.env)
        self.env['HCXAIStore']=N(SaveJournal=self.save)
        self.env['HCXAIRules']=N(Token=lambda s:isinstance(s,str) and 0 < len(s) <= 128)
        self.journal=Authored((SCRIPTS/'HCXAIJournal.c').read_text(),self.env)
        self.owner=N(m_Data=self.env['HCXAIJournalData'](),m_Session='new-process',m_Limit=8)
        self.owner.m_Data.Rows=A()
        self.owner.m_Data.SchemaVersion=1
        for name in ('Valid','Reconcile','Begin','End'):
            setattr(self.owner,name,lambda *a,n=name:self.journal.call(n,self.owner,*a))

    def save(self,data):
        if self.ok:self.saved.append(copy.deepcopy(data))
        return self.ok

    def row(self,lease='old',session='prior-process',closed=False):
        return N(Id=lease,WorldSession=session,Session='event',MissionId='site',Closed=closed)

    def test_restart_closes_old_nonpersistent_intents_without_spawning_or_replaying(self):
        self.owner.m_Data.Rows=A([self.row()])
        self.assertTrue(self.owner.Reconcile())
        self.assertTrue(self.saved[-1].Rows[0].Closed)
        self.assertFalse(self.owner.Begin('old','event','site'))
        self.assertTrue(self.owner.Begin('fresh','event','site'))
        self.assertEqual(2,len(self.owner.m_Data.Rows))

    def test_same_process_open_intent_and_corrupt_journal_refuse_admission(self):
        self.owner.m_Data.Rows=A([self.row(session='new-process')])
        self.assertFalse(self.owner.Reconcile())
        self.owner.m_Data.Rows=A([self.row(),self.row()])
        self.assertFalse(self.owner.Reconcile())
        self.owner.m_Data.Rows=A([self.row()]);self.owner.m_Data.SchemaVersion=2
        self.assertFalse(self.owner.Reconcile())

    def test_uncertain_write_retains_identity_and_capacity(self):
        self.ok=False
        self.assertFalse(self.owner.Begin('uncertain','event','site'))
        self.assertFalse(self.owner.Begin('uncertain','event','site'))
        self.assertEqual(1,len(self.owner.m_Data.Rows))
        self.owner.m_Limit=1
        self.assertFalse(self.owner.Begin('other','event','site'))

    def test_end_is_idempotent_and_failed_reconciliation_cannot_claim_success(self):
        self.assertTrue(self.owner.Begin('one','event','site'))
        self.assertTrue(self.owner.End('one'));self.assertTrue(self.owner.End('one'))
        self.assertFalse(self.owner.End('unknown'))
        self.ok=False
        self.assertFalse(self.owner.Reconcile())


class MarkerTests(unittest.TestCase):
    def test_probe_is_server_only_cached_and_qualification_stays_closed(self):
        calls=[];server=[False]
        env=dict(GetGame=lambda:N(IsServer=lambda:server[0]),
                 FileExist=lambda p:calls.append(p) or True,Print=lambda *a:None)
        text=(SCRIPTS/'HCXAIQualification.c').read_text()
        # Explicit adaptation of static state to the same authored-body harness.
        code=Authored(text.replace('s_Probed','m_Probed').replace('s_OptIn','m_OptIn'),env)
        owner=N(m_Probed=False,m_OptIn=False)
        env['HCXAIQualification']=owner
        code.env=env
        for name in ('Qualified','LocalAcceptanceOptIn','Admitted'):
            setattr(owner,name,lambda n=name:code.call(n,owner))
        self.assertFalse(owner.Admitted());self.assertEqual([],calls)
        server[0]=True
        self.assertTrue(owner.Admitted());self.assertTrue(owner.Admitted())
        self.assertEqual(['$profile:HollowCountry/acceptance/pve_patrols.enable'],calls)
        self.assertFalse(owner.Qualified())

    def test_absent_marker_stays_closed_until_process_restart(self):
        calls=[]
        env=dict(GetGame=lambda:N(IsServer=lambda:True),
                 FileExist=lambda path:calls.append(path) or False,Print=lambda *a:None)
        text=(SCRIPTS/'HCXAIQualification.c').read_text()
        code=Authored(text.replace('s_Probed','m_Probed').replace('s_OptIn','m_OptIn'),env)
        owner=N(m_Probed=False,m_OptIn=False)
        env['HCXAIQualification']=owner
        for name in ('Qualified','LocalAcceptanceOptIn','Admitted'):
            setattr(owner,name,lambda n=name:code.call(n,owner))
        self.assertFalse(owner.Admitted())
        env['FileExist']=lambda path:True
        self.assertFalse(owner.Admitted())
        self.assertEqual(1,len(calls))
