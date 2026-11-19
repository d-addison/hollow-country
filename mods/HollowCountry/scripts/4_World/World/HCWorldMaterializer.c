// W5-PERF-6: <=4 ledger proposals/ring tick; population from AILimits.
// Native time/player cache evidence: HCWorkBudget.c (Game.c:914/945/1535).
// LC-T402 / #98, EXP-L1 + EXP-P2. Native evidence (installed snapshot):
// scripts-1.30.164289/3_Game/Global/Game.c:945 GetPlayers;
// 3_Game/Entities/Man.c:21 GetIdentity; Entities/Object.c:287 GetPosition,
// :517 IsAlive; 1_Core/proto/EnConvert.c:30 int.ToString;
// EnScript.c:380,385,394,407,470 array Count/Clear/Find/Insert/
// RemoveOrdered; EnDebug.c:96 Print. All other calls are project interfaces.
// Queue/cooldowns are process-local, never body persistence. Durable outcomes
// use HCWorldModule.AddFact and its existing verified temp/backup/copy store.
// HC-10 / #143-147, #139: no concurrent live copy of a party/cargo.
// Native persistence evidence: scripts-1.30.164289/1_Core/proto/EnSystem.c:
// 397 FileExist, 525 MakeDirectory, 528 DeleteFile, 531 CopyFile;
// 3_Game/tools/JsonFileLoader.c:69,85 LoadData/MakeData. Bounded Read/Write
// reuse HCWorldStore (same inspected native file APIs, verified readback).
// In process only Result confirms absence. On restart Persist=false provider
// bodies cannot survive; unresolved claims finish unknown, without cargo replay.
// HC has no dependency on the optional provider. No entities or inventory here.
class HCWorldProposal
{
    string Id;
    string FactionId;
    string PlaceId;
    vector Position;
    int ActorCap;
    string Kind;
    ref HCAIPartyIdentity Identity;
}

class HCWorldProposalLease
{
    ref HCWorldProposal Proposal;
    string RowId;
    int RowIndex = -1;
    float Created;
    bool Claimed;
    bool Finished;
    bool Materialized;
    int Survivors;
    bool OutcomeApplied;
}

// w29-debugmap #194: detached read-only row for the `materializer-proposals`
// debug layer (an ACTIVE proposal lease, not an eligible ledger candidate). No
// party identity, faction id or lease handle leaves the owner.
class HCDebugProposalRow
{
    string Id;
    string PlaceId;
    string Kind;
    vector Position;
    int ActorCap;
    string State = "queued";
    int AgeSeconds;
}

// Narrow READ-ONLY ledger seam, authored here without editing world owners'
// files. Returns fresh proposals, never retained ledger rows. Fixed indices
// use configured holdout/party spans for cooldowns (fixed for this process). The place anchor is deliberately NOT a house or player position.
modded class HCWorldModule
{
    HCWorldProposal MaterializerRow(int rowIndex)
    {
        if (!m_Running || !m_Data || rowIndex < 0 || rowIndex >= HCAILimits.Get().MaxHoldouts + HCAILimits.Get().MaxParties) { return null; }
        HCWorldProposal row = new HCWorldProposal;
        if (rowIndex < HCAILimits.Get().MaxHoldouts)
        {
            if (rowIndex >= m_Data.Holdouts.Count()) { return null; }
            HCWorldHoldout holdout = m_Data.Holdouts[rowIndex];
            if (!holdout || (holdout.State != "OCCUPIED" && holdout.State != "ALERT") || holdout.Occupants < 1) { return null; }
            if (!HCHoldouts.HCAllowsMaterializer(holdout)) { return null; }
            row.Id = "holdout:" + holdout.Id;
            row.FactionId = holdout.FactionId;
            row.PlaceId = holdout.PlaceId;
            row.ActorCap = holdout.Occupants;
            row.Kind = "HOLDOUT";
            row.Identity = HCAIPartyIdentity.HCCreate(row.Id, "camp:" + holdout.Id, holdout.PlaceId, "stationary:" + holdout.Id, "cargo:" + holdout.Id, Epoch());
        }
        else
        {
            int partyIndex = rowIndex - HCAILimits.Get().MaxHoldouts;
            if (partyIndex >= m_Data.Parties.Count()) { return null; }
            HCWorldParty party = m_Data.Parties[partyIndex];
            if (!party || party.Materialized || !party.Route || party.Edge < 0 || party.Edge >= party.Route.Count() || party.Size < 1) { return null; }
            row.Id = "party:" + party.Id;
            row.FactionId = party.FactionId;
            row.PlaceId = party.Route[party.Edge];
            row.ActorCap = party.Size;
            row.Kind = party.Kind;
            row.Identity = HCAIPartyIdentity.HCCreate(row.Id, "home:" + party.Home, party.Home, "route:" + party.Id, "cargo:" + party.Id, Epoch());
        }
        HCWorldPlace place = m_Data.Place(row.PlaceId);
        HCWorldFaction faction = m_Data.Faction(row.FactionId);
        if (!place || !faction || faction.Strength < 1 || !row.Identity) { return null; }
        row.Position = place.Position;
        if (row.ActorCap > faction.Strength) { row.ActorCap = faction.Strength; }
        if (row.ActorCap > HCAILimits.Maximum(row.Kind)) { row.ActorCap = HCAILimits.Maximum(row.Kind); }
        return row;
    }
}

