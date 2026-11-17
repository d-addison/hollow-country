

// Hollow Country DISPOSABLE weather precedence probe; observation only, no gameplay acceptance.
// Server only; runs once per process. It reads native weather state and never sets any of it.
// Samples are bounded by an inlined count, an inlined duration cap and a watchdog. Output is JSON lines
// in the probe profile directory (numbers as quoted strings) and a sentinel file written last.
// Limits: the cap is checked before each sample and the watchdog fires between steps; neither can
// interrupt a synchronous call that never returns.
class HCDisposableDiagnosticMission : CustomMission
{
    protected bool m_HCWPStarted = false;
    protected bool m_HCWPDone = false;
    protected bool m_HCWPOpened = false;
    protected int m_HCWPSamples = 0;
    protected int m_HCWPMaxSamples = 60;
    protected int m_HCWPIntervalMs = 30000;
    protected int m_HCWPCapMs = 1830000;
    protected int m_HCWPBeginMs = 0;
    protected int m_HCWPEndMs = 0;
    protected int m_HCWPWriteErrors = 0;
    protected string m_HCWPQuote = "";
    protected string m_HCWPSlash = "";
    protected string m_HCWPOutput = "";
    protected string m_HCWPSentinel = "";

    override void OnInit()
    {
        super.OnInit();
        if (!GetGame() || !GetGame().IsServer() || m_HCWPStarted)
            return;
        m_HCWPStarted = true;
        int quoteCode = 34;
        m_HCWPQuote = quoteCode.AsciiToString();
        int slashCode = 92;
        m_HCWPSlash = slashCode.AsciiToString();
        m_HCWPOutput = "$profile:HCWeatherProbe/observations.json";
        m_HCWPSentinel = "$profile:HCWeatherProbe/complete.txt";
        string message = "[HC Weather Probe] ARMED; observation only; samples=" + m_HCWPMaxSamples.ToString();
        Print(message);
        GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(HCWPBegin, 30000, false);
        GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(HCWPWatchdog, 1920000, false);
    }

    string HCWPKey(string name)
    {
        return m_HCWPQuote + name + m_HCWPQuote + ":";
    }

    string HCWPQuoted(string value)
    {
        string text = value;
        if (text.Length() > 96)
            text = text.Substring(0, 96);
        text.Replace(m_HCWPQuote, "'");
        text.Replace(m_HCWPSlash, "/");
        return m_HCWPQuote + text + m_HCWPQuote;
    }

    string HCWPBool(bool value)
    {
        if (value)
            return "true";
        return "false";
    }

    string HCWPFloat(float value)
    {
        return HCWPQuoted(value.ToString());
    }

    void HCWPAppend(string line)
    {
        FileHandle handle = OpenFile(m_HCWPOutput, FileMode.APPEND);
        if (!handle)
        {
            m_HCWPWriteErrors = m_HCWPWriteErrors + 1;
            return;
        }
        FPrintln(handle, line);
        CloseFile(handle);
    }

    string HCWPHeaderLine()
    {
        string world;
        string version;
        GetGame().GetWorldName(world);
        GetGame().GetVersion(version);
        string row = "{" + HCWPKey("type") + HCWPQuoted("header") + "," + HCWPKey("schema") + "1," + HCWPKey("kind") + HCWPQuoted("weather-probe-observations") + ",";
        row = row + HCWPKey("world") + HCWPQuoted(world) + "," + HCWPKey("version") + HCWPQuoted(version) + ",";
        row = row + HCWPKey("planned_samples") + m_HCWPMaxSamples.ToString() + "," + HCWPKey("interval_ms") + m_HCWPIntervalMs.ToString() + ",";
        row = row + HCWPKey("cap_ms") + m_HCWPCapMs.ToString() + "}";
        return row;
    }

    string HCWPEndLine(string status)
    {
        string row = "{" + HCWPKey("type") + HCWPQuoted("end") + "," + HCWPKey("status") + HCWPQuoted(status) + ",";
        row = row + HCWPKey("samples") + m_HCWPSamples.ToString() + "," + HCWPKey("write_errors") + m_HCWPWriteErrors.ToString() + ",";
        row = row + HCWPKey("end_ms") + m_HCWPEndMs.ToString() + "}";
        return row;
    }

    string HCWPPhenomenon(string name, WeatherPhenomenon phenomenon)
    {
        float limitMin = 0;
        float limitMax = 0;
        float changeMin = 0;
        float changeMax = 0;
        float timeMin = 0;
        float timeMax = 0;
        phenomenon.GetLimits(limitMin, limitMax);
        phenomenon.GetForecastChangeLimits(changeMin, changeMax);
        phenomenon.GetForecastTimeLimits(timeMin, timeMax);
        string row = HCWPKey(name) + "{";
        row = row + HCWPKey("actual") + HCWPFloat(phenomenon.GetActual()) + "," + HCWPKey("forecast") + HCWPFloat(phenomenon.GetForecast()) + ",";
        row = row + HCWPKey("next_change") + HCWPFloat(phenomenon.GetNextChange()) + ",";
        row = row + HCWPKey("limit_min") + HCWPFloat(limitMin) + "," + HCWPKey("limit_max") + HCWPFloat(limitMax) + ",";
        row = row + HCWPKey("change_min") + HCWPFloat(changeMin) + "," + HCWPKey("change_max") + HCWPFloat(changeMax) + ",";
        row = row + HCWPKey("time_min") + HCWPFloat(timeMin) + "," + HCWPKey("time_max") + HCWPFloat(timeMax) + "}";
        return row;
    }

