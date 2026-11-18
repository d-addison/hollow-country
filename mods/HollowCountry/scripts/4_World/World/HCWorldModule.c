// LC-T303 traces only; LC-T401 catalog lives in 3_Game. Native evidence:
// scripts-1.30.164289/1_Core/proto/EnScript.c:380,385,407 (arrays),
// 1_Core/proto/EnSystem.c:76,100 (UTC via HCWorldClock),
// 3_Game/tools/JsonFileLoader.c:69,85 (snapshot cloning).
// 1_Core/proto/EnConvert.c:30 (int.ToString),
// 1_Core/proto/EnDebug.c:96 (Print); EnScript.c:389 array.Set.
// HCModule/HCModuleRegistry lifecycle is the project's runtime contract.
// No provider bodies, entities, inventories, RPCs or player state here.
class HCWorldModule : HCModule
{
    protected static HCWorldModule s_Instance;
    protected ref HCWorldStore m_Store;
    protected ref HCWorldData m_Data;
    protected bool m_Running;
    protected bool m_AdmissionPrinted;
    protected bool m_Dirty;
    protected float m_StepSeconds;
    protected float m_SaveSeconds;
    protected int m_Cursor;
    protected int m_StepsSinceSave;
    protected string m_HoldoutRefusal;

    static HCWorldModule Get()
    {
        if (s_Instance && s_Instance.m_Running) { return s_Instance; }
        return null;
    }

    override string GetName() { return "World"; }

    override bool IsEnabled(HCSettings settings)
    {
        return settings && settings.EnableWorld;
    }

    override void OnStart(HCSettings settings)
    {
        if (m_Running || !IsEnabled(settings)) { return; }
        if (!m_AdmissionPrinted)
        {
            Print(HCV2Admission.Line("World", true, "EXP-P1", HCV2Gates.Qualified("EXP-P1")));
            m_AdmissionPrinted = true;
        }
        int now = HCWorldClock.UTC();
        if (now < 1)
        {
            Print("[HollowCountry] V2 world unavailable: unsupported UTC clock");
            return;
        }
        m_Store = new HCWorldStore;
        if (!m_Store.Load())
        {
            Print("[HollowCountry] V2 world unavailable: profile or UTC inaccessible");
            return;
        }
        m_Data = m_Store.Data();
        m_Data.Escalation.Day = HCWorldClock.Day(m_Data, now);
        m_Dirty = m_Store.Fresh();
        foreach (HCWorldParty restartedParty : m_Data.Parties)
        {
            if (restartedParty.Materialized)
            {
                restartedParty.Materialized = false;
                restartedParty.LastMoved = now;
                m_Dirty = true;
            }
        }
        m_Cursor = 0;
        m_StepSeconds = 0;
        m_SaveSeconds = 0;
        m_Running = true;
        s_Instance = this;
        Print("[HollowCountry] V2 world loaded day=" + Day().ToString() + " places=" + m_Data.Places.Count().ToString() + " facts=" + m_Data.Facts.Count().ToString() + " factions=" + m_Data.Factions.Count().ToString());
    }

    override void OnTick(float deltaTime)
    {
        if (!m_Running || !(deltaTime > 0)) { return; }
        // Long stalls never produce a burst of catch-up steps or saves.
        float elapsed = deltaTime;
        if (elapsed > 60) { elapsed = 60; }
        m_StepSeconds += elapsed;
        m_SaveSeconds += elapsed;
        if (m_SaveSeconds > 60) { m_SaveSeconds = 60; }
        if (m_StepSeconds >= 60)
        {
            m_StepSeconds = 0;
            HCWorldStep(HCWorldClock.UTC());
        }
        if (m_Dirty && m_SaveSeconds >= 60)
        {
            m_SaveSeconds = 0;
            if (m_Store.Save(m_Data)) { m_Dirty = false; m_StepsSinceSave = 0; }
        }
    }

    override void OnStop()
    {
        if (!m_Running) { return; }
        s_Instance = null;
        m_Running = false;
        if (m_Dirty && m_Store.Save(m_Data)) { m_Dirty = false; m_StepsSinceSave = 0; }
    }

