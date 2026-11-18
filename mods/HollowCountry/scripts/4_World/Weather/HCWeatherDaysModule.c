// #61 / EXP-A2: source implemented; native compile and two-client visibility
// acceptance pending. The SAME ChernarusPlusData owner as v1 writes every knob.
// V2 replaces its forecast selection while active; no mission XML/config edits,
// mission-weather takeover, frozen-state bypass, lighting table or client loop.
// Installed snapshot: ~/.cache/hollow-country/native-scripts/scripts-1.30.164289/
// 3_Game/Weather.c:38 GetActual, :49 Set, :65-74 SetLimits holds actual in range,
// :180 GetTime,
// :183 GetOvercast, :186 GetFog, :189 GetRain, :192 GetSnowfall,
// :199 GetWindDirection, :205 GetWindMagnitude, :219 SetStorm,
// :248 GetWindSpeed, :269 SetWindMaximumSpeed, :303 SetRainThresholds,
// :354 IsDynVolFogEnabled, :360/:370/:381 volumetric setters,
// :392 GetMissionWeather, :402 GetWeatherUpdateFrozen;
// :126-145 native phenomenon -> WorldData.WeatherOnBeforeChange;
// :154-159 Overcast/Fog/Rain/WindMagnitude alias WeatherPhenomenon.
// 3_Game/WorldData.c:19 m_Weather, :251 WeatherOnBeforeChange, :414 CalculateVolFog;
// 4_World/Classes/Worlds/ChernarusPlus.c:92/:468 matching overrides.
// 3_Game/Global/Game.c:440 GetDayTime, :1093 GetMission, :1120 IsServer;
// 3_Game/gameplay.c:742 Mission.GetWorldData; 1_Core/proto/EnScript.c:94 Cast;
// 1_Core/proto/EnDebug.c:96 Print; 1_Core/proto/EnString.c:526 string.Format;
// 1_Core/proto/EnMath.c:427 Math.Floor.
// Existing HCGroupClock.Utc uses 1_Core/proto/EnSystem.c:76/:100 UTC time/date.
// Existing v1 lighting owner uses CfgGameplayHandler.c:6 m_Data and
// CfgGameplayDataJson.c:192 lightingConfig (0 = WorldLighting.c:17 default).
class HCWeatherDaysModule : HCModule
{
    protected ChernarusPlusData m_Data;

    override string GetName() { return "WeatherDays"; }
    override bool IsEnabled(HCSettings settings) { return settings.EnableGrade; }

    override void OnStart(HCSettings settings)
    {
        Print(HCV2Admission.Line("WeatherDays", true, "EXP-A2", HCV2Gates.Qualified("EXP-A2")));
        if (!GetGame() || !GetGame().IsServer()) return;
        // Respect the existing weather owner's explicit off switch as well.
        if (!settings.EnableAtmosphere)
        {
            Print("[HollowCountry] V2 weather blocked: EnableAtmosphere is off");
            return;
        }
        if (!HCAtmosphereQualification.SupportedWorld() || !HCAtmosphereQualification.DelegatedWeather()) return;
        // Review P1: honour the v1 atmosphere admission (on by default; the
        // acceptance/atmosphere.disable marker turns both v1 and V2 weather off).
        if (!HCAtmosphereQualification.Qualified() && !HCAtmosphereQualification.LocalOptIn())
        {
            Print("[HollowCountry] V2 weather blocked: atmosphere opted out by the operator; vanilla weather retained");
            return;
        }
        Mission mission = GetGame().GetMission();
        if (!mission) return;
        m_Data = ChernarusPlusData.Cast(mission.GetWorldData());
        if (m_Data) m_Data.HCBeginWeatherDays();
    }

    override void OnTick(float deltaTime)
    {
        if (m_Data) m_Data.HCTickWeatherDays();
    }

    override void OnStop()
    {
        if (m_Data) m_Data.HCEndWeatherDays();
        m_Data = null;
    }
}

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        Register(new HCWeatherDaysModule);
    }
}

