// W6 #133. Same-layer extension, no edits to shared core files.
// Native scripts-1.30.164289: 1_Core/proto/EnScript.c:94 Class.Cast, :380,394,407
// Count/Find/Insert; EnConvert.c:30 ToString. <=64 registered modules/request.
// Do not call IsEnabled here: some modules load configuration in that method.
// Enabled means the existing server requested OnStart, not runtime admission.
modded class HCServer
{
    void HCAdminDescribe(HCAdminReply reply)
    {
        if (!m_Started || !m_Registry) { reply.Lines.Insert("[HC Admin] module=Core enabled=0 active=0 budget=n/a"); return; }
        array<ref HCModule> modules = m_Registry.GetModules();
        int work = Math.Min(64, modules.Count());
        for (int moduleIndex = 0; moduleIndex < work; moduleIndex++)
        {
            HCModule module = modules[moduleIndex];
            if (!module) { continue; }
            string enabled = "0";
            if (m_Active.Find(module) >= 0) { enabled = "1"; }
            string name = module.GetName();
            string metrics = "active=n/a budget=n/a";
            HCInfectedModule infected = HCInfectedModule.Cast(module);
            HCEventModule events = HCEventModule.Cast(module);
            HCCampModule camps = HCCampModule.Cast(module);
            HCHoldouts holdouts = HCHoldouts.Cast(module);
            if (infected) { metrics = infected.HCAdminCounts(); }
            else if (events) { metrics = events.HCAdminCounts(); }
            else if (camps) { metrics = camps.HCAdminCounts(); }
            else if (holdouts) { metrics = "sites=" + holdouts.Count().ToString() + " occupied=" + holdouts.Occupied().ToString() + " site_cap=24 occupied_cap=6"; }
            else if (name == "Scenes") { metrics = HCScenesModule.HCAdminCounts(); }
            else if (name == "Escalation") { metrics = "day=" + HCEscalationClock.Day().ToString() + " day_cap=3650 pressure_cap=1"; }
            else if (name == "AdminMap") { metrics = "command_cap=1 snapshot_cap=1 vertex_cap=512 allowlist_cap=32"; }
            else if (name == "InfectedMemory") { metrics = HCInfectedMemory.HCAdminCounts(); }
            else if (name == "Radio") { metrics = HCRadioChatter.Cast(module).HCAdminCounts(); }
            else if (name == "DeadDrops") { metrics = HCDeadDrops.Cast(module).HCAdminCounts(); }
            else if (name == "LootRefresh") { metrics = HCSearchRefreshModule.Cast(module).HCAdminCounts(); }
            else if (name == "Forage") { metrics = HCForageModule.Cast(module).HCAdminCounts(); }
            else if (name == "SettlementDecay") { metrics = HCSettlementDecay.Cast(module).HCAdminCounts(); }
            else if (name == "WeatherDays") { metrics = HCWeatherDaysModule.Cast(module).HCAdminCounts(); }
            else if (name == "BodyStories") { metrics = HCBodyStories.Cast(module).HCAdminCounts(); }
            reply.Lines.Insert("[HC Admin] module=" + name + " enabled=" + enabled + " " + metrics);
        }
    }

    // Only modules the server actually started; never a registry-only entry.
    HCModule HCAdminModuleNamed(string name)
    {
        if (!m_Started || !m_Active) { return null; }
        int work = Math.Min(64, m_Active.Count());
        for (int moduleIndex = 0; moduleIndex < work; moduleIndex++)
        {
            HCModule module = m_Active[moduleIndex];
            if (module && module.GetName() == name) { return module; }
        }
        return null;
    }

    // gate: "" when the command only needs its module, else a fixed reason.
    protected void HCAdminKitLine(HCAdminReply reply, string command, string moduleName, string gate, string input)
    {
        string available = "1";
        string why = "";
        if (gate != "")
        {
            available = "0";
            why = " reason=" + gate;
        }
        else if (!HCAdminModuleNamed(moduleName))
        {
            available = "0";
            why = " reason=module-inactive";
        }
        reply.Lines.Insert("[HC Admin] kit cmd=" + command + " module=" + moduleName + " available=" + available + why + " input=" + input);
    }

    // One line per allowlisted command, in the order of HCAdminModule.HCKnown.
    void HCAdminKit(HCAdminReply reply)
    {
        string sitterGate = "";
        if (!GetGame().ConfigIsExisting("CfgVehicles HC_ZmbM_Sitter")) { sitterGate = "class-missing-HC_ZmbM_Sitter"; }
        HCAdminKitLine(reply, "status", "AdminMap", "", "none");
        HCAdminKitLine(reply, "snapshot", "DebugSnapshot", "", "none; 5 s cooldown");
        HCAdminKitLine(reply, "kit", "AdminMap", "", "none");
        HCAdminKitLine(reply, "list", "AdminMap", "", "none; state near you");
        HCAdminKitLine(reply, "sitter", "Infected", sitterGate, "none; 1 body cap");
        HCAdminKitLine(reply, "clear", "Infected", "", "none; deletes only the admin sitter");
        HCAdminKitLine(reply, "dormant", "Infected", "refused-by-design", "none");
        HCAdminKitLine(reply, "horde", "Infected", "", "none; nearest native cohort within 100 m");
        HCAdminKitLine(reply, "memory", "InfectedMemory", "", "value 0 to 3 simulated loud shots, 0 clears this cell");
        HCAdminKitLine(reply, "scene", "Scenes", "", "none; nearest due scene");
        HCAdminKitLine(reply, "event", "Events", "", "none; nearest reviewed site");
        HCAdminKitLine(reply, "camp", "Camps", "", "none; camp within 100 m");
        HCAdminKitLine(reply, "holdout", "Holdouts", "", "none; holdout within 100 m");
        HCAdminKitLine(reply, "day", "Escalation", "", "value 0 to 3650");
        HCAdminKitLine(reply, "radio", "Radio", "", "none; needs a tuned powered radio");
        HCAdminKitLine(reply, "deaddrop", "DeadDrops", "", "none; drop within 1000 m");
        HCAdminKitLine(reply, "loot", "LootRefresh", "", "none; oldest pending timer");
        HCAdminKitLine(reply, "forage", "Forage", "", "none; months 6 to 11");
        HCAdminKitLine(reply, "decay", "SettlementDecay", "", "none; town within 1000 m");
        HCAdminKitLine(reply, "weather", "WeatherDays", "", "value 0 clear 1 plain 2 calm 3 fog 4 bad");
    }

    // Bounded read-only state near the admin: one line per owner.
    void HCAdminNearby(HCAdminReply reply, vector pos)
    {
        HCInfectedModule infected = HCInfectedModule.Cast(HCAdminModuleNamed("Infected"));
        if (infected) { reply.Lines.Insert("[HC Admin] list infected " + infected.HCAdminNear(pos)); }
        else { reply.Lines.Insert("[HC Admin] list infected unavailable"); }
        reply.Lines.Insert("[HC Admin] list memory " + HCInfectedMemory.HCAdminNear(pos));
        HCDeadDrops drops = HCDeadDrops.Cast(HCAdminModuleNamed("DeadDrops"));
        if (drops) { reply.Lines.Insert("[HC Admin] list deaddrop " + drops.HCAdminNear(pos)); }
        else { reply.Lines.Insert("[HC Admin] list deaddrop unavailable"); }
        HCForageModule forage = HCForageModule.Cast(HCAdminModuleNamed("Forage"));
        if (forage) { reply.Lines.Insert("[HC Admin] list forage " + forage.HCAdminNear(pos)); }
        else { reply.Lines.Insert("[HC Admin] list forage unavailable"); }
        HCSettlementDecay decay = HCSettlementDecay.Cast(HCAdminModuleNamed("SettlementDecay"));
        if (decay) { reply.Lines.Insert("[HC Admin] list decay " + decay.HCAdminNear(pos)); }
        else { reply.Lines.Insert("[HC Admin] list decay unavailable"); }
    }
}
