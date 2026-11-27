// Row cursor native evidence: 1_Core/proto/EnScript.c:380 Count, :399 Get.
// HC-37 / #146 supersedes LC-T411's abstract casualty/claim roll.
// One pre-bound body/tick; shared HCWorkBudget + HCUnitBudget. No discovery,
// targeting controller, player hunt, body/item creation or inventory mutation.
// scripts-1.30.164289 native references (inspected locally):
// 3_Game/Global/Game.c:1120 IsServer; Entities/Object.c:517 IsAlive;
// 1_Core/proto/EnMath.c:427 Floor, :553 Min; EnConvert.c:30 int.ToString;
// EnScript.c:380,385,394,407 arrays; EnDebug.c:96 Print;
// 3_Game/tools/JsonFileLoader.c:69,85 LoadData/MakeData (detached fact copy).
// Wave 16: ready means started, outcome store loaded, tick running. A missing combat
// provider or an unsurveyed pair is a wait (HCDecline, logged once per reason), never a
// refusal; only store faults and contradictory actor state refuse.
// The journal is written by the shared save scheduler through HCEncounterStore;
// startup load/recovery stays synchronous before jobs register.
// Deaths reach HC-16 through its existing real EEKilled hook, never a second
// debit from this journal. Native targeting/disengage/cargo acceptance PENDING.
class HCConflictReadiness
{
    // Honest state words for the ready status: which provider facts hold right now.
    static string HCConflictReadinessReason(bool portBound, bool pairBound)
    {
        if (!portBound) { return "provider_absent_base_only"; }
        if (!pairBound) { return "awaiting_surveyed_opposed_pair"; }
        return "surveyed_pair_bound_observation_only";
    }
}

// One volatile continuation: a crash spends quota without replaying an effect.
class HCConflictPendingOutcome
{
    string Kind;
    string PlaceId;
    string Cell;
    string LeftFaction;
    string RightFaction;
    string WinnerFaction;
    string LoserFaction;
    float Since = -1;
    bool Warned;
    bool Fixture;
    int Revision;
}

class HCConflictQuotaSaveJob : HCSaveJob
{
    // HCModule is not Managed: weak Owner never auto-nulls. OnStop must unregister first.
    HCFactionConflict Owner;
    override string HCName() { return "FactionConflictQuota"; }
    override float HCInterval() { return 0; }
    override bool HCPendingCheckpoint() { return Owner && Owner.HCQuotaPendingCheckpoint(); }
    override int HCStep()
    {
        if (!Owner) { return STEP_FAILED; }
        return Owner.HCStepQuota();
    }
}

class HCConflictOutcomeSaveJob : HCSaveJob
{
    // HCModule is not Managed: weak Owner never auto-nulls. OnStop must unregister first.
    HCFactionConflict Owner;
    override string HCName() { return "FactionConflictOutcomes"; }
    override float HCInterval() { return 0; }
    override bool HCPendingCheckpoint() { return Owner && Owner.HCOutcomesPendingCheckpoint(); }
    override int HCStep()
    {
        if (!Owner) { return STEP_FAILED; }
        return Owner.HCStepOutcomes();
    }
}

// One pass owns its maps and commits before yielding. Validated limits: <=64
// places/held cells, <=128 journal rows, one lease scan and one Facts scan;
// candidate geometry does at most P*P <=4096 horizontal distance checks.
// Native EnScript.c:866/906/917 map Get/Remove/Contains; EnString.c:396 Split.
class HCTerritoryRegrowth
{
    ref array<string> Cells = new array<string>;
    ref array<string> CellOf = new array<string>;
    ref map<string, string> PlaceCells = new map<string, string>;
    ref map<string, bool> Catalog = new map<string, bool>;
    ref map<string, bool> Homes = new map<string, bool>;
    ref map<string, bool> Held = new map<string, bool>;
    ref map<string, bool> Protected = new map<string, bool>;
    ref map<string, bool> Cooldown = new map<string, bool>;
    ref map<string, bool> Hostile = new map<string, bool>;
    protected static ref map<string, string> s_Released = new map<string, string>;
    protected static ref map<string, string> s_Wait = new map<string, string>;
    protected static ref map<string, int> s_StrengthAt = new map<string, int>;
    string Reclaimed = "none";
    string Shifted = "none";
    string Released = "none";
    bool Blocked;

    static bool Home(string faction, int index)
    {
        if (faction == "locals") { return index % 4 == 0; }
        if (faction == "volunteers") { return index % 4 == 1; }
        if (faction == "scavengers") { return index % 4 == 2; }
        if (faction == "travellers") { return index % 4 == 3; }
        return faction == "raiders" && index % 3 == 1;
    }

    static void HCWait(string faction, string reason)
    {
        if (s_Wait.Get(faction) == reason) { return; }
        s_Wait.Set(faction, reason);
        if (reason != "") { Print("[HC World] territory_regrow_wait faction=" + faction + " reason=" + reason); }
    }

    static bool StrengthDue(string faction, int now, int interval)
    {
        int previous = s_StrengthAt.Get(faction);
        if (previous > now) { s_StrengthAt.Set(faction, now); return false; }
        if (previous > 0 && now - previous < interval) { return false; }
        s_StrengthAt.Set(faction, now);
        return true;
    }

    void Build(HCWorldData data, HCWorldFaction faction, int now)
    {
        for (int placeIndex = 0; placeIndex < data.Places.Count(); placeIndex++)
        {
            HCWorldPlace place = data.Places[placeIndex];
            string cell = HCFactionConflict.Cell(place.Position);
            CellOf.Insert(cell);
            if (!Catalog.Contains(cell)) { Cells.Insert(cell); Catalog.Set(cell, true); }
            // First Id-or-Name match, exactly as HCWorldData.Place, including aliases.
            if (!PlaceCells.Contains(place.Id)) { PlaceCells.Set(place.Id, cell); }
            if (!PlaceCells.Contains(place.Name)) { PlaceCells.Set(place.Name, cell); }
            if (Home(faction.Id, placeIndex)) { Homes.Set(cell, true); }
        }
        array<string> territory = faction.Territory;
        foreach (string heldCell : territory) { Held.Set(heldCell, true); }
        map<string, bool> cooldownPlaces = new map<string, bool>;
        array<ref HCWorldFact> facts = data.Facts;
        foreach (HCWorldFact fact : facts)
        {
            if (fact.At > now) { continue; }
            if (fact.Kind != "faction_clash" && fact.Kind != "camp_infected_pressure") { continue; }
            if (now - fact.At < 604800) { cooldownPlaces.Set(fact.PlaceId, true); }
        }
        for (int cooldownIndex = 0; cooldownIndex < data.Places.Count(); cooldownIndex++)
        {
            HCWorldPlace cooldownPlace = data.Places[cooldownIndex];
            if (cooldownPlaces.Contains(cooldownPlace.Id) || cooldownPlaces.Contains(cooldownPlace.Name)) { Cooldown.Set(CellOf[cooldownIndex], true); }
        }
        map<string, bool> hostileFactions = new map<string, bool>;
        array<string> hostileIds = faction.Hostile;
        foreach (string hostileId : hostileIds) { hostileFactions.Set(hostileId, true); }
        array<ref HCWorldFaction> factions = data.Factions;
        foreach (HCWorldFaction other : factions)
        {
            if (other.Id == faction.Id || !hostileFactions.Contains(other.Id)) { continue; }
            bool reciprocal = false;
            // HCWorldLimits.FACTIONS is five; explicit bound also covers imported lists.
            for (int relationIndex = 0; relationIndex < 5 && relationIndex < other.Hostile.Count(); relationIndex++)
            {
                if (other.Hostile[relationIndex] == faction.Id) { reciprocal = true; }
            }
            if (!reciprocal) { continue; }
            array<string> otherTerritory = other.Territory;
            foreach (string hostileCell : otherTerritory) { Hostile.Set(hostileCell, true); }
        }
    }

    bool ProtectPlace(string place)
    {
        if (!PlaceCells.Contains(place)) { return false; }
        Protected.Set(PlaceCells.Get(place), true);
        return true;
    }

    // Reduced terms avoid overflow, and catalog order breaks rotated ties.
    static int Rotation(int day, int now, int interval, int factionIndex, int count)
    {
        if (count < 1) { return 0; }
        int period = now / interval;
        return (day % count + period % count + factionIndex % count) % count;
    }

    bool Choose(HCWorldData data, HCWorldFaction faction, int rotation, int staleRotation, int extra)
    {
        if (Cells.Count() > HCWorldLimits.PLACES) { return false; }
        int heldCount = faction.Territory.Count();
        for (int staleStep = 0; staleStep < heldCount; staleStep++)
        {
            int staleIndex = (staleStep + staleRotation) % heldCount;
            string staleCell = faction.Territory[staleIndex];
            if (Catalog.Contains(staleCell)) { continue; }
            if (Protected.Contains(staleCell)) { Blocked = true; continue; }
            faction.Territory.RemoveOrdered(staleIndex);
            Released = staleCell;
            s_Released.Set(faction.Id, staleCell);
            return true;
        }
        int target = Math.Min(HCWorldLimits.TERRITORY, Math.Min(Cells.Count(), Homes.Count() + extra));
        string reclaim = "";
        int reclaimRank = 99;
        bool missingHome = false;
        for (int homeStep = 0; homeStep < Cells.Count(); homeStep++)
        {
            string homeCell = Cells[(homeStep + rotation) % Cells.Count()];
            if (!Homes.Contains(homeCell) || Held.Contains(homeCell)) { continue; }
            missingHome = true;
            if (Protected.Contains(homeCell)) { Blocked = true; continue; }
            int homeRank = 1;
            if (Hostile.Contains(homeCell)) { homeRank = 0; }
            if (Cooldown.Contains(homeCell)) { homeRank += 2; }
            if (homeRank < reclaimRank) { reclaimRank = homeRank; reclaim = homeCell; }
        }
        if (reclaim != "" && heldCount < HCWorldLimits.TERRITORY)
        {
            faction.Territory.Insert(reclaim);
            Reclaimed = reclaim;
            return true;
        }
        // No capacity exception: full holdings use the same release branch.
        if (missingHome && heldCount < HCWorldLimits.TERRITORY) { return false; }
        bool adding = !missingHome && heldCount < target;
        string chosen = "";
        float chosenDistance = -1;
        int chosenCooldown = 2;
        string lastReleased = s_Released.Get(faction.Id);
        for (int candidateStep = 0; candidateStep < Cells.Count(); candidateStep++)
        {
            string candidate = Cells[(candidateStep + rotation) % Cells.Count()];
            if (adding)
            {
                if (Held.Contains(candidate) || candidate == lastReleased) { continue; }
            }
            else
            {
                if (!Held.Contains(candidate) || Homes.Contains(candidate)) { continue; }
            }
            if (Protected.Contains(candidate)) { Blocked = true; continue; }
            float nearest = -1;
            // Aliases all contribute geometry; across every candidate <=P^2 checks.
            for (int sourceIndex = 0; sourceIndex < data.Places.Count(); sourceIndex++)
            {
                if (CellOf[sourceIndex] != candidate) { continue; }
                vector source = data.Places[sourceIndex].Position;
                source[1] = 0;
                for (int anchorIndex = 0; anchorIndex < data.Places.Count(); anchorIndex++)
                {
                    string anchorCell = CellOf[anchorIndex];
                    if (adding && !Held.Contains(anchorCell)) { continue; }
                    if (!adding && !Homes.Contains(anchorCell)) { continue; }
                    vector anchor = data.Places[anchorIndex].Position;
                    anchor[1] = 0;
                    float distance = vector.DistanceSq(source, anchor);
                    if (nearest < 0 || distance < nearest) { nearest = distance; }
                }
            }
            if (nearest < 0) { continue; }
            int cooling = 0;
            if (Cooldown.Contains(candidate)) { cooling = 1; }
            bool better = chosen == "";
            if (adding && (cooling < chosenCooldown || (cooling == chosenCooldown && nearest < chosenDistance))) { better = true; }
            if (!adding && nearest > chosenDistance) { better = true; }
            if (better) { chosen = candidate; chosenDistance = nearest; chosenCooldown = cooling; }
        }
        if (chosen == "")
        {
            // Consume one unprotected add attempt even when exclusion leaves no
            // candidate: a catalog-sized target must not strand its sole free cell.
            if (adding && !Blocked) { s_Released.Remove(faction.Id); }
            return false;
        }
        if (adding)
        {
            faction.Territory.Insert(chosen);
            Shifted = chosen;
            s_Released.Remove(faction.Id);
        }
        else
        {
            faction.Territory.RemoveOrdered(faction.Territory.Find(chosen));
            Released = chosen;
            s_Released.Set(faction.Id, chosen);
        }
        return true;
    }
}

