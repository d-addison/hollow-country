// Lifecycle, readiness and counters for the fortification-pack bridge. The
// module is enabled only when the setting is on AND a pack's config is loaded,
// so a server without the packs reports enabled=false and expects no activity.
// Native: Game.c:612 ConfigIsExisting, :1120 IsServer; EnDebug.c:96 Print.
// Counters (HCModuleReadiness.HCUse): fortify_placed, fortify_refused, barricade_breached.
class HCFortifyModule : HCModule
{
    static const string MODULE = "Fortify";
    protected static HCFortifyModule s_Instance;
    protected bool m_Started;
    protected bool m_UnclaimedAllowed = true;
    protected int m_BreachSeconds = 90;
    protected ref HCOperationalStatus m_Operational = new HCOperationalStatus;

    override string GetName() { return MODULE; }

    override bool IsEnabled(HCSettings settings)
    {
        if (!settings || !settings.EnableFortify) { return false; }
        return HCFortifyBridge.HCPackPresent();
    }

    // Registered only for an enabled module, so absent packs add no expectation.
    override void RegisterUses()
    {
        HCModuleReadiness.HCRegisterUse(MODULE, "fortify_placed");
        HCModuleReadiness.HCRegisterUse(MODULE, "fortify_refused");
        HCModuleReadiness.HCRegisterUse(MODULE, "barricade_breached");
    }

    static bool Active()
    {
        return s_Instance && s_Instance.m_Started && GetGame() && GetGame().IsServer();
    }

    static bool UnclaimedAllowed()
    {
        if (!s_Instance) { return true; }
        return s_Instance.m_UnclaimedAllowed;
    }

    static float BreachSeconds()
    {
        if (!s_Instance) { return 90.0; }
        return s_Instance.m_BreachSeconds;
    }

    override void OnStart(HCSettings settings)
    {
        super.OnStart(settings);
        if (!GetGame() || !GetGame().IsServer() || !IsEnabled(settings)) { return; }
        m_UnclaimedAllowed = settings.FortifyUnclaimedBuild;
        m_BreachSeconds = settings.FortifyBreachSeconds;
        HCFortifyBridge.HCProbeConfigs();
        s_Instance = this;
        m_Started = true;
        string barricades = "0";
        string kits = "0";
        if (HCFortifyBridge.HCBarricadePackPresent()) { barricades = "1"; }
        if (HCFortifyBridge.HCKitPackPresent()) { kits = "1"; }
        Print("[HC Fortify] started barricade_pack=" + barricades + " kit_pack=" + kits + " breach_seconds=" + m_BreachSeconds.ToString() + " runtime=PENDING");
    }

    override HCOperationalStatus HCGetOperationalStatus()
    {
        HCModuleReadiness.HCDerive(m_Operational, m_Started, "", "", "pack_bridge_active");
        return m_Operational;
    }

    override void OnStop()
    {
        super.OnStop();
        m_Started = false;
        if (s_Instance == this) { s_Instance = null; }
    }
}

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        Register(new HCFortifyModule);
    }
}

// One extra stamp per watched door: the last time a barricade in the doorway
// took infected pressure (HCInfectedDoors.Visit). Never persisted.
modded class HCInfectedDoorPressure
{
    float m_BarricadeAt = -1;
}
