// The only place Hollow Country touches the optional base-fortification packs.
// Pack classes are NEVER referenced as script types: everything goes through
// config class names (Object.IsKindOf, Game.ConfigIsExisting), so the mission
// compiles and boots with either pack absent. Calls refuse with a reason code
// and print at most one bounded, identity-free line per minute.
//
// Native scripts-1.30.164289 evidence:
//   Game.c:612 ConfigIsExisting, :1139 ServerConfigGetInt, :1120 IsServer, :1535 GetTime;
//   Object.c:511 IsKindOf, :994 GetHealth(zone,type), :1008 GetMaxHealth, :1034 DecreaseHealth,
//   :1191 GetAllowDamage; EntityAI.c IsPendingDeletion; DamageSystem.c:76
//   GetDamageZoneFromComponentName; BaseBuildingBase.c:358 IsOpened, :882 GetConstruction;
//   ConstructionBase.c:631 GetConstructionParts; ConstructionPart.c IsBuilt/IsBase/
//   IsUtilityPart/GetPartName; EnSystem.c ReadFile/OpenFile; EnString.c IndexOfFrom/Substring.
// Damage goes through DecreaseHealth, so a destroyed part follows the native
// ruined-part path (Construction.DestroyPartServer). No instant destroy, no
// immunity, and the server's disableBaseDamage is never overridden.
class HCFortifyBridge
{
    static const string REASON_NONE = "";
    static const string REASON_SCALE = "rag_scale_excluded";
    static const string REASON_ANYWHERE = "rag_build_anywhere_on";
    static const string REASON_NOT_MEMBER = "claim_not_member";
    static const string REASON_CLAIM_UNAVAILABLE = "claim_unavailable";
    static const string REASON_UNCLAIMED = "unclaimed_building";
    static const string REASON_DAMAGE_OFF = "damage_disabled";
    static const string REASON_NO_PART = "no_breakable_part";

    // Bounds: parts read per barricade, bytes read per pack config, probe period.
    static const int MAX_PARTS = 32;
    static const int MAX_CONFIG_BYTES = 65536;
    static const int CONFIG_PROBE_MS = 30000;
    static const int REFUSAL_WINDOW_MS = 60000;
    static const float MAX_STEP_SECONDS = 5.0;
    static const string RAG_CONFIG = "$profile:RaG_Core/Configs/RaG_BaseBuilding/RaG_BaseBuilding.json";

    protected static bool s_Probed;
    protected static bool s_BarricadePack;
    protected static bool s_KitPack;
    protected static int s_NextConfigMs;
    protected static bool s_RagAnywhere;
    protected static bool s_RagNoDamage;
    protected static int s_NextRefusalMs;
    protected static bool s_Refused;

    // Class-exists probe, once per run. Config presence is fixed for a boot.
    protected static void HCProbe()
    {
        if (s_Probed || !GetGame()) { return; }
        s_Probed = true;
        s_BarricadePack = GetGame().ConfigIsExisting("CfgVehicles BuildingFortficationsCore") && GetGame().ConfigIsExisting("CfgVehicles BF_DoorBarricade");
        s_KitPack = GetGame().ConfigIsExisting("CfgVehicles RaG_BB_BaseKit");
    }

    static bool HCBarricadePackPresent() { HCProbe(); return s_BarricadePack; }
    static bool HCKitPackPresent() { HCProbe(); return s_KitPack; }
    static bool HCPackPresent() { HCProbe(); return s_BarricadePack || s_KitPack; }

    // True only while the Fortify module is started (server, setting on, a pack present).
    static bool HCActive() { return HCFortifyModule.Active(); }

    // ---- classification (config names only) -------------------------------

    // Shelter-scale kits that may be placed. Everything else the kit pack adds is refused.
    static bool HCShelterScaleKit(Object kit)
    {
        if (!kit) { return false; }
        if (kit.IsKindOf("RaG_BB_Single_DoorKit")) { return true; }
        if (kit.IsKindOf("RaG_BB_Window_SmallKit")) { return true; }
        if (kit.IsKindOf("RaG_BB_Low_WallKit")) { return true; }
        if (kit.IsKindOf("RaG_BB_WoodStorageKit")) { return true; }
        return kit.IsKindOf("RaG_BB_Floor_HatchKit");
    }

    static bool HCShelterScaleBuilt(Object built)
    {
        if (!built) { return false; }
        if (built.IsKindOf("RaG_BB_Single_Door")) { return true; }
        if (built.IsKindOf("RaG_BB_Window_Small")) { return true; }
        if (built.IsKindOf("RaG_BB_Low_Wall")) { return true; }
        if (built.IsKindOf("RaG_BB_WoodStorage")) { return true; }
        return built.IsKindOf("RaG_BB_Floor_Hatch");
    }

