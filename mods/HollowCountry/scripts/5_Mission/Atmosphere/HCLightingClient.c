// LC-T104 / LC-ATM-04, EXP-A2. Installed native scripts-1.30.164289:
// 3_Game/WorldLighting.c:12-29 SetGlobalLighting (0 = bright default);
// 3_Game/Global/World.c:53 IsNight, :101 LoadNewLightingCfg,
// :105 LoadUserLightingCfg(path,name) (FIRST ITEM ONLY), :110 SetUserLightingLerp;
// 3_Game/Global/Game.c:440 GetDayTime, :931 GetWorld, :944 GetPlayer,
// :1093 GetMission, :1125 IsDedicatedServer, :1371 GetWeather, :1550 GetCallQueue;
// 3_Game/Weather.c:38 GetActual, :183 GetOvercast, :186 GetFog, :189 GetRain;
// 3_Game/gameplay.c:747 GetWorldLighting; 2_GameLib/tools.c:61 CallLater, :65 Remove;
// 3_Game/PPEManager/PPERequesterBank.c:42 REQ_UNDERGROUND, :236 IsRequesterRunning;
// 4_World/Entities/ManBase/PlayerBase.c:2848 GetUndergroundPresence;
// :3925 IsUnconscious; 3_Game/Entities/Object.c:517 IsAlive;
// 4_World/Classes/UndergroundHandlerClient.c:39 loads native table, :315-326
// keeps its requester alive until exit fade/handler teardown, :329-341 lerp;
// 5_Mission/mission/missionGameplay.c:102 OnInit, :266 OnMissionFinish;
// 1_Core/proto/EnDebug.c:96 Print, 1_Core/proto/EnConvert.c:115 float.ToString,
// 1_Core/proto/EnScript.c:94 inherited Class.Cast (PlayerBase.Cast).
// PBO path/schema inspected read-only in installed addons/dz.pbo:
// lighting/lighting_underground.txt, LightingNew/<name>. All HC values authored.
// No sky preset, view distance, weather mutation or personal-light changes.
// Native load returns void: a call is NOT evidence that a table parsed/rendered.
// The authored-table loader HCLoadLightingTable is a modded WorldLighting in
// 3_Game/Atmosphere/HCWorldLighting.c: Enforce cannot mod a 3_Game class here.

class HCLightingClient
{
    protected WorldLighting m_HCLighting;
    protected bool m_HCRunning;
    protected bool m_HCOwnsSlot;
    protected string m_HCLoaded = "";
    protected float m_HCWeight;
    protected string m_HCLoggedName = "";
    protected float m_HCLoggedWeight = -1.0;
    protected float m_HCLogSeconds = 60.0;
    // HC-51 shares the existing 3-second callback; one scalar item, no scan,
    // save job or cursor. Off/underground/death cleanup never waits on a budget.
    protected ref HCUnitBudget m_HCSeasonUnits = new HCUnitBudget;
    protected ref HCWorkBudget m_HCSeasonWork = new HCWorkBudget;

    void HCLightingClient(WorldLighting lighting)
    {
        m_HCLighting = lighting;
    }

    void Start()
    {
        if (m_HCRunning) return;
        if (!m_HCLighting)
        {
            Print("[HollowCountry] V2 client lighting not started: world_lighting_unavailable runtime=PENDING");
            return;
        }
        if (GetGame() && !GetGame().IsDedicatedServer())
        {
            m_HCRunning = true;
            // HCClientPresentation creates this owner under the effective GRADE bit.
            GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(Tick, 3000, true);
        }
    }

    protected void LogChange(string name, float weight)
    {
        if (m_HCLogSeconds < 60) return;
        if (name == m_HCLoggedName && weight == m_HCLoggedWeight) return;
        Print("[HollowCountry] V2 client lighting blend=" + name + " weight=" + weight.ToString());
        m_HCLoggedName = name;
        m_HCLoggedWeight = weight;
        m_HCLogSeconds = 0;
    }

    protected void Restore()
    {
        if (m_HCOwnsSlot && GetGame() && GetGame().GetWorld())
            GetGame().GetWorld().SetUserLightingLerp(0);
        m_HCOwnsSlot = false;
        m_HCLoaded = "";
        m_HCWeight = 0;
    }

