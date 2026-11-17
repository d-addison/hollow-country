// Server-only tick performance sampler. Not an HCModule; HCServer owns one instance.
// Collects the HC tick interval and the time HC modules spent inside one tick, and prints one
// summary line per window. Memory is bounded: two ring buffers and two sort buffers of at most
// HC_PERF_MAX_SAMPLES floats, allocated once. No file I/O. Output is read by tools/testing/perf_capture.py.
// Verified in the installed 1.30.164289 script dump: array<T>.Insert/Set/Get/Count/Clear/Sort/Reserve,
// CGame.GetPlayers(out array<Man>), CGame.GetTickTime, Math.Round, string.ToString, Print,
// proto native int TickCount(int prev) (1_Core/proto/EnSystem.c:106: ticks between prev and now).
// The TickCount unit is NOT documented and vanilla never calls it, so work is passed in as raw ticks and
// converted per window: ticks_per_ms = TickCount(window start) / server-clock milliseconds of the window.
// Both are deltas, so int wrap is not a concern while the window stays at or below 120 s at the observed rate
// (about 10000 ticks per ms, so 1.2 billion ticks per 120 s window, below 2^31).
// A negative or zero delta, an interval longer than twice the window clamp, or a ticks_per_ms outside
// [HC_PERF_MIN_TICKS_PER_MS, HC_PERF_MAX_TICKS_PER_MS] prints calibration=invalid and omits every work_* value.
// Players: the count is read at every sample; the line carries the window minimum and maximum.
// The line is printed through the expression "" + report. Print(report) with a variable makes the engine print
// the declaration (string report = '...'), as observed in a real RPT.
const int HC_PERF_MAX_SAMPLES = 512;
const int HC_PERF_MAX_WINDOW_SECONDS = 120;
const float HC_PERF_MIN_TICKS_PER_MS = 0.01;
const float HC_PERF_MAX_TICKS_PER_MS = 100000.0;

class HCPerfSampler
{
    protected bool m_Active;
    protected int m_WindowSeconds;
    protected int m_WindowIndex;
    protected float m_WindowElapsed;
    protected int m_Cursor;
    protected float m_TickMax;
    protected int m_WorkMaxTicks;
    protected int m_PlayersMin;
    protected int m_PlayersMax;
    protected int m_WindowTick0;
    protected float m_WindowTime0;
    protected ref array<float> m_Ticks = new array<float>();
    protected ref array<float> m_Works = new array<float>();
    protected ref array<float> m_SortedTicks = new array<float>();
    protected ref array<float> m_SortedWorks = new array<float>();
    protected ref array<Man> m_Players = new array<Man>();

    void HCPerfSampler()
    {
        m_Ticks.Reserve(HC_PERF_MAX_SAMPLES);
        m_Works.Reserve(HC_PERF_MAX_SAMPLES);
        m_SortedTicks.Reserve(HC_PERF_MAX_SAMPLES);
        m_SortedWorks.Reserve(HC_PERF_MAX_SAMPLES);
    }

    bool IsActive() { return m_Active; }

    void Start(int windowSeconds)
    {
        if (!GetGame() || !GetGame().IsServer()) return;
        if (windowSeconds <= 0) return;
        m_WindowSeconds = windowSeconds;
        if (m_WindowSeconds > HC_PERF_MAX_WINDOW_SECONDS) m_WindowSeconds = HC_PERF_MAX_WINDOW_SECONDS;
        m_WindowIndex = 0;
        ResetWindow();
        m_Active = true;
        Print("[HollowCountry] Perf sampler started, window seconds: " + m_WindowSeconds.ToString());
    }

    // elapsedSeconds: wall time since the previous HC tick. workTicks: TickCount(start) around the module loop.
    void Sample(float elapsedSeconds, int workTicks)
    {
        if (!m_Active) return;
        float tickMs = elapsedSeconds * 1000;
        int safeTicks = workTicks;
        int playerCount = CountPlayers();
        if (tickMs < 0) tickMs = 0;
        if (safeTicks < 0) safeTicks = 0;
        // Both buffers share one cursor; it only moves once the ring was already full before this sample.
        bool wasFull = m_Ticks.Count() >= HC_PERF_MAX_SAMPLES;
        Store(m_Ticks, tickMs);
        Store(m_Works, safeTicks);
        if (wasFull)
        {
            m_Cursor++;
            if (m_Cursor >= HC_PERF_MAX_SAMPLES) m_Cursor = 0;
        }
        if (tickMs > m_TickMax) m_TickMax = tickMs;
        if (safeTicks > m_WorkMaxTicks) m_WorkMaxTicks = safeTicks;
        if (m_PlayersMin < 0) m_PlayersMin = playerCount;
        if (playerCount < m_PlayersMin) m_PlayersMin = playerCount;
        if (playerCount > m_PlayersMax) m_PlayersMax = playerCount;
        if (elapsedSeconds > 0) m_WindowElapsed += elapsedSeconds;
        if (m_WindowElapsed >= m_WindowSeconds) EmitWindow();
    }

