// Shared raw-counter window, owned by the module. Native EnSystem.c:106 TickCount.
// Child cycle spans are subtracted from cycle housekeeping, never double counted.
// Source audit for build 173's isolated 34.17 ms tick (not a native verdict):
// - HC-29 prune/sample/probe retain cursors under HCPerfSlices; default four
//   rows/tick explains deferred falling by 240/minute. A probe still performs
//   two nav samples plus FindPath atomically; its three item labels expose them.
// - Cycle: one town config row/tick (512 source / 64 retained), MaxHerds and
//   MaxMovers bound home/prune/summary walks. Survey now tests one candidate
//   per visited row. One animal request spans three shared TakePath grants;
//   native FindPath itself has no inspected time/expansion limit.
// - Resource survey classifies a supplied point/body; it discovers no cohort.
// - Cycle animals are native input leases, not spawns. Infected town requests
//   use the existing owner's <=256 actor scan and <=40-member pack, one offer
//   per tick; Reachable/ActivateWaypoint are still native-heavy and belong to
//   Infected's tick. Deferred maxima below retain their cross-owner cost.
// - Wildlife observation samples a capped registry with unit/clock slices;
//   snapshots scan up to 256 bindings and copy <=64 facts. Provider maintenance
//   has shared named grants, bounded contacts/clues and one creation attempt.
//   That attempt can include <=16 observers x six rays, CreateObjectEx, death,
//   verified allocation/ledger writes. Refill can renew nine ledger files.
// - Scene receipt selection is cursor/slice bounded but HCCommit and provider
//   claim/refill call synchronous HCEncounterStore.Save (shared World owner).
//   These disk calls and native creation cannot be preempted by a unit grant.
// - HC-29 routine saves run in the shared scheduler; excluded RuntimeStore and
//   SaveJob already publish save maxima. The supplied save_phase=0/14 us line
//   is one instant, not evidence excluding save cost elsewhere in the window.
// Keep atomic query / creation / disk latency and herd movement cadence pending
// until the lead's Mission compile and retail soak with real activity counters.
class HCEcologySteps
{
    protected static ref HCStepTimer s_Timer;
    protected static int s_CycleParts;

    static void Begin()
    {
        if (!s_Timer)
        {
            s_Timer = new HCStepTimer("Ecology");
            s_Timer.HCDefine("hc29");
            s_Timer.HCDefine("cycle");
            s_Timer.HCDefine("survey");
            s_Timer.HCDefine("navsample");
            s_Timer.HCDefine("path");
            s_Timer.HCDefine("ray");
            s_Timer.HCDefine("wildlife");
            s_Timer.HCDefine("scenes");
        }
        s_CycleParts = 0;
    }

    static void Record(int step, int start, string item)
    {
        if (!s_Timer) { return; }
        int elapsed = TickCount(start);
        s_Timer.HCAdd(step, elapsed);
        // The broad runtime/wildlife spans have finer item labels inside them.
        if (step != 0 && step != 6) { s_Timer.HCItem(item, elapsed); }
        if (step >= 2 && step <= 5) { s_CycleParts += elapsed; }
    }

    static void Cycle(int start)
    {
        if (s_Timer) { s_Timer.HCAdd(1, Math.Max(0, TickCount(start) - s_CycleParts)); }
    }

    static void Item(string item, int start)
    {
        if (s_Timer) { s_Timer.HCItem(item, TickCount(start)); }
    }

    // Migration is invoked by Infected, outside Ecology's module tick. Keep
    // its cost out of worst_tick_ticks; the shared format has deferred maxima.
    static void Deferred(int start)
    {
        if (s_Timer) { s_Timer.HCDeferred(TickCount(start)); }
    }

    static void End(int start)
    {
        if (s_Timer) { s_Timer.HCEndTick(TickCount(start)); }
    }
}
