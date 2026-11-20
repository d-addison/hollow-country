// #256: server-authoritative pressure, client-only positional warning.
// Installed sounds_hpp.pbo/config.bin: CfgSoundSets Zmb_Attack_Light1_Soundset,
// Zmb_Attack_Heavy1_Soundset, Zmb_Attack_TwoHands_Soundset -> matching
// CfgSoundShaders with infected/AttackFoley samples, spatial=1, loop=0.
// Native scripts-1.30.164289: 3_Game/EffectManager.c:159 CreateSound,
// :280 DestroyEffect; Effects/EffectSound.c:199 SoundPlay, :626
// SetSoundAutodestroy, :856/:878 SetSoundVolume/SetSoundMaxVolume.
// No engine assets are shipped.
// Event_OnRPC and mission hooks follow the existing mission client receivers.
// No timer, particle, animation, AI noise or change to native door mechanics.
class HCDoorPressureCue
{
    protected ref array<EffectSound> m_Sounds = new array<EffectSound>;
    protected int m_SoundCursor;
    static const int MAX_SOUNDS = 8;

    void HCReceive(PlayerIdentity sender, Object target, int rpcType, ParamsReadContext ctx)
    {
        if (rpcType != HCInfectedDoorPolicy.RPC_PRESSURE_CUE) { return; }
        if (GetGame().IsServer() || sender || target || !ctx) { return; }
        int version;
        vector position;
        int level;
        if (!ctx.Read(version) || version != HCInfectedDoorPolicy.CUE_VERSION) { return; }
        if (!ctx.Read(position) || !HCWorldLimits.Position(position)) { return; }
        if (!ctx.Read(level) || level < 1 || level > 3) { return; }
        PlayerBase listener = PlayerBase.Cast(GetGame().GetPlayer());
        if (!listener || !listener.IsAlive()) { return; }
        if (vector.DistanceSq(listener.GetPosition(), position) > HCInfectedDoorPolicy.CUE_RADIUS_SQ) { return; }
        string soundSet = "Zmb_Attack_Light1_Soundset";
        if (level == 2) { soundSet = "Zmb_Attack_Heavy1_Soundset"; }
        if (level == 3) { soundSet = "Zmb_Attack_TwoHands_Soundset"; }
        if (!GetGame().ConfigIsExisting("CfgSoundSets " + soundSet)) { return; }
        // Fixed ring: even if a native sound stalls, retained handles stay <=8.
        if (m_Sounds.Count() == MAX_SOUNDS)
        {
            SEffectManager.DestroyEffect(m_Sounds[m_SoundCursor]);
        }
        EffectSound cue = SEffectManager.CreateSound(soundSet, position);
        if (!cue) { return; }
        cue.SetSoundAutodestroy(true);
        cue.SetSoundMaxVolume(0.4 + 0.2 * level);
        cue.SetSoundVolume(0.4 + 0.2 * level);
        if (m_Sounds.Count() < MAX_SOUNDS) { m_Sounds.Insert(cue); }
        else { m_Sounds[m_SoundCursor] = cue; }
        m_SoundCursor = (m_SoundCursor + 1) % MAX_SOUNDS;
        if (!cue.SoundPlay()) { SEffectManager.DestroyEffect(cue); }
    }

    void HCStop()
    {
        for (int soundIndex = 0; soundIndex < m_Sounds.Count(); soundIndex++)
        {
            SEffectManager.DestroyEffect(m_Sounds[soundIndex]);
        }
        m_Sounds.Clear();
    }
}

modded class MissionGameplay
{
    protected ref HCDoorPressureCue m_HCDoorPressureCue;

    override void OnInit()
    {
        super.OnInit();
        if (GetGame().IsDedicatedServer()) { return; }
        m_HCDoorPressureCue = new HCDoorPressureCue;
        DayZGame.Event_OnRPC.Insert(m_HCDoorPressureCue.HCReceive);
    }

    override void OnMissionFinish()
    {
        if (m_HCDoorPressureCue)
        {
            DayZGame.Event_OnRPC.Remove(m_HCDoorPressureCue.HCReceive);
            m_HCDoorPressureCue.HCStop();
        }
        m_HCDoorPressureCue = null;
        super.OnMissionFinish();
    }
}
