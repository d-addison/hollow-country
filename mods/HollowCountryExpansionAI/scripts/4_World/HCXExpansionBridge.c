// Single Expansion AI dependency boundary. Original HC code only: installed
// ai_scripts.pbo signatures/registry were inspected, never copied.
// Native cache: Object.IsAlive/IsPendingDeletion, Game.GetTime; provider API:
// eAIFaction.GetType/Create, eAIRegisterFaction.s_FactionIDs, eAIGroup,
// eAIBase, eAITarget/Information, eAIFormation and eAIDynamicPatrol(T).
// Refusal logging uses one global window: constant memory, <=1 line/minute.
// Native lifecycle observations (including group lookup for death accounting)
// accept corpses. Gameplay operations require live entities. No entity names,
// identities or operator-supplied strings enter refusal logs.
class HCXExpansionBridge
{
    protected static int s_NextRefusalMs;
    protected static bool s_Refused;

    static void HCRefuse(string call, string reason)
    {
        int nowMs;
        if (GetGame()) { nowMs = GetGame().GetTime(); }
        if (s_Refused && nowMs < s_NextRefusalMs) { return; }
        s_Refused = true;
        s_NextRefusalMs = nowMs + 60000;
        Print("[HCX Bridge] refused " + call + " reason=" + reason);
    }

    // H8 lifecycle. HCServer.Start (modded below) enters NOT_READY and bumps the epoch;
    // the first call after the provider answers moves to READY; HCServer.Stop flips to
    // SHUTTING_DOWN before any module OnStop. Mutating calls and handle reads need READY.
    // Cleanup (group delete, patrol stop/despawn, hold retire/prune) is never gated. Only the
    // HCHold*Final persistence reads are ungated, so a stopping patrol still reads its real
    // group (a defaulted count would persist a false "cleared" site); every other read needs READY.
    // The HCHold*Cleanup route undo resolves the same way, so a cancelled raid always restores.
    // Refusals are counted here, not printed through HCRefuse (one line per minute for all).
    static const int HC_STATE_NOT_READY = 0;
    static const int HC_STATE_READY = 1;
    static const int HC_STATE_SHUTTING_DOWN = 2;
    static const int HC_REASON_CAP = 16;
    static const int HC_SUMMARY_MS = 300000;
    protected static int s_HCState;
    protected static int s_HCEpoch;
    protected static int s_HCReadyCheckMs = -1;
    // Bumped when HC deletes a group, so every hold re-checks the provider's list at once.
    protected static int s_HCListStamp;
    protected static string s_HCMissingLogged;
    protected static int s_HCRefusedNotReady;
    protected static int s_HCRefusedShuttingDown;
    protected static int s_HCRefusedGone;
    protected static int s_HCHandlesLive;
    protected static int s_HCNextSummaryMs;
    protected static ref map<string, int> s_HCByCall;

    static int HCState() { return s_HCState; }
    static int HCEpoch() { return s_HCEpoch; }
    static int HCListStamp() { return s_HCListStamp; }

    static string HCStateName()
    {
        if (s_HCState == HC_STATE_READY) { return "ready"; }
        if (s_HCState == HC_STATE_SHUTTING_DOWN) { return "shutting_down"; }
        return "not_ready";
    }

    // Provider facts, quiet (no HCRefuse). "" when READY could be reached; otherwise the first
    // missing condition: expansion_ai_settings, expansion_patrol_settings or hc_faction.
    static string HCMissingCondition()
    {
        if (!GetExpansionSettings()) { return "expansion_ai_settings"; }
        ExpansionAISettings aiSettings = GetExpansionSettings().GetAI();
        if (!aiSettings || !aiSettings.IsLoaded()) { return "expansion_ai_settings"; }
        ExpansionAIPatrolSettings patrolSettings = GetExpansionSettings().GetAIPatrol(false);
        if (!patrolSettings || !patrolSettings.IsLoaded()) { return "expansion_patrol_settings"; }
        typename factionKind = eAIFaction.GetType("HCVolunteers");
        if (!factionKind || !eAIRegisterFaction.s_FactionIDs) { return "hc_faction"; }
        if (!eAIRegisterFaction.s_FactionIDs.Contains(factionKind)) { return "hc_faction"; }
        return "";
    }

    protected static bool HCProviderUp()
    {
        return HCMissingCondition() == "";
    }

    // The bridge itself is up: HCServer.Start ran (epoch > 0) and the server is not stopping. Modules
    // may report ready from here; every provider call stays gated by HCGate until READY.
    static bool HCBridgeUp()
    {
        if (!GetGame() || !GetGame().IsServer()) { return true; }
        return s_HCEpoch > 0 && s_HCState != HC_STATE_SHUTTING_DOWN;
    }

    // Logs the missing READY condition once per distinct condition and epoch; a bounded poll
    // (the adapter calls it once a second while not READY) so nothing waits on a first call.
    static void HCNoteMissing()
    {
        if (!GetGame() || !GetGame().IsServer() || s_HCEpoch <= 0 || s_HCState != HC_STATE_NOT_READY) { return; }
        if (HCReady()) { return; }
        string missing = HCMissingCondition();
        if (missing == "" || missing == s_HCMissingLogged) { return; }
        s_HCMissingLogged = missing;
        Print("[HC XAI Bridge] READY condition missing=" + missing + " epoch=" + s_HCEpoch.ToString() + "; provider calls refuse with reason=NOT_READY and are retried, no give-up");
    }

    static string HCMissingLogged() { return s_HCMissingLogged; }

    // NOT_READY becomes READY lazily, at most once per millisecond tick (once per frame).
    static bool HCReady()
    {
        if (!GetGame() || !GetGame().IsServer()) { return true; }
        if (s_HCState == HC_STATE_READY) { return true; }
        if (s_HCState != HC_STATE_NOT_READY || s_HCEpoch <= 0) { return false; }
        int nowMs = GetGame().GetTime();
        if (nowMs == s_HCReadyCheckMs) { return false; }
        s_HCReadyCheckMs = nowMs;
        if (!HCProviderUp()) { return false; }
        s_HCState = HC_STATE_READY;
        Print("[HC XAI Bridge] lifecycle state=ready epoch=" + s_HCEpoch.ToString());
        return true;
    }

    // True while handles may resolve. No lazy transition, no counting.
    static bool HCLive()
    {
        if (!GetGame() || !GetGame().IsServer()) { return true; }
        return s_HCState == HC_STATE_READY;
    }

    protected static void HCCountCall(string call)
    {
        if (!s_HCByCall) { s_HCByCall = new map<string, int>; }
        string key = call;
        int seen;
        if (!s_HCByCall.Find(key, seen) && s_HCByCall.Count() >= HC_REASON_CAP) { key = "OTHER"; }
        seen = 0;
        s_HCByCall.Find(key, seen);
        s_HCByCall.Set(key, seen + 1);
    }

    // READY, or a counted refusal. The caller returns its documented default.
    static bool HCGate(string call)
    {
        if (!GetGame() || !GetGame().IsServer()) { return true; }
        if (s_HCState == HC_STATE_READY) { return true; }
        if (s_HCState == HC_STATE_NOT_READY && HCReady()) { return true; }
        if (s_HCState == HC_STATE_SHUTTING_DOWN) { s_HCRefusedShuttingDown++; }
        else { s_HCRefusedNotReady++; }
        HCCountCall(call);
        return false;
    }

    static void HCCountGone(string call)
    {
        s_HCRefusedGone++;
        HCCountCall(call + ":GROUP_GONE");
    }

    static void HCCountHoldCap()
    {
        HCCountCall("HOLD_CAP");
    }

    static void HCCountHoldAbsoluteCap()
    {
        HCCountCall("HOLD_ABSOLUTE_CAP");
    }

    static void HCHandleMade() { s_HCHandlesLive++; }
    static void HCHandleDropped() { if (s_HCHandlesLive > 0) { s_HCHandlesLive--; } }

    // Called first in HCServer.Start. Retired holds are NOT cleared: their release timing is
    // the one #334 proved; the epoch alone makes every earlier handle unresolvable.
    static void HCLifecycleStart()
    {
        s_HCEpoch++;
        s_HCState = HC_STATE_NOT_READY;
        s_HCReadyCheckMs = -1;
        s_HCMissingLogged = "";
        s_HCRefusedNotReady = 0;
        s_HCRefusedShuttingDown = 0;
        s_HCRefusedGone = 0;
        if (s_HCByCall) { s_HCByCall.Clear(); }
        HCXAITactics.HCBridgeReset();
        s_HCNextSummaryMs = 0;
        if (GetGame()) { s_HCNextSummaryMs = GetGame().GetTime() + HC_SUMMARY_MS; }
    }

    // Called first in HCServer.Stop, before the first module OnStop. Terminal until the next Start.
    static bool HCLifecycleStop()
    {
        if (s_HCState == HC_STATE_SHUTTING_DOWN) { return false; }
        s_HCState = HC_STATE_SHUTTING_DOWN;
        HCXAITactics.HCBridgeReset();
        Print("[HC XAI Bridge] lifecycle state=shutting_down epoch=" + s_HCEpoch.ToString() + " holds=" + HCXAIGroupHolds.Count().ToString() + " handles=" + s_HCHandlesLive.ToString());
        return true;
    }

    static void HCLifecycleSummary()
    {
        string missingNote = "";
        if (s_HCState == HC_STATE_NOT_READY && s_HCEpoch > 0) { missingNote = " missing=" + HCMissingCondition(); }
        Print("[HC XAI Bridge] state=" + HCStateName() + missingNote + " epoch=" + s_HCEpoch.ToString() + " refused not_ready=" + s_HCRefusedNotReady.ToString() + " shutting_down=" + s_HCRefusedShuttingDown.ToString() + " group_gone=" + s_HCRefusedGone.ToString() + " handles=" + s_HCHandlesLive.ToString() + "/" + HCXAIGroupHolds.Count().ToString());
    }

    // Final summary after the module stops, with the per-call breakdown when anything was refused.
    static void HCLifecycleFinal()
    {
        HCLifecycleSummary();
        if (!s_HCByCall || s_HCByCall.Count() == 0) { return; }
        string line = "[HC XAI Bridge] refused_by_call";
        for (int at = 0; at < s_HCByCall.Count(); at++)
        {
            line += " " + s_HCByCall.GetKey(at) + "=" + s_HCByCall.GetElement(at).ToString();
        }
        Print("" + line);
    }

    // Every five minutes, from HCServer.Tick (bounded: one compare per tick).
    static void HCLifecycleTick()
    {
        if (!GetGame() || s_HCEpoch <= 0 || s_HCState == HC_STATE_SHUTTING_DOWN) { return; }
        int nowMs = GetGame().GetTime();
        if (nowMs < s_HCNextSummaryMs) { return; }
        s_HCNextSummaryMs = nowMs + HC_SUMMARY_MS;
        HCLifecycleSummary();
    }

    // Engine-callback gate: READY runs the HC part, anything else is super-only (counted).
    static bool HCCallbackGate(string call)
    {
        return HCGate(call);
    }

    // Native EnSystem UTC out-parameter APIs; sample date again across midnight.
    // CF owns epoch conversion; its bridge validates ranges before provider calls.
    // Returns -1 on refusal, including dates outside 1970-2037. Callers must
    // reject negative results before updating lockouts or persisting an epoch.
    static int HCGetTimestamp()
    {
        int year, month, day, hour, minute, second;
        int endYear, endMonth, endDay;
        GetYearMonthDayUTC(year, month, day);
        GetHourMinuteSecondUTC(hour, minute, second);
        GetYearMonthDayUTC(endYear, endMonth, endDay);
        if (year != endYear || month != endMonth || day != endDay)
        {
            // One bounded re-sample handles an ordinary UTC midnight crossing.
            GetYearMonthDayUTC(year, month, day);
            GetHourMinuteSecondUTC(hour, minute, second);
            GetYearMonthDayUTC(endYear, endMonth, endDay);
            if (year != endYear || month != endMonth || day != endDay)
            {
                HCRefuse("GetTimestamp", "UTC_DATE_CHANGED");
                return -1;
            }
        }
        return HCXCFBridge.HCTimestamp(year, month, day, hour, minute, second);
    }