    // A row means one faction, hold-out or abstract party. Store serialization
    // is a separate, bounded whole-image operation, at most once per minute.
    protected void HCWorldStep(int now)
    {
        if (now < 1) { return; }
        int factionRows = m_Data.Factions.Count();
        int holdoutRows = m_Data.Holdouts.Count();
        int totalRows = factionRows + holdoutRows + m_Data.Parties.Count();
        int work = HCWorldLimits.STEP_ROWS;
        if (work > totalRows) { work = totalRows; }
        for (int workIndex = 0; workIndex < work; workIndex++)
        {
            if (m_Cursor >= totalRows) { m_Cursor = 0; }
            int rowIndex = m_Cursor;
            m_Cursor++;
            if (rowIndex < factionRows)
            {
                StepFaction(m_Data.Factions[rowIndex], now);
            }
            else
            {
                if (rowIndex < factionRows + holdoutRows)
                {
                    StepHoldout(m_Data.Holdouts[rowIndex - factionRows], now);
                }
                else
                {
                    StepParty(m_Data.Parties[rowIndex - factionRows - holdoutRows], now);
                }
            }
        }
        // V2 settlement decay/faction conflict reads the previous day from LastTick,
        // so it runs before the stamp moves.
        HCFactionConflict.Tick(this, m_Data, now);
        m_Data.Meta.LastTick = now;
        m_Data.Escalation.Day = HCWorldClock.Day(m_Data, now);
        // Review P2: the tick stamp alone does not need a save every minute;
        // persist the stepped rows at most every ten steps unless a row changed.
        m_StepsSinceSave = m_StepsSinceSave + 1;
        if (m_StepsSinceSave >= 10) { m_Dirty = true; }
    }

    protected void StepFaction(HCWorldFaction faction, int now)
    {
        if (faction.LastAlertDecay == 0) { faction.LastAlertDecay = now; }
        if (now - faction.LastAlertDecay < 3600) { return; }
        int decay = (now - faction.LastAlertDecay) / 3600;
        faction.Alert -= decay;
        if (faction.Alert < 0) { faction.Alert = 0; }
        faction.LastAlertDecay += decay * 3600;
        // Conflict and materializer outcomes adjust finite strength through AdjustStrength.
    }

    protected void StepHoldout(HCWorldHoldout holdout, int now)
    {
        if (holdout.State == "RAIDED" && now >= holdout.ReoccupyAfter)
        {
            holdout.State = "DORMANT";
            holdout.Since = now;
            holdout.Routine = "AWAITING_OCCUPANTS";
        }
        if (holdout.State == "ALERT" && now - holdout.Since >= 3600)
        {
            holdout.State = "OCCUPIED";
            holdout.Since = now;
        }
        if (holdout.State == "OCCUPIED" || holdout.State == "ALERT")
        {
            // Abstract daily life only. No item transfers, lit windows or
            // invented replacement survivors; LC-T408 owns those integrations.
            int hour = (now % HCWorldLimits.DAY) / 3600;
            holdout.Routine = "SHELTER";
            if (hour >= 6 && hour < 18) { holdout.Routine = "DAY"; }
        }
    }

    protected void StepParty(HCWorldParty party, int now)
    {
        int today = HCWorldClock.Day(m_Data, now);
        if (party.TransferDay != today)
        {
            party.DailyTransfers = 0;
            party.TransferDay = today;
        }
        // A later body lease owns movement while materialized. On load there
        // are no retained bodies; no entity handle or position is persisted.
        if (party.Materialized) { return; }
        if (party.LastMoved == 0) { party.LastMoved = now; return; }
        if (now <= party.LastMoved) { return; }
        // Provisional one wall-clock hour per named-place edge. At most one
        // edge per processed row, even across downtime; never an entity move.
        float seconds = now - party.LastMoved;
        party.Progress += seconds / 3600.0;
        party.LastMoved = now;
        if (party.Progress >= 1)
        {
            party.Progress = 0;
            party.Edge = (party.Edge + 1) % party.Route.Count();
            AddFact("party_passed", party.Route[party.Edge], 0);
        }
    }

    // UTC seconds, zero-based since Meta.Epoch; no accelerated game dates.
    int Day()
    {
        if (!m_Running) { return 0; }
        int now = HCWorldClock.UTC();
        if (now < 1) { return m_Data.Escalation.Day; }
        return HCWorldClock.Day(m_Data, now);
    }

    int WorldDay() { return Day(); }

    int Epoch()
    {
        if (!m_Running) { return 0; }
        return m_Data.Meta.Epoch;
    }

    // Accept either a stable place ID or the authored display name. Generic
    // short fact kinds are data; callers must supply observed world facts and
    // must never put an identity, live position or free-form player text here.
    bool AddFact(string kind, string place, int severity)
    {
        if (!m_Running) { return false; }
        HCWorldPlace anchor = m_Data.Place(place);
        if (!anchor || !HCWorldLimits.Token(kind) || severity < 0 || severity > 3) { return false; }
        int now = HCWorldClock.UTC();
        if (now < m_Data.Meta.Epoch) { return false; }
        if (kind == "party_passed")
        {
            foreach (HCWorldFact priorPass : m_Data.Facts)
            {
                bool samePlace = priorPass.Kind == kind && priorPass.PlaceId == anchor.Id;
                bool recentPass = priorPass.At <= now && now - priorPass.At < 21600;
                if (samePlace && recentPass && priorPass.Expires > now) { return true; }
            }
        }
        HCWorldFact fact = new HCWorldFact;
        fact.Kind = kind;
        fact.PlaceId = anchor.Id;
        fact.Severity = severity;
        fact.At = now;
        fact.Expires = now + HCWorldLimits.FACT_LIFETIME;
        if (!m_Data.AppendFact(fact)) { return false; }
        m_Dirty = true;
        return true;
    }

