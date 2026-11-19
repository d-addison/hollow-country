// s2-tactics: dynamic AI tactics for Hollow Country AI groups.
//  (a) Smoke cover: when a group is under effective fire (weapon hits and close
//      bullet impacts, counted per group) or a group mate is down while the
//      group is in combat, a member that PERCEIVES a threat (line of sight in
//      its own eAI target list) and carries a real smoke grenade throws it
//      toward the threat, short of it, and the pin is pulled once it left the
//      inventory. Consumed, never spawned.
//  (b) Infected lure: when perceived infected pressure a group (enough of them
//      in line of sight, close enough to matter, no human threat in view), a
//      member throws a real empty can or bottle to the side, away from the
//      group, and one native noise is emitted where it lands.
// No omniscience: only the acting member's own eAI target list with m_LOS is read;
// no player list is ever enumerated. Everything is config driven
// ($profile:HollowCountry/expansion-ai-tactics.json, shipped default in this
// addon), on by default, with three named opt-outs in that file: Disabled,
// SmokeDisabled and LureDisabled.
// Throw, drop, activation and noise capabilities with their native file:line
// and verified/unverified status are listed at the top of HCXAIThrowables.c.
// Expansion references (read-only, nothing copied): eAIBase.c:466 eAI_GetAll,
// :1931 GetTargets, :1344 EEHitBy and eAI_OnNoiseEvent (override pattern as in
// HCXDefence.c); eAITargetInformation.c:130 IsZombie, :115 IsNoise, :105 IsItem;
// eAITarget GetPosition (last known, not the live position);
// eAIGroup.c:1123 IsInCombat, :1139 GetMember, :1185 Count, :695 GetID.
// Vanilla: PlayerBase.c:3925 IsUnconscious, Weapon_Base (a hit by a weapon is
// effective fire; the native damage-type constants are not in the scripts).
// Runtime acceptance PENDING: nothing here was observed in DayZ.
class HCXAITacticsPolicy
{
    static const string FILE = "expansion-ai-tactics.json";
    // Structural bounds (array sizes, not gameplay tunables).
    static const int FIRE_RING = 10;
    static const int MAX_PENDING = 8;
    static const int TARGET_SCAN_MAX = 16;
    static const int MEMBER_SCAN_MAX = 16;
    static const int SCAN_TIMEOUT_MS = 30000;
    static const int BACKOFF_MAX = 32;

    // Zero-filled (missing) and out-of-range values fall back to the default.
    static int ClampInt(int value, int fallback, int lo, int hi)
    {
        if (value < lo || value > hi) { return fallback; }
        return value;
    }

    static float ClampFloat(float value, float fallback, float lo, float hi)
    {
        if (value != value || value < lo || value > hi) { return fallback; }
        return value;
    }

    static bool Allowed(bool globalDisabled, bool featureDisabled)
    {
        return !globalDisabled && !featureDisabled;
    }

    static bool Recent(int nowMs, int eventMs, int windowMs)
    {
        return eventMs > 0 && nowMs >= eventMs && nowMs - eventMs <= windowMs;
    }

    // "fire" or "downed" when a trigger holds and a threat is perceived in range;
    // otherwise the named refusal. NaN distance counts as not perceived.
    static string SmokeDecision(int fireEvents, int eventsRequired, bool downedMate, bool perceived, float distance, float minMeters, float maxMeters)
    {
        string trigger = "";
        if (downedMate) { trigger = "downed"; }
        if (fireEvents >= eventsRequired) { trigger = "fire"; }
        if (trigger == "") { return "no_trigger"; }
        if (!perceived || distance != distance) { return "no_perceived_threat"; }
        if (distance < minMeters) { return "threat_too_close"; }
        if (distance > maxMeters) { return "threat_too_far"; }
        return trigger;
    }

    static string Gate(int nowMs, int lastMs, int cooldownMs, int uses, int cap)
    {
        if (lastMs > 0 && nowMs >= lastMs && nowMs - lastMs < cooldownMs) { return "cooldown"; }
        if (cap > 0 && uses >= cap) { return "group_cap"; }
        return "";
    }

    static bool WindowExpired(int nowMs, int startMs, int windowMs)
    {
        if (startMs <= 0) { return true; }
        return nowMs - startMs >= windowMs;
    }

    static bool TrackedFull(int count, int cap)
    {
        return count >= cap;
    }

    // Distance the smoke lands from the thrower: at most the configured fraction
    // of the way to the threat, never beyond the throw reach.
    static float ThrowMeters(float distance, float throwMeters, int fractionPct)
    {
        float reach = distance * fractionPct / 100.0;
        return Math.Min(throwMeters, reach);
    }

    static float ThrowForce(float meters, float maxMeters, float forceMin, float forceMax)
    {
        if (maxMeters <= 0) { return forceMax; }
        float ratio = meters / maxMeters;
        if (ratio > 1.0) { ratio = 1.0; }
        if (ratio < 0.0) { ratio = 0.0; }
        return forceMin + (forceMax - forceMin) * ratio;
    }

