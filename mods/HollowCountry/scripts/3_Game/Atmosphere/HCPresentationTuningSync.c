// #303: HC-27 numeric presentation companion. Server -> client only.
// Native scripts-1.30.164289: gameplay.c:104-117 ScriptRPC.Send;
// DayZGame.c:1497/1506/1533 session events, :3141 OnRPC; tools/JsonFileLoader.c
// :69/88 LoadData/MakeData. A single <=4096-character JSON image carries all
// presentation fields; HCApply retains the same field/range/cross-field checks.
// Game-level receipt buffers one newest snapshot before MissionGameplay exists.
class HCPresentationTuningSync
{
    static const int RPC_TUNING = 4854011;
    static const int VERSION = 1;
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
        string image;
        if (!ctx || !ctx.Read(version) || version != VERSION || !ctx.Read(revision)) { return; }
        if (revision <= s_ClientRevision || !ctx.Read(image)) { return; }
        if (image.Length() < 2 || image.Length() > WIRE_LIMIT) { return; }
        HCc2PresentationConfig received;
        string error;
        if (!JsonFileLoader<HCc2PresentationConfig>.LoadData(image, received, error) || !received) { return; }
        HCc2PresentationConfig checked = new HCc2PresentationConfig;
        checked.HCApply(image, received);
        s_ClientRevision = revision;
        s_Pending = checked;
        HCApplyPending();
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
        if (rpc_type != HCPresentationTuningSync.RPC_TUNING)
        {
            super.OnRPC(sender, target, rpc_type, ctx);
            return;
        }
        if (IsServer() || sender || target) { return; }
        HCPresentationTuningSync.HCReceive(ctx);
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
