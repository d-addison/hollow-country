// W6 #133. Same-layer extension, no edits to shared core files.
// Native scripts-1.30.164289: 1_Core/proto/EnScript.c:94 Class.Cast, :380,394,407
// Count/Find/Insert; EnConvert.c:30 ToString; Game.c:914 GetTickTime.
// HC-25 status reads caches only; <=64 transport lines including loss receipt.
modded class HCServer
{
    // Lead binds reply.Authorized only after HCAuthorized(sender), before this
    // handler. HCSend still rechecks the actual sender identity at delivery.
    void HCAdminDescribe(HCAdminReply reply)
    {
        if (!reply || !reply.Authorized) { return; }
        HCOperationalContributors.HCAdminRows(reply, true, GetGame().GetTickTime());
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
        HCAdminKitLine(reply, "dormant", "Infected", "refused-by-design; missing-hook-HCRequestFreshDormant", "none; runtime=PENDING");
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
