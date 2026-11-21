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
// Persistence delegates
// to HCEncounterStore (HCHoldouts.c:28) and the world checkpoint; no new scheduler.
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
    protected string m_Declined;
    protected string m_StatusReason;
    protected bool m_ProviderLogged;
    protected int m_ActorCursor;
    protected int m_CallbackFrame = -1;
    protected ref HCUnitBudget m_CallbackUnits = new HCUnitBudget;

    override string GetName() { return "FactionConflict"; }
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
        m_ConflictConfig = HCConflictConfig.HCLoad();
        if (!m_ConflictConfig) { HCRefuse("CONFLICT_CONFIG_INVALID"); return; }
        if (!m_ConflictConfig.Enabled) { m_Operational.HCPublish("off", "conflict_operator_off"); return; }
        m_QuotaStore = new HCEncounterStore<HCConflictQuota>("faction-conflict-quota");
        HCConflictQuota freshQuota = new HCConflictQuota;
        m_Quota = m_QuotaStore.Load(freshQuota, "Rows");
        string quotaText = m_QuotaStore.HCTakeLoadedText();
        if (!HCConflictQuota.HCValid(m_Quota, quotaText)) { HCRefuse("CONFLICT_QUOTA_INVALID"); return; }
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
        if (HCTerritoryOutcomes.HCRecover(m_Outcomes) > 0 && !HCSave())
        {
            HCRefuse("RESTART_OUTCOME_STORE_UNCERTAIN");
            return;
        }
        // The addon binds its combat port after this module starts; the real provider
        // state is derived on the first tick (HCRefreshStatus), never assumed here.
        m_StatusReason = "awaiting_provider_bind";
        m_Operational.HCPublish("ready", "awaiting_provider_bind");
        HCLog(null, "ready", "AWAITING_SURVEYED_PAIR");
        string raidReason = HCCampRaidActors.HCGet().HCRefusal();
        Print("[HC Plan] HC-37 raids=delegated_to_HC39 reason=" + raidReason + " runtime=PENDING");
        Print("[HC Plan] HC-37 camp_population_outcome=owner_required data_pressure=enabled runtime=PENDING");
    }

    // Derives the ready reason from the real port/pair state; publishes only on change.
    void HCRefreshStatus()
    {
        if (!s_Active || !m_Healthy) { return; }
        HCServiceWorld();
        if (!m_Healthy) { return; }
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
        HCWorldModule world = HCWorldModule.Get();
        if (!world || !m_ConflictConfig) { return; }
        // Retry at most one durable receipt per tick, rotating even when viewers
        // keep its site pending. Unrelated sites still receive their normal step.
        if (m_OutcomeCursor >= m_Outcomes.Rows.Count()) { m_OutcomeCursor = 0; }
        if (m_OutcomeCursor < m_Outcomes.Rows.Count())
        {
            HCTerritoryOutcomeRow outcome = m_Outcomes.Rows[m_OutcomeCursor];
            m_OutcomeCursor++;
            if (outcome.TerritoryEpoch > 0 && !outcome.TerritoryApplied && outcome.LeftSurvivors >= 0)
            {
                if (!world.HCConflictObserved(outcome, m_ConflictConfig)) { HCDecline("TERRITORY_PUBLICATION_PENDING"); }
                else
                {
                    outcome.TerritoryApplied = true;
                    if (!HCSave()) { return; }
                }
            }
        }
        if (m_Current)
        {
            if (m_Current.TerritoryEpoch == 0)
            {
                m_Current.TerritoryEpoch = HCWorldClock.UTC();
                HCSave();
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

    static bool HCReserveDataOutcome(string place, int now)
    {
        if (!s_Active || !s_Instance || !s_Instance.m_Healthy) { return false; }
        if (!HCConflictQuota.HCReserve(s_Instance.m_Quota, s_Instance.m_ConflictConfig, place, now)) { return false; }
        if (s_Instance.m_QuotaStore.Save(s_Instance.m_Quota)) { return true; }
        s_Instance.HCRefuse("CONFLICT_QUOTA_STORE_UNCERTAIN");
        return false;
    }

    override void OnStop()
    {
        s_Active = false;
        if (m_Healthy && m_Current && m_Current.State == "OBSERVING")
        {
            m_Current.State = "UNKNOWN_STOP";
            HCSave();
        }
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

    protected bool HCSave()
    {
        if (m_Healthy && HCTerritoryOutcomes.HCValid(m_Outcomes) && m_Store.Save(m_Outcomes)) { return true; }
        // An uncertain transaction closes this feature; preserve all receipts
        // and intents. Never retry/refund/recreate after a failed barrier.
        m_Healthy = false;
        return HCRefuse("OUTCOME_STORE_UNCERTAIN");
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
                // Retry can read its original receipt, never restart actors.
                if (prior.PlaceId != place || prior.Survey != survey) { return ""; }
                if (prior.Generation != leftIdentity.HCGeneration()) { HCDecline("LEASE_GENERATION_MISMATCH"); return ""; }
                if (prior.LeftLease == leftLease && (prior.LeftFaction != leftFaction || prior.RightFaction != rightFaction)) { return ""; }
                if (prior.LeftLease == rightLease && (prior.LeftFaction != rightFaction || prior.RightFaction != leftFaction)) { return ""; }
                return prior.Id;
            }
            // A lease cannot fight a fresh encounter under a different pair.
            if (prior.LeftLease == leftLease || prior.RightLease == leftLease) { return ""; }
            if (prior.LeftLease == rightLease || prior.RightLease == rightLease) { return ""; }
        }
        if (HCTerritoryPending(place)) { HCDecline("TERRITORY_PUBLICATION_PENDING"); return ""; }
        if (m_Current || m_Outcomes.Rows.Count() >= HCTerritoryOutcomes.MAX_ROWS)
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
        if (!HCSave()) { return ""; }
        m_Current = row;
        m_LeftActors.Clear();
        m_RightActors.Clear();
        foreach (Object boundLeft : left) { m_LeftActors.Insert(boundLeft); }
        foreach (Object boundRight : right) { m_RightActors.Insert(boundRight); }
        m_ActorCursor = 0;
        m_Declined = "";
        m_StatusReason = "surveyed_pair_bound_observation_only";
        m_Operational.HCPublish("ready", "surveyed_pair_bound_observation_only");
        HCLog(row, "ready", "CARGO_TRANSFER_UNVERIFIED");
        return row.Id;
    }

    override void OnTick(float deltaTime)
    {
        if (!s_Active || !m_Healthy || !(deltaTime > 0)) { return; }
        HCRefreshStatus();
        if (!m_Current || !(deltaTime > 0)) { return; }
        m_Units.HCReset(1);
        m_Work.HCReset(1);
        if (!m_Units.HCTake(1) || !m_Work.HCContinue()) { return; }
        int total = m_LeftActors.Count() + m_RightActors.Count();
        HCReached.Mark("faction_conflict.actor_step");
        int slot = m_ActorCursor % total;
        m_ActorCursor = (slot + 1) % total;
        int side = 0;
        Object body;
        if (slot < m_LeftActors.Count()) { body = m_LeftActors[slot]; }
        else { side = 1; slot -= m_LeftActors.Count(); body = m_RightActors[slot]; }
        // Deleted/unknown is never a casualty. Provider deletion is not death.
        if (!body || body.IsAlive()) { return; }
        if (HCTerritoryOutcomes.HCDeath(m_Current, side, slot) && HCSave()) { HCLog(m_Current, "ready", "none"); }
    }

    static bool HCFinish(string encounter)
    {
        if (!s_Active || !s_Instance || !GetGame() || !GetGame().IsServer()) { return false; }
        return s_Instance.HCFinishObserved(encounter);
    }

    // Adapter calls after the real server EEKilled, before any player-killer
    // filter. Only a pre-bound dead body can add a receipt; no global kill feed.
    static bool HCObserveKilled(Object body)
    {
        if (!s_Active || !s_Instance || !GetGame() || !GetGame().IsServer()) { return false; }
        if (!s_Instance.m_Healthy || !s_Instance.m_Current || !body || body.IsAlive()) { return false; }
        if (!s_Instance.HCCallbackAllowed()) { return false; }
        int side = 0;
        int slot = s_Instance.m_LeftActors.Find(body);
        if (slot < 0) { side = 1; slot = s_Instance.m_RightActors.Find(body); }
        if (!HCTerritoryOutcomes.HCDeath(s_Instance.m_Current, side, slot)) { return false; }
        if (!s_Instance.HCSave()) { return false; }
        s_Instance.HCLog(s_Instance.m_Current, "ready", "none");
        return true;
    }

    // HC-16 consumes a bounded detached receipt. This is NOT a second camp
    // death debit, inventory snapshot, cargo grant or world-strength mutation.
    static HCTerritoryOutcomeRow HCOutcomeFact(string encounter)
    {
        if (!s_Active || !s_Instance || !GetGame() || !GetGame().IsServer()) { return null; }
        if (!s_Instance.m_Healthy || !s_Instance.m_Outcomes) { return null; }
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
        if (!HCSave()) { return false; }
        m_StatusReason = "observed_pair_outcome_committed";
        m_Operational.HCPublish("ready", "observed_pair_outcome_committed");
        HCLog(m_Current, "ready", "CARGO_TRANSFER_UNVERIFIED");
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

    // Authored off-screen starting claims, not sightings of NPCs. No claim
    // is recreated once a faction has lost it or reached zero strength.
    static void Seed(HCWorldData data, HCWorldFaction faction, int now)
    {
        if (faction.LastRegrowth != 0) { return; }
        faction.LastRegrowth = now;
        if (faction.Territory.Count() > 0) { return; }
        map<string, bool> seeded = new map<string, bool>;
        for (int placeIndex = 0; placeIndex < data.Places.Count(); placeIndex++)
        {
            bool claim = false;
            if (faction.Id == "locals" && placeIndex % 4 == 0) { claim = true; }
            if (faction.Id == "volunteers" && placeIndex % 4 == 1) { claim = true; }
            if (faction.Id == "scavengers" && placeIndex % 4 == 2) { claim = true; }
            if (faction.Id == "travellers" && placeIndex % 4 == 3) { claim = true; }
            if (faction.Id == "raiders" && placeIndex % 3 == 1) { claim = true; }
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

    static bool Tick(HCWorldModule world, HCWorldData data, int now)
    {
        if (!s_Active || !world || !data || now < data.Meta.Epoch) { return true; }
        if (s_WorkNow != now)
        {
            s_WorkNow = now;
            s_GrowthNext = 0;
        }
        s_WorkBudget.HCReset(1);
        s_UnitBudget.HCReset(1);
        if (!s_UnitBudget.HCTake(1) || !s_WorkBudget.HCContinue()) { s_WorkBudget.HCDeferred("FactionConflict", 1); return false; }
        // Initial authored claims only; no unfunded population regrowth.
        // Seed touches <=64 validated place anchors once per faction, never entities.
        if (s_GrowthNext < data.Factions.Count())
        {
            HCWorldFaction growing = data.Factions[s_GrowthNext];
            s_GrowthNext = s_GrowthNext + 1;
            Seed(data, growing, now);
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
        if (!m_Running || !m_Data || !config || !config.Enabled || !HCRecoveryGate.HCReady("world") || m_FixtureConflict != "") { return false; }
        int now = HCWorldClock.UTC();
        if (now < m_Data.Meta.Epoch) { reason = "conflict-clock-unavailable"; return false; }
        int selected = -1;
        int selectedLeft = -1;
        int selectedRight = -1;
        float best = 0;
        int factions = m_Data.Factions.Count();
        if (factions != HCWorldLimits.FACTIONS) { reason = "conflict-faction-catalog-invalid"; return false; }
        m_WorkBudget.HCReset(m_Data.Places.Count() * (factions * factions + 1));
        for (int i = 0; i < m_Data.Places.Count(); i++)
        {
            if (!m_WorkBudget.HCContinue()) { reason = "conflict-selection-budget"; return false; }
            HCWorldPlace place = m_Data.Places[i];
            if (HCFactionConflict.HCTerritoryPending(place.Id) || !HCConflictFar(place, config) || HCConflictLeased(place.Id)) { continue; }
            if ((port && port.HCActiveAt(place.Id)) || !HCConflictBudget(config, place.Id, now)) { continue; }
            string cell = HCFactionConflict.Cell(place.Position);
            for (int left = 0; left < factions - 1; left++)
            {
                for (int right = left + 1; right < factions; right++)
                {
                    if (!m_WorkBudget.HCContinue()) { reason = "conflict-selection-budget"; return false; }
                    if (!HCConflictPolicy.HCOpposed(m_Data.Factions[left], m_Data.Factions[right], cell)) { continue; }
                    float distance = vector.DistanceSq(pos, place.Position);
                    if (selected < 0 || distance < best) { best = distance; selected = i; selectedLeft = left; selectedRight = right; }
                }
            }
        }
        reason = "no-eligible-distant-opposed-cell";
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

    // One place/pair per core tick, persistent round-robin cursor. No global
    // scans for bodies, targeting override, spawn, loot or simulated casualties.
    void HCConflictStep(HCConflictConfig config, HCFactionCombatPort port)
    {
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
        if (!HCFactionConflict.HCReserveDataOutcome(place.Id, now)) { return; }
        if (!AddFact("faction_clash", place.Id, 1)) { return; }
        if (winner == left.Id) { HCConflictPublish(left, right, place, cell); }
        if (winner == right.Id) { HCConflictPublish(right, left, place, cell); }
        string outcomeLine = "[HC Plan] HC-37 data_outcome place=" + place.Id + " winner=" + winner + " bodies=0 loot=0 runtime=PENDING";
        if (fixture) { outcomeLine += " fixture=1"; }
        Print("" + outcomeLine);
        if (fixture) { HCModuleReadiness.HCUseFixture("FactionConflict", "outcome_recorded"); }
        else { HCModuleReadiness.HCUse("FactionConflict", "outcome_recorded"); }
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
            if (!HCFactionConflict.HCReserveDataOutcome(place.Id, now)) { return; }
            AddFact("camp_infected_pressure", place.Id, 1);
            AddFact("holdout_alert", place.Id, 1);
            string outcome = "camp_holds";
            if (camp.Occupants == 0)
            {
                HCWorldFaction holder = m_Data.Faction(camp.FactionId);
                if (holder)
                {
                    int claim = holder.Territory.Find(cell);
                    if (claim >= 0) { holder.Territory.Remove(claim); m_Dirty = true; }
                }
                outcome = "empty_camp_claim_falls";
            }
            Print("[HC Plan] HC-37 infected_pressure place=" + place.Id + " outcome=" + outcome + " runtime=PENDING");
            return;
        }
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
        foreach (HCWorldPlace place : places)
        {
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