    // "" when a lure is justified, else the named refusal.
    static string LureDecision(int infected, int minInfected, float nearest, float minMeters, float maxMeters, bool humanThreat)
    {
        if (humanThreat) { return "human_threat"; }
        if (infected < minInfected) { return "no_infected"; }
        if (nearest != nearest || nearest < minMeters) { return "too_close"; }
        if (nearest > maxMeters) { return "too_far"; }
        return "";
    }

    static bool SmokeTypeOk(string typeName, string exclude)
    {
        if (exclude != "" && typeName.Contains(exclude)) { return false; }
        return true;
    }

    // typeList is "|A|B|": whole-token match only.
    static bool NoisyItemOk(string typeList, string typeName, bool hasQuantity, float quantity, bool allowFull)
    {
        if (typeName == "") { return false; }
        if (!typeList.Contains("|" + typeName + "|")) { return false; }
        if (allowFull) { return true; }
        if (!hasQuantity) { return true; }
        return quantity <= 0;
    }

    // wait: still carried; activate: on the ground and pinned (smoke) or landed
    // (lure); done: pin already pulled; give_up: never left the inventory or the
    // bounded retries are spent.
    static string ActivateStep(bool held, bool pinned, int tries, int maxTries, int ageMs, int maxAgeMs)
    {
        if (!pinned) { return "done"; }
        if (held)
        {
            if (ageMs > maxAgeMs) { return "give_up"; }
            return "wait";
        }
        if (tries >= maxTries) { return "give_up"; }
        return "activate";
    }

    // thrown: the native throw call went out; dropped: its preconditions refused
    // and the real item was put on the ground instead; failed: neither moved the
    // item, so nothing is queued and no use is counted.
    static string ThrowOutcome(string refusal, bool dropped)
    {
        if (refusal == "") { return "thrown"; }
        if (dropped) { return "dropped"; }
        return "failed";
    }

    // What one pending entry needs next. step is ActivateStep's verdict; landed is
    // true once the lure landing delay has passed.
    // remove_lost: counted lost and named; remove_activated: smoke is live;
    // activate_smoke: pull the pin now; noise_remove: emit the one lure noise.
    static string PendingAction(bool gone, bool smoke, string step, bool landed)
    {
        if (gone)
        {
            if (smoke) { return "remove_lost"; }
            return "remove";
        }
        if (step == "give_up") { return "remove_lost"; }
        if (step == "done")
        {
            if (smoke) { return "remove_activated"; }
            return "remove";
        }
        if (step == "activate")
        {
            if (smoke) { return "activate_smoke"; }
            if (landed) { return "noise_remove"; }
        }
        return "keep";
    }

    // Per-actor stock backoff: an empty scan blocks only that member.
    static bool BackedOff(int nowMs, int untilMs)
    {
        return untilMs > 0 && nowMs < untilMs;
    }

    static int BackoffUntil(int nowMs, int cooldownMs)
    {
        return nowMs + cooldownMs;
    }
}

class HCXAITacticsConfig
{
    int SchemaVersion;
    bool Disabled;
    bool SmokeDisabled;
    bool LureDisabled;
    bool LureAllowFull;
    string SmokeExclude;
    string LureTypes;
    string LureNoisePath;
    int CapWindowSec;
    int SmokeCooldownSec;
    int SmokeGroupCap;
    int SmokeFireEvents;
    int FireWindowSec;
    float NearMissMeters;
    float SmokeMinThreatMeters;
    float SmokeMaxThreatMeters;
    float SmokeThrowMeters;
    int SmokeThreatFractionPct;
    int SmokeActivationTries;
    int ActivateWaitSec;
    float ThrowForceMin;
    float ThrowForceMax;
    int ThrowLiftPct;
    int LureCooldownSec;
    int LureGroupCap;
    int LureMinInfected;
    float LureMinInfectedMeters;
    float LureMaxInfectedMeters;
    float LureThrowMeters;
    int LureLandDelayMs;
    int LureNoiseMultPct;
    int TickActors;
    int ScanLimit;
    int TrackedGroups;
    int CheckEverySec;

