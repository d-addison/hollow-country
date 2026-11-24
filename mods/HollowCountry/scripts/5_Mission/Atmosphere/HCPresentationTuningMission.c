// #303: numeric companion to HCClientPresentationMission's feature-bit sync.
// Native scripts-1.30.164289: mission/missionServer.c:85 OnInit,
// :549/599/633 new/ready/reconnect; missionGameplay.c:102/266 init/finish;
// 2_GameLib/tools.c:61/65 ScriptCallQueue.CallLater/Remove.
// Poll the bounded source every 30 s. Decode only when its text changes and
// broadcast only when the effective tuning changes.
// No client request path, recipient enumeration, profile write or new module.
class HCPresentationTuningServer
{
    protected static string s_Image;
    protected static string s_SourceImage;
    protected static int s_Revision;
    protected static ref HCUnitBudget s_Units = new HCUnitBudget;
    protected static ref HCWorkBudget s_Work = new HCWorkBudget;

    static void HCStart()
    {
        s_Image = "";
        s_SourceImage = "";
        s_Revision = 0;
        HCRefresh();
        GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).Remove(HCPresentationTuningServer.HCCheckChanges);
        GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(HCPresentationTuningServer.HCCheckChanges, 30000, true);
    }

    protected static bool HCRefresh()
    {
        if (!GetGame() || !GetGame().IsServer()) { return false; }
        string sourceImage = HCc2PresentationConfig.HCReadSource();
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
        if (!GetGame() || !GetGame().IsServer() || s_Image == "") { return; }
        ScriptRPC rpc = new ScriptRPC;
        rpc.Write(HCPresentationTuningSync.VERSION);
        rpc.Write(s_Revision);
        rpc.Write(s_Image);
        rpc.Send(null, HCPresentationTuningSync.RPC_TUNING, true, identity);
        // No identities in diagnostics. A null recipient is one native broadcast.
        Print("[HC Config] atmosphere-presentation sync=sent reason=" + reason + " revision=" + s_Revision.ToString() + " chars=" + s_Image.Length().ToString() + " runtime=PENDING");
    }

    // Scheduled separately from per-frame mission updates: a fixed-size file
    // read remains synchronous and must still be measured in the native run.
    static void HCCheckChanges()
    {
        if (!GetGame() || !GetGame().IsServer()) { return; }
        s_Units.HCReset(1);
        s_Work.HCReset(1);
        if (!s_Units.HCTake(1) || !s_Work.HCContinue()) { return; }
        if (HCRefresh()) { HCSend(null, "changed_broadcast"); }
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
        GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).Remove(HCPresentationTuningServer.HCCheckChanges);
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
    }

    override void OnMissionFinish()
    {
        super.OnMissionFinish();
        if (!GetGame().IsServer()) { HCPresentationTuningSync.HCResetClient(); }
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