    void Stop()
    {
        if (!m_Active) return;
        m_Active = false;
        ResetWindow();
        Print("[HollowCountry] Perf sampler stopped");
    }

    protected void Store(array<float> ring, float value)
    {
        if (ring.Count() < HC_PERF_MAX_SAMPLES)
        {
            ring.Insert(value);
            return;
        }
        ring.Set(m_Cursor, value);
    }

    protected void ResetWindow()
    {
        m_WindowElapsed = 0;
        m_Cursor = 0;
        m_TickMax = 0;
        m_WorkMaxTicks = 0;
        m_PlayersMin = -1;
        m_PlayersMax = 0;
        m_WindowTick0 = TickCount(0);
        m_WindowTime0 = 0;
        if (GetGame()) m_WindowTime0 = GetGame().GetTickTime();
        m_Ticks.Clear();
        m_Works.Clear();
    }

    protected void FillSorted(array<float> source, array<float> sorted)
    {
        sorted.Clear();
        for (int i = 0; i < source.Count(); i++) sorted.Insert(source.Get(i));
        sorted.Sort();
    }

    // Nearest-rank percentile of an ascending array.
    protected float Percentile(array<float> sorted, int percent)
    {
        int stored = sorted.Count();
        if (stored <= 0) return 0;
        int rank = (stored * percent + 99) / 100;
        int index = rank - 1;
        if (index < 0) index = 0;
        if (index >= stored) index = stored - 1;
        return sorted.Get(index);
    }

    // Two decimal places without scientific notation.
    protected string FormatMs(float value)
    {
        float safe = value;
        if (safe < 0) safe = 0;
        int hundredths = Math.Round(safe * 100);
        int whole = hundredths / 100;
        int fraction = hundredths % 100;
        string fractionText = fraction.ToString();
        if (fraction < 10) fractionText = "0" + fractionText;
        return whole.ToString() + "." + fractionText;
    }

    protected int CountPlayers()
    {
        m_Players.Clear();
        if (!GetGame()) return 0;
        GetGame().GetPlayers(m_Players);
        return m_Players.Count();
    }

    protected void EmitWindow()
    {
        m_WindowIndex++;
        FillSorted(m_Ticks, m_SortedTicks);
        FillSorted(m_Works, m_SortedWorks);
        int ticksDelta = TickCount(m_WindowTick0);
        float intervalMs = 0;
        if (GetGame()) intervalMs = (GetGame().GetTickTime() - m_WindowTime0) * 1000;
        float ticksPerMs = 0;
        bool calibrated = false;
        if (ticksDelta > 0 && intervalMs > 0 && intervalMs <= HC_PERF_MAX_WINDOW_SECONDS * 2000)
        {
            ticksPerMs = ticksDelta / intervalMs;
            calibrated = ticksPerMs >= HC_PERF_MIN_TICKS_PER_MS && ticksPerMs <= HC_PERF_MAX_TICKS_PER_MS;
        }
        string report = "[HC Perf] window=" + m_WindowIndex.ToString();
        report = report + " samples=" + m_Ticks.Count().ToString();
        report = report + " tick_p50=" + FormatMs(Percentile(m_SortedTicks, 50));
        report = report + " tick_p95=" + FormatMs(Percentile(m_SortedTicks, 95));
        report = report + " tick_p99=" + FormatMs(Percentile(m_SortedTicks, 99));
        report = report + " tick_max=" + FormatMs(m_TickMax);
        if (calibrated)
        {
            report = report + " work_p50=" + FormatMs(Percentile(m_SortedWorks, 50) / ticksPerMs);
            report = report + " work_p95=" + FormatMs(Percentile(m_SortedWorks, 95) / ticksPerMs);
            report = report + " work_max=" + FormatMs(m_WorkMaxTicks / ticksPerMs);
        }
        report = report + " players_min=" + m_PlayersMin.ToString();
        report = report + " players_max=" + m_PlayersMax.ToString();
        if (calibrated) report = report + " ticks_per_ms=" + FormatMs(ticksPerMs);
        if (!calibrated) report = report + " calibration=invalid";
        Print("" + report);
        ResetWindow();
    }
}
