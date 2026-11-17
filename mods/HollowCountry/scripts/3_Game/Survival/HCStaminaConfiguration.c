// Native reference: scripts-1.30.164289.
// Local serialization observed; native CFG delivery/order remains unqualified.
class HCStaminaProfile
{
    int SchemaVersion = 0;
    string Profile = "";
    bool Experimental = false;
    ref HCStaminaSettings Settings;
}

modded class ITEM_StaminaData
{
    int HCSchemaVersion = 0;
    bool HCEnabled = false;
    bool HCExperimental = false;
    float HCContinuousExertionScale = 1.0;
    float HCRecoveryScale = 1.0;
}

class HCStaminaConfiguration
{
    protected static ref HCStaminaSettings s_Candidate;
    protected static bool s_Active;
    protected static bool s_Server;
    protected static bool s_LoadAttempted;
    protected static bool s_Experimental;
    protected static bool s_Suspended;

    static bool ClientActive()
    {
        return s_Active && !s_Server;
    }

    // Qualification is separate from explicit experimental activation.
    static bool Qualified()
    {
        return false;
    }

    static void Reset(bool active, bool server)
    {
        s_Candidate = null;
        s_Active = active;
        s_Server = server;
        s_LoadAttempted = false;
        s_Experimental = false;
        s_Suspended = false;
    }

    static HCStaminaSettings Copy(HCStaminaSettings settings)
    {
        if (!settings || !settings.Validate())
            return null;
        HCStaminaSettings result = new HCStaminaSettings;
        result.SchemaVersion = settings.SchemaVersion;
        result.Enabled = settings.Enabled;
        result.ContinuousExertionScale = settings.ContinuousExertionScale;
        result.RecoveryScale = settings.RecoveryScale;
        return result;
    }

    static bool ProfileValid(HCStaminaProfile profile)
    {
        if (!profile || profile.SchemaVersion != 1 || !profile.Settings || !profile.Settings.Validate())
            return false;
        if (profile.Profile == "custom")
            return true;
        if (profile.Profile != "vanilla")
            return false;
        return !profile.Settings.Enabled && profile.Settings.ContinuousExertionScale == 1.0 && profile.Settings.RecoveryScale == 1.0;
    }

    protected static bool Stage(HCStaminaSettings settings, bool experimental)
    {
        s_Candidate = null;
        s_Experimental = false;
        if (!s_Active)
            return false;
        s_Candidate = Copy(settings);
        if (!s_Candidate)
            return false;
        s_Experimental = experimental;
        return true;
    }

    static HCStaminaSettings Snapshot()
    {
        if (!s_Active)
            return null;
        return Copy(s_Candidate);
    }

    static bool Enabled()
    {
        return s_Active && !s_Suspended && s_Experimental && s_Candidate && s_Candidate.Enabled;
    }

    static float ExertionScale()
    {
        if (!Enabled())
            return 1.0;
        return s_Candidate.ContinuousExertionScale;
    }

    static float RecoveryScale()
    {
        if (!Enabled())
            return 1.0;
        return s_Candidate.RecoveryScale;
    }

    static bool InstallTrusted(HCStaminaSettings settings)
    {
        if (!Enabled() || !settings || !settings.Validate())
            return false;
        return settings.SchemaVersion == s_Candidate.SchemaVersion && settings.Enabled == s_Candidate.Enabled && settings.ContinuousExertionScale == s_Candidate.ContinuousExertionScale && settings.RecoveryScale == s_Candidate.RecoveryScale;
    }

    static void ConnectionState(int duration)
    {
        if (!s_Active || s_Server)
            return;
        s_Suspended = duration >= 0;
    }

