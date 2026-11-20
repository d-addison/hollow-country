// Native reference: scripts-1.30.164289, 3_Game/DayZGame.c:1267
// OnGameplayDataHandlerLoad, :3141-3161 OnRPC and native CfgGameplay dispatch.
// 1_Core/proto/EnDebug.c:96 Print (startup transport diagnostic).
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
    float HCWeightPenaltyScale = 1.0;
}

class HCStaminaConfiguration
{
    // Narrow request only; the response uses native RPC_CFG_GAMEPLAY_SYNC.
    // 4854011 is reserved here; clients never submit stamina settings.
    static const int RPC_REQUEST = 4854011;
    protected static const int REQUEST_COOLDOWN_MS = 10000;
    protected static ref map<int, int> s_RequestTimes;
    protected static ref HCStaminaSettings s_Candidate;
    protected static ref HCStaminaSettings s_Pending;
    protected static bool s_PendingExperimental;
    protected static bool s_ReceiptLogged;
    protected static bool s_Requested;
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
        s_Pending = null;
        s_PendingExperimental = false;
        s_ReceiptLogged = false;
        s_Requested = false;
        s_RequestTimes = null;
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
        result.WeightPenaltyScale = settings.WeightPenaltyScale;
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

    static HCStaminaProfile DefaultProfile()
    {
        HCStaminaProfile profile = new HCStaminaProfile;
        profile.SchemaVersion = 1;
        profile.Profile = "custom";
        profile.Experimental = true;
        profile.Settings = new HCStaminaSettings;
        profile.Settings.Enabled = true;
        profile.Settings.ContinuousExertionScale = 0.25;
        profile.Settings.RecoveryScale = 2.5;
        return profile;
    }

