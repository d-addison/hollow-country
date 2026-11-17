"""Stage a disposable native weather precedence probe runtime; never launch the engine.

Question (#35, DayZ 1.30.164289, ChernarusPlus): does a cfgweather.xml candidate actually govern
the weather, or does world script override it? The stock scripts decide this through
WeatherPhenomenon.OnBeforeChange: it returns without changes when Weather.GetMissionWeather()
is true, freezes when GetWeatherUpdateFrozen() is true, and otherwise hands the decision to
WorldData.WeatherOnBeforeChange (ChernarusPlus overrides it, and its constructor forces snowfall
limits and a random starting overcast). Whether the engine sets MissionWeather(true) when
cfgweather.xml carries enable="1" is UNKNOWN; the probe measures it instead of assuming it.

The probe is a server-only, observation-only harness. A hook appended to the stock mission's init.c
samples every N seconds for a bounded number of samples and writes JSON lines; it calls no setter, makes
no gameplay change and writes nothing outside its own profile directory. tools/audit/weather_report.py
reads the output. The comparison needs two runs staged from the same stock runtime, one with the stock
cfgweather.xml and one with a distinctive validated candidate; the operator runs both. Nothing here proves
how DayZ behaves, and runtime acceptance stays PENDING.

Stage a fresh runtime (destination must not exist). The candidate directory is the output of
tools/package/atmosphere.py write_candidate and is re-validated here; an unvalidated or tampered
candidate is refused. The candidate is also regenerated from the stock cfgweather.xml the runtime
carries (never from a caller-supplied file) and must match byte for byte; an unreported XML change is
refused even when its metadata hashes were recomputed:

    python3 tools/setup/weather_probe.py --destination /mnt/d/HollowCountryLocal/weather-stock-001
    python3 tools/setup/weather_probe.py --destination /mnt/d/HollowCountryLocal/weather-cand-001 \
        --candidate CANDIDATE_DIR

Native APIs the hook calls, verified against the installed 1.30.164289 script cache
(~/.cache/hollow-country/native-scripts/scripts-1.30.164289), as `API -> file:line`:

  GetGame -> 2_GameLib/gameLib.c:4
  IsServer -> 3_Game/Global/Game.c:1120
  GetWeather -> 3_Game/Global/Game.c:1371
  CGame.GetTime -> 3_Game/Global/Game.c:1535
  GetCallQueue -> 3_Game/Global/Game.c:1550
  GetWorld -> 3_Game/Global/Game.c:931
  GetWorldName -> 3_Game/Global/Game.c:932
  GetVersion -> 3_Game/Global/Game.c:942
  GetDate -> 3_Game/Global/World.c:28
  CallLater -> 2_GameLib/tools.c:61
  GetActual -> 3_Game/Weather.c:38
  GetForecast -> 3_Game/Weather.c:41
  GetNextChange -> 3_Game/Weather.c:52
  GetLimits -> 3_Game/Weather.c:61
  GetForecastChangeLimits -> 3_Game/Weather.c:81
  GetForecastTimeLimits -> 3_Game/Weather.c:102
  Weather.GetTime -> 3_Game/Weather.c:180
  GetOvercast -> 3_Game/Weather.c:183
  GetFog -> 3_Game/Weather.c:186
  GetRain -> 3_Game/Weather.c:189
  GetSnowfall -> 3_Game/Weather.c:192
  GetWindDirection -> 3_Game/Weather.c:199
  GetWindMagnitude -> 3_Game/Weather.c:205
  GetWindSpeed -> 3_Game/Weather.c:248
  GetWindMaximumSpeed -> 3_Game/Weather.c:263
  IsDynVolFogEnabled -> 3_Game/Weather.c:354
  GetDynVolFogDistanceDensity -> 3_Game/Weather.c:364
  GetDynVolFogHeightDensity -> 3_Game/Weather.c:374
  GetDynVolFogHeightBias -> 3_Game/Weather.c:385
  GetMissionWeather -> 3_Game/Weather.c:392
  GetWeatherUpdateFrozen -> 3_Game/Weather.c:402
  OnBeforeChange -> 3_Game/Weather.c:125
  WeatherOnBeforeChange -> 3_Game/WorldData.c:251
  WeatherOnBeforeChange -> 4_World/Classes/Worlds/ChernarusPlus.c:92
  SetLimits -> 4_World/Classes/Worlds/ChernarusPlus.c:70
  FileExist -> 1_Core/proto/EnSystem.c:397
  OpenFile -> 1_Core/proto/EnSystem.c:417
  CloseFile -> 1_Core/proto/EnSystem.c:443
  FPrintln -> 1_Core/proto/EnSystem.c:481
  MakeDirectory -> 1_Core/proto/EnSystem.c:525
  int.ToString -> 1_Core/proto/EnConvert.c:30
  int.AsciiToString -> 1_Core/proto/EnConvert.c:44
  float.ToString -> 1_Core/proto/EnConvert.c:115
  OnInit -> 5_Mission/mission/missionServer.c:85

The phenomenon accessors return typedefs of WeatherPhenomenon (3_Game/Weather.c:153-158). The setters
(Set, SetLimits, MissionWeather, SetWeatherUpdateFreeze, SuppressLightningSimulation) are never called.
Float formatting of float.ToString was unobserved when the hook was written, so floats are written as quoted
JSON strings and the report parses them; integers are written unquoted. The first native run
(weather-probe-001-stock, observation only) showed about six significant digits and an exponent form for
very small values, e.g. "5.51835e-05".

GetNextChange: the Weather.c:51 comment says "the time in seconds when". The same native run shows a
countdown of the REMAINING seconds until the next forecast (fog 294.987 at weather_time 5.30, 234.57 at
65.3, 3.907 and then a jump up to 898.934 at 301.47 with a new forecast), not an absolute time; the report reads it so. That
one run is observation, not a guarantee, and the countdown rate differed by phenomenon (about 0.98 to 1.0
of the weather clock).

Limits of the in-script guards: the duration cap is checked before every sample and the watchdog is a
queued call, so neither can interrupt a synchronous call that never returns. A hung engine call hangs the
probe; the launcher's wait limit is the only outer bound, and nothing is read from a run that did not write
its sentinel. Weather ticking without any connected client is unobserved; if it does not tick, the samples
will show constant values and the report cannot discriminate (it says so).

Compile rules applied to the generated text are those observed in native compiles: no identifier equal to
an engine type name, no line starting with || or &&, no ternary, one declaration per local per function,
out arguments declared before the call, no exponent literals, and at most 8 binary '+' per statement with
explicit .ToString() for every number in a string concatenation (a 27-plus line was refused natively with
"Formula too complex"; at most 9 compiled). statement_problems enforces the plus and ToString rule here
until the shared probe_runtime lint carries it.
"""
import argparse
import math
from pathlib import Path
import re
import sys
import tempfile