class HCWorldMaterializer : HCModule
{
    static const int MAX_PLAYERS = 32;
    static const int ROWS_PER_RING = 32;
    static const int PROVIDER_TIMEOUT = 120;
    static const int RING_SECONDS = 30;
    static const int LOG_SECONDS = 600;
    static const int ROW_COOLDOWN = 21600;
    protected static HCWorldMaterializer s_Instance;
    protected ref array<ref HCWorldProposalLease> m_Active = new array<ref HCWorldProposalLease>;
    protected ref array<float> m_Cooldowns = new array<float>;
    protected float m_Clock;
    protected float m_RingSeconds;
    protected float m_LogSeconds;
    protected int m_PlayerCursor;
    protected int m_RowCursor;
    protected ref HCWorkBudget m_WorkBudget = new HCWorkBudget;
    protected ref HCUnitBudget m_UnitBudget = new HCUnitBudget;
    protected ref HCAIPartyCustodyData m_Custody;
    protected bool m_CustodyReady;
    protected string m_CustodyText;
    protected bool m_CustodyFailurePrinted;
    protected string m_CustodyPath = "$profile:HollowCountry/ai-custody.json";
    protected int m_DuplicateRefused;
    protected int m_Proposals;
    protected int m_Materialized;
    protected int m_Traces;
    protected bool m_Running;
    protected bool m_AdmissionPrinted;
    protected bool m_StartedOnce;

    override string GetName() { return "Materializer"; }
    override bool IsEnabled(HCSettings settings) { return settings && settings.EnableEncounters; }

    override void OnStart(HCSettings settings)
    {
        if (m_Running || !IsEnabled(settings)) { return; }
        if (!m_AdmissionPrinted)
        {
            Print(HCV2Admission.Line("Materializer", true, "EXP-L1", HCV2Gates.Qualified("EXP-L1")));
            m_AdmissionPrinted = true;
        }
        m_Active.Clear();
        m_Cooldowns.Clear();
        for (int cooldownIndex = 0; cooldownIndex < HCAILimits.Get().MaxHoldouts + HCAILimits.Get().MaxParties; cooldownIndex++) { m_Cooldowns.Insert(0); }
        m_Clock = 0;
        m_RingSeconds = 0;
        m_LogSeconds = 0;
        m_CustodyReady = this.HCLoadCustody();
        if (!m_CustodyReady) { HCAIBudget.Block(); }
        else if (!m_StartedOnce) { this.HCRestoreCustody(); }
        else
        {
            // A module off/on transition is not a process restart. Provider
            // bodies may still exist; retain their claims until Result.
            foreach (HCAIPartyCustodyRow sameProcess : m_Custody.Rows)
            {
                if (sameProcess.Outcome == "CLAIMED" || sameProcess.Outcome == "QUARANTINED") { HCAIBudget.Restore(sameProcess.LeaseId, sameProcess.ActorCap); }
            }
        }
        // A failed load or migration is still the first start on the next toggle.
        if (m_CustodyReady) { m_StartedOnce = true; }
        m_Running = true;
        s_Instance = this;
        this.HCPlanLine("on");
    }

    override void OnTick(float deltaTime)
    {
        if (!m_Running || !(deltaTime > 0) || deltaTime > 3600) { return; }
        m_Clock += deltaTime;
        m_RingSeconds += deltaTime;
        m_LogSeconds += deltaTime;
        Expire();
        if (m_RingSeconds >= RING_SECONDS)
        {
            m_RingSeconds = 0;
            InterestRing();
        }
        if (m_LogSeconds >= LOG_SECONDS)
        {
            m_LogSeconds = 0;
            Print("[HollowCountry] V2 materializer proposals=" + m_Proposals.ToString() + " materialized=" + m_Materialized.ToString() + " traces=" + m_Traces.ToString());
            this.HCPlanLine("on");
        }
    }

