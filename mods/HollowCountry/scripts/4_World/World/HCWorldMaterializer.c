// W5-PERF-6: <=4 ledger proposals/ring tick, <=2 active lease outcomes.
// Native time/player cache evidence: HCWorkBudget.c (Game.c:914/945/1535).
// LC-T402 / #98, EXP-L1 + EXP-P2. Native evidence (installed snapshot):
// scripts-1.30.164289/3_Game/Global/Game.c:945 GetPlayers;
// 3_Game/Entities/Man.c:21 GetIdentity; Entities/Object.c:287 GetPosition,
// :517 IsAlive; 1_Core/proto/EnConvert.c:30 int.ToString;
// EnScript.c:380,385,407,470 array Count/Clear/Insert/
// RemoveOrdered; EnDebug.c:96 Print. All other calls are project interfaces.
// Queue/cooldowns are process-local, never body persistence. Durable outcomes
// use HCWorldModule.AddFact and its existing verified temp/backup/copy store.
// A claimed reservation is NEVER timed out: only Result confirms body absence.
// HC has no dependency on the optional provider. No entities or inventory here.
class HCWorldProposal
{
    string Id;
    string FactionId;
    string PlaceId;
    vector Position;
    int ActorCap;
    string Kind;
}

class HCWorldProposalLease
{
    ref HCWorldProposal Proposal;
    string RowId;
    float Created;
    bool Claimed;
    bool Finished;
    bool Materialized;
    int Survivors;
}

// Narrow READ-ONLY ledger seam, authored here without editing world owners'
// files. Returns fresh proposals, never retained ledger rows. Fixed indices
// reserve [0,24) for holdouts and [24,36) for parties so additions cannot shift
// cooldowns. The place anchor is deliberately NOT a house or player position.
modded class HCWorldModule
{
    HCWorldProposal MaterializerRow(int rowIndex)
    {
        if (!m_Running || !m_Data || rowIndex < 0 || rowIndex >= HCWorldLimits.HOLDOUTS + HCWorldLimits.PARTIES) { return null; }
        HCWorldProposal row = new HCWorldProposal;
        if (rowIndex < HCWorldLimits.HOLDOUTS)
        {
            if (rowIndex >= m_Data.Holdouts.Count()) { return null; }
            HCWorldHoldout holdout = m_Data.Holdouts[rowIndex];
            if (!holdout || (holdout.State != "OCCUPIED" && holdout.State != "ALERT") || holdout.Occupants < 1) { return null; }
            row.Id = "holdout:" + holdout.Id;
            row.FactionId = holdout.FactionId;
            row.PlaceId = holdout.PlaceId;
            row.ActorCap = holdout.Occupants;
            row.Kind = "HOLDOUT";
        }
        else
        {
            int partyIndex = rowIndex - HCWorldLimits.HOLDOUTS;
            if (partyIndex >= m_Data.Parties.Count()) { return null; }
            HCWorldParty party = m_Data.Parties[partyIndex];
            if (!party || party.Materialized || !party.Route || party.Edge < 0 || party.Edge >= party.Route.Count() || party.Size < 1) { return null; }
            row.Id = "party:" + party.Id;
            row.FactionId = party.FactionId;
            row.PlaceId = party.Route[party.Edge];
            row.ActorCap = party.Size;
            row.Kind = party.Kind;
        }
        HCWorldPlace place = m_Data.Place(row.PlaceId);
        HCWorldFaction faction = m_Data.Faction(row.FactionId);
        if (!place || !faction || faction.Strength < 1) { return null; }
        row.Position = place.Position;
        if (row.ActorCap > faction.Strength) { row.ActorCap = faction.Strength; }
        if (row.ActorCap > HCWorldMaterializer.MAX_PER_PROPOSAL) { row.ActorCap = HCWorldMaterializer.MAX_PER_PROPOSAL; }
        return row;
    }
}