class HCFactionConflict : HCModule
{
    protected static HCFactionConflict s_Instance;
    protected static ref HCFactionCombatPort s_CombatPort;
    protected static bool s_Active;
    protected static int s_WorkNow = -1;
    protected static int s_GrowthNext;
    protected static ref HCWorkBudget s_WorkBudget = new HCWorkBudget;
    protected static ref HCUnitBudget s_UnitBudget = new HCUnitBudget;
    protected ref HCEncounterStore<HCTerritoryOutcomeData> m_Store;
    protected ref HCTerritoryOutcomeData m_Outcomes;
    protected HCTerritoryOutcomeRow m_Current;
    protected ref array<Object> m_LeftActors = new array<Object>;
    protected ref array<Object> m_RightActors = new array<Object>;
    protected ref HCUnitBudget m_Units = new HCUnitBudget;
    protected ref HCWorkBudget m_Work = new HCWorkBudget;
    protected ref HCOperationalStatus m_Operational = new HCOperationalStatus;
    protected bool m_Healthy;
    protected string m_Refusal;
    protected ref HCConflictConfig m_ConflictConfig;
    protected int m_OutcomeCursor;
    protected ref HCEncounterStore<HCConflictQuota> m_QuotaStore;
    protected ref HCConflictQuota m_Quota;
    protected ref HCConflictQuotaSaveJob m_QuotaJob;
    protected ref HCConflictPendingOutcome m_PendingQuota;
    protected int m_QuotaRequested;
    protected int m_QuotaCheckpoint;
    protected int m_QuotaDurable;
    // Both fallback pumps share m_QuotaStepTime/m_QuotaStepBudget, reset once per tick; quota first.
    protected float m_QuotaStepTime = -1;
    protected ref HCWorkBudget m_QuotaStepBudget = new HCWorkBudget;
    protected ref HCConflictOutcomeSaveJob m_OutcomeJob;
    protected int m_OutcomeRequested;
    protected int m_OutcomeCheckpoint;
    protected int m_OutcomeDurable;
    protected int m_BindRevision;
    protected int m_FinishRevision;
    // Weak: m_Outcomes.Rows owns this row and is never pruned, like m_Current.
    protected HCTerritoryOutcomeRow m_PendingBind;
    protected float m_OutcomeSince = -1;
    protected bool m_OutcomeWarned;
    protected float m_OutcomeStepTime = -1;
    protected string m_Declined;
    protected string m_StatusReason;
    protected bool m_ProviderLogged;
    // Volatile identity only: recovery must never resume a synthetic fixture.
    protected string m_FixtureEncounter;
    protected bool m_FixtureJournalRan;
    protected int m_FixtureAppliedRevision;
    protected int m_ActorCursor;
    protected int m_CallbackFrame = -1;
    protected ref HCUnitBudget m_CallbackUnits = new HCUnitBudget;

    override string GetName() { return "FactionConflict"; }
    override int StartupPhase() { return HC_PHASE_FEATURE; }
    override void RegisterUses()
    {
        HCModuleReadiness.HCRegisterUse("FactionConflict", "outcome_recorded");
        HCModuleReadiness.HCRegisterUse("FactionConflict", "journal_committed");
        HCModuleReadiness.HCRegisterUse("FactionConflict", "territory_regrowth");
    }
    override HCOperationalStatus HCGetOperationalStatus()
    {
        string fault = "";
        if (s_Active && m_Healthy && !HCWorldModule.Get()) { fault = "world_owner_unavailable"; }
        HCModuleReadiness.HCDerive(m_Operational, s_Active && m_Healthy, m_Refusal, fault, m_StatusReason);
        return m_Operational;
    }
    override bool IsEnabled(HCSettings settings) { return settings && settings.EnableEncounters; }
    override void OnStart(HCSettings settings)
    {
        if (s_Active) { HCLog(m_Current, "requested", "ALREADY_STARTED"); return; }
        if (!IsEnabled(settings))
        {
            m_Operational.HCPublish("off", "operator_preference");
            HCLog(null, "off", "OPERATOR_PREFERENCE");
            return;
        }
        if (!GetGame() || !GetGame().IsServer()) { HCRefuse("SERVER_AUTHORITY_REQUIRED"); return; }
        Print(HCV2Admission.Line("FactionConflict", true, "EXP-S4", HCV2Gates.Qualified("EXP-S4")));
        m_Refusal = "";
        m_FixtureEncounter = "";
        m_FixtureJournalRan = false;
        m_FixtureAppliedRevision = 0;
        m_OutcomeRequested = 0;
        m_OutcomeCheckpoint = 0;
        m_OutcomeDurable = 0;
        m_PendingBind = null;
        m_BindRevision = 0;
        m_FinishRevision = 0;
        m_OutcomeSince = -1;
        m_OutcomeWarned = false;
        m_OutcomeStepTime = -1;
        m_ConflictConfig = HCConflictConfig.HCLoad();
        if (!m_ConflictConfig) { HCRefuse("CONFLICT_CONFIG_INVALID"); return; }
        if (!m_ConflictConfig.Enabled) { m_Operational.HCPublish("off", "conflict_operator_off"); return; }
        m_QuotaStore = new HCEncounterStore<HCConflictQuota>("faction-conflict-quota");
        HCConflictQuota freshQuota = new HCConflictQuota;
        // Load's fresh/recovery save is synchronous BEFORE job registration.
        // After registration only SaveStep may advance quota images/revisions.
        m_Quota = m_QuotaStore.Load(freshQuota, "Rows");
        string quotaText = m_QuotaStore.HCTakeLoadedText();
        if (!HCConflictQuota.HCValid(m_Quota, quotaText)) { HCRefuse("CONFLICT_QUOTA_INVALID"); return; }
        m_QuotaRequested = 0;
        m_QuotaCheckpoint = 0;
        m_QuotaDurable = 0;
        m_PendingQuota = null;
        m_QuotaStepTime = -1;
        s_Active = true;
        s_WorkNow = -1;
        s_Instance = this;
        m_Store = new HCEncounterStore<HCTerritoryOutcomeData>("faction-outcomes");
        HCTerritoryOutcomeData freshOutcomes = new HCTerritoryOutcomeData;
        m_Outcomes = m_Store.Load(freshOutcomes, "Rows");
        m_Healthy = HCTerritoryOutcomes.HCValid(m_Outcomes);
        string loadedText = m_Store.HCTakeLoadedText();
        // A row missing a survivor key zero-fills to 0 and reads as NONE_REMAIN (#188).
        if (m_Healthy && loadedText != "" && !HCTerritoryOutcomes.HCFieldsPresent(loadedText))
        {
            m_Healthy = false;
            HCRefuse("OUTCOME_STORE_FIELDS_MISSING");
            return;
        }
        if (!m_Healthy) { HCRefuse("OUTCOME_STORE_INVALID"); return; }
        if (HCTerritoryOutcomes.HCRecover(m_Outcomes) > 0 && !HCSaveBeforeJobs())
        {
            HCRefuse("RESTART_OUTCOME_STORE_UNCERTAIN");
            return;
        }
        m_QuotaJob = new HCConflictQuotaSaveJob;
        m_QuotaJob.Owner = this;
        m_QuotaJob.HCUrgent = true;
        HCSaveScheduler.HCRegister(m_QuotaJob);
        m_OutcomeJob = new HCConflictOutcomeSaveJob;
        m_OutcomeJob.Owner = this;
        HCSaveScheduler.HCRegister(m_OutcomeJob);
    }

    override void OnAllModulesStarted()
    {
        if (s_Instance != this || !m_Healthy || m_Refusal != "") { return; }
        // The addon has installed its combat port; derive the actual provider
        // status before core captures the first readiness receipt.
        HCRefreshStatus();
        string raidReason = HCCampRaidActors.HCGet().HCRefusal();
        Print("[HC Plan] HC-37 raids=delegated_to_HC39 reason=" + raidReason + " runtime=PENDING");
        Print("[HC Plan] HC-37 camp_population_outcome=owner_required data_pressure=enabled runtime=PENDING");
    }

    // Derives the ready reason from the real port/pair state; publishes only on change.
    void HCRefreshStatus()
    {
        if (!s_Active || !m_Healthy) { return; }
        if (!m_ProviderLogged)
        {
            m_ProviderLogged = true;
            if (s_CombatPort) { Print("[HC Plan] HC-37 provider=bound pair=surveyed_opposed_only runtime=PENDING"); }
            else { Print("[HC Plan] HC-37 provider=absent reason=expansion_ai_addon_not_loaded pair=none runtime=PENDING"); }
        }
        bool bound = false;
        if (s_CombatPort) { bound = true; }
        bool paired = false;
        if (m_Current) { paired = true; }
        string reason = HCConflictReadiness.HCConflictReadinessReason(bound, paired);
        if (reason == m_StatusReason) { return; }
        m_StatusReason = reason;
        m_Operational.HCPublish("ready", reason);
        HCLog(m_Current, "ready", reason);
    }

    protected void HCServiceWorld()
    {
        HCResetFallbackBudget();
        HCPumpQuotaFallback();
        HCPumpOutcomeFallback();
        if (!HCPollQuotaFault()) { return; }
        if (!HCPollOutcomeFault()) { return; }
        HCWarnStalls();
        HCApplyQuotaOutcome();
        if (!HCOutcomesCommitted()) { return; }
        if (m_FixtureAppliedRevision > 0 && m_OutcomeDurable >= m_FixtureAppliedRevision)
        {
            Print("[HC Plan] HC-37 fixture_journal_applied encounter=" + m_FixtureEncounter + " requested=" + m_FixtureAppliedRevision.ToString() + " durable=" + m_OutcomeDurable.ToString() + " fixture=1");
            m_FixtureAppliedRevision = 0;
            // Done: later finishes no longer wait behind the fixture row; m_FixtureJournalRan keeps it once per boot.
            m_FixtureEncounter = "";
        }
        HCPromoteBind();
        HCWorldModule world = HCWorldModule.Get();
        if (!world || !m_ConflictConfig) { return; }
        // Retry at most one durable receipt per tick, rotating even when viewers
        // keep its site pending. Unrelated sites still receive their normal step.
        if (m_OutcomeCursor >= m_Outcomes.Rows.Count()) { m_OutcomeCursor = 0; }
        if (m_OutcomeCursor < m_Outcomes.Rows.Count())
        {
            HCTerritoryOutcomeRow outcome = m_Outcomes.Rows[m_OutcomeCursor];
            m_OutcomeCursor++;
            // Complete the fixture's durable finish receipt before its applied receipt.
            bool fixtureFinishPending = outcome.Id == m_FixtureEncounter && m_FinishRevision > 0;
            if (!fixtureFinishPending && outcome.TerritoryEpoch > 0 && !outcome.TerritoryApplied && outcome.LeftSurvivors >= 0)
            {
                if (!world.HCConflictObserved(outcome, m_ConflictConfig)) { HCDecline("TERRITORY_PUBLICATION_PENDING"); }
                else
                {
                    outcome.TerritoryApplied = true;
                    int appliedRevision = HCRequestSave();
                    if (outcome.Id == m_FixtureEncounter) { m_FixtureAppliedRevision = appliedRevision; }
                    return;
                }
            }
        }
        if (m_Current)
        {
            if (m_Current.TerritoryEpoch == 0)
            {
                m_Current.TerritoryEpoch = HCWorldClock.UTC();
                HCRequestSave();
                return;
            }
            HCFinishObserved(m_Current.Id);
            return;
        }
        world.HCConflictStep(m_ConflictConfig, s_CombatPort);
    }

