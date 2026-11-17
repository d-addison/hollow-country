"""Authored Enforce bodies with explicit synthetic engine/provider scaffolding."""
import copy
import json
from pathlib import Path
import re
from types import SimpleNamespace as N
import unittest

ROOT = Path(__file__).resolve().parents[2]
ADDON = ROOT / "mods/HollowCountryExpansionAI"
SCRIPTS = ADDON / "scripts"
PIN = "d84d3c73694969eba2f969e9178a1914e2f1b31d"
NATIVE = "09012cdae8c4ae2d478ca90f3e2e3f01e435f0f6945a63b7cae290e3ccdea28a"


class A(list):
    def __bool__(self): return True
    def Count(self): return len(self)
    def Insert(self, x): self.append(x)
    def RemoveOrdered(self, i): self.pop(i)
    def Find(self, x): return self.index(x) if x in self else -1
    def Clear(self): self.clear()


def block(text, start):
    depth, end = 1, start
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[start:end - 1]


class Authored:
    """Syntax adaptation only; all admission/lifecycle decisions stay in C."""
    def __init__(self, source, env):
        self.source, self.env, self.cache = source, env, {}

    def call(self, name, owner, *args):
        if name not in self.cache:
            literals = {}
            def literal(m):
                key = "LITERAL_" + str(len(literals))
                literals[key] = json.loads(m[0])
                return key
            source = re.sub(r'"(?:[^"\\]|\\.)*"', literal, self.source)
            source = re.sub(r"//[^\n]*", "", source)
            found = re.search(r"\b[\w<>]+\s+" + name + r"\(([^)]*)\)\s*\{", source)
            if not found:
                raise AssertionError("missing authored method " + name)
            body = block(source, found.end())
            params = []
            for param in found[1].split(","):
                if not param.strip(): continue
                parts = param.split("=", 1)
                adapted = parts[0].split()[-1]
                if len(parts) == 2:
                    adapted += "=" + parts[1].strip().replace("false", "False").replace("true", "True")
                params.append(adapted)
            lines, indent = ["def run(self, " + ", ".join(params) + "):"], 1
            for token in re.split(r"([{};])", body):
                token = token.strip()
                if not token or token == ";": continue
                if token == "{": indent += 1; continue
                if token == "}": indent -= 1; continue
                token = re.sub(r"new array<[^;()]+>\(\)", "A()", token)
                token = re.sub(r"new (\w+)\(\)", r"\1()", token)
                types = r"(?:bool|int|float|string|vector|Object|EntityAI|PlayerBase|Magazine|eAIBase|eAIGroup|eAIFaction|ExpansionAISettings|HCObserverTransition\w+|HCXAI\w+|HCEventObjectiveEvidence)"
                bare = re.fullmatch(types + r" (\w+)", token)
                if bare: token = bare[1] + " = None"
                token = re.sub(r"\b" + types + r"\s+(?=\w+\s*=)", "", token)
                token = re.sub(r"(?<![.\w])m_\w+\b", lambda m: "self." + m[0], token)
                token = token.replace("this.", "self.")
                token = token.replace("&&", " and ").replace("||", " or ")
                token = re.sub(r"!(?!=)", "not ", token)
                for a, b in (("true", "True"), ("false", "False"), ("null", "None")):
                    token = re.sub(r"\b" + a + r"\b", b, token)
                if token.startswith(("if (", "while (")):
                    a, b = token.split(" (", 1)
                    token = a + " " + b[:-1] + ":"
                elif token.startswith("else if ("): token = "elif " + token[9:-1] + ":"
                elif token == "else": token = "else:"
                elif token.startswith("foreach ("):
                    loop = re.fullmatch(r"foreach \([\w<>]+ (\w+) : (.+)\)", token)
                    token = "for " + loop[1] + " in " + loop[2] + ":"
                token = re.sub(r"([\w.]+)\+\+$", r"\1 += 1", token)
                token = re.sub(r"([\w.]+)--$", r"\1 -= 1", token)
                token = re.sub(r"([\w.]+)\.Length\(\)", r"len(\1)", token)
                token = re.sub(r"([\w.]+)\.Substring\(([^,]+), ([^)]+)\)", r"\1[\2:\2+\3]", token)
                token = re.sub(r"([\w.]+)\.ToString\(\)", r"str(\1)", token)
                token = re.sub(r"([\w.]+)\.Contains\(([^)]+)\)", r"(\2 in \1)", token)
                lines.append("    " * indent + token)
            scope = dict(self.env, **literals)
            exec(compile("\n".join(lines), "authored-expansion:" + name, "exec"), scope)
            self.cache[name] = scope["run"]
        return self.cache[name](owner, *args)


def declarations(env):
    text = (SCRIPTS / "4_World/HCXAIData.c").read_text()
    for match in re.finditer(r"class (HCXAI\w+)\s*\{", text):
        fields = re.findall(r"^\s*(?:ref )?([\w<> ]+?) (\w+)(?: = ([^;]+))?;",
                            block(text, match.end()), re.M)
        def make(fields=fields):
            result = N()
            for typ, key, raw in fields:
                if typ.startswith("array<"): value = A()
                elif raw and raw.startswith("new "):
                    value = env[raw.split()[1].split("(")[0]]()
                elif typ == "vector": value = (0., 0., 0.)
                elif raw: value = json.loads(raw)
                else: value = dict(bool=False, int=0, float=0., string="").get(typ)
                setattr(result, key, value)
            return result
        env[match[1]] = make


class ExpansionAdapterTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.now = 1000
        self.observer_code = 3  # Explicit synthetic observer dependency result.
        self.journal_ok = True
        self.marker = True
        self.reconciled = True
        self.created = []
        self.pending_factory = []
        self.env = dict(A=A, HCObserverTransitionState=lambda: N(), HCObserverTransitionPolicy=lambda:N(),
                        HCObserverTransitionGate=N(
                            ValidPolicy=lambda p: p is not None,
                            Configure=lambda s,p: True,
                            Evaluate=lambda s,i,n: self.observer_code),
                        HCEventObjectiveEvidence=lambda: N(),
                        HCXAIStore=N(Freeze=lambda p: copy.deepcopy(p), NativeBuild=lambda:"1.30.164289"))
        declarations(self.env)
        self.rule_source = (SCRIPTS / "4_World/HCXAIRules.c").read_text()
        self.runtime_source = (SCRIPTS / "4_World/HCXAIAdapter.c").read_text()
        self.rules = Authored(self.rule_source, self.env)
        self.rule_api = N()
        for name in re.findall(r"static \w+ (\w+)\(", self.rule_source):
            setattr(self.rule_api, name, lambda *a,n=name: self.rules.call(n,None,*a))
        self.env["HCXAIRules"] = self.rule_api
        self.env["HCXAIQualification"] = N(Admitted=lambda:self.marker)
        self.env["HCXAIJournal"] = N(Open=lambda *a:N(Begin=lambda *a:self.journal_ok,
                                                       End=lambda *a:self.journal_ok) if self.reconciled else None)
        self.global_ai = N(s_eAI_UnlimitedReload=0,s_eAI_UnlimitedReloadAll=0)
        self.settings = N(EnableFlankingOutsideCombat=False,DamageMultiplier=1.,
                          DamageReceivedMultiplier=1.,CanRecruitFriendly=False,CanRecruitGuards=False)
        self.env.update(eAIBase=self.global_ai,
                        GetExpansionSettings=lambda:N(GetAI=lambda:self.settings),
                        ECE_CREATEPHYSICS=1,ECE_KEEPHEIGHT=2,ECE_NOSURFACEALIGN=4,
                        eAIWaypointBehavior=N(HALT=0,LOOP=1),
                        eAIFaction=N(Create=lambda name:self.faction),
                        eAIGroup=N(CreateGroup=lambda f:self.group()),
                        Print=lambda text:self.calls.append(("diagnostic",text)))
        self.faction=N(IsInvincible=lambda:False,IsObserver=lambda:False,
                       IsPassive=lambda:False,HasUnlimitedStamina=lambda:False,
                       GetMeleeDamageMultiplier=lambda:1.,GetMeleeYeetForce=lambda:0.)
        self.game=N(IsServer=lambda:True,GetTime=lambda:self.now,
                    GetWorldName=lambda:"chernarusplus",
                    CreateObjectEx=self.factory,ConfigIsExisting=lambda p:True)
        self.env["GetGame"]=lambda:self.game
        self.global_ai.Cast=lambda x:x if getattr(x,"native_ai",False) else None
        self.env["EntityAI"]=N(Cast=lambda x:x)
        self.env["PlayerBase"]=N(Cast=lambda x:x)
        self.env["Magazine"]=N(Cast=lambda x:x if getattr(x,"magazine",False) else None)
        self.profile=self.env["HCXAIProfile"]()
        vars(self.profile).update(
            WorldName="chernarusplus",WorldSession="synthetic-world-session",
            BuildVersion="1.30.164289",NativeScriptsSha256=NATIVE,SourceCommit=PIN,
            WorldSha256="a"*64,ArtifactSha256="b"*64,DependencyInventorySha256="c"*64,
            MaxGroups=2,MaxActors=4,MaxItems=16,MaxTickWork=2,MaxLeaseHistory=8,
            MaxObservationAgeMs=100,MaxLeaseMs=10000,CoordinateBound=20000.,
            ObserverPolicy=N(Revision=1))
        self.route=self.env["HCXAIMission"]()
        vars(self.route).update(MissionId="mission-site-5",SiteId="mission-site",GroupSize=2,ActorClass="eAI_SurvivorM_Mirek",
                                FactionName="Raiders",Anchor=(100.,0.,100.),
                                SurveySha256="d"*64,LoadoutSha256="e"*64)
        self.route.Spawns=A([(100.,0.,100.),(101.,0.,100.)])
        self.route.Waypoints=A([(110.,0.,110.),(120.,0.,120.)])
        self.item=self.env["HCXAIEquipment"]()
        vars(self.item).update(ClassName="Mosin9130",InHands=True)
        self.route.Equipment=A([self.item])
        self.profile.Missions=A([self.route])
        self.receipt=self.env["HCXAIAdmission"]()
        for key in ("WorldName","WorldSession","BuildVersion","NativeScriptsSha256",
                    "SourceCommit","WorldSha256","ArtifactSha256","DependencyInventorySha256"):
            setattr(self.receipt,key,getattr(self.profile,key))
        vars(self.receipt).update(
            Sequence=1,ObservedAtMs=1000,ArtifactBytesVerified=True,DependencyClosureVerified=True,
            ObserverProviderQualified=True,RoutesQualified=True,InventoryLedgerQualified=True,
            OwnershipReconciled=True)
        self.hooks=N(
            Admission=lambda session:copy.deepcopy(self.receipt),
            RouteQualified=lambda survey,loadout:True,
            BeginLease=lambda *a:self.journal_ok,
            MemberCreated=lambda *a:self.journal_ok,
            MemberGone=lambda *a:self.journal_ok,
            EndLease=lambda *a:self.journal_ok,
            Observers=lambda *a:N())
        self.engine=Authored(self.runtime_source,self.env)
        self.mod=N(m_Profile=None,m_Hooks=None,m_Accepting=False,m_Starting=False,m_Status="uninitialized",
                   m_Leases=A(),m_ReservedActors=0,m_ReservedItems=0,m_ReservedGroups=0,
                   m_Cursor=0,m_LastNow=-1,m_Build="1.30.164289",
                   m_LastReceiptSequence=0,m_LastReceiptAt=-1)
        for name in re.findall(r"(?:override )?\b\w+ (\w+)\([^)]*\)\s*\{",self.runtime_source):
            setattr(self.mod,name,lambda *a,n=name:self.engine.call(n,self.mod,*a))

    def group(self):
        members=A(); waypoints=A()
        group=N(members=members,waypoints=waypoints,mode=0,m_Leave=False,
                Count=lambda:len(members),IsInCombat=lambda:False,
                AddWaypoint=lambda p:waypoints.append(p))
        group.SetWaypointBehaviour=lambda x:setattr(group,"mode",x)
        group.Delete=lambda:self.calls.append(("group-delete",))
        return group

    def factory(self, typ, pos, flags):
        self.calls.append(("create",typ,pos,flags))
        actor=self.pending_factory.pop(0) if self.pending_factory else self.actor()
        if actor is not None:self.created.append(actor)
        return actor

    def actor(self):
        actor=N(native_ai=True,alive=True,group=None,items=A(),deleted=False)
        actor.GetGroup=lambda:actor.group
        actor.SetGroup=lambda g:(setattr(actor,"group",g),g.members.append(actor))
        actor.IsAlive=lambda:actor.alive
        actor.GetPosition=lambda:(100.,0.,100.)
        actor.GetIdentity=lambda:None
        actor.GetAllowDamage=lambda:True
        actor.HCXAI_Fair=lambda:True
        actor.HCXAI_Own=lambda:None
        actor.eAI_SetUnlimitedReload=lambda x:self.calls.append(("reload",x))
        actor.eAI_SetDamageMultiplier=lambda x:self.calls.append(("damage-out",x))
        actor.eAI_SetDamageReceivedMultiplier=lambda x:self.calls.append(("damage-in",x))
        actor.eAI_SetEnableFlankingOutsideCombat=lambda x:self.calls.append(("flank",x))
        actor.eAI_SetLootingBehavior=lambda x:self.calls.append(("looting",x))
        def item(typ):
            obj=N(magazine=False)
            actor.items.append(obj)
            return obj
        actor.GetInventory=lambda:N(CreateInInventory=item)
        actor.GetHumanInventory=lambda:N(CreateInHands=item)
        actor.Delete=lambda:self.calls.append(("delete",actor))
        return actor

    def install(self):
        return self.mod.Install(self.profile,self.hooks)

    def start(self,lease="lease",session="event-session",cap=4):
        return self.mod.StartLease(lease,session,"mission-site-5",(100.,0.,100.),cap)

    def step(self,index=0):
        self.mod.StepLease(self.mod.m_Leases[index],self.now)

    def use_authored_journal(self, rows=()):
        """Explicit synthetic durable store, executing the real journal bodies."""
        self.disk = self.env["HCXAIJournalData"]()
        self.disk.Rows = A(copy.deepcopy(rows))
        self.saves = []
        def save(data):
            self.saves.append(copy.deepcopy(data))
            if self.journal_ok:
                self.disk = copy.deepcopy(data)
            return self.journal_ok
        self.env["HCXAIStore"].LoadJournal = lambda: copy.deepcopy(self.disk)
        self.env["HCXAIStore"].SaveJournal = save
        source = (SCRIPTS / "4_World/HCXAIJournal.c").read_text()
        engine = Authored(source, self.env)
        def journal():
            owner = N()
            for name in re.findall(r"\b\w+ (\w+)\([^)]*\)\s*\{", source):
                setattr(owner, name, lambda *a,n=name: engine.call(n, owner, *a))
            return owner
        self.env["HCXAIJournal"] = journal
        self.env["HCXAIJournal"].Open = lambda *a: engine.call("Open", None, *a)

    def journal_row(self, lease, closed=False, prunable=False, world=None):
        row = self.env["HCXAIJournalRow"]()
        vars(row).update(Id=lease, WorldSession=world or self.profile.WorldSession,
                         Session="event-session", MissionId=self.route.MissionId,
                         Closed=closed, Prunable=prunable)
        return row

    def retire(self, lease):
        """Only the deletion callback/pointer clearing are synthetic engine input."""
        self.mod.StopLease(lease.Id)
        for slot in lease.Slots:
            if slot.Handle:
                self.mod.RecordDelete(slot.Handle)
                slot.Handle = None
        for _ in lease.Slots:
            self.mod.StepLease(lease, self.now)

    def test_history_recycles_clean_retirements_past_cap_without_entity_work(self):
        self.profile.MaxLeaseHistory = 2
        self.use_authored_journal()
        self.assertTrue(self.install())
        for index in range(6):
            self.assertTrue(self.start(lease="clean-" + str(index)))
            lease = self.mod.m_Leases[-1]
            self.mod.StepLease(lease, self.now)
            self.mod.StepLease(lease, self.now)
            self.retire(lease)
            self.assertTrue(lease.Released)
        self.assertEqual(["clean-4", "clean-5"], [l.Id for l in self.mod.m_Leases])
        self.assertEqual(["clean-4", "clean-5"], [r.Id for r in self.disk.Rows])
        self.assertTrue(all(r.Closed and r.Prunable for r in self.disk.Rows))
        self.assertEqual(0, self.mod.m_ReservedActors)
        before = list(self.calls)
        self.assertTrue(self.start(lease="next"))
        self.assertEqual(before, self.calls)  # Admission pruning does no entity work.
        self.assertEqual(["clean-5", "next"], [r.Id for r in self.disk.Rows])

    def test_pruning_skips_open_retiring_ambiguous_and_faulted_leases(self):
        self.profile.MaxLeaseHistory = 5
        self.use_authored_journal()
        self.assertTrue(self.install())
        for name in ("open", "retiring", "ambiguous", "faulted", "clean"):
            self.assertTrue(self.start(lease=name))
            lease = self.mod.m_Leases[-1]
            if name == "clean":
                self.retire(lease)
            elif name == "faulted":
                lease.Failed = True
                self.retire(lease)
            else:
                # Explicit synthetic budget to isolate history eligibility.
                self.mod.m_ReservedGroups = 0
                self.mod.m_ReservedActors = 0
                self.mod.m_ReservedItems = 0
                if name != "open":
                    self.mod.StopLease(name)
                if name == "ambiguous":
                    lease.Slots[0].Attempted = True  # No deletion evidence.
        self.assertTrue(self.start(lease="fresh"))
        expected = ["open", "retiring", "ambiguous", "faulted", "fresh"]
        self.assertEqual(expected, [l.Id for l in self.mod.m_Leases])
        self.assertEqual(expected, [r.Id for r in self.disk.Rows])
        before = copy.deepcopy(self.disk)
        self.assertFalse(self.start(lease="blocked"))
        self.assertEqual(vars(before), vars(self.disk))
        self.assertEqual([], self.created)

    def test_unconfirmed_receipt_closure_is_not_prunable(self):
        self.profile.MaxLeaseHistory = 1
        self.profile.MaxGroups = 1
        self.use_authored_journal()
        self.assertTrue(self.install()); self.assertTrue(self.start())
        lease = self.mod.m_Leases[0]
        self.hooks.EndLease = lambda *a: False
        self.retire(lease)
        self.assertFalse(lease.Released)
        self.assertFalse(self.disk.Rows[0].Prunable)
        self.assertFalse(self.start(lease="blocked"))
        self.hooks.EndLease = lambda *a: True
        self.retire(lease)
        self.assertTrue(self.start(lease="fresh"))

    def test_restart_at_cap_prunes_only_oldest_explicitly_confirmed_row(self):
        self.profile.MaxLeaseHistory = 4
        rows = [self.journal_row("prior-open", world="prior-process"),
                self.journal_row("legacy-closed", closed=True),
                self.journal_row("oldest-clean", closed=True, prunable=True),
                self.journal_row("newest-clean", closed=True, prunable=True)]
        self.use_authored_journal(rows)
        self.assertTrue(self.install()); self.assertTrue(self.start(lease="fresh"))
        self.assertEqual(["prior-open", "legacy-closed", "newest-clean", "fresh"],
                         [r.Id for r in self.disk.Rows])
        self.assertTrue(self.disk.Rows[0].Closed)
        self.assertFalse(self.disk.Rows[0].Prunable)
        self.assertEqual([], self.created)

    def test_journal_prune_persists_shrink_and_failed_write_retains_runtime_history(self):
        self.profile.MaxLeaseHistory = 1
        self.profile.MaxGroups = 1
        self.use_authored_journal()
        self.assertTrue(self.install()); self.assertTrue(self.start())
        lease = self.mod.m_Leases[0]
        self.retire(lease)
        self.journal_ok = False
        self.assertFalse(self.start(lease="fresh"))
        self.assertEqual(["lease"], [l.Id for l in self.mod.m_Leases])
        self.assertEqual(["lease"], [r.Id for r in self.disk.Rows])
        self.journal_ok = True
        self.assertTrue(self.start(lease="fresh"))
        self.assertIn([], [[r.Id for r in data.Rows] for data in self.saves])
        self.assertEqual(["fresh"], [r.Id for r in self.disk.Rows])

    def test_released_flag_alone_cannot_discard_ambiguous_actors(self):
        self.profile.MaxLeaseHistory = 1
        self.profile.MaxGroups = 1
        self.use_authored_journal()
        self.assertTrue(self.install()); self.assertTrue(self.start())
        lease = self.mod.m_Leases[0]
        self.retire(lease)
        lease.Slots[0].Handle = self.actor()  # Inconsistent synthetic evidence.
        self.assertFalse(self.start(lease="blocked"))
        self.assertEqual(["lease"], [r.Id for r in self.disk.Rows])
        self.assertEqual([], self.created)

    def test_restart_with_retained_fault_can_recycle_more_than_runtime_cap(self):
        self.profile.MaxLeaseHistory = 2
        self.use_authored_journal([self.journal_row("fault", closed=True),
                                   self.journal_row("old-clean", True, True)])
        self.assertTrue(self.install())
        for index in range(6):
            self.assertTrue(self.start(lease="new-" + str(index)))
            self.retire(self.mod.m_Leases[-1])
            self.assertEqual(["fault", "new-" + str(index)],
                             [r.Id for r in self.disk.Rows])
            self.assertLessEqual(len(self.mod.m_Leases), 2)

    def test_restart_at_hard_cap_is_bounded_and_duplicate_checks_precede_pruning(self):
        self.profile.MaxLeaseHistory = 64
        rows = [self.journal_row("old-" + str(i), True, True) for i in range(64)]
        self.use_authored_journal(rows)
        self.assertTrue(self.install())
        self.assertFalse(self.start(lease="old-0"))
        self.assertEqual(64, len(self.disk.Rows))
        self.assertTrue(self.start(lease="fresh"))
        self.assertEqual(["old-" + str(i) for i in range(1, 64)] + ["fresh"],
                         [r.Id for r in self.disk.Rows])

    def test_reconciliation_does_not_make_old_open_intents_prunable(self):
        self.profile.MaxLeaseHistory = 2
        self.use_authored_journal([self.journal_row("open-" + str(i), world="old-process")
                                   for i in range(2)])
        self.assertTrue(self.install())
        self.assertTrue(all(r.Closed and not r.Prunable for r in self.disk.Rows))
        for index in range(4):
            self.assertFalse(self.start(lease="blocked-" + str(index)))
        self.assertEqual(["open-0", "open-1"], [r.Id for r in self.disk.Rows])
        self.assertLessEqual(len(self.mod.m_Leases), 2)
        self.assertEqual([], self.created)

    def test_restart_cannot_promote_inconsistent_open_pruning_markers(self):
        self.profile.MaxLeaseHistory = 2
        rows = [self.journal_row("open-" + str(i), prunable=True, world="old-process")
                for i in range(2)]
        self.use_authored_journal(rows)
        self.assertTrue(self.install())
        self.assertFalse(self.start(lease="blocked"))
        self.assertTrue(all(r.Closed and not r.Prunable for r in self.disk.Rows))

    def test_marker_does_not_bypass_version_fairness_or_restart_reconciliation(self):
        self.marker=False
        self.assertFalse(self.install())
        self.marker=True;self.reconciled=False
        self.assertFalse(self.install())
        self.reconciled=True
        self.profile.ProviderVersion="different"
        self.assertFalse(self.install())

    def test_marker_does_not_bypass_installed_patch_version_or_receipt(self):
        for mutate in (lambda:setattr(self.profile,'ProviderVersion','1.9.85'),
                       lambda:setattr(self.game,'ConfigIsExisting',lambda path:False),
                       lambda:setattr(self.receipt,'ArtifactBytesVerified',False)):
            self.setUp();mutate()
            self.assertFalse(self.install())
            self.assertFalse(self.mod.Ready('chernarusplus'))
            self.assertEqual([],self.created)

    def test_both_global_reload_masks_refuse_admission(self):
        for field in ("s_eAI_UnlimitedReload", "s_eAI_UnlimitedReloadAll"):
            setattr(self.global_ai,field,1)
            self.assertFalse(self.mod.NativeGlobalsFair())
            setattr(self.global_ai,field,0)
        self.assertTrue(self.mod.NativeGlobalsFair())

    def test_timeout_retires_only_after_unobserved_gate(self):
        self.install();self.start();self.step();self.step()
        self.now += self.profile.MaxLeaseMs
        self.receipt.ObservedAtMs=self.now;self.receipt.Sequence+=1
        self.observer_code=2;self.step()
        self.assertTrue(self.mod.m_Leases[0].Retiring)
        self.assertFalse([c for c in self.calls if c[0]=="delete"])
        self.observer_code=3;self.step()
        self.assertEqual(1,len([c for c in self.calls if c[0]=="delete"]))

    def test_owned_recreate_is_refused_before_any_provider_clone(self):
        calls=[]
        actor=N(HCXAI_LeaseOwned=True,m_eAI_Recreate=True)
        self.env["super"]=N(eAI_Recreate=lambda:calls.append("clone"))
        self.engine.call("eAI_Recreate",actor)
        self.assertEqual([],calls)
        self.assertFalse(actor.m_eAI_Recreate)
        actor.HCXAI_LeaseOwned=False
        self.engine.call("eAI_Recreate",actor)
        self.assertEqual(["clone"],calls)

    def test_enabled_preference_is_not_admission(self):
        empty=self.env["HCXAIProfile"]()
        self.assertTrue(empty.Enabled)
        self.assertFalse(self.rule_api.ProfileValid(empty))
        self.assertFalse(self.mod.Install(self.profile,None))
        self.assertFalse(self.mod.Ready("chernarusplus"))

    def test_complete_profile_and_strict_limits(self):
        self.assertTrue(self.rule_api.ProfileValid(self.profile))
        for key,value in (("MaxTickWork",9),("MaxActors",0),("MaxLeaseHistory",65),
                          ("MaxObservationAgeMs",0),("CoordinateBound",float("nan")),
                          ("AllowBuiltinStuckRecovery",False),("SourceCommit","0"*40)):
            p=copy.deepcopy(self.profile);setattr(p,key,value)
            with self.subTest(key=key):self.assertFalse(self.rule_api.ProfileValid(p))

    def test_route_bounds_duplicates_and_observed_hashes(self):
        for change in (lambda p:p.Missions.append(copy.deepcopy(p.Missions[0])),
                       lambda p:p.Missions[0].Spawns.clear(),
                       lambda p:setattr(p.Missions[0],"GroupSize",3),
                       lambda p:setattr(p.Missions[0],"SiteId","other"),
                       lambda p:p.Missions[0].Waypoints.append((float("inf"),0,0)),
                       lambda p:setattr(p.Missions[0],"SurveySha256",""),
                       lambda p:setattr(p.Missions[0],"ActorClass","eAIDummy_SurvivorM_Mirek")):
            p=copy.deepcopy(self.profile);change(p)
            self.assertFalse(self.rule_api.ProfileValid(p))

    def test_live_receipt_binds_hashes_world_build_and_qualification(self):
        self.assertTrue(self.rule_api.ReceiptValid(self.profile,self.receipt,1000))
        for field in ("SourceCommit","ArtifactSha256","DependencyInventorySha256","WorldSha256",
                      "NativeScriptsSha256","BuildVersion","WorldName","WorldSession"):
            r=copy.deepcopy(self.receipt);setattr(r,field,"mismatch")
            self.assertFalse(self.rule_api.ReceiptValid(self.profile,r,1000))
        for field in ("ArtifactBytesVerified","DependencyClosureVerified","ObserverProviderQualified",
                      "RoutesQualified","InventoryLedgerQualified","OwnershipReconciled"):
            r=copy.deepcopy(self.receipt);setattr(r,field,False)
            self.assertFalse(self.rule_api.ReceiptValid(self.profile,r,1000))
        self.assertFalse(self.rule_api.ReceiptValid(self.profile,self.receipt,1101))
        self.assertFalse(self.rule_api.ReceiptValid(self.profile,self.receipt,999))

    def test_install_freezes_policy_and_real_globals_override_declarations(self):
        self.assertTrue(self.install())
        self.profile.MaxActors=32
        self.assertEqual(4,self.mod.m_Profile.MaxActors)
        self.global_ai.s_eAI_UnlimitedReloadAll=1
        self.assertFalse(self.mod.Ready("chernarusplus"))
        self.assertFalse(self.start())
        self.assertEqual([],self.created)

    def test_start_is_idempotent_and_binds_session_anchor_and_cap(self):
        self.assertTrue(self.install());self.assertTrue(self.start())
        self.assertTrue(self.start())
        self.assertEqual((1,2,2),(len(self.mod.m_Leases),self.mod.m_ReservedActors,
                                  self.mod.m_ReservedItems))
        self.assertFalse(self.start(session="old-session"))
        self.assertFalse(self.mod.StartLease("other","event-session","mission-site-5",(0.,0.,0.),4))
        self.assertFalse(self.start(lease="small",cap=1))
        self.assertEqual([],self.created)

    def test_reservations_include_retiring_work_and_history_is_not_reused(self):
        self.install();self.start();self.assertTrue(self.mod.StopLease("lease"))
        self.assertFalse(self.mod.Gone("lease"))
        self.assertTrue(self.start(lease="second"))
        self.assertFalse(self.start(lease="third"))
        self.assertFalse(self.start())
        self.assertEqual(4,self.mod.m_ReservedActors)

    def test_uncertain_intent_failure_retains_reserved_budget(self):
        self.install();self.journal_ok=False
        self.assertFalse(self.start())
        self.assertEqual(2,self.mod.m_ReservedActors)
        self.assertFalse(self.mod.Gone("lease"))
        self.assertEqual([],self.created)

    def test_real_factory_group_waypoints_and_fairness_setters(self):
        self.install();self.start();self.step();self.step()
        self.assertEqual(2,len(self.created))
        lease=self.mod.m_Leases[0]
        self.assertEqual(self.route.Waypoints,lease.Group.waypoints)
        self.assertEqual(1,lease.Group.mode)
        self.assertTrue(all(a.HCXAI_LeaseOwned for a in self.created))
        self.assertFalse(lease.Group.m_Persist)
        self.assertEqual(2,self.calls.count(("reload",0)))
        self.assertEqual(2,self.calls.count(("damage-in",1)))
        self.assertEqual(2,self.calls.count(("damage-out",1)))
        self.assertNotIn("SetPosition",self.runtime_source)

    def test_partial_spawn_failure_keeps_confirmed_actor_and_reservations(self):
        self.install();self.start()
        self.pending_factory=[self.actor(),None]
        self.step();self.step()
        lease=self.mod.m_Leases[0]
        self.assertTrue(lease.Retiring)
        self.assertEqual(2,self.mod.m_ReservedActors)
        self.assertFalse(self.start())
        self.assertFalse(self.mod.Gone("lease"))
        self.assertEqual([], [x for x in self.calls if x[0]=="delete"])

    def test_observer_veto_unknown_and_waiting_prevent_spawn_and_delete(self):
        self.install();self.start()
        for code in (0,1,2):
            self.observer_code=code;self.step()
            self.assertEqual([],self.created)
        self.observer_code=3;self.step()
        self.mod.StopLease("lease")
        for code in (0,1,2):
            self.observer_code=code;self.step()
            self.assertEqual([], [x for x in self.calls if x[0]=="delete"])

    def test_stop_request_is_not_observed_absence_or_released_budget(self):
        self.install();self.start();self.step();self.step()
        lease=self.mod.m_Leases[0]
        self.mod.StopLease("lease")
        self.step();self.step()
        self.assertFalse(self.mod.Gone("lease"))
        self.assertEqual(2,self.mod.m_ReservedActors)
        for slot in lease.Slots:
            self.mod.RecordDelete(slot.Handle)
            slot.Handle=None
        self.journal_ok=False
        self.step();self.step()
        self.assertFalse(self.mod.Gone("lease"))
        self.journal_ok=True
        self.step();self.step()
        self.assertTrue(self.mod.Gone("lease"))
        self.assertEqual(0,self.mod.m_ReservedActors)

    def test_null_handle_without_deletion_callback_is_not_gone(self):
        self.install();self.start();self.step();self.step()
        self.mod.StopLease("lease")
        for slot in self.mod.m_Leases[0].Slots:slot.Handle=None
        self.step();self.step()
        self.assertFalse(self.mod.Gone("lease"))
        self.assertEqual(2,self.mod.m_ReservedActors)

    def test_death_receipts_are_owned_once_and_attributed_without_target_positions(self):
        self.install();self.start();self.step()
        actor=self.created[0]
        participant=N(IsAlive=lambda:True,GetIdentity=lambda:N(GetId=lambda:"enrolled"))
        actor.alive=False
        self.mod.RecordDeath(actor,"enrolled")
        self.mod.RecordDeath(actor,"enrolled")
        self.mod.RecordDeath(self.actor(),"enrolled")
        first=self.mod.ObserveLease("lease",participant)
        second=self.mod.ObserveLease("lease",participant)
        self.assertEqual(("lease","event-session","enrolled"),
                         (first.Lease,first.Session,first.ParticipantId))
        self.assertTrue(first.Observed)
        self.assertEqual(vars(first),vars(second))
        self.assertEqual(1,first.Sequence)
        first.Token="caller-mutated"
        self.assertNotEqual(first.Token,self.mod.ObserveLease("lease",participant).Token)
        self.assertNotIn("Position",vars(first))
        outsider=N(IsAlive=lambda:True,GetIdentity=lambda:N(GetId=lambda:"outsider"))
        self.assertIsNone(self.mod.ObserveLease("lease",outsider))

    def test_clock_rollback_quarantines_without_releasing_or_deleting(self):
        self.install();self.start();self.step()
        self.mod.m_LastNow=1000;self.now=999
        self.mod.OnTick(1.)
        self.assertFalse(self.mod.m_Accepting)
        self.assertEqual(2,self.mod.m_ReservedActors)
        self.assertEqual([], [x for x in self.calls if x[0]=="delete"])

    def test_tick_work_and_client_authority_are_bounded(self):
        self.install();self.start();self.mod.OnTick(1.)
        self.assertLessEqual(len(self.created),2)
        self.game.IsServer=lambda:False
        self.assertFalse(self.start(lease="client"))
        self.assertFalse(self.mod.StopLease("lease"))
        self.assertFalse(self.mod.Gone("lease"))

    def test_optional_package_contract_has_no_provider_types_in_base_dependency(self):
        config=(ADDON/"config.cpp").read_text()
        for name in ("HollowCountry","DayZExpansion_AI_Scripts","DayZExpansion_Core_Scripts",
                     "DayZExpansion_ModStorage_Scripts","JM_CF_Scripts","DF_Scripts","DF_GUI",
                     "DayZExpansion_Animations_AI","DayZExpansion_Sounds_AI"):
            self.assertIn('"'+name+'"',config)
        self.assertNotIn("HollowCountryExpansionAI",(ROOT/"mods/HollowCountry/config.cpp").read_text())
        self.assertIn("extends HCEventAIProvider",self.runtime_source)
        for hook in ("super.EEKilled(killer)","super.EEDelete(parent)"):
            self.assertIn(hook,self.runtime_source)

    def test_replay_after_world_or_capability_loss_does_not_claim_ready(self):
        self.install();self.start()
        self.game.GetWorldName=lambda:"other-world"
        self.assertFalse(self.start())
        self.game.GetWorldName=lambda:"chernarusplus"
        self.receipt.ObserverProviderQualified=False
        self.assertFalse(self.start())
        self.assertEqual(1,len(self.mod.m_Leases))
        self.assertEqual([],self.created)

    def test_start_callback_reentry_cannot_duplicate_identity_or_reservations(self):
        self.install()
        entered=[]
        def route(*args):
            if not entered:
                entered.append(True)
                self.assertFalse(self.start())
            return True
        self.hooks.RouteQualified=route
        self.assertTrue(self.start())
        self.assertEqual(1,len(self.mod.m_Leases))
        self.assertEqual(2,self.mod.m_ReservedActors)

    def test_observer_reentry_cannot_repeat_native_creation(self):
        self.install();self.start()
        entered=[]
        def observers(*args):
            if not entered:
                entered.append(True)
                self.step()
            return N()
        self.hooks.Observers=observers
        self.step()
        self.assertEqual(1,len(self.created))
        self.assertEqual(1,sum(s.Attempted for s in self.mod.m_Leases[0].Slots))

    def test_magazine_write_is_bounded_once_and_read_back(self):
        actor=self.actor()
        magazine=N(magazine=True,ammo=0,GetAmmoMax=lambda:30)
        writes=[]
        magazine.ServerSetAmmoCount=lambda value:(writes.append(value),setattr(magazine,"ammo",value))
        magazine.GetAmmoCount=lambda:magazine.ammo
        actor.GetInventory=lambda:N(CreateInInventory=lambda typ:magazine)
        spec=self.env["HCXAIEquipment"]()
        vars(spec).update(ClassName="Mag_AKM_30Rnd",IsMagazine=True,AmmoCount=12)
        mission=copy.deepcopy(self.route);mission.Equipment=A([spec])
        self.assertTrue(self.mod.Equip(actor,mission))
        self.assertEqual([12],writes)
        spec.AmmoCount=31
        self.assertFalse(self.mod.Equip(actor,mission))
        self.assertEqual([12],writes)
        spec.AmmoCount=10;magazine.GetAmmoCount=lambda:9
        self.assertFalse(self.mod.Equip(actor,mission))

    def test_actual_actor_fairness_getter_checks_effective_fields(self):
        actor=N(GetAllowDamage=lambda:True,m_eAI_EnableFlankingOutsideCombat=False,
                m_eAI_UnlimitedReload=0,m_eAI_IsUnlimitedReloadAll=False,
                m_eAI_DamageMultiplier=1.,m_eAI_DamageReceivedMultiplier=1.,
                m_eAI_HeadshotResistance=0.,m_HCXAI_Owned=False,m_eAI_Recreate=False)
        self.assertTrue(self.engine.call("HCXAI_Fair",actor))
        for field in ("m_eAI_EnableFlankingOutsideCombat","m_eAI_UnlimitedReload",
                      "m_eAI_IsUnlimitedReloadAll","m_eAI_DamageMultiplier",
                      "m_eAI_DamageReceivedMultiplier","m_eAI_HeadshotResistance"):
            changed=copy.copy(actor);setattr(changed,field,2)
            self.assertFalse(self.engine.call("HCXAI_Fair",changed))
        actor.GetAllowDamage=lambda:False
        self.assertFalse(self.engine.call("HCXAI_Fair",actor))


