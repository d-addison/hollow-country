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
// entirely to HCEncounterStore (HCHoldouts.c:28); no new save scheduler.
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
    protected string m_Declined;
    protected string m_StatusReason;
    protected bool m_ProviderLogged;
    protected int m_ActorCursor;
    protected int m_CallbackFrame = -1;
    protected ref HCUnitBudget m_CallbackUnits = new HCUnitBudget;

    override string GetName() { return "FactionConflict"; }
    override HCOperationalStatus HCGetOperationalStatus() { return m_Operational; }
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
        s_Active = true;
        s_WorkNow = -1;
        s_Instance = this;
        m_Store = new HCEncounterStore<HCTerritoryOutcomeData>("faction-outcomes");
        m_Outcomes = m_Store.Load(new HCTerritoryOutcomeData, "Rows");
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
        if (m_Current || m_Outcomes.Rows.Count() >= HCTerritoryOutcomes.MAX_ROWS)
        {
            HCDecline("ENCOUNTER_OR_HISTORY_CAP");
            return "";
        }
        if (leftIdentity.HCPartyId() == rightIdentity.HCPartyId() || leftIdentity.HCCargoId() == rightIdentity.HCCargoId()) { return ""; }
        if (!s_CombatPort.HCSurveyed(place, survey)) { HCDecline("CONTESTED_SURVEY_UNVERIFIED"); return ""; }
        for (int checkedLeft = 0; checkedLeft < left.Count(); checkedLeft++)
        {
            Object leftBody = left[checkedLeft];
            if (!leftBody || !leftBody.IsAlive() || !s_CombatPort.HCOwns(leftLease, leftFaction, leftBody, place, survey)) { return ""; }
            if (left.Find(leftBody) != checkedLeft || right.Find(leftBody) >= 0) { return ""; }
        }
        for (int checkedRight = 0; checkedRight < right.Count(); checkedRight++)
        {
            Object rightBody = right[checkedRight];
            if (!rightBody || !rightBody.IsAlive() || !s_CombatPort.HCOwns(rightLease, rightFaction, rightBody, place, survey)) { return ""; }
            if (right.Find(rightBody) != checkedRight) { return ""; }
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
        if (!s_Active || !m_Healthy) { return; }
        HCRefreshStatus();
        if (!m_Current || !(deltaTime > 0)) { return; }
        m_Units.HCReset(1);
        m_Work.HCReset(1);
        if (!m_Units.HCTake(1) || !m_Work.HCContinue()) { return; }
        int total = m_LeftActors.Count() + m_RightActors.Count();
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
        for (int placeIndex = 0; placeIndex < data.Places.Count(); placeIndex++)
        {
            bool claim = false;
            if (faction.Id == "locals" && placeIndex % 4 == 0) { claim = true; }
            if (faction.Id == "volunteers" && placeIndex % 4 == 1) { claim = true; }
            if (faction.Id == "scavengers" && placeIndex % 4 == 2) { claim = true; }
            if (faction.Id == "travellers" && placeIndex % 4 == 3) { claim = true; }
            if (faction.Id == "raiders" && placeIndex % 3 == 1) { claim = true; }
            string cell = Cell(data.Places[placeIndex].Position);
            if (claim && faction.Territory.Find(cell) < 0 && faction.Territory.Count() < HCWorldLimits.TERRITORY) { faction.Territory.Insert(cell); }
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