    override void OnStop()
    {
        // Mission shutdown owns provider cleanup. Unreported body outcomes are
        // not invented or replayed after restart; ledger facts remain durable.
        m_Running = false;
        this.HCPlanLine("off");
        if (s_Instance == this) { s_Instance = null; }
        foreach (HCWorldProposalLease stopped : m_Active)
        {
            // Unclaimed leases have never been handed to a provider.
            if (!stopped.Claimed) { HCAIBudget.Release(stopped.Proposal.Id); }
        }
        m_Active.Clear();
    }

    protected void HCPlanLine(string state)
    {
        if (state != "off" && !m_CustodyReady) { state = "refused"; }
        int leases = 0;
        if (m_Custody && m_Custody.Rows) { leases = m_Custody.Rows.Count(); }
        Print("[HC Plan] HC-10 actor_cap=" + HCAILimits.Get().MaxLiveAI.ToString() + " leases=" + leases.ToString() + " duplicate_refused=" + m_DuplicateRefused.ToString() + " state=" + state + " runtime=PENDING");
    }

    // No backup replay. Missing primary with backup, interrupted intent,
    // corrupt/noncanonical data and external edits all suspend admission.
    // This sidecar MUST be backed up with engine inventory AND world.json.
    protected bool HCLoadCustody()
    {
        m_Custody = new HCAIPartyCustodyData();
        m_CustodyText = "";
        if (!FileExist("$profile:HollowCountry") && !MakeDirectory("$profile:HollowCountry")) { return false; }
        if (FileExist(m_CustodyPath + ".tmp")) { return false; }
        if (!FileExist(m_CustodyPath)) { return !FileExist(m_CustodyPath + ".bak"); }
        string text = HCWorldStore.Read(m_CustodyPath);
        HCAIPartyCustodyData loaded;
        string error;
        if (text == "" || !JsonFileLoader<HCAIPartyCustodyData>.LoadData(text, loaded, error) || !loaded) { return false; }
        // V1 never wrote NextLease. Validate the exact legacy image before
        // adding the new monotonic counter; never repair a malformed V2 image.
        if (loaded.SchemaVersion == 1 && loaded.NextLease == 0) { loaded.NextLease = 1; }
        if (!this.HCValidCustody(loaded)) { return false; }
        string canonical;
        if (loaded.SchemaVersion == 1)
        {
            HCAIPartyCustodyLegacyData legacy;
            if (!JsonFileLoader<HCAIPartyCustodyLegacyData>.LoadData(text, legacy, error) || !legacy || legacy.SchemaVersion != 1) { return false; }
            if (!JsonFileLoader<HCAIPartyCustodyLegacyData>.MakeData(legacy, canonical, error) || canonical != text) { return false; }
        }
        else if (!JsonFileLoader<HCAIPartyCustodyData>.MakeData(loaded, canonical, error) || canonical != text) { return false; }
        m_Custody = loaded;
        m_CustodyText = text;
        return true;
    }

    // Expansion transient groups use Persist=false. There is no surviving body
    // after a process restart, and no trustworthy casualty observation either.
    // Cargo never left its owner store here: release custody without spawning,
    // refunding, copying inventory or applying a guessed world outcome.
    protected void HCRestoreCustody()
    {
        int recovered = 0;
        foreach (HCAIPartyCustodyRow restored : m_Custody.Rows)
        {
            if (restored.Outcome == "CLAIMED" || restored.Outcome == "QUARANTINED")
            {
                restored.Outcome = "FINISHED_UNKNOWN";
                restored.Materialized = false;
                restored.Survivors = 0;
                HCAIBudget.Release(restored.LeaseId);
                recovered++;
                Print("[HC AI] custody restore lease=" + restored.LeaseId + " outcome=FINISHED_UNKNOWN runtime=PENDING");
            }
            else { HCAIBudget.Release(restored.LeaseId); }
        }
        if (recovered > 0 || m_Custody.SchemaVersion == 1)
        {
            m_Custody.SchemaVersion = 2;
            this.HCSaveCustody();
        }
        Print("[HC AI] custody restore finished_unknown=" + recovered.ToString() + " runtime=PENDING");
    }