    static bool HCFixtureConflict(vector pos, bool apply, out string reason)
    {
        reason = "conflict-owner-unavailable";
        HCWorldModule world = HCWorldModule.Get();
        if (!s_Active || !s_Instance || !s_Instance.m_Healthy || !world) { return false; }
        return world.HCFixtureConflict(pos, apply, s_Instance.m_ConflictConfig, s_CombatPort, reason);
    }

    // Lead-only journal drive; probes validate detached rows without consuming callback work.
    static bool HCFixtureConflictJournal(vector pos, bool apply, out string reason)
    {
        reason = "EnableSmokeFixtures-off";
        if (!HCAdminFixtures.HCEnabled()) { return false; }
        reason = "conflict-owner-unavailable";
        HCWorldModule world = HCWorldModule.Get();
        if (!s_Active || !s_Instance || !world) { return false; }
        return s_Instance.HCBindFixture(world, pos, apply, reason);
    }

    protected bool HCBindFixture(HCWorldModule world, vector pos, bool apply, out string reason)
    {
        reason = "conflict-owner-unavailable";
        if (!m_Healthy || m_Refusal != "" || !m_OutcomeJob || m_OutcomeJob.HCFaulted || !m_ConflictConfig || !m_Outcomes) { return false; }
        reason = "conflict-journal-busy";
        if (!HCOutcomesCommitted() || m_OutcomeJob.HCDirty || m_Current || m_PendingBind || m_BindRevision > 0 || m_FinishRevision > 0 || m_PendingQuota) { return false; }
        reason = "fixture-journal-once";
        if (m_FixtureJournalRan) { return false; }
        reason = "journal-history-headroom";
        if (m_Outcomes.Rows.Count() >= HCTerritoryOutcomes.MAX_ROWS - 32) { return false; }
        string place;
        string opposed;
        bool forced;
        string selectionCounts;
        if (!world.HCFixtureJournalPlace(pos, m_ConflictConfig, place, opposed, forced, selectionCounts, reason)) { return false; }
        HCTerritoryOutcomeRow fixtureRow = new HCTerritoryOutcomeRow;
        string suffix = m_Outcomes.NextEncounter.ToString();
        fixtureRow.Id = "conflict:" + suffix;
        fixtureRow.PlaceId = place;
        fixtureRow.Survey = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";
        fixtureRow.LeftLease = "fixture-left:" + suffix;
        fixtureRow.RightLease = "fixture-right:" + suffix;
        fixtureRow.LeftParty = fixtureRow.LeftLease;
        fixtureRow.RightParty = fixtureRow.RightLease;
        fixtureRow.LeftCargo = fixtureRow.LeftLease;
        fixtureRow.RightCargo = fixtureRow.RightLease;
        fixtureRow.Generation = 1;
        fixtureRow.LeftFaction = "raiders";
        fixtureRow.RightFaction = opposed;
        fixtureRow.LeftDead.Insert(false);
        fixtureRow.LeftDead.Insert(false);
        fixtureRow.RightDead.Insert(false);
        reason = "fixture-row-invalid";
        if (fixtureRow.LeftFaction != "raiders" || HCWorldFactionCatalog.Relation(fixtureRow.LeftFaction, fixtureRow.RightFaction) != -1) { return false; }
        if (!HCWorldLimits.Token(fixtureRow.Id) || !HCWorldLimits.Token(fixtureRow.PlaceId) || !HCWorldLimits.Token(fixtureRow.LeftFaction) || !HCWorldLimits.Token(fixtureRow.RightFaction)) { return false; }
        if (!HCWorldLimits.Token(fixtureRow.LeftLease) || !HCWorldLimits.Token(fixtureRow.RightLease)) { return false; }
        if (!HCWorldLimits.Token(fixtureRow.LeftParty) || !HCWorldLimits.Token(fixtureRow.RightParty)) { return false; }
        if (!HCWorldLimits.Token(fixtureRow.LeftCargo) || !HCWorldLimits.Token(fixtureRow.RightCargo)) { return false; }
        // Validate the entire prospective image BEFORE touching the owner's journal.
        HCTerritoryOutcomeData prospective = new HCTerritoryOutcomeData;
        array<ref HCTerritoryOutcomeRow> priorRows = m_Outcomes.Rows;
        foreach (HCTerritoryOutcomeRow priorRow : priorRows) { prospective.Rows.Insert(priorRow); }
        prospective.Rows.Insert(fixtureRow);
        prospective.NextEncounter = m_Outcomes.NextEncounter + 1;
        if (!HCTerritoryOutcomes.HCValid(prospective)) { return false; }
        reason = "fixture-journal-available";
        if (!apply) { return true; }
        reason = "conflict-callback-budget";
        if (!HCCallbackAllowed()) { return false; }
        m_Outcomes.Rows.Insert(fixtureRow);
        m_Outcomes.NextEncounter++;
        m_FixtureEncounter = fixtureRow.Id;
        m_FixtureJournalRan = true;
        int fixtureRevision = HCRequestSave();
        reason = "OUTCOME_STORE_UNCERTAIN";
        if (fixtureRevision == 0) { return false; }
        m_PendingBind = fixtureRow;
        m_BindRevision = fixtureRevision;
        m_LeftActors.Clear();
        m_RightActors.Clear();
        m_ActorCursor = 0;
        m_Declined = "RECEIPT_PENDING";
        string forcedSuffix = "";
        if (forced) { forcedSuffix = " forced=1"; }
        Print("[HC Plan] HC-37 fixture_journal_bound encounter=" + fixtureRow.Id + " place=" + fixtureRow.PlaceId + " left=raiders right=" + fixtureRow.RightFaction + " fixture=1" + forcedSuffix);
        HCLog(fixtureRow, "ready", "RECEIPT_PENDING");
        reason = "fixture-journal-queued";
        if (forced) { reason += " forced=1" + selectionCounts; }
        return true;
    }

    // Read only the validated <=128-row journal. Pending sites cannot produce
    // another fight or pressure outcome before their territory receipt publishes.
    static bool HCTerritoryPending(string place)
    {
        if (!s_Instance || !s_Instance.m_Outcomes) { return false; }
        array<ref HCTerritoryOutcomeRow> rows = s_Instance.m_Outcomes.Rows;
        foreach (HCTerritoryOutcomeRow row : rows)
        {
            if (row.PlaceId == place && row.TerritoryEpoch > 0 && !row.TerritoryApplied && row.LeftSurvivors >= 0) { return true; }
        }
        return false;
    }

    // fx_conflict selection only: the journal fixture's place stays reserved until its row is applied, so the
    // two fixtures never share one place (otherwise the normal step drops fx_conflict silently).
    static bool HCFixtureJournalHolds(string place)
    {
        if (!s_Instance || !s_Instance.m_Outcomes || s_Instance.m_FixtureEncounter == "") { return false; }
        array<ref HCTerritoryOutcomeRow> journalRows = s_Instance.m_Outcomes.Rows;
        foreach (HCTerritoryOutcomeRow journalRow : journalRows)
        {
            if (journalRow.Id == s_Instance.m_FixtureEncounter && journalRow.PlaceId == place && !journalRow.TerritoryApplied) { return true; }
        }
        return false;
    }

    static bool HCQuotaOutcomePending()
    {
        return s_Instance && s_Instance.m_PendingQuota;
    }

    static bool HCReserveDataOutcome(HCConflictPendingOutcome pending, int now)
    {
        if (!s_Active || !s_Instance || !s_Instance.m_Healthy || !pending || HCQuotaOutcomePending()) { return false; }
        if (!s_Instance.HCPollQuotaFault()) { return false; }
        if (!HCConflictQuota.HCReserve(s_Instance.m_Quota, s_Instance.m_ConflictConfig, pending.PlaceId, now)) { return false; }
        s_Instance.m_QuotaRequested++;
        pending.Revision = s_Instance.m_QuotaRequested;
        pending.Since = GetGame().GetTickTime();
        s_Instance.m_PendingQuota = pending;
        s_Instance.m_QuotaJob.HCDirty = true;
        s_Instance.m_QuotaJob.HCUrgent = true;
        s_Instance.m_QuotaJob.HCDue = GetGame().GetTickTime();
        return true;
    }

    bool HCQuotaPendingCheckpoint() { return m_QuotaDurable != m_QuotaRequested; }

    int HCStepQuota()
    {
        if (!m_QuotaStore || !m_Quota) { return HCSaveJob.STEP_FAILED; }
        bool starting = !m_QuotaStore.SaveInFlight();
        if (starting) { m_QuotaCheckpoint = m_QuotaRequested; }
        int result = m_QuotaStore.SaveStep(m_Quota);
        if (result == HCSaveJob.STEP_DONE) { m_QuotaDurable = m_QuotaCheckpoint; }
        return result;
    }

    protected void HCResetFallbackBudget()
    {
        float now = GetGame().GetTickTime();
        if (now != m_QuotaStepTime)
        {
            m_QuotaStepTime = now;
            m_QuotaStepBudget.HCReset(HCWorldRuntimeConfig.HCGet().SaveStagesPerTick, HCPerfConfig.HCGet().SaveStageTargetMs);
        }
    }

    protected void HCPumpQuotaFallback()
    {
        if (!m_QuotaJob || m_QuotaJob.HCFaulted || !m_QuotaJob.HCDirty || !m_QuotaJob.HCUrgent) { return; }
        if (HCPerfConfig.HCGet().EnableSharedSaves && HCSaveScheduler.HCRegistered(m_QuotaJob)) { return; }
        if (m_QuotaStepBudget.HCContinue()) { HCSaveScheduler.HCPumpFallback(m_QuotaJob); }
    }

    protected void HCPumpOutcomeFallback()
    {
        if (!m_OutcomeJob || m_OutcomeJob.HCFaulted || !m_OutcomeJob.HCDirty || !m_OutcomeJob.HCUrgent) { return; }
        if (HCPerfConfig.HCGet().EnableSharedSaves && HCSaveScheduler.HCRegistered(m_OutcomeJob)) { return; }
        float outcomeNow = GetGame().GetTickTime();
        if (m_OutcomeStepTime == outcomeNow) { return; }
        m_OutcomeStepTime = outcomeNow;
        if (m_QuotaStepBudget.HCContinue()) { HCSaveScheduler.HCPumpFallback(m_OutcomeJob); }
    }

    protected bool HCPollOutcomeFault()
    {
        if (!m_OutcomeJob || !m_OutcomeJob.HCFaulted) { return true; }
        if (m_Healthy) { HCRefuse("OUTCOME_STORE_UNCERTAIN"); }
        return false;
    }