    // Validated ranges; the shipped JSON mirrors these defaults (pinned by a test).
    void Normalise()
    {
        SchemaVersion = 1;
        CapWindowSec = HCXAITacticsPolicy.ClampInt(CapWindowSec, 600, 60, 86400);
        SmokeCooldownSec = HCXAITacticsPolicy.ClampInt(SmokeCooldownSec, 90, 10, 3600);
        SmokeGroupCap = HCXAITacticsPolicy.ClampInt(SmokeGroupCap, 3, 1, 20);
        SmokeFireEvents = HCXAITacticsPolicy.ClampInt(SmokeFireEvents, 2, 1, 10);
        FireWindowSec = HCXAITacticsPolicy.ClampInt(FireWindowSec, 8, 2, 60);
        NearMissMeters = HCXAITacticsPolicy.ClampFloat(NearMissMeters, 6.0, 1.0, 30.0);
        SmokeMinThreatMeters = HCXAITacticsPolicy.ClampFloat(SmokeMinThreatMeters, 15.0, 5.0, 100.0);
        SmokeMaxThreatMeters = HCXAITacticsPolicy.ClampFloat(SmokeMaxThreatMeters, 120.0, 20.0, 400.0);
        SmokeThrowMeters = HCXAITacticsPolicy.ClampFloat(SmokeThrowMeters, 12.0, 3.0, 40.0);
        SmokeThreatFractionPct = HCXAITacticsPolicy.ClampInt(SmokeThreatFractionPct, 40, 10, 90);
        SmokeActivationTries = HCXAITacticsPolicy.ClampInt(SmokeActivationTries, 4, 1, 10);
        ActivateWaitSec = HCXAITacticsPolicy.ClampInt(ActivateWaitSec, 10, 2, 60);
        ThrowForceMin = HCXAITacticsPolicy.ClampFloat(ThrowForceMin, 20.0, 5.0, 200.0);
        ThrowForceMax = HCXAITacticsPolicy.ClampFloat(ThrowForceMax, 60.0, 5.0, 200.0);
        ThrowLiftPct = HCXAITacticsPolicy.ClampInt(ThrowLiftPct, 40, 5, 100);
        LureCooldownSec = HCXAITacticsPolicy.ClampInt(LureCooldownSec, 120, 10, 3600);
        LureGroupCap = HCXAITacticsPolicy.ClampInt(LureGroupCap, 3, 1, 20);
        LureMinInfected = HCXAITacticsPolicy.ClampInt(LureMinInfected, 3, 1, 20);
        LureMinInfectedMeters = HCXAITacticsPolicy.ClampFloat(LureMinInfectedMeters, 12.0, 3.0, 60.0);
        LureMaxInfectedMeters = HCXAITacticsPolicy.ClampFloat(LureMaxInfectedMeters, 60.0, 15.0, 200.0);
        LureThrowMeters = HCXAITacticsPolicy.ClampFloat(LureThrowMeters, 25.0, 8.0, 60.0);
        LureLandDelayMs = HCXAITacticsPolicy.ClampInt(LureLandDelayMs, 1200, 200, 5000);
        LureNoiseMultPct = HCXAITacticsPolicy.ClampInt(LureNoiseMultPct, 100, 10, 300);
        TickActors = HCXAITacticsPolicy.ClampInt(TickActors, 4, 1, 32);
        ScanLimit = HCXAITacticsPolicy.ClampInt(ScanLimit, 48, 8, 128);
        TrackedGroups = HCXAITacticsPolicy.ClampInt(TrackedGroups, 32, 4, 128);
        CheckEverySec = HCXAITacticsPolicy.ClampInt(CheckEverySec, 2, 1, 60);
        if (ThrowForceMin > ThrowForceMax) { ThrowForceMin = 20.0; ThrowForceMax = 60.0; }
        if (SmokeMinThreatMeters >= SmokeMaxThreatMeters) { SmokeMinThreatMeters = 15.0; SmokeMaxThreatMeters = 120.0; }
        if (LureMinInfectedMeters >= LureMaxInfectedMeters) { LureMinInfectedMeters = 12.0; LureMaxInfectedMeters = 60.0; }
        if (SmokeExclude == "") { SmokeExclude = "Contaminated"; }
        if (LureTypes == "") { LureTypes = "SardinesCan|TunaCan|BakedBeansCan|PeachesCan|SpaghettiCan|TacticalBaconCan|UnknownFoodCan|WaterBottle"; }
        if (LureNoisePath == "") { LureNoisePath = "CfgVehicles SurvivorBase NoiseActionDefault"; }
    }
}

// Per-group ledger: fire events (ring), cooldowns, caps and scan back-off.
class HCXTacticsGroup
{
    int GroupId;
    eAIGroup Group;
    int WindowStart;
    int SmokeLast;
    int SmokeUses;
    int LureLast;
    int LureUses;
    int FireNext;
    ref array<int> Fire = new array<int>;
}

// Per-actor stock backoff (bounded by HCXAITacticsPolicy.BACKOFF_MAX): a member
// without smoke or a noisy item never blocks a mate who carries one.
class HCXTacticsBackoff
{
    eAIBase Actor;
    int SmokeUntil;
    int LureUntil;
}

class HCXTacticsPending
{
    ItemBase Item;
    eAIBase Actor;
    bool Smoke;
    int Since;
    int Tries;
    int LandAt;
}

// What the acting member itself perceives right now (its own target list).
class HCXTacticsView
{
    int Infected;
    float Nearest;
    vector NearestAt;
    bool HumanSeen;
    bool Seen;
    float ThreatMeters;
    vector ThreatAt;

    void HCClear()
    {
        Infected = 0;
        Nearest = 100000.0;
        NearestAt = "0 0 0";
        HumanSeen = false;
        Seen = false;
        ThreatMeters = 100000.0;
        ThreatAt = "0 0 0";
    }
}