    protected bool HCValidCustody(HCAIPartyCustodyData data)
    {
        if (!data || (data.SchemaVersion != 1 && data.SchemaVersion != 2) || data.NextLease < 1 || !data.Rows || data.Rows.Count() > HCAIPartyCustody.MAX_ROWS) { return false; }
        foreach (HCAIPartyCustodyRow row : data.Rows)
        {
            if (!row || row.ActorCap < 1 || row.ActorCap > HCAILimits.SIZE_CEILING || !HCWorldLimits.Token(row.LeaseId)) { return false; }
            if (!HCAIPartyIdentity.HCCreate(row.PartyId, row.CampId, row.HomeId, row.RouteId, row.CargoId, row.Generation)) { return false; }
            if (row.Outcome != "CLAIMED" && row.Outcome != "FINISHED" && row.Outcome != "FINISHED_UNKNOWN" && row.Outcome != "QUARANTINED") { return false; }
            if (row.Survivors < 0 || row.Survivors > row.ActorCap || (!row.Materialized && row.Survivors != 0)) { return false; }
            if ((row.Outcome == "CLAIMED" || row.Outcome == "FINISHED_UNKNOWN") && (row.Materialized || row.Survivors != 0)) { return false; }
            foreach (HCAIPartyCustodyRow other : data.Rows)
            {
                if (other == row) { break; }
                if (other.PartyId == row.PartyId || other.CargoId == row.CargoId || other.LeaseId == row.LeaseId) { return false; }
            }
        }
        return true;
    }

    // Synchronous transaction barrier, NOT a routine scheduler checkpoint.
    // Verified intent -> prior backup -> copy/readback -> delete intent, using
    // the existing store ports. Any failure latches off; never refund/replay.
    protected bool HCSaveCustody()
    {
        if (this.HCWriteCustody()) { return true; }
        m_CustodyReady = false;
        HCAIBudget.Block();
        if (!m_CustodyFailurePrinted)
        {
            m_CustodyFailurePrinted = true;
            Print("[HC AI] CUSTODY SAVE FAILED; ALL NEW AI BLOCKED; inspect ai-custody.json and intent before restart runtime=PENDING");
        }
        return false;
    }

    protected bool HCWriteCustody()
    {
        if (!m_CustodyReady || !this.HCValidCustody(m_Custody)) { m_CustodyReady = false; return false; }
        string text;
        string error;
        if (!JsonFileLoader<HCAIPartyCustodyData>.MakeData(m_Custody, text, error)) { m_CustodyReady = false; return false; }
        if (FileExist(m_CustodyPath + ".tmp")) { m_CustodyReady = false; return false; }
        if (m_CustodyText != "" && HCWorldStore.Read(m_CustodyPath) != m_CustodyText) { m_CustodyReady = false; return false; }
        if (m_CustodyText == "" && FileExist(m_CustodyPath)) { m_CustodyReady = false; return false; }
        // Latch before first write: a failed barrier is never retried in process.
        m_CustodyReady = false;
        if (!HCWorldStore.Write(m_CustodyPath + ".tmp", text)) { return false; }
        if (m_CustodyText != "")
        {
            if (FileExist(m_CustodyPath + ".bak") && !DeleteFile(m_CustodyPath + ".bak")) { return false; }
            if (!CopyFile(m_CustodyPath, m_CustodyPath + ".bak") || HCWorldStore.Read(m_CustodyPath + ".bak") != m_CustodyText) { return false; }
        }
        if (FileExist(m_CustodyPath) && !DeleteFile(m_CustodyPath)) { return false; }
        if (!CopyFile(m_CustodyPath + ".tmp", m_CustodyPath) || HCWorldStore.Read(m_CustodyPath) != text) { return false; }
        if (!DeleteFile(m_CustodyPath + ".tmp")) { return false; }
        m_CustodyText = text;
        m_CustodyReady = true;
        return true;
    }

    protected bool HCCustodyAllows(HCAIPartyIdentity identity)
    {
        if (!m_CustodyReady || !m_Custody || !m_Custody.Rows || !identity) { return false; }
        bool evictable = false;
        foreach (HCAIPartyCustodyRow reservedRow : m_Custody.Rows)
        {
            if (reservedRow.Outcome == "FINISHED" || reservedRow.Outcome == "FINISHED_UNKNOWN") { evictable = true; continue; }
            if (reservedRow.PartyId == identity.HCPartyId() || reservedRow.CargoId == identity.HCCargoId())
            {
                if (m_DuplicateRefused < 2147483647) { m_DuplicateRefused++; }
                return false;
            }
        }
        return evictable || m_Custody.Rows.Count() < HCAIPartyCustody.MAX_ROWS;
    }