    static bool HCEntity(EntityAI entity, string call, bool requireAlive = true)
    {
        if (!entity) { HCRefuse(call, "ENTITY_NULL"); return false; }
        if (requireAlive && (!entity.IsAlive() || entity.IsPendingDeletion())) { HCRefuse(call, "ENTITY_NOT_LIVE"); return false; }
        return true;
    }

    static bool HCCheckFactionName(string name, string call)
    {
        if (name == "") { HCRefuse(call, "FACTION_EMPTY"); return false; }
        typename kind = eAIFaction.GetType(name);
        if (!kind || !eAIRegisterFaction.s_FactionIDs || !eAIRegisterFaction.s_FactionIDs.Contains(kind)) { HCRefuse(call, "FACTION_UNKNOWN"); return false; }
        return true;
    }

    static bool HCFactionRegistered(string name)
    {
        return HCCheckFactionName(name, "FactionRegistered");
    }

    static bool HCFactionValid(eAIFaction faction, string call)
    {
        if (!faction) { HCRefuse(call, "FACTION_NULL"); return false; }
        if (!eAIRegisterFaction.s_FactionIDs || !eAIRegisterFaction.s_FactionIDs.Contains(faction.Type())) { HCRefuse(call, "FACTION_UNKNOWN"); return false; }
        return true;
    }

    static bool HCConfig(ExpansionAIDynamicSpawnBase config, string call)
    {
        if (!config) { HCRefuse(call, "CONFIG_NULL"); return false; }
        if (!config.Waypoints || config.Waypoints.Count() == 0) { HCRefuse(call, "CONFIG_EMPTY"); return false; }
        if (!HCCheckFactionName(config.Faction, call)) { return false; }
        return true;
    }

    static ExpansionAISettings HCSettings()
    {
        if (!GetExpansionSettings()) { HCRefuse("Settings", "SETTINGS_NULL"); return null; }
        ExpansionAISettings settings = GetExpansionSettings().GetAI();
        if (!settings || !settings.IsLoaded()) { HCRefuse("Settings", "SETTINGS_NOT_LOADED"); return null; }
        return settings;
    }

    static ExpansionAIPatrolSettings HCPatrolSettings()
    {
        if (!GetExpansionSettings()) { HCRefuse("PatrolSettings", "SETTINGS_NULL"); return null; }
        ExpansionAIPatrolSettings settings = GetExpansionSettings().GetAIPatrol(false);
        if (!settings || !settings.IsLoaded()) { HCRefuse("PatrolSettings", "SETTINGS_NOT_LOADED"); return null; }
        return settings;
    }

    static vector HCPlacementPosition(vector position, bool forceOnSurface = false)
    {
        return ExpansionAISpawnBase.GetPlacementPosition(position, forceOnSurface);
    }

    static void HCFormationSetLooseness(eAIFormation formation, float looseness)
    {
        if (!formation) { HCRefuse("FormationSetLooseness", "FORMATION_NULL"); return; }
        formation.SetLooseness(looseness);
    }

    static HCXAISitePatrol HCCreatePatrol(ExpansionAIDynamicSpawnBase config, vector position)
    {
        if (!HCGate("CreatePatrol")) { return null; }
        if (!HCConfig(config, "CreatePatrol")) { return null; }
        return eAIDynamicPatrolT<HCXAISitePatrol>.CreateEx(config, position);
    }


    static eAIGroup HCDayZPlayerImplementGetGroup(DayZPlayerImplement value)
    {
        if (!HCEntity(value, "HCDayZPlayerImplementGetGroup", false)) { return null; }
        return value.GetGroup();
    }

    static eAIPlayerTargetInformation HCDayZPlayerImplementGetTargetInformation(DayZPlayerImplement value)
    {
        if (!HCEntity(value, "HCDayZPlayerImplementGetTargetInformation", false)) { return null; }
        return value.GetTargetInformation();
    }

    static void HCDayZPlayerImplementSetGroup(DayZPlayerImplement value, eAIGroup group, bool autoDeleteFormerGroupIfEmpty = true, int groupMemberIndex = -1)
    {
        if (!HCGate("SetGroup")) { return; }
        if (!HCEntity(value, "HCDayZPlayerImplementSetGroup", true)) { return; }
        if (!group) { HCRefuse("HCDayZPlayerImplementSetGroup", "GROUP_NULL"); return; }
        value.SetGroup(group, autoDeleteFormerGroupIfEmpty, groupMemberIndex);
    }

    // Expansion core adds these reads to the player classes (names in HCXAIFormations.c and HCXDefence.c).
    // A refusal returns 0 / zero, which the callers treat as "standing" / "use the body direction".
    static float HCDayZPlayerImplementGetMovementSpeed(DayZPlayerImplement value)
    {
        if (!HCEntity(value, "HCDayZPlayerImplementGetMovementSpeed", false)) { return 0.0; }
        return value.Expansion_GetMovementSpeed();
    }

    static vector HCPlayerBaseGetAimDirection(PlayerBase value)
    {
        if (!HCEntity(value, "HCPlayerBaseGetAimDirection", false)) { return vector.Zero; }
        return value.Expansion_GetAimDirection();
    }

    // A second Delete would queue a second DeletePatrol, whose Find returns -1.
    static void HCSitePatrolDelete(HCXAISitePatrol value)
    {
        if (!value) { HCRefuse("HCSitePatrolDelete", "RECEIVER_NULL"); return; }
        if (value.IsBeingDestroyed()) { HCRefuse("HCSitePatrolDelete", "ALREADY_DELETING"); return; }
        value.HCEndPatrol();
        // Despawned may synchronously finish a transient and re-enter Delete.
        if (value.IsBeingDestroyed()) { return; }
        value.HCReleaseHold();
        value.Delete();
    }

    static bool HCSitePatrolBeingDestroyed(HCXAISitePatrol value)
    {
        if (!value) { HCRefuse("HCSitePatrolBeingDestroyed", "RECEIVER_NULL"); return true; }
        return value.IsBeingDestroyed();
    }

    static void HCSitePatrolDespawn(HCXAISitePatrol value, bool deferDespawnUntilLoosingAggro = false)
    {
        if (!value) { HCRefuse("HCSitePatrolDespawn", "RECEIVER_NULL"); return; }
        value.Despawn(deferDespawnUntilLoosingAggro);
    }

    static void HCSitePatrolSpawn(HCXAISitePatrol value)
    {
        if (!value) { HCRefuse("HCSitePatrolSpawn", "RECEIVER_NULL"); return; }
        if (!HCGate("PatrolSpawn")) { return; }
        if (!HCConfig(value.m_Config, "HCSitePatrolSpawn")) { return; }
        value.Spawn();
    }

    static void HCSitePatrolSpawnDeferred(HCXAISitePatrol value, int index)
    {
        if (!value) { HCRefuse("HCSitePatrolSpawnDeferred", "RECEIVER_NULL"); return; }
        if (index < 0 || value.IsBeingDestroyed()) { HCRefuse("HCSitePatrolSpawnDeferred", "DEFERRED_SPAWN_TERMINAL"); return; }
        // Dispatch the HC override, which checks the hold before any provider/config read.
        value.SpawnAI_Deferred(index);
    }

    static void HCSitePatrolStop(HCXAISitePatrol value)
    {
        if (!value) { HCRefuse("HCSitePatrolStop", "RECEIVER_NULL"); return; }
        value.Stop();
    }

    static bool HCSitePatrolWasGroupDestroyed(HCXAISitePatrol value)
    {
        if (!value) { HCRefuse("HCSitePatrolWasGroupDestroyed", "RECEIVER_NULL"); return false; }
        if (!HCConfig(value.m_Config, "HCSitePatrolWasGroupDestroyed")) { return false; }
        return value.WasGroupDestroyed();
    }

    static bool HCBaseExpansion_IsAnimationIdle(eAIBase value)
    {
        if (!HCEntity(value, "HCBaseExpansion_IsAnimationIdle", true)) { return false; }
        return value.Expansion_IsAnimationIdle();
    }

    static void HCBaseExpansion_PlayEmote(eAIBase value)
    {
        if (!HCEntity(value, "HCBaseExpansion_PlayEmote", true)) { return; }
        value.Expansion_PlayEmote();
    }

    static void HCBaseExpansion_SetEmote(eAIBase value, int emoteID, bool autoCancel = false, int autoCancelDelay = 0)
    {
        if (!HCEntity(value, "HCBaseExpansion_SetEmote", true)) { return; }
        value.Expansion_SetEmote(emoteID, autoCancel, autoCancelDelay);
    }

    static EntityAI HCBaseFindAttachmentBySlotName(eAIBase value, string slot_name)
    {
        if (!HCEntity(value, "HCBaseFindAttachmentBySlotName", false)) { return null; }
        return value.FindAttachmentBySlotName(slot_name);
    }

    static eAIBase HCBaseGet(int index)
    {
        if (index < 0 || index >= eAIBase.eAI_GetAll().Count()) { HCRefuse("HCBaseGet", "ACTOR_INDEX"); return null; }
        return eAIBase.Get(index);
    }

    static ActionManagerBase HCBaseGetActionManager(eAIBase value)
    {
        if (!HCEntity(value, "HCBaseGetActionManager", false)) { return null; }
        return value.GetActionManager();
    }

    static bool HCBaseGetAllowDamage(eAIBase value)
    {
        if (!HCEntity(value, "HCBaseGetAllowDamage", false)) { return false; }
        return value.GetAllowDamage();
    }

    static EmoteManager HCBaseGetEmoteManager(eAIBase value)
    {
        if (!HCEntity(value, "HCBaseGetEmoteManager", false)) { return null; }
        return value.GetEmoteManager();
    }

    static EntityAI HCBaseGetEntityInHands(eAIBase value)
    {
        if (!HCEntity(value, "HCBaseGetEntityInHands", false)) { return null; }
        return value.GetEntityInHands();
    }

    static HumanInventory HCBaseGetHumanInventory(eAIBase value)
    {
        if (!HCEntity(value, "HCBaseGetHumanInventory", false)) { return null; }
        return value.GetHumanInventory();
    }

    static PlayerIdentity HCBaseGetIdentity(eAIBase value)
    {
        if (!HCEntity(value, "HCBaseGetIdentity", false)) { return null; }
        return value.GetIdentity();
    }

    static GameInventory HCBaseGetInventory(eAIBase value)
    {
        if (!HCEntity(value, "HCBaseGetInventory", false)) { return null; }
        return value.GetInventory();
    }

    static ItemBase HCBaseGetItemInHands(eAIBase value)
    {
        if (!HCEntity(value, "HCBaseGetItemInHands", false)) { return null; }
        return value.GetItemInHands();
    }

    static int HCBaseGetMovementSpeedLimit(eAIBase value)
    {
        if (!HCEntity(value, "HCBaseGetMovementSpeedLimit", false)) { return 0; }
        return value.GetMovementSpeedLimit();
    }

    static int HCBaseGetMovementSpeedLimitUnderThreat(eAIBase value)
    {
        if (!HCEntity(value, "HCBaseGetMovementSpeedLimitUnderThreat", false)) { return 0; }
        return value.GetMovementSpeedLimitUnderThreat();
    }

    static vector HCBaseGetPosition(eAIBase value)
    {
        if (!HCEntity(value, "HCBaseGetPosition", false)) { return vector.Zero; }
        return value.GetPosition();
    }

    static eAITarget HCBaseGetTarget(eAIBase value, int index = 0)
    {
        if (!HCEntity(value, "HCBaseGetTarget", true)) { return null; }
        return value.GetTarget(index);
    }

    static array<ref eAITarget> HCBaseGetTargets(eAIBase value)
    {
        if (!HCEntity(value, "HCBaseGetTargets", true)) { return null; }
        return value.GetTargets();
    }