try:
    from . import diagnostic_mission as dm
    from . import probe_runtime as rt
except ImportError:  # executed as a script from tools/setup
    import diagnostic_mission as dm
    import probe_runtime as rt

try:
    from tools.package import atmosphere
except ImportError:  # executed as a script from tools/setup
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from tools.package import atmosphere

BATTLEYE_SHA256 = rt.BATTLEYE_SHA256
DEFAULT_SOURCE_RUNTIME = rt.DEFAULT_SOURCE_RUNTIME
WSL_PARENT = Path("/mnt/d/HollowCountryLocal")
PLAN_NAME = "weather-probe-plan.json"
PLAN_KIND = "weather-probe"
OBSERVATIONS_KIND = "weather-probe-observations"
PROBE_DIRECTORY = "HCWeatherProbe"
OUTPUT_NAME = "observations.json"
SENTINEL_NAME = "complete.txt"
OUTPUT_RELATIVE = "profiles/" + PROBE_DIRECTORY + "/" + OUTPUT_NAME
SENTINEL_RELATIVE = "profiles/" + PROBE_DIRECTORY + "/" + SENTINEL_NAME
LAUNCHER_ROW = (PLAN_NAME, PROBE_DIRECTORY, OUTPUT_NAME)
PHENOMENA = ("overcast", "fog", "rain", "windMagnitude", "windDirection", "snowfall")
WORLD = "chernarusplus"
MIN_START_DELAY_S, MAX_START_DELAY_S = 5, 600
MIN_INTERVAL_S, MAX_INTERVAL_S = 5, 600
MIN_SAMPLES, MAX_SAMPLES = 6, 360
DEFAULT_START_DELAY_S, DEFAULT_INTERVAL_S, DEFAULT_SAMPLES = 30, 30, 60
# Start-CEProbeServer.ps1 refuses a plan whose wait is outside 5..120 minutes.
MAX_WORST_CASE_MINUTES = 120
CAP_SLACK_MS = 30000
WATCHDOG_SLACK_MS = 60000
BOOT_MARGIN_MINUTES = 3
MAX_PLUS_PER_STATEMENT = 8
MAX_CANDIDATE_XML_BYTES = atmosphere.MAX_XML_BYTES
# Mirrors the diagnostic_mission._PURPOSES row the shared module should carry for this probe.
PURPOSE = "weather-probe"
PURPOSE_ROW = ("disposable-weather-probe", None,
               ["server mode", "fresh storage and profiles", "no clients",
                "inspect observation completeness separately from startup"])

