// The only place Hollow Country touches the optional base-fortification packs.
// Pack classes are NEVER referenced as script types: everything goes through
// config class names (Object.IsKindOf, Game.ConfigIsExisting) or one script type
// resolved at runtime from a string (String.ToType, Class.IsInherited), so the
// mission compiles and boots with either pack absent. Calls refuse with a reason
// code and print at most one bounded, identity-free line per minute.
//
// Why two kinds of check: IsKindOf walks CONFIG parents only (Object.c:511). The
// barricade pack's built objects have a config parent chain that reaches the
// native base building class, and its kits are config-parented to the pack kit
// base or to the door kit. The kit pack's built objects have NO common config
// parent (each is parented to a plain inventory class); they share only a script
// base, so that one type is resolved from its name once and tested with
// IsInherited. Both parent chains were read from the installed packs' config.
//
// Native scripts-1.30.164289 evidence:
//   Game.c:612 ConfigIsExisting, :1139 ServerConfigGetInt, :1120 IsServer, :1535 GetTime;
//   Object.c:511 IsKindOf, :994 GetHealth(zone,type), :1008 GetMaxHealth, :1034 DecreaseHealth,
//   :1191 GetAllowDamage; EntityAI.c IsPendingDeletion; DamageSystem.c:76
//   GetDamageZoneFromComponentName; BaseBuildingBase.c:358 IsOpened, :882 GetConstruction;
//   ConstructionBase.c:631 GetConstructionParts; ConstructionPart.c IsBuilt/IsBase/
//   IsUtilityPart/GetPartName; EnSystem.c ReadFile/OpenFile; EnString.c IndexOfFrom/Substring/ToType;
//   EnScript.c:23 Class.IsInherited; PlayerBase.c GetHologramServer; PlayerBase.MessageStatus.
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

    // HCBreach results. REFUSED = not a valid target now (damage disabled, no
    // standing part, opened or gone): the caller must not treat it as pressure.
    // NONE = valid contact but no time has elapsed yet (first contact).
    static const int BREACH_REFUSED = -1;
    static const int BREACH_NONE = 0;
    static const int BREACH_DAMAGED = 1;
    static const int BREACH_DESTROYED = 2;

    // Bounds: parts read per barricade, bytes read per pack config, probe period.
    static const int MAX_PARTS = 32;
    static const int MAX_CONFIG_BYTES = 65536;
    static const int CONFIG_PROBE_MS = 30000;
    static const int REFUSAL_WINDOW_MS = 60000;
    static const float MAX_STEP_SECONDS = 5.0;
    // With a caller time budget (the raid window), one standing part may take at most
    // BREACH_BUDGET_SHARE / standingParts of the budget still remaining. The remainder
    // shrinks as parts fall, so n parts use at most 1 - prod(1 - share/j) of the budget
    // (about two thirds for 14 parts at 0.3) and the rest of the window stays for the raid.
    static const float BREACH_BUDGET_SHARE = 0.3;
    // Refused-breach counter bound: barricade+reason keys remembered per boot.
    static const int MAX_REFUSED_KEYS = 64;
    // Script base of the kit pack's built objects, resolved at runtime from this string.
    static const string RAG_BUILT_BASE = "RaG_BB_Base";
    static const string RAG_CONFIG = "$profile:RaG_Core/Configs/RaG_BaseBuilding/RaG_BaseBuilding.json";

    protected static bool s_Probed;
    protected static bool s_BarricadePack;
    protected static bool s_KitPack;
    protected static int s_NextConfigMs;
    protected static bool s_RagAnywhere;
    protected static bool s_ConfigNoted;
    protected static typename s_RagBuiltType;
    protected static int s_NextRefusalMs;
    protected static bool s_Refused;
    protected static ref array<string> s_RefusedKeys;

    // Class-exists probe, once per run. Config presence is fixed for a boot.
    protected static void HCProbe()
    {
        if (s_Probed || !GetGame()) { return; }
        s_Probed = true;
        s_BarricadePack = GetGame().ConfigIsExisting("CfgVehicles BuildingFortficationsCore") && GetGame().ConfigIsExisting("CfgVehicles BF_DoorBarricade");
        s_KitPack = GetGame().ConfigIsExisting("CfgVehicles RaG_BB_BaseKit");
        if (s_KitPack)
        {
            s_RagBuiltType = RAG_BUILT_BASE.ToType();
            if (!s_RagBuiltType) { Print("[HC Fortify] kit pack present but its built-object type did not resolve; kit-pack builds cannot be claim-gated reason=built_type_unresolved runtime=PENDING"); }
        }
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

    // Kits of both packs. The barricade pack's door kits are config-parented to the
    // plain inventory class (the double-door kit to the door kit), not to the pack's
    // kit base, so the door kit is named too. The kit pack's kits all share one base.
    static bool HCIsPackKit(Object kit)
    {
        if (!kit || !HCPackPresent()) { return false; }
        if (s_BarricadePack && (kit.IsKindOf("BuildingFortficationsKit") || kit.IsKindOf("BF_DoorBarricadeKit"))) { return true; }
        return HCIsRagKit(kit);
    }

    static bool HCIsRagKit(Object kit)
    {
        if (!kit || !s_KitPack) { return false; }
        return kit.IsKindOf("RaG_BB_BaseKit");
    }

    // A built barricade core (config parent chain reaches the pack's core class).
    protected static bool HCIsBarricadeCore(BaseBuildingBase building)
    {
        return s_BarricadePack && building.IsKindOf("BuildingFortficationsCore");
    }

    // A built kit-pack object: script base resolved once from its name.
    protected static bool HCIsRagBuilt(Object target)
    {
        if (!s_KitPack || !s_RagBuiltType || !target) { return false; }
        return target.IsInherited(s_RagBuiltType);
    }

    // A built pack object (barricade core or kit-pack object) that further parts can be built on.
    // The native base-building cast filters first so unrelated objects never reach IsKindOf.
    static bool HCIsPackBuilt(Object target)
    {
        if (!target || !HCPackPresent()) { return false; }
        BaseBuildingBase building = BaseBuildingBase.Cast(target);
        if (!building) { return false; }
        return HCIsBarricadeCore(building) || HCIsRagBuilt(building);
    }

    // A barricade that can stand in a doorway (window barricades never block a door).
    protected static bool HCDoorBarricadeClass(BaseBuildingBase building)
    {
        return building.IsKindOf("BF_DoorBarricade") || building.IsKindOf("BF_DoubleDoorBarricade");
    }

    static bool HCIsDoorBarricade(Object obj)
    {
        if (!obj || !s_BarricadePack) { return false; }
        BaseBuildingBase building = BaseBuildingBase.Cast(obj);
        if (!building) { return false; }
        return HCDoorBarricadeClass(building);
    }

    // The barricade currently stands: not opened, has a built non-base part with health left.
    static bool HCStanding(Object obj)
    {
        BaseBuildingBase barricade = BaseBuildingBase.Cast(obj);
        if (!barricade || barricade.IsPendingDeletion() || barricade.IsOpened()) { return false; }
        string zone;
        int standing;
        return HCWeakestZone(barricade, zone, standing) > 0;
    }

    // A standing door barricade (class-checked). Cheap negative: server only, pack present,
    // native cast first, config name check only for base-building objects.
    static bool HCBlocksDoor(Object obj)
    {
        if (!obj || !s_BarricadePack || !HCActive()) { return false; }
        BaseBuildingBase barricade = BaseBuildingBase.Cast(obj);
        if (!barricade || !HCDoorBarricadeClass(barricade)) { return false; }
        return HCStanding(barricade);
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
        if (HCIsRagBuilt(target) && !HCShelterScaleBuilt(target)) { return REASON_SCALE; }
        return HCClaimReason(player, target.GetPosition());
    }

    // Reason a kit deployment is refused before the action starts (server hologram
    // position, player position as the fallback), or "". The client never refuses:
    // the module is server-only, so the server's action condition rejects the start
    // and the client never completes its local placement.
    static string HCDeployReason(PlayerBase player, Object kit)
    {
        if (!HCActive() || !player || !HCIsPackKit(kit)) { return REASON_NONE; }
        vector position = player.GetPosition();
        Hologram hologram = player.GetHologramServer();
        if (hologram && hologram.GetProjectionEntity()) { position = hologram.GetProjectionEntity().GetPosition(); }
        return HCPlacementReason(player, kit, position);
    }

    // Members of the claim covering the position may build; unclaimed ground follows the setting.
    // An actor that cannot hold a claim identity (dead, unconscious, restrained, in a vehicle,
    // no identity) is a claim-service refusal, never a membership verdict.
    protected static string HCClaimReason(PlayerBase player, vector position)
    {
        if (!HCBuildingClaim.HCConstructionAllowed(player, position))
        {
            if (!HCBuildingClaim.HCActor(player)) { return REASON_CLAIM_UNAVAILABLE; }
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

    // Refusal plus the player's status line (start of an action, or its server finish).
    static void HCRefuseTo(PlayerBase player, string reason)
    {
        HCRefuse(reason);
        if (player) { player.MessageStatus(HCReasonText(reason)); }
    }

    // Breach refusals are not player attempts: count one per barricade and reason
    // (bounded), so a barricade that stays refused is not recounted on every visit.
    protected static void HCRefuseBreach(BaseBuildingBase barricade, string reason)
    {
        if (!s_RefusedKeys) { s_RefusedKeys = new array<string>; }
        vector at = barricade.GetPosition();
        int atX = Math.Round(at[0]);
        int atZ = Math.Round(at[2]);
        string key = reason + ":" + atX.ToString() + ":" + atZ.ToString();
        if (s_RefusedKeys.Find(key) >= 0 || s_RefusedKeys.Count() >= MAX_REFUSED_KEYS) { return; }
        s_RefusedKeys.Insert(key);
        HCRefuse(reason);
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
        if (!s_KitPack) { s_RagAnywhere = false; return; }
        string text;
        if (!HCGroupIO.HCReadRaw(RAG_CONFIG, MAX_CONFIG_BYTES, text))
        {
            // Last known value is kept (false before the first good read); say so once.
            if (!s_ConfigNoted)
            {
                s_ConfigNoted = true;
                Print("[HC Fortify] kit pack config unreadable or missing; build-anywhere keeps its last known value (off before the first read) reason=pack_config_unreadable runtime=PENDING");
            }
            return;
        }
        s_RagAnywhere = HCFlagOn(text, "BaseBuildAnywhere") || HCFlagOn(text, "FlagBuildAnywhere");
    }

    static bool HCRagBuildAnywhere()
    {
        HCRefreshRagConfig(false);
        return s_RagAnywhere;
    }

    static void HCProbeConfigs()
    {
        HCProbe();
        s_ConfigNoted = false;
        s_Refused = false;
        s_RefusedKeys = new array<string>;
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

    // Weakest standing part: returns its health (0 when none) and its damage zone,
    // and how many built parts still stand (bounded by MAX_PARTS).
    protected static float HCWeakestZone(BaseBuildingBase barricade, out string zone, out int standing)
    {
        zone = "";
        standing = 0;
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
            standing = standing + 1;
            if (zone == "" || health < weakest)
            {
                zone = candidate;
                weakest = health;
            }
        }
        return weakest;
    }

    // One bounded breach step by one attacker: the weakest standing part loses
    // maxHealth * seconds / window, where window is the configured breach seconds
    // (heavy attackers take half) and, when the caller has a finite time budget
    // (a raid window), no longer than BREACH_BUDGET_SHARE / standing parts of the budget
    // left. Returns BREACH_REFUSED, BREACH_NONE (valid, no time elapsed yet),
    // BREACH_DAMAGED or BREACH_DESTROYED (part ruined, native path).
    static int HCBreach(Object target, float seconds, bool heavy, float budgetSeconds = 0)
    {
        if (!HCActive() || !GetGame().IsServer() || !HCIsDoorBarricade(target)) { return BREACH_REFUSED; }
        BaseBuildingBase barricade = BaseBuildingBase.Cast(target);
        if (!barricade || barricade.IsPendingDeletion() || barricade.IsOpened()) { return BREACH_REFUSED; }
        if (!barricade.GetAllowDamage() || GetGame().ServerConfigGetInt("disableBaseDamage") > 0)
        {
            HCRefuseBreach(barricade, REASON_DAMAGE_OFF);
            return BREACH_REFUSED;
        }
        string zone;
        int standing;
        float health = HCWeakestZone(barricade, zone, standing);
        if (health <= 0 || zone == "")
        {
            HCRefuseBreach(barricade, REASON_NO_PART);
            return BREACH_REFUSED;
        }
        float step = Math.Clamp(seconds, 0, MAX_STEP_SECONDS);
        if (step <= 0) { return BREACH_NONE; }
        float window = HCFortifyModule.BreachSeconds();
        if (heavy) { window = window * 0.5; }
        if (budgetSeconds > 0 && standing > 0)
        {
            float paced = budgetSeconds * BREACH_BUDGET_SHARE / standing;
            if (paced < window) { window = paced; }
        }
        float damage = barricade.GetMaxHealth(zone, "Health") * step / Math.Max(1.0, window);
        if (damage <= 0) { return BREACH_NONE; }
        // The object may be gone once the last part is ruined: decide before the call.
        bool destroyed = health - damage <= 0;
        barricade.DecreaseHealth(zone, "Health", damage);
        if (destroyed)
        {
            HCModuleReadiness.HCUse(HCFortifyModule.MODULE, "barricade_breached");
            return BREACH_DESTROYED;
        }
        return BREACH_DAMAGED;
    }
}
