// Dev-only ladder driver. Native scripts-1.30.164289 evidence:
// 3_Game/Entities/Building.c:23-25 ladder count/top/bottom (space unobserved);
// 3_Game/Entities/Object.c:192 GetActionComponentNameList, :287 GetPosition,
// :467 GetType, :517 IsAlive, :873 ModelToWorld; Entities/Man.c:63 IsUnconscious;
// 3_Game/Global/Game.c:930 GetObjectsAtPosition3D; Global/DayZPhysics.c:199 RaycastRV;
// 4_World/Static/MiscGameplayFunctions.c:778 GetPlayerHeadPosition;
// 4_World/Classes/UserActionsComponent/Actions/Interact/ActionEnterLadder.c:19-114
// checks the real geometry component, memory points, distance and approach side;
// :117-150 Start calls StartCommand_Ladder on the player's own action path.
// ActionExitLadder.c:15-31 checks CanExit then Exit; 3_Game/human.c:671-675,
// :1512 GetCommand_Ladder; :253-256 controller speed/angle overrides; :1458 GetInputController.
// 4_World/Entities/ManBase/PlayerBase.c:1887 GetActionManager;
// ActionManagerBase.c:91 GetRunningAction, :214 GetAction; ActionBase.c:968 Can; ActionTargets.c:125 ctor;
// ActionManagerClient.c:804 PerformActionStart. No direct command start or position writes.
class HCDriverClimb
{
    protected Building m_Building;
    protected int m_Ladder;
    protected vector m_Bottom;
    protected vector m_Top;
    protected float m_Age;
    protected float m_Held;
    protected float m_TopY;
    protected float m_Wait;
    protected int m_Phase;
    protected int m_Ray;
    protected int m_Scan;
    protected float m_Best;
    protected bool m_Timeout;
    protected bool m_Entered;
    protected bool m_Logged;
    protected int m_Started;
    protected ref array<Object> m_Near = new array<Object>;
    protected ref array<CargoBase> m_Cargo = new array<CargoBase>;
    protected ref set<Object> m_Hits = new set<Object>;
    protected ref array<string> m_Selections = new array<string>;
    protected ref ActionTarget m_None;
    protected ref HCWorkBudget m_Budget = new HCWorkBudget;

    bool AwaitingEntry()
    {
        return m_Entered;
    }

    float Elapsed()
    {
        // Native 3_Game/Global/Game.c:1535 GetTime, receiver-local milliseconds.
        return (GetGame().GetTime() - m_Started) * 0.001;
    }

    void Drain(PlayerBase player, HCDriverWalker walker)
    {
        m_Timeout = true;
        walker.Release(player);
        ApplyClimbInput(player, 0, 0);
#ifndef SERVER
        ActionManagerClient manager = ActionManagerClient.Cast(player.GetActionManager());
        if (manager && player.IsAlive() && !player.IsUnconscious()) { TryExit(player, manager); }
#endif
    }

    void ReportExternalEnd(PlayerBase player, HCDriverWalker walker, int code, string reason)
    {
        if (m_Logged) { return; }
        string detail;
        Finish(player, walker, code, reason, detail);
    }

    // Phases: 0 query, 1 incremental nearest scan, 2 walk bottom, 3 enter bottom,
    // 4 ascend, 5 hold on roof, 6 return to top, 7 enter top, 8 descend; timeout drains independently.
    void Begin()
    {
        m_Building = null;
        m_Ladder = -1;
        m_Bottom = vector.Zero;
        m_Top = vector.Zero;
        m_Age = 0;
        m_Held = 0;
        m_TopY = 0;
        m_Wait = 0;
        m_Phase = 0;
        m_Ray = 0;
        m_Scan = 0;
        m_Best = 1000000000;
        m_Timeout = false;
        m_Entered = false;
        m_Logged = false;
        m_Started = GetGame().GetTime();
    }

    protected void ApplyClimbInput(PlayerBase player, float speed, float angle)
    {
#ifndef SERVER
        HumanInputController input = player.GetInputController();
        if (input)
        {
            input.OverrideMovementSpeed(HumanInputControllerOverrideType.ONE_FRAME, speed);
            input.OverrideMovementAngle(HumanInputControllerOverrideType.ONE_FRAME, angle);
        }
#endif
    }