HOOK_TEMPLATE = r"""

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
    protected int m_HCWPMaxSamples = @@SAMPLES@@;
    protected int m_HCWPIntervalMs = @@INTERVAL_MS@@;
    protected int m_HCWPCapMs = @@CAP_MS@@;
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
        GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(HCWPBegin, @@START_MS@@, false);
        GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(HCWPWatchdog, @@WATCHDOG_MS@@, false);
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
        string row = "{" + HCWPKey("type") + HCWPQuoted("header") + "," + HCWPKey("schema") + "1," + HCWPKey("kind") + HCWPQuoted("@@OBSERVATIONS_KIND@@") + ",";
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
"""

# ---------------------------------------------------------------------------
# Parameters, timing and rendering
# ---------------------------------------------------------------------------


def _integer(value, low, high, what):
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ValueError(f"{what} must be an integer {low}..{high}")
    return value


def _parameters(start_delay_s, interval_s, samples):
    _integer(start_delay_s, MIN_START_DELAY_S, MAX_START_DELAY_S, "start delay (s)")
    _integer(interval_s, MIN_INTERVAL_S, MAX_INTERVAL_S, "interval (s)")
    _integer(samples, MIN_SAMPLES, MAX_SAMPLES, "samples")


def cap_ms(interval_s, samples):
    """The sampling duration cap the hook enforces before each sample."""
    return samples * interval_s * 1000 + CAP_SLACK_MS


def watchdog_ms(start_delay_s, interval_s, samples):
    """The watchdog fires after the begin delay plus the full cap plus slack and finishes partial."""
    return start_delay_s * 1000 + cap_ms(interval_s, samples) + WATCHDOG_SLACK_MS


def worst_case_minutes(start_delay_s, interval_s, samples):
    """Minutes the launcher must wait: the watchdog plus a server boot margin."""
    return math.ceil(watchdog_ms(start_delay_s, interval_s, samples) / 60000) + BOOT_MARGIN_MINUTES


