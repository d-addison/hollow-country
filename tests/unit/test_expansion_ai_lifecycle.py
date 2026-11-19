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
        self.logs=[]
        self.env=dict(A=A,Print=self.logs.append,HCRefusal=N(CAPACITY='capacity'))
        declarations(self.env)
        self.env['HCXAIStore']=N(SaveJournal=self.save)
        self.env['HCXAIRules']=N(Token=lambda s:isinstance(s,str) and 0 < len(s) <= 128)
        self.journal=Authored((SCRIPTS/'HCXAIJournal.c').read_text(),self.env)
        self.owner=N(m_Data=self.env['HCXAIJournalData'](),m_Session='new-process',m_Limit=8,m_Refusal='')
        self.owner.m_Data.Rows=A()
        self.owner.m_Data.SchemaVersion=1
        for name in ('Valid','Reconcile','Begin','End','RefuseBegin','Refusal'):
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

    def full_journal(self):
        self.env['GetGame']=lambda:N(IsServer=lambda:True)
        for name in ('PrepareBegin','Prune'):
            setattr(self.owner,name,lambda *a,n=name:self.journal.call(n,self.owner,*a))
        self.owner.m_Limit=2
        tombstone=self.row(lease='tombstone',closed=True);tombstone.Prunable=False
        self.owner.m_Data.Rows=A([self.row(lease='open'),tombstone])

    def test_reconciled_orphans_make_prior_process_rows_prunable_so_the_cap_recycles(self):
        self.full_journal()
        self.assertTrue(self.owner.Reconcile(True))
        self.assertTrue(all(r.Closed and r.Prunable for r in self.saved[-1].Rows))
        for index in range(3):
            lease='fresh-'+str(index)
            self.assertTrue(self.owner.PrepareBegin(lease,'event','site'))
            self.assertTrue(self.owner.Begin(lease,'event','site'))
            self.assertTrue(self.owner.End(lease,True))
        self.assertEqual(['fresh-1','fresh-2'],[r.Id for r in self.owner.m_Data.Rows])

    def test_unreconciled_restart_keeps_prior_rows_unprunable_and_refuses_at_the_cap(self):
        self.full_journal()
        self.assertTrue(self.owner.Reconcile())
        self.assertTrue(all(r.Closed and not r.Prunable for r in self.saved[-1].Rows))
        self.assertFalse(self.owner.PrepareBegin('fresh','event','site'))

    def test_reconciled_orphans_leave_this_process_rows_alone(self):
        row=self.row(lease='current-fault',session='new-process',closed=True);row.Prunable=False
        self.owner.m_Data.Rows=A([row])
        self.assertTrue(self.owner.Reconcile(True))
        self.assertFalse(self.owner.m_Data.Rows[0].Prunable)
        self.owner.m_Data.Rows=A([self.row(lease='current-open',session='new-process')])
        self.assertFalse(self.owner.Reconcile(True))

    def test_open_passes_orphan_reconciliation_through(self):
        source=(SCRIPTS/'HCXAIJournal.c').read_text()
        self.assertIn('static HCXAIJournal Open(string worldSession, int limit, bool orphansReconciled = false)',source)
        self.assertIn('journal.Reconcile(orphansReconciled)',source)

    def test_end_is_idempotent_and_failed_reconciliation_cannot_claim_success(self):
        self.assertTrue(self.owner.Begin('one','event','site'))
        self.assertTrue(self.owner.End('one'));self.assertTrue(self.owner.End('one'))
        self.assertFalse(self.owner.End('unknown'))
        self.ok=False
        self.assertFalse(self.owner.Reconcile())



def v1_admission():
    """The shared HollowCountry V1 admission line, run from its authored body (read only)."""
    source = (ROOT / 'mods/HollowCountry/scripts/4_World/Core/HCV1Admission.c').read_text()
    code = Authored(source, {})
    return N(Line=lambda *a: code.call('Line', None, *a))


class MarkerTests(unittest.TestCase):
    def test_probe_is_server_only_cached_and_qualification_stays_closed(self):
        calls=[];server=[False];printed=[]
        env=dict(GetGame=lambda:N(IsServer=lambda:server[0]),
                 FileExist=lambda p:calls.append(p) or False,Print=printed.append)  # no .disable marker: on by default
        env['HCV1Admission']=v1_admission()
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
        self.assertEqual(['$profile:HollowCountry/acceptance/pve_patrols.disable'],calls)
        self.assertFalse(owner.Qualified())
        self.assertEqual(['[HollowCountry] V1 admission feature=PvePatrols preference=on gate=pve_patrols qualified=0'
                          ' result=admitted unverified: pve_patrols has no recorded native verdict;'
                          ' opt out with acceptance/pve_patrols.disable'], printed)

    def test_disable_marker_stays_closed_until_process_restart(self):
        calls=[];printed=[]
        env=dict(GetGame=lambda:N(IsServer=lambda:True),
                 FileExist=lambda path:calls.append(path) or True,Print=printed.append)  # the .disable marker is present
        env['HCV1Admission']=v1_admission()
        text=(SCRIPTS/'HCXAIQualification.c').read_text()
        code=Authored(text.replace('s_Probed','m_Probed').replace('s_OptIn','m_OptIn'),env)
        owner=N(m_Probed=False,m_OptIn=False)
        env['HCXAIQualification']=owner
        for name in ('Qualified','LocalAcceptanceOptIn','Admitted'):
            setattr(owner,name,lambda n=name:code.call(n,owner))
        self.assertFalse(owner.Admitted())
        env['FileExist']=lambda path:False  # removing the marker changes nothing until a restart
        self.assertFalse(owner.Admitted())
        self.assertEqual(1,len(calls))
        self.assertEqual(['[HollowCountry] V1 admission feature=PvePatrols preference=off gate=pve_patrols qualified=0'
                          ' result=off: operator opt-out acceptance/pve_patrols.disable'], printed)