    protected int Finish(PlayerBase player, HCDriverWalker walker, int code, string reason, out string detail)
    {
        // A native action can complete between the phase read and this terminal check.
        if (player && player.GetCommand_Ladder())
        {
            Drain(player, walker);
            detail = "draining";
            return HCDriverResult.RUNNING;
        }
        walker.Release(player);
        string building = "none";
        if (m_Building) { building = m_Building.GetType(); }
        detail = "climb building=" + building + " ladder=" + m_Ladder.ToString() + " top_y=" + m_TopY.ToString() + " held_s=" + m_Held.ToString() + " result=" + HCDriverResult.Name(code) + " detail=" + reason;
        Print("[HC Driver] " + detail);
        m_Logged = true;
        detail = reason;
        return code;
    }

#ifndef SERVER
    protected bool MatchesLadder(string selection)
    {
        if (selection.Length() > 64) { return false; }
        return selection.Length() >= 6 && selection.Substring(0, 6) == "ladder" && selection.IndexOfFrom(6, "_") < 0 && HumanCommandLadder.DebugGetLadderIndex(selection) == m_Ladder;
    }

    // Exactly one ray per frame. Never invent a component or bypass action.Can.
    protected bool TryEnter(PlayerBase player, ActionManagerClient manager, vector endpoint)
    {
        ActionBase action = ActionManagerBase.GetAction(ActionEnterLadder);
        if (!action) { return false; }
        int column = m_Ray % 5;
        int row = (m_Ray / 5) % 8;
        m_Ray++;
        vector aim = endpoint + Vector((column - 2) * 0.25, 0.25 + row * 0.3, 0);
        vector begin = MiscGameplayFunctions.GetPlayerHeadPosition(player);
        vector end = begin + (aim - begin) * 1.5;
        vector contact;
        vector normal;
        int component;
        m_Hits.Clear();
        if (!DayZPhysics.RaycastRV(begin, end, contact, normal, component, m_Hits, null, player, true)) { return false; }
        if (m_Hits.Count() == 0 || m_Hits.Get(0) != m_Building) { return false; }
        m_Selections.Clear();
        m_Building.GetActionComponentNameList(component, m_Selections);
        bool matches = false;
        for (int i = 0; i < m_Selections.Count() && i < 32; i++)
        {
            string selection = m_Selections[i];
            if (MatchesLadder(selection)) { matches = true; }
        }
        if (!matches) { return false; }
        ActionTarget target = new ActionTarget(m_Building, null, component, contact, 1.0);
        if (!action.Can(player, target, null)) { return false; }
        manager.PerformActionStart(action, target, null);
        m_Entered = true;
        m_Wait = 0;
        return true;
    }

    protected void TryExit(PlayerBase player, ActionManagerClient manager)
    {
        ActionBase exit = ActionManagerBase.GetAction(ActionExitLadder);
        if (!m_None) { m_None = new ActionTarget(null, null, -1, vector.Zero, -1.0); }
        if (exit && !manager.GetRunningAction() && exit.Can(player, m_None, null)) { manager.PerformActionStart(exit, m_None, null); }
    }

#endif

    int Run(HCDriverStep step, PlayerBase player, float dt, HCDriverWalker walker, bool begin, out string detail)
    {
        if (begin) { Begin(); }
        return Tick(step, player, dt, walker, detail);
    }

