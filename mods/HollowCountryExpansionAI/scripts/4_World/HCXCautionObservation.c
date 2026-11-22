// Raised-weapon caution (owner-approved 30/60/80 m, ranges from HCAILimits): the
// step BEFORE raised-weapon hostility. Called only from the provider
// CalculateThreat hook AFTER native LOS and a fresh HCXStance.Visible ray
// established that this actor sees the player: no omniscient AI, no player scan.
//
// Band table (non-hostile relation, player weapon raised; anything else is the
// unchanged stance logic):
//   d <= 40 m                      hostile at once (unchanged)
//   40 m < d <= 80 m               grace of AILimits.CautionGraceSeconds: actor stays
//                                  non-hostile, faces the player, shouts through the
//                                  shared HCXWarnPlayer admission, holds fire
//                                  (HCXWarningBlocked); then hostile if still raised
//   d > 80 m                       de-escalated (unchanged)
// The grace band is the same 80 m line where raised-weapon hostility applies; the
// caution ranges (CautionRangeM / CautionGunfireRangeM via HCStancePolicy.Evaluate)
// no longer bound it and are only reported in the first-warn log line. Hostile-
// relation actors (and so CautionHostileRangeM) never get a grace.
// The grace never fires and no stop gesture is made at a raised weapon: the actor
// keeps its own weapon up. Escalation stays with Expansion and the stance logic.
// Per actor-group/player pair cooldown, bounded pair table, shared
// HCXEmoteObservation.Work() per-second budget; any refusal leaves today's
// (hostile) behaviour, never a softer one.
// Installed Expansion ai_scripts.pbo eAIBase.c: LookAtPosition:9937 (stores a look
// target only) via HCXExpansionBridge.HCBaseLookAtPosition. Native 3_Game/Global/
// Game.c:1535 GetTime. Gunfire signal: eAIBase.HCXLastGunfire, stamped in the
// eAI_OnNoiseEvent hook (bridge) for SHOT noise the actor could actually hear.
class HCXCautionRow
{
    int GraceEnd;
    int NextAt;
}
class HCXCautionObservation
{
    static const int COOLDOWN_MS = 45000;
    static const int GUNFIRE_WINDOW_MS = 30000;
    static const int MAX_PAIRS = 64;
    static const int HOSTILE_M = 40;
    static const int MAX_M = 80;
    protected static ref map<string, ref HCXCautionRow> s_Rows = new map<string, ref HCXCautionRow>();
    protected static bool s_Logged;

    static void Reset()
    {
        s_Rows.Clear();
        s_Logged = false;
    }
    // Pure: gunfire the actor heard within the window. Unset (-1) or a clock that
    // moved backwards is never "recent".
    static bool RecentGunfire(int lastMs, int nowMs)
    {
        if (lastMs < 0 || nowMs < lastMs) { return false; }
        return nowMs - lastMs <= GUNFIRE_WINDOW_MS;
    }
    // Pure: is this contact in the grace band (see table above)?
    static bool InBand(float distance, bool raised, int relation)
    {
        if (!raised || relation < 0 || distance != distance || distance <= HOSTILE_M || distance > MAX_M) { return false; }
        return true;
    }
    // Free a slot only from expired rows; never evict a live grace or cooldown.
    protected static bool HasRoom(int nowMs)
    {
        if (s_Rows.Count() < MAX_PAIRS) { return true; }
        int index = s_Rows.Count() - 1;
        while (index >= 0)
        {
            HCXCautionRow expired = s_Rows.GetElement(index);
            if (!expired || (nowMs >= expired.NextAt && nowMs >= expired.GraceEnd)) { s_Rows.RemoveElement(index); }
            index--;
        }
        return s_Rows.Count() < MAX_PAIRS;
    }
    // Returns the grace end (server ms, > 0) while a grace holds this contact
    // non-hostile, else 0. A grace starts once per pair per cooldown; a raised
    // weapon after its end (or inside the cooldown) returns 0 and escalates.
    static int Observe(eAIBase actor, PlayerBase player, float distance, bool raised, int relation, bool alreadyHostile)
    {
        if (alreadyHostile || !raised || relation < 0 || !GetGame() || !GetGame().IsServer() || !actor || !player || !player.GetIdentity()) { return 0; }
        int nowMs = GetGame().GetTime();
        if (nowMs < 0) { return 0; }
        if (!HCXCautionObservation.InBand(distance, raised, relation)) { return 0; }
        if (!HCXEmoteObservation.ControlReady()) { return 0; }
        eAIGroup actorGroup = HCXExpansionBridge.HCDayZPlayerImplementGetGroup(actor);
        if (!actorGroup || actorGroup == HCXExpansionBridge.HCDayZPlayerImplementGetGroup(player)) { return 0; }
        string key = HCXExpansionBridge.HCGroupGetName(actorGroup) + "|" + player.GetIdentity().GetId();
        int graceMs = HCAILimits.CAUTION_GRACE * 1000;
        HCXCautionRow row;
        if (s_Rows.Find(key, row) && row)
        {
            // Running grace (lowering and re-raising inside it resumes, never restarts it).
            if (nowMs < row.GraceEnd && row.GraceEnd - nowMs <= graceMs) { return row.GraceEnd; }
            if (nowMs < row.NextAt) { return 0; }
        }
        else if (!HCXCautionObservation.HasRoom(nowMs)) { return 0; }
        // Budget refusal leaves the pair unspent and today's hostile behaviour.
        if (!HCXEmoteObservation.Work()) { return 0; }
        if (!row)
        {
            row = new HCXCautionRow();
            s_Rows.Set(key, row);
        }
        row.GraceEnd = nowMs + graceMs;
        row.NextAt = nowMs + COOLDOWN_MS;
        HCXExpansionBridge.HCBaseLookAtPosition(actor, player.GetPosition() + Vector(0, 1.2, 0));
        HCModuleReadiness.HCUse("v2-expansion-living-world", "caution_warn");
        if (!s_Logged)
        {
            s_Logged = true;
            bool gunfire = HCXCautionObservation.RecentGunfire(actor.HCXLastGunfire, nowMs);
            bool inRange = HCStancePolicy.Evaluate(raised, distance, gunfire, relation) == HCStancePolicy.WARN;
            Print("[HollowCountry] Caution warn first: relation=" + relation.ToString() + " distance_m=" + Math.Round(distance).ToString() + " gunfire=" + gunfire.ToString() + " in_caution_range=" + inRange.ToString() + " grace_s=" + HCAILimits.CAUTION_GRACE.ToString() + " fire=none runtime=PENDING");
        }
        return row.GraceEnd;
    }
}