class HCXAITactics
{
    protected static bool s_Running;
    protected static ref HCXAITacticsConfig s_Config;
    protected static ref array<ref HCXTacticsGroup> s_Groups = new array<ref HCXTacticsGroup>;
    protected static ref array<ref HCXTacticsPending> s_Pending = new array<ref HCXTacticsPending>;
    protected static ref array<ref HCXTacticsBackoff> s_Backoff = new array<ref HCXTacticsBackoff>;
    protected static ref HCXTacticsScan s_Scan;
    protected static ref HCXTacticsView s_View = new HCXTacticsView;
    protected static ref HCWorkBudget s_Budget = new HCWorkBudget;
    protected static HCXTacticsGroup s_ScanGroup;
    protected static eAIBase s_ScanActor;
    protected static bool s_ScanSmoke;
    protected static vector s_ScanAim;
    protected static int s_ScanStartedMs;
    protected static int s_Cursor;
    protected static int s_Sweep;
    protected static int s_NextCheckMs;
    protected static string s_Refusal;
    protected static int s_SmokeThrown;
    protected static int s_SmokeActivated;
    protected static int s_LureThrown;
    protected static int s_LureNoises;
    protected static int s_Dropped;
    protected static int s_Lost;
    protected static int s_Refused;
    protected static int s_Throttled;
    protected static int s_Deferred;
    protected static int s_FireEvents;
    protected static int s_Logged;
    protected static float s_SummaryAfter;

    static bool Running() { return s_Running; }

    static HCXAITacticsConfig LoadConfig()
    {
        HCXAITacticsConfig config = new HCXAITacticsConfig();
        HCProfileDefaults.Ensure(HCXAITacticsPolicy.FILE, HCXAIDefaults.Shipped());
        string path = HCProfileDefaults.Resolve(HCXAITacticsPolicy.FILE, HCXAIDefaults.Shipped());
        string data = "";
        if (path != "") { data = HCProfileDefaults.ReadText(path); }
        string error;
        if (data == "" || !JsonFileLoader<HCXAITacticsConfig>.LoadData(data, config, error))
        {
            Print("[HCX Tactics] config unreadable (" + HCXAITacticsPolicy.FILE + "); using validated in-code defaults, runtime=PENDING");
            config = new HCXAITacticsConfig();
        }
        config.Normalise();
        return config;
    }

    // True when the operator opted out (Disabled in the config); the module
    // then stays off and says so on its single admission line.
    static bool OperatorOff(HCXAITacticsConfig config)
    {
        bool markerOff = FileExist("$profile:HollowCountry/acceptance/ai_tactics.disable");
        return !HCXAITacticsPolicy.Allowed(config.Disabled, markerOff);
    }

    // This actor's own backoff entry, created on first use; the oldest entry goes at the bound.
    protected static HCXTacticsBackoff Backoff(eAIBase actor)
    {
        for (int index = s_Backoff.Count() - 1; index >= 0; index--)
        {
            HCXTacticsBackoff known = s_Backoff.Get(index);
            if (!known || !known.Actor) { s_Backoff.RemoveOrdered(index); continue; }
            if (known.Actor == actor) { return known; }
        }
        if (HCXAITacticsPolicy.TrackedFull(s_Backoff.Count(), HCXAITacticsPolicy.BACKOFF_MAX)) { s_Backoff.RemoveOrdered(0); }
        HCXTacticsBackoff created = new HCXTacticsBackoff();
        created.Actor = actor;
        s_Backoff.Insert(created);
        return created;
    }

    static void Start(HCXAITacticsConfig config)
    {
        s_Config = config;
        s_Groups.Clear();
        s_Pending.Clear();
        s_Backoff.Clear();
        s_Scan = null;
        s_ScanGroup = null;
        s_ScanActor = null;
        s_Cursor = 0;
        s_Sweep = 0;
        s_NextCheckMs = 0;
        s_Refusal = "";
        s_Running = true;
        s_SummaryAfter = GetGame().GetTickTime() + 60;
    }

    static void Stop()
    {
        s_Running = false;
        s_Groups.Clear();
        s_Pending.Clear();
        s_Backoff.Clear();
        s_Scan = null;
        s_ScanGroup = null;
        s_ScanActor = null;
    }

    // Print once per change (the per-class HCRefuse pattern).
    protected static void HCRefuse(string reason)
    {
        s_Refused++;
        if (reason == s_Refusal) { return; }
        s_Refusal = reason;
        Print("[HCX Tactics] refused reason=" + reason + " runtime=PENDING");
    }

    protected static HCXTacticsGroup Track(eAIGroup group, int nowMs)
    {
        if (!group || !s_Config) { return null; }
        int id = group.GetID();
        for (int index = 0; index < s_Groups.Count(); index++)
        {
            HCXTacticsGroup known = s_Groups.Get(index);
            if (known && known.GroupId == id) { return known; }
        }
        if (HCXAITacticsPolicy.TrackedFull(s_Groups.Count(), s_Config.TrackedGroups)) { s_Groups.RemoveOrdered(0); }
        HCXTacticsGroup created = new HCXTacticsGroup();
        created.GroupId = id;
        created.Group = group;
        for (int slot = 0; slot < HCXAITacticsPolicy.FIRE_RING; slot++) { created.Fire.Insert(0); }
        s_Groups.Insert(created);
        return created;
    }