    bool HCOutcomesPendingCheckpoint() { return m_Healthy && m_OutcomeDurable != m_OutcomeRequested; }
    protected bool HCOutcomesCommitted() { return m_OutcomeDurable == m_OutcomeRequested; }

    int HCStepOutcomes()
    {
        if (!m_Store || !m_Outcomes) { return HCSaveJob.STEP_FAILED; }
        bool starting = !m_Store.SaveInFlight();
        if (starting)
        {
            if (!m_Healthy) { return HCSaveJob.STEP_FAILED; }
            m_OutcomeCheckpoint = m_OutcomeRequested;
        }
        // One unmeasured MakeData encode, <=128 rows / 256 KiB, cannot be preempted.
        // SaveStep freezes at encode; later requests belong to the next image.
        int result = m_Store.SaveStep(m_Outcomes);
        if (result == HCSaveJob.STEP_DONE)
        {
            m_OutcomeDurable = m_OutcomeCheckpoint;
            if (HCOutcomesCommitted()) { m_OutcomeSince = -1; m_OutcomeWarned = false; }
        }
        return result;
    }

    protected void HCWarnStalls()
    {
        float now = GetGame().GetTickTime();
        if (m_PendingQuota && !m_PendingQuota.Warned && m_PendingQuota.Since >= 0 && now - m_PendingQuota.Since >= 60)
        {
            m_PendingQuota.Warned = true;
            Print("[HC Plan] HC-37 data_outcome_waiting place=" + m_PendingQuota.PlaceId + " age_s=" + (now - m_PendingQuota.Since).ToString() + " requested=" + m_QuotaRequested.ToString() + " durable=" + m_QuotaDurable.ToString() + " runtime=PENDING");
        }
        if (!HCOutcomesCommitted() && !m_OutcomeWarned && m_OutcomeSince >= 0 && now - m_OutcomeSince >= 60)
        {
            m_OutcomeWarned = true;
            Print("[HC Plan] HC-37 outcome_receipt_waiting requested=" + m_OutcomeRequested.ToString() + " durable=" + m_OutcomeDurable.ToString() + " age_s=" + (now - m_OutcomeSince).ToString() + " runtime=PENDING");
        }
    }

    protected bool HCPollQuotaFault()
    {
        if (!m_QuotaJob || !m_QuotaJob.HCFaulted) { return true; }
        HCDropQuotaOutcome("quota_store_faulted"); // No retry or refund, including dispatch aborts.
        return HCRefuse("CONFLICT_QUOTA_STORE_UNCERTAIN");
    }

    protected void HCDropQuotaOutcome(string reason)
    {
        if (!m_PendingQuota) { return; }
        Print("[HC Plan] HC-37 data_outcome_dropped place=" + m_PendingQuota.PlaceId + " reason=" + reason);
        m_PendingQuota = null;
    }

    protected void HCApplyQuotaOutcome()
    {
        if (!m_PendingQuota || m_QuotaDurable < m_PendingQuota.Revision) { return; }
        if (!HCOutcomesCommitted()) { return; }
        if (HCTerritoryPending(m_PendingQuota.PlaceId)) { HCDropQuotaOutcome("territory_pending"); return; }
        HCWorldModule world = HCWorldModule.Get();
        if (!world) { HCDropQuotaOutcome("world_stopped"); return; }
        string reason = world.HCApplyQuotaOutcome(m_PendingQuota, m_ConflictConfig, s_CombatPort);
        if (reason != "") { HCDropQuotaOutcome(reason); return; }
        Print("[HC Plan] HC-37 data_outcome_durable kind=" + m_PendingQuota.Kind + " place=" + m_PendingQuota.PlaceId);
        m_PendingQuota = null;
    }

    override void OnStop()
    {
        // Read the fault before HCFlush: HCFlush returns false for an already-faulted job and faults
        // the job when its stage guard trips (HCWorkBudget.c:342, :374), so the reasons stay distinct.
        bool quotaFaultedBefore = m_QuotaJob && m_QuotaJob.HCFaulted;
        bool quotaFlushed = true;
        if (m_QuotaJob) { quotaFlushed = HCSaveScheduler.HCFlush(m_QuotaJob); }
        if (m_PendingQuota && m_Healthy && !quotaFaultedBefore && !quotaFlushed) { HCDropQuotaOutcome("flush_failed"); }
        HCPollQuotaFault();
        if (m_PendingQuota)
        {
            if (!m_Healthy) { HCDropQuotaOutcome("unhealthy_at_stop"); }
            else if (m_QuotaDurable < m_PendingQuota.Revision) { HCDropQuotaOutcome("not_durable_at_stop"); }
            else
            {
                HCApplyQuotaOutcome();
                // HCApplyQuotaOutcome waits (keeps the slot) while the journal is uncommitted; at stop
                // that wait cannot end, so name the drop. No-op once the slot was applied or dropped.
                HCDropQuotaOutcome("outcomes_uncommitted_at_stop");
            }
        }
        if (m_OutcomeJob && m_Healthy)
        {
            HCTerritoryOutcomeRow stopping = m_Current;
            if (!stopping) { stopping = m_PendingBind; }
            if (stopping && stopping.State == "OBSERVING")
            {
                stopping.State = "UNKNOWN_STOP";
                HCRequestSave();
            }
        }
        bool outcomeFaultedBefore = m_OutcomeJob && m_OutcomeJob.HCFaulted;
        bool outcomeFlushed = true;
        if (m_OutcomeJob && m_Store && (m_Healthy || m_Store.SaveInFlight()))
        {
            outcomeFlushed = HCSaveScheduler.HCFlush(m_OutcomeJob);
        }
        bool outcomeFaultFree = HCPollOutcomeFault();
        if (!HCOutcomesCommitted())
        {
            string stopReason = "unhealthy_at_stop";
            if (outcomeFaultedBefore) { stopReason = "faulted"; }
            else if (!outcomeFlushed) { stopReason = "flush_failed"; }
            else if (!outcomeFaultFree) { stopReason = "faulted"; }
            Print("[HC Plan] HC-37 outcome_receipts_not_durable_at_stop requested=" + m_OutcomeRequested.ToString() + " durable=" + m_OutcomeDurable.ToString() + " reason=" + stopReason);
        }
        if (m_QuotaJob) { HCSaveScheduler.HCUnregister(m_QuotaJob); }
        if (m_OutcomeJob) { HCSaveScheduler.HCUnregister(m_OutcomeJob); }
        m_QuotaJob = null;
        m_OutcomeJob = null;
        m_PendingQuota = null;
        m_PendingBind = null;
        m_BindRevision = 0;
        m_FinishRevision = 0;
        m_QuotaRequested = 0;
        m_QuotaCheckpoint = 0;
        m_QuotaDurable = 0;
        m_QuotaStepTime = -1;
        m_OutcomeRequested = 0;
        m_OutcomeCheckpoint = 0;
        m_OutcomeDurable = 0;
        m_OutcomeSince = -1;
        m_OutcomeWarned = false;
        m_OutcomeStepTime = -1;
        s_Active = false;
        m_FixtureEncounter = "";
        m_FixtureJournalRan = false;
        m_FixtureAppliedRevision = 0;
        m_Current = null;
        m_LeftActors.Clear();
        m_RightActors.Clear();
        m_ActorCursor = 0;
        m_Healthy = false;
        m_Refusal = "";
        m_ConflictConfig = null;
        m_Quota = null;
        m_QuotaStore = null;
        m_OutcomeCursor = 0;
        m_StatusReason = "";
        m_Declined = "";
        m_ProviderLogged = false;
        s_Instance = null;
        m_Operational.HCPublish("off", "stopped");
        HCLog(null, "off", "none");
    }

    // Install only a trusted original server adapter, never JSON/RPC input.
    // No provider methods are guessed in this module. Defaults refuse all.
    static bool HCInstallCombatPort(HCFactionCombatPort port)
    {
        if (!GetGame() || !GetGame().IsServer() || !port || s_CombatPort) { return false; }
        s_CombatPort = port;
        if (s_Instance) { s_Instance.HCRefreshStatus(); }
        return true;
    }

    // Only the installing adapter removes its own port (addon stop).
    static bool HCRemoveCombatPort(HCFactionCombatPort port)
    {
        if (!port || s_CombatPort != port) { return false; }
        s_CombatPort = null;
        if (s_Instance) { s_Instance.HCRefreshStatus(); }
        return true;
    }

    protected bool HCRefuse(string reason)
    {
        if (m_Declined == reason) { return false; }
        m_Declined = reason;
        m_Refusal = reason;
        m_Healthy = false;
        s_Active = false;
        m_Operational.HCPublish("refused", reason);
        HCLog(m_Current, "refused", reason);
        return false;
    }

    // A wait, not a fault: the offer is declined, the module stays ready, and each
    // distinct reason is logged once (no per-offer log spam, no status flip).
    protected bool HCDecline(string reason)
    {
        if (reason == m_Declined) { return false; }
        m_Declined = reason;
        HCLog(m_Current, "ready", reason);
        return false;
    }

    protected void HCLog(HCTerritoryOutcomeRow row, string state, string reason)
    {
        string id = "none";
        string outcome = state;
        int observed = 0;
        if (row)
        {
            id = row.Id;
            outcome = row.State;
            observed = HCTerritoryOutcomes.HCDeaths(row.LeftDead) + HCTerritoryOutcomes.HCDeaths(row.RightDead);
            if (row.LeftSurvivors >= 0) { observed += row.LeftSurvivors + row.RightSurvivors; }
        }
        string line = "[HC Plan] HC-37 encounter=" + id + " observed=" + observed.ToString();
        line += " outcome=" + outcome + " state=" + state + " refusal=" + reason;
        Print(line + " runtime=PENDING");
    }

    // Recovery only, synchronous before either save job is registered.
    protected bool HCSaveBeforeJobs()
    {
        if (m_Healthy && HCTerritoryOutcomes.HCValid(m_Outcomes) && m_Store.Save(m_Outcomes)) { return true; }
        // An uncertain transaction closes this feature; preserve all receipts
        // and intents. Never retry/refund/recreate after a failed barrier.
        m_Healthy = false;
        return HCRefuse("OUTCOME_STORE_UNCERTAIN");
    }

    protected int HCRequestSave()
    {
        if (!m_Healthy || !m_OutcomeJob || !HCTerritoryOutcomes.HCValid(m_Outcomes))
        {
            m_Healthy = false;
            HCRefuse("OUTCOME_STORE_UNCERTAIN");
            return 0;
        }
        m_OutcomeRequested++;
        m_OutcomeJob.HCDirty = true;
        m_OutcomeJob.HCUrgent = true;
        float now = GetGame().GetTickTime();
        m_OutcomeJob.HCDue = now;
        if (m_OutcomeSince == -1) { m_OutcomeSince = now; }
        return m_OutcomeRequested;
    }

    // Shared per-frame callback capacity. Death polling has its own one-row
    // tick budget, so a burst of offers cannot starve observation forever.
    protected bool HCCallbackAllowed()
    {
        int frame = GetGame().GetTime(); // Game.c:1535, inspected native millisecond clock.
        if (frame != m_CallbackFrame)
        {
            m_CallbackFrame = frame;
            m_CallbackUnits.HCReset(1);
        }
        return m_CallbackUnits.HCTake(1);
    }

    static string HCBegin(string place, string survey, string leftLease, string leftFaction, array<Object> left, string rightLease, string rightFaction, array<Object> right)
    {
        if (!s_Active || !s_Instance || !GetGame() || !GetGame().IsServer()) { return ""; }
        return s_Instance.HCBind(place, survey, leftLease, leftFaction, left, rightLease, rightFaction, right);
    }

