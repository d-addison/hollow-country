// Core lifecycle seam for the bounded ecology observation service (#34).
// Calls only the reviewed HCEcologyRuntime Start/Tick/Stop surface. When the
// service will not run, the pre-start registration cohort is released.
class HCEcologyRuntimeModule : HCModule
{
    protected ref HCEcologyRuntimeSettings m_Settings;
    protected bool m_Started;

    override string GetName() { return "Ecology"; }

    override bool IsEnabled(HCSettings settings)
    {
        if (!GetGame() || !GetGame().IsServer()) { return false; }
        m_Settings = HCEcologyRuntimeIO.Settings();
        if (!m_Settings)
        {
            Print("[HC Ecology] settings unreadable or invalid; disabled");
            HCEcologyRuntime.CloseCollection();
            return false;
        }
        if (!m_Settings.Enabled)
        {
            Print("[HC Ecology] explicitly disabled by operator");
            HCEcologyRuntime.CloseCollection();
            return false;
        }
        return true;
    }

    override void OnStart(HCSettings settings)
    {
        m_Started = HCEcologyRuntime.Start(m_Settings, GetGame().GetWorldName(), Session());
        if (!m_Started)
        {
            Print("[HC Ecology] admission rejected; observation service not running");
            HCEcologyRuntime.CloseCollection();
        }
    }

    override void OnTick(float deltaTime)
    {
        HCEcologyRuntime.Tick(GetGame().GetTime());
    }

    override void OnStop()
    {
        HCEcologyRuntime.Stop();
        m_Started = false;
    }

    string Session()
    {
        int year;
        int month;
        int day;
        int hour;
        int minute;
        int second;
        GetYearMonthDayUTC(year, month, day);
        GetHourMinuteSecondUTC(hour, minute, second);
        return SessionToken(year, month, day, hour, minute, second, Math.RandomIntInclusive(0, 999999));
    }

    // Token alphabet only (HCEcologyRuntimeRules.Token): digits, 's' and '-'.
    static string SessionToken(int year, int month, int day, int hour, int minute, int second, int nonce)
    {
        string date = year.ToStringLen(4) + month.ToStringLen(2) + day.ToStringLen(2);
        string time = hour.ToStringLen(2) + minute.ToStringLen(2) + second.ToStringLen(2);
        return "s" + date + "-" + time + "-" + nonce.ToStringLen(6);
    }
}

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        Register(new HCEcologyRuntimeModule);
    }
}
