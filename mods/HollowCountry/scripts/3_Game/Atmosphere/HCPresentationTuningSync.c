// #303: HC-27 numeric presentation companion. Server -> client only.
// Native scripts-1.30.164289: gameplay.c:104-117 ScriptRPC.Send;
// DayZGame.c:1497/1506/1533 session events, :3141 OnRPC; tools/JsonFileLoader.c
// :69/88 LoadData/MakeData. Send the numeric config as a deep-serialized class,
// as CfgGameplayHandler.c:90/97 does, rather than a raw JSON string. Serializer.c
// :3-9 documents class serialization; static storage is not a wire field.
// Recreate JSON locally for HCApply's field/range/cross-field checks.
// Game-level receipt buffers one newest snapshot before MissionGameplay exists.
class HCPresentationTuningSync
{
    static const int RPC_TUNING = 4854011;
    static const int VERSION = 2;
    static const int WIRE_LIMIT = 4096;
    protected static int s_ClientRevision;
    protected static bool s_ClientReady;
    protected static ref HCc2PresentationConfig s_Pending;

    static void HCResetClient()
    {
        s_ClientRevision = 0;
        s_ClientReady = false;
        s_Pending = null;
        HCc2PresentationConfig.HCSet(new HCc2PresentationConfig);
    }

    static void HCClientReady()
    {
        s_ClientReady = true;
        HCApplyPending();
    }

    static void HCReceive(ParamsReadContext ctx)
    {
        int version;
        int revision;
        if (!ctx || !ctx.Read(version)) { HCRefuse("version_read"); return; }
        if (version != VERSION) { HCRefuse("version"); return; }
        if (!ctx.Read(revision)) { HCRefuse("revision_read"); return; }
        if (revision < 1 || revision > 2000000000) { HCRefuse("revision"); return; }
        if (revision <= s_ClientRevision) { return; }
        HCc2PresentationConfig received;
        if (!ctx.Read(received) || !received) { HCRefuse("config_read"); return; }
        string image;
        string error;
        if (!JsonFileLoader<HCc2PresentationConfig>.MakeData(received, image, error, false)) { HCRefuse("serialization"); return; }
        if (image.Length() < 2 || image.Length() > WIRE_LIMIT) { HCRefuse("wire_limit"); return; }
        HCc2PresentationConfig checked = new HCc2PresentationConfig;
        checked.HCApply(image, received);
        s_ClientRevision = revision;
        s_Pending = checked;
        HCApplyPending();
    }

    protected static void HCRefuse(string reason)
    {
        Print("[HC Config] atmosphere-presentation sync=refused reason=" + reason + " last_snapshot_retained runtime=PENDING");
    }

    protected static void HCApplyPending()
    {
        if (!s_ClientReady || !s_Pending) { return; }
        HCc2PresentationConfig.HCSet(s_Pending);
        s_Pending = null;
        Print("[HC Config] atmosphere-presentation sync=applied revision=" + s_ClientRevision.ToString() + " source=server runtime=PENDING");
    }
}

modded class DayZGame
{
    override void OnRPC(PlayerIdentity sender, Object target, int rpc_type, ParamsReadContext ctx)
    {
        if (rpc_type == HCPresentationTuningSync.RPC_TUNING)
        {
            if (!IsServer() && !sender && !target) { HCPresentationTuningSync.HCReceive(ctx); }
        }
        // Consume our stream before native Event_OnRPC observers; none owns this ID.
        super.OnRPC(sender, target, rpc_type, ctx);
    }

    override void OnEvent(EventType eventTypeId, Param params)
    {
        if (!IsServer())
        {
            if (eventTypeId == MPSessionStartEventTypeID || eventTypeId == MPSessionEndEventTypeID || eventTypeId == MPSessionFailEventTypeID || eventTypeId == WorldCleaupEventTypeID)
            {
                HCPresentationTuningSync.HCResetClient();
            }
        }
        super.OnEvent(eventTypeId, params);
    }
}