    static float HCBaseGetThreatToSelf(eAIBase value, bool ignoreLOS = false)
    {
        if (!HCEntity(value, "HCBaseGetThreatToSelf", true)) { return 0; }
        return value.GetThreatToSelf(ignoreLOS);
    }

    static string HCBaseGetType(eAIBase value)
    {
        if (!HCEntity(value, "HCBaseGetType", false)) { return ""; }
        return value.GetType();
    }

    static bool HCBaseIsAlive(eAIBase value)
    {
        if (!HCEntity(value, "HCBaseIsAlive", false)) { return false; }
        return value.IsAlive();
    }

    static bool HCBaseIsDamageDestroyed(eAIBase value)
    {
        if (!HCEntity(value, "HCBaseIsDamageDestroyed", false)) { return false; }
        return value.IsDamageDestroyed();
    }

    static bool HCBaseIsPendingDeletion(eAIBase value)
    {
        if (!HCEntity(value, "HCBaseIsPendingDeletion", false)) { return false; }
        return value.IsPendingDeletion();
    }

    static bool HCBaseIsUnconscious(eAIBase value)
    {
        if (!HCEntity(value, "HCBaseIsUnconscious", false)) { return false; }
        return value.IsUnconscious();
    }

    static void HCBaseNotify_Transport(eAIBase value, Transport vehicle, int seatIndex)
    {
        if (!HCEntity(value, "HCBaseNotify_Transport", true)) { return; }
        value.Notify_Transport(vehicle, seatIndex);
    }

    static void HCBaseRaiseWeapon(eAIBase value, bool up = true)
    {
        if (!HCEntity(value, "HCBaseRaiseWeapon", true)) { return; }
        value.RaiseWeapon(up);
    }

    // Expansion eAIBase.LookAtPosition (ai_scripts eAIBase.c:9937) only stores a look target.
    static void HCBaseLookAtPosition(eAIBase value, vector worldPosition)
    {
        if (!HCEntity(value, "HCBaseLookAtPosition", true)) { return; }
        value.LookAtPosition(worldPosition);
    }

    static bool HCBaseServerDropEntity(eAIBase value, EntityAI item)
    {
        if (!HCEntity(value, "HCBaseServerDropEntity", true)) { return false; }
        return value.ServerDropEntity(item);
    }

    static void HCBaseSetMovementSpeedLimits(eAIBase value, int pSpeed, int pSpeedUnderThreat = -1)
    {
        if (!HCEntity(value, "HCBaseSetMovementSpeedLimits", true)) { return; }
        value.SetMovementSpeedLimits(pSpeed, pSpeedUnderThreat);
    }

    static ActionBase HCBaseStartAction(eAIBase value, typename actionType, ActionTarget target, ItemBase mainItem = null)
    {
        if (!HCEntity(value, "HCBaseStartAction", true)) { return null; }
        return value.StartAction(actionType, target, mainItem);
    }

    static int HCBaseTargetCount(eAIBase value)
    {
        if (!HCEntity(value, "HCBaseTargetCount", true)) { return 0; }
        return value.TargetCount();
    }

    static void HCBaseDespawn(eAIBase value)
    {
        if (!HCEntity(value, "HCBaseDespawn", true)) { return; }
        value.eAI_Despawn();
    }

    static void HCBaseFireWeaponOnClient(eAIBase value, int muzzleIndex, int shotID)
    {
        if (!HCEntity(value, "HCBaseFireWeaponOnClient", true)) { return; }
        value.eAI_FireWeaponOnClient(muzzleIndex, shotID);
    }

    static array<eAIBase> HCBaseGetAll()
    {
        return eAIBase.eAI_GetAll();
    }

    static void HCBaseSetDamageMultiplier(eAIBase value, float multiplier)
    {
        if (!HCEntity(value, "HCBaseSetDamageMultiplier", true)) { return; }
        value.eAI_SetDamageMultiplier(multiplier);
    }

    static void HCBaseSetDamageReceivedMultiplier(eAIBase value, float multiplier)
    {
        if (!HCEntity(value, "HCBaseSetDamageReceivedMultiplier", true)) { return; }
        value.eAI_SetDamageReceivedMultiplier(multiplier);
    }

    static void HCBaseSetEnableFlankingOutsideCombat(eAIBase value, int option)
    {
        if (!HCEntity(value, "HCBaseSetEnableFlankingOutsideCombat", true)) { return; }
        value.eAI_SetEnableFlankingOutsideCombat(option);
    }

    static void HCBaseSetHalt(eAIBase value, bool halt)
    {
        if (!HCEntity(value, "HCBaseSetHalt", true)) { return; }
        value.eAI_SetHalt(halt);
    }

    static void HCBaseSetLootingBehavior(eAIBase value, int bitmask)
    {
        if (!HCEntity(value, "HCBaseSetLootingBehavior", true)) { return; }
        value.eAI_SetLootingBehavior(bitmask);
    }

    static void HCBaseSetUnlimitedReload(eAIBase value, int unlimitedReload)
    {
        if (!HCEntity(value, "HCBaseSetUnlimitedReload", true)) { return; }
        value.eAI_SetUnlimitedReload(unlimitedReload);
    }

    static eAIFaction HCFactionCreate(string factionName)
    {
        if (!HCCheckFactionName(factionName, "FactionCreate")) { return null; }
        return eAIFaction.Create(factionName);
    }

    static float HCFactionGetMeleeDamageMultiplier(eAIFaction value)
    {
        if (!HCFactionValid(value, "HCFactionGetMeleeDamageMultiplier")) { return 0; }
        return value.GetMeleeDamageMultiplier();
    }

    static float HCFactionGetMeleeYeetForce(eAIFaction value)
    {
        if (!HCFactionValid(value, "HCFactionGetMeleeYeetForce")) { return 0; }
        return value.GetMeleeYeetForce();
    }

    static typename HCFactionGetType(string factionName)
    {
        if (!HCCheckFactionName(factionName, "FactionGetType")) { typename refused; return refused; }
        return eAIFaction.GetType(factionName);
    }

    static bool HCFactionHasUnlimitedStamina(eAIFaction value)
    {
        if (!HCFactionValid(value, "HCFactionHasUnlimitedStamina")) { return false; }
        return value.HasUnlimitedStamina();
    }

    static bool HCFactionIsGuard(eAIFaction value)
    {
        if (!HCFactionValid(value, "HCFactionIsGuard")) { return false; }
        return value.IsGuard();
    }

    static bool HCFactionIsInvincible(eAIFaction value)
    {
        if (!HCFactionValid(value, "HCFactionIsInvincible")) { return false; }
        return value.IsInvincible();
    }

    static bool HCFactionIsObserver(eAIFaction value)
    {
        if (!HCFactionValid(value, "HCFactionIsObserver")) { return false; }
        return value.IsObserver();
    }

    static bool HCFactionIsPassive(eAIFaction value)
    {
        if (!HCFactionValid(value, "HCFactionIsPassive")) { return false; }
        return value.IsPassive();
    }

    static typename HCFactionType(eAIFaction value)
    {
        if (!HCFactionValid(value, "HCFactionType")) { typename refused; return refused; }
        return value.Type();
    }

    static vector HCFormationGetPosition(eAIFormation value, int member_no)
    {
        if (!value) { HCRefuse("HCFormationGetPosition", "RECEIVER_NULL"); return vector.Zero; }
        return value.GetPosition(member_no);
    }

    static vector HCFormationToWorld(eAIFormation value, vector fs)
    {
        if (!value) { HCRefuse("HCFormationToWorld", "RECEIVER_NULL"); return vector.Zero; }
        return value.ToWorld(fs);
    }

    // Legacy raw-group layer (callers that hold a callback-supplied eAIGroup local). H8 follow-up:
    // every read is gated by lifecycle READY and counted by call. Kept ungated on purpose:
    // HCGroupGetID (an immutable id for pairing and persistence keys), HCGroupDelete and
    // HCGroupRemoveDeceased (cleanup). Despawn and stop persistence reads use the
    // HCHold*Final calls, which resolve in any state.
    static void HCGroupAddWaypoint(eAIGroup value, vector pos)
    {
        if (!HCGate("GroupAddWaypoint")) { return; }
        if (!value) { HCRefuse("HCGroupAddWaypoint", "GROUP_NULL"); return; }
        value.AddWaypoint(pos);
    }

    static void HCGroupClearWaypoints(eAIGroup value)
    {
        if (!HCGate("GroupClearWaypoints")) { return; }
        if (!value) { HCRefuse("HCGroupClearWaypoints", "GROUP_NULL"); return; }
        value.ClearWaypoints();
    }

    static int HCGroupCount(eAIGroup value)
    {
        if (!HCGate("GroupCount")) { return 0; }
        if (!value) { HCRefuse("HCGroupCount", "GROUP_NULL"); return 0; }
        return value.Count();
    }

    static eAIGroup HCGroupCreateGroup(eAIFaction faction)
    {
        if (!HCGate("GroupCreate")) { return null; }
        if (!HCFactionValid(faction, "HCGroupCreateGroup")) { return null; }
        return eAIGroup.CreateGroup(faction);
    }

    static int HCGroupDeceasedCount(eAIGroup value)
    {
        if (!HCGate("GroupDeceasedCount")) { return 0; }
        if (!value) { HCRefuse("HCGroupDeceasedCount", "GROUP_NULL"); return 0; }
        return value.DeceasedCount();
    }

    static void HCGroupDelete(eAIGroup value)
    {
        if (!value) { HCRefuse("HCGroupDelete", "GROUP_NULL"); return; }
        s_HCListStamp++;
        value.Delete();
    }

    static eAIFaction HCGroupGetFaction(eAIGroup value)
    {
        if (!HCGate("GroupGetFaction")) { return null; }
        if (!value) { HCRefuse("HCGroupGetFaction", "GROUP_NULL"); return null; }
        return value.GetFaction();
    }

    static eAIFormation HCGroupGetFormation(eAIGroup value)
    {
        if (!HCGate("GroupGetFormation")) { return null; }
        if (!value) { HCRefuse("HCGroupGetFormation", "GROUP_NULL"); return null; }
        return value.GetFormation();
    }

    static DayZPlayerImplement HCGroupGetFormationLeader(eAIGroup value)
    {
        if (!HCGate("GroupGetFormationLeader")) { return null; }
        if (!value) { HCRefuse("HCGroupGetFormationLeader", "GROUP_NULL"); return null; }
        return value.GetFormationLeader();
    }

    static eAIGroupFormationState HCGroupGetFormationState(eAIGroup value)
    {
        if (!HCGate("GroupGetFormationState")) { return 0; }
        if (!value) { HCRefuse("HCGroupGetFormationState", "GROUP_NULL"); return 0; }
        return value.GetFormationState();
    }

    static int HCGroupGetID(eAIGroup value)
    {
        if (!value) { HCRefuse("HCGroupGetID", "GROUP_NULL"); return 0; }
        return value.GetID();
    }

    static int HCGroupGetIndex(eAIGroup value, DayZPlayerImplement player)
    {
        if (!HCGate("GroupGetIndex")) { return -1; }
        if (!value) { HCRefuse("HCGroupGetIndex", "GROUP_NULL"); return -1; }
        if (!HCEntity(player, "HCGroupGetIndex", false)) { return -1; }
        return value.GetIndex(player);
    }

    static DayZPlayerImplement HCGroupGetMember(eAIGroup value, int i)
    {
        if (!HCGate("GroupGetMember")) { return null; }
        if (!value) { HCRefuse("HCGroupGetMember", "GROUP_NULL"); return null; }
        if (i < 0 || i >= value.Count()) { HCRefuse("HCGroupGetMember", "MEMBER_INDEX"); return null; }
        return value.GetMember(i);
    }

    static string HCGroupGetName(eAIGroup value)
    {
        if (!HCGate("GroupGetName")) { return ""; }
        if (!value) { HCRefuse("HCGroupGetName", "GROUP_NULL"); return ""; }
        return value.GetName();
    }

