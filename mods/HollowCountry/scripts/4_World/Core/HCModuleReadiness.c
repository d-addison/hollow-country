// Wave 16 (w32-status): one shared, allocation-free derivation of a module's cached operational status
// from state the module already owns (a started flag, an optional refusal string, an optional runtime
// fault string). The readiness policy never reads config/files/engine or hard-codes ready:
// a module that did not reach its started state can never publish ready. Policy only; runtime=PENDING.
// Receipt logging also uses the verified HCReached token API, array Find/Insert
// (EnScript.c) and Print (EnDebug.c). HCDerive remains allocation-free.
class HCModuleReadiness
{
    protected static ref array<string> s_Reported = new array<string>();
    protected static ref array<bool> s_BootReady = new array<bool>();
    protected static ref array<bool> s_LatePrinted = new array<bool>();

    // Bounded mission counters. Registration builds the slot cache; repeated
    // actions use a hash lookup instead of scanning the inventory. Counts saturate.
    // Native EnScript.c map Find/Insert/Clear; keys cannot contain slash (HCReached.Token).
    protected static ref map<string, int> s_UseSlots = new map<string, int>();
    protected static ref array<string> s_UseModules = new array<string>();
    protected static ref array<string> s_UseFeatures = new array<string>();
    protected static ref array<int> s_UseCounts = new array<int>();
    protected static ref array<int> s_UseFixtureCounts = new array<int>();
    protected static ref array<int> s_UsePrintedCounts = new array<int>();
    protected static ref map<string, string> s_LegacyUses = new map<string, string>();
    protected static bool s_LegacyUsesBuilt;
    protected static bool s_UseScheduled;
    protected static bool s_UseRegistrationPrinted;
    static const int HC_USE_CAP = 256;

    static int HCRegisterUse(string module, string feature)
    {
        int slot = HCUseSlot(module, feature);
        if (slot >= 0) { return slot; }
        if (s_UseCounts.Count() >= HC_USE_CAP) { return -1; }
        // Literal tokens only; never retain an identity, object name or position.
        if (module == "" || feature == "" || module.Length() > 64 || feature.Length() > 64) { return -1; }
        if (HCReached.Token(module) != module || HCReached.Token(feature) != feature) { return -1; }
        slot = s_UseCounts.Count();
        s_UseModules.Insert(module);
        s_UseFeatures.Insert(feature);
        s_UseCounts.Insert(0);
        s_UseFixtureCounts.Insert(0);
        s_UsePrintedCounts.Insert(0);
        s_UseSlots.Insert(module + "/" + feature, slot);
        if (!s_UseScheduled && GetGame())
        {
            s_UseScheduled = true;
            int minutes = HCPerfConfig.HCGet().UseSummaryMinutes;
            GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(HCSummary, minutes * 60000, true);
        }
        return slot;
    }

    protected static int HCUseSlot(string module, string feature)
    {
        int slot;
        if (s_UseSlots.Find(module + "/" + feature, slot)) { return slot; }
        return -1;
    }

    static void HCUse(string module, string feature)
    {
        int slot = HCUseSlot(module, feature);
        if (slot < 0) { slot = HCRegisterUse(module, feature); }
        if (slot < 0) { return; }
        int count = s_UseCounts[slot];
        if (count < 2147483647) { s_UseCounts[slot] = count + 1; }
        if (count == 0) { HCUseLine(slot); }
    }

    // Real owner outcomes only; selection never calls this API.
    static void HCUseFixture(string module, string feature)
    {
        int slot = HCUseSlot(module, feature);
        if (slot < 0) { slot = HCRegisterUse(module, feature); }
        if (slot < 0) { return; }
        int count = s_UseCounts[slot];
        int fixtures = s_UseFixtureCounts[slot];
        if (count < 2147483647)
        {
            s_UseCounts[slot] = count + 1;
            s_UseFixtureCounts[slot] = fixtures + 1;
        }
        if (count == 0 || fixtures == 0) { HCUseLine(slot); }
    }

    protected static void HCUseLine(int slot)
    {
        string line = "[HC Use] module=" + s_UseModules[slot] + " feature=" + s_UseFeatures[slot];
        line = line + " count=" + s_UseCounts[slot].ToString();
        if (s_UseFixtureCounts[slot] > 0) { line += " fixture=" + s_UseFixtureCounts[slot].ToString(); }
        Print("" + line);
        s_UsePrintedCounts[slot] = s_UseCounts[slot];
    }

    // R3 probes may call this same checkpoint; counts remain cumulative so the
    // existing activity parser can compare checkpoints without summing deltas.
    static void HCSummary()
    {
        HCUseRegistrationSummary();
        int slot = 0;
        while (slot < s_UseCounts.Count())
        {
            if (s_UseCounts[slot] > s_UsePrintedCounts[slot]) { HCUseLine(slot); }
            slot++;
        }
    }

