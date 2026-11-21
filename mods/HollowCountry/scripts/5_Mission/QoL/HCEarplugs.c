// #245. Client profile preference; no RPC, server module or inventory state.
// Native 1.30.164289 evidence (snapshot-relative paths):
// 3_Game/Sound.c:71-72 GetSoundVolume/SetSoundVolume;
// 3_Game/Global/Game.c:287,301,306 profile get/set/save, :735 GetSoundScene,
// :943-944 UI/player, :1125 IsDedicatedServer; gameplay.c:636 GetGame.
// 3_Game/DayZGame.c:976,1147 m_volume_sound is the vanilla volume baseline.
// 3_Game/InputAPI/UAInput.c:60,218,279 LocalPress/GetInputByName/GetUApi;
// 3_Game/tools/UIManager.c:59 GetMenu; Entities/Object.c:517 IsAlive;
// 3_Game/Client/Notifications/NotificationSystem.c:104,215 notifications.
// 4_World/Entities/ManBase/PlayerBase.c:3778 unconscious mute, :3832 restore,
// :3866-3867 invokes HUD wake callback after restore, :3925 IsUnconscious.
// 5_Mission/mission/missionGameplay.c:102,266,287 init/finish/update,
// :1119 IsControlDisabled, :1334 Continue, :1676-1690 respawn restore.
// 5_Mission/GUI/IngameHud.c:351-369 player-loaded/wake callbacks.
// 5_Mission/GUI/NewUI/Options/OptionsMenu.c:236 Apply, :364 Reset,
// :392 ResetCurrentTab; native options apply/revert: 3_Game/gameplay.c:1465-1475.
// 1_Core/proto/EnMath.c:413 Round; proto/EnConvert.c:30 int.ToString;
// 1_Core/proto/EnScript.c:399 array.Get.
// Runtime audio acceptance remains pending DayZDiag and normal two-client runs.
class HCEarplugs
{
    protected static ref HCEarplugs s_Client;
    // The only level/factor table. Profile stores the validated table index.
    protected static ref array<float> s_Factors = {1.0, 0.60, 0.35, 0.15};
    protected static const string PROFILE_KEY = "HollowCountryEarplugsLevel";
    protected int m_Level;
    protected UAInput m_Input;
    protected bool m_RestorePending;
    protected float m_RetryElapsed;

    static void Start()
    {
        if (GetGame().IsDedicatedServer()) { return; }
        s_Client = new HCEarplugs;
        string saved;
        if (GetGame().GetProfileString(PROFILE_KEY, saved))
        {
            // Exact whitelist: malformed/out-of-range profile values mean out.
            for (int index = 0; index < 4; index++)
            {
                if (saved == index.ToString()) { s_Client.m_Level = index; }
            }
        }
        if (GetUApi()) { s_Client.m_Input = GetUApi().GetInputByName("UAHCEarplugs"); }
        RequestRestore();
    }

    static void Stop()
    {
        s_Client = null;
    }

    static void RequestRestore()
    {
        // Default/out state leaves vanilla alone until the first key press.
        if (!s_Client || s_Client.m_Level == 0) { return; }
        s_Client.m_RestorePending = true;
        s_Client.m_RetryElapsed = 0.25;
    }

    protected bool Apply(float fadeSeconds)
    {
        if (GetGame().IsDedicatedServer()) { return false; }
        PlayerBase player = PlayerBase.Cast(GetGame().GetPlayer());
        // Never cancel the native unconscious/death mute or its fade.
        if (!player || !player.IsAlive() || player.IsUnconscious()) { return false; }
        GetGame().GetSoundScene().SetSoundVolume(g_Game.m_volume_sound * s_Factors.Get(m_Level), fadeSeconds);
        HCModuleReadiness.HCUse("ClientUI", "earplugs_applied");
        return true;
    }

    protected void Press()
    {
        m_Level++;
        if (m_Level >= 4) { m_Level = 0; }
        m_RestorePending = !Apply(0.2);
        GetGame().SetProfileString(PROFILE_KEY, m_Level.ToString());
        GetGame().SaveProfile();
        string line = "Earplugs out";
        if (m_Level != 0)
        {
            int percent = Math.Round(s_Factors.Get(m_Level) * 100.0);
            line = "Earplugs: " + percent.ToString() + "%";
        }
        if (NotificationSystem.GetInstance())
        {
            NotificationSystem.AddNotificationExtended(2.0, line);
        }
    }

    static void Update(float timeslice, bool allowInput)
    {
        if (!s_Client) { return; }
        // One cached edge probe per frame is required to catch short presses,
        // matching HC grade/ping inputs. No scene-volume polling or scans.
        if (allowInput && s_Client.m_Input && s_Client.m_Input.LocalPress())
        {
            PlayerBase player = PlayerBase.Cast(GetGame().GetPlayer());
            if (player && player.IsAlive() && !player.IsUnconscious()) { s_Client.Press(); }
        }
        if (!s_Client.m_RestorePending) { return; }
        // Only pending lifecycle restores retry, <=4 times/sec without catch-up.
        // Wake callback can precede the movement command leaving unconsciousness.
        s_Client.m_RetryElapsed += timeslice;
        if (s_Client.m_RetryElapsed < 0.25) { return; }
        s_Client.m_RetryElapsed = 0;
        if (s_Client.Apply(1.0)) { s_Client.m_RestorePending = false; }
    }
}

modded class MissionGameplay
{
    override void OnInit()
    {
        super.OnInit();
        HCEarplugs.Start();
    }

    override void OnUpdate(float timeslice)
    {
        super.OnUpdate(timeslice);
        if (GetGame().IsDedicatedServer()) { return; }
        HCEarplugs.Update(timeslice, !IsControlDisabled() && !GetGame().GetUIManager().GetMenu());
    }

    override void Continue()
    {
        super.Continue();
        HCEarplugs.RequestRestore();
    }

    override void OnPlayerRespawned(Man player)
    {
        super.OnPlayerRespawned(player);
        HCEarplugs.RequestRestore();
    }

    override void OnMissionFinish()
    {
        super.OnMissionFinish();
        HCEarplugs.Stop();
    }
}

// HUD receives the local player's invoker after PlayerBase restores sound;
// avoids introducing a World-to-Mission dependency or polling every player.
modded class IngameHud
{
    override protected void OnUnconsciousStop()
    {
        super.OnUnconsciousStop();
        HCEarplugs.RequestRestore();
    }
}

modded class OptionsMenu
{
    override void Apply()
    {
        super.Apply();
        HCEarplugs.RequestRestore();
    }

    override void Reset()
    {
        super.Reset();
        HCEarplugs.RequestRestore();
    }

    override void ResetCurrentTab()
    {
        super.ResetCurrentTab();
        HCEarplugs.RequestRestore();
    }
}