    static eAIWaypointBehavior HCGroupGetWaypointBehaviour(eAIGroup value)
    {
        if (!HCGate("GroupGetWaypointBehaviour")) { return 0; }
        if (!value) { HCRefuse("HCGroupGetWaypointBehaviour", "GROUP_NULL"); return 0; }
        return value.GetWaypointBehaviour();
    }

    static array<vector> HCGroupGetWaypoints(eAIGroup value)
    {
        if (!HCGate("GroupGetWaypoints")) { return null; }
        if (!value) { HCRefuse("HCGroupGetWaypoints", "GROUP_NULL"); return null; }
        return value.GetWaypoints();
    }

    static bool HCGroupIsInCombat(eAIGroup value)
    {
        if (!HCGate("GroupIsInCombat")) { return false; }
        if (!value) { HCRefuse("HCGroupIsInCombat", "GROUP_NULL"); return false; }
        return value.IsInCombat();
    }

    static bool HCGroupRemoveDeceased(eAIGroup value, int i)
    {
        if (!value) { HCRefuse("HCGroupRemoveDeceased", "GROUP_NULL"); return false; }
        if (i < 0 || i >= value.DeceasedCount()) { HCRefuse("HCGroupRemoveDeceased", "MEMBER_INDEX"); return false; }
        return value.RemoveDeceased(i);
    }

    static void HCGroupSetFormation(eAIGroup value, eAIFormation f)
    {
        if (!HCGate("GroupSetFormation")) { return; }
        if (!value) { HCRefuse("HCGroupSetFormation", "GROUP_NULL"); return; }
        if (!f) { HCRefuse("HCGroupSetFormation", "FORMATION_NULL"); return; }
        value.SetFormation(f);
    }

    static void HCGroupSetWaypointBehaviour(eAIGroup value, eAIWaypointBehavior bhv)
    {
        if (!HCGate("GroupSetWaypointBehaviour")) { return; }
        if (!value) { HCRefuse("HCGroupSetWaypointBehaviour", "GROUP_NULL"); return; }
        value.SetWaypointBehaviour(bhv);
    }

    static EntityAI HCTargetGetEntity(eAITarget value)
    {
        if (!value) { HCRefuse("HCTargetGetEntity", "RECEIVER_NULL"); return null; }
        return value.GetEntity();
    }

    static vector HCTargetGetPosition(eAITarget value, bool actual = false)
    {
        if (!value) { HCRefuse("HCTargetGetPosition", "RECEIVER_NULL"); return vector.Zero; }
        return value.GetPosition(actual);
    }

    static void HCTargetSetInitial(eAITarget value, float threat, vector position)
    {
        if (!value) { HCRefuse("HCTargetSetInitial", "RECEIVER_NULL"); return; }
        value.SetInitial(threat, position);
    }

    static void HCTargetSetThreat(eAITarget value, float threat)
    {
        if (!value) { HCRefuse("HCTargetSetThreat", "RECEIVER_NULL"); return; }
        value.SetThreat(threat);
    }

    static void HCTargetUpdateFoundAtTime(eAITarget value)
    {
        if (!value) { HCRefuse("HCTargetUpdateFoundAtTime", "RECEIVER_NULL"); return; }
        value.UpdateFoundAtTime();
    }


    static eAITarget HCTargetInformationAddAI(eAITargetInformation value, eAIBase ai, int maxTime = -1, bool initialUpdate = true, out bool created = false)
    {
        created = false;
        if (!value) { HCRefuse("HCTargetInformationAddAI", "RECEIVER_NULL"); return null; }
        if (!HCEntity(ai, "HCTargetInformationAddAI")) { return null; }
        return value.AddAI(ai, maxTime, initialUpdate, created);
    }

    static eAITarget HCTargetInformationGetTargetForAI(eAITargetInformation value, eAIBase ai)
    {
        if (!value) { HCRefuse("HCTargetInformationGetTargetForAI", "RECEIVER_NULL"); return null; }
        if (!HCEntity(ai, "HCTargetInformationGetTargetForAI")) { return null; }
        return value.GetTargetForAI(ai);
    }

    static bool HCTargetInformationIsItem(eAITargetInformation value)
    {
        if (!value) { HCRefuse("HCTargetInformationIsItem", "RECEIVER_NULL"); return false; }
        return value.IsItem();
    }

    static bool HCTargetInformationIsNoise(eAITargetInformation value)
    {
        if (!value) { HCRefuse("HCTargetInformationIsNoise", "RECEIVER_NULL"); return false; }
        return value.IsNoise();
    }

    static bool HCTargetInformationIsZombie(eAITargetInformation value)
    {
        if (!value) { HCRefuse("HCTargetInformationIsZombie", "RECEIVER_NULL"); return false; }
        return value.IsZombie();
    }

    // Death-hold validation reads only the existing strong hold.
    static bool HCHeldDeathClean(HCXAIGroupHold hold, array<DayZPlayerImplement> killed, out bool terminal)
    {
        terminal = false;
        if (!hold) { HCRefuse("HCHeldDeathClean", "DEATH_HOLD_IDENTITY_MISSING"); return false; }
        return hold.HCDeathClean(killed, terminal);
    }
    // #334: resolve a stored group id to the live group, or null when it is gone.
    // Group ids are never reused (eAIGroup.s_IDCounter only increments), so a stale id
    // cannot match another group. Use this instead of keeping a raw eAIGroup handle in
    // long-lived records. Never creates a group.
    static eAIGroup HCGroupById(int id)
    {
        if (id <= 0) { return null; }
        return eAIGroup.GetGroupByID(id, false);
    }

    // H8 handle layer. Every call resolves the hold once, counts group_gone on null and
    // returns its documented default: 0, null, false or a fresh empty array (never a shared
    // static one). HCHoldId and HCHoldSame never touch the provider and work in any state.
    protected static eAIGroup HCHoldGroup(HCXAIGroupHold hold, string call)
    {
        if (!HCGate(call)) { return null; }
        if (!hold) { return null; }
        eAIGroup resolved = hold.HCResolve();
        if (!resolved) { HCCountGone(call); }
        return resolved;
    }

    // The held group as a short-lived local for one tick's work (callers that still take an
    // eAIGroup parameter); null when the handle is dead or the bridge is not READY. Never store it.
    static eAIGroup HCHoldResolve(HCXAIGroupHold hold)
    {
        return HCHoldGroup(hold, "HoldResolve");
    }

    // H8 agent handle layer. HCAgent resolves a handle to the live entity or null (never
    // creates one); a dead, early or older-epoch handle is the caller's "agent gone" path.
    static HCXAIAgentHold HCAgentHold(eAIBase agent)
    {
        if (!agent) { return null; }
        return new HCXAIAgentHold(agent);
    }

    static eAIBase HCAgent(HCXAIAgentHold hold)
    {
        if (!hold) { return null; }
        if (!HCGate("AgentResolve")) { return null; }
        eAIBase resolved = hold.HCResolve();
        if (!resolved) { HCCountCall("AgentResolve:AGENT_GONE"); }
        return resolved;
    }

    // Cleanup only (undo a halt, release a lease): resolves in any lifecycle state and epoch,
    // because the effect being undone outlives the epoch that made it. Null once deleted.
    static eAIBase HCAgentCleanup(HCXAIAgentHold hold)
    {
        if (!hold) { return null; }
        return hold.HCResolveCleanup();
    }

    // Pointer identity against an agent the caller holds as a local; never dereferences.
    static bool HCAgentSame(HCXAIAgentHold hold, eAIBase agent)
    {
        if (!hold || !agent) { return false; }
        return hold.HCIsAgent(agent);
    }

    static int HCHoldId(HCXAIGroupHold hold)
    {
        if (!hold) { return 0; }
        return hold.Id;
    }

    // Pointer identity against a group the caller holds as a local; never dereferences.
    static bool HCHoldSame(HCXAIGroupHold hold, eAIGroup group)
    {
        if (!hold || !group) { return false; }
        return hold.HCIsGroup(group);
    }

    static bool HCHoldAlive(HCXAIGroupHold hold)
    {
        return HCHoldGroup(hold, "HoldAlive") != null;
    }

    static int HCHoldCount(HCXAIGroupHold hold)
    {
        eAIGroup group = HCHoldGroup(hold, "HoldCount");
        if (!group) { return 0; }
        return group.Count();
    }

    static DayZPlayerImplement HCHoldGetMember(HCXAIGroupHold hold, int i)
    {
        eAIGroup group = HCHoldGroup(hold, "HoldGetMember");
        if (!group) { return null; }
        if (i < 0 || i >= group.Count()) { HCRefuse("HCHoldGetMember", "MEMBER_INDEX"); return null; }
        return group.GetMember(i);
    }

    static bool HCHoldHasMember(HCXAIGroupHold hold, DayZPlayerImplement player)
    {
        eAIGroup group = HCHoldGroup(hold, "HoldHasMember");
        if (!group || !player) { return false; }
        return HCDayZPlayerImplementGetGroup(player) == group;
    }

    static bool HCHoldIsInCombat(HCXAIGroupHold hold)
    {
        eAIGroup group = HCHoldGroup(hold, "HoldIsInCombat");
        if (!group) { return false; }
        return group.IsInCombat();
    }

    static DayZPlayerImplement HCHoldGetFormationLeader(HCXAIGroupHold hold)
    {
        eAIGroup group = HCHoldGroup(hold, "HoldGetFormationLeader");
        if (!group) { return null; }
        return group.GetFormationLeader();
    }

    static eAIGroupFormationState HCHoldGetFormationState(HCXAIGroupHold hold)
    {
        eAIGroup group = HCHoldGroup(hold, "HoldGetFormationState");
        if (!group) { return 0; }
        return group.GetFormationState();
    }

    static eAIFaction HCHoldGetFaction(HCXAIGroupHold hold)
    {
        eAIGroup group = HCHoldGroup(hold, "HoldGetFaction");
        if (!group) { return null; }
        return group.GetFaction();
    }

    static string HCHoldGetName(HCXAIGroupHold hold)
    {
        eAIGroup group = HCHoldGroup(hold, "HoldGetName");
        if (!group) { return ""; }
        return group.GetName();
    }

    static eAIWaypointBehavior HCHoldGetWaypointBehaviour(HCXAIGroupHold hold)
    {
        eAIGroup group = HCHoldGroup(hold, "HoldGetWaypointBehaviour");
        if (!group) { return 0; }
        return group.GetWaypointBehaviour();
    }

    static array<vector> HCHoldGetWaypoints(HCXAIGroupHold hold)
    {
        eAIGroup group = HCHoldGroup(hold, "HoldGetWaypoints");
        array<vector> points;
        if (group) { points = group.GetWaypoints(); }
        if (!points) { points = new array<vector>; }
        return points;
    }

    static void HCHoldAddWaypoint(HCXAIGroupHold hold, vector pos)
    {
        eAIGroup group = HCHoldGroup(hold, "HoldAddWaypoint");
        if (!group) { return; }
        group.AddWaypoint(pos);
    }

    static void HCHoldClearWaypoints(HCXAIGroupHold hold)
    {
        eAIGroup group = HCHoldGroup(hold, "HoldClearWaypoints");
        if (!group) { return; }
        group.ClearWaypoints();
    }

    static void HCHoldSetWaypointBehaviour(HCXAIGroupHold hold, eAIWaypointBehavior bhv)
    {
        eAIGroup group = HCHoldGroup(hold, "HoldSetWaypointBehaviour");
        if (!group) { return; }
        group.SetWaypointBehaviour(bhv);
    }

    static void HCHoldSetFormation(HCXAIGroupHold hold, eAIFormation f)
    {
        eAIGroup group = HCHoldGroup(hold, "HoldSetFormation");
        if (!group) { return; }
        if (!f) { HCRefuse("HCHoldSetFormation", "FORMATION_NULL"); return; }
        group.SetFormation(f);
    }