    static void HCUseRegistrationSummary()
    {
        if (s_UseRegistrationPrinted) { return; }
        s_UseRegistrationPrinted = true;
        // The current activity parser reserves [HC Use] for per-feature lines.
        // Keep the digest outside that prefix until its owner admits digests.
        Print("[HC UseRegistry] registered=" + s_UseCounts.Count().ToString());
    }

    static void HCUseBegin()
    {
        if (s_UseScheduled && GetGame())
        {
            GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).Remove(HCSummary);
        }
        s_UseScheduled = false;
        s_UseRegistrationPrinted = false;
        s_Reported.Clear();
        s_BootReady.Clear();
        s_LatePrinted.Clear();
        s_UseSlots.Clear();
        s_UseModules.Clear();
        s_UseFeatures.Clear();
        s_UseCounts.Clear();
        s_UseFixtureCounts.Clear();
        s_UsePrintedCounts.Clear();
        s_UseModules.Reserve(HC_USE_CAP);
        s_UseFeatures.Reserve(HC_USE_CAP);
        s_UseCounts.Reserve(HC_USE_CAP);
        s_UseFixtureCounts.Reserve(HC_USE_CAP);
        s_UsePrintedCounts.Reserve(HC_USE_CAP);
    }

    static void HCUseShutdown()
    {
        HCSummary();
        if (s_UseScheduled && GetGame())
        {
            GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).Remove(HCSummary);
        }
        s_UseScheduled = false;
    }

    // Compatibility inventory for Wave 2 adoption of HCModule.RegisterUses.
    // Keep this public seam: client lifecycle and optional addons override it.
    // Inventory is registered even when admission fails: readiness is not use.
    // Client features are also declared on the server, so a missing client RPT
    // cannot silently remove them from the release audit.
    static void HCRegisterModuleUses(string module)
    {
        if (!s_LegacyUsesBuilt)
        {
            s_LegacyUsesBuilt = true;
            s_LegacyUses.Insert("AdminMap", "window_open,request");
            s_LegacyUses.Insert("Cellars", "visual_applied");
            s_LegacyUses.Insert("Grade", "grade_applied");
            s_LegacyUses.Insert("Lighting", "blend_applied");
            s_LegacyUses.Insert("OptionalPacks", "animal_seen,bicycle_seen");
            s_LegacyUses.Insert("SignsOfLife", "light_observed,smoke_observed,flies_created");
            s_LegacyUses.Insert("Camps", "camp_recognised");
            s_LegacyUses.Insert("CampRespawn", "respawn_reserved");
            s_LegacyUses.Insert("Crafting", "recipe_completed");
            s_LegacyUses.Insert("DebugSnapshot", "snapshot_saved");
            s_LegacyUses.Insert("Ecology", "animal_observed");
            s_LegacyUses.Insert("Events", "police_supply_bound");
            s_LegacyUses.Insert("Forage", "item_spawned,item_picked");
            s_LegacyUses.Insert("Groups", "group_mutated,menu_open");
            s_LegacyUses.Insert("MapPins", "pins_published");
            s_LegacyUses.Insert("TeamPing", "ping_delivered");
            s_LegacyUses.Insert("HordeMigration", "route_advanced");
            s_LegacyUses.Insert("InfectedMemory", "heat_recorded");
            s_LegacyUses.Insert("Infected", "actor_bound");
            s_LegacyUses.Insert("CellarSampler", "class_measured");
            s_LegacyUses.Insert("Interiors", "prop_placed,search_completed");
            s_LegacyUses.Insert("BodyStories", "body_observed");
            s_LegacyUses.Insert("Leads", "lead_received");
            s_LegacyUses.Insert("Notes", "note_read");
            s_LegacyUses.Insert("Radio", "report_delivered");
            s_LegacyUses.Insert("SearchBinding", "supply_bound");
            s_LegacyUses.Insert("LootRefresh", "timer_rearmed");
            s_LegacyUses.Insert("Melee", "hit_processed");
            s_LegacyUses.Insert("Polish", "hint_shown,sound_played");
            s_LegacyUses.Insert("Progression", "familiarity_gained");
            s_LegacyUses.Insert("Scenes", "scene_placed");
            s_LegacyUses.Insert("SurvivalAlignment", "stamina_applied,stamina_hud_shown");
            s_LegacyUses.Insert("TapedHelmetMounts", "light_mounted");
            s_LegacyUses.Insert("TapedLight", "light_mounted");
            s_LegacyUses.Insert("TapedPackMounts", "light_mounted");
            s_LegacyUses.Insert("Shelters", "shelter_placed");
            s_LegacyUses.Insert("VehicleFlip", "impulse_applied");
            s_LegacyUses.Insert("WreckSalvage", "part_created");
            s_LegacyUses.Insert("WeatherDays", "profile_applied");
            s_LegacyUses.Insert("AITrade", "trade_completed");
            s_LegacyUses.Insert("DeadDrops", "cache_bound");
            s_LegacyUses.Insert("Escalation", "state_advanced");
            s_LegacyUses.Insert("FactionConflict", "outcome_recorded");
            s_LegacyUses.Insert("Holdouts", "camp_committed");
            s_LegacyUses.Insert("Pickers", "trip_started");
            s_LegacyUses.Insert("SettlementDecay", "prop_placed");
            s_LegacyUses.Insert("WorldSaves", "stage_written");
            s_LegacyUses.Insert("WorldIncidents", "incident_recorded");
            s_LegacyUses.Insert("Materializer", "actors_materialized");
            s_LegacyUses.Insert("World", "row_simulated");
            s_LegacyUses.Insert("InfectedDoors", "door_action");
            s_LegacyUses.Insert("InfectedLOD", "tier_changed,herd_materialized");
            s_LegacyUses.Insert("InfectedReach", "strike_landed,vehicle_battered,vault_started");
            s_LegacyUses.Insert("InfectedVariety", "actor_woken");
            s_LegacyUses.Insert("ClientUI", "map_open,inventory_open,earplugs_applied");
        }
        string features;
        if (!s_LegacyUses.Find(module, features)) { return; }
        array<string> declared = new array<string>();
        features.Split(",", declared);
        foreach (string feature : declared) { HCRegisterUse(module, feature); }
    }

    static void HCPrintLate(string name, bool enabled, bool started, HCOperationalStatus status)
    {
        int index = s_Reported.Find(name);
        if (index < 0 || s_BootReady[index] || s_LatePrinted[index]) { return; }
        if (!HCModuleReadiness.HCReady(enabled, started, status)) { return; }
        s_LatePrinted[index] = true;
        HCModuleReadiness.HCLine(name, enabled, started, status);
    }

    static bool HCReady(bool enabled, bool started, HCOperationalStatus status)
    {
        return enabled && started && status && status.HCState() == "ready";
    }

    static void HCPrint(string name, bool enabled, bool started, HCOperationalStatus status)
    {
        if (s_Reported.Find(name) >= 0 || s_Reported.Count() >= HC_MAX_MODULES) { return; }
        s_Reported.Insert(name);
        s_BootReady.Insert(HCModuleReadiness.HCReady(enabled, started, status));
        s_LatePrinted.Insert(false);
        HCModuleReadiness.HCLine(name, enabled, started, status);
    }

    protected static void HCLine(string name, bool enabled, bool started, HCOperationalStatus status)
    {
        string enabledWord = "false";
        string readyWord = "false";
        string reason = "owner_state_unreported";
        if (enabled) { enabledWord = "true"; }
        if (HCModuleReadiness.HCReady(enabled, started, status)) { readyWord = "true"; }
        if (status) { reason = status.HCReason(); }
        string line = "[HC Ready] module=" + HCReached.Token(name) + " enabled=" + enabledWord;
        line = line + " ready=" + readyWord + " reason=" + HCReached.Token(reason) + " runtime=PENDING";
        Print("" + line);
    }

    static const string HC_OFF_REASON = "not_started_or_disabled";

    // started + runtimeFault  -> degraded (a real fault of a running module, never a missing verdict)
    // started                  -> ready (readyReason names what loaded)
    // refusal                  -> refused (the module tried to start and said why it could not)
    // otherwise                -> off (disabled by setting, or OnStart returned before starting)
    static void HCDerive(HCOperationalStatus status, bool started, string refusal, string runtimeFault, string readyReason)
    {
        if (!status) { return; }
        if (started && runtimeFault != "")
        {
            status.HCPublish("degraded", runtimeFault);
            return;
        }
        if (started)
        {
            status.HCPublish("ready", readyReason);
            return;
        }
        if (refusal != "")
        {
            status.HCPublish("refused", refusal);
            return;
        }
        status.HCPublish("off", HCModuleReadiness.HC_OFF_REASON);
    }
}

// Keep the optional telemetry control in the existing performance DTO/loader.
// Missing or invalid values retain the ten-minute default on either peer.
modded class HCPerfConfig
{
    int UseSummaryMinutes = 10;

    override void HCApply(HCPerfConfig decoded, string text)
    {
        super.HCApply(decoded, text);
        if (HCJsonFields.Has(text, "UseSummaryMinutes") && decoded.UseSummaryMinutes >= 1 && decoded.UseSummaryMinutes <= 60)
        {
            UseSummaryMinutes = decoded.UseSummaryMinutes;
        }
    }
}
