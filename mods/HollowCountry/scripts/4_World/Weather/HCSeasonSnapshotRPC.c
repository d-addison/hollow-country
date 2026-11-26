// HC-51 / #150: one-way, three-int control snapshot; no client requests.
// Native scripts-1.30.164289: 3_Game/gameplay.c:104-117 ScriptRPC/Send
// (null recipient broadcasts); 1_Core/proto/Serializer.c:57 Write;
// 3_Game/Global/Game.c:1120 IsServer; 1_Core/proto/EnDebug.c:96 Print.
// ID check before assignment: rg -n --max-filesize 10M '4853913' mods
// returned no matches (2026-11-18); 4854001 belongs to HC-27 settings.
// HCAdminWorldWire later took 4853913/914 too (lint HC-E054 only read *RPC* names); it moved to 4853915/916 (2026-11-26).
// No enumeration, IO or per-player loop: one send per change/30s heartbeat.
// Revisions survive weather-owner stop/start in the same VM; never wrap.
// Runtime=PENDING: exact-source native compile and two-client transport.
class HCSeasonSnapshotRPC
{
    static const int RPC_SEASON = 4853913;
    protected static int s_Revision = 1;
    protected static int s_Phase = -1;
    protected static float s_Elapsed;
    protected static ref HCUnitBudget s_Units = new HCUnitBudget;
    protected static ref HCWorkBudget s_Work = new HCWorkBudget;

    static void HCPublish(int phaseCode)
    {
        if (!GetGame() || !GetGame().IsServer()) { return; }
        if (phaseCode < -1 || phaseCode > 3 || s_Revision >= 2000000000) { return; }
        if (phaseCode == s_Phase) { return; }
        s_Revision = s_Revision + 1;
        if (s_Revision == 2000000000)
        {
            phaseCode = -1;
            Print("[HC Plan] HC-51 state=refused reason=revision_exhausted count=0 runtime=PENDING");
        }
        s_Phase = phaseCode;
        s_Elapsed = 0.0;
        HCSend(null);
    }

    static void SendTo(PlayerIdentity identity)
    {
        if (!identity) { return; }
        HCSend(identity);
    }

    protected static void HCSend(PlayerIdentity identity)
    {
        if (!GetGame() || !GetGame().IsServer()) { return; }
        ScriptRPC rpc = new ScriptRPC;
        rpc.Write(HCSeasonVisualPolicy.VERSION);
        rpc.Write(s_Revision);
        rpc.Write(s_Phase);
        rpc.Send(null, RPC_SEASON, true, identity);
    }

    static void HCTick(float timeslice)
    {
        if (!GetGame() || !GetGame().IsServer()) { return; }
        if (!(timeslice > 0.0) || !(timeslice <= 2000000000.0)) { return; }
        // No recurring traffic before the weather owner first publishes a
        // phase. A later published off snapshot still needs its heartbeat.
        if (s_Phase == -1 && s_Revision == 1) { return; }
        s_Elapsed = s_Elapsed + timeslice;
        if (s_Elapsed < HCSeasonVisualPolicy.SNAPSHOT_HEARTBEAT_SECONDS) { return; }
        s_Units.HCReset(1);
        s_Work.HCReset(1);
        if (!s_Units.HCTake(1) || !s_Work.HCContinue()) { return; }
        s_Elapsed = 0.0;
        HCSend(null);
    }
}
