// LC-T502 / EXP-POL-2. HC-27 coordinator owns effective settings and lifecycle.
// Installed scripts-1.30.164289 native evidence (relative to that dump):
// 3_Game/EffectManager.c:256 PlaySoundOnObject(string,Object,float,float,bool)
// parents the sound at local zero before playback so it follows the listener;
// :280 DestroyEffect stops/unregisters; 3_Game/Effects/EffectSound.c:878 SetSoundMaxVolume.
// EffectSound.c:274 IsSoundPlaying; :549 playback begins asynchronously.
// 3_Game/Entities/Object.c:287,392 GetPosition/GetSurfaceType;
// 3_Game/Entities/Man.c:37,38 IsSoundInsideBuilding/IsCameraInsideVehicle;
// 3_Game/Global/Game.c:612,914 ConfigIsExisting/GetTickTime.
// 3_Game/Global/Game.c:931,944,1120 GetWorld/GetPlayer/IsServer;
// 3_Game/Entities/Object.c:517 IsAlive; 4_World/Entities/ManBase/PlayerBase.c:3925 IsUnconscious.
// 1_Core/proto/EnMath.c:106 RandomFloatInclusive; EnMath3D.c:18 Vector;
// EnString.c:171,240 ToLower/IndexOf; EnDebug.c:96 Print; 3_Game/gameplay.c:636 GetGame.
// 5_Mission/mission/missionGameplay.c:102,266,287 lifecycle hooks.
// Installed addons/sounds_hpp.pbo config.bin: SpookyArea_WhistlingWind_SoundSet
// inherits base_SpookyArea_SoundSet (spatial=1, doppler=0), with seven wind samples
// and fixed shader volume dB-13; no windy/trees/rain/night controllers required.
// Native 4_World/Classes/ContaminatedArea/SpookyAreaMisc.c:7,163 uses this set
// with SEffectManager.PlaySound. WindForestLight_SoundSet exists but failed to
// build a sound object in build 117; class existence alone is insufficient.
// Installed addons/surfaces.pbo config.bin CfgSurfaces: cp_conifer_* / cp_broadleaf_*.
// No audio or config assets copied. Quiet towns receive no extra layer; optional native
// ambient-volume reduction deferred (avoid changing footsteps/combat audio or other mods).
// Native compile, audibility/mix and mission cleanup with one server/client pending.
class HCEnvSound
{
    protected EffectSound m_Sound;
    protected float m_Check;
    protected float m_NextLayer;
    protected float m_StopAt;
    protected bool m_Stopped;
    protected bool m_Logged;
    protected bool m_Wind;
    protected bool m_AwaitingPlayback;
    protected int m_FailureLogs;

    void HCEnvSound()
    {
        float now = GetGame().GetTickTime();
        m_NextLayer = now + HCc2PresentationConfig.HCGet().SoundStartupSeconds;
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
        m_AwaitingPlayback = false;
    }

    void LogLayer(string layer)
    {
        if (m_Logged) return;
        m_Logged = true;
        Print("[HollowCountry] V2 client env sound layer=" + layer + " runtime=PENDING");
    }

    void LogFailure(string reason)
    {
        // Retry on the existing layer interval, but cap diagnostic detail per client.
        if (m_FailureLogs >= 3) return;
        m_FailureLogs++;
        Print("[HollowCountry] V2 client env sound failed reason=" + reason + " soundset=SpookyArea_WhistlingWind_SoundSet runtime=PENDING");
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
        if (m_Sound)
        {
            // SoundPlay returns before the wave-start callback. Allow one sample
            // interval before checking it; never report a handle as playback.
            if (!m_Sound.IsSoundPlaying())
            {
                StopSound();
                LogFailure("wave_not_playing");
                return;
            }
            if (m_AwaitingPlayback)
            {
                m_AwaitingPlayback = false;
                LogLayer("forest-wind");
            }
        }
        if (!CanPlay(now, m_NextLayer, m_Sound != null)) return;
        string soundSet;
        float duration;
        bool loop = false;
        if (forest)
        {
            soundSet = "SpookyArea_WhistlingWind_SoundSet";
            duration = 25;
            loop = true;
        }
        else return;
        // Bound retries even if an installed sound class is unavailable.
        m_NextLayer = now + Math.RandomFloatInclusive(HCc2PresentationConfig.HCGet().LayerGapMinSeconds, HCc2PresentationConfig.HCGet().LayerGapMaxSeconds);
        if (!GetGame().ConfigIsExisting("CfgSoundSets " + soundSet))
        {
            LogFailure("soundset_missing");
            return;
        }
        // This spatial set has a 100 m range: follow the listener throughout the loop.
        m_Sound = SEffectManager.PlaySoundOnObject(soundSet, player, 2, 2, loop);
        if (!m_Sound)
        {
            LogFailure("effect_missing");
            return;
        }
        m_Sound.SetSoundMaxVolume(HCc2PresentationConfig.HCGet().SoundVolume);
        m_Wind = loop;
        m_StopAt = now + duration;
        m_AwaitingPlayback = true;
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