def render_hook(start_delay_s=DEFAULT_START_DELAY_S, interval_s=DEFAULT_INTERVAL_S, samples=DEFAULT_SAMPLES):
    """Return the generated Enforce text (bytes); it is candidate-independent so both runs share one hook."""
    _parameters(start_delay_s, interval_s, samples)
    text = (HOOK_TEMPLATE.replace("@@SAMPLES@@", str(samples)).replace("@@INTERVAL_MS@@", str(interval_s * 1000))
            .replace("@@CAP_MS@@", str(cap_ms(interval_s, samples))).replace("@@START_MS@@", str(start_delay_s * 1000))
            .replace("@@WATCHDOG_MS@@", str(watchdog_ms(start_delay_s, interval_s, samples)))
            .replace("@@OBSERVATIONS_KIND@@", OBSERVATIONS_KIND))
    if "@@" in text or not text.isascii():
        raise ValueError("hook must be ASCII with every placeholder resolved")
    return text.encode("ascii")


# ---------------------------------------------------------------------------
# Statement-shape lint (plus count and explicit ToString); mirrors the shared lint rule
# ---------------------------------------------------------------------------

_STRING = re.compile(r'"(?:[^"\\]|\\.)*"')


def _code_of(text):
    """Text with comments dropped and string literal contents blanked."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return "\n".join(_STRING.sub('""', line).split("//")[0] for line in text.splitlines())


def _statements(text):
    """(first_line, statement) pairs split on ; { } so a statement may span lines."""
    result, current, first, line = [], [], None, 1
    for char in _code_of(text):
        if char == "\n":
            line += 1
        if char in ";{}":
            body = "".join(current).strip()
            if body:
                result.append((first, body))
            current, first = [], None
            continue
        if first is None and not char.isspace():
            first = line
        current.append(char)
    return result


def _top_level_operands(expression):
    operands, depth, current = [], 0, []
    for char in expression:
        if char in "([":
            depth += 1
        elif char in ")]":
            depth -= 1
        if char == "+" and depth == 0:
            operands.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    operands.append("".join(current).strip())
    return operands


def statement_problems(text):
    """Problems with the plus count per statement and with implicit number-to-string conversion."""
    code = _code_of(text)
    string_names = set(re.findall(r"\bstring\s+(\w+)", code))
    string_functions = set(re.findall(r"^[ \t]{4}string\s+(\w+)\s*\(", code, re.M))
    problems = []
    if "++" in code or "+=" in code:
        problems.append("increment and compound-assignment operators are not used in generated hooks")
    for first, body in _statements(text):
        plus = body.count("+")
        if plus > MAX_PLUS_PER_STATEMENT:
            problems.append(f"line {first}: statement has {plus} '+' operators (max {MAX_PLUS_PER_STATEMENT}); "
                            "the native compiler refuses long formulas")
        body = re.sub(r"^(?:if|while|else if)\s*\(", "(", body)
        if "+" not in body or '""' not in body:
            continue
        right = body.split("=", 1)[1] if re.match(r"^[\w\[\]\. ]+=[^=]", body) else body
        right = re.sub(r"^return\s+", "", right.strip())
        for operand in _top_level_operands(right):
            function = re.match(r"^(\w+)\(", operand)
            if (operand == '""' or operand.endswith(".ToString()") or operand.endswith(".AsciiToString()")
                    or operand in string_names or (function and function.group(1) in string_functions)):
                continue
            problems.append(f"line {first}: operand '{operand}' is not provably a string (use .ToString())")
    return problems


def max_plus_per_statement(text):
    """Largest binary '+' count in one statement of the generated hook (informational)."""
    return max((body.count("+") for _line, body in _statements(text)), default=0)


# ---------------------------------------------------------------------------
# Candidate handling
# ---------------------------------------------------------------------------


def load_candidate(candidate):
    """Re-validate an atmosphere candidate's own integrity; (cfgweather bytes, report). Not yet source-verified."""
    report = atmosphere.validate_candidate(candidate)
    profile = report["profile"]
    if profile["world"] != WORLD:
        raise ValueError(f"the candidate was generated for {profile['world']}; the probe runs {WORLD} only")
    data, _identity = rt.read_identified(Path(candidate) / "cfgweather.xml", MAX_CANDIDATE_XML_BYTES)
    if rt.sha256(data) != report["candidate_sha256"]:
        raise ValueError("candidate cfgweather.xml changed during staging")
    return data, report