    // Handle-to-handle identity (pointer compare of the two held groups); never dereferences.
    static bool HCHoldSameHold(HCXAIGroupHold hold, HCXAIGroupHold other)
    {
        if (!hold || !other) { return false; }
        return hold.HCSameGroup(other);
    }

    // A new or kept hold for the group another handle resolves to; a dead source retires the
    // current hold and yields null (the caller's "group gone" path).
    static HCXAIGroupHold HCHoldFollowHold(HCXAIGroupHold current, HCXAIGroupHold source)
    {
        eAIGroup resolved = HCHoldGroup(source, "HoldFollow");
        return HCXAIGroupHolds.Follow(current, resolved);
    }

    static int HCHoldDeceasedCount(HCXAIGroupHold hold)
    {
        eAIGroup group = HCHoldGroup(hold, "HoldDeceasedCount");
        if (!group) { return 0; }
        return group.DeceasedCount();
    }

    static eAIFormation HCHoldGetFormation(HCXAIGroupHold hold)
    {
        eAIGroup group = HCHoldGroup(hold, "HoldGetFormation");
        if (!group) { return null; }
        return group.GetFormation();
    }

    static int HCHoldGetIndex(HCXAIGroupHold hold, DayZPlayerImplement player)
    {
        eAIGroup group = HCHoldGroup(hold, "HoldGetIndex");
        if (!group) { return -1; }
        if (!HCEntity(player, "HCHoldGetIndex", false)) { return -1; }
        return group.GetIndex(player);
    }

    // Final reads: the Despawn and stop persistence path. They resolve in any lifecycle state
    // (READY, NOT_READY, SHUTTING_DOWN) of the current epoch so a stopping patrol still reads its real group and
    // never persists a defaulted "cleared" site. They are never gated and never counted; a
    // retired hold, an older epoch or a group the provider no longer lists still reads as gone.
    protected static eAIGroup HCHoldGroupFinal(HCXAIGroupHold hold)
    {
        if (!hold) { return null; }
        return hold.HCResolveAny();
    }

    // Cleanup-class route undo (raid cancel): resolves like a Final read, so the lifecycle gate
    // (NOT_READY, SHUTTING_DOWN) never skips restoring the original route. The epoch is still
    // checked (HCResolveAny): a cancel after the epoch bump cannot restore, and logs that once.
    // Not for new work.
    protected static bool s_HCCleanupStaleLogged;
    protected static eAIGroup HCHoldGroupCleanup(HCXAIGroupHold hold, string call)
    {
        eAIGroup group = HCHoldGroupFinal(hold);
        if (!group && hold && hold.HCEpochStale())
        {
            HCCountCall(call + ":EPOCH_STALE");
            if (!s_HCCleanupStaleLogged)
            {
                s_HCCleanupStaleLogged = true;
                Print("[HCX Bridge] route restore skipped call=" + call + " reason=EPOCH_STALE");
            }
        }
        return group;
    }

    static void HCHoldClearWaypointsCleanup(HCXAIGroupHold hold)
    {
        eAIGroup group = HCHoldGroupCleanup(hold, "HoldClearWaypointsCleanup");
        if (!group) { return; }
        group.ClearWaypoints();
    }

    static void HCHoldAddWaypointCleanup(HCXAIGroupHold hold, vector pos)
    {
        eAIGroup group = HCHoldGroupCleanup(hold, "HoldAddWaypointCleanup");
        if (!group) { return; }
        group.AddWaypoint(pos);
    }

    static void HCHoldSetWaypointBehaviourCleanup(HCXAIGroupHold hold, eAIWaypointBehavior bhv)
    {
        eAIGroup group = HCHoldGroupCleanup(hold, "HoldSetWaypointBehaviourCleanup");
        if (!group) { return; }
        group.SetWaypointBehaviour(bhv);
    }

    // Cleanup-class reads for the "is the route still ours" check before a restore: same
    // resolution as the Cleanup writers, so a restore outside READY can still verify and run.
    static array<vector> HCHoldGetWaypointsCleanup(HCXAIGroupHold hold)
    {
        eAIGroup group = HCHoldGroupCleanup(hold, "HoldGetWaypointsCleanup");
        array<vector> points;
        if (group) { points = group.GetWaypoints(); }
        if (!points) { points = new array<vector>; }
        return points;
    }

    static eAIWaypointBehavior HCHoldGetWaypointBehaviourCleanup(HCXAIGroupHold hold)
    {
        eAIGroup group = HCHoldGroupCleanup(hold, "HoldGetWaypointBehaviourCleanup");
        if (!group) { return 0; }
        return group.GetWaypointBehaviour();
    }

    static bool HCHoldAliveFinal(HCXAIGroupHold hold)
    {
        return HCHoldGroupFinal(hold) != null;
    }

    static int HCHoldCountFinal(HCXAIGroupHold hold)
    {
        eAIGroup group = HCHoldGroupFinal(hold);
        if (!group) { return 0; }
        return group.Count();
    }

    static int HCHoldDeceasedCountFinal(HCXAIGroupHold hold)
    {
        eAIGroup group = HCHoldGroupFinal(hold);
        if (!group) { return 0; }
        return group.DeceasedCount();
    }

    static bool HCHoldIsInCombatFinal(HCXAIGroupHold hold)
    {
        eAIGroup group = HCHoldGroupFinal(hold);
        if (!group) { return false; }
        return group.IsInCombat();
    }

    static bool HCHoldForcePatrolDespawnFinal(HCXAIGroupHold hold)
    {
        eAIGroup group = HCHoldGroupFinal(hold);
        if (!group) { return false; }
        return group.m_ForcePatrolDespawn;
    }

    // Cleanup, never gated: drop the corpse records of a group so its later deletion cannot
    // touch them. Returns the number removed.
    static int HCHoldRemoveDeceasedAll(HCXAIGroupHold hold)
    {
        eAIGroup group = HCHoldGroupFinal(hold);
        if (!group) { return 0; }
        int removed = 0;
        int bodyCount = group.DeceasedCount();
        while (bodyCount > 0)
        {
            bodyCount--;
            if (group.RemoveDeceased(bodyCount)) { removed++; }
        }
        return removed;
    }
}

// H8 follow-up: an eAIBase is an engine entity that the provider deletes on its own schedule
// (corpse cleanup, despawn, wipe). Holders outside this file keep an HCXAIAgentHold, never an
// eAIBase member; HCXExpansionBridge.HCAgent resolves it. The handle is weak, so a deleted
// agent reads as null; the epoch and READY gate make every older or early handle read as gone.
// A resolved agent may be a corpse: callers still check HCBaseIsAlive themselves.
class HCXAIAgentHold
{
    // Never read outside this file.
    protected eAIBase Agent;
    int Epoch;
    void HCXAIAgentHold(eAIBase agent)
    {
        Agent = agent;
        Epoch = HCXExpansionBridge.HCEpoch();
    }
    bool HCIsAgent(eAIBase agent)
    {
        return Agent != null && Agent == agent;
    }
    eAIBase HCResolveCleanup()
    {
        return Agent;
    }
    eAIBase HCResolve()
    {
        if (!Agent || Epoch != HCXExpansionBridge.HCEpoch()) { return null; }
        if (!HCXExpansionBridge.HCLive()) { return null; }
        return Agent;
    }
}

// #334: eAIGroup is not Managed, so eAIDynamicPatrol.m_Group and each member's
// group pointer are raw. When the first corpse of a wiped group is deleted, the
// provider destroys the group on the next frame (DayZPlayerImplement.eAI_Cleanup
// from the destructor). The patrol and the remaining corpses still point at it.
// HC holds a strong reference to each site group until every member entity it set
// up is deleted, plus a settle window for the provider's queued DeleteGroup call.
class HCXAIGroupHold
{
    // Never read outside this file: HCResolve and the HCHold* bridge calls are the only way in.
    protected ref eAIGroup Group;
    ref array<DayZPlayerImplement> Members;
    int SettledAtMs;
    int SettledSeenMs;
    int SettledSeen;
    // H8 handle: the bridge epoch the hold was made in, the provider group id (ids are never
    // reused) and whether the owner retired it. Outside the bridge only HCResolve and the
    // HCHold* bridge calls read the group.
    int Epoch;
    int Id;
    int Deaths;
    bool Retired;
    static const int HC_LISTED_TTL_MS = 100;
    int ListedAtMs = -1;
    int ListedStamp;
    bool ListedGone;
    void HCXAIGroupHold(eAIGroup group)
    {
        Group = group;
        Members = new array<DayZPlayerImplement>;
        SettledAtMs = -1;
        SettledSeenMs = -1;
        Epoch = HCXExpansionBridge.HCEpoch();
        // Identity is read only after the strong reference has been established.
        if (Group) { Id = Group.GetID(); }
        HCXExpansionBridge.HCHandleMade();
    }
    void ~HCXAIGroupHold()
    {
        HCXExpansionBridge.HCHandleDropped();
    }
    // Pointer identity only; never dereferences the group, works in any bridge state.
    bool HCIsGroup(eAIGroup group)
    {
        return Group != null && Group == group;
    }
    bool HCSameGroup(HCXAIGroupHold other)
    {
        return other != null && Group != null && Group == other.Group;
    }
    // Only the settled retired pass may release the strong provider ref.
    void HCReleaseSettled()
    {
        Group = null;
    }
    bool HCHasGroup()
    {
        return Group != null;
    }
    // Null when the bridge is not READY, the hold is from an older epoch or retired, or the
    // provider no longer knows the group. A null result is a normal outcome.
    eAIGroup HCResolve()
    {
        if (Retired || !Group || Epoch != HCXExpansionBridge.HCEpoch()) { return null; }
        if (!HCXExpansionBridge.HCLive()) { return null; }
        if (!this.HCListed()) { return null; }
        return Group;
    }
    bool HCEpochStale()
    {
        return Epoch != HCXExpansionBridge.HCEpoch();
    }
    // Same checks without the lifecycle gate (the epoch is still enforced): only the HCHold*Final
    // persistence reads and the HCHold*Cleanup route undo use it.
    eAIGroup HCResolveAny()
    {
        if (Retired || !Group || Epoch != HCXExpansionBridge.HCEpoch()) { return null; }
        if (!this.HCListed()) { return null; }
        return Group;
    }
    // Whether the provider still lists this group. eAIGroup.GetGroupByID is a linear scan of
    // the provider's group list and every bridge call resolves the hold, so a per-state loop
    // cost one scan per call (RC audit row 4, R2 20.12 ms). The answer is cached on the hold:
    // "gone" is final (group ids are never reused), "listed" is trusted for HC_LISTED_TTL_MS and
    // dropped at once when HC itself deletes a group (HCListStamp). The hold's strong reference
    // keeps the object valid, so the worst case of a stale "listed" is one command to a group the
    // provider has just removed, which its own null checks absorb. At most one scan per hold per
    // 100 ms, not one per call.
    protected bool HCListed()
    {
        if (Id <= 0) { return true; }
        if (ListedGone) { return false; }
        int nowMs = 0;
        if (GetGame()) { nowMs = GetGame().GetTime(); }
        int age = nowMs - ListedAtMs;
        if (ListedAtMs >= 0 && age >= 0 && age < HC_LISTED_TTL_MS && ListedStamp == HCXExpansionBridge.HCListStamp()) { return true; }
        if (HCXExpansionBridge.HCGroupById(Id) != Group)
        {
            ListedGone = true;
            return false;
        }
        ListedAtMs = nowMs;
        ListedStamp = HCXExpansionBridge.HCListStamp();
        return true;
    }
    bool HCDeathClean(array<DayZPlayerImplement> killed, out bool terminal)
    {
        terminal = false;
        if (Retired || Epoch != HCXExpansionBridge.HCEpoch() || !Group || Id <= 0 || !killed || killed.Count() == 0)
        {
            HCXExpansionBridge.HCRefuse("HCHeldDeathClean", "DEATH_HOLD_IDENTITY_MISSING");
            return false;
        }
        if (eAIGroup.GetGroupByID(Id, false) != Group)
        {
            terminal = true;
            HCXExpansionBridge.HCRefuse("HCHeldDeathClean", "DEATH_HOLD_GROUP_UNLISTED");
            return false;
        }
        int live = Group.Count();
        if (live == 0) { terminal = true; return false; }
        if (live > 16 || killed.Count() > 16)
        {
            HCXExpansionBridge.HCRefuse("HCHeldDeathClean", "DEATH_HOLD_MEMBER_CAP");
            return false;
        }
        foreach (DayZPlayerImplement dead : killed)
        {
            // Deleted weak entries are absent too; deceased accounting below must
            // still confirm provider cleanup, otherwise defer until terminal.
            if (dead && Group.GetIndex(dead) >= 0)
            {
                HCXExpansionBridge.HCRefuse("HCHeldDeathClean", "DEATH_HOLD_CLEANUP_PENDING");
                return false;
            }
        }
        if (Deaths < killed.Count() || Group.DeceasedCount() < Deaths)
        {
            HCXExpansionBridge.HCRefuse("HCHeldDeathClean", "DEATH_HOLD_DECEASED_UNCONFIRMED");
            return false;
        }
        return true;
    }
    // A positive cache entry is never death-hold release/resume evidence.
    eAIGroup HCResolveFresh()
    {
        if (Retired || !Group || Id <= 0 || Epoch != HCXExpansionBridge.HCEpoch() || !HCXExpansionBridge.HCLive()) { return null; }
        if (HCXExpansionBridge.HCGroupById(Id) != Group) { ListedGone = true; return null; }
        return Group;
    }
    bool HCNamesLiveSlot()
    {
        return HCXAISitePatrol.HCNamesLiveSlot(Group);
    }
    void Track(DayZPlayerImplement member)
    {
        if (member && Members.Find(member) < 0) { Members.Insert(member); }
    }
    // Bounded: at most 16 current members of the held group.
    void TrackGroup()
    {
        // Bookkeeping on the hold's own strong reference: never lifecycle-gated, or a hold made
        // outside READY would track no member and release its group early.
        if (!Group) { return; }
        int count = Group.Count();
        for (int memberIndex = 0; memberIndex < count && memberIndex < 16; memberIndex++)
        {
            this.Track(Group.GetMember(memberIndex));
        }
    }
    // Adds another hold's live members (bounded); used when a group is retired twice.
    void Absorb(HCXAIGroupHold other)
    {
        for (int at = Members.Count() - 1; at >= 0; at--)
        {
            if (!Members[at]) { Members.Remove(at); }
        }
        if (!other || !other.Members) { return; }
        foreach (DayZPlayerImplement member : other.Members)
        {
            if (Members.Count() >= 32) { return; }
            this.Track(member);
        }
    }
    // Entries are weak and turn null once the entity is deleted.
    bool Settled()
    {
        foreach (DayZPlayerImplement member : Members)
        {
            if (member) { return false; }
        }
        return true;
    }
}