    int Tick(HCDriverStep step, PlayerBase player, float dt, HCDriverWalker walker, out string detail)
    {
#ifdef SERVER
        return Finish(player, walker, HCDriverResult.UNSUPPORTED, "client-only", detail);
#else
        m_Age = Elapsed();
        m_Wait += dt;
        HumanCommandLadder ladder = player.GetCommand_Ladder();
        ActionManagerClient manager = ActionManagerClient.Cast(player.GetActionManager());
        if (m_Age >= step.timeout_s) { m_Timeout = true; }
        if (ladder && (!manager || !player.GetInputController() || player.IsUnconscious())) { m_Timeout = true; }
        if (m_Timeout)
        {
            walker.Release(player);
            ApplyClimbInput(player, 0, 0);
            // The driver watchdog caps this drain at timeout + 30, then gates recovery
            // on MovementReady for at most another 60 seconds, including forced ends.
            if (ladder)
            {
                if (manager && player.IsAlive() && !player.IsUnconscious()) { TryExit(player, manager); }
                return HCDriverResult.RUNNING;
            }
            // An already submitted entry can arrive after the deadline.
            if (m_Entered && m_Wait < 6) { return HCDriverResult.RUNNING; }
            return Finish(player, walker, HCDriverResult.REFUSED, "timeout-drained", detail);
        }
        if (!manager || !player.GetInputController()) { return Finish(player, walker, HCDriverResult.UNSUPPORTED, "no-client-entry", detail); }
        if (m_Phase == 0)
        {
            if (ladder) { m_Timeout = true; return HCDriverResult.RUNNING; }
            if (!ActionManagerBase.GetAction(ActionEnterLadder) || !ActionManagerBase.GetAction(ActionExitLadder)) { return Finish(player, walker, HCDriverResult.UNSUPPORTED, "native-ladder-action-unavailable", detail); }
            GetGame().GetObjectsAtPosition3D(player.GetPosition(), Math.Clamp(step.range_m, 5, 150), m_Near, m_Cargo);
            m_Phase = 1;
        }
        if (m_Phase == 1)
        {
            m_Budget.HCReset(64);
            while (m_Scan < m_Near.Count() && m_Budget.HCContinue())
            {
                Building candidate = Building.Cast(m_Near[m_Scan]);
                m_Scan++;
                if (!candidate || candidate.GetLaddersCount() <= 0) { continue; }
                float distance = vector.DistanceSq(player.GetPosition(), candidate.GetPosition());
                if (distance <= step.range_m * step.range_m && distance < m_Best) { m_Building = candidate; m_Best = distance; }
            }
            if (m_Scan < m_Near.Count()) { return HCDriverResult.RUNNING; }
            m_Near.Clear();
            m_Cargo.Clear();
            if (!m_Building) { return Finish(player, walker, HCDriverResult.REFUSED, "no-ladder-building", detail); }
            m_Ladder = 0;
            vector rawBottom = m_Building.GetLadderPosBottom(m_Ladder);
            vector rawTop = m_Building.GetLadderPosTop(m_Ladder);
            vector modelBottom = m_Building.ModelToWorld(rawBottom);
            vector modelTop = m_Building.ModelToWorld(rawTop);
            m_Bottom = rawBottom;
            m_Top = rawTop;
            string space = "world";
            if (vector.Distance(rawBottom, m_Building.GetPosition()) > 50)
            {
                m_Bottom = modelBottom;
                m_Top = modelTop;
                space = "model";
            }
            Print("[HC Driver] climb coordinates raw_bottom=" + rawBottom.ToString() + " model_bottom=" + modelBottom.ToString() + " raw_top=" + rawTop.ToString() + " model_top=" + modelTop.ToString() + " space=" + space);
            if (vector.Distance(m_Bottom, m_Building.GetPosition()) > 50 || m_Top[1] < m_Bottom[1] + 2) { return Finish(player, walker, HCDriverResult.REFUSED, "ladder-coordinates", detail); }
            walker.Begin(m_Bottom[0], m_Bottom[2], "walk", 1.0, step.timeout_s);
            m_Phase = 2;
        }
        if (m_Phase == 2 || m_Phase == 6)
        {
            int walked = walker.Update(player, dt);
            if (walked == HCDriverResult.RUNNING) { return walked; }
            if (walked != HCDriverResult.OK) { return Finish(player, walker, HCDriverResult.REFUSED, "approach-failed", detail); }
            m_Phase++;
            m_Ray = 0;
            m_Wait = 0;
            m_Entered = false;
        }
        if (m_Phase == 3 || m_Phase == 7)
        {
            if (ladder) { m_Phase++; m_Wait = 0; return HCDriverResult.RUNNING; }
            if (!m_Entered)
            {
                vector endpoint = m_Bottom;
                if (m_Phase == 7) { endpoint = m_Top; }
                TryEnter(player, manager, endpoint);
            }
            if ((!m_Entered && m_Ray >= 40) || (m_Entered && m_Wait > 6)) { return Finish(player, walker, HCDriverResult.REFUSED, "enter-not-allowed-or-not-started", detail); }
            return HCDriverResult.RUNNING;
        }
        if (m_Phase == 4 || m_Phase == 8)
        {
            if (ladder)
            {
                float angle = 0;
                if (m_Phase == 8) { angle = 180; }
                ApplyClimbInput(player, 1, angle);
                float exitY = m_Top[1];
                if (m_Phase == 8) { exitY = m_Bottom[1]; }
                if (Math.AbsFloat(player.GetPosition()[1] - exitY) < 1.5) { TryExit(player, manager); }
                return HCDriverResult.RUNNING;
            }
            ApplyClimbInput(player, 0, 0);
            m_Entered = false;
            if (m_Phase == 8)
            {
                if (Math.AbsFloat(player.GetPosition()[1] - m_Bottom[1]) > 2) { return Finish(player, walker, HCDriverResult.REFUSED, "wrong-bottom-exit", detail); }
                return Finish(player, walker, HCDriverResult.OK, "returned", detail);
            }
            if (Math.AbsFloat(player.GetPosition()[1] - m_Top[1]) > 2) { return Finish(player, walker, HCDriverResult.REFUSED, "wrong-top-exit", detail); }
            m_TopY = player.GetPosition()[1];
            m_Phase = 5;
            return HCDriverResult.RUNNING;
        }
        if (m_Phase == 5)
        {
            ApplyClimbInput(player, 0, 0);
            if (Math.AbsFloat(player.GetPosition()[1] - m_Top[1]) > 2) { return Finish(player, walker, HCDriverResult.REFUSED, "left-haven", detail); }
            m_Held += dt;
            if (m_Held < step.hold_s) { return HCDriverResult.RUNNING; }
            walker.Begin(m_Top[0], m_Top[2], "walk", 1.0, step.timeout_s);
            m_Phase = 6;
        }
        return HCDriverResult.RUNNING;
#endif
    }
}