class JournalStoreTests(unittest.TestCase):
    """Authored file transaction with explicit synthetic native IO/JSON adapters."""
    PATH = "$profile:HollowCountry/expansion-ai-leases.json"
    PENDING = "$profile:HollowCountry/expansion-ai-leases.pending.json"

    def setUp(self):
        self.files = {}
        self.operations = []
        self.copy_ok = True
        self.save_ok = True
        self.delete_ok = True
        env = dict(A=A, HCObserverTransitionPolicy=lambda:N())
        declarations(env)
        self.data = env["HCXAIJournalData"]()
        def encode(data):
            return json.dumps(vars(data), default=vars, sort_keys=True)
        def decode(data):
            try:
                return json.loads(data, object_hook=lambda fields:N(**fields))
            except (ValueError, TypeError):
                return None
        def save(path, data, error):
            self.operations.append(("save", path))
            self.files[path] = encode(data) if self.save_ok else "{"
            return self.save_ok
        def copy_file(source, target):
            self.operations.append(("copy", source, target))
            self.files[target] = self.files[source] if self.copy_ok else "{"
            return self.copy_ok
        def delete(path):
            self.operations.append(("delete", path))
            if self.delete_ok: self.files.pop(path, None)
            return self.delete_ok
        env.update(Json=N(Encode=encode, Decode=decode, SaveFile=save),
                   GetGame=lambda:N(IsServer=lambda:True), FileExist=lambda p:p in self.files,
                   MakeDirectory=lambda p:True, FileMode=N(READ=0),
                   OpenFile=lambda p,m:p if p in self.files else None,
                   ReadFile=lambda p,n:self.files[p][:n], CloseFile=lambda h:None,
                   CopyFile=copy_file, DeleteFile=delete)
        source = (SCRIPTS / "4_World/HCXAIStore.c").read_text()
        # Native out parameters become Python assignments; no branch is replaced.
        source = re.sub(r'JsonFileLoader<HCXAIJournalData>\.MakeData\((\w+), (\w+), error\)',
                        r'((\2 := Json.Encode(\1)) != null)', source)
        source = re.sub(r'JsonFileLoader<HCXAIJournalData>\.LoadData\((\w+), (\w+), error\)',
                        r'((\2 := Json.Decode(\1)) != null)', source)
        source = source.replace('JsonFileLoader<HCXAIJournalData>.SaveFile', 'Json.SaveFile')
        source = source.replace('FileHandle', 'int')
        source = source.replace('int count = ReadFile(handle, data, 65537);',
                                'data = ReadFile(handle, 65537); int count = data.Length();')
        engine = Authored(source, env)
        self.store = N()
        env["HCXAIStore"] = self.store
        for name in re.findall(r"static \w+ (\w+)\([^)]*\)\s*\{", source):
            setattr(self.store, name, lambda *a,n=name:engine.call(n, None, *a))

    def test_successful_write_verifies_staged_snapshot_and_clears_guard(self):
        self.assertTrue(self.store.SaveJournal(self.data))
        self.assertIn(("save", self.PENDING), self.operations)
        self.assertIn(("copy", self.PENDING, self.PATH), self.operations)
        self.assertNotIn(self.PENDING, self.files)
        self.assertEqual(1, self.store.LoadJournal().SchemaVersion)

    def test_interrupted_publication_blocks_load_and_subsequent_writes(self):
        self.copy_ok = False
        self.assertFalse(self.store.SaveJournal(self.data))
        self.assertIn(self.PENDING, self.files)
        self.assertIsNone(self.store.LoadJournal())
        before = list(self.operations)
        self.copy_ok = True
        self.assertFalse(self.store.SaveJournal(self.data))
        self.assertEqual(before, self.operations)

    def test_failed_stage_preserves_committed_bytes_and_retains_guard(self):
        self.files[self.PATH] = '{"SchemaVersion": 1, "Rows": []}'
        before = self.files[self.PATH]
        self.save_ok = False
        self.assertFalse(self.store.SaveJournal(self.data))
        self.assertEqual(before, self.files[self.PATH])
        self.assertIsNone(self.store.LoadJournal())

    def test_guard_cleanup_failure_never_claims_committed_success(self):
        self.delete_ok = False
        self.assertFalse(self.store.SaveJournal(self.data))
        self.assertIsNone(self.store.LoadJournal())


if __name__ == "__main__":
    unittest.main()