    protected string HCBind(string place, string survey, string leftLease, string leftFaction, array<Object> left, string rightLease, string rightFaction, array<Object> right)
    {
        if (!m_Healthy || !HCCallbackAllowed()) { return ""; }
        if (!s_CombatPort) { HCDecline("COMBAT_PROVIDER_ABSENT"); return ""; }
        if (!HCWorldLimits.Token(place) || !HCTerritoryOutcomes.HCHash(survey)) { return ""; }
        if (HCWorldFactionCatalog.Relation(leftFaction, rightFaction) != -1) { return ""; }
        if (!left || !right || left.Count() < 1 || right.Count() < 1) { return ""; }
        if (left.Count() > HCAILimits.SIZE_CEILING || right.Count() > HCAILimits.SIZE_CEILING) { return ""; }
        HCAIPartyIdentity leftIdentity = HCWorldMaterializer.HCIdentity(leftLease);
        HCAIPartyIdentity rightIdentity = HCWorldMaterializer.HCIdentity(rightLease);
        if (!leftIdentity || !rightIdentity || leftLease == rightLease) { return ""; }
        if (leftIdentity.HCGeneration() != rightIdentity.HCGeneration()) { return ""; }
        foreach (HCTerritoryOutcomeRow prior : m_Outcomes.Rows)
        {
            if (HCTerritoryOutcomes.HCSamePair(prior, leftLease, rightLease))
            {
                // Defensive retry can read its original receipt, never restart actors.
                // The current adapter discards the offered id and never retries this path.
                if (prior.PlaceId != place || prior.Survey != survey) { return ""; }
                if (prior.Generation != leftIdentity.HCGeneration()) { HCDecline("LEASE_GENERATION_MISMATCH"); return ""; }
                if (prior.LeftLease == leftLease && (prior.LeftFaction != leftFaction || prior.RightFaction != rightFaction)) { return ""; }
                if (prior.LeftLease == rightLease && (prior.LeftFaction != rightFaction || prior.RightFaction != leftFaction)) { return ""; }
                if (prior == m_PendingBind)
                {
                    if (m_OutcomeDurable >= m_BindRevision) { HCPromoteBind(); }
                    else { HCDecline("RECEIPT_PENDING"); return ""; }
                }
                return prior.Id;
            }
            // A lease cannot fight a fresh encounter under a different pair.
            if (prior.LeftLease == leftLease || prior.RightLease == leftLease) { return ""; }
            if (prior.LeftLease == rightLease || prior.RightLease == rightLease) { return ""; }
        }
        if (HCTerritoryPending(place)) { HCDecline("TERRITORY_PUBLICATION_PENDING"); return ""; }
        if (m_Current || m_PendingBind || m_Outcomes.Rows.Count() >= HCTerritoryOutcomes.MAX_ROWS)
        {
            HCDecline("ENCOUNTER_OR_HISTORY_CAP");
            return "";
        }
        if (leftIdentity.HCPartyId() == rightIdentity.HCPartyId() || leftIdentity.HCCargoId() == rightIdentity.HCCargoId()) { return ""; }
        if (!s_CombatPort.HCSurveyed(place, survey)) { HCDecline("CONTESTED_SURVEY_UNVERIFIED"); return ""; }
        // Native EnScript.c:877/902/917: hash membership, not nested actor scans.
        map<Object, bool> actors = new map<Object, bool>;
        for (int checkedLeft = 0; checkedLeft < left.Count(); checkedLeft++)
        {
            Object leftBody = left[checkedLeft];
            if (!leftBody || !leftBody.IsAlive() || !s_CombatPort.HCOwns(leftLease, leftFaction, leftBody, place, survey)) { return ""; }
            if (actors.Contains(leftBody)) { return ""; }
            actors.Set(leftBody, true);
        }
        for (int checkedRight = 0; checkedRight < right.Count(); checkedRight++)
        {
            Object rightBody = right[checkedRight];
            if (!rightBody || !rightBody.IsAlive() || !s_CombatPort.HCOwns(rightLease, rightFaction, rightBody, place, survey)) { return ""; }
            if (actors.Contains(rightBody)) { return ""; }
            actors.Set(rightBody, true);
        }
        HCTerritoryOutcomeRow row = new HCTerritoryOutcomeRow;
        row.Id = "conflict:" + m_Outcomes.NextEncounter.ToString();
        row.PlaceId = place;
        row.Survey = survey;
        row.LeftLease = leftLease;
        row.RightLease = rightLease;
        row.LeftFaction = leftFaction;
        row.RightFaction = rightFaction;
        row.LeftParty = leftIdentity.HCPartyId();
        row.RightParty = rightIdentity.HCPartyId();
        row.LeftCargo = leftIdentity.HCCargoId();
        row.RightCargo = rightIdentity.HCCargoId();
        row.Generation = leftIdentity.HCGeneration();
        for (int leftIndex = 0; leftIndex < left.Count(); leftIndex++) { row.LeftDead.Insert(false); }
        for (int rightIndex = 0; rightIndex < right.Count(); rightIndex++) { row.RightDead.Insert(false); }
        m_Outcomes.Rows.Insert(row);
        m_Outcomes.NextEncounter++;
        int revision = HCRequestSave();
        if (revision == 0) { return ""; }
        m_PendingBind = row;
        m_BindRevision = revision;
        m_LeftActors.Clear();
        m_RightActors.Clear();
        foreach (Object boundLeft : left) { m_LeftActors.Insert(boundLeft); }
        foreach (Object boundRight : right) { m_RightActors.Insert(boundRight); }
        m_ActorCursor = 0;
        m_Declined = "RECEIPT_PENDING";
        HCLog(row, "ready", "RECEIPT_PENDING");
        return "";
    }

    protected void HCPromoteBind()
    {
        if (!m_PendingBind || m_OutcomeDurable < m_BindRevision) { return; }
        m_Current = m_PendingBind;
        m_PendingBind = null;
        m_BindRevision = 0;
        m_Declined = "";
        m_StatusReason = "surveyed_pair_bound_observation_only";
        m_Operational.HCPublish("ready", "surveyed_pair_bound_observation_only");
        HCLog(m_Current, "ready", "CARGO_TRANSFER_UNVERIFIED");
    }

    override void OnTick(float deltaTime)
    {
        if (!s_Active || !m_Healthy || !(deltaTime > 0)) { return; }
        HCServiceWorld();
        if (!m_Healthy) { return; }
        HCRefreshStatus();
        if (!m_Current || !(deltaTime > 0)) { return; }
        m_Units.HCReset(1);
        m_Work.HCReset(1);
        if (!m_Units.HCTake(1) || !m_Work.HCContinue()) { return; }
        int total = m_LeftActors.Count() + m_RightActors.Count();
        // HC-37: guard the actor cursor modulo below (original HFC:726), including actorless fixtures.
        if (total < 1) { return; }
        HCReached.Mark("faction_conflict.actor_step");
        int slot = m_ActorCursor % total;
        m_ActorCursor = (slot + 1) % total;
        int side = 0;
        Object body;
        if (slot < m_LeftActors.Count()) { body = m_LeftActors[slot]; }
        else { side = 1; slot -= m_LeftActors.Count(); body = m_RightActors[slot]; }
        // Deleted/unknown is never a casualty. Provider deletion is not death.
        if (!body || body.IsAlive()) { return; }
        // Recorded for the next image; this success has no gameplay effect.
        if (HCTerritoryOutcomes.HCDeath(m_Current, side, slot) && HCRequestSave() > 0) { HCLog(m_Current, "ready", "none"); }
    }

    // Defensive API: no mods/ callers; internal service drives completion.
    static bool HCFinish(string encounter)
    {
        if (!s_Active || !s_Instance || !GetGame() || !GetGame().IsServer()) { return false; }
        return s_Instance.HCFinishObserved(encounter);
    }

    // Defensive API: no mods/ callers. Only a pre-bound dead body adds a receipt.
    // True means recorded for the next durable image; no effect consumes this bool.
    static bool HCObserveKilled(Object body)
    {
        if (!s_Active || !s_Instance || !GetGame() || !GetGame().IsServer()) { return false; }
        if (!s_Instance.m_Healthy || !s_Instance.m_Current || !body || body.IsAlive()) { return false; }
        if (!s_Instance.HCCallbackAllowed()) { return false; }
        int side = 0;
        int slot = s_Instance.m_LeftActors.Find(body);
        if (slot < 0) { side = 1; slot = s_Instance.m_RightActors.Find(body); }
        if (!HCTerritoryOutcomes.HCDeath(s_Instance.m_Current, side, slot)) { return false; }
        if (s_Instance.HCRequestSave() == 0) { return false; }
        s_Instance.HCLog(s_Instance.m_Current, "ready", "none");
        return true;
    }

    // Defensive API: no mods/ callers. HC-16 may consume a bounded detached receipt.
    // No second camp death debit, inventory snapshot, cargo grant or strength mutation.
    static HCTerritoryOutcomeRow HCOutcomeFact(string encounter)
    {
        if (!s_Active || !s_Instance || !GetGame() || !GetGame().IsServer()) { return null; }
        if (!s_Instance.m_Healthy || !s_Instance.m_Outcomes) { return null; }
        if (!s_Instance.HCOutcomesCommitted()) { return null; }
        foreach (HCTerritoryOutcomeRow row : s_Instance.m_Outcomes.Rows)
        {
            if (row.Id != encounter) { continue; }
            string encoded;
            string error;
            HCTerritoryOutcomeRow detached;
            if (!JsonFileLoader<HCTerritoryOutcomeRow>.MakeData(row, encoded, error)) { return null; }
            if (!JsonFileLoader<HCTerritoryOutcomeRow>.LoadData(encoded, detached, error)) { return null; }
            return detached;
        }
        return null;
    }

