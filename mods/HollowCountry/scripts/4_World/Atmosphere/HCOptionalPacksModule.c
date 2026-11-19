// LC-T105/T106/T204; EXP-D1 subscription-only FALLBACK. Never spawns entities.
// Native snapshot scripts-1.30.164289:
// 3_Game/Global/Game.c:612 ConfigIsExisting(string path), :1120 IsServer().
// 3_Game/gameplay.c:636 GetGame() returns the installed DayZGame singleton.
// 1_Core/proto/EnDebug.c:96 Print(void var).
// Config keys inspected in the operator's installed README / events.xml:
// Ambient Animals Pack Animal_Otter; DayZ-Bicycle Old_Bike. No pack source ships.
// Gate verdicts are diagnostic only; EnableAmbientLife controls startup.
class HCOptionalPacksModule : HCModule
{
    protected bool m_Started;
    protected ref HCOperationalStatus m_Operational = new HCOperationalStatus;

    override string GetName() { return "OptionalPacks"; }

    // Wave 16: cached readiness from the live started flag (never hard-coded).
    override HCOperationalStatus HCGetOperationalStatus()
    {
        HCModuleReadiness.HCDerive(m_Operational, m_Started, "", "", "optional_pack_config_probe_logged");
        return m_Operational;
    }

    override bool IsEnabled(HCSettings settings)
    {
        return settings && settings.EnableAmbientLife;
    }

    override void OnStart(HCSettings settings)
    {
        if (m_Started || !IsEnabled(settings) || !GetGame() || !GetGame().IsServer()) return;
        m_Started = true;
        Print(HCV2Admission.Line("AmbientAnimals", true, "EXP-A4", HCV2Gates.Qualified("EXP-A4")));
        Print(HCV2Admission.Line("Bicycles", true, "EXP-T3", HCV2Gates.Qualified("EXP-T3")));
        string animalsLoaded = "0";
        string bicyclesLoaded = "0";
        if (GetGame().ConfigIsExisting("CfgVehicles Animal_Otter")) animalsLoaded = "1";
        if (GetGame().ConfigIsExisting("CfgVehicles Old_Bike")) bicyclesLoaded = "1";
        Print("[HollowCountry] V2 optional pack AmbientAnimals loaded=" + animalsLoaded);
        Print("[HollowCountry] V2 optional pack Bicycles loaded=" + bicyclesLoaded);
    }

    override void OnStop() { m_Started = false; }
}

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        Register(new HCOptionalPacksModule);
    }
}
