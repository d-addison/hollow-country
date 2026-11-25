// #303: numeric companion to HCClientPresentationMission's feature-bit sync.
// Native scripts-1.30.164289: mission/missionServer.c:85 OnInit,
// :549/599/633 new/ready/reconnect; missionGameplay.c:102/266 init/finish;
// 2_GameLib/tools.c:61/65 ScriptCallQueue.CallLater/Remove;
// 3_Game/Global/Game.c:914 GetTickTime, :1550 GetCallQueue.
// Poll through the shared scheduler every 30 s, one file operation per stage.
// Decode only when source bytes change; broadcast only effective tuning changes.
// No client request path, recipient enumeration, profile write or new module.
class HCPresentationTuningServer
{
    protected static string s_Image;
    protected static string s_SourceImage;
    protected static ref HCc2PresentationConfig s_Config;
    protected static int s_Revision;
    protected static ref HCPresentationTuningReadJob s_ReadJob;
    protected static ref HCUnitBudget s_Units = new HCUnitBudget;
    protected static ref HCWorkBudget s_Work = new HCWorkBudget;

    static void HCStart()
    {
        HCStop();
        s_Image = "";
        s_SourceImage = "";
        s_Config = null;
        s_Revision = 0;
        HCRefresh(HCc2PresentationConfig.HCReadSource());
        s_ReadJob = new HCPresentationTuningReadJob;
        HCSaveScheduler.HCRegister(s_ReadJob);
        // EnSystem.c:397-531 exposes no file size/mtime query in this snapshot.
        // Stage the poll instead; source bytes remain the change detector.
        Print("[HC Config] atmosphere-presentation poll=staged reason=native_file_metadata_unavailable runtime=PENDING");
        GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(HCPresentationTuningServer.HCPumpRead, 1000, true);
        GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).Remove(HCPresentationTuningServer.HCCheckChanges);
        GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(HCPresentationTuningServer.HCCheckChanges, 30000, true);
    }

    protected static bool HCRefresh(string sourceImage)
    {
        if (!GetGame() || !GetGame().IsServer()) { return false; }
        if (s_Image != "" && sourceImage == s_SourceImage) { return false; }
        HCc2PresentationConfig config = HCc2PresentationConfig.HCDecode(sourceImage);
        string image;
        string error;
        if (!JsonFileLoader<HCc2PresentationConfig>.MakeData(config, image, error, false))
        {
            Print("[HC Config] atmosphere-presentation sync=refused reason=serialization last_snapshot_retained runtime=PENDING");
            return false;
        }
        if (image.Length() < 2 || image.Length() > HCPresentationTuningSync.WIRE_LIMIT)
        {
            Print("[HC Config] atmosphere-presentation sync=refused reason=wire_limit last_snapshot_retained runtime=PENDING");
            return false;
        }
        if (image == s_Image)
        {
            s_SourceImage = sourceImage;
            return false;
        }
        if (s_Revision >= 2000000000)
        {
            Print("[HC Config] atmosphere-presentation sync=refused reason=revision_exhausted last_snapshot_retained runtime=PENDING");
            return false;
        }
        HCc2PresentationConfig.HCSet(config);
        s_Image = image;
        s_Config = config;
        s_SourceImage = sourceImage;
        s_Revision = s_Revision + 1;
        return true;
    }

    static void HCSendTo(PlayerIdentity identity)
    {
        if (!identity) { return; }
        HCSend(identity, "connect");
    }

    protected static void HCSend(PlayerIdentity identity, string reason)
    {
        if (!GetGame() || !GetGame().IsServer() || !s_Config) { return; }
        ScriptRPC rpc = new ScriptRPC;
        // Ordinary local ints avoid passing static/const expressions to void Write.
        int version = HCPresentationTuningSync.VERSION;
        int revision = s_Revision;
        HCc2PresentationConfig config = s_Config;
        if (!rpc.Write(version) || !rpc.Write(revision) || !rpc.Write(config))
        {
            Print("[HC Config] atmosphere-presentation sync=refused reason=write last_snapshot_retained runtime=PENDING");
            return;
        }
        rpc.Send(null, HCPresentationTuningSync.RPC_TUNING, true, identity);
        // No identities in diagnostics. A null recipient is one native broadcast.
        Print("[HC Config] atmosphere-presentation sync=sent reason=" + reason + " revision=" + s_Revision.ToString() + " chars=" + s_Image.Length().ToString() + " runtime=PENDING");
    }

    static void HCCheckChanges()
    {
        if (!GetGame() || !GetGame().IsServer() || !s_ReadJob) { return; }
        s_Units.HCReset(1);
        s_Work.HCReset(1);
        if (!s_Units.HCTake(1) || !s_Work.HCContinue()) { return; }
        s_ReadJob.HCRequest();
    }

    // One fallback stage per second if shared saves are disabled or capacity
    // refused registration. Registered urgent work uses the scheduler frame budget.
    static void HCPumpRead()
    {
        HCSaveScheduler.HCPumpFallback(s_ReadJob);
    }

    static void HCReadComplete(string sourceImage)
    {
        if (HCRefresh(sourceImage)) { HCSend(null, "changed_broadcast"); }
    }

    static void HCStop()
    {
        if (GetGame())
        {
            GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).Remove(HCPresentationTuningServer.HCCheckChanges);
            GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).Remove(HCPresentationTuningServer.HCPumpRead);
        }
        if (!s_ReadJob) { return; }
        HCSaveScheduler.HCUnregister(s_ReadJob);
        s_ReadJob.HCCancel();
        s_ReadJob = null;
    }
}

