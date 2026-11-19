// LC-T502 / EXP-POL-2. HC-27 coordinator owns effective settings and lifecycle.
// Installed scripts-1.30.164289 native evidence (relative to that dump):
// 3_Game/EffectManager.c:237 PlaySoundEnviroment(string,vector,float,float,bool),
// :280 DestroyEffect stops/unregisters; 3_Game/Effects/EffectSound.c:878 SetSoundMaxVolume.
// 3_Game/Entities/Object.c:287,392 GetPosition/GetSurfaceType;
// 3_Game/Entities/Man.c:37,38 IsSoundInsideBuilding/IsCameraInsideVehicle;
// 3_Game/Global/World.c:53 IsNight; Global/Game.c:612,914 ConfigIsExisting/GetTickTime.
// 3_Game/Global/Game.c:931,944,1120 GetWorld/GetPlayer/IsServer;
// 3_Game/Entities/Object.c:517 IsAlive; 4_World/Entities/ManBase/PlayerBase.c:3925 IsUnconscious.
// 1_Core/proto/EnMath.c:106 RandomFloatInclusive; EnMath3D.c:18 Vector;
// EnString.c:171,240 ToLower/IndexOf; EnDebug.c:96 Print; 3_Game/gameplay.c:636 GetGame.
// 5_Mission/mission/missionGameplay.c:102,266,287 lifecycle hooks.
// Installed addons/sounds_hpp.pbo, config.bin (binary, class byte offsets):
// CfgSoundSets/WindForestLight_SoundSet @5994660 -> WindForestLight_SoundShader @4504718
// (native windy/trees/rain/night controllers, spatial=0, loop=1).
// CfgSoundSets/WolfHowl1_tailDistant_SoundSet @5509692 -> shader @2142317 (range 900m).
// Installed addons/surfaces.pbo config.bin CfgSurfaces: cp_conifer_* / cp_broadleaf_*.
// No audio or config assets copied. Quiet towns receive no extra layer; optional native
// ambient-volume reduction deferred (avoid changing footsteps/combat audio or other mods).
// Native compile, controller audibility/mix, mission cleanup and two-client acceptance pending.
class HCEnvSound
{
    protected EffectSound m_Sound;
    protected float m_Check;
    protected float m_NextLayer;
    protected float m_NextHowl;
    protected float m_StopAt;
    protected bool m_Stopped;
    protected bool m_Logged;
    protected bool m_Wind;

    void HCEnvSound()
    {
        float now = GetGame().GetTickTime();
        m_NextLayer = now + 45;
        m_NextHowl = now + Math.RandomFloatInclusive(600, 900);
    }

    static bool CanPlay(float now, float nextAt, bool hasSound)
    {
        return now >= nextAt && !hasSound;
    }

    void StopSound()
    {
        if (m_Sound) SEffectManager.DestroyEffect(m_Sound);
        m_Sound = null;
        m_Wind = false;
    }

    void LogLayer(string layer)
    {
        if (m_Logged) return;
        m_Logged = true;
        Print("[HollowCountry] V2 client env sound layer=" + layer);
    }

    bool Forest(string surface)
    {
        surface.ToLower();
        return surface.IndexOf("cp_conifer_") == 0 || surface.IndexOf("cp_broadleaf_") == 0;
    }

    void Update(float timeslice)
    {
        if (m_Stopped) return;
        float now = GetGame().GetTickTime();
        // Release handles even between the bounded five-second environment samples.
        if (m_Sound && now >= m_StopAt) StopSound();
        m_Check = m_Check + timeslice;
        if (m_Check < 5) return;
        m_Check = 0;
        PlayerBase player = PlayerBase.Cast(GetGame().GetPlayer());
        if (!player || !player.IsAlive() || player.IsUnconscious()) { StopSound(); return; }
        if (player.IsSoundInsideBuilding() || player.IsCameraInsideVehicle()) { StopSound(); return; }
        bool forest = Forest(player.GetSurfaceType());
        // A wind loop must stop when the listener leaves woodland, too.
        if (m_Sound && m_Wind && !forest) StopSound();
        if (!CanPlay(now, m_NextLayer, m_Sound != null)) return;
        string soundSet;
        string layer;
        vector position = player.GetPosition();
        float duration;
        bool loop = false;
        if (GetGame().GetWorld().IsNight() && now >= m_NextHowl)
        {
            soundSet = "WolfHowl1_tailDistant_SoundSet";
            layer = "night-howl";
            // An ambient tail only; never a gunshot or AI stimulus. No entities spawned.
            position = position + Vector(220, 10, 220);
            duration = 15;
            m_NextHowl = now + Math.RandomFloatInclusive(600, 900);
        }
        else if (forest)
        {
            soundSet = "WindForestLight_SoundSet";
            layer = "forest-wind";
            duration = 25;
            loop = true;
        }
        else return;
        // Bound retries even if an installed sound class is unavailable.
        m_NextLayer = now + Math.RandomFloatInclusive(180, 300);
        if (!GetGame().ConfigIsExisting("CfgSoundSets " + soundSet)) return;
        m_Sound = SEffectManager.PlaySoundEnviroment(soundSet, position, 2, 2, loop);
        if (!m_Sound) return;
        m_Sound.SetSoundMaxVolume(0.2);
        m_Wind = loop;
        m_StopAt = now + duration;
        LogLayer(layer);
    }

    int HCHandleCount()
    {
        if (m_Sound) { return 1; }
        return 0;
    }

    void Stop()
    {
        if (m_Stopped) return;
        m_Stopped = true;
        StopSound();
        LogLayer("quiet");
    }
}
