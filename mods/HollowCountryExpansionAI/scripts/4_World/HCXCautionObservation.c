// Raised-weapon caution (owner-approved 30/60/80 m, ranges from HCAILimits).
// Wires HCStancePolicy.Evaluate into the observation path. Called only from the
// provider CalculateThreat hook AFTER native LOS and a fresh HCXStance.Visible ray
// established that this actor sees the player: no omniscient AI, no player scan.
// WARN = turn to face the player (+ a stop gesture for non-hostile actors). It
// never fires, never changes threat and never lowers hostility: any escalation
// stays with Expansion's own threat logic. Per actor-group/player pair cooldown,
// bounded pair table, shared HCXEmoteObservation.Work() per-second budget.
// Installed Expansion ai_scripts.pbo eAIBase.c: LookAtPosition:9937 (stores a look
// target only), Expansion_SetEmote:10860/Expansion_PlayEmote:10867 via the existing
// HCXNativeSignalProvider.Emote. Native 3_Game/Global/Game.c:1535 GetTime.
// Gunfire signal: eAIBase.HCXLastGunfire, stamped in the eAI_OnNoiseEvent hook
// (bridge) for SHOT noise the actor could actually hear.
class HCXCautionObservation
{
    static const int COOLDOWN_MS = 45000;
    static const int GUNFIRE_WINDOW_MS = 30000;
    static const int MAX_PAIRS = 64;
    protected static ref map<string, int> s_Next = new map<string, int>();
    protected static bool s_Logged;

    static void Reset()
    {
        s_Next.Clear();
        s_Logged = false;
    }
    // Pure: gunfire the actor heard within the window. Unset (-1) or a clock that
    // moved backwards is never "recent".
    static bool RecentGunfire(int lastMs, int nowMs)
    {
        if (lastMs < 0 || nowMs < lastMs) { return false; }
        return nowMs - lastMs <= GUNFIRE_WINDOW_MS;
    }
    // Admit one warning for this pair. Never evicts an unexpired row to admit
    // another pair: a full table of live cooldowns refuses instead.
    protected static bool Admit(string key, int nowMs)
    {
        int next;
        if (s_Next.Find(key, next))
        {
            if (!HCStancePolicy.WarningDue(nowMs, next)) { return false; }
            return true;
        }
        if (s_Next.Count() < MAX_PAIRS) { return true; }
        int index = s_Next.Count() - 1;
        while (index >= 0)
        {
            if (nowMs >= s_Next.GetElement(index)) { s_Next.RemoveElement(index); }
            index--;
        }
        return s_Next.Count() < MAX_PAIRS;
    }
    // Returns true when a warning was issued. distance/raised/relation are the
    // caller's already-computed observed facts.
    static bool Observe(eAIBase actor, PlayerBase player, float distance, bool raised, int relation)
    {
        if (!GetGame() || !GetGame().IsServer() || !actor || !player || !player.GetIdentity()) { return false; }
        int nowMs = GetGame().GetTime();
        if (nowMs < 0) { return false; }
        bool gunfire = HCXCautionObservation.RecentGunfire(actor.HCXLastGunfire, nowMs);
        if (HCStancePolicy.Evaluate(raised, distance, gunfire, relation) != HCStancePolicy.WARN) { return false; }
        if (!HCXEmoteObservation.ControlReady()) { return false; }
        eAIGroup actorGroup = HCXExpansionBridge.HCDayZPlayerImplementGetGroup(actor);
        if (!actorGroup || actorGroup == HCXExpansionBridge.HCDayZPlayerImplementGetGroup(player)) { return false; }
        string key = HCXExpansionBridge.HCGroupGetName(actorGroup) + "|" + player.GetIdentity().GetId();
        if (!HCXCautionObservation.Admit(key, nowMs)) { return false; }
        // Budget refusal leaves the cooldown unspent so the next observation retries.
        if (!HCXEmoteObservation.Work()) { return false; }
        s_Next.Set(key, nowMs + COOLDOWN_MS);
        HCXExpansionBridge.HCBaseLookAtPosition(actor, player.GetPosition() + Vector(0, 1.2, 0));
        bool gesture = false;
        // Hostile factions are already engaging: do not lower their weapon for a gesture.
        if (relation >= 0) { gesture = HCXEmoteObservation.CautionGesture(actor); }
        HCModuleReadiness.HCUse("v2-expansion-living-world", "caution_warn");
        if (!s_Logged)
        {
            s_Logged = true;
            Print("[HollowCountry] Caution warn first: relation=" + relation.ToString() + " distance_m=" + Math.Round(distance).ToString() + " gunfire=" + gunfire.ToString() + " gesture=" + gesture.ToString() + " fire=none runtime=PENDING");
        }
        return true;
    }
}