class HCWorldMaterializer : HCModule
{
    static const int MAX_PROPOSALS = 2;
    static const int MAX_PER_PROPOSAL = 4;
    static const int MAX_ACTORS = 8;
    static const int MAX_PLAYERS = 32;
    static const int ROWS_PER_RING = 32;
    static const int PROVIDER_TIMEOUT = 120;
    static const int RING_SECONDS = 30;
    static const int LOG_SECONDS = 600;
    static const int ROW_COOLDOWN = 21600;
    protected static HCWorldMaterializer s_Instance;
    protected static int s_Sequence;
    protected ref array<ref HCWorldProposalLease> m_Active = new array<ref HCWorldProposalLease>;
    protected ref array<float> m_Cooldowns = new array<float>;
    protected float m_Clock;
    protected float m_RingSeconds;
    protected float m_LogSeconds;
    protected int m_PlayerCursor;
    protected int m_RowCursor;
    protected ref HCWorkBudget m_WorkBudget = new HCWorkBudget;
    protected int m_Proposals;
    protected int m_Materialized;
    protected int m_Traces;
    protected bool m_Running;
    protected bool m_AdmissionPrinted;

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
        for (int cooldownIndex = 0; cooldownIndex < HCWorldLimits.HOLDOUTS + HCWorldLimits.PARTIES; cooldownIndex++) { m_Cooldowns.Insert(0); }
        m_Clock = 0;
        m_RingSeconds = 0;
        m_LogSeconds = 0;
        m_Running = true;
        s_Instance = this;
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
        }
    }

    override void OnStop()
    {
        // Mission shutdown owns provider cleanup. Unreported body outcomes are
        // not invented or replayed after restart; ledger facts remain durable.
        m_Running = false;
        if (s_Instance == this) { s_Instance = null; }
        m_Active.Clear();
    }

    static bool CanPropose(int active, int actors, int actorCap)
    {
        return active >= 0 && active < HCWorldMaterializer.MAX_PROPOSALS && actors >= 0 && actorCap >= 1 && actorCap <= HCWorldMaterializer.MAX_PER_PROPOSAL && actors <= HCWorldMaterializer.MAX_ACTORS - actorCap;
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
        if (!world || !world.GetFaction(lease.Proposal.FactionId)) { return; }
        if (!FoldBack(world, lease.Proposal, materialized, survivors)) { return; }
        // Same synchronous result consumes its reservation only after both
        // ledger mutations. No spawned body means no strength debit.
        if (materialized)
        {
            if (!world.AdjustStrength(lease.Proposal.FactionId, survivors - lease.Proposal.ActorCap)) { return; }
            m_Materialized++;
        }
        else { m_Traces++; }
        m_Active.RemoveOrdered(leaseIndex);
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
            candidate.Claimed = true;
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
        foreach (HCWorldProposalLease completed : s_Instance.m_Active)
        {
            if (completed.Proposal.Id != id || !completed.Claimed || completed.Finished) { continue; }
            if (survivors < 0 || survivors > completed.Proposal.ActorCap || (!materialized && survivors != 0)) { return; }
            completed.Finished = true;
            completed.Materialized = materialized;
            completed.Survivors = survivors;
            // Failed world admission keeps the reservation and retries on tick.
            s_Instance.Expire();
            return;
        }
    }

    protected void InterestRing()
    {
        HCWorldModule world = HCWorldModule.Get();
        if (!world || !GetGame() || m_Active.Count() >= MAX_PROPOSALS) { return; }
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
        int totalRows = HCWorldLimits.HOLDOUTS + HCWorldLimits.PARTIES;
        m_WorkBudget.HCReset(4);
        for (int rowWork = 0; rowWork < ROWS_PER_RING; rowWork++)
        {
            if (m_Active.Count() >= MAX_PROPOSALS) { return; }
            if (!m_WorkBudget.HCContinue()) { m_WorkBudget.HCDeferred(GetName(), ROWS_PER_RING - rowWork); return; }
            if (m_RowCursor >= totalRows) { m_RowCursor = 0; }
            int rowIndex = m_RowCursor;
            m_RowCursor++;
            if (m_Cooldowns[rowIndex] > m_Clock) { continue; }
            HCWorldProposal row = world.MaterializerRow(rowIndex);
            if (!row) { continue; }
            bool nearby = false;
            foreach (vector point : interests)
            {
                float dx = point[0] - row.Position[0];
                float dz = point[2] - row.Position[2];
                if (dx * dx + dz * dz <= 2250000) { nearby = true; break; }
            }
            if (!nearby) { continue; }
            int reservedActors = 0;
            int factionActors = 0;
            bool duplicate = false;
            foreach (HCWorldProposalLease reserved : m_Active)
            {
                reservedActors += reserved.Proposal.ActorCap;
                if (reserved.Proposal.FactionId == row.FactionId) { factionActors += reserved.Proposal.ActorCap; }
                if (reserved.RowId == row.Id) { duplicate = true; }
            }
            HCWorldFaction faction = world.GetFaction(row.FactionId);
            if (!faction || duplicate || row.ActorCap + factionActors > faction.Strength || !CanPropose(m_Active.Count(), reservedActors, row.ActorCap)) { continue; }
            HCWorldProposalLease lease = new HCWorldProposalLease;
            lease.RowId = row.Id;
            s_Sequence++;
            row.Id = "materializer:" + world.Epoch().ToString() + ":" + s_Sequence.ToString();
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