    // Only unresolved in-process custody and quarantines charge debt. Completed
    // history is bounded and evictable; active leases are already charged below.
    protected int HCCustodyDebt(bool actorUnits)
    {
        int debt = 0;
        if (!m_Custody || !m_Custody.Rows) { return 0; }
        foreach (HCAIPartyCustodyRow debtRow : m_Custody.Rows)
        {
            if (debtRow.Outcome == "FINISHED" || debtRow.Outcome == "FINISHED_UNKNOWN") { continue; }
            bool held = false;
            foreach (HCWorldProposalLease activeLease : m_Active)
            {
                if (activeLease.Proposal.Id == debtRow.LeaseId) { held = true; break; }
            }
            if (held) { continue; }
            if (actorUnits) { debt += debtRow.ActorCap; }
            else { debt++; }
        }
        return debt;
    }

    protected bool HCClaimFits()
    {
        int actors = this.HCCustodyDebt(true);
        foreach (HCWorldProposalLease capacityLease : m_Active) { actors += capacityLease.Proposal.ActorCap; }
        return actors <= HCAILimits.Get().MaxLiveAI && m_Active.Count() + this.HCCustodyDebt(false) <= HCAILimits.Get().MaxMaterialized;
    }

    // Compatibility queries for custody reports. HCAIBudget owns admission for
    // every provider; startup restores this debt there before new proposals.
    // Missing/unreadable custody blocks new bodies, never grants room.
    static int HCUnresolvedActors()
    {
        if (!s_Instance || !s_Instance.m_Running || !s_Instance.m_CustodyReady) { return HCAILimits.Get().MaxLiveAI; }
        return s_Instance.HCCustodyDebt(true);
    }

    static int HCUnresolvedLeases()
    {
        if (!s_Instance || !s_Instance.m_Running || !s_Instance.m_CustodyReady) { return HCAILimits.Get().MaxMaterialized; }
        return s_Instance.HCCustodyDebt(false);
    }

    protected bool HCClaim(HCWorldProposalLease candidate)
    {
        if (!candidate || !candidate.Proposal || candidate.Claimed || candidate.Finished || !this.HCCustodyAllows(candidate.Proposal.Identity)) { return false; }
        if (!this.HCClaimFits()) { return false; }
        HCAIPartyCustodyRow row = HCAIPartyCustody.HCReservation(candidate.Proposal.Identity, candidate.Proposal.Id, candidate.Proposal.ActorCap);
        if (!row) { return false; }
        int priorIndex = m_Custody.Rows.Count() - 1;
        while (priorIndex >= 0)
        {
            HCAIPartyCustodyRow prior = m_Custody.Rows[priorIndex];
            if ((prior.Outcome == "FINISHED" || prior.Outcome == "FINISHED_UNKNOWN") && (prior.PartyId == row.PartyId || prior.CargoId == row.CargoId)) { m_Custody.Rows.RemoveOrdered(priorIndex); }
            priorIndex -= 1;
        }
        int evictIndex = 0;
        while (m_Custody.Rows.Count() >= HCAIPartyCustody.MAX_ROWS && evictIndex < m_Custody.Rows.Count())
        {
            HCAIPartyCustodyRow old = m_Custody.Rows[evictIndex];
            if (old.Outcome == "FINISHED" || old.Outcome == "FINISHED_UNKNOWN") { m_Custody.Rows.RemoveOrdered(evictIndex); }
            else { evictIndex++; }
        }
        if (m_Custody.Rows.Count() >= HCAIPartyCustody.MAX_ROWS) { return false; }
        m_Custody.Rows.Insert(row);
        if (!this.HCSaveCustody()) { return false; }
        candidate.Claimed = true;
        return true;
    }

    // Wave 2 director seam: immutable identity for the exact current lease.
    // Never derive an identity from the place position or provider body count.
    static HCAIPartyIdentity HCIdentity(string leaseId)
    {
        if (!s_Instance || !s_Instance.m_Running) { return null; }
        foreach (HCWorldProposalLease identityLease : s_Instance.m_Active)
        {
            if (identityLease.Proposal.Id == leaseId && identityLease.Claimed) { return identityLease.Proposal.Identity; }
        }
        return null;
    }