    static bool LoadServer()
    {
        if (!s_Active || !s_Server || s_LoadAttempted)
            return false;
        s_LoadAttempted = true;
        FileHandle handle = OpenFile("$profile:HollowCountry/stamina.json", FileMode.READ);
        if (!handle)
            return false;
        string text;
        int count = ReadFile(handle, text, 16385);
        CloseFile(handle);
        if (count <= 0 || count > 16384)
            return false;
        string error;
        HCStaminaProfile profile = new HCStaminaProfile;
        if (!JsonFileLoader<HCStaminaProfile>.LoadData(text, profile, error) || !ProfileValid(profile))
            return false;
        CfgGameplayJson data = CfgGameplayHandler.m_Data;
        if (!data || !data.PlayerData || !data.PlayerData.StaminaData)
            return false;
        HCStaminaSettings settings = Copy(profile.Settings);
        ITEM_StaminaData item = data.PlayerData.StaminaData;
        item.HCSchemaVersion = settings.SchemaVersion;
        item.HCEnabled = settings.Enabled;
        item.HCExperimental = profile.Experimental;
        item.HCContinuousExertionScale = settings.ContinuousExertionScale;
        item.HCRecoveryScale = settings.RecoveryScale;
        return Stage(settings, profile.Experimental);
    }

    static void ServerLoaded()
    {
        Reset(true, true);
        CfgGameplayJson data = CfgGameplayHandler.m_Data;
        if (data && data.PlayerData && data.PlayerData.StaminaData)
        {
            ITEM_StaminaData item = data.PlayerData.StaminaData;
            item.HCSchemaVersion = 0;
            item.HCEnabled = false;
            item.HCExperimental = false;
            item.HCContinuousExertionScale = 1.0;
            item.HCRecoveryScale = 1.0;
        }
        LoadServer();
    }

    static bool NativeReceipt(CfgGameplayJson data, CfgGameplayJson previous)
    {
        s_Candidate = null;
        s_Experimental = false;
        if (!s_Active || s_Server || !data || data == previous || !data.PlayerData || !data.PlayerData.StaminaData)
            return false;
        ITEM_StaminaData item = data.PlayerData.StaminaData;
        HCStaminaSettings settings = new HCStaminaSettings;
        settings.SchemaVersion = item.HCSchemaVersion;
        settings.Enabled = item.HCEnabled;
        settings.ContinuousExertionScale = item.HCContinuousExertionScale;
        settings.RecoveryScale = item.HCRecoveryScale;
        return Stage(settings, item.HCExperimental);
    }

    static void SessionEvent(EventType eventTypeId, bool server)
    {
        if (eventTypeId == WorldCleaupEventTypeID)
        {
            Reset(false, false);
            return;
        }
        if (server)
            return;
        if (eventTypeId == MPSessionStartEventTypeID)
            Reset(true, false);
        if (eventTypeId == MPSessionEndEventTypeID || eventTypeId == MPSessionFailEventTypeID)
            Reset(false, false);
    }
}

modded class DayZGame
{
    override void OnGameplayDataHandlerLoad()
    {
        super.OnGameplayDataHandlerLoad();
        if (IsServer())
            HCStaminaConfiguration.ServerLoaded();
    }

    override void OnEvent(EventType eventTypeId, Param params)
    {
        HCStaminaConfiguration.SessionEvent(eventTypeId, IsServer());
        super.OnEvent(eventTypeId, params);
    }

    override void OnMPConnectionLostEvent(int duration)
    {
        HCStaminaConfiguration.ConnectionState(duration);
        super.OnMPConnectionLostEvent(duration);
    }

    override void OnRPC(PlayerIdentity sender, Object target, int rpc_type, ParamsReadContext ctx)
    {
        if (rpc_type != ERPCs.RPC_CFG_GAMEPLAY_SYNC)
        {
            super.OnRPC(sender, target, rpc_type, ctx);
            return;
        }
        if (IsServer() || sender || target || !ctx || !HCStaminaConfiguration.ClientActive())
            return;
        CfgGameplayJson previous = CfgGameplayHandler.m_Data;
        super.OnRPC(sender, target, rpc_type, ctx);
        HCStaminaConfiguration.NativeReceipt(CfgGameplayHandler.m_Data, previous);
    }
}