    static bool HCIsPackKit(Object kit)
    {
        if (!kit || !HCPackPresent()) { return false; }
        if (s_BarricadePack && kit.IsKindOf("BuildingFortficationsKit")) { return true; }
        if (!s_KitPack) { return false; }
        return kit.IsKindOf("RaG_BB_BaseKit") || kit.IsKindOf("RaG_BB_Pefab_BaseKit");
    }

    static bool HCIsRagKit(Object kit)
    {
        if (!kit || !s_KitPack) { return false; }
        return kit.IsKindOf("RaG_BB_BaseKit") || kit.IsKindOf("RaG_BB_Pefab_BaseKit");
    }

    // A built pack object (barricade core or kit-pack base) that further parts can be built on.
    static bool HCIsPackBuilt(Object target)
    {
        if (!target || !HCPackPresent()) { return false; }
        if (s_BarricadePack && target.IsKindOf("BuildingFortficationsCore")) { return true; }
        return s_KitPack && target.IsKindOf("RaG_BB_Base");
    }

    // A barricade that can stand in a doorway (window barricades never block a door).
    static bool HCIsDoorBarricade(Object obj)
    {
        if (!obj || !s_BarricadePack) { return false; }
        return obj.IsKindOf("BF_DoorBarricade") || obj.IsKindOf("BF_DoubleDoorBarricade");
    }

    // The barricade currently stands: not opened, has a built non-base part with health left.
    static bool HCBlocksDoor(Object obj)
    {
        if (!HCActive() || !HCIsDoorBarricade(obj)) { return false; }
        BaseBuildingBase barricade = BaseBuildingBase.Cast(obj);
        if (!barricade || barricade.IsPendingDeletion() || barricade.IsOpened()) { return false; }
        string zone;
        return HCWeakestZone(barricade, zone) > 0;
    }

    // ---- claim ACL ---------------------------------------------------------

    // Reason a kit placement is refused, or "" when allowed (also "" for non-pack kits).
    static string HCPlacementReason(PlayerBase player, Object kit, vector position)
    {
        if (!HCActive() || !HCIsPackKit(kit)) { return REASON_NONE; }
        if (HCIsRagKit(kit))
        {
            if (!HCShelterScaleKit(kit)) { return REASON_SCALE; }
            if (HCRagBuildAnywhere()) { return REASON_ANYWHERE; }
        }
        return HCClaimReason(player, position);
    }

    // Reason further construction on a pack object is refused, or "".
    static string HCBuildReason(PlayerBase player, Object target)
    {
        if (!HCActive() || !HCIsPackBuilt(target)) { return REASON_NONE; }
        if (s_KitPack && target.IsKindOf("RaG_BB_Base") && !HCShelterScaleBuilt(target)) { return REASON_SCALE; }
        return HCClaimReason(player, target.GetPosition());
    }

    // Members of the claim covering the position may build; unclaimed ground follows the setting.
    protected static string HCClaimReason(PlayerBase player, vector position)
    {
        if (!HCBuildingClaim.HCConstructionAllowed(player, position))
        {
            if (HCBuildingClaim.HCClaimCoversAt(position)) { return REASON_NOT_MEMBER; }
            return REASON_CLAIM_UNAVAILABLE;
        }
        if (!HCFortifyModule.UnclaimedAllowed() && !HCBuildingClaim.HCClaimCoversAt(position)) { return REASON_UNCLAIMED; }
        return REASON_NONE;
    }

    // Bounded refusal: one identity-free line per window, counted every time.
    static void HCRefuse(string reason)
    {
        HCModuleReadiness.HCUse(HCFortifyModule.MODULE, "fortify_refused");
        int nowMs;
        if (GetGame()) { nowMs = GetGame().GetTime(); }
        if (s_Refused && nowMs < s_NextRefusalMs) { return; }
        s_Refused = true;
        s_NextRefusalMs = nowMs + REFUSAL_WINDOW_MS;
        Print("[HC Fortify] refused reason=" + reason + " runtime=PENDING");
    }

    // Player-facing text for a reason code (no identities, no class names).
    static string HCReasonText(string reason)
    {
        if (reason == REASON_SCALE) { return "Refused: this kit is larger than a shelter-scale build."; }
        if (reason == REASON_ANYWHERE) { return "Refused: the server allows building anywhere for this kit pack, so shelter kits are disabled."; }
        if (reason == REASON_NOT_MEMBER) { return "Refused: this building is claimed by another group."; }
        if (reason == REASON_CLAIM_UNAVAILABLE) { return "Refused: claim access is unavailable right now."; }
        if (reason == REASON_UNCLAIMED) { return "Refused: only claimed buildings can be fortified on this server."; }
        return "Refused: fortification not allowed here.";
    }

    static void HCPlaced()
    {
        HCModuleReadiness.HCUse(HCFortifyModule.MODULE, "fortify_placed");
    }

