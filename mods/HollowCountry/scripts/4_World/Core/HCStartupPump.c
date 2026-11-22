// Shared startup-only catch-up. Native scripts-1.30.164289:
// Global/Game.c:1552 GetUpdateQueue; DayZGame.c:3027 SYSTEM Invoke(timeslice);
// 2_GameLib/tools.c:115-124 ScriptInvoker Insert/Remove; EnSystem.c:106 TickCount.
// Owners retain all atomic/unit bounds. A native call cannot be preempted.
class HCStartupOwner
{
    string Name;
    float Started;
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
    protected static int s_Cursor;
    protected static int s_Frame;
    protected static bool s_Installed;
    protected static bool s_InSlice;
    protected static bool s_Disabled = true;

    static void HCBegin()
    {
        s_Disabled = FileExist("$profile:HollowCountry/acceptance/startup_catchup.disable");
    }

    static void HCRegister(HCStartupOwner owner, string name)
    {
        if (!owner || !GetGame() || !GetGame().IsServer()) { return; }
        owner.Name = name;
        owner.Started = GetGame().GetTickTime();
        // Fixed registration ceiling, including completed owners, bounds every visit.
        if (s_Owners.Count() >= 32 || s_Disabled)
        {
            HCFinish(owner);
            return;
        }
        s_Owners.Insert(owner);
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
        Print("[HC Startup] owner=" + owner.Name + " catchup_s=" + elapsed.ToString() + " frames=" + owner.Frames.ToString() + " slices=" + owner.Slices.ToString() + " ms_max=" + owner.MsMax.ToString());
    }

    // The shared frame deadline replaces tick-pool admission only during a pump slice.
    static bool HCInSlice() { return s_InSlice; }

    // Called only inside catch-up slices; tick callers retain their existing caps.
    static float HCSliceMs(float cap)
    {
        if (s_InSlice) { return Math.Min(cap, s_Budget.HCRemainingMs()); }
        return cap;
    }

    static void HCFrame(float timeslice)
    {
        if (!GetGame().IsServer()) { return; }
        s_Frame++;
        HCPerfConfig config = HCPerfConfig.HCGet();
        s_Budget.HCReset(32, config.StartupFrameMs);
        int idle = 0;
        // Persistent round-robin cursor also survives a frame exhausting its clock.
        // 32 slices/frame is a second bound even on an uncalibrated/fast clock.
        while (s_Owners.Count() > 0 && idle < s_Owners.Count() && s_Budget.HCContinue())
        {
            if (s_Cursor >= s_Owners.Count()) { s_Cursor = 0; }
            HCStartupOwner owner = s_Owners[s_Cursor];
            s_Cursor++;
            if (owner.Finished) { idle++; continue; }
            if (owner.FinishRequested || !owner.HCNeedsWork() || GetGame().GetTickTime() - owner.Started >= config.StartupDeadlineSeconds)
            {
                HCFinish(owner);
                idle++;
                continue;
            }
            idle = 0;
            if (!(s_Budget.HCRemainingMs() > 0)) { break; }
            if (owner.LastFrame != s_Frame) { owner.Frames++; owner.LastFrame = s_Frame; }
            int began = TickCount(0);
            s_InSlice = true;
            owner.HCSlice();
            s_InSlice = false;
            float ms = s_Budget.HCMilliseconds(TickCount(began));
            owner.MsMax = Math.Max(owner.MsMax, ms);
            owner.Slices++;
            if (owner.FinishRequested || !owner.HCNeedsWork()) { HCFinish(owner); }
        }
        bool active = false;
        foreach (HCStartupOwner retained : s_Owners)
        {
            if (!retained.Finished) { active = true; break; }
        }
        if (!active && s_Installed)
        {
            GetGame().GetUpdateQueue(CALL_CATEGORY_SYSTEM).Remove(HCFrame);
            s_Installed = false;
        }
    }

    static void HCStop()
    {
        foreach (HCStartupOwner owner : s_Owners) { HCFinish(owner); }
        if (s_Installed && GetGame()) { GetGame().GetUpdateQueue(CALL_CATEGORY_SYSTEM).Remove(HCFrame); }
        s_Installed = false;
        s_InSlice = false;
        s_Owners.Clear();
        s_Cursor = 0;
    }
}
