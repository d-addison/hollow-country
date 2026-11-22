// Shared startup-only catch-up. Native scripts-1.30.164289:
// Global/Game.c:1552 GetUpdateQueue; DayZGame.c:3027 SYSTEM Invoke(timeslice);
// 2_GameLib/tools.c:115-124 ScriptInvoker Insert/Remove; EnSystem.c:106 TickCount.
// Owners retain all atomic/unit bounds. A native call cannot be preempted.
class HCStartupOwner
{
    string Name;
    int Priority;
    bool DeadlineReached;
    // Registered: mission-init registration time. Started: first pumped frame;
    // the SYSTEM queue does not tick during server load, so the deadline starts here.
    float Registered;
    float Started;
    bool Visited;
    int Frames;
    int Slices;
    int LastFrame = -1;
    float MsMax;
    bool Finished;
    bool FinishRequested;
    bool HCNeedsWork() { return false; }
    void HCSlice() {}
}

class HCStartupPump
{
    protected static ref array<ref HCStartupOwner> s_Owners = new array<ref HCStartupOwner>;
    protected static ref HCStartupFrameBudget s_Budget = new HCStartupFrameBudget;
    protected static float s_SliceMs;
    protected static int s_SliceBegan;
    protected static float s_DrainStarted;
    protected static int s_DeadlineOwners;
    protected static int s_OverrunFrames;
    protected static float s_FrameMsMax;
    protected static int s_Frame;
    protected static int s_FairCursor;
    protected static bool s_Installed;
    protected static bool s_InSlice;
    protected static bool s_Disabled = true;

    static void HCBegin()
    {
        s_Disabled = FileExist("$profile:HollowCountry/acceptance/startup_catchup.disable");
    }

    // Tier 0: readiness dependencies; tier 1: normal startup; tier 2: optional
    // caches. Existing owners keep their call sites; new owners may choose a tier.
    protected static int HCPriority(string name)
    {
        if (name == "routes_catalog" || name == "road_graph" || name == "interiors_pack") { return 0; }
        // Scenes and Shelters must admit their actual data/placement before ready.
        if (name == "story_index" || name == "shelters") { return 0; }
        if (name == "admin_teleport") { return 2; }
        return 1;
    }

    static void HCRegister(HCStartupOwner owner, string name, int priority = -1)
    {
        if (!owner || !GetGame() || !GetGame().IsServer()) { return; }
        owner.Name = name;
        if (priority < 0) { priority = HCPriority(name); }
        owner.Priority = Math.Clamp(priority, 0, 2);
        owner.Registered = GetGame().GetTickTime();
        owner.Started = owner.Registered;
        // Fixed registration ceiling, including completed owners, bounds every visit.
        if (s_Owners.Count() >= 32 || s_Disabled)
        {
            HCFinish(owner);
            return;
        }
        s_Owners.Insert(owner);
        // Stable insertion, bounded by the 32-owner registration ceiling.
        int index = s_Owners.Count() - 1;
        while (index > 0 && s_Owners[index - 1].Priority > owner.Priority)
        {
            s_Owners[index] = s_Owners[index - 1];
            index--;
        }
        s_Owners[index] = owner;
        // A late registration can sort ahead of the next fair owner. Preserve
        // that owner's turn; before the first frame, start in tier order.
        if (s_Frame > 0 && index <= s_FairCursor) { s_FairCursor++; }
        if (!s_Installed)
        {
            s_Installed = true;
            GetGame().GetUpdateQueue(CALL_CATEGORY_SYSTEM).Insert(HCFrame);
        }
    }

    static void HCFinish(HCStartupOwner owner)
    {
        if (!owner || owner.Finished) { return; }
        if (s_InSlice) { owner.FinishRequested = true; return; }
        owner.Finished = true;
        float elapsed = Math.Max(0, GetGame().GetTickTime() - owner.Started);
        float waited = Math.Max(0, owner.Started - owner.Registered);
        string reason = "complete";
        if (owner.DeadlineReached) { reason = "deadline"; }
        else if (s_Disabled) { reason = "disabled"; }
        else if (owner.HCNeedsWork()) { reason = "stopped"; }
        string tier = " tier=" + owner.Priority.ToString() + " reason=" + reason;
        Print("[HC Startup] owner=" + owner.Name + tier + " wait_s=" + waited.ToString() + " catchup_s=" + elapsed.ToString() + " frames=" + owner.Frames.ToString() + " slices=" + owner.Slices.ToString() + " ms_max=" + owner.MsMax.ToString());
    }

    // The shared frame deadline replaces tick-pool admission only during a pump slice.
    static bool HCInSlice() { return s_InSlice; }

    // Called only inside catch-up slices; tick callers retain their existing caps.
    static float HCSliceMs(float cap)
    {
        if (s_InSlice)
        {
            float remaining = Math.Max(0, s_SliceMs - s_Budget.HCMilliseconds(TickCount(s_SliceBegan)));
            return Math.Min(cap, Math.Min(remaining, s_Budget.HCRemainingMs()));
        }
        return cap;
    }