    protected static void NoteFire(eAIBase ai)
    {
        if (!HCXStance.Owns(ai)) { return; }
        int nowMs = GetGame().GetTime();
        HCXTacticsGroup rec = HCXAITactics.Track(ai.GetGroup(), nowMs);
        if (!rec) { return; }
        rec.Fire.Set(rec.FireNext, nowMs);
        rec.FireNext++;
        if (rec.FireNext >= HCXAITacticsPolicy.FIRE_RING) { rec.FireNext = 0; }
        s_FireEvents++;
    }

    // Effective fire: only a hit by a weapon counts.
    static void OnHit(eAIBase ai, EntityAI source)
    {
        if (!s_Running || !ai || !source) { return; }
        if (!Weapon_Base.Cast(source)) { return; }
        HCXAITactics.NoteFire(ai);
    }

    // Effective fire: a bullet impact close to this member.
    static void OnImpact(eAIBase ai, vector position)
    {
        if (!s_Running || !ai || !s_Config) { return; }
        if (vector.Distance(ai.GetPosition(), position) > s_Config.NearMissMeters) { return; }
        HCXAITactics.NoteFire(ai);
    }

    protected static int FireCount(HCXTacticsGroup rec, int nowMs)
    {
        int count = 0;
        int windowMs = s_Config.FireWindowSec * 1000;
        for (int slot = 0; slot < rec.Fire.Count(); slot++)
        {
            if (HCXAITacticsPolicy.Recent(nowMs, rec.Fire.Get(slot), windowMs)) { count++; }
        }
        return count;
    }

    protected static bool DownedMate(eAIGroup group, eAIBase actor)
    {
        if (!group.IsInCombat()) { return false; }
        int total = group.Count();
        for (int slot = 0; slot < total && slot < HCXAITacticsPolicy.MEMBER_SCAN_MAX; slot++)
        {
            PlayerBase mate = PlayerBase.Cast(group.GetMember(slot));
            if (mate && mate != actor && mate.IsAlive() && mate.IsUnconscious()) { return true; }
        }
        return false;
    }

    // Reads only this member's own target list; m_LOS gates every entry, and
    // eAITarget.GetPosition() is the last known position, not the live one.
    protected static void Perceive(eAIBase actor)
    {
        s_View.HCClear();
        array<ref eAITarget> targets = actor.GetTargets();
        if (!targets) { return; }
        vector here = actor.GetPosition();
        for (int slot = 0; slot < targets.Count() && slot < HCXAITacticsPolicy.TARGET_SCAN_MAX; slot++)
        {
            eAITarget target = targets.Get(slot);
            if (!target || !target.m_Info || !target.m_LOS) { continue; }
            vector at = target.GetPosition();
            float meters = vector.Distance(here, at);
            if (target.m_Info.IsZombie())
            {
                s_View.Infected++;
                if (meters < s_View.Nearest) { s_View.Nearest = meters; s_View.NearestAt = at; }
                continue;
            }
            if (target.m_Info.IsNoise() || target.m_Info.IsItem() || target.m_ThreatLevelActive <= 0) { continue; }
            s_View.HumanSeen = true;
            if (meters < s_View.ThreatMeters) { s_View.ThreatMeters = meters; s_View.ThreatAt = at; s_View.Seen = true; }
        }
    }

    protected static void StartScan(eAIBase actor, HCXTacticsGroup rec, bool smoke, vector aim, int nowMs)
    {
        s_Scan = new HCXTacticsScan();
        s_Scan.Mode = 2;
        if (smoke) { s_Scan.Mode = 1; }
        s_Scan.Exclude = s_Config.SmokeExclude;
        s_Scan.Types = "|" + s_Config.LureTypes + "|";
        s_Scan.AllowFull = s_Config.LureAllowFull;
        s_Scan.HCStart(actor, "");
        s_ScanActor = actor;
        s_ScanGroup = rec;
        s_ScanSmoke = smoke;
        s_ScanAim = aim;
        s_ScanStartedMs = nowMs;
    }

    protected static void EndScan()
    {
        s_Scan = null;
        s_ScanActor = null;
        s_ScanGroup = null;
    }

