// HC-27: server-owned presentation preferences, never client gameplay authority.
// Installed scripts-1.30.164289 native evidence (relative paths):
// 3_Game/Global/Game.c:1120 IsServer; 3_Game/gameplay.c:104,117 ScriptRPC/Send;
// 1_Core/proto/Serializer.c:57 Write; 1_Core/proto/EnScript.c:380 Count;
// 1_Core/proto/EnMath.c:553 Math.Min; EnConvert.c:30 int.ToString;
// EnDebug.c:96 Print; 3_Game/Entities/Man.c:21 GetIdentity;
// 1_Core/proto/EnScript.c:94 Cast. HCPerfPlayers owns GetPlayers snapshot.
// Cached control traffic: at most one settings read / five mission seconds,
// except the initial lazy snapshot. No config IO, module admission or core hooks.
// Static revision survives HCServer.Stop/Start (including clock discontinuity).
// Runtime=PENDING: exact-source native compile and two-client RPC delivery.
class HCClientPresentationServer
{
    protected static int s_Revision;
    protected static int s_Mask;
    protected static float s_Elapsed;

    static int HCComputeMask(HCSettings settings)
    {
        if (!settings) { return 0; }
        int mask = settings.ClientPresentationMask;
        if (!HCClientPresentationSettings.HCValidMask(mask)) { return 0; }
        if (!settings.EnableGrade) { mask = mask & (HCClientPresentationSettings.ALL - HCClientPresentationSettings.GRADE); }
        if (!settings.EnableSignsOfLife) { mask = mask & (HCClientPresentationSettings.ALL - HCClientPresentationSettings.SIGNS); }
        if (!settings.EnableAmbientLife) { mask = mask & (HCClientPresentationSettings.ALL - HCClientPresentationSettings.AMBIENT); }
        // HINTS has no separate server feature veto; operator mask still applies.
        return mask;
    }

    protected static bool HCRefresh()
    {
        if (s_Revision >= 2000000000) { return false; }
        // Lazy initialization may happen partway through a polling interval.
        s_Elapsed = 0;
        HCSettings settings = HCServer.Get().GetSettings();
        int mask = HCComputeMask(settings);
        if (s_Revision > 0 && mask == s_Mask) { return false; }
        s_Revision = s_Revision + 1;
        // Reserve the final representable revision for a permanent off snapshot.
        // Never wrap or send conflicting payloads at the same revision.
        if (s_Revision == 2000000000)
        {
            mask = 0;
            Print("[HC Plan] HC-27 presentation=refused reason=revision_exhausted runtime=PENDING");
        }
        s_Mask = mask;
        string line = "[HC Plan] HC-27 presentation_settings revision=" + s_Revision.ToString();
        Print(line + " mask=" + s_Mask.ToString() + " runtime=PENDING");
        return true;
    }

    static void SendTo(PlayerIdentity identity)
    {
        if (!GetGame().IsServer() || !identity) { return; }
        if (s_Revision == 0) { HCRefresh(); }
        ScriptRPC rpc = new ScriptRPC;
        rpc.Write(HCClientPresentationSettings.VERSION);
        rpc.Write(s_Revision);
        rpc.Write(s_Mask);
        rpc.Send(null, HCClientPresentationSettings.RPC_SETTINGS, true, identity);
    }

    protected static void HCBroadcast()
    {
        array<Man> players = HCPerfPlayers.HCGet();
        int count = Math.Min(players.Count(), 90);
        int index = 0;
        while (index < count)
        {
            PlayerBase player = PlayerBase.Cast(players[index]);
            index = index + 1;
            if (player) { SendTo(player.GetIdentity()); }
        }
    }

    static void HCTick(float timeslice)
    {
        if (!GetGame().IsServer() || timeslice <= 0) { return; }
        s_Elapsed = s_Elapsed + timeslice;
        if (s_Elapsed < 5) { return; }
        s_Elapsed = 0;
        if (HCRefresh()) { HCBroadcast(); }
    }
}
