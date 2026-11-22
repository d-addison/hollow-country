// E1 / owner direction 2026-11-19: AI react to world events. This file is the ONE
// bounded registry of perceivable incidents; it decides nothing about movement.
// A row is {kind, position, radius, start, expiry, sound range, visual range}.
// Sources (HCIncidentSources.c): vanilla gas zones and helicopter wrecks through their
// own server lifecycle, plus explicit one-line HCWorldIncidents.HCPublish calls at event sources
// that hold REAL coordinates (the world-fact ledger carries only a place id, so it is not a source).
// Group response lives in HCXAIIncidentResponse.c, which reads
// ONLY this registry and only through a member's own perception (HCPerceives).
// Everything is data: kinds, ranges, caps and lifetimes come from the policy below
// (source defaults, optional $profile:HollowCountry/incidents.json, validated, never uncapped).
// ON by default; operator opt-out is $profile:HollowCountry/acceptance/world_incidents.disable.
// Sight: DayZPhysics.c:199 RaycastRV (3_Game/Global), human.c:1417 Human.GetBoneIndexByName,
// Object.c:238 GetBonePositionWS (same head-ray start as DayZPlayerImplementMeleeCombat.c:339).
// Native scripts-1.30.164289: 3_Game/Global/Game.c:1120 IsServer, :1535 GetTime (ms);
// 3_Game/Entities/Object.c:215 IsPendingDeletion; 1_Core/proto/EnScript.c:380 Count,
// :385 Clear, :407 Insert, :470 RemoveOrdered; 1_Core/proto/EnSystem.c:397 FileExist;
// EnConvert.c:210 vector.DistanceSq; 3_Game/tools/JsonFileLoader.c:69 LoadData; EnDebug.c:96 Print.
// Radio: HCLeadModule maps relayed world facts to player-readable papers only. No AI radio
// receiver exists in the repository or in the installed Expansion AI scripts, so AI learn by
// perception alone; that fact is logged once at start. Runtime acceptance PENDING.
class HCWorldIncidentKind
{
    string Kind;
    string FactKind;
    string Response;
    float Radius;
    float SoundRange;
    int SoundSeconds;
    float VisualRange;
    int LifetimeSeconds;
    int Severity;
    string RadioFact;
}

class HCWorldIncidentPolicy
{
    int Version = 1;
    int MaxIncidents = 32;
    int SweepPerTick = 4;
    int MaxResponders = 1;
    float MergeMeters = 5;
    float SightHeightMeters = 1;
    ref array<ref HCWorldIncidentKind> Kinds = new array<ref HCWorldIncidentKind>;

    protected static ref HCWorldIncidentPolicy s_Instance;
    protected static bool s_Loaded;
    protected static bool s_Logged;

    void HCAddKind(string kind, string factKind, string response, float radius, float soundRange, int soundSeconds, float visualRange, int lifetime, int severity, string radioFact)
    {
        HCWorldIncidentKind row = new HCWorldIncidentKind;
        row.Kind = kind;
        row.FactKind = factKind;
        row.Response = response;
        row.Radius = radius;
        row.SoundRange = soundRange;
        row.SoundSeconds = soundSeconds;
        row.VisualRange = visualRange;
        row.LifetimeSeconds = lifetime;
        row.Severity = severity;
        row.RadioFact = radioFact;
        Kinds.Insert(row);
    }

    // Source defaults. Radii mirror the installed vanilla zones (Dynamic 120 m, Local 10 m).
    // Sound/visual ranges and windows are design budgets, not measured; PENDING two-client survey.
    void HCDefaults()
    {
        Kinds.Clear();
        HCAddKind("gas_static", "", "avoid", 100, 0, 0, 150, 0, 1, "");
        HCAddKind("gas_dynamic", "", "avoid", 120, 0, 0, 200, 0, 2, "DANGER");
        HCAddKind("gas_local", "", "avoid", 10, 0, 0, 60, 0, 1, "");
        HCAddKind("crash", "", "investigate", 0, 1500, 180, 400, 0, 2, "EVENT");
        HCAddKind("crash_cold", "", "investigate", 0, 1500, 180, 80, 0, 1, "EVENT");
        HCAddKind("scene", "scene_started", "react", 0, 0, 0, 250, 900, 1, "");
        HCAddKind("raid", "holdout_raided", "react", 0, 600, 300, 250, 900, 2, "");
        HCAddKind("gunfire", "shots_heard", "react", 0, 800, 120, 0, 300, 1, "");
        HCAddKind("horde", "herd_moving", "flee", 80, 300, 120, 300, 600, 2, "");
        HCAddKind("signal_smoke", "", "react", 0, 0, 0, 500, 600, 1, "");
    }

