// #131. Existing HCEventGameplay input pattern; three optional inputs require
// coordinator-owned inputs.xml declarations: UAHollowCountryPingOK,
// UAHollowCountryPingHurt, UAHollowCountryPingHelp. No vanilla binding is reused.
// Native scripts-1.30.164289: 3_Game/gameplay.c:636 GetGame;
// 3_Game/InputAPI/UAInput.c:60 LocalPress,
// :218 GetInputByName, :279 GetUApi; Global/Game.c:944 GetPlayer, :1120 IsServer;
// 5_Mission/mission/missionGameplay.c:102 OnInit, :287 OnUpdate;
// missionGameplay.c:1119 IsControlDisabled; 3_Game/Global/Game.c:943 GetUIManager;
// 3_Game/tools/UIManager.c:59 GetMenu; PlayerBase.c:3925 IsUnconscious; Object.c:517 IsAlive.
// Per client frame: <=3 cached input probes, zero allocations unless pressed.
modded class MissionGameplay
{
    protected UAInput m_HCPingOK;
    protected UAInput m_HCPingHurt;
    protected UAInput m_HCPingHelp;
    override void OnInit()
    {
        super.OnInit();
        if (GetGame().IsServer() || !GetUApi()) { return; }
        m_HCPingOK = GetUApi().GetInputByName("UAHollowCountryPingOK");
        m_HCPingHurt = GetUApi().GetInputByName("UAHollowCountryPingHurt");
        m_HCPingHelp = GetUApi().GetInputByName("UAHollowCountryPingHelp");
    }
    override void OnUpdate(float timeslice)
    {
        super.OnUpdate(timeslice);
        if (GetGame().IsServer() || IsControlDisabled() || GetGame().GetUIManager().GetMenu()) { return; }
        HCGroupClient client = HCGroupClient.Get();
        if (!client) { return; }
        // Input is intent only; the server rechecks identity/session/membership,
        // life, rate, recipient range and configured visibility on every request.
        HCGroupSnapshot frame = client.GetSnapshot();
        if (!frame || !frame.Enabled || !frame.Settings) { return; }
        if (!frame.Settings.HCTeamPingEnabled || frame.GroupId < 1 || client.IsBusy()) { return; }
        PlayerBase player = PlayerBase.Cast(GetGame().GetPlayer());
        if (!player || !player.IsAlive() || player.IsUnconscious()) { return; }
        int status = -1;
        if (m_HCPingOK && m_HCPingOK.LocalPress()) { status = 0; }
        if (m_HCPingHurt && m_HCPingHurt.LocalPress()) { status = 1; }
        if (m_HCPingHelp && m_HCPingHelp.LocalPress()) { status = 2; }
        if (status < 0) { return; }
        HCGroupRequest request = new HCGroupRequest;
        request.Op = HCGroupOp.TEAM_PING;
        request.Role = status;
        client.Send(request);
    }
}