// Retired holds: bounded scan, two entries per site-director owner tick.
// A hold is released once its last
// tracked member has been gone for 2 s AND on three distinct frames, so one long
// hitch cannot release it before the provider's queued group cleanup has run.
class HCXAIGroupHolds
{
    protected static ref array<ref HCXAIGroupHold> s_Retired;
    protected static int s_Cursor;
    protected static bool s_HighLogged;
    protected static bool s_FinishReleased;
    static const int HC_SETTLE_MS = 2000;
    static const int HC_HIGH_COUNT = 256;
    static void Retire(HCXAIGroupHold hold)
    {
        // Retirement stays active during OnStop, but never re-creates the list after the
        // finish release pass, even while the game pointer still exists during static cleanup.
        if (s_FinishReleased || !hold || !hold.HCHasGroup() || !GetGame()) { return; }
        hold.Retired = true;
        if (!s_Retired) { s_Retired = new array<ref HCXAIGroupHold>; }
        // One retired hold per group: a group retired again (leases, jobs, replans) merges its
        // members into the existing hold, so the list is bounded by groups, not by events.
        foreach (HCXAIGroupHold retired : s_Retired)
        {
            if (retired && retired.HCSameGroup(hold))
            {
                retired.Absorb(hold);
                if (!retired.Settled())
                {
                    retired.SettledAtMs = -1;
                    retired.SettledSeen = 0;
                }
                return;
            }
        }
        s_Retired.Insert(hold);
        if (s_Retired.Count() > HC_HIGH_COUNT && !s_HighLogged)
        {
            s_HighLogged = true;
            Print("[HCX Bridge] retired group holds high count=" + s_Retired.Count().ToString() + " reason=corpses_outlive_sites");
        }
    }
    static void HCFinish()
    {
        if (!HCServer.HCMissionFinishing() || s_FinishReleased) { return; }
        // Native 3_Game/Global/Game.c:1535 GetTime; 1_Core/proto/EnScript.c:463
        // Remove is unordered: reverse traversal needs no retained order. EnDebug.c:96 Print.
        int released = 0;
        int retained = 0;
        int nowMs = 0;
        if (GetGame()) { nowMs = GetGame().GetTime(); }
        // One shutdown pass over the existing retired list; never walk live owners.
        // Identical release evidence to PruneStep: no live slot/member, 2 s and 3 frames.
        if (s_Retired)
        {
            for (int at = s_Retired.Count() - 1; at >= 0; at--)
            {
                HCXAIGroupHold held = s_Retired[at];
                if (held)
                {
                    if (!GetGame() || held.HCNamesLiveSlot() || !held.Settled() || held.SettledAtMs < 0 || nowMs - held.SettledAtMs < HC_SETTLE_MS || held.SettledSeen < 3)
                    {
                        retained++;
                        continue;
                    }
                    // Clear even if another owner still holds this retired handle: every resolver
                    // refuses a null Group before touching the provider, including Final reads.
                    held.HCReleaseSettled();
                    released++;
                }
                s_Retired.Remove(at);
            }
        }
        s_FinishReleased = true;
        Print("[HC XAI Bridge] teardown retired_released=" + released.ToString() + " retained=" + retained.ToString());
    }

    static void PruneStep()
    {
        if (!s_Retired || !GetGame()) { return; }
        int nowMs = GetGame().GetTime();
        for (int checked = 0; checked < 2 && s_Retired.Count() > 0; checked++)
        {
            if (s_Cursor >= s_Retired.Count()) { s_Cursor = 0; }
            HCXAIGroupHold hold = s_Retired[s_Cursor];
            if (hold && hold.HCNamesLiveSlot()) { hold.SettledAtMs = -1; hold.SettledSeen = 0; s_Cursor++; continue; }
            if (hold && !hold.Settled()) { hold.SettledAtMs = -1; hold.SettledSeen = 0; s_Cursor++; continue; }
            if (hold && hold.SettledSeenMs != nowMs) { hold.SettledSeenMs = nowMs; hold.SettledSeen++; }
            if (hold && hold.SettledAtMs < 0) { hold.SettledAtMs = nowMs; s_Cursor++; continue; }
            if (hold && (nowMs - hold.SettledAtMs < HC_SETTLE_MS || hold.SettledSeen < 3)) { s_Cursor++; continue; }
            s_Retired.Remove(s_Cursor);
        }
    }
    // Removes the oldest retired hold that has met the PruneStep release rule (settled for
    // HC_SETTLE_MS and three distinct frames) or that is already null; false when none is ready.
    protected static bool EvictOldestReleasable()
    {
        if (!s_Retired) { return false; }
        for (int at = 0; at < s_Retired.Count(); at++)
        {
            HCXAIGroupHold held = s_Retired[at];
            if (held)
            {
                if (held.HCNamesLiveSlot()) { continue; }
                if (!held.Settled() || held.SettledAtMs < 0 || held.SettledSeen < 3) { continue; }
                if (GetGame() && GetGame().GetTime() - held.SettledAtMs < HC_SETTLE_MS) { continue; }
            }
            s_Retired.Remove(at);
            if (s_Cursor > at) { s_Cursor--; }
            return true;
        }
        return false;
    }
    // Returns the hold for group and tracks its members; a hold on another group is retired.
    // Never null while group is non-null.
    static HCXAIGroupHold Follow(HCXAIGroupHold hold, eAIGroup group)
    {
        if (hold && hold.HCIsGroup(group))
        {
            hold.TrackGroup();
            return hold;
        }
        Retire(hold);
        if (!group) { return null; }
        // Retired holds at the high-water mark: a live slot group always gets its hold (a null
        // here would skip the combat-despawn veto and persist a false "cleared" site). Make room
        // by evicting the oldest hold that PruneStep would already release; if none is ready the
        // list overshoots (up to the absolute ceiling below) until one settles.
        if (Count() >= HC_HIGH_COUNT)
        {
            HCXExpansionBridge.HCCountHoldCap();
            EvictOldestReleasable();
        }
        // Absolute ceiling: past twice the high-water mark with nothing releasable, refuse the
        // new handle (counted, one rate-limited log line). Callers treat a null hold as "group
        // not read" (Despawn skips RecordCleared, no false cleared site).
        if (Count() >= HC_HIGH_COUNT * 2)
        {
            HCXExpansionBridge.HCCountHoldAbsoluteCap();
            HCXExpansionBridge.HCRefuse("HCXAIGroupHolds.Follow", "HOLD_ABSOLUTE_CAP count=" + Count().ToString());
            return null;
        }
        HCXAIGroupHold next = new HCXAIGroupHold(group);
        next.TrackGroup();
        return next;
    }
    static int Count()
    {
        if (!s_Retired) { return 0; }
        return s_Retired.Count();
    }
}

// Provider superclass dispatch is kept here to avoid virtual recursion.
class HCXExpansionPatrol : eAIDynamicPatrol
{
    protected bool HCBridgeCanSpawn()
    {
        if (!HCXExpansionBridge.HCGate("PatrolCanSpawn")) { return false; }
        if (!HCXExpansionBridge.HCConfig(m_Config, "CanSpawn")) { return false; }
        return super.CanSpawn();
    }
    protected void HCBridgeSpawn()
    {
        if (!HCXExpansionBridge.HCGate("PatrolSpawn")) { return; }
        if (!HCXExpansionBridge.HCConfig(m_Config, "Spawn")) { return; }
        super.Spawn();
    }
    protected void HCBridgeSpawnAI_Deferred(int i)
    {
        if (!HCXExpansionBridge.HCGate("PatrolSpawnAI")) { return; }
        if (!HCXExpansionBridge.HCConfig(m_Config, "SpawnAI_Deferred")) { return; }
        if (!m_Group || !m_Formation) { HCXExpansionBridge.HCRefuse("SpawnAI_Deferred", "GROUP_OR_FORMATION_NULL"); return; }
        super.SpawnAI_Deferred(i);
    }
    // The provider slot is raw. Identity comparisons never dereference it; only
    // the unheld spawn/update path may Follow it into an owned hold. Other
    // readers resolve the hold, with death-sensitive readers using a fresh lookup.
    bool HCBridgeHasGroupSlot()
    {
        return m_Group != null;
    }
    bool HCBridgeNamesGroup(eAIGroup group)
    {
        return group && m_Group == group;
    }
    bool HCBridgeOwnsHold(HCXAIGroupHold hold)
    {
        return hold && hold.HCIsGroup(m_Group);
    }
    HCXAIGroupHold HCBridgeFollowHold(HCXAIGroupHold hold)
    {
        return HCXAIGroupHolds.Follow(hold, m_Group);
    }
    protected void HCBridgeDespawn(bool deferDespawnUntilLoosingAggro = false) { super.Despawn(deferDespawnUntilLoosingAggro); }
    protected void HCBridgeOnUpdate()
    {
        if (!HCXExpansionBridge.HCGate("PatrolOnUpdate")) { return; }
        if (!HCXExpansionBridge.HCConfig(m_Config, "OnUpdate")) { return; }
        super.OnUpdate();
    }
    protected bool HCBridgeSetupAI(eAIBase ai)
    {
        if (!HCXExpansionBridge.HCEntity(ai, "SetupAI")) { return false; }
        if (!HCXExpansionBridge.HCFactionValid(m_Faction, "SetupAI")) { return false; }
        super.SetupAI(ai);
        return true;
    }
}