    // w29-debugmap #194: read-only debug seam. Only a running module is visible.
    // These getters never call Next/Expire/HCClaim/Resolve, never claim or finish a
    // lease, and return detached rows. Runtime acceptance pending.
    static HCWorldMaterializer HCDebugGet()
    {
        if (!s_Instance || !s_Instance.m_Running) { return null; }
        return s_Instance;
    }

    int HCDebugProposalCount() { return m_Active.Count(); }

    HCDebugProposalRow HCDebugProposal(int wanted)
    {
        if (wanted < 0 || wanted >= m_Active.Count()) { return null; }
        HCWorldProposalLease lease = m_Active[wanted];
        if (!lease || !lease.Proposal) { return null; }
        HCDebugProposalRow row = new HCDebugProposalRow;
        row.Id = lease.Proposal.Id;
        row.PlaceId = lease.Proposal.PlaceId;
        row.Kind = lease.Proposal.Kind;
        row.Position = lease.Proposal.Position;
        row.ActorCap = lease.Proposal.ActorCap;
        if (lease.Claimed) { row.State = "claimed"; }
        if (lease.Finished) { row.State = "finished"; }
        if (lease.Finished && lease.Materialized) { row.State = "materialized"; }
        row.AgeSeconds = Math.Floor(m_Clock - lease.Created);
        return row;
    }

    static bool CanPropose(int active, int actors, int actorCap)
    {
        return active >= 0 && active < HCAILimits.Get().MaxMaterialized && actors >= 0 && actorCap >= 1 && actorCap <= HCAILimits.SIZE_CEILING && actors <= HCAILimits.Get().MaxLiveAI - actorCap;
    }

    static bool NoProvider(bool claimed, float age)
    {
        return !claimed && age >= HCWorldMaterializer.PROVIDER_TIMEOUT;
    }

    // Only confirmed materialized casualties debit finite faction strength.
    // Refusals/timeouts preserve strength and leave a bounded place trace.
    static bool FoldBack(HCWorldModule world, HCWorldProposal proposal, bool materialized, int survivors)
    {
        if (!world || !proposal || survivors < 0 || survivors > proposal.ActorCap) { return false; }
        if (!materialized)
        {
            if (survivors != 0) { return false; }
            if (proposal.Kind == "HOLDOUT") { return world.AddFact("holdout_traces", proposal.PlaceId, 0); }
            return world.AddFact("party_passed", proposal.PlaceId, 0);
        }
        return world.AddFact(proposal.FactionId + "_survivors_" + survivors.ToString() + "_of_" + proposal.ActorCap.ToString(), proposal.PlaceId, 1);
    }

    protected void Resolve(int leaseIndex, bool materialized, int survivors)
    {
        HCWorldProposalLease lease = m_Active[leaseIndex];
        HCWorldModule world = HCWorldModule.Get();
        // The provider has confirmed body absence. Even if a world write fails,
        // release the body budget exactly once; never retry a partial debit.
        if (lease.OutcomeApplied) { return; }
        lease.OutcomeApplied = true;
        HCAIBudget.Release(lease.Proposal.Id);
        if (lease.RowIndex >= 0 && lease.RowIndex < m_Cooldowns.Count()) { m_Cooldowns[lease.RowIndex] = m_Clock + ROW_COOLDOWN; }
        m_Active.RemoveOrdered(leaseIndex);
        if (!world || !world.GetFaction(lease.Proposal.FactionId)) { Print("[HC AI] custody fold-back unavailable world/faction runtime=PENDING"); return; }
        if (!HCWorldMaterializer.FoldBack(world, lease.Proposal, materialized, survivors)) { Print("[HC AI] custody fold-back fact failed runtime=PENDING"); return; }
        if (materialized)
        {
            if (!world.AdjustStrength(lease.Proposal.FactionId, survivors - lease.Proposal.ActorCap)) { Print("[HC AI] custody fold-back strength failed runtime=PENDING"); return; }
            m_Materialized++;
        }
        else { m_Traces++; }
    }

    protected void Expire()
    {
        int leaseIndex = m_Active.Count() - 1;
        while (leaseIndex >= 0)
        {
            if (m_Active[leaseIndex].Finished)
            {
                this.Resolve(leaseIndex, m_Active[leaseIndex].Materialized, m_Active[leaseIndex].Survivors);
            }
            else
            {
                if (HCWorldMaterializer.NoProvider(m_Active[leaseIndex].Claimed, m_Clock - m_Active[leaseIndex].Created)) { this.Resolve(leaseIndex, false, 0); }
            }
            leaseIndex -= 1;
        }
    }

