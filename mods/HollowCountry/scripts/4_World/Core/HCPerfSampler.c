// Server-only tick performance sampler. Not an HCModule; HCServer owns one instance.
// Collects the HC tick interval and the time HC modules spent inside one tick, and prints one
// summary line per window. Memory is bounded: two ring buffers and two sort buffers of at most
// HC_PERF_MAX_SAMPLES floats, module buffers capped at HC_PERF_MAX_MODULES, and 64*4 cost integers.
// No file I/O. Output is read by tools/testing/perf_capture.py.
// Verified in the installed 1.30.164289 script dump: array<T>.Insert/Set/Get/Count/Clear/Sort/Reserve/Find (1_Core/proto/EnScript.c:380-493),
// CGame.GetPlayers(out array<Man>), CGame.GetTickTime, Math.Round, string.ToString, Print,
// proto native int TickCount(int prev) (1_Core/proto/EnSystem.c:106: ticks between prev and now).
// The TickCount unit is NOT documented and vanilla never calls it, so work is passed in as raw ticks and
// converted per window: ticks_per_ms = TickCount(window start) / server-clock milliseconds of the window.
// Both are deltas, so int wrap is not a concern while the window stays at or below 120 s at the observed rate
// (about 10000 ticks per ms, so 1.2 billion ticks per 120 s window, below 2^31).
// A negative or zero delta, an interval longer than twice the window clamp, or a ticks_per_ms outside
// [HC_PERF_MIN_TICKS_PER_MS, HC_PERF_MAX_TICKS_PER_MS] prints calibration=invalid and omits every work_* value.
// HC-29: invalid windows publish attributed raw ticks before reset, never a
// conversion using another window's rate. Cached conversion expires on Stop.
// Players: the count is read at every sample; the line carries the window minimum and maximum.
// The line is printed through the expression "" + report. Print(report) with a variable makes the engine print
// the declaration (string report = '...'), as observed in a real RPT.
const int HC_PERF_MAX_SAMPLES = 512;
const int HC_PERF_MAX_MODULES = 64;
// Per-module [HC Cost] lines per emission (plus the pinned Ecology line when outside the top N);
// a single [HC CostTotal] line covers all modules.
const int HC_PERF_COST_TOP = 8;
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
    protected int m_SlowTickCount;
    // Stable registration slots: capped/reserved once; no name lookup in SampleModule.
    protected ref array<string> m_ModuleNames = new array<string>();
    protected ref array<int> m_ModuleMaxTicks = new array<int>();
    protected ref array<string> m_SortedModuleNames = new array<string>();
    // Four maxima per existing module slot: startup, native callback, save,
    // admission. Attribution can overlap module work; these are not additive.
    // Fixed 64*4 integers, no new registry, clock, player scan or profiler.
    protected ref array<int> m_CostMaxTicks = new array<int>();
    // Scratch flags for the top-N selection; one per module slot, refilled at each emission.
    protected ref array<int> m_CostPicked = new array<int>();
    protected float m_TicksPerMs;
    protected int m_EcologyIndex = -1;
    protected ref array<Man> m_Players = new array<Man>();

    void HCPerfSampler()
    {
        m_CostMaxTicks.Reserve(HC_PERF_MAX_MODULES * 4);
        m_CostPicked.Reserve(HC_PERF_MAX_MODULES);
        m_ModuleNames.Reserve(HC_PERF_MAX_MODULES);
        m_ModuleMaxTicks.Reserve(HC_PERF_MAX_MODULES);
        m_SortedModuleNames.Reserve(HC_PERF_MAX_MODULES);
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
        m_CostMaxTicks.Clear();
        m_TicksPerMs = 0;
        HCRefreshEcologyCalibration();
        m_EcologyIndex = -1;
        m_ModuleNames.Clear();
        m_ModuleMaxTicks.Clear();
        m_SortedModuleNames.Clear();
        ResetWindow();
        m_Active = true;
        Print("[HollowCountry] Perf sampler started, window seconds: " + m_WindowSeconds.ToString());
    }

    // HCServer registers active modules once after Start, in tick-loop order.
    void RegisterModule(string name)
    {
        if (!m_Active || m_ModuleNames.Count() >= HC_PERF_MAX_MODULES) return;
        if (name == "Ecology") m_EcologyIndex = m_ModuleNames.Count();
        m_ModuleNames.Insert(name);
        m_ModuleMaxTicks.Insert(0);
        m_CostMaxTicks.Insert(-1);
        m_CostMaxTicks.Insert(-1);
        m_CostMaxTicks.Insert(-1);
        m_CostMaxTicks.Insert(-1);
    }

    void SampleModule(int moduleIndex, int workTicks)
    {
        if (!m_Active || moduleIndex < 0 || moduleIndex >= m_ModuleMaxTicks.Count()) return;
        if (workTicks > m_ModuleMaxTicks.Get(moduleIndex)) m_ModuleMaxTicks.Set(moduleIndex, workTicks);
        if (moduleIndex == m_EcologyIndex) HCSampleEcology(moduleIndex);
    }

    // Runtime keeps callback peaks until the next module sample. Startup runs
    // before sampler Start, so its cached admission/startup costs survive too.
    // No entity/player scan or module callback; registration binds the slot once.
    protected void HCSampleEcology(int moduleIndex)
    {
        HCEcologyRuntime runtime = HCEcologyRuntime.HCPeek();
        if (!runtime) return;
        runtime.HCSetCalibration(m_TicksPerMs);
        SampleCost(moduleIndex, 0, runtime.HCStartupTicks());
        SampleCost(moduleIndex, 1, runtime.HCCallbackTicks());
        SampleCost(moduleIndex, 2, runtime.HCSaveTicks());
        SampleCost(moduleIndex, 3, runtime.HCAdmissionTicks());
        runtime.HCResetCostTicks();
    }

    // Refresh when a window closes, including invalid calibration and Stop;
    // waiting for the next module sample would leave a stale rate in HCReport.
    // Passive singleton lookup only: no lifecycle callback or native query.
    protected void HCRefreshEcologyCalibration()
    {
        HCEcologyRuntime runtime = HCEcologyRuntime.HCPeek();
        if (runtime) runtime.HCSetCalibration(m_TicksPerMs);
    }

    // Same validated registration index as SampleModule. Kind: 0 startup,
    // 1 native callback, 2 save, 3 admission. Raw units are never called ms.
    void SampleCost(int moduleIndex, int kind, int workTicks)
    {
        if (!m_Active || moduleIndex < 0 || moduleIndex >= m_ModuleNames.Count()) return;
        if (kind < 0 || kind >= 4 || workTicks < 0) return;
        int costSlot = moduleIndex * 4 + kind;
        if (workTicks > m_CostMaxTicks.Get(costSlot)) m_CostMaxTicks.Set(costSlot, workTicks);
    }

    // A caller must refresh this each window. Zero explicitly refuses conversion.
    float HCTicksPerMs() { return m_TicksPerMs; }

    protected string FormatCost(int ticks, float ticksPerMs)
    {
        if (ticks < 0) return "unobserved";
        return FormatMs(ticks / ticksPerMs);
    }

    // Largest observed cost across the four kinds; -1 when nothing was observed.
    protected int CostPeak(int moduleIndex)
    {
        int slot = moduleIndex * 4;
        int peak = m_CostMaxTicks.Get(slot);
        int kind = 1;
        while (kind < 4)
        {
            int value = m_CostMaxTicks.Get(slot + kind);
            if (value > peak) peak = value;
            kind++;
        }
        return peak;
    }

    // One totals line, then the HC_PERF_COST_TOP costliest modules by peak
    // (descending; ties and unobserved modules keep registration order). The
    // Ecology module is pinned last when it fell outside the top N, so at most
    // N + 1 lines print and Ecology never prints twice. m_CostPicked holds the
    // 1-based print order per module, 0 = not printed.
    // The *_maxsum_* fields add each module's own per-window MAXIMUM. Those
    // maxima need not coincide in time, and startup/callback/save/admission
    // overlap, so they are an upper bound per kind and never a total cost.
    protected void EmitCosts(float ticksPerMs)
    {
        int moduleCount = m_ModuleNames.Count();
        int shown = moduleCount;
        if (shown > HC_PERF_COST_TOP) shown = HC_PERF_COST_TOP;
        int observed = 0;
        int sumStartup = 0;
        int sumCallback = 0;
        int sumSave = 0;
        int sumAdmission = 0;
        m_CostPicked.Clear();
        int scan = 0;
        while (scan < moduleCount)
        {
            m_CostPicked.Insert(0);
            int scanSlot = scan * 4;
            if (CostPeak(scan) >= 0) observed++;
            if (m_CostMaxTicks.Get(scanSlot) > 0) sumStartup += m_CostMaxTicks.Get(scanSlot);
            if (m_CostMaxTicks.Get(scanSlot + 1) > 0) sumCallback += m_CostMaxTicks.Get(scanSlot + 1);
            if (m_CostMaxTicks.Get(scanSlot + 2) > 0) sumSave += m_CostMaxTicks.Get(scanSlot + 2);
            if (m_CostMaxTicks.Get(scanSlot + 3) > 0) sumAdmission += m_CostMaxTicks.Get(scanSlot + 3);
            scan++;
        }
        int rank = 0;
        while (rank < shown)
        {
            int best = -1;
            int bestPeak = -2;
            int pick = 0;
            while (pick < moduleCount)
            {
                if (m_CostPicked.Get(pick) == 0)
                {
                    int pickPeak = CostPeak(pick);
                    if (pickPeak > bestPeak)
                    {
                        best = pick;
                        bestPeak = pickPeak;
                    }
                }
                pick++;
            }
            if (best < 0) break;
            rank++;
            m_CostPicked.Set(best, rank);
        }
        int printed = rank;
        if (m_EcologyIndex >= 0 && m_EcologyIndex < moduleCount && m_CostPicked.Get(m_EcologyIndex) == 0)
        {
            printed++;
            m_CostPicked.Set(m_EcologyIndex, printed);
        }
        int omitted = moduleCount - printed;
        string total = "[HC CostTotal] modules=" + moduleCount.ToString() + " observed=" + observed.ToString();
        total = total + " shown=" + printed.ToString() + " omitted=" + omitted.ToString();
        if (ticksPerMs > 0)
        {
            total = total + " startup_maxsum_ms=" + FormatMs(sumStartup / ticksPerMs);
            total = total + " callback_maxsum_ms=" + FormatMs(sumCallback / ticksPerMs);
            total = total + " save_maxsum_ms=" + FormatMs(sumSave / ticksPerMs);
            total = total + " admission_maxsum_ms=" + FormatMs(sumAdmission / ticksPerMs);
        }
        else
        {
            total = total + " startup_maxsum_ticks=" + sumStartup.ToString();
            total = total + " callback_maxsum_ticks=" + sumCallback.ToString();
            total = total + " save_maxsum_ticks=" + sumSave.ToString();
            total = total + " admission_maxsum_ticks=" + sumAdmission.ToString();
            total = total + " calibration=invalid reason=invalid_calibration";
        }
        Print("" + total + "; runtime=PENDING");
        int order = 1;
        while (order <= printed)
        {
            int emit = 0;
            while (emit < moduleCount)
            {
                if (m_CostPicked.Get(emit) == order)
                {
                    EmitCostLine(emit, ticksPerMs);
                    break;
                }
                emit++;
            }
            order++;
        }
    }

    protected void EmitCostLine(int costIndex, float ticksPerMs)
    {
        string cost = "[HC Cost] module=" + m_ModuleNames.Get(costIndex);
        int slot = costIndex * 4;
        if (ticksPerMs > 0)
        {
            cost = cost + " startup_ms=" + FormatCost(m_CostMaxTicks.Get(slot), ticksPerMs);
            cost = cost + " callback_ms=" + FormatCost(m_CostMaxTicks.Get(slot + 1), ticksPerMs);
            cost = cost + " save_ms=" + FormatCost(m_CostMaxTicks.Get(slot + 2), ticksPerMs);
            cost = cost + " admission_ms=" + FormatCost(m_CostMaxTicks.Get(slot + 3), ticksPerMs);
        }
        else
        {
            // -1 means unobserved, as in SampleCost. Preserve once-only
            // startup/admission evidence even if this window cannot convert.
            int startupTicks = m_CostMaxTicks.Get(slot);
            int callbackTicks = m_CostMaxTicks.Get(slot + 1);
            int saveTicks = m_CostMaxTicks.Get(slot + 2);
            int admissionTicks = m_CostMaxTicks.Get(slot + 3);
            cost = cost + " startup_ticks=" + startupTicks.ToString();
            cost = cost + " callback_ticks=" + callbackTicks.ToString();
            cost = cost + " save_ticks=" + saveTicks.ToString();
            cost = cost + " admission_ticks=" + admissionTicks.ToString();
            cost = cost + " calibration=invalid reason=invalid_calibration";
        }
        Print("" + cost + "; runtime=PENDING");
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
        Store(m_Works, (float)safeTicks);
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
        // HCServer keeps this window open through every module's OnStop.
        // Consume the owner's cached shutdown save/refusal costs after Finish.
        if (m_EcologyIndex >= 0) HCSampleEcology(m_EcologyIndex);
        // A partial window has no freshly validated conversion. Preserve raw
        // save costs (including failed writes) rather than reuse an old rate.
        EmitCosts(0);
        m_Active = false;
        m_TicksPerMs = 0;
        HCRefreshEcologyCalibration();
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
        int costReset = 0;
        while (costReset < m_CostMaxTicks.Count())
        {
            m_CostMaxTicks.Set(costReset, -1);
            costReset++;
        }
        m_WindowElapsed = 0;
        m_Cursor = 0;
        m_TickMax = 0;
        m_WorkMaxTicks = 0;
        m_SlowTickCount = 0;
        int moduleReset = 0;
        while (moduleReset < m_ModuleMaxTicks.Count())
        {
            m_ModuleMaxTicks.Set(moduleReset, 0);
            moduleReset++;
        }
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
        int hundredths = (int)(Math.Round(safe * 100));
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
            ticksPerMs = (float)ticksDelta / intervalMs;
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
            report = report + " work_max=" + FormatMs((float)m_WorkMaxTicks / ticksPerMs);
        }
        report = report + " players_min=" + m_PlayersMin.ToString();
        report = report + " players_max=" + m_PlayersMax.ToString();
        if (calibrated) report = report + " ticks_per_ms=" + FormatMs(ticksPerMs);
        if (!calibrated) report = report + " calibration=invalid";
        if (calibrated)
        {
            // HCServer's validated >=500 ms interval and <=120 s window fit
            // all samples in the 512-slot work buffer. Count strictly over 10 ms.
            int workIndex = 0;
            while (workIndex < m_Works.Count())
            {
                if (m_Works.Get(workIndex) / ticksPerMs > 10.0) m_SlowTickCount++;
                workIndex++;
            }
            m_SortedModuleNames.Clear();
            // First registered slot per name, built once so the sorted pass below
            // does not rescan m_ModuleNames per module.
            map<string, int> slotByName = new map<string, int>;
            int nameSlot = 0;
            foreach (string registeredName : m_ModuleNames)
            {
                m_SortedModuleNames.Insert(registeredName);
                if (!slotByName.Contains(registeredName)) { slotByName.Insert(registeredName, nameSlot); }
                nameSlot++;
            }
            m_SortedModuleNames.Sort();
            string slowestName = "none";
            int slowestTicks = -1;
            string moduleReport = "";
            int moduleOrder = 0;
            while (moduleOrder < m_SortedModuleNames.Count())
            {
                string moduleName = m_SortedModuleNames.Get(moduleOrder);
                int moduleSlot = slotByName.Get(moduleName);
                int moduleTicks = m_ModuleMaxTicks.Get(moduleSlot);
                if (moduleTicks > slowestTicks)
                {
                    slowestTicks = moduleTicks;
                    slowestName = moduleName;
                }
                if (moduleOrder > 0) moduleReport = moduleReport + ",";
                moduleReport = moduleReport + moduleName + ":" + FormatMs((float)moduleTicks / ticksPerMs);
                moduleOrder++;
            }
            report = report + " slowest_module=" + slowestName;
            report = report + " slowest_module_max_ms=" + FormatMs((float)slowestTicks / ticksPerMs);
            report = report + " slow_ticks=" + m_SlowTickCount.ToString();
            if (m_ModuleNames.Count() > 0) report = report + " mod_max=" + moduleReport;
        }
        m_TicksPerMs = 0;
        if (calibrated)
        {
            m_TicksPerMs = ticksPerMs;
        }
        HCRefreshEcologyCalibration();
        EmitCosts(m_TicksPerMs);
        Print("" + report);
        ResetWindow();
    }
}