// Consolidated original HC hook chain. Earlier overrides become protected
// helpers; the final override invokes them at the original super-call position.
// Death/delete callbacks deliberately retain native corpse bookkeeping.
modded class eAIBase
{
    bool HCXAI_LeaseOwned;
    override void eAI_Recreate()
    {
        if (!HCXExpansionBridge.HCEntity(this, "eAI_Recreate")) { return; }
        if (this.HCXAI_LeaseOwned)
        {
            m_eAI_Recreate = false;
            Print("[HC Expansion AI] refused inventory-cloning recreate for leased actor; native recovery remains owner-approved");
            return;
        }
        super.eAI_Recreate();
    }
    bool HCXAI_Fair()
    {
        return HCXExpansionBridge.HCBaseGetAllowDamage(this) && !m_eAI_EnableFlankingOutsideCombat && m_eAI_UnlimitedReload == 0 && !m_eAI_IsUnlimitedReloadAll && m_eAI_DamageMultiplier == 1 && m_eAI_DamageReceivedMultiplier == 1 && m_eAI_HeadshotResistance == 0;
    }
    protected void HCBridgeAdapterKilled(Object killer)
    {
        super.EEKilled(killer);
        EntityAI source = EntityAI.Cast(killer);
        if (!source) { return; }
        PlayerBase participant = PlayerBase.Cast(source.GetHierarchyRootPlayer());
        if (!participant || !participant.GetIdentity()) { return; }
        string participantId = participant.GetIdentity().GetId();
        // Expansion defers group cleanup to the next frame so EEKilled may still
        // read it: DayZPlayerImplement.c:431-438 (GetGroup at :234).
        HCXAIEncounters encounters = HCXAIEncounters.Active();
        if (encounters) { encounters.RecordKill(HCXExpansionBridge.HCDayZPlayerImplementGetGroup(this), participantId); }
    }

    bool HCBaseRaidUnlock;

    protected bool m_HCCampDeathSent;
    protected void HCBridgeCampKilled(Object killer)
    {
        if (!m_HCCampDeathSent)
        {
            m_HCCampDeathSent = true;
            HCXAICampRoutine.HCObserveKilled(this);
        }
        this.HCBridgeAdapterKilled(killer);
    }

    protected void HCBridgeTacticsHit(TotalDamageResult damageResult, int damageType, EntityAI source, int component, string dmgZone, string ammo, vector modelPos, float speedCoef)
    {
        super.EEHitBy(damageResult, damageType, source, component, dmgZone, ammo, modelPos, speedCoef);
        if (GetGame() && GetGame().IsServer()) { HCXAITactics.OnHit(this, source); }
    }

    protected void HCBridgeTacticsNoise(EntityAI source, vector position, float lifetime, eAINoiseParams params, float strengthMultiplier)
    {
        if (!HCXExpansionBridge.HCEntity(this, "eAI_OnNoiseEvent")) { return; }
        super.eAI_OnNoiseEvent(source, position, lifetime, params, strengthMultiplier);
        if (params && source && params.m_Type == eAINoiseType.BULLETIMPACT) { HCXAITactics.OnImpact(this, position); }
    }

    protected void HCBridgeDefenceHit(TotalDamageResult damageResult, int damageType, EntityAI source, int component, string dmgZone, string ammo, vector modelPos, float speedCoef)
    {
        this.HCBridgeTacticsHit(damageResult, damageType, source, component, dmgZone, ammo, modelPos, speedCoef);
        if (GetGame() && GetGame().IsServer()) { HCXDefence.OnHit(this, source); }
    }
    protected void HCBridgeDefenceKilled(Object killer)
    {
        this.HCBridgeCampKilled(killer);
        if (GetGame() && GetGame().IsServer()) { HCXDefence.OnKill(this, killer); }
    }
    protected void HCBridgeDefenceNoise(EntityAI source, vector position, float lifetime, eAINoiseParams params, float strengthMultiplier)
    {
        if (!HCXExpansionBridge.HCEntity(this, "eAI_OnNoiseEvent")) { return; }
        this.HCBridgeTacticsNoise(source, position, lifetime, params, strengthMultiplier);
        if (params && source && params.m_Type == eAINoiseType.BULLETIMPACT) { HCXDefence.OnImpact(this, source, position); }
    }

    protected PlayerBase m_HCXCeaseTarget;
    protected int m_HCXCeaseUntil;

    bool HCXSignalBlocked(PlayerBase player = null)
    {
        if (!GetGame() || !GetGame().IsServer() || !m_HCXCeaseTarget || GetGame().GetTime() >= m_HCXCeaseUntil) { return false; }
        if (player) { return player == m_HCXCeaseTarget; }
        eAITarget target = GetTarget();
        return target && HCXExpansionBridge.HCTargetGetEntity(target) == m_HCXCeaseTarget;
    }
    bool HCXSignalCease(PlayerBase player)
    {
        if (!player) { return false; }
        m_HCXCeaseTarget = player;
        m_HCXCeaseUntil = GetGame().GetTime() + 2000;
        eAITarget target = GetTarget();
        if (target && HCXExpansionBridge.HCTargetGetEntity(target) == player) { RaiseWeapon(false); }
        return HCXSignalBlocked(player);
    }
    void HCXSignalRelease(PlayerBase player)
    {
        if (player == m_HCXCeaseTarget) { m_HCXCeaseTarget = null; m_HCXCeaseUntil = 0; }
    }
    override bool CanRaiseWeapon()
    {
        if (HCXSignalBlocked()) { return false; }
        return super.CanRaiseWeapon();
    }
    override void RaiseWeapon(bool up = true)
    {
        if (up && HCXSignalBlocked()) { up = false; }
        super.RaiseWeapon(up);
    }
    protected bool HCBridgeSignalCanFire(Weapon_Base weapon)
    {
        if (!HCXExpansionBridge.HCEntity(this, "eAI_CanFire")) { return false; }
        if (HCXSignalBlocked()) { RaiseWeapon(false); return false; }
        return super.eAI_CanFire(weapon);
    }

    int HCXLastGunfire = -1;
    bool HCXLivingRefused;
    override void EEHitBy(TotalDamageResult damageResult, int damageType, EntityAI source, int component, string dmgZone, string ammo, vector modelPos, float speedCoef)
    {
        // Lifecycle: outside READY only the provider's own handling runs.
        if (!HCXExpansionBridge.HCCallbackGate("EEHitBy"))
        {
            super.EEHitBy(damageResult, damageType, source, component, dmgZone, ammo, modelPos, speedCoef);
            return;
        }
        this.HCBridgeDefenceHit(damageResult, damageType, source, component, dmgZone, ammo, modelPos, speedCoef);
        if (!GetGame() || !GetGame().IsServer() || !HCXStance.Owns(this)) { return; }
        PlayerBase attacker = HCXDefence.AttackerOf(source);
        if (HCXDefence.HCHitRecorded(this, attacker) && HCXStance.Relation(this, attacker) >= 0) { HCXEmoteObservation.Remember(this, attacker, HCXFactions.Id(HCXExpansionBridge.HCGroupGetFaction(GetGroup()))); }
    }
    protected void HCBridgeStanceKilled(Object killer)
    {
        if (GetGame() && GetGame().IsServer())
        {
            HCXAISiteDirector raidDirector = HCXAISiteDirector.Active();
            if (raidDirector)
            {
                raidDirector.HCArmDeath(GetGroup(), this);
                raidDirector.RecordDeath(GetGroup());
            }
            // Durable betrayal depends on faction relation, not the defence
            // record super.OnKill creates for the bounded survivor response.
            PlayerBase attacker = HCXDefence.AttackerOf(EntityAI.Cast(killer));
            if (HCXStance.Owns(this) && HCXStance.HCRememberKill(this, attacker)) { HCXEmoteObservation.Remember(this, attacker, HCXFactions.Id(HCXExpansionBridge.HCGroupGetFaction(GetGroup()))); }
        }
        this.HCBridgeDefenceKilled(killer);
    }
    override void eAI_OnNoiseEvent(EntityAI source, vector position, float lifetime, eAINoiseParams params, float strengthMultiplier)
    {
        if (!HCXExpansionBridge.HCEntity(this, "eAI_OnNoiseEvent")) { return; }
        if (!HCXExpansionBridge.HCCallbackGate("NoiseEvent"))
        {
            super.eAI_OnNoiseEvent(source, position, lifetime, params, strengthMultiplier);
            return;
        }
        this.HCBridgeDefenceNoise(source, position, lifetime, params, strengthMultiplier);
        if (!HCXStance.Owns(this) || !params || params.m_Type != eAINoiseType.SHOT || !source) { return; }
        // Observe only the delivered physical noise, bounded by its audible range
        // and our reduced hearing. No player scan, target or position forwarding.
        float audible = Math.Min(80, Math.Min(m_eAI_NoiseInvestigationDistanceLimit, params.m_Strength * strengthMultiplier));
        vector heard = position;
        if (heard == vector.Zero) { heard = source.GetPosition(); }
        if (audible > 0 && vector.Distance(GetPosition(), heard) <= audible) { HCXLastGunfire = GetGame().GetTime(); }
    }

    bool HCWarningActor;
    int HCXLastWarning = -60000;

    // Native 1.30: PlayerBase.c:6924 MessageStatus, :7779 RequestSoundEvent
    // (sound API also used by the preceding #276 adapter).
    bool HCXWarnPlayer(PlayerBase player, int now)
    {
        if (!HCWarningActor || now - HCXLastWarning < HCXWarningShout.COOLDOWN_MS) { return false; }
        if (!HCXWarningShout.AdmitPlayer(player, now)) { return false; }
        HCXLastWarning = now;
        RequestSoundEvent(EPlayerSoundEventID.MELEE_ATTACK_HEAVY);
        player.MessageStatus("Stay back. Lower your weapon and move away.");
        Print("[HollowCountry] Stance warning: shout + text; keep back 40m; runtime=PENDING");
        return true;
    }

    PlayerBase HCXWarningPlayer;
    // Caution grace (HCXCautionObservation): fire stays held for this raised-weapon contact until then.
    PlayerBase HCXCautionPlayer;
    int HCXCautionUntil;
    PlayerBase HCXWarningShotPlayer;
    int HCXWarningSeen;
    int HCXWarningStarted;
    bool HCXWarningPending;

    bool HCXWarningBlocked()
    {
        if (!GetGame() || !GetGame().IsServer() || !HCXWarningPlayer) { return false; }
        if (!HCXStance.Owns(this) || HCXLivingRefused || HCXAIQualification.ProviderProblem() != "") { return false; }
        int age = GetGame().GetTime() - HCXWarningSeen;
        eAITarget target = GetTarget();
        if (age < 0 || age > 2000 || !target || HCXExpansionBridge.HCTargetGetEntity(target) != HCXWarningPlayer || !eAI_HasLOS()) { return false; }
        if (!IsAlive() || IsUnconscious() || IsRestrained() || !HCXWarningPlayer.IsAlive()) { return false; }
        if (HCXStance.Relation(this, HCXWarningPlayer) < 0) { return false; }
        // A raised weapon normally ends the hold; a running caution grace keeps it.
        if (HCXStance.RaisedWeapon(HCXWarningPlayer) && (HCXCautionPlayer != HCXWarningPlayer || GetGame().GetTime() >= HCXCautionUntil)) { return false; }
        float distance = vector.Distance(GetPosition(), HCXWarningPlayer.GetPosition());
        if (distance <= 40 || distance > 80 || HCXDefence.Hostile(this, HCXWarningPlayer, target)) { return false; }
        return true;
    }

    override bool eAI_CanFire(Weapon_Base weapon)
    {
        if (!HCXExpansionBridge.HCEntity(this, "eAI_CanFire")) { return false; }
        if (!HCXExpansionBridge.HCCallbackGate("CanFire"))
        {
            // Outside READY (boot, shutdown) the warning-shot hold still applies: it reads only
            // HC state and ungated engine getters, so it needs no provider call.
            if (HCXWarningBlocked()) { return false; }
            return super.eAI_CanFire(weapon);
        }
        if (HCXWarningBlocked()) { HCReached.Mark("ai.warning_fire_hold"); return false; }
        return this.HCBridgeSignalCanFire(weapon);
    }

    override void eAI_UpdateFSM(float pDt, int simulationPrecision)
    {
        if (!HCXExpansionBridge.HCEntity(this, "eAI_UpdateFSM")) { return; }
        // Perception/navigation/FSM continue; only normal fire at this contact is held.
        super.eAI_UpdateFSM(pDt, simulationPrecision);
        if (!HCXExpansionBridge.HCCallbackGate("UpdateFSM")) { return; }
        if (!HCXWarningBlocked()) { HCXWarningPending = false; return; }
        vector aim = HCXWarningPlayer.GetPosition() + Vector(0, 1.2, 0);
        LookAtPosition(aim);
        AimAtPosition(aim);
        if (CanRaiseWeapon()) { RaiseWeapon(true); }
        if (!HCXWarningPending) { return; }
        if (HCXWarningShotPlayer != HCXWarningPlayer) { HCXWarningPending = false; return; }
        int elapsed = GetGame().GetTime() - HCXWarningStarted;
        if (elapsed < 1500) { return; }
        // Exactly one attempt per admitted warning, including empty/unsafe fallback.
        HCXWarningPending = false;
        Weapon_Base weapon = Weapon_Base.Cast(GetHumanInventory().GetEntityInHands());
        if (!weapon || !this.HCBridgeSignalCanFire(weapon))
        {
            Print("[HollowCountry] Stance warning_shot fallback=no_ready_firearm");
            return;
        }
        HCXWarningShot.Fire(this, HCXWarningPlayer, weapon);
    }

    protected bool m_HCGapBodyDeathSent;
    override void EEKilled(Object killer)
    {
        if (!HCXExpansionBridge.HCCallbackGate("EEKilled"))
        {
            super.EEKilled(killer);
            return;
        }
        this.HCBridgeStanceKilled(killer);
        if (m_HCGapBodyDeathSent || !GetGame() || !GetGame().IsServer()) { return; }
        m_HCGapBodyDeathSent = true;
        if (!HCBodyStories.Get()) { return; } // EnableLeads opt-out
        HCGapBodySceneProducer.HCObserve(this);
    }
}