    // Hands a detached place-only DTO to at most one provider. Claiming keeps
    // the slot/body reservation until Result; polling alone cannot release it.
    static bool Next(out HCWorldProposal p)
    {
        p = null;
        if (!s_Instance || !s_Instance.m_Running || !HCWorldModule.Get()) { return false; }
        s_Instance.Expire();
        foreach (HCWorldProposalLease candidate : s_Instance.m_Active)
        {
            if (candidate.Claimed || candidate.Finished) { continue; }
            HCWorldProposal copy = new HCWorldProposal;
            copy.Id = candidate.Proposal.Id;
            copy.FactionId = candidate.Proposal.FactionId;
            copy.PlaceId = candidate.Proposal.PlaceId;
            copy.Position = candidate.Proposal.Position;
            copy.ActorCap = candidate.Proposal.ActorCap;
            copy.Kind = candidate.Proposal.Kind;
            copy.Identity = candidate.Proposal.Identity;
            if (!s_Instance.HCClaim(candidate)) { continue; }
            p = copy;
            return true;
        }
        return false;
    }

    // Provider contract: call only after all owned actors have died/despawned,
    // with the number that survived. Refusal calls Result(id, false, 0).
    static void Result(string id, bool materialized, int survivors)
    {
        if (!s_Instance || !s_Instance.m_Running) { return; }
        s_Instance.HCRecordResult(id, materialized, survivors);
    }

    protected void HCRecordResult(string id, bool materialized, int survivors)
    {
        if (!m_CustodyReady || !m_Custody) { return; }
        HCAIPartyCustodyRow resultRow;
        foreach (HCAIPartyCustodyRow journalRow : m_Custody.Rows)
        {
            if (journalRow.LeaseId == id) { resultRow = journalRow; break; }
        }
        if (!resultRow) { HCAIBudget.Release(id); return; }
        if (resultRow.Outcome == "FINISHED_UNKNOWN") { HCAIBudget.Release(id); return; }
        if (resultRow.Outcome == "QUARANTINED") { return; }
        int disposition = HCAIPartyCustody.HCFinish(resultRow, materialized, survivors);
        if (disposition == 2) { HCAIBudget.Release(id); return; }
        if (disposition == 0) { HCAIBudget.Restore(id, resultRow.ActorCap); }
        if (disposition == 1 && !materialized)
        {
            // A clean refusal never owned a body or cargo; release its claim.
            m_Custody.Rows.RemoveOrdered(m_Custody.Rows.Find(resultRow));
        }
        if (!this.HCSaveCustody()) { return; }
        if (disposition == 0)
        {
            // Contradictory callbacks keep any active reservation quarantined.
            foreach (HCWorldProposalLease uncertain : m_Active)
            {
                if (uncertain.Proposal.Id == id) { uncertain.OutcomeApplied = true; }
            }
            return;
        }
        foreach (HCWorldProposalLease completed : m_Active)
        {
            if (completed.Proposal.Id != id || !completed.Claimed || completed.Finished) { continue; }
            completed.Finished = true;
            completed.Materialized = materialized;
            completed.Survivors = survivors;
            this.Expire();
            return;
        }
        HCAIBudget.Release(id);
    }

    static void HCTypedResult(HCAIPartyResult result)
    {
        if (!s_Instance || !s_Instance.m_Running || !result) { return; }
        s_Instance.HCRecordTypedResult(result);
    }

    protected void HCRecordTypedResult(HCAIPartyResult result)
    {
        if (!result || !m_CustodyReady || !m_Custody) { return; }
        HCAIPartyIdentity observed = result.HCIdentity();
        if (!HCAIPartyIdentity.HCValid(observed)) { return; }
        foreach (HCAIPartyCustodyRow typedRow : m_Custody.Rows)
        {
            if (typedRow.LeaseId != result.HCLeaseId()) { continue; }
            if (typedRow.PartyId != observed.HCPartyId() || typedRow.CampId != observed.HCCampId() || typedRow.HomeId != observed.HCHomeId() || typedRow.RouteId != observed.HCRouteId() || typedRow.CargoId != observed.HCCargoId() || typedRow.Generation != observed.HCGeneration())
            {
                // A mismatched identity is not a second population/result.
                // Reuse invalid-result quarantine without applying casualties.
                this.HCRecordResult(result.HCLeaseId(), true, -1);
                return;
            }
            this.HCRecordResult(result.HCLeaseId(), result.HCMaterialized(), result.HCSurvivors());
            return;
        }
        // Finished history may already have been evicted. Unique lease IDs
        // make this release harmless to a newer offer of the same party.
        HCAIBudget.Release(result.HCLeaseId());
    }

