// #35: one Chernarus world-data owner; no module slot, polling or client hook.
// Native snapshot: ~/.cache/hollow-country/native-scripts/scripts-1.30.164289/
// 3_Game/WorldData.c:19/:36 weather/defaults, :427 SetupWeatherSettings,
// :251 WeatherOnBeforeChange, :414 CalculateVolFog, :561-601 settings fields;
// 4_World/Classes/Worlds/ChernarusPlus.c:82/:92/:468 matching overrides.
// 3_Game/Weather.c:38 GetActual, :49 Set, :74 SetLimits, :183 GetOvercast,
// :186 GetFog, :189 GetRain, :192 GetSnowfall, :199 GetWindDirection,
// :205 GetWindMagnitude, :219 SetStorm, :248 GetWindSpeed,
// :269 SetWindMaximumSpeed, :303 SetRainThresholds, :354 IsDynVolFogEnabled,
// :360/:370/:381 volumetric setters, :392 GetMissionWeather,
// :402 GetWeatherUpdateFrozen, :180 GetTime; :10-20 EWeatherPhenomenon.
// 3_Game/Global/Game.c:440 GetDayTime. See qualification for shared game APIs.
// 3_Game/CfgGameplayHandler.c:6 m_Data, :88-98 native synchronization;
// 3_Game/CfgGameplayDataJson.c:16-17 PlayerData/WorldsData,
// :89 disablePersonalLight, :192 lightingConfig.
// 3_Game/WorldLighting.c:12-22 presets 0 default/1 darknight (never applied); native client consumers:
// 4_World/Entities/ManBase/PlayerBase.c:6042-6058,
// 4_World/Entities/ManBase/PlayerBaseClient.c:39-55. No renderer authority invented.
modded class ChernarusPlusData
{
    protected bool m_HCAtmosphereStarted;

    protected void HCConfigureAtmosphereDefaults()
    {
        m_WeatherDefaultSettings.m_RainThreshold = 0.65;
        m_WeatherDefaultSettings.m_StormThreshold = 0.85;
        m_WeatherDefaultSettings.m_OvercastMinTime = 300;
        m_WeatherDefaultSettings.m_OvercastMaxTime = 300;
        m_WeatherDefaultSettings.m_OvercastMinLength = 300;
        m_WeatherDefaultSettings.m_OvercastMaxLength = 300;
        m_WeatherDefaultSettings.m_CalmAfterStormTimeMin = 1800;
        m_WeatherDefaultSettings.m_CalmAfterStormTimeMax = 1800;
        m_WeatherDefaultSettings.m_DefaultHeigthBias = 50;
        m_WeatherDefaultSettings.m_GlobalSuddenChance = 0;
        m_WeatherDefaultSettings.m_BadWeatherSuddenChance = 0;
    }

    bool HCStartAtmosphere()
    {
        if (!HCAtmosphereQualification.Enabled())
            return false;
        if (m_Weather.GetMissionWeather() || m_Weather.GetWeatherUpdateFrozen())
        {
            Print("[HollowCountry][Atmosphere] BLOCKED foreign mission weather/frozen controller; no atmosphere applied");
            return false;
        }
        if (m_HCAtmosphereStarted)
            return true;
        HCConfigureAtmosphereDefaults();
        m_HCAtmosphereStarted = true;
        m_Weather.GetOvercast().SetLimits(0, 1);
        m_Weather.GetFog().SetLimits(0, 0.25);
        m_Weather.GetRain().SetLimits(0, 0.9);
        m_Weather.GetSnowfall().SetLimits(0, 0);
        m_Weather.GetWindMagnitude().SetLimits(0, 16);
        m_Weather.GetWindDirection().SetLimits(-3.14159, 3.14159);
        m_Weather.SetWindMaximumSpeed(16);
        m_Weather.SetStorm(1, m_WeatherDefaultSettings.m_StormThreshold, 90);
        m_Weather.SetRainThresholds(m_WeatherDefaultSettings.m_RainThreshold, 1, 90);
        // Already-loaded native DTO, before joins: native sync owns distribution.
        // Preserve the existing native/operator seasonal temperature arrays.
        // Owner rule 2026-11-17: never dark nights. Config 0 is lighting_default
        // (WorldLighting.c:17); 1 is lighting_darknight (:21). Forced to 0 whatever
        // the operator value. Personal light (CfgGameplayDataJson.c:89) is not written.
        int previousLighting = CfgGameplayHandler.m_Data.WorldsData.lightingConfig;
        PrintFormat("[HollowCountry][Atmosphere] lightingConfig previous=%1; forcing 0 (bright nights, owner rule)", previousLighting);
        CfgGameplayHandler.m_Data.WorldsData.lightingConfig = 0;
        PrintFormat("[HollowCountry][Atmosphere] disablePersonalLight untouched; value %1", CfgGameplayHandler.m_Data.PlayerData.disablePersonalLight);
        if (!m_Weather.IsDynVolFogEnabled())
            Print("[HollowCountry][Atmosphere] PARTIAL world config lacks volumetric fog; normalized fog only; valley-fog acceptance PENDING");
        HCForecast(EWeatherPhenomenon.OVERCAST);
        HCForecast(EWeatherPhenomenon.RAIN);
        HCForecast(EWeatherPhenomenon.FOG);
        HCForecast(EWeatherPhenomenon.WIND_MAGNITUDE);
        HCForecast(EWeatherPhenomenon.WIND_DIRECTION);
        HCForecast(EWeatherPhenomenon.SNOWFALL);
        CalculateVolFog(m_Weather.GetOvercast().GetActual(), m_Weather.GetWindSpeed(), 300);
        Print("[HollowCountry][Atmosphere] EXPERIMENTAL ChernarusPlus script owner; bright-night lighting 0 forced, personal light untouched, night cloud/rain capped; other operator settings and seasonal curve retained; runtime acceptance PENDING");
        return true;
    }

    protected bool HCForecast(EWeatherPhenomenon type)
    {
        float daytime = GetGame().GetDayTime();
        float elapsed = m_Weather.GetTime();
        float cloud = m_Weather.GetOvercast().GetActual();
        // Lagging storm cloud at dusk must not drive night rain or wind.
        float cappedCloud = HCAtmospherePolicy.NightCapped(cloud, daytime);
        if (type == EWeatherPhenomenon.OVERCAST)
            m_Weather.GetOvercast().Set(HCAtmospherePolicy.CloudTarget(elapsed, daytime), 300, 300);
        else if (type == EWeatherPhenomenon.RAIN)
            m_Weather.GetRain().Set(HCAtmospherePolicy.RainTarget(cappedCloud), 180, 120);
        else if (type == EWeatherPhenomenon.FOG)
            m_Weather.GetFog().Set(HCAtmospherePolicy.FogTarget(daytime), 300, 0);
        else if (type == EWeatherPhenomenon.WIND_MAGNITUDE)
            m_Weather.GetWindMagnitude().Set(HCAtmospherePolicy.WindTarget(cappedCloud), 180, 120);
        else if (type == EWeatherPhenomenon.WIND_DIRECTION)
            m_Weather.GetWindDirection().Set(HCAtmospherePolicy.WindDirectionTarget(elapsed), 300, 300);
        else if (type == EWeatherPhenomenon.SNOWFALL)
            m_Weather.GetSnowfall().Set(0, 300, 300);
        else if (type != EWeatherPhenomenon.VOLFOG_HEIGHT_DENSITY && type != EWeatherPhenomenon.VOLFOG_DISTANCE_DENSITY && type != EWeatherPhenomenon.VOLFOG_HEIGHT_BIAS)
            return false;
        CalculateVolFog(cloud, m_Weather.GetWindSpeed(), 300);
        return true;
    }

    override bool WeatherOnBeforeChange(EWeatherPhenomenon type, float actual, float change, float time)
    {
        if (!HCAtmosphereQualification.Enabled())
            return super.WeatherOnBeforeChange(type, actual, change, time);
        if (!HCStartAtmosphere())
            return super.WeatherOnBeforeChange(type, actual, change, time);
        // Do not call the vanilla Chernarus driver for an owned phenomenon.
        return HCForecast(type);
    }

    protected override void CalculateVolFog(float lerpValue, float windMagnitude, float changeTime)
    {
        if (!HCAtmosphereQualification.Enabled() || !m_HCAtmosphereStarted)
        {
            super.CalculateVolFog(lerpValue, windMagnitude, changeTime);
            return;
        }
        if (!m_Weather.IsDynVolFogEnabled())
            return;
        float daytime = GetGame().GetDayTime();
        float transition = HCAtmospherePolicy.TransitionTime(changeTime);
        m_Weather.SetDynVolFogDistanceDensity(HCAtmospherePolicy.DistanceDensity(daytime, lerpValue, windMagnitude), transition);
        m_Weather.SetDynVolFogHeightDensity(0.95, transition);
        m_Weather.SetDynVolFogHeightBias(HCAtmospherePolicy.HeightBias(daytime), transition);
    }
}