    HCWorldIncidentKind HCFind(string kind)
    {
        array<ref HCWorldIncidentKind> rules = Kinds;
        foreach (HCWorldIncidentKind row : rules)
        {
            if (row.Kind == kind) { return row; }
        }
        return null;
    }

    HCWorldIncidentKind HCFindFact(string factKind)
    {
        if (factKind == "") { return null; }
        array<ref HCWorldIncidentKind> rules = Kinds;
        foreach (HCWorldIncidentKind row : rules)
        {
            if (row.FactKind == factKind) { return row; }
        }
        return null;
    }

    static bool HCRange(float value, float low, float high)
    {
        if (value != value) { return false; }
        return value >= low && value <= high;
    }

    static bool HCResponseKnown(string response)
    {
        return response == "avoid" || response == "investigate" || response == "react" || response == "flee" || response == "none";
    }

    static bool HCKindValid(HCWorldIncidentKind row)
    {
        if (!row) { return false; }
        if (!HCWorldLimits.Token(row.Kind) || row.Kind.Length() > 32) { return false; }
        if (row.FactKind != "" && !HCWorldLimits.Token(row.FactKind)) { return false; }
        if (row.RadioFact != "" && !HCWorldLimits.Token(row.RadioFact)) { return false; }
        if (!HCResponseKnown(row.Response)) { return false; }
        if (!HCRange(row.Radius, 0, 2000) || !HCRange(row.SoundRange, 0, 5000) || !HCRange(row.VisualRange, 0, 2000)) { return false; }
        if (row.SoundSeconds < 0 || row.SoundSeconds > 3600 || row.LifetimeSeconds < 0 || row.LifetimeSeconds > 86400) { return false; }
        return row.Severity >= 0 && row.Severity <= 3;
    }

    // A relayed fact may never be a subscribed fact kind, or the relay would re-enter the registry.
    static bool HCValid(HCWorldIncidentPolicy policy)
    {
        if (!policy || policy.Version != 1) { return false; }
        if (policy.MaxIncidents < 1 || policy.MaxIncidents > 64 || policy.SweepPerTick < 1 || policy.SweepPerTick > 16) { return false; }
        if (policy.MaxResponders < 1 || policy.MaxResponders > 8 || !HCRange(policy.MergeMeters, 0, 100)) { return false; }
        if (!HCRange(policy.SightHeightMeters, 0, 5)) { return false; }
        if (!policy.Kinds || policy.Kinds.Count() < 1 || policy.Kinds.Count() > 24) { return false; }
        for (int rowIndex = 0; rowIndex < policy.Kinds.Count(); rowIndex++)
        {
            HCWorldIncidentKind row = policy.Kinds[rowIndex];
            if (!HCKindValid(row)) { return false; }
            for (int otherIndex = 0; otherIndex < rowIndex; otherIndex++)
            {
                HCWorldIncidentKind other = policy.Kinds[otherIndex];
                if (other.Kind == row.Kind) { return false; }
                if (row.FactKind != "" && other.FactKind == row.FactKind) { return false; }
            }
        }
        array<ref HCWorldIncidentKind> rules = policy.Kinds;
        foreach (HCWorldIncidentKind relayed : rules)
        {
            if (relayed.RadioFact != "" && policy.HCFindFact(relayed.RadioFact)) { return false; }
        }
        return true;
    }