    void Tick()
    {
        if (!m_HCRunning || !GetGame() || !GetGame().GetWorld()) return;
        m_HCLogSeconds = m_HCLogSeconds + 3;
        if (m_HCLogSeconds > 60) m_HCLogSeconds = 60;
        PlayerBase viewer = PlayerBase.Cast(GetGame().GetPlayer());
        if (HCCellarsClient.HCVisualActive())
        {
            m_HCOwnsSlot = false;
            m_HCLoaded = "";
            m_HCWeight = 0;
            LogChange("cellar_fallback", 0);
            return;
        }
        if (!viewer || !GetGame().GetWeather())
        {
            Restore();
            LogChange("vanilla", 0);
            return;
        }
        // Underground loads its own table on entry and writes lerp every frame.
        // Do not clear that lerp, reload a table, or interrupt its exit fade.
        if (viewer.GetUndergroundPresence() != EUndergroundPresence.NONE || PPERequesterBank.IsRequesterRunning(PPERequesterBank.REQ_UNDERGROUND))
        {
            m_HCOwnsSlot = false;
            m_HCLoaded = "";
            m_HCWeight = 0;
            LogChange("native_underground", 0);
            return;
        }
        if (!viewer.IsAlive() || viewer.IsUnconscious())
        {
            Restore();
            LogChange("viewer_inactive", 0);
            return;
        }
        m_HCSeasonUnits.HCReset(1);
        m_HCSeasonWork.HCReset(1);
        if (!m_HCSeasonUnits.HCTake(1) || !m_HCSeasonWork.HCContinue())
        {
            Restore();
            return;
        }
        float hour = GetGame().GetDayTime();
        float cloud = GetGame().GetWeather().GetOvercast().GetActual();
        float rain = GetGame().GetWeather().GetRain().GetActual();
        float fog = GetGame().GetWeather().GetFog().GetActual();
        float daylight = HCLightingBlend.Daylight(hour);
        string desired = HCLightingBlend.Name(hour, cloud, rain, fog);
        float target = HCLightingBlend.Weight(hour, cloud, rain, fog);
        // HC-51: one bounded server snapshot, no local phase extrapolation or
        // second table/lerp writer. Stronger existing weather/dusk presentation
        // keeps precedence. The same fade-to-zero swap below handles seasons.
        string season = HCSeasonVisualClient.HCGetPhase();
        float seasonalWeight = HCLightingBlend.HCSeasonWeight(season, hour);
        if (seasonalWeight > target)
        {
            desired = HCLightingBlend.HCSeasonName(season, hour);
            target = seasonalWeight;
        }
        // Native seasonal night can begin before the weather policy's 20:00.
        // Review P1: also require the sun to be up and clear of the horizon, so no
        // table can lift twilight or night above vanilla. World.c:50,52; Environment.c:685.
        float sunUp = GetGame().GetWorld().GetSunOrMoon();
        vector sunDir = GetGame().GetWorld().GetSunOrMoonDirection();
        // Vanilla Environment.c:685 casts toward the sun along -direction, so the
        // vector points away from the sun and elevation is its negated y.
        float elevation = -sunDir[1];
        if (sunUp < 0.5 || elevation < 0.10)
        {
            daylight = 0;
            target = 0;
            desired = "vanilla";
        }
        else
        {
            float elevationScale = Math.Clamp((elevation - 0.10) / 0.25, 0, 1);
            target = target * elevationScale;
        }
        if (GetGame().GetWorld().IsNight())
        {
            daylight = 0;
            target = 0;
            desired = "vanilla";
        }
        // Only one user table exists. Fade the old one to zero before swapping,
        // then ramp the new one up, at most 0.10 per three-second callback.
        if (desired != m_HCLoaded && m_HCWeight > 0) target = 0;
        if (m_HCWeight == 0 && desired != "vanilla" && desired != m_HCLoaded)
        {
            m_HCLighting.HCLoadLightingTable(desired);
            m_HCLoaded = desired;
        }
        m_HCWeight = HCLightingBlend.Step(m_HCWeight, target, daylight);
        if (m_HCWeight > 0 || m_HCOwnsSlot)
        {
            GetGame().GetWorld().SetUserLightingLerp(m_HCWeight);
            m_HCOwnsSlot = m_HCWeight > 0;
        }
        string applied = m_HCLoaded;
        if (m_HCWeight == 0) applied = "vanilla";
        LogChange(applied, m_HCWeight);
    }

    void Stop()
    {
        m_HCRunning = false;
        if (GetGame()) GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).Remove(Tick);
        Restore();
        m_HCLighting = null;
    }
}