    protected static void Evaluate(eAIBase actor, int nowMs)
    {
        eAIGroup group = actor.GetGroup();
        HCXTacticsGroup rec = HCXAITactics.Track(group, nowMs);
        if (!rec) { return; }
        if (HCXAITacticsPolicy.WindowExpired(nowMs, rec.WindowStart, s_Config.CapWindowSec * 1000))
        {
            rec.WindowStart = nowMs;
            rec.SmokeUses = 0;
            rec.LureUses = 0;
        }
        if (s_Scan || s_Pending.Count() >= HCXAITacticsPolicy.MAX_PENDING) { s_Deferred++; return; }
        bool smokeOn = HCXAITacticsPolicy.Allowed(s_Config.Disabled, s_Config.SmokeDisabled);
        bool lureOn = HCXAITacticsPolicy.Allowed(s_Config.Disabled, s_Config.LureDisabled);
        string smokeGate = HCXAITacticsPolicy.Gate(nowMs, rec.SmokeLast, s_Config.SmokeCooldownSec * 1000, rec.SmokeUses, s_Config.SmokeGroupCap);
        string lureGate = HCXAITacticsPolicy.Gate(nowMs, rec.LureLast, s_Config.LureCooldownSec * 1000, rec.LureUses, s_Config.LureGroupCap);
        HCXTacticsBackoff own = HCXAITactics.Backoff(actor);
        if (smokeGate != "" || HCXAITacticsPolicy.BackedOff(nowMs, own.SmokeUntil)) { smokeOn = false; s_Throttled++; }
        if (lureGate != "" || HCXAITacticsPolicy.BackedOff(nowMs, own.LureUntil)) { lureOn = false; s_Throttled++; }
        if (!smokeOn && !lureOn) { return; }
        HCXAITactics.Perceive(actor);
        if (smokeOn)
        {
            bool downed = DownedMate(group, actor);
            string verdict = HCXAITacticsPolicy.SmokeDecision(FireCount(rec, nowMs), s_Config.SmokeFireEvents, downed, s_View.Seen, s_View.ThreatMeters, s_Config.SmokeMinThreatMeters, s_Config.SmokeMaxThreatMeters);
            if (verdict == "fire" || verdict == "downed")
            {
                HCXAITactics.StartScan(actor, rec, true, s_View.ThreatAt, nowMs);
                return;
            }
        }
        if (lureOn)
        {
            string lureVerdict = HCXAITacticsPolicy.LureDecision(s_View.Infected, s_Config.LureMinInfected, s_View.Nearest, s_Config.LureMinInfectedMeters, s_Config.LureMaxInfectedMeters, s_View.HumanSeen);
            if (lureVerdict == "") { HCXAITactics.StartScan(actor, rec, false, s_View.NearestAt, nowMs); }
        }
    }

    protected static void ExecuteSmoke(ItemBase item, int nowMs)
    {
        eAIBase actor = s_ScanActor;
        HCXTacticsGroup rec = s_ScanGroup;
        vector here = actor.GetPosition();
        float meters = vector.Distance(here, s_ScanAim);
        float reach = HCXAITacticsPolicy.ThrowMeters(meters, s_Config.SmokeThrowMeters, s_Config.SmokeThreatFractionPct);
        vector heading = s_ScanAim - here;
        heading[1] = 0;
        vector landing = here + heading.Normalized() * reach;
        float force = HCXAITacticsPolicy.ThrowForce(reach, s_Config.SmokeThrowMeters, s_Config.ThrowForceMin, s_Config.ThrowForceMax);
        string refusal = HCXAIThrowables.Throw(actor, item, landing, force, s_Config.ThrowLiftPct);
        bool dropped = false;
        if (refusal != "")
        {
            HCXAITactics.HCRefuse(refusal);
            dropped = HCXAIThrowables.Drop(actor, item);
        }
        string outcome = HCXAITacticsPolicy.ThrowOutcome(refusal, dropped);
        if (outcome == "failed")
        {
            HCXAITactics.HCRefuse("drop_refused");
            HCXAITactics.Backoff(actor).SmokeUntil = HCXAITacticsPolicy.BackoffUntil(nowMs, s_Config.SmokeCooldownSec * 1000);
            return;
        }
        if (outcome == "dropped") { s_Dropped++; }
        rec.SmokeLast = nowMs;
        rec.SmokeUses++;
        s_SmokeThrown++;
        HCXAITactics.Enqueue(item, actor, true, nowMs);
    }

    protected static void ExecuteLure(ItemBase item, int nowMs)
    {
        eAIBase actor = s_ScanActor;
        HCXTacticsGroup rec = s_ScanGroup;
        vector here = actor.GetPosition();
        vector toward = s_ScanAim - here;
        toward[1] = 0;
        toward = toward.Normalized();
        vector side = Vector(toward[2], 0, -toward[0]);
        int half = rec.GroupId / 2;
        if (half * 2 != rec.GroupId) { side = side * -1; }
        vector landing = here + side * s_Config.LureThrowMeters;
        float force = HCXAITacticsPolicy.ThrowForce(s_Config.LureThrowMeters, s_Config.LureThrowMeters, s_Config.ThrowForceMin, s_Config.ThrowForceMax);
        string refusal = HCXAIThrowables.Throw(actor, item, landing, force, s_Config.ThrowLiftPct);
        if (refusal != "")
        {
            HCXAITactics.HCRefuse(refusal);
            HCXAITactics.Backoff(actor).LureUntil = HCXAITacticsPolicy.BackoffUntil(nowMs, s_Config.LureCooldownSec * 1000);
            return;
        }
        rec.LureLast = nowMs;
        rec.LureUses++;
        s_LureThrown++;
        HCXAITactics.Enqueue(item, actor, false, nowMs);
    }