    static bool HCFields(string encoded)
    {
        if (!HCJsonFields.Has(encoded, "Version") || !HCJsonFields.Has(encoded, "MaxIncidents") || !HCJsonFields.Has(encoded, "SweepPerTick")) { return false; }
        if (!HCJsonFields.Has(encoded, "MaxResponders") || !HCJsonFields.Has(encoded, "MergeMeters") || !HCJsonFields.Has(encoded, "SightHeightMeters") || !HCJsonFields.Has(encoded, "Kinds")) { return false; }
        if (!HCJsonFields.Every(encoded, "Kind", 3) || !HCJsonFields.Every(encoded, "FactKind", 3) || !HCJsonFields.Every(encoded, "Response", 3)) { return false; }
        if (!HCJsonFields.Every(encoded, "Radius", 3) || !HCJsonFields.Every(encoded, "SoundRange", 3) || !HCJsonFields.Every(encoded, "SoundSeconds", 3)) { return false; }
        return HCJsonFields.Every(encoded, "VisualRange", 3) && HCJsonFields.Every(encoded, "LifetimeSeconds", 3) && HCJsonFields.Every(encoded, "Severity", 3) && HCJsonFields.Every(encoded, "RadioFact", 3);
    }

    static void HCInvalid(string reason)
    {
        if (s_Logged) { return; }
        s_Logged = true;
        Print("[HC Incidents] INCIDENT_POLICY_INVALID reason=" + reason + " runtime=PENDING");
    }

    static HCWorldIncidentPolicy HCGet()
    {
        if (s_Loaded) { return s_Instance; }
        s_Loaded = true;
        HCWorldIncidentPolicy policy = new HCWorldIncidentPolicy;
        string path = "$profile:HollowCountry/incidents.json";
        if (FileExist(path))
        {
            string encoded;
            string error;
            if (!HCGroupIO.Read(path, 16384, encoded)) { HCInvalid("read"); return null; }
            if (!HCFields(encoded)) { HCInvalid("fields"); return null; }
            if (!JsonFileLoader<HCWorldIncidentPolicy>.LoadData(encoded, policy, error)) { HCInvalid("parse"); return null; }
        }
        else
        {
            policy.HCDefaults();
        }
        if (!HCValid(policy)) { HCInvalid("range"); return null; }
        s_Instance = policy;
        return s_Instance;
    }
}

class HCWorldIncident
{
    int Id;
    string Kind;
    string Response;
    vector Position;
    float Radius;
    int StartAt;
    int ExpiresAt;
    float SoundRange;
    int SoundSeconds;
    float VisualRange;
    int Severity;
    string RadioFact;
    string Faction;
    // Weak by design: the native entity owns its own lifetime; a lost anchor retires the row.
    Object Anchor;
    bool Anchored;
    int Responders;
    bool Reported;
}

class HCWorldIncidents : HCModule
{
    protected static ref HCWorldIncidents s_Instance;
    protected ref HCWorldIncidentPolicy m_Policy;
    protected ref array<ref HCWorldIncident> m_Rows = new array<ref HCWorldIncident>;
    protected ref HCOperationalStatus m_Status = new HCOperationalStatus;
    protected int m_NextId = 1;
    protected int m_Cursor;
    protected int m_Refused;
    protected bool m_Running;
    protected bool m_Off;
    protected bool m_FullLogged;
    protected string m_Refusal;

    override string GetName() { return "WorldIncidents"; }
    override bool IsEnabled(HCSettings settings) { return true; }
    override HCOperationalStatus HCGetOperationalStatus() { return HCStatus(); }

    static HCWorldIncidents HCGet()
    {
        if (!s_Instance) { s_Instance = new HCWorldIncidents; }
        return s_Instance;
    }

    static int HCNowSeconds() { return GetGame().GetTime() / 1000; }

    // Publication points. Server only; every caller is a super-first hook or a one-line call with real coordinates.
    static int HCPublish(string kind, vector position, float radius, int lifetime, Object anchor)
    {
        if (!GetGame() || !GetGame().IsServer()) { return 0; }
        HCWorldIncidents owner = HCWorldIncidents.HCGet();
        return owner.HCAdd(kind, position, radius, lifetime, anchor, HCWorldIncidents.HCNowSeconds());
    }