// Native scripts-1.30.164289/1_Core/proto/EnSystem.c:397 FileExist,
// :417 OpenFile, :425 ReadFile, :443 CloseFile. The path and 8192-byte limit
// match HCc2PresentationConfig.HCReadSource; no writes or RPC format changes.
class HCPresentationTuningReadJob : HCSaveJob
{
    protected int m_Stage;
    protected FileHandle m_Handle;
    protected bool m_Open;
    protected string m_Text;
    protected bool m_Invalid;

    override string HCName() { return "PresentationRead"; }

    void HCRequest()
    {
        if (HCDirty || HCInFlight) { return; }
        m_Stage = 0;
        m_Text = "";
        m_Invalid = false;
        HCDirty = true;
        HCUrgent = true;
        HCDue = GetGame().GetTickTime();
    }

    void HCCancel()
    {
        if (m_Open) { CloseFile(m_Handle); m_Open = false; }
        m_Text = "";
        HCDirty = false;
        HCInFlight = false;
        HCUrgent = false;
    }

    override int HCStep()
    {
        if (m_Stage == 0)
        {
            HCOperation = "source_probe";
            m_Stage = 1;
            if (!FileExist("$profile:HollowCountry/atmosphere-presentation.json")) { m_Stage = 4; }
            return STEP_MORE;
        }
        if (m_Stage == 1)
        {
            HCOperation = "source_open";
            m_Handle = OpenFile("$profile:HollowCountry/atmosphere-presentation.json", FileMode.READ);
            m_Open = false;
            if (m_Handle) { m_Open = true; }
            m_Stage = 2;
            if (!m_Open) { m_Invalid = true; m_Stage = 4; }
            return STEP_MORE;
        }
        if (m_Stage == 2)
        {
            HCOperation = "source_read";
            // One bounded read, including the byte beyond the 8192 limit.
            int count = ReadFile(m_Handle, m_Text, 8193);
            m_Invalid = count < 1 || count > 8192 || m_Text.Length() != count;
            m_Stage = 3;
            return STEP_MORE;
        }
        if (m_Stage == 3)
        {
            HCOperation = "source_close";
            CloseFile(m_Handle);
            m_Open = false;
            m_Stage = 4;
            return STEP_MORE;
        }
        HCOperation = "source_apply";
        if (m_Invalid)
        {
            Print("[HC Config] atmosphere-presentation reason=read_or_json defaults_retained runtime=PENDING");
            m_Text = "";
        }
        HCPresentationTuningServer.HCReadComplete(m_Text);
        m_Text = "";
        m_Stage = 0;
        return STEP_DONE;
    }
}

modded class MissionServer
{
    override void OnInit()
    {
        super.OnInit();
        HCPresentationTuningServer.HCStart();
    }

    override PlayerBase OnClientNewEvent(PlayerIdentity identity, vector pos, ParamsReadContext ctx)
    {
        PlayerBase player = super.OnClientNewEvent(identity, pos, ctx);
        HCPresentationTuningServer.HCSendTo(identity);
        return player;
    }

    override void OnClientReadyEvent(PlayerIdentity identity, PlayerBase player)
    {
        super.OnClientReadyEvent(identity, player);
        HCPresentationTuningServer.HCSendTo(identity);
    }

    override void OnClientReconnectEvent(PlayerIdentity identity, PlayerBase player)
    {
        super.OnClientReconnectEvent(identity, player);
        HCPresentationTuningServer.HCSendTo(identity);
    }

    override void OnMissionFinish()
    {
        HCPresentationTuningServer.HCStop();
        super.OnMissionFinish();
    }
}

modded class MissionGameplay
{
    override void OnInit()
    {
        // Apply an early receipt before presentation owners cache their defaults.
        // Do not reset here: the game-level receiver may already hold the snapshot.
        if (!GetGame().IsServer()) { HCPresentationTuningSync.HCClientReady(); }
        super.OnInit();
        if (!GetGame().IsServer()) { HCStaminaConfiguration.ClientReady(); }
    }

    override void OnMissionFinish()
    {
        super.OnMissionFinish();
        if (!GetGame().IsServer()) { HCPresentationTuningSync.HCResetClient(); }
        if (!GetGame().IsServer()) { HCStaminaConfiguration.Reset(false, false); }
    }
}

// Grade caches its initial percent. Refresh the server default on a late receipt
// or file change, while retaining the existing explicit local K-key preference.
// Other consumers query HCGet for each bounded presentation update.
modded class HCGradeSettingsClient
{
    protected int m_HCTuningDefault = -1;

    override void Update(float timeslice, bool allowInput)
    {
        int serverDefault = HCc2PresentationConfig.HCGet().GradeDefaultPercent;
        if (m_HCTuningDefault != serverDefault)
        {
            string saved;
            bool explicitPreference = false;
            if (GetGame().GetProfileString(PROFILE_KEY, saved))
            {
                for (int candidate = 0; candidate <= 100; candidate += 10)
                {
                    if (saved == candidate.ToString()) { explicitPreference = true; }
                }
            }
            if (!explicitPreference)
            {
                m_Percent = serverDefault;
                // Base Update returns early at zero; clear any active grade first.
                if (m_Percent == 0) { Stop(); }
            }
            m_HCTuningDefault = serverDefault;
        }
        super.Update(timeslice, allowInput);
    }
}