    protected bool HCFinishObserved(string encounter)
    {
        if (!m_Healthy || !HCCallbackAllowed()) { return false; }
        if (!m_Current || m_Current.Id != encounter)
        {
            foreach (HCTerritoryOutcomeRow completed : m_Outcomes.Rows)
            {
                if (completed.Id == encounter) { return completed.LeftSurvivors >= 0; }
            }
            return false;
        }
        if (m_FinishRevision > 0)
        {
            if (m_OutcomeDurable < m_FinishRevision) { return HCDecline("OUTCOME_RECEIPT_PENDING"); }
            return HCCompleteObserved();
        }
        // Fixture BEFORE production LeftDead indexing by m_LeftActors.Count() (original HFC:800-819).
        // Only the volatile boot identity authorizes this synthetic death and BOTH_REMAIN.
        if (m_Current.Id == m_FixtureEncounter)
        {
            if (!m_Current.LeftDead[1])
            {
                if (HCTerritoryOutcomes.HCDeath(m_Current, 0, 1) && HCRequestSave() > 0) { HCLog(m_Current, "ready", "none"); }
                return false;
            }
            if (!HCOutcomesCommitted()) { return false; }
            if (!HCTerritoryOutcomes.HCResolve(m_Current, 1, 1)) { return HCRefuse("CONTRADICTORY_ACTOR_STATE"); }
            int fixtureFinishRevision = HCRequestSave();
            if (fixtureFinishRevision == 0) { return false; }
            m_FinishRevision = fixtureFinishRevision;
            return HCDecline("OUTCOME_RECEIPT_PENDING");
        }
        if (!s_CombatPort || !s_CombatPort.HCDisengaged(encounter)) { return HCDecline("DISENGAGEMENT_UNVERIFIED"); }
        // At most 2 * SIZE_CEILING bound handles. Check absence BEFORE mutating
        // any receipt; no partial count can be interpreted as a final outcome.
        for (int knownLeft = 0; knownLeft < m_LeftActors.Count(); knownLeft++)
        {
            if (!m_LeftActors[knownLeft] && !m_Current.LeftDead[knownLeft]) { return HCDecline("ACTOR_ABSENCE_UNKNOWN"); }
        }
        for (int knownRight = 0; knownRight < m_RightActors.Count(); knownRight++)
        {
            if (!m_RightActors[knownRight] && !m_Current.RightDead[knownRight]) { return HCDecline("ACTOR_ABSENCE_UNKNOWN"); }
        }
        int leftSurvivors = 0;
        int rightSurvivors = 0;
        for (int leftSlot = 0; leftSlot < m_LeftActors.Count(); leftSlot++)
        {
            if (m_LeftActors[leftSlot] && m_LeftActors[leftSlot].IsAlive()) { leftSurvivors++; }
            else { HCTerritoryOutcomes.HCDeath(m_Current, 0, leftSlot); }
        }
        for (int rightSlot = 0; rightSlot < m_RightActors.Count(); rightSlot++)
        {
            if (m_RightActors[rightSlot] && m_RightActors[rightSlot].IsAlive()) { rightSurvivors++; }
            else { HCTerritoryOutcomes.HCDeath(m_Current, 1, rightSlot); }
        }
        if (!HCTerritoryOutcomes.HCResolve(m_Current, leftSurvivors, rightSurvivors)) { return HCRefuse("CONTRADICTORY_ACTOR_STATE"); }
        int revision = HCRequestSave();
        if (revision == 0) { return false; }
        m_FinishRevision = revision;
        return HCDecline("OUTCOME_RECEIPT_PENDING");
    }

    protected bool HCCompleteObserved()
    {
        m_FinishRevision = 0;
        m_StatusReason = "observed_pair_outcome_committed";
        m_Operational.HCPublish("ready", "observed_pair_outcome_committed");
        HCLog(m_Current, "ready", "CARGO_TRANSFER_UNVERIFIED");
        if (m_Current.Id == m_FixtureEncounter) { HCModuleReadiness.HCUseFixture("FactionConflict", "journal_committed"); }
        else { HCModuleReadiness.HCUse("FactionConflict", "journal_committed"); }
        m_OutcomeCursor = 0;
        m_Current = null;
        m_LeftActors.Clear();
        m_RightActors.Clear();
        return true;
    }

    static string Cell(vector position)
    {
        int x = Math.Floor(position[0] / 1000);
        int z = Math.Floor(position[2] / 1000);
        return x.ToString() + ":" + z.ToString();
    }

    // Preserve the bulk authored bootstrap for fresh worlds.
    static void Seed(HCWorldData data, HCWorldFaction faction, int now)
    {
        if (faction.LastRegrowth != 0) { return; }
        faction.LastRegrowth = now;
        if (faction.Territory.Count() > 0) { return; }
        map<string, bool> seeded = new map<string, bool>;
        for (int placeIndex = 0; placeIndex < data.Places.Count(); placeIndex++)
        {
            bool claim = HCTerritoryRegrowth.Home(faction.Id, placeIndex);
            string cell = Cell(data.Places[placeIndex].Position);
            if (claim && !seeded.Contains(cell) && faction.Territory.Count() < HCWorldLimits.TERRITORY)
            {
                seeded.Set(cell, true);
                faction.Territory.Insert(cell);
            }
        }
    }

    // A recently fought-over place rests for seven real days. Bounded ring
    // contents, expiry and future timestamps are checked without player data.
    static bool HCRecentlyContested(HCWorldData data, string placeId, int now)
    {
        foreach (HCWorldSiteMemory memory : data.SiteMemory)
        {
            bool sameSite = memory.PlaceId == placeId && memory.Event == "RAIDED";
            bool current = memory.At <= now && memory.Expires > now;
            if (sameSite && current) { return true; }
        }
        return false;
    }

    static string HCRegrowthProtection(HCTerritoryRegrowth pass)
    {
        if (!s_Instance) { return "frozen"; }
        if (!s_Instance.HCOutcomesCommitted()) { return "frozen"; }
        if (s_Instance.m_Outcomes)
        {
            array<ref HCTerritoryOutcomeRow> journal = s_Instance.m_Outcomes.Rows;
            foreach (HCTerritoryOutcomeRow journalRow : journal)
            {
                if (journalRow.TerritoryEpoch > 0 && !journalRow.TerritoryApplied && journalRow.LeftSurvivors >= 0)
                {
                    if (!pass.ProtectPlace(journalRow.PlaceId)) { return "journal_place_missing"; }
                }
            }
        }
        if (s_Instance.m_Current && !pass.ProtectPlace(s_Instance.m_Current.PlaceId)) { return "journal_place_missing"; }
        if (s_Instance.m_PendingBind && !pass.ProtectPlace(s_Instance.m_PendingBind.PlaceId)) { return "journal_place_missing"; }
        if (s_Instance.m_PendingQuota) { pass.Protected.Set(s_Instance.m_PendingQuota.Cell, true); }
        return "";
    }

    static bool Tick(HCWorldModule world, HCWorldData data, int now)
    {
        if (!world || !data || now < data.Meta.Epoch) { return true; }
        if (s_WorkNow != now)
        {
            s_WorkNow = now;
            s_GrowthNext = 0;
        }
        s_WorkBudget.HCReset(1);
        s_UnitBudget.HCReset(1);
        if (!s_UnitBudget.HCTake(1) || !s_WorkBudget.HCContinue()) { s_WorkBudget.HCDeferred("FactionConflict", 1); return false; }
        // Abstract strength/territory recover without entities, loot or refunds.
        // One complete faction per continuation; <=64 places, <=128 journal rows,
        // one Facts/lease scan and <=P^2 (4096) distance checks, no yielded plan.
        if (s_GrowthNext < data.Factions.Count())
        {
            HCWorldFaction growing = data.Factions[s_GrowthNext];
            int growingIndex = s_GrowthNext;
            s_GrowthNext = s_GrowthNext + 1;
            if (growing.LastRegrowth == 0 && s_Active) { Seed(data, growing, now); }
            else { world.HCRegrow(growing, growingIndex, now, s_Active); }
            s_WorkBudget.HCDeferred("FactionConflict", data.Factions.Count() - s_GrowthNext);
            return false;
        }
        // HC-37: abstract overlap is pressure only. It never authorizes a
        // casualty, territory transfer, corpse, stock grant or camp raid.
        return true;
    }
}

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        Register(new HCFactionConflict);
    }
}

// Native EnSystem.c:397 FileExist; all I/O delegates to existing verified HC stores.
// Named operator policy, default ON; absent scalar keys refuse instead of
// accepting JsonFileLoader zero-fill. The shared verified JSON store owns I/O.
class HCConflictConfig
{
    int Version = 1;
    bool Enabled = true;
    float FarMeters = 1500;
    int CooldownSeconds = 604800;
    int MaxDailyOutcomes = 2;
    int MaxPlayers = 64;
    float PressureMeters = 120;
    bool ResolveEqualStrength = true;

    static HCConflictConfig HCLoad()
    {
        string path = "$profile:HollowCountry/faction-conflict.json";
        if (!HCV2ThreatStore<HCConflictConfig>.CanOpen(path)) { return null; }
        HCConflictConfig config;
        if (!FileExist(path))
        {
            config = new HCConflictConfig;
            if (!HCV2ThreatStore<HCConflictConfig>.Save(path, config, 4096)) { return null; }
        }
        string encoded;
        if (!HCGroupIO.Read(path, 4096, encoded)) { return null; }
        if (!HCJsonFields.Every(encoded, "Version", 1) || !HCJsonFields.Every(encoded, "Enabled", 1)) { return null; }
        if (!HCJsonFields.Every(encoded, "FarMeters", 1) || !HCJsonFields.Every(encoded, "CooldownSeconds", 1)) { return null; }
        if (!HCJsonFields.Every(encoded, "MaxDailyOutcomes", 1) || !HCJsonFields.Every(encoded, "MaxPlayers", 1)) { return null; }
        if (!HCJsonFields.Every(encoded, "ResolveEqualStrength", 1) || !HCJsonFields.Every(encoded, "PressureMeters", 1)) { return null; }
        if (!HCV2ThreatStore<HCConflictConfig>.Load(path, 4096, config)) { return null; }
        if (config.Version != 1 || config.FarMeters < 1500 || config.FarMeters > 15000) { return null; }
        if (config.CooldownSeconds < 86400 || config.CooldownSeconds > HCWorldLimits.FACT_LIFETIME) { return null; }
        if (config.MaxDailyOutcomes < 1 || config.MaxDailyOutcomes > 8 || config.MaxPlayers < 1 || config.MaxPlayers > HCLODPolicy.MAX_PLAYERS) { return null; }
        if (config.PressureMeters < 1 || config.PressureMeters > config.FarMeters) { return null; }
        return config;
    }
}