    // Same, for sources that know which faction the event belongs to (reinforcement by allies).
    static int HCPublishAs(string kind, vector position, float radius, int lifetime, Object anchor, string faction)
    {
        int id = HCWorldIncidents.HCPublish(kind, position, radius, lifetime, anchor);
        if (id > 0) { HCWorldIncidents.HCGet().HCTag(id, faction); }
        return id;
    }

    // Operator opt-out (start-order independent) or a refused/off registry.
    // Operator file is restart-scoped; never probe the filesystem per tick.
    protected static bool s_OptOutRead;
    protected static bool s_OptedOut;

    protected static bool HCOptedOut()
    {
        if (!s_OptOutRead)
        {
            s_OptOutRead = true;
            s_OptedOut = FileExist("$profile:HollowCountry/acceptance/world_incidents.disable");
        }
        return s_OptedOut;
    }

    static bool HCOff()
    {
        if (HCOptedOut()) { return true; }
        return s_Instance && s_Instance.m_Off;
    }

    static void HCRetire(Object anchor)
    {
        if (!s_Instance || !anchor) { return; }
        s_Instance.HCRetireAnchor(anchor);
    }

    void HCStart()
    {
        m_Refusal = "";
        m_Running = false;
        m_Off = false;
        bool optedOut = HCOptedOut();
        Print(HCV2Admission.Line("world_incidents", !optedOut, "native_incident_survey", false) + " runtime=PENDING");
        if (!GetGame() || !GetGame().IsServer())
        {
            m_Off = true;
            m_Refusal = "not_server";
            return;
        }
        if (optedOut)
        {
            m_Off = true;
            return;
        }
        m_Policy = HCWorldIncidentPolicy.HCGet();
        if (!m_Policy)
        {
            m_Off = true;
            m_Refusal = "incident_policy_invalid";
            return;
        }
        m_Running = true;
        Print("[HC Incidents] radio_relay=player_only reason=no_ai_radio_receivers perception=member_sound_or_sight runtime=PENDING");
    }

    override void OnStart(HCSettings settings) { HCStart(); }

    override void OnTick(float deltaTime)
    {
        if (!m_Running) { return; }
        if (!HCServer.HCTickWork().HCTakeFor(HCUnitBudget.HC_WORK_INCIDENTS, 1)) { return; }
        HCSweep(HCWorldIncidents.HCNowSeconds());
        HCReached.Mark("world_incidents.sweep");
    }

    override void OnStop()
    {
        m_Running = false;
        m_Rows.Clear();
        m_Cursor = 0;
    }

    HCOperationalStatus HCStatus()
    {
        HCModuleReadiness.HCDerive(m_Status, m_Running, m_Refusal, "", "incident_registry_loaded");
        return m_Status;
    }

    bool HCActive() { return m_Running; }
    int HCCount() { return m_Rows.Count(); }

    HCWorldIncident HCRowAt(int index)
    {
        if (index < 0 || index >= m_Rows.Count()) { return null; }
        return m_Rows[index];
    }

    HCWorldIncident HCById(int id)
    {
        array<ref HCWorldIncident> rows = m_Rows;
        foreach (HCWorldIncident row : rows)
        {
            if (row.Id == id) { return row; }
        }
        return null;
    }

    HCWorldIncident HCFindSame(string kind, vector position, Object anchor)
    {
        float merge = m_Policy.MergeMeters * m_Policy.MergeMeters;
        array<ref HCWorldIncident> rows = m_Rows;
        foreach (HCWorldIncident row : rows)
        {
            if (anchor && row.Anchored && row.Anchor == anchor) { return row; }
            if (anchor || row.Anchored || row.Kind != kind) { continue; }
            if (vector.DistanceSq(row.Position, position) <= merge) { return row; }
        }
        return null;
    }