modded class ChernarusPlusData
{
    protected bool m_HCWeatherDaysActive;
    protected bool m_HCWeatherDaysSuspended;
    protected bool m_HCWeatherWasWet;
    protected int m_HCWeatherDay = -1;
    protected int m_HCWeatherSlot = -1;
    protected float m_HCWeatherLastHour;
    protected float m_HCWeatherCalm;
    protected string m_HCWeatherProfile;

    void HCBeginWeatherDays()
    {
        if (m_HCWeatherDaysActive || !m_Weather) return;
        if (HCGroupClock.Utc() < 1)
        {
            Print("[HollowCountry] V2 weather blocked: invalid UTC clock");
            return;
        }
        if (m_Weather.GetMissionWeather() || m_Weather.GetWeatherUpdateFrozen())
        {
            Print("[HollowCountry] V2 weather blocked: foreign mission weather/frozen controller");
            return;
        }
        // Remove v1's queued check before handing its owner to this module tick.
        HCStopAtmosphere();
        HCConfigureAtmosphereDefaults();
        m_HCWeatherDaysActive = true;
        m_HCWeatherDaysSuspended = false;
        m_HCAtmosphereStarted = true;
        m_HCWeatherDay = -1;
        m_HCWeatherSlot = -1;
        m_HCWeatherProfile = "";
        m_HCWeatherCalm = 0;
        m_HCWeatherWasWet = false;
        m_HCWeatherLastHour = GetGame().GetDayTime();
        HCApplyNightLimits(true);
        m_Weather.GetRain().SetLimits(0, 0.9);
        m_Weather.GetSnowfall().SetLimits(0, 0);
        m_Weather.GetWindMagnitude().SetLimits(0, 16);
        m_Weather.GetWindDirection().SetLimits(-3.14159, 3.14159);
        m_Weather.SetWindMaximumSpeed(16);
        m_Weather.SetStorm(1, m_WeatherDefaultSettings.m_StormThreshold, 90);
        m_Weather.SetRainThresholds(m_WeatherDefaultSettings.m_RainThreshold, 1, 90);
        // Same bright-night baseline and owner as v1; personal light untouched.
        CfgGameplayHandler.m_Data.WorldsData.lightingConfig = 0;
        HCTickWeatherDays();
    }

    // The old lifecycle may request startup after modules start. Do not start a
    // second queue or seed the v1 forecast over the selected V2 profile.
    override bool HCStartAtmosphere()
    {
        if (m_HCWeatherDaysActive) return true;
        return super.HCStartAtmosphere();
    }

    void HCEndWeatherDays()
    {
        if (!m_HCWeatherDaysActive) return;
        m_HCWeatherDaysActive = false;
        HCStopAtmosphere();
    }

    void HCTickWeatherDays()
    {
        if (!m_HCWeatherDaysActive || !GetGame() || !GetGame().IsServer()) return;
        if (m_Weather.GetMissionWeather() || m_Weather.GetWeatherUpdateFrozen())
        {
            if (!m_HCWeatherDaysSuspended)
                Print("[HollowCountry] V2 weather suspended: foreign mission weather/frozen controller");
            m_HCWeatherDaysSuspended = true;
            return;
        }
        int utc = HCGroupClock.Utc();
        if (utc < 1) return;
        // Integer division keeps the day exact (no binary32 rounding into
        // tomorrow near UTC midnight); '%' inside a float expression does not compile natively.
        int day = utc / 86400;
        float hour = GetGame().GetDayTime();
        float gameHours = hour - m_HCWeatherLastHour;
        if (gameHours < 0) gameHours += 24;
        m_HCWeatherLastHour = hour;
        float rain = m_Weather.GetRain().GetActual();
        float cloud = m_Weather.GetOvercast().GetActual();
        m_HCWeatherCalm = HCWeatherDays.CalmRemaining(m_HCWeatherCalm, gameHours, m_HCWeatherWasWet, rain, cloud);
        if (rain > 0.05 || cloud >= 0.85) m_HCWeatherWasWet = true;
        if (rain <= 0.02 && cloud < 0.85) m_HCWeatherWasWet = false;
        string profile = HCWeatherDays.Profile(day, hour, m_HCWeatherCalm);
        bool changed = day != m_HCWeatherDay || profile != m_HCWeatherProfile;
        if (changed)
            Print(string.Format("[HollowCountry] V2 weather day=%1 profile=%2", day, profile));
        m_HCWeatherDay = day;
        m_HCWeatherProfile = profile;
        bool boundary = HCAtmospherePolicy.IsNight(hour) != m_HCNightLimited;
        HCApplyNightLimits(false);
        // Native holds actual within limits. Lowering the cap through 07..09
        // prevents a long native transition leaving dense fog past 09:00 even
        // with accelerated world time. No other owner writes normalized fog.
        float fog = HCWeatherDays.FogTarget(day, hour, m_HCWeatherCalm);
        m_Weather.GetFog().SetLimits(0, fog);
        int slot = Math.Floor(hour * 4);
        if (changed || boundary || slot != m_HCWeatherSlot || m_HCWeatherDaysSuspended)
        {
            m_HCWeatherSlot = slot;
            m_Weather.GetFog().Set(fog, 30, 0);
            if (changed || boundary || m_HCWeatherDaysSuspended)
            {
                HCWeatherDaysForecast(EWeatherPhenomenon.OVERCAST);
                HCWeatherDaysForecast(EWeatherPhenomenon.RAIN);
                HCWeatherDaysForecast(EWeatherPhenomenon.WIND_MAGNITUDE);
                HCWeatherDaysForecast(EWeatherPhenomenon.WIND_DIRECTION);
                HCWeatherDaysForecast(EWeatherPhenomenon.SNOWFALL);
            }
            CalculateVolFog(cloud, m_Weather.GetWindSpeed(), 30);
        }
        m_HCWeatherDaysSuspended = false;
    }

    protected bool HCWeatherDaysForecast(EWeatherPhenomenon type)
    {
        float hour = GetGame().GetDayTime();
        float cloud = m_Weather.GetOvercast().GetActual();
        if (type == EWeatherPhenomenon.OVERCAST)
            m_Weather.GetOvercast().Set(HCWeatherDays.CloudTarget(m_HCWeatherProfile, m_Weather.GetTime(), hour), 300, 300);
        else if (type == EWeatherPhenomenon.RAIN)
            m_Weather.GetRain().Set(HCWeatherDays.RainTarget(m_HCWeatherProfile, cloud, hour), 180, 120);
        else if (type == EWeatherPhenomenon.WIND_MAGNITUDE)
            m_Weather.GetWindMagnitude().Set(HCWeatherDays.WindTarget(m_HCWeatherProfile, cloud, hour), 180, 120);
        else if (type == EWeatherPhenomenon.FOG)
            m_Weather.GetFog().Set(HCWeatherDays.FogTarget(m_HCWeatherDay, hour, m_HCWeatherCalm), 30, 0);
        else if (type == EWeatherPhenomenon.WIND_DIRECTION)
            m_Weather.GetWindDirection().Set(HCAtmospherePolicy.WindDirectionTarget(m_Weather.GetTime()), 300, 300);
        else if (type == EWeatherPhenomenon.SNOWFALL)
            m_Weather.GetSnowfall().Set(0, 300, 300);
        else if (type != EWeatherPhenomenon.VOLFOG_HEIGHT_DENSITY && type != EWeatherPhenomenon.VOLFOG_DISTANCE_DENSITY && type != EWeatherPhenomenon.VOLFOG_HEIGHT_BIAS)
            return false;
        CalculateVolFog(cloud, m_Weather.GetWindSpeed(), 30);
        return true;
    }

    override bool WeatherOnBeforeChange(EWeatherPhenomenon type, float actual, float change, float time)
    {
        if (!m_HCWeatherDaysActive) return super.WeatherOnBeforeChange(type, actual, change, time);
        if (!GetGame().IsServer() || m_Weather.GetMissionWeather() || m_Weather.GetWeatherUpdateFrozen()) return false;
        return HCWeatherDaysForecast(type);
    }

    protected override void CalculateVolFog(float lerpValue, float windMagnitude, float changeTime)
    {
        if (!m_HCWeatherDaysActive)
        {
            super.CalculateVolFog(lerpValue, windMagnitude, changeTime);
            return;
        }
        if (m_Weather.GetMissionWeather() || m_Weather.GetWeatherUpdateFrozen() || !m_Weather.IsDynVolFogEnabled()) return;
        float hour = GetGame().GetDayTime();
        // V2's selected mornings alone get extra valley density. Retain the v1
        // wind damping, and immediately remove the extra term outside mornings.
        float density = HCAtmospherePolicy.DistanceDensity(12, lerpValue, windMagnitude);
        float extra = HCWeatherDays.FogTarget(m_HCWeatherDay, hour, m_HCWeatherCalm) - 0.04;
        m_Weather.SetDynVolFogDistanceDensity(density + extra * 0.12, 0);
        m_Weather.SetDynVolFogHeightDensity(0.95, 0);
        m_Weather.SetDynVolFogHeightBias(50 + extra * 70, 0);
    }
}
