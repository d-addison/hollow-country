// LC-T103 / EXP-A1. Client-local display preference, default 60%, never RPC.
// Native snapshot scripts-1.30.164289, relative paths:
// 3_Game/Global/Game.c:287 GetProfileString, :301 SetProfileString, :306
// SaveProfile, :931 GetWorld, :943 GetUIManager, :944 GetPlayer,
// :1125 IsDedicatedServer, :1371 GetWeather; 3_Game/Global/World.c:28 GetDate.
// 3_Game/Weather.c:38 GetActual, :183/:186/:189 overcast/fog/rain getters.
// 3_Game/InputAPI/UAInput.c:60 LocalPress, :218 GetInputByName, :279 GetUApi;
// 3_Game/tools/UIManager.c:59 GetMenu; 3_Game/Entities/Object.c:517 IsAlive.
// 3_Game/Client/Notifications/NotificationSystem.c:104 GetInstance,
// :215 AddNotificationExtended; 1_Core/proto/EnConvert.c:30 int.ToString;
// 1_Core/proto/EnMath.c:540 Clamp, :608 Lerp.
// 5_Mission/mission/missionGameplay.c:102 OnInit, :266 OnMissionFinish,
// :287 OnUpdate(float timeslice), :1119 IsControlDisabled.
// 4_World/Entities/ManBase/PlayerBase.c:3925 IsUnconscious (guard also used
// by existing 5_Mission/Groups/HCGroupGameplay.c:24-32).
// 3_Game/PPEManager/Requesters/PPERequestPlatformsBase.c:44,53 Stop/IsRequesterRunning.
// Four policy/PPE updates per second at most, no catch-up loop after a stall.
// Grade defaults to K (unused in the four installed vanilla keyboard presets).
class HCGradeSettingsClient
{
    static const string PROFILE_KEY = "HollowCountryGradeIntensity";
    protected int m_Percent = 60;
    protected int m_LastReportedPercent = -1;
    protected bool m_LastReportedRunning;
    protected float m_Elapsed;
    protected float m_Fade;
    protected float m_Overcast;
    protected float m_Fog;
    protected float m_Rain;
    protected bool m_WeatherRead;
    protected UAInput m_Input;
    // Bank owns requester singleton; this is only a borrowed handle.
    protected HCGradeRequester m_Requester;
    protected ref HCGradeParameters m_Parameters = new HCGradeParameters;

    void Start()
    {
        string saved;
        if (GetGame().GetProfileString(PROFILE_KEY, saved))
        {
            // Accept only exact 10% steps; corrupt/missing values retain 60%.
            for (int candidate = 0; candidate <= 100; candidate += 10)
            {
                if (saved == candidate.ToString()) { m_Percent = candidate; }
            }
        }
        ResolveHandles();
        // Reconnect always begins neutral; fade in only during valid gameplay.
        Stop();
    }

    protected void ResolveHandles()
    {
        if (!m_Input && GetUApi()) { m_Input = GetUApi().GetInputByName("UAHollowCountryGrade"); }
        if (!m_Requester && PPEManagerStatic.GetPPEManager())
        {
            m_Requester = HCGradeRequester.Cast(PPERequesterBank.GetRequester(HCGradeRequester));
        }
    }

    void Update(float timeslice, bool allowInput)
    {
        // Sample edge-triggered input each frame; weather/PPE remain throttled.
        if (allowInput && m_Input && m_Input.LocalPress())
        {
            m_Percent += 10;
            if (m_Percent > 100) { m_Percent = 0; }
            GetGame().SetProfileString(PROFILE_KEY, m_Percent.ToString());
            GetGame().SaveProfile();
            if (m_Percent == 0) { Stop(); }
            Report();
            if (NotificationSystem.GetInstance())
            {
                NotificationSystem.AddNotificationExtended(3.0, "Hollow Country grade", m_Percent.ToString() + "%");
            }
        }
        if (m_Percent == 0) { return; }
        m_Elapsed += timeslice;
        if (m_Elapsed < 0.25) { return; }
        m_Elapsed = 0.0;
        ResolveHandles();
        PlayerBase viewer = PlayerBase.Cast(GetGame().GetPlayer());
        PPEManager manager = PPEManagerStatic.GetPPEManager();
        if (!viewer || !viewer.IsAlive() || viewer.IsUnconscious() || !m_Requester || !manager || m_Percent == 0)
        {
            Stop();
            return;
        }
        // Yield completely on the next bounded sample; native effects retain
        // priority even between samples. Resume with a one-second fade-in.
        if (manager.HCGradeNativeActive(m_Requester))
        {
            Stop();
            return;
        }
        Weather weather = GetGame().GetWeather();
        if (!weather || !GetGame().GetWorld())
        {
            Stop();
            return;
        }
        int year, month, day, hour, minute;
        GetGame().GetWorld().GetDate(year, month, day, hour, minute);
        float worldHour = hour + minute / 60.0;
        // Never let a smoothed previous daytime frame linger into night.
        if (worldHour <= 8.0 || worldHour >= 18.0)
        {
            Stop();
            return;
        }
        float weatherBlend = 0.25;
        if (!m_WeatherRead) { weatherBlend = 1.0; }
        m_Overcast = Math.Lerp(m_Overcast, weather.GetOvercast().GetActual(), weatherBlend);
        m_Fog = Math.Lerp(m_Fog, weather.GetFog().GetActual(), weatherBlend);
        m_Rain = Math.Lerp(m_Rain, weather.GetRain().GetActual(), weatherBlend);
        m_WeatherRead = true;
        m_Fade = Math.Clamp(m_Fade + 0.25, 0.0, 1.0);
        HCGradePolicy.Evaluate(worldHour, m_Overcast, m_Fog, m_Rain, m_Percent * 0.01 * m_Fade, m_Parameters);
        m_Requester.Apply(m_Parameters);
        Report();
    }

    // HC-27: count only the HC requester; never stop native PPE requesters.
    int HCHandleCount()
    {
        if (m_Requester && m_Requester.IsRequesterRunning()) { return 1; }
        return 0;
    }

    void Stop()
    {
        if (m_Requester && m_Requester.IsRequesterRunning()) { m_Requester.Stop(); }
        m_Fade = 0.0;
        m_WeatherRead = false;
        Report();
    }

    protected void Report()
    {
        bool running = false;
        if (m_Requester) { running = m_Requester.IsRequesterRunning(); }
        if (m_LastReportedPercent == m_Percent && m_LastReportedRunning == running) { return; }
        string state = "stopped";
        if (running) { state = "started"; }
        Print("[HollowCountry] V2 client grade intensity=" + m_Percent.ToString() + "% requester=" + state);
        m_LastReportedPercent = m_Percent;
        m_LastReportedRunning = running;
    }
}