    // Returns the incident id, or 0 when refused (unknown kind, no policy, registry full of permanent rows).
    int HCAdd(string kind, vector position, float radius, int lifetime, Object anchor, int now)
    {
        if (m_Off) { return 0; }
        if (!m_Policy) { m_Policy = HCWorldIncidentPolicy.HCGet(); }
        if (!m_Policy) { return 0; }
        HCWorldIncidentKind rule = m_Policy.HCFind(kind);
        if (!rule)
        {
            m_Refused++;
            return 0;
        }
        int life = lifetime;
        if (life < 1) { life = rule.LifetimeSeconds; }
        HCWorldIncident known = HCFindSame(kind, position, anchor);
        if (known)
        {
            if (life > 0 && known.ExpiresAt > 0) { known.ExpiresAt = now + life; }
            return known.Id;
        }
        if (m_Rows.Count() >= m_Policy.MaxIncidents && !HCEvict())
        {
            m_Refused++;
            if (!m_FullLogged)
            {
                m_FullLogged = true;
                Print("[HC Incidents] INCIDENT_REGISTRY_FULL permanent rows only; new incident refused runtime=PENDING");
            }
            return 0;
        }
        HCWorldIncident row = new HCWorldIncident;
        row.Id = m_NextId;
        m_NextId++;
        row.Kind = rule.Kind;
        row.Response = rule.Response;
        row.Position = position;
        row.Radius = radius;
        if (row.Radius <= 0) { row.Radius = rule.Radius; }
        row.StartAt = now;
        row.ExpiresAt = 0;
        if (life > 0) { row.ExpiresAt = now + life; }
        row.SoundRange = rule.SoundRange;
        row.SoundSeconds = rule.SoundSeconds;
        row.VisualRange = rule.VisualRange;
        row.Severity = rule.Severity;
        row.RadioFact = rule.RadioFact;
        row.Reported = rule.RadioFact == "";
        if (anchor)
        {
            row.Anchor = anchor;
            row.Anchored = true;
        }
        m_Rows.Insert(row);
        HCModuleReadiness.HCUseGuarded("WorldIncidents", "incident_recorded", row);
        HCRadio(row);
        return row.Id;
    }

    // Only real repeated emissions renew sound; surveys that re-publish a live
    // source retain its original sound window. Identity, claims and radio stay intact.
    void HCRefreshSound(int id, int now)
    {
        if (m_Off) { return; }
        HCWorldIncident row = HCById(id);
        if (!row || row.SoundRange <= 0 || row.SoundSeconds <= 0) { return; }
        row.StartAt = now;
    }

    // Earliest-expiring transient row goes first; permanent (native-owned) rows are never evicted.
    bool HCEvict()
    {
        int pick = -1;
        int earliest = 0;
        for (int index = 0; index < m_Rows.Count(); index++)
        {
            HCWorldIncident candidate = m_Rows[index];
            if (candidate.ExpiresAt < 1) { continue; }
            if (pick < 0 || candidate.ExpiresAt < earliest)
            {
                pick = index;
                earliest = candidate.ExpiresAt;
            }
        }
        if (pick < 0) { return false; }
        HCRemoveAt(pick);
        return true;
    }

    void HCRemoveAt(int index)
    {
        if (index < 0 || index >= m_Rows.Count()) { return; }
        m_Rows.RemoveOrdered(index);
    }

    void HCRetireAnchor(Object anchor)
    {
        if (!anchor) { return; }
        int index = 0;
        while (index < m_Rows.Count())
        {
            HCWorldIncident row = m_Rows[index];
            if (row.Anchored && row.Anchor == anchor)
            {
                HCRemoveAt(index);
                continue;
            }
            index++;
        }
    }

    void HCRetireId(int id)
    {
        for (int index = 0; index < m_Rows.Count(); index++)
        {
            if (m_Rows[index].Id == id)
            {
                HCRemoveAt(index);
                return;
            }
        }
    }

    // True when the native anchor vanished without its EEDelete hook (e.g. cleaned up by the engine).
    bool HCGone(HCWorldIncident row)
    {
        if (!row.Anchored) { return false; }
        if (!row.Anchor) { return true; }
        return row.Anchor.IsPendingDeletion();
    }