// HC hook link from HCXStance.c
modded class eAIPlayerTargetInformation
{
    protected ref map<eAIBase, ref HCXWarning> m_HCWarnings = new map<eAIBase, ref HCXWarning>();

    override float CalculateThreat(eAIBase ai = null, eAITargetInformationState state = null)
    {
        if (ai && !HCXExpansionBridge.HCEntity(ai, "CalculateThreat")) { return 0; }
        if (!HCXExpansionBridge.HCCallbackGate("CalculateThreat")) { return super.CalculateThreat(ai, state); }
        PlayerBase player = PlayerBase.Cast(GetEntity());
        if (!HCXStance.Owns(ai) || !player || !player.GetIdentity()) { return super.CalculateThreat(ai, state); }
        if (!GetGame() || !GetGame().IsServer()) { return super.CalculateThreat(ai, state); }
        // Only the selected, perceived contact owns the warning fire interlock.
        eAITarget selected = HCXExpansionBridge.HCBaseGetTarget(ai);
        if (selected && HCXExpansionBridge.HCTargetGetEntity(selected) == player) { ai.HCXWarningPlayer = null; }
        // Hit/kill hooks persist accepted aggression before this evaluation.
        // Surrender refuses cease-fire while a live hit/kill record exists;
        // native perception still gates whether defence can raise threat.
        bool defenceHostile = !ai.HCXLivingRefused && HCXAIQualification.ProviderProblem() == "" && HCXDefence.Hostile(ai, player, state);
        bool observed = state && state.m_LOS && player.IsAlive() && !player.IsUnconscious() && HCXStance.Visible(ai, player);
        if (!ai.HCXLivingRefused && HCXAIQualification.ProviderProblem() == "" && HCXEmoteObservation.Surrender(ai, player, observed))
        {
            state.m_ThreatLevel = 0;
            state.m_ThreatLevelActive = 0;
            state.m_AggressionTimeout = 0;
            HCXWarning surrenderedWarning;
            if (m_HCWarnings.Find(ai, surrenderedWarning))
            {
                surrenderedWarning.Started = -1;
                surrenderedWarning.LastSeen = -1;
                surrenderedWarning.Hostile = false;
            }
            return 0;
        }
        if (defenceHostile)
        {
            float defence = HCXDefencePolicy.Threat(super.CalculateThreat(ai, state), true);
            if (state && defence > state.m_ThreatLevelActive) { state.m_ThreatLevelActive = defence; }
            return defence;
        }
        // Grudges are consulted only after real perception. Persisted identity
        // is never used to discover a player or supply a target position.
        if (observed && !ai.HCXLivingRefused && HCXAIQualification.ProviderProblem() == "" && HCXEmoteObservation.Grudge(ai, player))
        {
            state.m_ThreatLevelActive = HCXDefencePolicy.Threat(state.m_ThreatLevelActive, true);
            return state.m_ThreatLevelActive;
        }
        int nowMs = GetGame().GetTime();
        eAITarget current = HCXExpansionBridge.HCBaseGetTarget(ai);
        bool currentPlayer = current && HCXExpansionBridge.HCTargetGetEntity(current) == player;
        HCXWarning warning;
        if (!m_HCWarnings.Find(ai, warning))
        {
            int expiredIndex = m_HCWarnings.Count() - 1;
            while (expiredIndex >= 0)
            {
                eAIBase priorActor = m_HCWarnings.GetKey(expiredIndex);
                if (!priorActor || !HCXExpansionBridge.HCBaseIsAlive(priorActor) || !HCXExpansionBridge.HCDayZPlayerImplementGetGroup(priorActor)) { m_HCWarnings.Remove(priorActor); }
                expiredIndex--;
            }
            if (m_HCWarnings.Count() >= 8) { return 0; }
            warning = new HCXWarning();
            m_HCWarnings.Insert(ai, warning);
        }
        // Refuse unseen, stale or invalid evidence. Facts are read only after
        // native perception has established LOS and a fresh ray agrees.
        string admissionProblem = HCXAIQualification.ProviderProblem();
        if (!observed || nowMs < 0 || ai.HCXLivingRefused || admissionProblem != "")
        {
            warning.Started = -1;
            warning.LastSeen = -1;
            warning.Hostile = false;
            if (state)
            {
                state.m_ThreatLevel = 0;
                state.m_ThreatLevelActive = 0;
                state.m_AggressionTimeout = 0;
            }
            if (currentPlayer) { HCXExpansionBridge.HCBaseRaiseWeapon(ai, false); }
            // W5 review (a): delivered noise cannot identify this unseen target.
            // Native perception owns discovery; never retain a threat floor to
            // manufacture LOS. Both provider threat caches are cleared above.
            return 0;
        }
        warning.LastWaveSerial = HCXEmoteObservation.Wave(ai, player, observed, warning.LastWaveSerial);
        // A lost observation or server stall starts a new warning, never accrues
        // unseen time toward hostility.
        if (warning.LastSeen < 0 || nowMs < warning.LastSeen || nowMs - warning.LastSeen > 2000)
        {
            warning.Started = -1;
            warning.Hostile = false;
        }
        warning.LastSeen = nowMs;
        float distance = vector.Distance(HCXExpansionBridge.HCBaseGetPosition(ai), player.GetPosition());
        bool raised = HCXStance.RaisedWeapon(player);
        int relation = HCXStance.Relation(ai, player);
        // Raised-weapon caution: the step BEFORE raised-weapon hostility. Observed
        // contacts only (LOS and fresh ray above). A non-zero result is the end of a
        // bounded grace (non-hostile, 40 m < d <= 80 m, weapon raised).
        int graceEnd = HCXCautionObservation.Observe(ai, player, distance, raised, relation, warning.Hostile);
        bool cautionHold = graceEnd > 0;
        // Hostile factions skip the warning sequence. Non-hostile contacts engage
        // at 40m, or on aiming within 80m unless a caution grace is still running.
        if (relation < 0 || distance <= 40 || (raised && distance <= 80 && !cautionHold))
        {
            ai.HCXCautionUntil = 0;
            if (!warning.Hostile) { Print("[HollowCountry] Stance hostile: faction, closing within 40m or raised weapon"); }
            warning.Hostile = true;
            state.m_ThreatLevelActive = 0.6;
            return 0.6;
        }
        if (distance > 80 || (warning.Hostile && !raised))
        {
            if (warning.Started >= 0 || warning.Hostile) { Print("[HollowCountry] Stance de-escalated: weapon lowered or outside caution range"); }
            warning.Started = -1;
            warning.Hostile = false;
            state.m_ThreatLevelActive = 0.1;
            state.m_AggressionTimeout = 0;
            if (currentPlayer) { HCXExpansionBridge.HCBaseRaiseWeapon(ai, false); }
            return 0.1;
        }
        if (!currentPlayer) { state.m_ThreatLevelActive = 0.15; return 0.15; }
        if (cautionHold)
        {
            // Grace: stay non-hostile, face (eAI_UpdateFSM) and shout via the shared
            // per-player admission. Fire stays held by HCXWarningBlocked. No warning
            // shot is queued for a raised weapon: this path never opens fire.
            ai.HCXWarningPlayer = player;
            ai.HCXWarningSeen = nowMs;
            ai.HCXCautionPlayer = player;
            ai.HCXCautionUntil = graceEnd;
            ai.HCXWarningPending = false;
            if (warning.Started < 0 && nowMs >= warning.NextWarning)
            {
                warning.NextWarning = nowMs + HCXWarningShout.COOLDOWN_MS;
                if (ai.HCXWarnPlayer(player, nowMs)) { warning.Started = nowMs; }
            }
            state.m_ThreatLevelActive = 0.2;
            state.m_AggressionTimeout = 0;
            return 0.2;
        }
        ai.HCXWarningPlayer = player;
        ai.HCXWarningSeen = nowMs;
        if (warning.Started < 0 && nowMs >= warning.NextWarning)
        {
            warning.NextWarning = nowMs + HCXWarningShout.COOLDOWN_MS;
            // Both sound and the real-round attempt share one global per-player
            // admission. Refusal still holds ordinary fire between 40 and 80m.
            if (ai.HCXWarnPlayer(player, nowMs))
            {
                warning.Started = nowMs;
                ai.HCXWarningShotPlayer = player;
                ai.HCXWarningStarted = nowMs;
                ai.HCXWarningPending = true;
            }
        }
        state.m_ThreatLevelActive = 0.2;
        state.m_AggressionTimeout = 0;
        return 0.2;
    }
}

// H8: the bridge's lifecycle follows HCServer. SHUTTING_DOWN is set before super.Stop() runs the
// first module OnStop; NOT_READY (and a new epoch) is set before super.Start() starts modules.
// HollowCountryExpansionAI requires CfgPatches HollowCountry, and both use worldScriptModule
// (4_World), so this modded class is applied after the core ones.
modded class HCServer
{
    override void Start()
    {
        HCXExpansionBridge.HCLifecycleStart();
        super.Start();
    }

    override void Tick()
    {
        super.Tick();
        HCXExpansionBridge.HCLifecycleTick();
    }

    override void Stop()
    {
        bool firstStop = HCXExpansionBridge.HCLifecycleStop();
        super.Stop();
        if (HCServer.HCMissionFinishing()) { HCXAIGroupHolds.HCFinish(); }
        if (firstStop) { HCXExpansionBridge.HCLifecycleFinal(); }
    }
}