modded class HCClientDriver
{
    protected bool m_ClimbDrainLogged;

    override void Tick(float timeslice)
    {
        // Run before super's alive/hold/calibration gates: none may suspend this watchdog.
        if (m_Live && !m_Finished && m_StepOpen && m_Stage > 0 && m_Script.steps[m_Index].kind == "climb")
        {
            HCDriverStep step = m_Script.steps[m_Index];
            float elapsed = m_Climb.Elapsed();
            if (elapsed >= step.timeout_s + 30)
            {
                PlayerBase player = PlayerBase.Cast(GetGame().GetPlayer());
                m_Walker.Release(player);
                HCDriverMovement.Stop();
                if (!m_ClimbDrainLogged)
                {
                    // Native 3_Game/human.c:1473 GetCurrentCommandID (native command enum only).
                    int command = -1;
                    if (player) { command = player.GetCurrentCommandID(); }
                    string label = step.id;
                    if (label == "") { label = "s" + (m_Index + 1).ToString(); }
                    Print("[HC Driver] step=" + label + " kind=climb result=fail detail=reason=climb-drain-timeout command=" + command.ToString());
                    m_ClimbDrainLogged = true;
                    m_Refused++;
                }
                if (player) { m_Climb.Drain(player, m_Walker); }
                if (player && MovementReady(player) && !player.GetCommand_Ladder())
                {
                    // Already reported exactly once; close the step without a second result line.
                    m_Actions.Abort(player, m_Walker);
                    HCDriverMovement.FinishedSerial = HCDriverMovement.Serial;
                    HCDriverMovement.ClosedReason = "";
                    m_Index++;
                    m_Hold.Reset();
                    m_StepOpen = false;
                    m_StepCalibRetried = false;
                    m_ClimbDrainLogged = false;
                    if (m_Index >= m_Script.steps.Count()) { Conclude(); }
                    return;
                }
                if (elapsed >= step.timeout_s + 90)
                {
                    Print("[HC Driver] done run=" + m_Script.run_id + " reason=climb-stuck");
                    // soak_campaign.DRIVER_DONE requires the legacy count summary to
                    // arm its 120 s tail; the reason diagnostic alone is not matched.
                    Conclude();
                }
                return;
            }
        }
        super.Tick(timeslice);
    }

    override protected void EndStep(HCDriverStep step, int code, string detail, PlayerBase player)
    {
        if (step.kind == "climb")
        {
            // Even forced ends (death/hold/lease failure) must wait for native detach.
            // Native human.c:1512 GetCommand_Ladder; no command cancellation is invented.
            if (player && player.GetCommand_Ladder()) { m_Climb.Drain(player, m_Walker); return; }
            m_Climb.ReportExternalEnd(player, m_Walker, code, detail);
        }
        super.EndStep(step, code, detail, player);
    }
}