    protected static bool EnsureProfile()
    {
        string root = "$profile:HollowCountry";
        string path = root + "/stamina.json";
        if (FileExist(path))
            return true;
        if (!FileExist(root) && !MakeDirectory(root))
        {
            Print("[HollowCountry] Stamina blocked: cannot create profile directory");
            return false;
        }
        HCStaminaProfile profile = DefaultProfile();
        string error;
        if (!JsonFileLoader<HCStaminaProfile>.SaveFile(path, profile, error))
        {
            Print("[HollowCountry] Stamina blocked: cannot save default profile: " + error);
            return false;
        }
        Print("[HollowCountry] Created enabled stamina profile: 25% continuous drain, 250% recovery, 50% weight penalty; native qualification pending");
        return true;
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

    static float WeightPenaltyScale()
    {
        if (!Enabled())
            return 1.0;
        return s_Candidate.WeightPenaltyScale;
    }

    static bool InstallTrusted(HCStaminaSettings settings)
    {
        if (!Enabled() || !settings || !settings.Validate())
            return false;
        return settings.SchemaVersion == s_Candidate.SchemaVersion && settings.Enabled == s_Candidate.Enabled && settings.ContinuousExertionScale == s_Candidate.ContinuousExertionScale && settings.RecoveryScale == s_Candidate.RecoveryScale && settings.WeightPenaltyScale == s_Candidate.WeightPenaltyScale;
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
        if (!EnsureProfile())
            return false;
        FileHandle handle = OpenFile("$profile:HollowCountry/stamina.json", FileMode.READ);
        if (!handle)
        {
            Print("[HollowCountry] Stamina blocked: cannot read profile");
            return false;
        }
        string text;
        int count = ReadFile(handle, text, 16385);
        CloseFile(handle);
        if (count <= 0 || count > 16384)
        {
            Print("[HollowCountry] Stamina blocked: profile must contain 1..16384 bytes; file preserved");
            return false;
        }
        string error;
        HCStaminaProfile profile = new HCStaminaProfile;
        if (!JsonFileLoader<HCStaminaProfile>.LoadData(text, profile, error))
        {
            Print("[HollowCountry] Stamina blocked: invalid profile; file preserved: " + error);
            return false;
        }
        // Schema-one profiles predate this field. Zero is also an explicit
        // operator choice, so only absence restores the constructor default.
        if (profile && profile.Settings && !HCJsonFields.Check(text, "WeightPenaltyScale", 2, false))
        {
            HCStaminaSettings legacyDefaults = new HCStaminaSettings;
            profile.Settings.WeightPenaltyScale = legacyDefaults.WeightPenaltyScale;
        }
        if (!ProfileValid(profile))
        {
            Print("[HollowCountry] Stamina blocked: invalid profile; file preserved: " + error);
            return false;
        }
        // Owner decision 2026-11-18: stamina doubled again. A profile still holding
        // the previous shipped default (0.5 drain / 1.25 recovery) is upgraded once;
        // any other operator value is preserved.
        if (profile.Profile == "custom" && profile.Settings.ContinuousExertionScale == 0.5 && profile.Settings.RecoveryScale == 1.25)
        {
            profile.Settings.ContinuousExertionScale = 0.25;
            profile.Settings.RecoveryScale = 2.5;
            string path = "$profile:HollowCountry/stamina.json";
            if (!JsonFileLoader<HCStaminaProfile>.SaveFile(path, profile, error))
            {
                Print("[HollowCountry] Stamina profile upgrade not saved; using new default this session: " + error);
            }
            else
            {
                Print("[HollowCountry] Stamina profile upgraded from previous default: 25% continuous drain, 250% recovery");
            }
        }
        CfgGameplayJson data = CfgGameplayHandler.m_Data;
        if (!data || !data.PlayerData || !data.PlayerData.StaminaData)
        {
            Print("[HollowCountry] Stamina blocked: native gameplay configuration unavailable");
            return false;
        }
        HCStaminaSettings settings = Copy(profile.Settings);
        ITEM_StaminaData item = data.PlayerData.StaminaData;
        item.HCSchemaVersion = settings.SchemaVersion;
        item.HCEnabled = settings.Enabled;
        item.HCExperimental = profile.Experimental;
        item.HCContinuousExertionScale = settings.ContinuousExertionScale;
        item.HCRecoveryScale = settings.RecoveryScale;
        item.HCWeightPenaltyScale = settings.WeightPenaltyScale;
        return Stage(settings, profile.Experimental);
    }

    static void ServerLoaded()
    {
        Reset(true, true);
        Print("[HollowCountry] Stamina CFG sync vanilla passthrough active; HC receipt gated; runtime acceptance PENDING");
        CfgGameplayJson data = CfgGameplayHandler.m_Data;
        if (data && data.PlayerData && data.PlayerData.StaminaData)
        {
            ITEM_StaminaData item = data.PlayerData.StaminaData;
            item.HCSchemaVersion = 0;
            item.HCEnabled = false;
            item.HCExperimental = false;
            item.HCContinuousExertionScale = 1.0;
            item.HCRecoveryScale = 1.0;
            item.HCWeightPenaltyScale = 1.0;
        }
        LoadServer();
    }

    static bool NativeReceipt(CfgGameplayJson data, CfgGameplayJson previous)
    {
        // Only called after the authenticated native handler replaces its DTO.
        // A failed native read must not erase an earlier valid receipt.
        if (s_Server || !data || data == previous)
            return false;
        s_Candidate = null;
        s_Experimental = false;
        s_Pending = null;
        s_PendingExperimental = false;
        if (!data.PlayerData || !data.PlayerData.StaminaData)
            return false;
        ITEM_StaminaData item = data.PlayerData.StaminaData;
        HCStaminaSettings settings = new HCStaminaSettings;
        settings.SchemaVersion = item.HCSchemaVersion;
        settings.Enabled = item.HCEnabled;
        settings.ContinuousExertionScale = item.HCContinuousExertionScale;
        settings.RecoveryScale = item.HCRecoveryScale;
        settings.WeightPenaltyScale = item.HCWeightPenaltyScale;
        s_Pending = Copy(settings);
        s_PendingExperimental = item.HCExperimental;
        if (!s_Active)
            return false;
        return StageClientReceipt();
    }

    protected static bool StageClientReceipt()
    {
        bool staged = Stage(s_Pending, s_PendingExperimental);
        s_Pending = null;
        s_PendingExperimental = false;
        if (!s_ReceiptLogged)
        {
            s_ReceiptLogged = true;
            Print("[HollowCountry] Stamina client receipt staged=" + staged + " enabled=" + Enabled() + " runtime=PENDING");
        }
        return staged;
    }

    static void RequestClientReceipt()
    {
        if (!ClientActive() || s_Candidate || s_Requested)
            return;
        s_Requested = true;
        ScriptRPC rpc = new ScriptRPC;
        rpc.Write(1);
        rpc.Send(null, RPC_REQUEST, true, null);
        Print("[HollowCountry] Stamina client config requested runtime=PENDING");
    }

    static void ResendClientReceipt(PlayerIdentity sender)
    {
        if (!GetGame().IsServer() || !sender)
            return;
        if (!s_RequestTimes)
            s_RequestTimes = new map<int, int>;
        // Native session IDs are reused after disconnect; SessionEvent removes
        // their entries. Keep no persistent account identifiers or request log.
        int connectionId = sender.GetPlayerId();
        int now = GetGame().GetTime();
        int previous;
        if (s_RequestTimes.Find(connectionId, previous) && now >= previous && now - previous < REQUEST_COOLDOWN_MS)
            return;
        // Record before serialization; retries within the cooldown do no work.
        // A wrapped/reset engine clock starts a fresh cooldown.
        s_RequestTimes.Set(connectionId, now);
        CfgGameplayHandler.SyncDataSendEx(sender);
    }

    static void SessionEvent(EventType eventTypeId, bool server, Param params)
    {
        if (eventTypeId == WorldCleaupEventTypeID)
        {
            Reset(false, false);
            return;
        }
        if (server)
        {
            if (eventTypeId == ClientDisconnectedEventTypeID && s_RequestTimes)
            {
                ClientDisconnectedEventParams disconnected = ClientDisconnectedEventParams.Cast(params);
                if (disconnected && disconnected.param1)
                    s_RequestTimes.Remove(disconnected.param1.GetPlayerId());
            }
            return;
        }
        if (eventTypeId == MPSessionStartEventTypeID)
        {
            // SyncDataSendEx can precede session start. Preserve only the
            // validated receipt from this connection, never stale native data.
            s_Active = true;
            s_Suspended = false;
            if (s_Pending)
                StageClientReceipt();
            else
                RequestClientReceipt();
        }
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
        HCStaminaConfiguration.SessionEvent(eventTypeId, IsServer(), params);
        super.OnEvent(eventTypeId, params);
    }

    override void OnMPConnectionLostEvent(int duration)
    {
        HCStaminaConfiguration.ConnectionState(duration);
        super.OnMPConnectionLostEvent(duration);
    }

    override void OnRPC(PlayerIdentity sender, Object target, int rpc_type, ParamsReadContext ctx)
    {
        if (rpc_type == HCStaminaConfiguration.RPC_REQUEST)
        {
            int version;
            if (IsServer() && sender && !target && ctx && ctx.Read(version) && version == 1)
                HCStaminaConfiguration.ResendClientReceipt(sender);
            return;
        }
        if (rpc_type != ERPCs.RPC_CFG_GAMEPLAY_SYNC)
        {
            super.OnRPC(sender, target, rpc_type, ctx);
            return;
        }
        if (IsServer() || sender || target || !ctx)
        {
            super.OnRPC(sender, target, rpc_type, ctx);
            return;
        }
        CfgGameplayJson previous = CfgGameplayHandler.m_Data;
        super.OnRPC(sender, target, rpc_type, ctx);
        HCStaminaConfiguration.NativeReceipt(CfgGameplayHandler.m_Data, previous);
    }
}