def reconstruct_candidate(candidate, stock_bytes, expected_sha256):
    """Rebuild the candidate from the verified stock bytes; any difference from its files is refused.

    Metadata hashes can be recomputed by anyone, so only regenerating the candidate from the stock
    cfgweather.xml the runtime actually carries proves that nothing unreported changed. The stock
    bytes go through a private temporary file because the atmosphere API reads a path.
    """
    with tempfile.TemporaryDirectory(prefix="weather-stock-") as scratch:
        source = Path(scratch) / "cfgweather.xml"
        source.write_bytes(stock_bytes)
        report = atmosphere.validate_candidate(candidate, source=source)
    if report.get("source_verified") is not True:
        raise ValueError("the candidate could not be reconstructed from the runtime's stock cfgweather.xml")
    if report["candidate_sha256"] != expected_sha256:
        raise ValueError("candidate cfgweather.xml changed during reconstruction")
    return report


def _check_registries():
    """Refuse to stage unless the shared modules carry this probe's rows; never register them here."""
    if rt.LAUNCHER_PROBES.get(PLAN_KIND) != LAUNCHER_ROW:
        raise ValueError(
            "probe_runtime.LAUNCHER_PROBES lacks the weather-probe row "
            f"{PLAN_KIND!r}: {LAUNCHER_ROW!r}; the launcher would refuse this plan")
    row = dm._PURPOSES.get(PURPOSE)
    if row is None or tuple(row[:2]) != PURPOSE_ROW[:2] or list(row[2]) != PURPOSE_ROW[2]:
        raise ValueError(
            f"diagnostic_mission._PURPOSES must carry exactly {PURPOSE!r}: {PURPOSE_ROW!r} (found {row!r}); "
            "this module does not register purposes itself")


# ---------------------------------------------------------------------------
# Staging (shared lint, name rule, verification and skeleton live in probe_runtime)
# ---------------------------------------------------------------------------


