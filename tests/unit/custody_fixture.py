"""Explicit synthetic disk/JSON/world ports; execute authored custody methods."""
import json
import re
from types import SimpleNamespace as N

from tests.unit.test_hc_ai_custody import adapted, IDENTITY, MATERIALIZER
from tests.unit.test_expansion_ai_adapter import A
from tests.unit.ai_limits_fixture import install


class CustodyFixture:
    def __init__(self):
        self.disk, self.logs, self.facts, self.debits = {}, [], [], []
        self.fail_write = False
        self.world = N(GetFaction=lambda key: N(Strength=72),
                       AddFact=lambda *args: self.facts.append(args) or True,
                       AdjustStrength=lambda *args: self.debits.append(args) or True,
                       MaterializerRow=lambda index: self.proposal() if index == 0 else None)
        self.env = dict(A=A, len=len, str=str, indices=range, Print=self.logs.append,
                        HCWorldModule=N(Get=lambda: self.world),
                        FileExist=lambda path: path in self.disk,
                        MakeDirectory=lambda path: self.disk.setdefault(path, '') == '',
                        DeleteFile=lambda path: self.disk.pop(path, None) is not None,
                        CopyFile=self.copy_file,
                        HCWorldStore=N(Read=lambda path: self.disk.get(path, ''), Write=self.write),
                        HCWorldProposal=lambda: N(),
                        HCWorldProposalLease=lambda: N(Claimed=False, Finished=False,
                            Materialized=False, Survivors=0, OutcomeApplied=False, RowIndex=-1),
                        GetGame=lambda: N(),
                        HCPerfPlayers=N(HCGet=lambda: A([N(GetIdentity=lambda: True,
                            IsAlive=lambda: True, GetPosition=lambda: [100., 0., 100.])])),
                        HCWorldLimits=N(Token=lambda key: bool(key) and len(key) <= 96,
                                        Position=lambda position: True),
                        synthetic_encode=self.encode, synthetic_decode=self.decode,
                        synthetic_legacy_encode=lambda data: self.encode(N(SchemaVersion=data.SchemaVersion, Rows=data.Rows)))
        self.limits = install(self.env)
        self.budget = self.env['HCAIBudget']
        data = IDENTITY.read_text()
        cap = int(re.search(r'MAX_ROWS = (\d+)', data)[1])
        self.env['HCAIPartyCustodyRow'] = lambda: N(Outcome='CLAIMED', Materialized=False, Survivors=0)
        self.env['HCAIPartyIdentity'] = N(HCValid=lambda identity: True, HCCreate=lambda *args: N())
        self.data_policy = adapted(data, self.env)
        self.env['HCAIPartyCustody'] = N(MAX_ROWS=cap)
        schema = int(re.search(r'SchemaVersion = (\d+)', data)[1])
        self.env['HCAIPartyCustodyData'] = lambda: N(SchemaVersion=schema, NextLease=1, Rows=A())
        for method in ('HCReservation', 'HCFinish'):
            setattr(self.env['HCAIPartyCustody'], method,
                    lambda *args, name=method: self.data_policy.call(name, None, *args))
        source = MATERIALIZER.read_text()
        # Syntax-only adaptation for native out parameters. JSON and disk are
        # named synthetic stdlib ports, never a model of native atomicity.
        source = source.replace('JsonFileLoader<HCAIPartyCustodyLegacyData>.MakeData(legacy, canonical, error)', '((canonical := synthetic_legacy_encode(legacy)) != \"\")')
        source = re.sub(r'JsonFileLoader<\w+>\.MakeData\((\w+(?:\.\w+)*), (\w+), error\)',
                        r'((\2 := synthetic_encode(\1)) != "")', source)
        source = re.sub(r'JsonFileLoader<\w+>\.LoadData\((\w+), (\w+), error\)',
                        r'((\2 := synthetic_decode(\1)) != null)', source)
        source = re.sub(r'for \(int (\w+) = ([^;]+); \1 < ([^;]+); \1\+\+\)',
                        r'foreach (int \1 : indices(\2, \3))', source)
        source = source.replace('new array<vector>;', 'new array<vector>();')
        source = re.sub(r'new (\w+);', r'new \1();', source)
        source = re.sub(r'array<\w+>(?= \w+ =)|\bMan(?= \w+ =)', 'HCXAIValue', source)
        source = source.replace('row.Identity.HCGeneration().ToString()', 'str(row.Identity.HCGeneration())')
        source = source.replace('HCAILimits.Get().MaxLiveAI.ToString()', 'str(HCAILimits.Get().MaxLiveAI)')
        source = source.replace('GetName(),', 'this.GetName(),').replace('!IsEnabled(settings)', '!this.IsEnabled(settings)')
        source = source.replace('        Expire();', '        this.Expire();').replace('            InterestRing();', '            this.InterestRing();')
        source = source.replace('!CanPropose(', '!HCWorldMaterializer.CanPropose(')
        source = source.replace('s_Instance', 'HCWorldMaterializer.s_Instance')
        self.policy = adapted(source, self.env)
        self.api = N(PROVIDER_TIMEOUT=120, s_Instance=None)
        for name in ('ROW_COOLDOWN', 'ROWS_PER_RING', 'MAX_PLAYERS', 'RING_SECONDS', 'LOG_SECONDS'):
            self.env[name] = int(re.search(r'const int ' + name + r' = (\d+)', source)[1])
            setattr(self.api, name, self.env[name])
        self.env['HCWorldMaterializer'] = self.api
        for method in ('FoldBack', 'NoProvider', 'CanPropose'):
            setattr(self.api, method, lambda *args, name=method: self.policy.call(name, None, *args))
        self.runtime = self.new_runtime()

    @staticmethod
    def encode(data):
        return json.dumps(data, default=lambda value: vars(value), sort_keys=True)

    @staticmethod
    def decode(text):
        from tests.unit.json_loader_port import decode_json
        return decode_json(text, 'HCAIPartyCustodyData', A)

    def copy_file(self, source, dest):
        if source not in self.disk: return False
        self.disk[dest] = self.disk[source]
        return True

    def write(self, path, text):
        if self.fail_write: return False
        self.disk[path] = text
        return True

    def identity(self, key='synthetic-party'):
        fields = dict(PartyId='party:' + key, CampId='camp:' + key, HomeId='synthetic-home',
                      RouteId='route:' + key, CargoId='cargo:' + key, Generation=42)
        return N(**{'HC' + key: lambda value=value: value for key, value in fields.items()})

    def proposal(self, key='synthetic-party'):
        return N(Id='party:' + key, Identity=self.identity(key), ActorCap=4,
                 FactionId='synthetic-faction', PlaceId='synthetic-home', Kind='PATROL',
                 Position=[100., 0., 100.])

    def new_runtime(self):
        work = N(HCReset=lambda cap: None, HCContinue=lambda: True,
                 HCTake=lambda count: True, HCDeferred=lambda *args: None)
        runtime = N(m_CustodyReady=True, m_Custody=self.env['HCAIPartyCustodyData'](),
                    m_CustodyText='', m_CustodyFailurePrinted=False, m_StartedOnce=False, m_CustodyPath='$profile:HollowCountry/ai-custody.json',
                    m_Active=A(), m_Cooldowns=A([0] * 72), m_Clock=0, m_RowCursor=0,
                    m_PlayerCursor=0, m_WorkBudget=work, m_UnitBudget=work,
                    m_DuplicateRefused=0, m_Proposals=0, m_Traces=0, m_Materialized=0,
                    m_Running=False, m_AdmissionPrinted=True)
        names = re.findall(r'(?:protected |override |static )*(?:bool|void|int|string|HCAIPartyIdentity) (\w+)\(', MATERIALIZER.read_text())
        for name in names:
            setattr(runtime, name, lambda *args, name=name: self.policy.call(name, runtime, *args))
        return runtime

    def offer(self):
        self.runtime.m_RowCursor = 0  # focus the bounded ring on synthetic row zero
        prior = len(self.runtime.m_Active)
        self.runtime.InterestRing()
        if len(self.runtime.m_Active) == prior: return None
        lease = self.runtime.m_Active[-1]
        return lease if self.runtime.HCClaim(lease) else None
