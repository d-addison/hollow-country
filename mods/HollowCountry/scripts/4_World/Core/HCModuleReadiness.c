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
    protected static bool s_UseScheduled;
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
        s_UseSlots.Insert(module + "/" + feature, slot);
        HCUseLine(slot);
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
    }

    static void HCSummary()
    {
        int slot = 0;
        while (slot < s_UseCounts.Count())
        {
            HCUseLine(slot);
            slot++;
        }
    }

    static void HCUseBegin()
    {
        if (s_UseScheduled && GetGame())
        {
            GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).Remove(HCSummary);
        }
        s_UseScheduled = false;
        s_UseSlots.Clear();
        s_UseModules.Clear();
        s_UseFeatures.Clear();
        s_UseCounts.Clear();
        s_UseFixtureCounts.Clear();
        s_UseModules.Reserve(HC_USE_CAP);
        s_UseFeatures.Reserve(HC_USE_CAP);
        s_UseCounts.Reserve(HC_USE_CAP);
        s_UseFixtureCounts.Reserve(HC_USE_CAP);
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

    // Inventory is registered even when admission fails: readiness is not use.
    // Client features are also declared on the server, so a missing client RPT
    // cannot silently remove them from the release audit.
    static void HCRegisterModuleUses(string module)
    {
        if (module == "AdminMap")
        {
            HCRegisterUse("AdminMap", "window_open");
            HCRegisterUse("AdminMap", "request");
            return;
        }
        if (module == "Cellars")
        {
            HCRegisterUse("Cellars", "visual_applied");
            return;
        }
        if (module == "Grade")
        {
            HCRegisterUse("Grade", "grade_applied");
            return;
        }
        if (module == "Lighting")
        {
            HCRegisterUse("Lighting", "blend_applied");
            return;
        }
        if (module == "OptionalPacks")
        {
            HCRegisterUse("OptionalPacks", "animal_seen");
            HCRegisterUse("OptionalPacks", "bicycle_seen");
            return;
        }
        if (module == "SignsOfLife")
        {
            HCRegisterUse("SignsOfLife", "light_observed");
            HCRegisterUse("SignsOfLife", "smoke_observed");
            HCRegisterUse("SignsOfLife", "flies_created");
            return;
        }
        if (module == "Camps")
        {
            HCRegisterUse("Camps", "camp_recognised");
            return;
        }
        if (module == "CampRespawn")
        {
            HCRegisterUse("CampRespawn", "respawn_reserved");
            return;
        }
        if (module == "Crafting")
        {
            HCRegisterUse("Crafting", "recipe_completed");
            return;
        }
        if (module == "DebugSnapshot")
        {
            HCRegisterUse("DebugSnapshot", "snapshot_saved");
            return;
        }
        if (module == "Ecology")
        {
            HCRegisterUse("Ecology", "animal_observed");
            return;
        }
        if (module == "Events")
        {
            HCRegisterUse("Events", "police_supply_bound");
            return;
        }
        if (module == "Forage")
        {
            HCRegisterUse("Forage", "item_spawned");
            HCRegisterUse("Forage", "item_picked");
            return;
        }
        if (module == "Groups")
        {
            HCRegisterUse("Groups", "group_mutated");
            HCRegisterUse("Groups", "menu_open");
            return;
        }
        if (module == "MapPins")
        {
            HCRegisterUse("MapPins", "pins_published");
            return;
        }
        if (module == "TeamPing")
        {
            HCRegisterUse("TeamPing", "ping_delivered");
            return;
        }
        if (module == "HordeMigration")
        {
            HCRegisterUse("HordeMigration", "route_advanced");
            return;
        }
        if (module == "InfectedMemory")
        {
            HCRegisterUse("InfectedMemory", "heat_recorded");
            return;
        }
        if (module == "Infected")
        {
            HCRegisterUse("Infected", "actor_bound");
            return;
        }
        if (module == "CellarSampler")
        {
            HCRegisterUse("CellarSampler", "class_measured");
            return;
        }
        if (module == "Interiors")
        {
            HCRegisterUse("Interiors", "prop_placed");
            HCRegisterUse("Interiors", "search_completed");
            return;
        }
        if (module == "BodyStories")
        {
            HCRegisterUse("BodyStories", "body_observed");
            return;
        }
        if (module == "Leads")
        {
            HCRegisterUse("Leads", "lead_received");
            return;
        }
        if (module == "Notes")
        {
            HCRegisterUse("Notes", "note_read");
            return;
        }
        if (module == "Radio")
        {
            HCRegisterUse("Radio", "report_delivered");
            return;
        }
        if (module == "SearchBinding")
        {
            HCRegisterUse("SearchBinding", "supply_bound");
            return;
        }
        if (module == "LootRefresh")
        {
            HCRegisterUse("LootRefresh", "timer_rearmed");
            return;
        }
        if (module == "Melee")
        {
            HCRegisterUse("Melee", "hit_processed");
            return;
        }
        if (module == "Polish")
        {
            HCRegisterUse("Polish", "hint_shown");
            HCRegisterUse("Polish", "sound_played");
            return;
        }
        if (module == "Progression")
        {
            HCRegisterUse("Progression", "familiarity_gained");
            return;
        }
        if (module == "Scenes")
        {
            HCRegisterUse("Scenes", "scene_placed");
            return;
        }
        if (module == "SurvivalAlignment")
        {
            HCRegisterUse("SurvivalAlignment", "stamina_applied");
            HCRegisterUse("SurvivalAlignment", "stamina_hud_shown");
            return;
        }
        if (module == "TapedHelmetMounts")
        {
            HCRegisterUse("TapedHelmetMounts", "light_mounted");
            return;
        }
        if (module == "TapedLight")
        {
            HCRegisterUse("TapedLight", "light_mounted");
            return;
        }
        if (module == "TapedPackMounts")
        {
            HCRegisterUse("TapedPackMounts", "light_mounted");
            return;
        }
        if (module == "Shelters")
        {
            HCRegisterUse("Shelters", "shelter_placed");
            return;
        }
        if (module == "VehicleFlip")
        {
            HCRegisterUse("VehicleFlip", "impulse_applied");
            return;
        }
        if (module == "WreckSalvage")
        {
            HCRegisterUse("WreckSalvage", "part_created");
            return;
        }
        if (module == "WeatherDays")
        {
            HCRegisterUse("WeatherDays", "profile_applied");
            return;
        }
        if (module == "AITrade")
        {
            HCRegisterUse("AITrade", "trade_completed");
            return;
        }
        if (module == "DeadDrops")
        {
            HCRegisterUse("DeadDrops", "cache_bound");
            return;
        }
        if (module == "Escalation")
        {
            HCRegisterUse("Escalation", "state_advanced");
            return;
        }
        if (module == "FactionConflict")
        {
            HCRegisterUse("FactionConflict", "outcome_recorded");
            return;
        }
        if (module == "Holdouts")
        {
            HCRegisterUse("Holdouts", "camp_committed");
            return;
        }
        if (module == "Pickers")
        {
            HCRegisterUse("Pickers", "trip_started");
            return;
        }
        if (module == "SettlementDecay")
        {
            HCRegisterUse("SettlementDecay", "prop_placed");
            return;
        }
        if (module == "WorldSaves")
        {
            HCRegisterUse("WorldSaves", "stage_written");
            return;
        }
        if (module == "WorldIncidents")
        {
            HCRegisterUse("WorldIncidents", "incident_recorded");
            return;
        }
        if (module == "Materializer")
        {
            HCRegisterUse("Materializer", "actors_materialized");
            return;
        }
        if (module == "World")
        {
            HCRegisterUse("World", "row_simulated");
            return;
        }
        if (module == "InfectedDoors")
        {
            HCRegisterUse("InfectedDoors", "door_action");
            return;
        }
        if (module == "InfectedLOD")
        {
            HCRegisterUse("InfectedLOD", "tier_changed");
            HCRegisterUse("InfectedLOD", "herd_materialized");
            return;
        }
        if (module == "InfectedReach")
        {
            HCRegisterUse("InfectedReach", "strike_landed");
            HCRegisterUse("InfectedReach", "vehicle_battered");
            HCRegisterUse("InfectedReach", "vault_started");
            return;
        }
        if (module == "InfectedVariety")
        {
            HCRegisterUse("InfectedVariety", "actor_woken");
            return;
        }
        if (module == "ClientUI")
        {
            HCRegisterUse("ClientUI", "map_open");
            HCRegisterUse("ClientUI", "inventory_open");
            HCRegisterUse("ClientUI", "earplugs_applied");
            return;
        }
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
        if (s_Reported.Find(name) >= 0 || s_Reported.Count() >= 64) { return; }
        if (enabled) { HCRegisterModuleUses(name); }
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