    protected static void Enqueue(ItemBase item, eAIBase actor, bool smoke, int nowMs)
    {
        HCXTacticsPending pending = new HCXTacticsPending();
        pending.Item = item;
        pending.Actor = actor;
        pending.Smoke = smoke;
        pending.Since = nowMs;
        pending.LandAt = nowMs + s_Config.LureLandDelayMs;
        s_Pending.Insert(pending);
    }

    // One bounded step of the single inventory scan. Found: the real carried item.
    protected static void StepScan(int nowMs)
    {
        if (!s_Scan) { return; }
        if (!s_ScanActor || !s_ScanActor.IsAlive() || nowMs - s_ScanStartedMs > HCXAITacticsPolicy.SCAN_TIMEOUT_MS)
        {
            HCXAITactics.EndScan();
            return;
        }
        ItemBase found = s_Scan.HCStep(s_Config.ScanLimit);
        if (found)
        {
            if (s_ScanSmoke) { HCXAITactics.ExecuteSmoke(found, nowMs); }
            else { HCXAITactics.ExecuteLure(found, nowMs); }
            HCXAITactics.EndScan();
            return;
        }
        if (!s_Scan.Complete) { return; }
        HCXTacticsBackoff own = HCXAITactics.Backoff(s_ScanActor);
        if (s_ScanSmoke)
        {
            own.SmokeUntil = HCXAITacticsPolicy.BackoffUntil(nowMs, s_Config.SmokeCooldownSec * 1000);
            HCXAITactics.HCRefuse("no_smoke_stock");
        }
        else
        {
            own.LureUntil = HCXAITacticsPolicy.BackoffUntil(nowMs, s_Config.LureCooldownSec * 1000);
            HCXAITactics.HCRefuse("no_noisy_item");
        }
        HCXAITactics.EndScan();
    }

    // Activates a landed smoke and emits the one lure noise. An item that never
    // left the inventory, or vanished, is counted lost and named, never retried forever.
    protected static void StepPending(int nowMs)
    {
        int index = 0;
        while (index < s_Pending.Count() && s_Budget.HCContinue())
        {
            HCXTacticsPending pending = s_Pending.Get(index);
            bool gone = !pending || !pending.Item || pending.Item.IsPendingDeletion();
            bool smoke = false;
            string step = "wait";
            bool landed = false;
            if (!gone)
            {
                smoke = pending.Smoke;
                bool pinned = true;
                int maxTries = 1;
                if (smoke)
                {
                    pinned = HCXAIThrowables.Pinned(pending.Item);
                    maxTries = s_Config.SmokeActivationTries;
                }
                step = HCXAITacticsPolicy.ActivateStep(HCXAIThrowables.Held(pending.Item), pinned, pending.Tries, maxTries, nowMs - pending.Since, s_Config.ActivateWaitSec * 1000);
                landed = nowMs >= pending.LandAt;
            }
            else if (pending) { smoke = pending.Smoke; }
            string action = HCXAITacticsPolicy.PendingAction(gone, smoke, step, landed);
            if (action == "remove_lost")
            {
                s_Lost++;
                if (!gone) { HCXAITactics.HCRefuse("throw_not_observed"); }
            }
            if (action == "remove_activated") { s_SmokeActivated++; }
            if (action == "activate_smoke")
            {
                pending.Tries++;
                HCXAIThrowables.ActivateSmoke(pending.Item);
            }
            if (action == "noise_remove" && HCXAIThrowables.Noise(pending.Item, s_Config.LureNoisePath, s_Config.LureNoiseMultPct)) { s_LureNoises++; }
            if (action.Contains("remove")) { s_Pending.RemoveOrdered(index); }
            else { index++; }
        }
    }

    // Visits a bounded number of AI per check, rotating, then one ledger sweep.
    protected static void PollActors(int nowMs)
    {
        array<eAIBase> all = eAIBase.eAI_GetAll();
        if (!all) { return; }
        int total = all.Count();
        if (total < 1) { return; }
        int evaluated = 0;
        for (int pass = 0; pass < total && evaluated < s_Config.TickActors; pass++)
        {
            if (s_Cursor >= total) { s_Cursor = 0; }
            if (!s_Budget.HCContinue()) { s_Deferred++; break; }
            eAIBase actor = all.Get(s_Cursor);
            s_Cursor++;
            if (!actor || !actor.IsAlive() || actor.IsUnconscious() || !HCXStance.Owns(actor)) { continue; }
            evaluated++;
            HCXAITactics.Evaluate(actor, nowMs);
        }
        if (s_Groups.Count() > 0)
        {
            if (s_Sweep >= s_Groups.Count()) { s_Sweep = 0; }
            HCXTacticsGroup sweep = s_Groups.Get(s_Sweep);
            if (!sweep || !sweep.Group) { s_Groups.RemoveOrdered(s_Sweep); }
            else { s_Sweep++; }
        }
    }