    protected void InterestRing()
    {
        HCWorldModule world = HCWorldModule.Get();
        if (!world || !GetGame() || !m_CustodyReady) { return; }
        int unresolvedLeases = this.HCCustodyDebt(false);
        if (m_Active.Count() + unresolvedLeases >= HCAILimits.Get().MaxMaterialized) { return; }
        array<Man> players = HCPerfPlayers.HCGet();
        int playerCount = players.Count();
        if (playerCount < 1) { return; }
        int playerWork = playerCount;
        if (playerWork > MAX_PLAYERS) { playerWork = MAX_PLAYERS; }
        array<vector> interests = new array<vector>;
        for (int playerOffset = 0; playerOffset < playerWork; playerOffset++)
        {
            if (m_PlayerCursor >= playerCount) { m_PlayerCursor = 0; }
            Man observer = players[m_PlayerCursor];
            m_PlayerCursor++;
            if (!observer || !observer.GetIdentity() || !observer.IsAlive()) { continue; }
            vector interest = observer.GetPosition();
            if (HCWorldLimits.Position(interest)) { interests.Insert(interest); }
        }
        // Player positions never leave this function or enter proposal DTOs.
        int totalRows = HCAILimits.Get().MaxHoldouts + HCAILimits.Get().MaxParties;
        m_WorkBudget.HCReset(4);
        m_UnitBudget.HCReset(4);
        for (int rowWork = 0; rowWork < ROWS_PER_RING; rowWork++)
        {
            if (m_Active.Count() + unresolvedLeases >= HCAILimits.Get().MaxMaterialized) { return; }
            if (!m_WorkBudget.HCContinue()) { m_WorkBudget.HCDeferred(GetName(), ROWS_PER_RING - rowWork); return; }
            if (!m_UnitBudget.HCTake(1)) { m_WorkBudget.HCDeferred(GetName(), ROWS_PER_RING - rowWork); return; }
            if (m_RowCursor >= totalRows) { m_RowCursor = 0; }
            int rowIndex = m_RowCursor;
            m_RowCursor++;
            if (m_Cooldowns[rowIndex] > m_Clock) { continue; }
            HCWorldProposal row = world.MaterializerRow(rowIndex);
            if (!row || !this.HCCustodyAllows(row.Identity)) { continue; }
            bool nearby = false;
            foreach (vector point : interests)
            {
                float dx = point[0] - row.Position[0];
                float dz = point[2] - row.Position[2];
                if (dx * dx + dz * dz <= 2250000) { nearby = true; break; }
            }
            if (!nearby) { continue; }
            int reservedActors = this.HCCustodyDebt(true);
            int factionActors = 0;
            bool duplicate = false;
            foreach (HCWorldProposalLease reserved : m_Active)
            {
                reservedActors += reserved.Proposal.ActorCap;
                if (reserved.Proposal.FactionId == row.FactionId) { factionActors += reserved.Proposal.ActorCap; }
                if (reserved.RowId == row.Id) { duplicate = true; }
            }
            HCWorldFaction faction = world.GetFaction(row.FactionId);
            if (!faction || duplicate || row.ActorCap + factionActors > faction.Strength || !CanPropose(m_Active.Count() + unresolvedLeases, reservedActors, row.ActorCap)) { continue; }
            HCWorldProposalLease lease = new HCWorldProposalLease;
            lease.RowId = row.Id;
            lease.RowIndex = rowIndex;
            // Persisted sequence makes callbacks unique across retries/restarts,
            // independent of the (up to 96-character) stable party identity.
            if (m_Custody.NextLease >= 2147483647) { return; }
            row.Id = "lease:" + m_Custody.NextLease.ToString();
            m_Custody.NextLease++;
            if (!HCAIBudget.TryReserve(row.Id, row.ActorCap)) { continue; }
            lease.Proposal = row;
            lease.Created = m_Clock;
            m_Active.Insert(lease);
            m_Cooldowns[rowIndex] = m_Clock + ROW_COOLDOWN;
            m_Proposals++;
        }
    }
}

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        Register(new HCWorldMaterializer);
    }
}