    void HCTag(int id, string faction)
    {
        HCWorldIncident row = HCById(id);
        if (row && faction != "") { row.Faction = faction; }
    }

    // One player-readable relay per incident through the existing lead ledger. Never AI knowledge.
    void HCRadio(HCWorldIncident row)
    {
        if (row.Reported) { return; }
        HCWorldModule world = HCWorldModule.Get();
        if (!world) { return; }
        row.Reported = true;
        string place = world.NearestPlace(row.Position);
        if (place == "") { return; }
        // NearestPlace returns the display name while AddFact wants the id (HCCampModule.Fact).
        place.ToLower();
        world.AddFact(row.RadioFact, place, row.Severity);
    }

    vector HCEye(Human looker)
    {
        int head = looker.GetBoneIndexByName("Head");
        if (head < 0)
        {
            vector feet = looker.GetPosition();
            return Vector(feet[0], feet[1] + 1.6, feet[2]);
        }
        return looker.GetBonePositionWS(head);
    }

    // One bounded raycast from the looker's head to the incident edge (aimed SightHeightMeters up). Any
    // terrain or object before it blocks sight; the anchor's own hull never hides itself. No budget, no sight.
    bool HCClear(HCWorldIncident row, Human looker)
    {
        if (!HCServer.HCTickWork().HCTakeFor(HCUnitBudget.HC_WORK_INCIDENTS, 1)) { return false; }
        vector eye = HCEye(looker);
        float dx = row.Position[0] - eye[0];
        float dz = row.Position[2] - eye[2];
        float flat = Math.Sqrt(dx * dx + dz * dz);
        float keep = 1;
        if (flat > row.Radius && flat > 0.01) { keep = (flat - row.Radius) / flat; }
        else { keep = 0; }
        vector aim = Vector(eye[0] + dx * keep, row.Position[1] + m_Policy.SightHeightMeters, eye[2] + dz * keep);
        vector contact;
        vector normal;
        int component;
        Object hull = row.Anchor;
        return !DayZPhysics.RaycastRV(eye, aim, contact, normal, component, null, hull, looker, false, false, ObjIntersectView, 0.0);
    }

    // A member perceives an incident only inside the sound range while the sound window is open (sound
    // carries around corners), or inside the sight range (measured from the edge) WITH a clear line
    // from its head. Nothing else makes a group aware.
    bool HCPerceives(HCWorldIncident row, Human looker, int now)
    {
        if (!row || !looker) { return false; }
        float distSq = vector.DistanceSq(row.Position, looker.GetPosition());
        if (row.SoundRange > 0 && now - row.StartAt <= row.SoundSeconds && distSq <= row.SoundRange * row.SoundRange) { return true; }
        float seen = row.Radius + row.VisualRange;
        if (row.VisualRange > 0 && distSq <= seen * seen) { return HCClear(row, looker); }
        return false;
    }

    bool HCClaim(HCWorldIncident row)
    {
        if (!row || row.Responders >= m_Policy.MaxResponders) { return false; }
        row.Responders = row.Responders + 1;
        return true;
    }

    void HCRelease(int id)
    {
        HCWorldIncident row = HCById(id);
        if (row && row.Responders > 0) { row.Responders = row.Responders - 1; }
    }

    // At most SweepPerTick rows are examined per call; the cursor resumes where the last call ended.
    void HCSweep(int now)
    {
        if (!m_Policy) { return; }
        int examined = 0;
        while (examined < m_Policy.SweepPerTick && m_Rows.Count() > 0)
        {
            if (m_Cursor >= m_Rows.Count()) { m_Cursor = 0; }
            HCWorldIncident row = m_Rows[m_Cursor];
            examined++;
            if (row.ExpiresAt > 0 && row.ExpiresAt <= now)
            {
                HCRemoveAt(m_Cursor);
                continue;
            }
            if (HCGone(row))
            {
                HCRemoveAt(m_Cursor);
                continue;
            }
            HCRadio(row);
            m_Cursor++;
        }
    }
}

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        Register(HCWorldIncidents.HCGet());
    }
}