    // Re-publication repairs an interrupted world write using the durable
    // transition time. It never grants a restart another full fact lifetime.
    bool AddHoldoutFact(HCWorldHoldout row)
    {
        if (!m_Running || !m_Data.HoldoutValid(row)) { return false; }
        if (row.State != "RAIDED" && row.State != "ABANDONED") { return true; }
        HCWorldPlace anchor = m_Data.Place(row.PlaceId);
        int now = HCWorldClock.UTC();
        if (row.Since < m_Data.Meta.Epoch || row.Since > now) { return false; }
        if (now - row.Since >= HCWorldLimits.FACT_LIFETIME) { return true; }
        foreach (HCWorldFact priorTransition : m_Data.Facts)
        {
            // Legacy publishes stamped At with publication time (>= Since).
            // Keep that existing fact and expiry as well as exact-time rows.
            if (priorTransition.Kind == row.State && priorTransition.PlaceId == anchor.Id && priorTransition.At >= row.Since && priorTransition.At <= now) { return true; }
        }
        HCWorldFact fact = new HCWorldFact;
        fact.Kind = row.State;
        fact.PlaceId = anchor.Id;
        fact.Severity = 1;
        if (row.State == "RAIDED") { fact.Severity = 2; }
        fact.At = row.Since;
        fact.Expires = row.Since + HCWorldLimits.FACT_LIFETIME;
        if (!m_Data.AppendFact(fact)) { return false; }
        m_Dirty = true;
        return true;
    }

    // maxAge is real seconds. Newest first, expired/future rows excluded;
    // copies keep consumers from mutating stored facts or bypassing dirty state.
    void GetRecentFacts(int maxAge, array<ref HCWorldFact> output)
    {
        if (!output) { return; }
        output.Clear();
        if (!m_Running || maxAge < 0) { return; }
        int now = HCWorldClock.UTC();
        int factCount = m_Data.Facts.Count();
        for (int factOffset = 0; factOffset < factCount; factOffset++)
        {
            int factIndex = factCount - 1 - factOffset;
            if (factCount == HCWorldLimits.FACTS) { factIndex = (m_Data.FactHead + factCount - 1 - factOffset) % factCount; }
            HCWorldFact stored = m_Data.Facts[factIndex];
            if (stored.At > now || stored.Expires <= now || now - stored.At > maxAge) { continue; }
            HCWorldFact copy = new HCWorldFact;
            copy.Kind = stored.Kind;
            copy.PlaceId = stored.PlaceId;
            copy.Severity = stored.Severity;
            copy.At = stored.At;
            copy.Expires = stored.Expires;
            output.Insert(copy);
        }
    }

    string NearestPlace(vector pos)
    {
        if (!m_Running || !HCWorldLimits.Position(pos)) { return ""; }
        string nearest;
        float best = 2250000; // 1500 m horizontal naming cap.
        foreach (HCWorldPlace candidate : m_Data.Places)
        {
            float dx = pos[0] - candidate.Position[0];
            float dz = pos[2] - candidate.Position[2];
            float distance = dx * dx + dz * dz;
            if (distance <= best)
            {
                best = distance;
                nearest = candidate.Name;
            }
        }
        return nearest;
    }

    HCWorldFaction GetFaction(string id)
    {
        if (!m_Running) { return null; }
        HCWorldFaction stored = m_Data.Faction(id);
        if (!stored) { return null; }
        HCWorldFaction copy;
        string text;
        string error;
        if (!JsonFileLoader<HCWorldFaction>.MakeData(stored, text, error)) { return null; }
        if (!JsonFileLoader<HCWorldFaction>.LoadData(text, copy, error)) { return null; }
        return copy;
    }

    int Relation(string a, string b)
    {
        return HCWorldFactionCatalog.Relation(a, b);
    }

    // Narrow registration seams for authored downstream catalogs. Copy on input
    // so an external caller cannot mutate a retained row or evade admission.
    bool AddHoldout(HCWorldHoldout row)
    {
        if (!m_Running || !m_Data.HoldoutValid(row)) { return false; }
        HCWorldHoldout copy;
        string text;
        string error;
        if (!JsonFileLoader<HCWorldHoldout>.MakeData(row, text, error) || !JsonFileLoader<HCWorldHoldout>.LoadData(text, copy, error) || !m_Data.InsertHoldout(copy)) { return false; }
        m_Dirty = true;
        return true;
    }