    protected static bool HCActive(HCStartupOwner owner, HCPerfConfig config)
    {
        if (owner.Finished) { return false; }
        if (!owner.Visited)
        {
            owner.Visited = true;
            owner.Started = GetGame().GetTickTime();
        }
        if (owner.FinishRequested || !owner.HCNeedsWork()) { HCFinish(owner); return false; }
        if (GetGame().GetTickTime() - owner.Started >= config.StartupDeadlineSeconds)
        {
            owner.DeadlineReached = true;
            s_DeadlineOwners++;
            HCFinish(owner);
            return false;
        }
        return true;
    }

    protected static void HCRunSlice(HCStartupOwner owner, float milliseconds)
    {
        s_SliceMs = milliseconds;
        if (owner.LastFrame != s_Frame) { owner.Frames++; owner.LastFrame = s_Frame; }
        int began = TickCount(0);
        s_SliceBegan = began;
        s_InSlice = true;
        owner.HCSlice();
        s_InSlice = false;
        float ms = s_Budget.HCMilliseconds(TickCount(began));
        owner.MsMax = Math.Max(owner.MsMax, ms);
        owner.Slices++;
        if (owner.FinishRequested || !owner.HCNeedsWork()) { HCFinish(owner); }
    }

    static void HCFrame(float timeslice)
    {
        if (!GetGame().IsServer()) { return; }
        if (s_Frame == 0) { s_DrainStarted = GetGame().GetTickTime(); }
        s_Frame++;
        HCPerfConfig config = HCPerfConfig.HCGet();
        s_Budget.HCReset(32, config.StartupFrameMs);
        int began = TickCount(0);
        int active = 0;
        foreach (HCStartupOwner candidate : s_Owners)
        {
            if (HCActive(candidate, config)) { active++; }
        }
        int slices = 0;
        int remaining = active;
        // Rotate through tier order across frames before granting bonus work.
        // Owners can admit one atomic unit even with HCSliceMs(0), so stop
        // after exhaustion instead of forcing every owner through this frame.
        // At least one slice advances; the next owner leads the next frame.
        // With <=32 registrations, every pending owner (including tier 0) gets
        // a turn within <=32 frames, even when each atomic unit overruns.
        int visits = 0;
        int fairLimit = s_Owners.Count();
        while (visits < fairLimit && slices < 32)
        {
            if (slices > 0 && s_Budget.HCRemainingMs() <= 0) { break; }
            if (s_FairCursor >= s_Owners.Count()) { s_FairCursor = 0; }
            HCStartupOwner fair = s_Owners[s_FairCursor];
            s_FairCursor++;
            if (s_FairCursor >= s_Owners.Count()) { s_FairCursor = 0; }
            visits++;
            if (fair.Finished) { continue; }
            float share = s_Budget.HCRemainingMs() / (remaining + 1);
            HCRunSlice(fair, share);
            remaining--;
            slices++;
        }
        // Only spare time goes to extra slices, readiness-critical tiers first.
        // <=32 total slices/frame, including the fair pass; no extra allocation.
        int cursor = 0;
        int idle = 0;
        while (slices < 32 && idle < s_Owners.Count() && s_Budget.HCRemainingMs() > 0)
        {
            if (cursor >= s_Owners.Count()) { cursor = 0; }
            HCStartupOwner bonus = s_Owners[cursor];
            cursor++;
            if (bonus.Finished) { idle++; continue; }
            idle = 0;
            HCRunSlice(bonus, s_Budget.HCRemainingMs());
            slices++;
        }
        float frameMs = s_Budget.HCMilliseconds(TickCount(began));
        s_FrameMsMax = Math.Max(s_FrameMsMax, frameMs);
        if (frameMs > config.StartupFrameMs) { s_OverrunFrames++; }
        bool pending = false;
        foreach (HCStartupOwner retained : s_Owners)
        {
            if (!retained.Finished) { pending = true; break; }
        }
        if (!pending && s_Installed)
        {
            float elapsed = Math.Max(0, GetGame().GetTickTime() - s_DrainStarted);
            string drain = "[HC Startup] drain_s=" + elapsed.ToString() + " owners=" + s_Owners.Count().ToString();
            drain = drain + " deadline_owners=" + s_DeadlineOwners.ToString() + " overrun_frames=" + s_OverrunFrames.ToString();
            Print(drain + " frame_ms_max=" + s_FrameMsMax.ToString());
            GetGame().GetUpdateQueue(CALL_CATEGORY_SYSTEM).Remove(HCFrame);
            s_Installed = false;
            s_Frame = 0;
            s_FairCursor = 0;
            s_DeadlineOwners = 0;
            s_OverrunFrames = 0;
            s_FrameMsMax = 0;
        }
    }

    static void HCStop()
    {
        foreach (HCStartupOwner owner : s_Owners) { HCFinish(owner); }
        if (s_Installed && GetGame()) { GetGame().GetUpdateQueue(CALL_CATEGORY_SYSTEM).Remove(HCFrame); }
        s_Installed = false;
        s_InSlice = false;
        s_Owners.Clear();
        s_Frame = 0;
        s_FairCursor = 0;
        s_DeadlineOwners = 0;
        s_OverrunFrames = 0;
        s_FrameMsMax = 0;
        s_SliceMs = 0;
    }
}