def stage(source_runtime, destination, *, candidate=None,
          start_delay_s=DEFAULT_START_DELAY_S, interval_s=DEFAULT_INTERVAL_S, samples=DEFAULT_SAMPLES,
          wait_minutes=None, battleye_sha256=BATTLEYE_SHA256, native_scripts=None, now=None, _wsl_parent=None):
    """Stage a fresh probe runtime and write weather-probe-plan.json. Never launches anything.

    Without ``candidate`` the stock cfgweather.xml is staged untouched (the control run); with one,
    the validated candidate bytes replace it (the treatment run). ``_wsl_parent`` is an internal test
    hook; the production parent is always WSL_PARENT.
    """
    _check_registries()
    hook = render_hook(start_delay_s, interval_s, samples)
    native = rt.native_type_names(native_scripts) if native_scripts else frozenset()
    problems = rt.lint_hook(hook.decode("ascii"), native_types=native) + statement_problems(hook.decode("ascii"))
    if problems:
        raise ValueError("generated hook violates native compile rules: " + "; ".join(problems[:3]))
    worst_minutes = worst_case_minutes(start_delay_s, interval_s, samples)
    if wait_minutes is None:
        wait_minutes = max(5, worst_minutes)
    if (isinstance(wait_minutes, bool) or not isinstance(wait_minutes, int)
            or not 5 <= wait_minutes <= MAX_WORST_CASE_MINUTES or wait_minutes < worst_minutes):
        raise ValueError(f"wait minutes must be 5..{MAX_WORST_CASE_MINUTES} and cover the {worst_minutes} minute worst case")
    treatment = load_candidate(candidate) if candidate is not None else None
    context = rt.begin(source_runtime, destination, parent=WSL_PARENT if _wsl_parent is None else _wsl_parent,
                       battleye_sha256=battleye_sha256, hold=("cfgweather.xml",))
    stock = context["source"]["held"]["cfgweather.xml"]
    replacements = {}
    cfgweather = {"variant": "stock", "stock_sha256": rt.sha256(stock), "candidate": None}
    if treatment is not None:
        data, report = treatment
        profile = report["profile"]
        if profile["source_sha256"] != rt.sha256(stock):
            raise ValueError("the candidate was not generated from this runtime's stock cfgweather.xml")
        report = reconstruct_candidate(candidate, stock, report["candidate_sha256"])
        replacements["cfgweather.xml"] = data
        cfgweather["variant"] = "candidate"
        cfgweather["candidate"] = {
            "name": profile["name"], "world": profile["world"], "source_verified": report["source_verified"],
            "enable": profile["enable"], "reset": profile["reset"], "sha256": report["candidate_sha256"],
            "changes": len(report["changes"]), "change_paths": [change["path"] for change in report["changes"]]}
    built = rt.build_runtime(context, hook, purpose=PURPOSE, replacements=replacements)
    cfgweather["staged_sha256"] = built["staged_hash"]["mpmissions/" + rt.MISSION_NAME + "/cfgweather.xml"]
    plan = rt.plan_header(PLAN_KIND, now, before={"acceptance": "PENDING"}, after={"variant": cfgweather["variant"]})
    plan.update(rt.plan_runtime_fields(context, built))
    plan.update({
        "probe": {"mode": "server-only-no-clients", "clients": 0, "start_delay_s": start_delay_s,
                  "interval_s": interval_s, "samples": samples, "cap_ms": cap_ms(interval_s, samples),
                  "watchdog_ms": watchdog_ms(start_delay_s, interval_s, samples), "wait_minutes": wait_minutes,
                  "hook_sha256": rt.sha256(hook), "hook_bytes": len(hook), "phenomena": list(PHENOMENA),
                  "output_relative_path": OUTPUT_RELATIVE, "sentinel_relative_path": SENTINEL_RELATIVE,
                  "observations_kind": OBSERVATIONS_KIND, "cfgweather": cfgweather},
        "mission_files": built["mission_files"], "staged_files": built["staged"],
    })
    return rt.write_plan(context["destination"], PLAN_NAME, plan)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--destination", required=True, help="fresh runtime directory (must not exist)")
    parser.add_argument("--source-runtime", default=DEFAULT_SOURCE_RUNTIME)
    parser.add_argument("--candidate", help="validated atmosphere candidate directory (omit for the stock control run)")
    parser.add_argument("--start-delay-s", type=int, default=DEFAULT_START_DELAY_S)
    parser.add_argument("--interval-s", type=int, default=DEFAULT_INTERVAL_S)
    parser.add_argument("--samples", type=int, default=DEFAULT_SAMPLES)
    parser.add_argument("--wait-minutes", type=int)
    parser.add_argument("--battleye-sha256", default=BATTLEYE_SHA256)
    parser.add_argument("--native-scripts", help="extracted native script cache used to lint the hook")
    args = parser.parse_args(argv)
    cache = args.native_scripts
    if cache is None:
        default = Path.home() / ".cache/hollow-country/native-scripts/scripts-1.30.164289"
        cache = default if (default / "3_Game").is_dir() else None
    try:
        plan = stage(args.source_runtime, args.destination, candidate=args.candidate,
                     start_delay_s=args.start_delay_s,
                     interval_s=args.interval_s, samples=args.samples, wait_minutes=args.wait_minutes,
                     battleye_sha256=args.battleye_sha256, native_scripts=cache)
    except (OSError, ValueError) as error:
        print(f"weather_probe: {error}", file=sys.stderr)
        return 1
    info = plan["probe"]
    print(f"staged weather probe runtime: {Path(args.destination) / PLAN_NAME}")
    print(f"variant={info['cfgweather']['variant']} samples={info['samples']} interval_s={info['interval_s']} "
          f"wait_minutes={info['wait_minutes']} hook_bytes={info['hook_bytes']} hook_sha256={info['hook_sha256']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
