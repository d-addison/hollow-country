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
        if (!HCEntity(value, "HCDayZPlayerImplementSetGroup", true)) { return; }
        if (!group) { HCRefuse("HCDayZPlayerImplementSetGroup", "GROUP_NULL"); return; }
        value.SetGroup(group, autoDeleteFormerGroupIfEmpty, groupMemberIndex);
    }

    static void HCSitePatrolDelete(HCXAISitePatrol value)
    {
        if (!value) { HCRefuse("HCSitePatrolDelete", "RECEIVER_NULL"); return; }
        value.Delete();
    }

    static void HCSitePatrolDespawn(HCXAISitePatrol value, bool deferDespawnUntilLoosingAggro = false)
    {
        if (!value) { HCRefuse("HCSitePatrolDespawn", "RECEIVER_NULL"); return; }
        value.Despawn(deferDespawnUntilLoosingAggro);
    }

    static void HCSitePatrolSpawn(HCXAISitePatrol value)
    {
        if (!value) { HCRefuse("HCSitePatrolSpawn", "RECEIVER_NULL"); return; }
        if (!HCConfig(value.m_Config, "HCSitePatrolSpawn")) { return; }
        value.Spawn();
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

    static void HCGroupAddWaypoint(eAIGroup value, vector pos)
    {
        if (!value) { HCRefuse("HCGroupAddWaypoint", "GROUP_NULL"); return; }
        value.AddWaypoint(pos);
    }

    static void HCGroupClearWaypoints(eAIGroup value)
    {
        if (!value) { HCRefuse("HCGroupClearWaypoints", "GROUP_NULL"); return; }
        value.ClearWaypoints();
    }

    static int HCGroupCount(eAIGroup value)
    {
        if (!value) { HCRefuse("HCGroupCount", "GROUP_NULL"); return 0; }
        return value.Count();
    }

    static eAIGroup HCGroupCreateGroup(eAIFaction faction)
    {
        if (!HCFactionValid(faction, "HCGroupCreateGroup")) { return null; }
        return eAIGroup.CreateGroup(faction);
    }

    static int HCGroupDeceasedCount(eAIGroup value)
    {
        if (!value) { HCRefuse("HCGroupDeceasedCount", "GROUP_NULL"); return 0; }
        return value.DeceasedCount();
    }

    static void HCGroupDelete(eAIGroup value)
    {
        if (!value) { HCRefuse("HCGroupDelete", "GROUP_NULL"); return; }
        value.Delete();
    }

    static eAIFaction HCGroupGetFaction(eAIGroup value)
    {
        if (!value) { HCRefuse("HCGroupGetFaction", "GROUP_NULL"); return null; }
        return value.GetFaction();
    }

    static eAIFormation HCGroupGetFormation(eAIGroup value)
    {
        if (!value) { HCRefuse("HCGroupGetFormation", "GROUP_NULL"); return null; }
        return value.GetFormation();
    }

    static DayZPlayerImplement HCGroupGetFormationLeader(eAIGroup value)
    {
        if (!value) { HCRefuse("HCGroupGetFormationLeader", "GROUP_NULL"); return null; }
        return value.GetFormationLeader();
    }

    static eAIGroupFormationState HCGroupGetFormationState(eAIGroup value)
    {
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
        if (!value) { HCRefuse("HCGroupGetIndex", "GROUP_NULL"); return -1; }
        if (!HCEntity(player, "HCGroupGetIndex", false)) { return -1; }
        return value.GetIndex(player);
    }

    static DayZPlayerImplement HCGroupGetMember(eAIGroup value, int i)
    {
        if (!value) { HCRefuse("HCGroupGetMember", "GROUP_NULL"); return null; }
        if (i < 0 || i >= value.Count()) { HCRefuse("HCGroupGetMember", "MEMBER_INDEX"); return null; }
        return value.GetMember(i);
    }

    static string HCGroupGetName(eAIGroup value)
    {
        if (!value) { HCRefuse("HCGroupGetName", "GROUP_NULL"); return ""; }
        return value.GetName();
    }

    static eAIWaypointBehavior HCGroupGetWaypointBehaviour(eAIGroup value)
    {
        if (!value) { HCRefuse("HCGroupGetWaypointBehaviour", "GROUP_NULL"); return 0; }
        return value.GetWaypointBehaviour();
    }

    static array<vector> HCGroupGetWaypoints(eAIGroup value)
    {
        if (!value) { HCRefuse("HCGroupGetWaypoints", "GROUP_NULL"); return null; }
        return value.GetWaypoints();
    }

    static bool HCGroupIsInCombat(eAIGroup value)
    {
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
        if (!value) { HCRefuse("HCGroupSetFormation", "GROUP_NULL"); return; }
        if (!f) { HCRefuse("HCGroupSetFormation", "FORMATION_NULL"); return; }
        value.SetFormation(f);
    }

    static void HCGroupSetWaypointBehaviour(eAIGroup value, eAIWaypointBehavior bhv)
    {
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
}

// Provider superclass dispatch is kept here to avoid virtual recursion.
class HCXExpansionPatrol : eAIDynamicPatrol
{
    protected bool HCBridgeCanSpawn()
    {
        if (!HCXExpansionBridge.HCConfig(m_Config, "CanSpawn")) { return false; }
        return super.CanSpawn();
    }
    protected void HCBridgeSpawn()
    {
        if (!HCXExpansionBridge.HCConfig(m_Config, "Spawn")) { return; }
        super.Spawn();
    }
    protected void HCBridgeSpawnAI_Deferred(int i)
    {
        if (!HCXExpansionBridge.HCConfig(m_Config, "SpawnAI_Deferred")) { return; }
        if (!m_Group || !m_Formation) { HCXExpansionBridge.HCRefuse("SpawnAI_Deferred", "GROUP_OR_FORMATION_NULL"); return; }
        super.SpawnAI_Deferred(i);
    }
    protected void HCBridgeDespawn(bool deferDespawnUntilLoosingAggro = false) { super.Despawn(deferDespawnUntilLoosingAggro); }
    protected void HCBridgeOnUpdate()
    {
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
            if (raidDirector) { raidDirector.RecordDeath(GetGroup()); }
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
        if (HCXStance.Relation(this, HCXWarningPlayer) < 0 || HCXStance.RaisedWeapon(HCXWarningPlayer)) { return false; }
        float distance = vector.Distance(GetPosition(), HCXWarningPlayer.GetPosition());
        if (distance <= 40 || distance > 80 || HCXDefence.Hostile(this, HCXWarningPlayer, target)) { return false; }
        return true;
    }

    override bool eAI_CanFire(Weapon_Base weapon)
    {
        if (!HCXExpansionBridge.HCEntity(this, "eAI_CanFire")) { return false; }
        if (HCXWarningBlocked()) { HCReached.Mark("ai.warning_fire_hold"); return false; }
        return this.HCBridgeSignalCanFire(weapon);
    }

    override void eAI_UpdateFSM(float pDt, int simulationPrecision)
    {
        if (!HCXExpansionBridge.HCEntity(this, "eAI_UpdateFSM")) { return; }
        // Perception/navigation/FSM continue; only normal fire at this contact is held.
        super.eAI_UpdateFSM(pDt, simulationPrecision);
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
        // Hostile factions skip the warning sequence. Non-hostile contacts engage
        // at 40m or on aiming, with no elapsed-time escalation at a safe distance.
        if (relation < 0 || distance <= 40 || (raised && distance <= 80))
        {
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
