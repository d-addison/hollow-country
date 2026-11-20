// P5 / D2: reliable connect-time server snapshot, no client requests or ticks.
// ID 4854010 had no matches in mods/ or native scripts before assignment.
// Native scripts-1.30.164289: 3_Game/gameplay.c:104-117 ScriptRPC/Send;
// 1_Core/proto/Serializer.c:57 Write/Read; 3_Game/DayZGame.c:991,3144
// Event_OnRPC; 2_GameLib/tools.c:120,122 ScriptInvoker.Insert/Remove;
// 5_Mission/mission/missionServer.c:549,599,633 connect/ready/reconnect;
// missionGameplay.c:102,266 OnInit/OnMissionFinish.
// Same trusted sender/null-target checks as HCClientPresentation.HCReceive.
// Wire: version, active, weight-enabled, base, perKg, min, max, fist,
// in-place-enabled, distance. Disabled snapshots explicitly restore vanilla.
class HCMeleeClientSync
{
    static const int RPC_SETTINGS = 4854010;
    static const int VERSION = 1;

    static void SendTo(PlayerIdentity identity)
    {
        if (!GetGame().IsServer() || !identity) { return; }
        HCMeleeSettings settings = HCMeleeConfig.HCGet();
        ScriptRPC rpc = new ScriptRPC;
        rpc.Write(VERSION);
        rpc.Write(HCMeleeModule.Active());
        rpc.Write(settings.WeightStamina);
        rpc.Write(settings.WeightStaminaBase);
        rpc.Write(settings.WeightStaminaPerKg);
        rpc.Write(settings.WeightStaminaMin);
        rpc.Write(settings.WeightStaminaMax);
        rpc.Write(settings.WeightStaminaFist);
        rpc.Write(settings.InPlaceLight);
        rpc.Write(settings.InPlaceDistance);
        rpc.Send(null, RPC_SETTINGS, true, identity);
    }

    void HCReceive(PlayerIdentity sender, Object target, int rpcType, ParamsReadContext ctx)
    {
        if (rpcType != RPC_SETTINGS || GetGame().IsServer() || sender || target) { return; }
        HCMeleeFightSettings.HCReset();
        int version;
        bool active;
        HCMeleeSettings settings = new HCMeleeSettings;
        if (!ctx || !ctx.Read(version) || version != VERSION || !ctx.Read(active)) { return; }
        if (!ctx.Read(settings.WeightStamina) || !ctx.Read(settings.WeightStaminaBase)) { return; }
        if (!ctx.Read(settings.WeightStaminaPerKg) || !ctx.Read(settings.WeightStaminaMin)) { return; }
        if (!ctx.Read(settings.WeightStaminaMax) || !ctx.Read(settings.WeightStaminaFist)) { return; }
        if (!ctx.Read(settings.InPlaceLight) || !ctx.Read(settings.InPlaceDistance)) { return; }
        if (!active || !HCValid(settings)) { return; }
        HCMeleeFightSettings.HCApply(settings);
    }

    protected bool HCValid(HCMeleeSettings settings)
    {
        HCOperatorSettingsRegistry.HCMeleeInit();
        if (!HCOperatorSettingsRegistry.HCValid("Melee.WeightStaminaBase", settings.WeightStaminaBase)) { return false; }
        if (!HCOperatorSettingsRegistry.HCValid("Melee.WeightStaminaPerKg", settings.WeightStaminaPerKg)) { return false; }
        if (!HCOperatorSettingsRegistry.HCValid("Melee.WeightStaminaMin", settings.WeightStaminaMin)) { return false; }
        if (!HCOperatorSettingsRegistry.HCValid("Melee.WeightStaminaMax", settings.WeightStaminaMax)) { return false; }
        if (!HCOperatorSettingsRegistry.HCValid("Melee.WeightStaminaFist", settings.WeightStaminaFist)) { return false; }
        return HCOperatorSettingsRegistry.HCValid("Melee.InPlaceDistance", settings.InPlaceDistance);
    }
}

modded class MissionGameplay
{
    protected ref HCMeleeClientSync m_HCMeleeClientSync;

    override void OnInit()
    {
        super.OnInit();
        HCMeleeFightSettings.HCReset();
        if (GetGame().IsDedicatedServer()) { return; }
        m_HCMeleeClientSync = new HCMeleeClientSync;
        DayZGame.Event_OnRPC.Insert(m_HCMeleeClientSync.HCReceive);
    }

    override void OnMissionFinish()
    {
        if (m_HCMeleeClientSync) { DayZGame.Event_OnRPC.Remove(m_HCMeleeClientSync.HCReceive); }
        m_HCMeleeClientSync = null;
        HCMeleeFightSettings.HCReset();
        super.OnMissionFinish();
    }
}

modded class MissionServer
{
    override PlayerBase OnClientNewEvent(PlayerIdentity identity, vector pos, ParamsReadContext ctx)
    {
        PlayerBase player = super.OnClientNewEvent(identity, pos, ctx);
        HCMeleeClientSync.SendTo(identity);
        return player;
    }

    override void OnClientReadyEvent(PlayerIdentity identity, PlayerBase player)
    {
        super.OnClientReadyEvent(identity, player);
        HCMeleeClientSync.SendTo(identity);
    }

    override void OnClientReconnectEvent(PlayerIdentity identity, PlayerBase player)
    {
        super.OnClientReconnectEvent(identity, player);
        HCMeleeClientSync.SendTo(identity);
    }
}