    string HCWPSampleLine(int seq)
    {
        Weather weather = GetGame().GetWeather();
        int nowMs = GetGame().GetTime();
        int year = 0;
        int month = 0;
        int day = 0;
        int hour = 0;
        int minute = 0;
        GetGame().GetWorld().GetDate(year, month, day, hour, minute);
        string row = "{" + HCWPKey("type") + HCWPQuoted("sample") + "," + HCWPKey("seq") + seq.ToString() + ",";
        row = row + HCWPKey("game_ms") + nowMs.ToString() + "," + HCWPKey("weather_time") + HCWPFloat(weather.GetTime()) + ",";
        row = row + HCWPKey("mission_weather") + HCWPBool(weather.GetMissionWeather()) + "," + HCWPKey("update_frozen") + HCWPBool(weather.GetWeatherUpdateFrozen()) + ",";
        row = row + HCWPKey("year") + year.ToString() + "," + HCWPKey("month") + month.ToString() + ",";
        row = row + HCWPKey("day") + day.ToString() + "," + HCWPKey("hour") + hour.ToString() + ",";
        row = row + HCWPKey("minute") + minute.ToString() + ",";
        row = row + HCWPKey("wind_speed") + HCWPFloat(weather.GetWindSpeed()) + "," + HCWPKey("wind_max_speed") + HCWPFloat(weather.GetWindMaximumSpeed()) + ",";
        row = row + HCWPKey("volfog_enabled") + HCWPBool(weather.IsDynVolFogEnabled()) + "," + HCWPKey("volfog_distance_density") + HCWPFloat(weather.GetDynVolFogDistanceDensity()) + ",";
        row = row + HCWPKey("volfog_height_density") + HCWPFloat(weather.GetDynVolFogHeightDensity()) + "," + HCWPKey("volfog_height_bias") + HCWPFloat(weather.GetDynVolFogHeightBias()) + ",";
        row = row + HCWPKey("phenomena") + "{";
        row = row + HCWPPhenomenon("overcast", weather.GetOvercast()) + "," + HCWPPhenomenon("fog", weather.GetFog()) + ",";
        row = row + HCWPPhenomenon("rain", weather.GetRain()) + "," + HCWPPhenomenon("windMagnitude", weather.GetWindMagnitude()) + ",";
        row = row + HCWPPhenomenon("windDirection", weather.GetWindDirection()) + "," + HCWPPhenomenon("snowfall", weather.GetSnowfall()) + "}}";
        return row;
    }

    void HCWPBegin()
    {
        if (m_HCWPDone)
            return;
        m_HCWPBeginMs = GetGame().GetTime();
        string directory = m_HCWPOutput.Substring(0, m_HCWPOutput.IndexOf("/"));
        if (!FileExist(directory) && !MakeDirectory(directory))
        {
            m_HCWPDone = true;
            Print("[HC Weather Probe] FAILED cannot create output directory");
            return;
        }
        if (FileExist(m_HCWPOutput) || FileExist(m_HCWPSentinel))
        {
            m_HCWPDone = true;
            Print("[HC Weather Probe] FAILED earlier probe output exists; not overwriting");
            return;
        }
        FileHandle handle = OpenFile(m_HCWPOutput, FileMode.WRITE);
        if (!handle)
        {
            m_HCWPDone = true;
            Print("[HC Weather Probe] FAILED cannot open observations file");
            return;
        }
        FPrintln(handle, HCWPHeaderLine());
        CloseFile(handle);
        m_HCWPOpened = true;
        Print("[HC Weather Probe] BEGIN; observation only");
        HCWPStep();
    }

    void HCWPStep()
    {
        if (m_HCWPDone || m_HCWPSamples >= m_HCWPMaxSamples)
            return;
        int elapsedMs = GetGame().GetTime() - m_HCWPBeginMs;
        if (elapsedMs > m_HCWPCapMs)
        {
            HCWPFinish("partial");
            return;
        }
        HCWPAppend(HCWPSampleLine(m_HCWPSamples));
        m_HCWPSamples = m_HCWPSamples + 1;
        if (m_HCWPSamples >= m_HCWPMaxSamples)
        {
            HCWPFinish("complete");
            return;
        }
        GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(HCWPStep, m_HCWPIntervalMs, false);
    }

    void HCWPWatchdog()
    {
        if (m_HCWPDone)
            return;
        if (!m_HCWPOpened)
        {
            m_HCWPDone = true;
            Print("[HC Weather Probe] FAILED watchdog fired before the observations file was opened");
            return;
        }
        HCWPFinish("partial");
    }

    void HCWPFinish(string status)
    {
        if (m_HCWPDone)
            return;
        m_HCWPDone = true;
        m_HCWPEndMs = GetGame().GetTime();
        string outcome = status;
        if (m_HCWPWriteErrors > 0)
            outcome = "failed";
        HCWPAppend(HCWPEndLine(outcome));
        HCWPWriteSentinel(outcome);
    }

    void HCWPWriteSentinel(string status)
    {
        FileHandle sentinel = OpenFile(m_HCWPSentinel, FileMode.WRITE);
        if (!sentinel)
        {
            Print("[HC Weather Probe] FAILED cannot open sentinel file");
            return;
        }
        string line = "status=" + status + " samples=" + m_HCWPSamples.ToString() + " write_errors=" + m_HCWPWriteErrors.ToString();
        FPrintln(sentinel, line);
        CloseFile(sentinel);
        string summary = "[HC Weather Probe] " + status + " samples=" + m_HCWPSamples.ToString();
        Print(summary);
    }
}