    // Validated copy-on-input refresh; replacing a row never changes its index.
    // Synchronous refusal detail for the immediately preceding upsert only.
    string HoldoutRefusal() { return m_HoldoutRefusal; }

    bool UpsertHoldout(HCWorldHoldout row)
    {
        m_HoldoutRefusal = "world inactive";
        if (!m_Running) { return false; }
        m_HoldoutRefusal = "invalid holdout";
        if (!m_Data.HoldoutValid(row)) { return false; }
        int rowIndex = -1;
        int occupiedOthers = 0;
        for (int holdoutIndex = 0; holdoutIndex < m_Data.Holdouts.Count(); holdoutIndex++)
        {
            HCWorldHoldout stored = m_Data.Holdouts[holdoutIndex];
            if (stored.Id == row.Id) { rowIndex = holdoutIndex; }
            if (stored.Id != row.Id && stored.Occupants > 0) { occupiedOthers++; }
        }
        m_HoldoutRefusal = "occupied cap";
        if (row.Occupants > 0 && occupiedOthers >= HCWorldLimits.OCCUPIED) { return false; }
        HCWorldHoldout copy = new HCWorldHoldout;
        copy.Id = row.Id;
        copy.PlaceId = row.PlaceId;
        copy.FactionId = row.FactionId;
        copy.HouseClass = row.HouseClass;
        copy.HousePos = row.HousePos;
        copy.CacheRef = row.CacheRef;
        copy.Occupants = row.Occupants;
        copy.State = row.State;
        copy.Since = row.Since;
        copy.ReoccupyAfter = row.ReoccupyAfter;
        copy.Routine = row.Routine;
        if (rowIndex >= 0) { m_Data.Holdouts.Set(rowIndex, copy); }
        else
        {
            // Refuse before InsertHoldout's generic cap log: the publisher
            // reports this reason once per holdout instead of once per tick.
            m_HoldoutRefusal = "catalog cap";
            if (m_Data.Holdouts.Count() >= HCWorldLimits.HOLDOUTS) { return false; }
            m_HoldoutRefusal = "catalog admission";
            if (!m_Data.InsertHoldout(copy)) { return false; }
        }
        m_HoldoutRefusal = "";
        m_Dirty = true;
        Print("[HollowCountry] V2 world holdout id=" + row.Id + " state=" + row.State);
        return true;
    }

    bool AdjustStrength(string faction, int delta)
    {
        if (!m_Running) { return false; }
        HCWorldFaction targetFaction = m_Data.Faction(faction);
        if (!targetFaction) { return false; }
        // Clamp before adding, including extreme caller deltas, without overflow.
        int strength = targetFaction.Strength;
        int room = HCWorldLimits.STRENGTH - strength;
        if (delta > 0)
        {
            if (delta >= room) { strength = HCWorldLimits.STRENGTH; }
            else { strength = strength + delta; }
        }
        if (delta < 0)
        {
            if (delta <= -strength) { strength = 0; }
            else { strength = strength + delta; }
        }
        if (strength == targetFaction.Strength) { return true; }
        targetFaction.Strength = strength;
        if (strength == 0) { targetFaction.Territory.Clear(); }
        m_Dirty = true;
        Print("[HollowCountry] V2 world strength faction=" + faction + " strength=" + strength.ToString());
        return true;
    }

    bool AddParty(HCWorldParty row)
    {
        if (!m_Running || !m_Data.PartyValid(row) || row.Materialized) { return false; }
        HCWorldParty copy;
        string text;
        string error;
        if (!JsonFileLoader<HCWorldParty>.MakeData(row, text, error) || !JsonFileLoader<HCWorldParty>.LoadData(text, copy, error) || !m_Data.InsertParty(copy)) { return false; }
        m_Dirty = true;
        return true;
    }

    // Record an actual downstream raid result, with no stock/loot operation.
    bool MarkHoldoutRaided(string id)
    {
        if (!m_Running) { return false; }
        foreach (HCWorldHoldout holdout : m_Data.Holdouts)
        {
            if (holdout.Id != id) { continue; }
            if (holdout.State == "RAIDED") { return false; }
            int now = HCWorldClock.UTC();
            if (now < m_Data.Meta.Epoch) { return false; }
            holdout.State = "RAIDED";
            holdout.Occupants = 0;
            holdout.Since = now;
            holdout.ReoccupyAfter = now + 7 * HCWorldLimits.DAY;
            holdout.Routine = "LOCKOUT";
            AddFact("holdout_raided", holdout.PlaceId, 2);
            m_Dirty = true;
            return true;
        }
        return false;
    }
}

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        Register(new HCWorldModule);
    }
}