    static void Tick()
    {
        if (!s_Running || !s_Config) { return; }
        int nowMs = GetGame().GetTime();
        s_Budget.HCReset(s_Config.TickActors * 4 + HCXAITacticsPolicy.MAX_PENDING);
        HCXAITactics.StepPending(nowMs);
        HCXAITactics.StepScan(nowMs);
        if (nowMs >= s_NextCheckMs)
        {
            s_NextCheckMs = nowMs + s_Config.CheckEverySec * 1000;
            if (HCXAITacticsPolicy.Allowed(s_Config.Disabled, false)) { HCXAITactics.PollActors(nowMs); }
        }
        s_Budget.HCDeferred("HCXAITactics", s_Deferred);
        float tickNow = GetGame().GetTickTime();
        int signature = s_SmokeThrown + s_SmokeActivated + s_LureThrown + s_LureNoises + s_Lost + s_Refused + s_Dropped;
        if (tickNow >= s_SummaryAfter && signature != s_Logged)
        {
            s_SummaryAfter = tickNow + 60;
            s_Logged = signature;
            string summary = "[HCX Tactics] groups=" + s_Groups.Count().ToString() + "/" + s_Config.TrackedGroups.ToString() + " fire_events=" + s_FireEvents.ToString();
            summary = summary + " smoke_thrown=" + s_SmokeThrown.ToString() + " smoke_activated=" + s_SmokeActivated.ToString() + " smoke_dropped=" + s_Dropped.ToString();
            summary = summary + " lure_thrown=" + s_LureThrown.ToString() + " lure_noises=" + s_LureNoises.ToString() + " lost=" + s_Lost.ToString();
            summary = summary + " refused=" + s_Refused.ToString() + " throttled=" + s_Throttled.ToString() + " deferred=" + s_Deferred.ToString() + " pending=" + s_Pending.Count().ToString();
            Print("" + summary);
        }
    }
}

class HCXAITacticsModule : HCModule
{
    protected ref HCOperationalStatus m_Operational = new HCOperationalStatus;
    protected string m_Refusal;

    override string GetName() { return "AITactics"; }

    // started = the tactics service is running, never hard-coded.
    override HCOperationalStatus HCGetOperationalStatus()
    {
        HCModuleReadiness.HCDerive(m_Operational, HCXAITactics.Running(), m_Refusal, "", "ai_tactics_service_running");
        return m_Operational;
    }

    override bool IsEnabled(HCSettings settings) { return settings && settings.EnableEncounters; }

    override void OnStart(HCSettings settings)
    {
        if (!GetGame().IsServer() || !IsEnabled(settings)) { return; }
        if (HCXAITactics.Running())
        {
            Print("[HCX Tactics] start ignored: already running");
            return;
        }
        HCXAITacticsConfig config = HCXAITactics.LoadConfig();
        bool off = HCXAITactics.OperatorOff(config);
        Print(HCV2Admission.Line("AITactics", !off, "S2-TACTICS", false));
        if (off)
        {
            Print("[HCX Tactics] off: operator opt-out (Disabled in expansion-ai-tactics.json or acceptance/ai_tactics.disable); runtime=PENDING");
            return;
        }
        HCXAITactics.Start(config);
        string started = "[HCX Tactics] started smoke=" + HCV2Admission.OnOff(!config.SmokeDisabled) + " lure=" + HCV2Admission.OnOff(!config.LureDisabled);
        started = started + " cooldown smoke=" + config.SmokeCooldownSec.ToString() + "s lure=" + config.LureCooldownSec.ToString() + "s";
        started = started + " cap/group=" + config.SmokeGroupCap.ToString() + "/" + config.LureGroupCap.ToString() + " per " + config.CapWindowSec.ToString() + "s;";
        started = started + " flare_lure_unverified (no native flare noise path found); capability_unverified: throw force units, infected noise reaction, smoke activation;";
        started = started + " opt-out Disabled/SmokeDisabled/LureDisabled in expansion-ai-tactics.json or the ai_tactics.disable acceptance marker; runtime=PENDING";
        Print("" + started);
    }

    override void OnTick(float deltaTime) { HCXAITactics.Tick(); }
    override void OnStop() { HCXAITactics.Stop(); }
}

modded class eAIBase
{
    override void EEHitBy(TotalDamageResult damageResult, int damageType, EntityAI source, int component, string dmgZone, string ammo, vector modelPos, float speedCoef)
    {
        super.EEHitBy(damageResult, damageType, source, component, dmgZone, ammo, modelPos, speedCoef);
        if (GetGame() && GetGame().IsServer()) { HCXAITactics.OnHit(this, source); }
    }

    override void eAI_OnNoiseEvent(EntityAI source, vector position, float lifetime, eAINoiseParams params, float strengthMultiplier)
    {
        super.eAI_OnNoiseEvent(source, position, lifetime, params, strengthMultiplier);
        if (params && source && params.m_Type == eAINoiseType.BULLETIMPACT) { HCXAITactics.OnImpact(this, position); }
    }
}

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        HCXAITacticsModule tacticsModule = new HCXAITacticsModule();
        Register(tacticsModule);
    }
}