    // ---- kit pack config (read only, never written) -------------------------

    protected static void HCRefreshRagConfig(bool force)
    {
        int nowMs;
        if (GetGame()) { nowMs = GetGame().GetTime(); }
        if (!force && nowMs < s_NextConfigMs) { return; }
        s_NextConfigMs = nowMs + CONFIG_PROBE_MS;
        s_RagAnywhere = false;
        s_RagNoDamage = false;
        if (!s_KitPack) { return; }
        string text;
        if (!HCGroupIO.HCReadRaw(RAG_CONFIG, MAX_CONFIG_BYTES, text)) { return; }
        s_RagAnywhere = HCFlagOn(text, "BaseBuildAnywhere") || HCFlagOn(text, "FlagBuildAnywhere");
        s_RagNoDamage = HCFlagOn(text, "DisableAllDamage");
    }

    static bool HCRagBuildAnywhere()
    {
        HCRefreshRagConfig(false);
        return s_RagAnywhere;
    }

    static void HCProbeConfigs()
    {
        HCProbe();
        HCRefreshRagConfig(true);
        if (s_RagAnywhere) { Print("[HC Fortify] kit pack build-anywhere is on; shelter kits will be refused until it is off runtime=PENDING"); }
    }

    // True for "Key": true / 1, tolerant of whitespace. False when absent.
    protected static bool HCFlagOn(string text, string key)
    {
        int at = text.IndexOf("\"" + key + "\"");
        if (at < 0) { return false; }
        int cursor = at + key.Length() + 2;
        int stop = Math.Min(text.Length(), cursor + 16);
        while (cursor < stop)
        {
            string glyph = text.Substring(cursor, 1);
            cursor++;
            if (glyph == ":" || glyph == " " || glyph == "\t" || glyph == "\r" || glyph == "\n") { continue; }
            return glyph == "1" || glyph == "t" || glyph == "T";
        }
        return false;
    }

    // ---- breach damage ------------------------------------------------------

    // Weakest standing part: returns its health (0 when none) and its damage zone.
    protected static float HCWeakestZone(BaseBuildingBase barricade, out string zone)
    {
        zone = "";
        Construction construction = barricade.GetConstruction();
        if (!construction) { return 0; }
        map<string, ref ConstructionPart> parts = construction.GetConstructionParts();
        if (!parts) { return 0; }
        float weakest = 0;
        int count = Math.Min(parts.Count(), MAX_PARTS);
        for (int index = 0; index < count; index++)
        {
            ConstructionPart part = parts.Get(parts.GetKey(index));
            if (!part || !part.IsBuilt() || part.IsBase() || part.IsUtilityPart()) { continue; }
            string candidate;
            if (!DamageSystem.GetDamageZoneFromComponentName(barricade, part.GetPartName(), candidate)) { continue; }
            float health = barricade.GetHealth(candidate, "Health");
            if (health <= 0) { continue; }
            if (zone == "" || health < weakest)
            {
                zone = candidate;
                weakest = health;
            }
        }
        return weakest;
    }

    // One bounded breach step by one attacker: the weakest standing part loses
    // maxHealth * seconds / breachSeconds (heavy attackers take half the time).
    // Returns 0 refused/none, 1 damaged, 2 part destroyed this step (native path).
    static int HCBreach(Object target, float seconds, bool heavy)
    {
        if (!HCActive() || !GetGame().IsServer() || !HCIsDoorBarricade(target)) { return 0; }
        BaseBuildingBase barricade = BaseBuildingBase.Cast(target);
        if (!barricade || barricade.IsPendingDeletion() || barricade.IsOpened()) { return 0; }
        if (!barricade.GetAllowDamage() || GetGame().ServerConfigGetInt("disableBaseDamage") > 0)
        {
            HCRefuse(REASON_DAMAGE_OFF);
            return 0;
        }
        string zone;
        float health = HCWeakestZone(barricade, zone);
        if (health <= 0 || zone == "")
        {
            HCRefuse(REASON_NO_PART);
            return 0;
        }
        float step = Math.Clamp(seconds, 0, MAX_STEP_SECONDS);
        if (step <= 0) { return 0; }
        float window = HCFortifyModule.BreachSeconds();
        if (heavy) { window = window * 0.5; }
        float damage = barricade.GetMaxHealth(zone, "Health") * step / Math.Max(1.0, window);
        if (damage <= 0) { return 0; }
        // The object may be gone once the last part is ruined: decide before the call.
        bool destroyed = health - damage <= 0;
        barricade.DecreaseHealth(zone, "Health", damage);
        if (destroyed)
        {
            HCModuleReadiness.HCUse(HCFortifyModule.MODULE, "barricade_breached");
            return 2;
        }
        return 1;
    }
}
