// #61 / EXP-A2: source implemented; native compile and two-client visibility
// acceptance pending. The SAME ChernarusPlusData owner as v1 writes every knob.
// V2 replaces its forecast selection while active; no mission XML/config edits,
// mission-weather takeover, frozen-state bypass, lighting table or client loop.
// Installed snapshot: ~/.cache/hollow-country/native-scripts/scripts-1.30.164289/
// 3_Game/Weather.c:38 GetActual, :49 Set, :61 GetLimits(out float, out float),
// :65-74 SetLimits holds actual in range,
// :180 GetTime,
// :183 GetOvercast, :186 GetFog, :189 GetRain, :192 GetSnowfall,
// :199 GetWindDirection, :205 GetWindMagnitude, :219 SetStorm,
// :248 GetWindSpeed, :269 SetWindMaximumSpeed, :303 SetRainThresholds,
// :321 SetSnowfallThresholds(float tMin, float tMax, float tTime);
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
    protected ref HCOperationalStatus m_Status = new HCOperationalStatus;

    override HCOperationalStatus HCGetOperationalStatus() { return m_Status; }

    protected void HCUpdateOperationalStatus()
    {
        if (!m_Data) { return; }
        if (!m_Data.HCWeatherDaysAuthority()) { m_Status.HCPublish("refused", "WEATHER_OWNER_NOT_ADMITTED"); }
        else if (m_Data.HCSeasonPhaseCode() < 0) { m_Status.HCPublish("off", "HC6_NOT_ADMITTED"); }
        else { m_Status.HCPublish("ready", "season_snapshot_owned_runtime_pending"); }
    }

    override string GetName() { return "WeatherDays"; }
    override bool IsEnabled(HCSettings settings) { return settings.EnableGrade; }

    override void OnStart(HCSettings settings)
    {
        m_Status.HCPublish("refused", "WEATHER_OWNER_NOT_ADMITTED");
        Print(HCV2Admission.Line("WeatherDays", true, "EXP-A2", HCV2Gates.Qualified("EXP-A2")));
        if (!GetGame() || !GetGame().IsServer()) return;
        // Respect the existing weather owner's explicit off switch as well.
        if (!settings.EnableAtmosphere)
        {
            m_Status.HCPublish("off", "EnableAtmosphere_off");
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
        HCUpdateOperationalStatus();
    }

    override void OnTick(float deltaTime)
    {
        if (m_Data) m_Data.HCTickWeatherDays();
        HCUpdateOperationalStatus();
    }

    override void OnStop()
    {
        if (m_Data) m_Data.HCEndWeatherDays();
        m_Data = null;
        HCSeasonSnapshotRPC.HCPublish(-1);
        m_Status.HCPublish("off", "module_stop");
    }

    // Admin test kit: read-only metrics and one bounded override request. The
    // override only selects which seeded day this same owner's tick reads.
    string HCAdminCounts()
    {
        if (!m_Data) { return "active=n/a override=n/a"; }
        return m_Data.HCAdminWeatherCounts();
    }

    bool HCAdminWeather(int code, out string reason)
    {
        reason = "weather-days-inactive; needs EnableGrade and EnableAtmosphere, otherwise vanilla weather is retained";
        if (!m_Data) { return false; }
        return m_Data.HCAdminWeather(code, reason);
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
    protected bool m_HCSnowLimitsWritten;
    protected float m_HCSnowLimit;
    protected bool m_HCWeatherWasWet;
    protected int m_HCWeatherDay = -1;
    protected int m_HCWeatherSlot = -1;
    protected string m_HCWeatherPhase = "unavailable";
    protected int m_HCReportedPhase = -2;
    protected float m_HCWeatherLastHour;
    protected float m_HCWeatherCalm;
    protected string m_HCWeatherProfile;
    // Admin override: a seeded day within 64 days of the real one, honoured
    // for 1800 server seconds, then dropped by this same tick.
    protected int m_HCWeatherAdminDay = -1;
    protected float m_HCWeatherAdminUntil;
    // HC-6 visual season clock; this weather owner starts, ticks and stops it.
    protected ref HCVisualSeasons m_HCVisualSeasons;

    // The HC-6 clock can keep running under a foreign controller, but its
    // phase MUST NOT authorize weather or client grades while authority is lost.
    bool HCWeatherDaysAuthority()
    {
        if (!m_HCWeatherDaysActive || !m_Weather || !GetGame() || !GetGame().IsServer()) { return false; }
        return !m_Weather.GetMissionWeather() && !m_Weather.GetWeatherUpdateFrozen();
    }

    int HCSeasonPhaseCode()
    {
        if (!HCWeatherDaysAuthority() || !m_HCVisualSeasons) { return -1; }
        if (!m_HCVisualSeasons.HCActive()) { return -1; }
        return m_HCVisualSeasons.HCPhase();
    }

    protected void HCPublishSeason()
    {
        int phaseCode = HCSeasonPhaseCode();
        HCSeasonSnapshotRPC.HCPublish(phaseCode);
        if (phaseCode == m_HCReportedPhase) { return; }
        m_HCReportedPhase = phaseCode;
        float snow = 0.0;
        if (m_Weather) { snow = m_Weather.GetSnowfall().GetActual(); }
        Print(HCWeatherDays.HCSeasonLine(HCSeasonVisualPolicy.HCPhaseName(phaseCode), snow, HCWeatherDaysAuthority()));
    }

    // HC-50 read-only seam for the one-shot white-terrain boot receipt.
    HCVisualSeasons HCWinterTerrainSeasons() { return m_HCVisualSeasons; }

    string HCAdminWeatherCounts()
    {
        if (!m_HCWeatherDaysActive) { return "active=0 override=n/a"; }
        int overrideActive = 0;
        if (m_HCWeatherAdminDay >= 0) { overrideActive = 1; }
        return "active=1 day=" + m_HCWeatherDay.ToString() + " profile=" + m_HCWeatherProfile + " calm_hours=" + m_HCWeatherCalm.ToString() + " override=" + overrideActive.ToString();
    }

    // code 0 clears; 1 plain, 2 calm, 3 fog (05:00-09:00 game time), 4 bad
    // (daytime). Picks the first day in [today, today+63] whose Seed % 5 draws
    // the requested profile, so Profile(), FogTarget() and the forecasts all
    // run unmodified.
    bool HCAdminWeather(int code, out string reason)
    {
        reason = "weather-code-0-clear-1-plain-2-calm-3-fog-4-bad";
        if (code < 0 || code > 4) { return false; }
        reason = "weather-days-inactive; needs EnableGrade and EnableAtmosphere, otherwise vanilla weather is retained";
        if (!m_HCWeatherDaysActive || !GetGame() || !GetGame().IsServer()) { return false; }
        // A foreign controller (COT, mission weather) owns the sky; the tick is
        // suspended, so an override would report success and change nothing.
        reason = "foreign-weather-controller-active";
        if (m_HCWeatherDaysSuspended || !m_Weather) { return false; }
        if (m_Weather.GetMissionWeather() || m_Weather.GetWeatherUpdateFrozen()) { return false; }
        if (code == 0)
        {
            m_HCWeatherAdminDay = -1;
            m_HCWeatherAdminUntil = 0;
            m_HCWeatherCalm = 0;
            reason = "weather-override-cleared; the real day profile resumes";
            return true;
        }
        int utc = HCGroupClock.Utc();
        reason = "weather-clock-unavailable";
        if (utc < 1) { return false; }
        int baseDay = utc / 86400;
        int chosen = -1;
        for (int offset = 0; offset < 64; offset++)
        {
            int seed = HCWeatherDays.Seed(baseDay + offset);
            if (seed < 0) { break; }
            int bucket = seed % 5;
            bool wanted = bucket >= 3;
            if (code == 4) { wanted = bucket == 0; }
            else if (code == 3) { wanted = bucket == 1 || bucket == 2; }
            if (wanted)
            {
                chosen = baseDay + offset;
                break;
            }
        }
        reason = "no-matching-seed-day-within-64-days";
        if (chosen < 0) { return false; }
        string profileName = "plain";
        if (code == 2) { profileName = "calm"; }
        else if (code == 3) { profileName = "fog"; }
        else if (code == 4) { profileName = "bad"; }
        m_HCWeatherAdminDay = chosen;
        m_HCWeatherAdminUntil = GetGame().GetTickTime() + 1800;
        m_HCWeatherCalm = 0;
        if (code == 2) { m_HCWeatherCalm = 3; }
        reason = "weather-override profile=" + profileName + " for 1800s; fog shows 05:00-09:00 game time, bad shows by day, 0 clears";
        return true;
    }

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
        if (!m_HCVisualSeasons) { m_HCVisualSeasons = new HCVisualSeasons; }
        m_HCVisualSeasons.HCStart(true);
        HCWinterTerrainAdmission.HCReport(m_HCVisualSeasons); // HC-50: one fail-closed receipt per start
        m_HCWeatherDay = -1;
        m_HCWeatherSlot = -1;
        m_HCWeatherPhase = "unavailable";
        m_HCReportedPhase = -2;
        m_HCWeatherProfile = "";
        m_HCWeatherCalm = 0;
        m_HCWeatherWasWet = false;
        m_HCWeatherLastHour = GetGame().GetDayTime();
        HCApplyNightLimits(true);
        m_Weather.GetRain().SetLimits(0.0, 0.9);
        HCWriteSnowLimits(0.0);
        // Native Weather.c:321, default overcast range/stopping time :309-311.
        // Falling snow keeps stock wetness effects; no extra thermal owner.
        m_Weather.SetSnowfallThresholds(HCSeasonVisualPolicy.SNOW_CLOUD_THRESHOLD, 1.0, 30.0);
        m_Weather.GetWindMagnitude().SetLimits(0.0, 16.0);
        m_Weather.GetWindDirection().SetLimits(-3.14159, 3.14159);
        m_Weather.SetWindMaximumSpeed(16.0);
        m_Weather.SetStorm(1.0, m_WeatherDefaultSettings.m_StormThreshold, 90.0);
        m_Weather.SetRainThresholds(m_WeatherDefaultSettings.m_RainThreshold, 1.0, 90.0);
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

    protected void HCWriteSnowLimits(float snowLimit)
    {
        m_Weather.GetSnowfall().SetLimits(0.0, snowLimit);
        m_HCSnowLimit = snowLimit;
        m_HCSnowLimitsWritten = true;
    }

    protected void HCReleaseSnowLimits()
    {
        if (!m_HCSnowLimitsWritten) { return; }
        // Relinquish once. A foreign owner may have written before this same
        // tick; compare both native limits before clearing our seasonal cap.
        m_HCSnowLimitsWritten = false;
        if (!m_Weather) { return; }
        float snowMin;
        float snowMax;
        m_Weather.GetSnowfall().GetLimits(snowMin, snowMax);
        if (snowMin == 0.0 && snowMax == m_HCSnowLimit)
        {
            m_Weather.GetSnowfall().SetLimits(0.0, 0.0);
        }
    }

    void HCEndWeatherDays()
    {
        if (!m_HCWeatherDaysActive) return;
        HCReleaseSnowLimits();
        m_HCWeatherDaysActive = false;
        HCPublishSeason();
        if (m_HCVisualSeasons) { m_HCVisualSeasons.HCStop(); }
        HCStopAtmosphere();
    }

    void HCTickWeatherDays()
    {
        if (!m_HCWeatherDaysActive || !GetGame() || !GetGame().IsServer()) return;
        // The season clock counts server running time, so it ticks even while a
        // foreign controller holds the sky.
        if (m_HCVisualSeasons) { m_HCVisualSeasons.HCTick(); }
        HCPublishSeason();
        if (m_Weather.GetMissionWeather() || m_Weather.GetWeatherUpdateFrozen())
        {
            if (!m_HCWeatherDaysSuspended)
            {
                HCReleaseSnowLimits();
                Print("[HollowCountry] V2 weather suspended: foreign mission weather/frozen controller");
            }
            m_HCWeatherDaysSuspended = true;
            return;
        }
        int utc = HCGroupClock.Utc();
        if (utc < 1) return;
        // Integer division keeps the day exact (no binary32 rounding into
        // tomorrow near UTC midnight); '%' inside a float expression does not compile natively.
        int day = utc / 86400;
        if (m_HCWeatherAdminDay >= 0)
        {
            if (GetGame().GetTickTime() < m_HCWeatherAdminUntil) { day = m_HCWeatherAdminDay; }
            else
            {
                m_HCWeatherAdminDay = -1;
                m_HCWeatherCalm = 0;
                Print("[HollowCountry] V2 weather admin override expired; real day profile resumes");
            }
        }
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
        int seasonCode = HCSeasonPhaseCode();
        string phase = HCSeasonVisualPolicy.HCPhaseName(seasonCode);
        bool changed = day != m_HCWeatherDay || profile != m_HCWeatherProfile || phase != m_HCWeatherPhase;
        m_HCWeatherPhase = phase;
        if (changed)
            Print(string.Format("[HollowCountry] V2 weather day=%1 profile=%2", day, profile));
        m_HCWeatherDay = day;
        m_HCWeatherProfile = profile;
        bool boundary = HCAtmospherePolicy.IsNight(hour) != m_HCNightLimited;
        HCApplyNightLimits(false);
        // This remains the sole normalized fog writer. Fade the seasonal
        // target at dawn/dusk and preserve observed fog inside the native cap.
        float fog = HCWeatherDays.HCSeasonFog(phase, day, hour, m_HCWeatherCalm);
        float actual = m_Weather.GetFog().GetActual();
        // Never clamp observed stock fog down to a seasonal target. Native
        // forecast interpolation performs the transition instead of a cap pop.
        // With no season phase (HC-27 grade or seasons off) keep the v1 hard
        // cap so a long native fog transition cannot linger past 09:00.
        float fogCap = fog;
        if (seasonCode >= 0) fogCap = Math.Max(fog, actual);
        m_Weather.GetFog().SetLimits(0.0, fogCap);
        int slot = Math.Floor(hour * 4);
        if (changed || boundary || slot != m_HCWeatherSlot || m_HCWeatherDaysSuspended)
        {
            m_HCWeatherSlot = slot;
            float snowLimit = 0.0;
            if (phase == "winter") { snowLimit = HCSeasonVisualPolicy.WINTER_SNOWFALL; }
            HCWriteSnowLimits(snowLimit);
            m_Weather.GetFog().Set(fog, 30.0, 0.0);
            if (changed || boundary || m_HCWeatherDaysSuspended)
            {
                HCWeatherDaysForecast(EWeatherPhenomenon.OVERCAST);
                HCWeatherDaysForecast(EWeatherPhenomenon.RAIN);
                HCWeatherDaysForecast(EWeatherPhenomenon.WIND_MAGNITUDE);
                HCWeatherDaysForecast(EWeatherPhenomenon.WIND_DIRECTION);
                HCWeatherDaysForecast(EWeatherPhenomenon.SNOWFALL);
            }
            CalculateVolFog(cloud, m_Weather.GetWindSpeed(), 30.0);
        }
        m_HCWeatherDaysSuspended = false;
    }

    protected bool HCWeatherDaysForecast(EWeatherPhenomenon type)
    {
        float hour = GetGame().GetDayTime();
        float cloud = m_Weather.GetOvercast().GetActual();
        if (type == EWeatherPhenomenon.OVERCAST)
            m_Weather.GetOvercast().Set(HCWeatherDays.HCSeasonCloud(HCSeasonVisualPolicy.HCPhaseName(HCSeasonPhaseCode()), m_HCWeatherProfile, m_Weather.GetTime(), hour), 300.0, 300.0);
        else if (type == EWeatherPhenomenon.RAIN)
            m_Weather.GetRain().Set(HCWeatherDays.HCSeasonRain(HCSeasonVisualPolicy.HCPhaseName(HCSeasonPhaseCode()), m_HCWeatherProfile, cloud, hour), 180.0, 120.0);
        else if (type == EWeatherPhenomenon.WIND_MAGNITUDE)
            m_Weather.GetWindMagnitude().Set(HCWeatherDays.WindTarget(m_HCWeatherProfile, cloud, hour), 180.0, 120.0);
        else if (type == EWeatherPhenomenon.FOG)
            m_Weather.GetFog().Set(HCWeatherDays.HCSeasonFog(HCSeasonVisualPolicy.HCPhaseName(HCSeasonPhaseCode()), m_HCWeatherDay, hour, m_HCWeatherCalm), 30.0, 0.0);
        else if (type == EWeatherPhenomenon.WIND_DIRECTION)
            m_Weather.GetWindDirection().Set(HCAtmospherePolicy.WindDirectionTarget(m_Weather.GetTime()), 300.0, 300.0);
        else if (type == EWeatherPhenomenon.SNOWFALL)
            m_Weather.GetSnowfall().Set(HCWeatherDays.HCSeasonSnow(HCSeasonVisualPolicy.HCPhaseName(HCSeasonPhaseCode()), m_HCWeatherProfile, cloud, hour), 300.0, 300.0);
        else if (type != EWeatherPhenomenon.VOLFOG_HEIGHT_DENSITY && type != EWeatherPhenomenon.VOLFOG_DISTANCE_DENSITY && type != EWeatherPhenomenon.VOLFOG_HEIGHT_BIAS)
            return false;
        CalculateVolFog(cloud, m_Weather.GetWindSpeed(), 30.0);
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
        float extra = HCWeatherDays.HCSeasonFog(HCSeasonVisualPolicy.HCPhaseName(HCSeasonPhaseCode()), m_HCWeatherDay, hour, m_HCWeatherCalm) - 0.04;
        m_Weather.SetDynVolFogDistanceDensity(density + extra * 0.12, 0);
        m_Weather.SetDynVolFogHeightDensity(0.95, 0);
        m_Weather.SetDynVolFogHeightBias(50 + extra * 70, 0);
    }
}