// Ledger owner extension: no new module, clock, entity or inventory owner.
// Native snapshot: Object.c:287 GetPosition; Man.c:21 GetIdentity;
// Object.c:517 IsAlive; EnConvert.c:210 vector.DistanceSq;
// EnScript.c:380/394/407/463 arrays; EnSystem.c:397 FileExist;
// Game.c:1120 IsServer, gameplay.c:636 GetGame. All other calls are HC ports.
modded class HCWorldModule
{
    protected int m_ConflictPlace;
    protected int m_ConflictLeft;
    protected int m_ConflictRight = 1;
    protected int m_ConflictFrame = -1;
    protected string m_FixtureConflict;

    // World owns dirty notification; all decisions and mutation stay in this continuation.
    void HCRegrow(HCWorldFaction faction, int factionIndex, int now, bool territoryActive)
    {
        HCServer server = HCServer.Get();
        if (!m_Running || !server) { return; }
        HCSettings settings = server.GetSettings();
        if (!settings) { return; }
        int interval = settings.TerritoryRegrowthSeconds;
        if (faction.LastRegrowth > now)
        {
            faction.LastRegrowth = now;
            m_Dirty = true;
            Print("[HC World] territory_regrow_clock faction=" + faction.Id + " action=rebase");
            return;
        }
        if (faction.LastRegrowth > 0 && now - faction.LastRegrowth < interval) { return; }
        int strengthBefore = faction.Strength;
        // Retries do not repeatedly grant strength while LastRegrowth must remain unstamped.
        if (HCTerritoryRegrowth.StrengthDue(faction.Id, now, interval))
        {
            int delta = settings.FactionRegrowthStrength;
            if (faction.Strength == 0) { delta = 1; }
            AdjustStrength(faction.Id, delta);
        }
        HCTerritoryRegrowth pass = new HCTerritoryRegrowth;
        string reason = "";
        bool membershipChanged = false;
        if (territoryActive)
        {
            pass.Build(m_Data, faction, now);
            reason = HCFactionConflict.HCRegrowthProtection(pass);
            if (reason == "")
            {
                // One allocation-producing debug scan per faction, never per candidate.
                HCWorldMaterializer materializer = HCWorldMaterializer.HCDebugGet();
                if (materializer)
                {
                    int leaseCount = materializer.HCDebugProposalCount();
                    for (int leaseIndex = 0; leaseIndex < leaseCount; leaseIndex++)
                    {
                        HCDebugProposalRow lease = materializer.HCDebugProposal(leaseIndex);
                        if (lease && !pass.ProtectPlace(lease.PlaceId)) { reason = "journal_place_missing"; }
                    }
                }
                if (m_FixtureConflict != "")
                {
                    array<string> fixtureParts = new array<string>;
                    m_FixtureConflict.Split("/", fixtureParts);
                    if (fixtureParts.Count() > 0 && !pass.ProtectPlace(fixtureParts[0])) { reason = "journal_place_missing"; }
                }
            }
            if (reason == "")
            {
                int growthDay = HCWorldClock.Day(m_Data, now);
                int rotation = HCTerritoryRegrowth.Rotation(growthDay, now, interval, factionIndex, pass.Cells.Count());
                int staleRotation = HCTerritoryRegrowth.Rotation(growthDay, now, interval, factionIndex, faction.Territory.Count());
                membershipChanged = pass.Choose(m_Data, faction, rotation, staleRotation, settings.TerritoryExtraCells);
                if (!membershipChanged)
                {
                    if (pass.Blocked) { reason = "cell_protected"; }
                    else { reason = "no_candidate"; }
                }
            }
        }
        // Protected/frozen passes retry next world step, never hold Tick open.
        if (reason == "" || reason == "no_candidate") { faction.LastRegrowth = now; }
        HCTerritoryRegrowth.HCWait(faction.Id, reason);
        if (membershipChanged) { m_Dirty = true; }
        if (membershipChanged || faction.Strength != strengthBefore)
        {
            Print("[HC World] territory_regrow faction=" + faction.Id + " strength=" + faction.Strength.ToString() + " cells=" + faction.Territory.Count().ToString() + " reclaimed=" + pass.Reclaimed + " shifted=" + pass.Shifted + " released=" + pass.Released);
            HCModuleReadiness.HCUse("FactionConflict", "territory_regrowth");
        }
    }

    // False on unknown, invalid or over-cap roster: uncertainty stays near.
    bool HCConflictFar(HCWorldPlace place, HCConflictConfig config)
    {
        array<Man> observers = HCPerfPlayers.HCGet();
        if (observers.Count() > config.MaxPlayers) { return false; }
        foreach (Man observer : observers)
        {
            if (!observer) { return false; }
            if (!observer.GetIdentity()) { continue; }
            vector position = observer.GetPosition();
            if (!HCWorldLimits.Position(position)) { return false; }
            // Dead players still count as viewers. Horizontal distance only.
            position[1] = 0;
            vector anchor = place.Position;
            anchor[1] = 0;
            if (vector.DistanceSq(position, anchor) <= config.FarMeters * config.FarMeters) { return false; }
        }
        return true;
    }

    protected bool HCConflictBudget(HCConflictConfig config, string place, int now)
    {
        int day = HCWorldClock.Day(m_Data, now);
        int count = 0;
        array<ref HCWorldFact> facts = m_Data.Facts;
        foreach (HCWorldFact fact : facts)
        {
            if (fact.At > now) { continue; }
            if (fact.Kind != "faction_clash" && fact.Kind != "camp_infected_pressure") { continue; }
            if (fact.PlaceId == place && now - fact.At < config.CooldownSeconds) { return false; }
            if (HCWorldClock.Day(m_Data, fact.At) == day) { count++; }
        }
        return count < config.MaxDailyOutcomes;
    }

    // Never abstract a site while an HC-10 lease owns real actors there.
    protected bool HCConflictLeased(string place)
    {
        HCWorldMaterializer materializer = HCWorldMaterializer.HCDebugGet();
        if (!materializer) { return false; }
        int total = materializer.HCDebugProposalCount();
        for (int leaseIndex = 0; leaseIndex < total; leaseIndex++)
        {
            HCDebugProposalRow lease = materializer.HCDebugProposal(leaseIndex);
            if (lease && lease.PlaceId == place && lease.State == "claimed") { return true; }
        }
        return false;
    }

    // Fixed authored faction catalog; one bounded pass over candidate place/pair
    // rows. Only cursors change, never history, quota, claims or strength.
    bool HCFixtureConflict(vector pos, bool apply, HCConflictConfig config, HCFactionCombatPort port, out string reason)
    {
        reason = "conflict-owner-unavailable-or-selection-pending";
        if (HCFactionConflict.HCQuotaOutcomePending()) { return false; }
        if (!m_Running || !m_Data || !config || !config.Enabled || !HCRecoveryGate.HCReady("world") || m_FixtureConflict != "") { return false; }
        int now = HCWorldClock.UTC();
        if (now < m_Data.Meta.Epoch) { reason = "conflict-clock-unavailable"; return false; }
        int selected = -1;
        int selectedLeft = -1;
        int selectedRight = -1;
        float best = 0;
        int factions = m_Data.Factions.Count();
        if (factions != HCWorldLimits.FACTIONS) { reason = "conflict-faction-catalog-invalid"; return false; }
        int pending = 0;
        int near = 0;
        int leased = 0;
        int active = 0;
        int budget = 0;
        int held = 0;
        int notOpposed = 0;
        int dailyCap = 0;
        int dailyCount = 0;
        int day = HCWorldClock.Day(m_Data, now);
        array<ref HCWorldFact> fixtureFacts = m_Data.Facts;
        foreach (HCWorldFact fixtureFact : fixtureFacts)
        {
            if (fixtureFact.At > now) { continue; }
            if (fixtureFact.Kind != "faction_clash" && fixtureFact.Kind != "camp_infected_pressure") { continue; }
            if (HCWorldClock.Day(m_Data, fixtureFact.At) == day) { dailyCount++; }
        }
        if (dailyCount >= config.MaxDailyOutcomes) { dailyCap = 1; }
        m_WorkBudget.HCReset(m_Data.Places.Count() * (factions * factions + 1));
        for (int i = 0; i < m_Data.Places.Count(); i++)
        {
            if (!m_WorkBudget.HCContinue()) { reason = "conflict-selection-budget"; return false; }
            HCWorldPlace place = m_Data.Places[i];
            if (HCFactionConflict.HCTerritoryPending(place.Id)) { pending++; continue; }
            if (!HCConflictFar(place, config)) { near++; continue; }
            if (HCConflictLeased(place.Id)) { leased++; continue; }
            if (port && port.HCActiveAt(place.Id)) { active++; continue; }
            // Budget includes place cooldown OR daily cap, never labelled cooldown.
            if (dailyCap == 1 || !HCConflictBudget(config, place.Id, now)) { budget++; continue; }
            if (HCFactionConflict.HCFixtureJournalHolds(place.Id)) { held++; continue; }
            bool hasOpposed = false;
            string cell = HCFactionConflict.Cell(place.Position);
            for (int left = 0; left < factions - 1; left++)
            {
                for (int right = left + 1; right < factions; right++)
                {
                    if (!m_WorkBudget.HCContinue()) { reason = "conflict-selection-budget"; return false; }
                    if (!HCConflictPolicy.HCOpposed(m_Data.Factions[left], m_Data.Factions[right], cell)) { continue; }
                    hasOpposed = true;
                    float distance = vector.DistanceSq(pos, place.Position);
                    if (selected < 0 || distance < best) { best = distance; selected = i; selectedLeft = left; selectedRight = right; }
                }
            }
            if (!hasOpposed) { notOpposed++; }
        }
        reason = "no-eligible-distant-opposed-cell places=" + m_Data.Places.Count().ToString() + " pending=" + pending.ToString() + " near=" + near.ToString() + " leased=" + leased.ToString();
        reason += " active=" + active.ToString() + " budget=" + budget.ToString() + " held=" + held.ToString() + " not_opposed=" + notOpposed.ToString() + " daily_cap=" + dailyCap.ToString();
        if (selected < 0) { return false; }
        if (apply)
        {
            m_ConflictPlace = selected;
            m_ConflictLeft = selectedLeft;
            m_ConflictRight = selectedRight;
            m_FixtureConflict = m_Data.Places[selected].Id + "/" + m_Data.Factions[selectedLeft].Id + "/" + m_Data.Factions[selectedRight].Id;
        }
        reason = "distant-opposed-cell-queued-normal-conflict-step";
        return true;
    }

    // Separate bounded selection: no production cursors, fixture selection, quota or facts change.
    bool HCFixtureJournalPlace(vector pos, HCConflictConfig config, out string placeId, out string opposedId, out bool forced, out string selectionCounts, out string reason)
    {
        placeId = "";
        opposedId = "";
        forced = false;
        selectionCounts = "";
        reason = "conflict-owner-unavailable";
        if (!m_Running || !m_Data || !config || !config.Enabled || !HCRecoveryGate.HCReady("world")) { return false; }
        int now = HCWorldClock.UTC();
        if (now < m_Data.Meta.Epoch) { reason = "conflict-clock-unavailable"; return false; }
        int factionCount = m_Data.Factions.Count();
        if (factionCount != HCWorldLimits.FACTIONS) { reason = "conflict-faction-catalog-invalid"; return false; }
        HCWorldFaction raiders = m_Data.Faction("raiders");
        reason = "fixture-row-invalid";
        if (!raiders) { return false; }
        float bestDistance = 0;
        float fallbackDistance = 0;
        string fallbackPlace = "";
        string fallbackFaction = "";
        int journalPending = 0;
        int journalNear = 0;
        int journalLeased = 0;
        int journalNotOpposed = 0;
        array<ref HCWorldPlace> journalPlaces = m_Data.Places;
        array<ref HCWorldFaction> journalFactions = m_Data.Factions;
        m_WorkBudget.HCReset(journalPlaces.Count() * (factionCount + 1));
        foreach (HCWorldPlace journalPlace : journalPlaces)
        {
            if (!m_WorkBudget.HCContinue()) { reason = "conflict-selection-budget"; return false; }
            if (HCFactionConflict.HCTerritoryPending(journalPlace.Id)) { journalPending++; continue; }
            if (!HCConflictFar(journalPlace, config)) { journalNear++; continue; }
            if (HCConflictLeased(journalPlace.Id)) { journalLeased++; continue; }
            bool journalHasOpposed = false;
            float journalDistance = vector.DistanceSq(pos, journalPlace.Position);
            // HCXFactionCombatAdapter.HCActiveAt requires HCLeaseAtPlace (adapter:69-80):
            // every live transient has a claimed proposal, already excluded above. No port calls.
            string journalCell = HCFactionConflict.Cell(journalPlace.Position);
            for (int journalFactionIndex = 0; journalFactionIndex < HCWorldLimits.FACTIONS; journalFactionIndex++)
            {
                HCWorldFaction opposedFaction = journalFactions[journalFactionIndex];
                if (!m_WorkBudget.HCContinue()) { reason = "conflict-selection-budget"; return false; }
                // Journal-only fallback: no strength, claims, budget or world-age requirement.
                // Strict > retains catalog order for equal distances and faction ties.
                if (opposedFaction.Id != "raiders" && HCWorldFactionCatalog.Relation("raiders", opposedFaction.Id) == -1)
                {
                    if (fallbackPlace == "" || journalDistance > fallbackDistance)
                    {
                        fallbackPlace = journalPlace.Id;
                        fallbackFaction = opposedFaction.Id;
                        fallbackDistance = journalDistance;
                    }
                }
                if (!HCConflictPolicy.HCOpposed(raiders, opposedFaction, journalCell)) { continue; }
                journalHasOpposed = true;
                if (placeId == "" || journalDistance < bestDistance)
                {
                    bestDistance = journalDistance;
                    placeId = journalPlace.Id;
                    opposedId = opposedFaction.Id;
                }
            }
            if (!journalHasOpposed) { journalNotOpposed++; }
        }
        selectionCounts = " places=" + journalPlaces.Count().ToString() + " pending=" + journalPending.ToString() + " near=" + journalNear.ToString() + " leased=" + journalLeased.ToString() + " not_opposed=" + journalNotOpposed.ToString();
        if (placeId == "" && fallbackPlace != "")
        {
            placeId = fallbackPlace;
            opposedId = fallbackFaction;
            forced = true;
        }
        reason = "no-eligible-distant-opposed-cell" + selectionCounts;
        if (placeId == "") { return false; }
        reason = "fixture-journal-place-selected";
        return true;
    }

    // One place/pair per core tick, persistent round-robin cursor. No global
    // scans for bodies, targeting override, spawn, loot or simulated casualties.
    void HCConflictStep(HCConflictConfig config, HCFactionCombatPort port)
    {
        // Do not consume frame/budget, cursor or fixture while a barrier waits.
        if (HCFactionConflict.HCQuotaOutcomePending()) { return; }
        if (!m_Running || !m_Data || !config || !config.Enabled || !HCRecoveryGate.HCReady("world")) { return; }
        int frame = GetGame().GetTime(); // native Game.c:1535
        if (frame == m_ConflictFrame) { return; }
        m_ConflictFrame = frame;
        HCUnitBudget shared = HCServer.HCTickWork();
        if (!shared.HCTakeFor(HCUnitBudget.HC_WORK_CONFLICT, 1)) { return; }
        int now = HCWorldClock.UTC();
        if (now < m_Data.Meta.Epoch || m_Data.Places.Count() < 1 || m_Data.Factions.Count() < 2) { return; }
        if (m_ConflictPlace >= m_Data.Places.Count()) { m_ConflictPlace = 0; }
        if (m_ConflictRight >= m_Data.Factions.Count())
        {
            m_ConflictLeft++;
            m_ConflictRight = m_ConflictLeft + 1;
        }
        if (m_ConflictLeft >= m_Data.Factions.Count() - 1) { m_ConflictLeft = 0; m_ConflictRight = 1; }
        HCWorldPlace place = m_Data.Places[m_ConflictPlace];
        HCWorldFaction left = m_Data.Factions[m_ConflictLeft];
        HCWorldFaction right = m_Data.Factions[m_ConflictRight];
        string fixtureKey = place.Id + "/" + left.Id + "/" + right.Id;
        bool fixture = m_FixtureConflict == fixtureKey;
        if (fixture) { m_FixtureConflict = ""; }
        m_ConflictPlace++;
        if (m_ConflictPlace >= m_Data.Places.Count()) { m_ConflictRight++; }
        if (HCFactionConflict.HCTerritoryPending(place.Id)) { return; }
        if (!HCConflictBudget(config, place.Id, now)) { return; }
        string cell = HCFactionConflict.Cell(place.Position);
        bool far = HCConflictFar(place, config);
        if (fixture && (!far || !HCConflictPolicy.HCOpposed(left, right, cell)))
        {
            Print("[HC Plan] HC-37 fixture-selection-invalidated fixture=1");
            return;
        }
        if (!HCConflictPolicy.HCOpposed(left, right, cell))
        {
            if (far && !HCConflictLeased(place.Id)) { HCConflictPressure(place, cell, now, config); }
            return;
        }
        if (!far)
        {
            if (port) { port.HCOffer(place.Id, left.Id, right.Id); }
            return;
        }
        if (HCConflictLeased(place.Id) || (port && port.HCActiveAt(place.Id))) { return; }
        string winner = HCConflictPolicy.HCWinner(left, right);
        if (winner == "" && config.ResolveEqualStrength)
        {
            winner = left.Id;
            if ((HCWorldClock.Day(m_Data, now) + m_ConflictPlace) % 2 == 1) { winner = right.Id; }
        }
        HCConflictPendingOutcome pending = new HCConflictPendingOutcome;
        pending.Kind = "clash";
        pending.PlaceId = place.Id;
        pending.Cell = cell;
        pending.LeftFaction = left.Id;
        pending.RightFaction = right.Id;
        pending.WinnerFaction = winner;
        if (winner == left.Id) { pending.LoserFaction = right.Id; }
        if (winner == right.Id) { pending.LoserFaction = left.Id; }
        pending.Fixture = fixture;
        HCFactionConflict.HCReserveDataOutcome(pending, now);
    }

    protected void HCConflictPublish(HCWorldFaction winner, HCWorldFaction loser, HCWorldPlace place, string cell)
    {
        if (!HCConflictPolicy.HCTransfer(winner, loser, cell)) { return; }
        m_Dirty = true;
        AddFact(winner.Id + "_pushed_" + loser.Id, place.Id, 2);
    }

    // Pressure is remembered data, never a fabricated infected body or an
    // authority to delete a funded camp. Camp owner retains bodies and stock.
    protected void HCConflictPressure(HCWorldPlace place, string cell, int now, HCConflictConfig config)
    {
        HCInfectedModule infected = HCInfectedModule.Instance;
        if (!infected) { return; }
        int pressure = infected.HCConflictPressureAt(place.Position, config.PressureMeters);
        if (pressure < 1) { return; }
        array<ref HCWorldHoldout> camps = m_Data.Holdouts;
        HCWorldHoldout camp;
        foreach (HCWorldHoldout candidate : camps)
        {
            if (candidate.PlaceId == place.Id) { camp = candidate; break; }
        }
        if (camp)
        {
            HCConflictPendingOutcome pending = new HCConflictPendingOutcome;
            pending.Kind = "pressure";
            pending.PlaceId = place.Id;
            pending.Cell = cell;
            HCFactionConflict.HCReserveDataOutcome(pending, now);
        }
    }

    // Called only after the paying quota image is durable. Resolve live data
    // again: an HC-10 lease or real combat always owns actors over abstraction.
    string HCApplyQuotaOutcome(HCConflictPendingOutcome pending, HCConflictConfig config, HCFactionCombatPort port)
    {
        if (!m_Running || !m_Data || !config) { return "world_stopped"; }
        HCWorldPlace place = m_Data.Place(pending.PlaceId);
        if (!place) { return "place_missing"; }
        if (!HCConflictFar(place, config)) { return "near"; }
        if (HCConflictLeased(place.Id)) { return "leased"; }
        if (port && port.HCActiveAt(place.Id)) { return "active"; }
        if (pending.Kind == "clash")
        {
            HCWorldFaction left = m_Data.Faction(pending.LeftFaction);
            HCWorldFaction right = m_Data.Faction(pending.RightFaction);
            if (!left || !right || !HCConflictPolicy.HCOpposed(left, right, pending.Cell)) { return "not_opposed"; }
            if (!AddFact("faction_clash", place.Id, 1)) { return "add_fact_refused"; }
            if (pending.WinnerFaction == left.Id) { HCConflictPublish(left, right, place, pending.Cell); }
            if (pending.WinnerFaction == right.Id) { HCConflictPublish(right, left, place, pending.Cell); }
            string outcomeLine = "[HC Plan] HC-37 data_outcome place=" + place.Id + " winner=" + pending.WinnerFaction + " bodies=0 loot=0 runtime=PENDING";
            if (pending.Fixture) { outcomeLine += " fixture=1"; }
            Print("" + outcomeLine);
            if (pending.Fixture) { HCModuleReadiness.HCUseFixture("FactionConflict", "outcome_recorded"); }
            else { HCModuleReadiness.HCUse("FactionConflict", "outcome_recorded"); }
        }
        else
        {
            array<ref HCWorldHoldout> liveCamps = m_Data.Holdouts;
            HCWorldHoldout liveCamp;
            foreach (HCWorldHoldout liveCandidate : liveCamps)
            {
                if (liveCandidate.PlaceId == pending.PlaceId) { liveCamp = liveCandidate; break; }
            }
            if (!liveCamp) { return "camp_missing"; }
            HCWorldFaction holder = m_Data.Faction(liveCamp.FactionId);
            if (!holder) { return "camp_faction_missing"; }
            bool empty = liveCamp.Occupants == 0;
            if (!AddFact("camp_infected_pressure", place.Id, 1)) { return "add_fact_refused"; }
            if (!AddFact("holdout_alert", place.Id, 1)) { return "add_fact_refused"; }
            string outcome = "camp_holds";
            if (empty)
            {
                int claim = holder.Territory.Find(pending.Cell);
                if (claim >= 0) { holder.Territory.Remove(claim); m_Dirty = true; }
                outcome = "empty_camp_claim_falls";
            }
            Print("[HC Plan] HC-37 infected_pressure place=" + place.Id + " outcome=" + outcome + " runtime=PENDING");
        }
        return "";
    }

    // Observed player/AI kills are included by the existing real death hook.
    // This does not debit population twice. Absolute holding removal is safe
    // on replay; the world checkpoint precedes the journal applied receipt.
    protected string m_ConflictCheckpoint;

    bool HCConflictObserved(HCTerritoryOutcomeRow row, HCConflictConfig config)
    {
        if (!m_Running || !HCRecoveryGate.HCReady("world") || m_Store.SaveInFlight()) { return false; }
        if (m_ConflictCheckpoint != "")
        {
            if (m_ConflictCheckpoint != row.Id || !HCFlushRoutine()) { return false; }
            m_ConflictCheckpoint = "";
            return true;
        }
        HCWorldPlace place = m_Data.Place(row.PlaceId);
        if (!place || !HCConflictFar(place, config)) { return false; }
        HCWorldFaction left = m_Data.Faction(row.LeftFaction);
        HCWorldFaction right = m_Data.Faction(row.RightFaction);
        if (!left || !right) { return false; }
        string cell = HCFactionConflict.Cell(place.Position);
        if (row.State == "LEFT_REMAINS") { HCConflictPublish(left, right, place, cell); }
        if (row.State == "RIGHT_REMAINS") { HCConflictPublish(right, left, place, cell); }
        m_ConflictCheckpoint = row.Id;
        return HCFlushRoutine();
    }

    void HCConflictDebug(HCDebugSnapshot snapshot)
    {
        if (!m_Running || !m_Data) { return; }
        array<ref HCWorldPlace> places = m_Data.Places;
        array<ref HCWorldFaction> factions = m_Data.Factions;
        for (int debugIndex = snapshot.HCRow; debugIndex < places.Count(); debugIndex++)
        {
            if (!snapshot.HCRowStep()) { return; }
            HCWorldPlace place = places[debugIndex];
            string holders = "";
            string cell = HCFactionConflict.Cell(place.Position);
            foreach (HCWorldFaction faction : factions)
            {
                if (faction.Territory.Find(cell) >= 0) { holders += faction.Id + " "; }
            }
            snapshot.AddPoint("territories", place.Id, place.Position, place.Name, holders);
        }
    }
}

class HCConflictDebugContributor : HCDebugContributor
{
    override void HCDescribe(HCDebugSnapshot snapshot)
    {
        HCWorldModule world = HCWorldModule.Get();
        if (world) { world.HCConflictDebug(snapshot); }
    }
}

// Read-only finite infected-owner seam. Never adopts, routes or kills an actor.
// Native Object.c:287 GetPosition, :517 IsAlive; EnConvert.c:210 DistanceSq.
modded class HCInfectedModule
{
    int HCConflictPressureAt(vector position, float radius)
    {
        if (!m_Healthy || m_Actors.Count() > HCLODPolicy.MAX_TRACKED) { return -1; }
        int count = 0;
        array<ref HCInfectedActor> actors = m_Actors;
        foreach (HCInfectedActor actor : actors)
        {
            if (!actor || !actor.InfectedEntity || !actor.InfectedEntity.IsAlive()) { continue; }
            if (vector.DistanceSq(position, actor.InfectedEntity.GetPosition()) <= radius * radius) { count++; }
        }
        return count;
    }
}
