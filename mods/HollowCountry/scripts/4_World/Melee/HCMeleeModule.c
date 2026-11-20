// Lifecycle only: no gameplay overrides, timers, scans or tick logging.
// Native scripts-1.30.164289: 3_Game/Global/Game.c:1120 IsServer;
// 1_Core/proto/EnSystem.c:397 FileExist; EnDebug.c:96 Print;
// EnScript.c:866,880,902,915 map Get/Find/Set/Contains; EnConvert.c:30 int.ToString.
class HCMeleeModule : HCModule
{
    static HCMeleeModule Instance;
    protected bool m_Started;
    protected bool m_Enabled;
    protected bool m_OptedOut;
    protected ref HCOperationalStatus m_Operational = new HCOperationalStatus;

    override string GetName() { return "Melee"; }
    override bool IsEnabled(HCSettings settings) { return settings && settings.EnableMelee; }

    static bool Active()
    {
        return GetGame() && GetGame().IsServer() && Instance && Instance.m_Started && Instance.m_Enabled && !Instance.m_OptedOut;
    }

    override void OnStart(HCSettings settings)
    {
        if (!GetGame().IsServer()) { super.OnStart(settings); return; }
        super.OnStart(settings);
        Instance = this;
        m_Started = false;
        m_Enabled = IsEnabled(settings);
        HCMeleeConfig.HCLoad("$profile:HollowCountry/melee.json");
        HCMeleeLog.Reset();
        m_OptedOut = FileExist("$profile:HollowCountry/acceptance/melee.disable");
        string result = "disabled";
        if (m_Enabled)
        {
            result = "admitted unverified";
            if (m_OptedOut) { result = "opted out"; }
        }
        string line = "[HollowCountry] V1 admission feature=Melee gate=melee qualified=0 result=" + result;
        Print(line + "; opt out with acceptance/melee.disable; runtime acceptance PENDING");
        // Opt-out is a successful admission decision, with behaviour inactive.
        m_Started = m_Enabled;
        // HCServer captures and emits the single shared [HC Ready] receipt.
    }

    override HCOperationalStatus HCGetOperationalStatus()
    {
        string reason = "defaults_or_scoped_settings_loaded_admitted_unverified";
        if (m_OptedOut) { reason = "operator_opted_out"; }
        HCModuleReadiness.HCDerive(m_Operational, m_Started, "", "", reason);
        return m_Operational;
    }

    override void OnStop()
    {
        if (!GetGame().IsServer()) { super.OnStop(); return; }
        super.OnStop();
        if (m_Started) { HCMeleeLog.Summary(); }
        m_Started = false;
        m_Enabled = false;
        if (Instance == this) { Instance = null; }
    }
}

class HCMeleeLog
{
    protected static ref map<string, int> s_Counts;

    static void Reset()
    {
        s_Counts = new map<string, int>;
        s_Counts.Set("head_execute", 0);
        s_Counts.Set("head_armored", 0);
        s_Counts.Set("head_light", 0);
        s_Counts.Set("cripple", 0);
        s_Counts.Set("arm_weak", 0);
        s_Counts.Set("poise_resist", 0);
        s_Counts.Set("stagger_immunity", 0);
        s_Counts.Set("implausible", 0);
        s_Counts.Set("glance", 0);
        s_Counts.Set("block_cost", 0);
        s_Counts.Set("guard_break", 0);
        s_Counts.Set("counter", 0);
        s_Counts.Set("weight_stamina", 0);
    }

    static void Event(string name, string detail)
    {
        if (!GetGame().IsServer() || !HCMeleeModule.Active() || !s_Counts) { return; }
        int total;
        // Never allocate a key from caller input; the map always has 13 names.
        if (!s_Counts.Find(name, total)) { return; }
        if (total < 2147483647) { total++; }
        s_Counts.Set(name, total);
        if (total <= HCMeleeConfig.HCGet().LogLimit)
        {
            Print("[HC Melee] " + name + " count=" + total.ToString() + " " + detail);
        }
    }

    static void Summary()
    {
        if (!s_Counts) { return; }
        string line = "[HC Melee] summary";
        line = line + " head_execute=" + s_Counts.Get("head_execute").ToString() + " head_armored=" + s_Counts.Get("head_armored").ToString();
        line = line + " head_light=" + s_Counts.Get("head_light").ToString() + " cripple=" + s_Counts.Get("cripple").ToString();
        line = line + " arm_weak=" + s_Counts.Get("arm_weak").ToString() + " poise_resist=" + s_Counts.Get("poise_resist").ToString();
        line = line + " stagger_immunity=" + s_Counts.Get("stagger_immunity").ToString() + " implausible=" + s_Counts.Get("implausible").ToString();
        line = line + " glance=" + s_Counts.Get("glance").ToString() + " block_cost=" + s_Counts.Get("block_cost").ToString();
        line = line + " guard_break=" + s_Counts.Get("guard_break").ToString() + " counter=" + s_Counts.Get("counter").ToString();
        line = line + " weight_stamina=" + s_Counts.Get("weight_stamina").ToString();
        Print(line + " runtime=PENDING");
    }
}

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        Register(new HCMeleeModule);
    }
}
