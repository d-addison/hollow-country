// Dev-only test addon (never shipped). Step runner of the scripted client driver: reads
// $profile:HollowCountry/acceptance/client_driver.json (written by tools/testing/driver_script.py),
// runs the steps strictly in order and logs one [HC Driver] line per step plus one done line.
// Native scripts-1.30.164289 proofs:
//  hook      5_Mission/mission/missionGameplay.c:102 OnInit, :287 OnUpdate, OnMissionFinish; every
//            override calls super first; other HC mods hook the same three methods the same way.
//  menus     3_Game/DayZGame.c:1395 and 3_Game/Global/Game.c:943 GetUIManager; UIManager IsMenuOpen,
//            FindMenu, CloseAll, EnterScriptedMenu; missionGameplay.c:1459 HandleMapToggleByKeyboardShortcut
//            (CloseAll, EnterScriptedMenu(MENU_MAP), AddActiveInputExcludes({"map"}),
//            AddActiveInputRestriction(EInputRestrictors.MAP)); 5_Mission/GUI/MapMenu.c:332
//            CloseMapMenu; missionGameplay.c:1190 ShowInventory, :1211 HideInventory, :1294 IsPaused,
//            :1299 Pause, :1334 Continue; 3_Game/constants.c:184-197 MENU_INGAME, MENU_INVENTORY,
//            MENU_MAP; 3_Game/CfgGameplayHandler.c:417 GetUse3DMap, :438 GetMapIgnoreMapOwnership.
//  admin     HCAdminClient (HCGet, HCListen, HCSend with its 1.1 s spacing, HCTick, Notice, Revision).
//  group     HCGroupClient (Get, GetSnapshot, IsBusy, GetNotice, Send) with HCGroupRequest; the M map
//            HCGroupProtocol.MENU_MAP opened as HCGroupGameplay.c OnUpdate does on UAMapToggle
//            Op CREATE / TEAM_PING exactly as the vanilla group UI and HCTeamPingInput send them.
// Per frame: one step update; bounded calibration sample strings; no counter, HCUse or server
// feature entry is touched; the player's name, id and paths are never printed.
class HCClientDriver
{
    protected ref HCDriverScript m_Script;
    protected ref HCDriverWalker m_Walker = new HCDriverWalker;
    protected ref HCDriverActions m_Actions = new HCDriverActions;
    protected ref HCDriverEnter m_Enter = new HCDriverEnter;
    protected ref HCDriverRoute m_Route = new HCDriverRoute;
    protected ref HCDriverCombat m_Combat = new HCDriverCombat;
    protected ref HCDriverLoot m_Loot = new HCDriverLoot;
    protected ref HCDriverSurvive m_Survive = new HCDriverSurvive;
    protected ref HCDriverVehicle m_Vehicle = new HCDriverVehicle;
    protected vector m_Start;
    protected bool m_CalibDone;
    protected int m_CalibStage;
    protected float m_CalibAge;
    protected vector m_CalibForward;
    protected vector m_CalibRight;
    protected vector m_ProbeStart;
    protected vector m_ProbeEnd;
    protected int m_ProbeSamples;
    protected int m_ProbeAngleMatches;
    protected bool m_CalibAnglesMatch;
    protected string m_ProbePositions;
    protected string m_ProbeSpeeds;
    protected string m_ProbeAngles;
    protected string m_ProbeInputs;
    protected string m_ProbeDirections;
    protected string m_ProbeTimes;
    protected float m_ProbeAngle;
    protected float m_RightCamera;
    protected float m_CalibTurn;
    protected float m_ForwardSettle;
    protected float m_RightSettle;
    protected float m_ProbeBack;
    protected float m_ProbeSettle;
    protected float m_CalibYaw;
    protected float m_CalibCamera;
    protected float m_CalibMidYaw;
    protected int m_CalibCommand;
    protected int m_CalibApplied;
    protected int m_CalibForwardFrames;
    protected int m_CalibRightFrames;
    protected PlayerBase m_ReadyPlayer;
    protected int m_CalibRuns;
    protected int m_CalibAttempts;
    protected float m_ReadyAge;
    protected float m_CalibWait;
    protected float m_CalibRetryWait;
    protected bool m_CalibOnDemand;
    protected bool m_StepCalibRetried;
    protected bool m_Live;
    protected bool m_Finished;
    protected int m_Index;
    protected bool m_StepOpen;
    protected float m_StepAge;
    protected int m_Stage;
    protected int m_Mark;
    protected bool m_AdminRefreshed;
    protected string m_Text;
    protected int m_Ok;
    protected int m_Refused;
    protected int m_Unsupported;
    protected int m_Timeout;

    void Init()
    {
        HCDriverMovement.Stop();
        HCDriverMovement.Calibrated = false;
        HCDriverScript script;
        string reason = HCDriverFile.Load(script);
        if (reason != "")
        {
            m_Finished = true;
            HCDriverLog.Inert(reason);
            return;
        }
        m_Script = script;
        m_Live = true;
    }

    void Shutdown()
    {
        HCDriverMovement.Stop();
        if (!m_Live || m_Finished) { return; }
        PlayerBase player = PlayerBase.Cast(GetGame().GetPlayer());
        m_Walker.Release(player);
        m_Actions.Abort(player, m_Walker);
        m_Combat.Release(player);
        m_Vehicle.Release();
        Conclude();
    }

    protected void Conclude()
    {
        HCDriverMovement.Stop();
        m_Finished = true;
        HCDriverLog.Done(m_Script.run_id, m_Script.steps.Count(), m_Ok, m_Refused, m_Unsupported, m_Timeout);
    }

    protected void EndStep(HCDriverStep step, int code, string detail, PlayerBase player)
    {
        m_Walker.Release(player);
        m_Actions.Abort(player, m_Walker);
        m_Combat.Release(player);
        m_Vehicle.Release();
        string stepId = step.id;
        if (stepId == "") { stepId = "s" + (m_Index + 1).ToString(); }
        if (step.kind == "walk" || step.kind == "route" || step.kind == "sprint")
        {
            vector end = player.GetPosition();
            string travel = "start=<" + HCDriverWalker.XZ(m_Start) + "> end=<" + HCDriverWalker.XZ(end) + "> moved_m=" + Math.Round(HCDriverWalker.FlatLength(end - m_Start)).ToString();
            int controls = 0;
            Mission mission = GetGame().GetMission();
            if (mission && mission.IsControlDisabled()) { controls = 1; }
            detail = travel + " cmd=" + HCDriverMovement.CommandId.ToString() + " controls=" + controls.ToString() + " " + detail;
        }
        HCDriverLog.Step(stepId, step.kind, code, detail);
        if (code == HCDriverResult.OK) { m_Ok++; }
        if (code == HCDriverResult.REFUSED) { m_Refused++; }
        if (code == HCDriverResult.UNSUPPORTED) { m_Unsupported++; }
        if (code == HCDriverResult.TIMEOUT) { m_Timeout++; }
        m_Index++;
        m_StepOpen = false;
        m_StepCalibRetried = false;
        if (m_Index >= m_Script.steps.Count()) { Conclude(); }
    }

    // One call per client frame from the MissionGameplay hook.
    void Tick(float timeslice)
    {
        if (!m_Live || m_Finished) { HCDriverMovement.Stop(); return; }
        PlayerBase player = PlayerBase.Cast(GetGame().GetPlayer());
        if (!player || !player.IsPlayerLoaded())
        {
            HCDriverMovement.Stop();
            HCDriverMovement.Calibrated = false;
            m_ReadyAge = 0;
            m_ReadyPlayer = null;
            return;
        }
        if (m_ReadyPlayer != player)
        {
            HCDriverMovement.Stop();
            HCDriverMovement.Calibrated = false;
            m_ReadyAge = 0;
            m_ReadyPlayer = player;
        }
        float dt = Math.Clamp(timeslice, 0.001, 0.25);
        if (MovementReady(player)) { m_ReadyAge = m_ReadyAge + dt; }
        else { m_ReadyAge = 0; HCDriverMovement.Stop(); }
        if (!m_CalibDone)
        {
            Calibrate(player, dt);
            return;
        }
        HCDriverStep step = m_Script.steps[m_Index];
        if (!step)
        {
            m_Index++;
            if (m_Index >= m_Script.steps.Count()) { Conclude(); }
            return;
        }
        if (!m_StepOpen && !HCDriverMovement.Calibrated && !m_StepCalibRetried && (step.kind == "walk" || step.kind == "route" || step.kind == "sprint"))
        {
            m_StepCalibRetried = true;
            if (m_CalibRuns < 4)
            {
                m_CalibOnDemand = true;
                m_CalibDone = false;
                m_CalibRetryWait = 0;
                return;
            }
        }
        if (!m_StepOpen)
        {
            m_Start = player.GetPosition();
            m_StepOpen = true;
            m_StepAge = 0;
            m_Stage = 0;
            m_Mark = 0;
            m_AdminRefreshed = false;
            m_Text = "";
        }
        m_StepAge = m_StepAge + dt;
        int code = HCDriverResult.RUNNING;
        string detail = "";
        if (step.kind == "wait" || step.kind == "stand")
        {
            if (m_StepAge >= step.seconds)
            {
                code = HCDriverResult.OK;
                detail = "held-" + Math.Round(step.seconds).ToString() + "s";
            }
        }
        else if (step.kind == "sprint")
        {
            code = StepSprint(step, player);
            detail = "sprinted-" + Math.Round(step.seconds).ToString() + "s";
            if (code == HCDriverResult.REFUSED) { detail = "sprint-no-movement-or-command"; }
        }
        else if (step.kind == "walk")
        {
            code = StepWalk(step, player, dt);
            detail = m_Walker.Detail();
        }
        else if (step.kind == "menu")
        {
            code = StepMenu(step);
            detail = m_Text;
        }
        else if (step.kind == "admin")
        {
            code = StepAdmin(step);
            detail = m_Text;
        }
        else if (step.kind == "group" || step.kind == "ping")
        {
            code = StepGroup(step, player);
            detail = m_Text;
        }
        else if (step.kind == "action")
        {
            code = StepAction(step, player, dt);
            detail = m_Actions.Detail();
        }
        else if (step.kind == "enter")
        {
            code = StepEnter(step, player, dt);
            detail = m_Text;
            if (detail == "") { detail = m_Enter.Detail(); }
        }
        else if (step.kind == "route")
        {
            code = StepRoute(step, player, dt);
            detail = m_Text;
            if (detail == "") { detail = m_Route.Detail(); }
        }
        else if (step.kind == "combat")
        {
            code = StepCombat(step, player, dt);
            detail = m_Combat.Detail();
        }
        else if (step.kind == "loot")
        {
            code = StepLoot(step, player, dt);
            detail = m_Loot.Detail();
        }
        else if (step.kind == "survive")
        {
            code = StepSurvive(step, player, dt);
            detail = m_Survive.Detail();
        }
        else if (step.kind == "vehicle")
        {
            code = StepVehicle(step, player, dt);
            detail = m_Vehicle.Detail();
        }
        else
        {
            code = HCDriverResult.UNSUPPORTED;
            detail = "unknown-kind";
        }
        if (code != HCDriverResult.RUNNING) { EndStep(step, code, detail, player); }
    }

    protected bool MovementReady(PlayerBase player)
    {
        Mission mission = GetGame().GetMission();
        return player.IsAlive() && !player.IsUnconscious() && player.GetCommand_Move() && player.GetInputController() && mission && !mission.IsControlDisabled();
    }

    protected void BeginCalibProbe(PlayerBase player)
    {
        HCDriverMovement.Stop();
        m_CalibStage = 1;
        m_CalibAge = 0;
        m_CalibYaw = player.GetOrientation()[0];
        m_CalibMidYaw = m_CalibYaw;
        m_CalibCamera = HCDriverWalker.CameraYaw();
        m_CalibCommand = HCDriverMovement.CommandId;
        m_CalibApplied = HCDriverMovement.AppliedFrames;
        m_CalibRightFrames = 0;
        m_CalibAttempts++;
        m_CalibRight = vector.Zero;
        m_ForwardSettle = 0;
        m_RightSettle = 0;
        m_CalibAnglesMatch = true;
        m_CalibTurn = 0;
        HCDriverMovement.Calibrated = false;
        HCDriverMovement.HeadingOffset = 0;
        HCDriverMovement.AngleSign = 1.0;
        ResetProbe(player, 0);
    }

    // Native 1_Core/proto/EnConvert.c:30,59,115: float.ToString has no precision argument; format cents explicitly.
    protected string CalibNumber(float value)
    {
        int cents = Math.Round(Math.AbsFloat(value) * 100.0);
        int whole = cents / 100;
        int fraction = cents - whole * 100;
        string sign = "";
        if (value < 0 && cents > 0) { sign = "-"; }
        return sign + whole.ToString() + "." + fraction.ToStringLen(2);
    }

    protected string CalibXZ(vector value)
    {
        return CalibNumber(value[0]) + "," + CalibNumber(value[2]);
    }

    protected void ResetProbe(PlayerBase player, float angle)
    {
        m_ProbeStart = player.GetPosition();
        m_ProbeAngle = angle;
        m_ProbeSamples = 0;
        m_ProbeAngleMatches = 0;
        m_ProbePositions = "";
        m_ProbeSpeeds = "";
        m_ProbeAngles = "";
        m_ProbeInputs = "";
        m_ProbeDirections = "";
        m_ProbeTimes = "";
        m_ProbeSettle = 0;
        m_ProbeBack = 0;
    }

    protected void SampleProbe(PlayerBase player)
    {
        // Five actual observations at 0.5,1,1.5,2,2.5 s, never repeat a stale sample after a hitch.
        if (m_ProbeSamples >= 5 || m_CalibAge < (m_ProbeSamples + 1) * 0.5) { return; }
        HumanCommandMove move = player.GetCommand_Move();
        if (!move) { return; }
        // Native 3_Game/human.c:459-470: filtered angle, raw input (false=idle), speed 0..3.
        float currentAngle = move.GetCurrentMovementAngle();
        float currentSpeed = move.GetCurrentMovementSpeed();
        float inputAngle;
        string rawInput = "idle";
        if (move.GetCurrentInputAngle(inputAngle)) { rawInput = CalibNumber(inputAngle); }
        // The human.c comment says degrees, but soak 191 read 1.57 for every sample of a 90-degree
        // strafe (input_angle=90), so this build returns radians. Accept either unit; the motion
        // check below still compares the measured displacement bearings, so a wrong match here
        // cannot calibrate on its own.
        float degAngle = currentAngle * Math.RAD2DEG;
        bool degMatch = Math.AbsFloat(HCDriverWalker.Wrap180(currentAngle - m_ProbeAngle)) <= 15.0;
        bool radMatch = Math.AbsFloat(HCDriverWalker.Wrap180(degAngle - m_ProbeAngle)) <= 15.0;
        if (degMatch || radMatch) { m_ProbeAngleMatches++; }
        string separator = "";
        if (m_ProbeSamples > 0) { separator = ";"; }
        m_ProbeTimes += separator + CalibNumber(m_CalibAge);
        m_ProbePositions += separator + CalibXZ(player.GetPosition());
        m_ProbeSpeeds += separator + CalibNumber(currentSpeed);
        m_ProbeAngles += separator + CalibNumber(currentAngle);
        m_ProbeInputs += separator + rawInput;
        // Native 3_Game/Entities/Object.c:314: GetDirection is the player's body direction.
        m_ProbeDirections += separator + CalibXZ(player.GetDirection());
        m_ProbeSamples++;
    }

    protected void LogProbe(PlayerBase player, string probe)
    {
        string line = "[HC Driver] calib probe=" + probe + " variant=" + HCDriverMovement.VariantName();
        line += " serial=" + HCDriverMovement.Serial.ToString();
        line += " req_speed=3.00 req_angle=" + CalibNumber(m_ProbeAngle) + " pos=<" + m_ProbePositions + ">";
        line += " cur_speed=<" + m_ProbeSpeeds + "> cur_angle=<" + m_ProbeAngles + ">";
        line += " input_angle=<" + m_ProbeInputs + "> dir=<" + m_ProbeDirections + ">";
        line += " sample_s=<" + m_ProbeTimes + "> start=<" + CalibXZ(m_ProbeStart) + ">";
        line += " stop=<" + CalibXZ(m_ProbeEnd) + "> settled=<" + CalibXZ(player.GetPosition()) + ">";
        line += " moved_m=" + CalibNumber(HCDriverWalker.FlatLength(m_ProbeEnd - m_ProbeStart));
        line += " settle_m=" + CalibNumber(m_ProbeSettle) + " back_m=" + CalibNumber(m_ProbeBack);
        line += " attempt=" + m_CalibAttempts.ToString() + " duration_s=4.00 settle_s=2.00";
        Print(line + " samples=" + m_ProbeSamples.ToString());
    }

    protected void FinishCalib(PlayerBase player, vector right, string reason)
    {
        m_Walker.Release(player);
        string result = "refused";
        string applied = "refused";
        if (HCDriverMovement.Calibrated) { result = "ok"; applied = "measured-camera-frame"; }
        string calibration = "[HC Driver] calib result=" + result + " variant=" + HCDriverMovement.VariantName() + " run=" + m_CalibRuns.ToString() + " reason=" + reason;
        calibration = calibration + " forward=<" + CalibXZ(m_CalibForward) + "> right=<" + CalibXZ(right) + ">";
        calibration += " threshold_m=0.30 right_moved_m=" + CalibNumber(HCDriverWalker.FlatLength(right));
        calibration += " forward_settle_m=" + CalibNumber(m_ForwardSettle) + " right_settle_m=" + CalibNumber(m_RightSettle);
        calibration += " correction_threshold_m=0.20 back_m=" + CalibNumber(m_ProbeBack);
        calibration = calibration + " facing=" + Math.Round(m_CalibCamera).ToString() + " yaw=" + Math.Round(m_CalibYaw).ToString() + "," + Math.Round(m_CalibMidYaw).ToString() + "," + Math.Round(player.GetOrientation()[0]).ToString();
        calibration = calibration + " cmd=" + m_CalibCommand.ToString() + "," + HCDriverMovement.CommandId.ToString() + " applied_frames=" + m_CalibForwardFrames.ToString() + "," + m_CalibRightFrames.ToString();
        calibration = calibration + " angle_sign=" + HCDriverMovement.AngleSign.ToString() + " frame_offset=" + CalibNumber(HCDriverMovement.HeadingOffset) + " right_offset=" + CalibNumber(HCDriverWalker.Wrap180(m_CalibTurn - 90.0 * HCDriverMovement.AngleSign)) + " apply=" + applied + " aim=disabled";
        int controls = 0;
        Mission mission = GetGame().GetMission();
        if (mission && mission.IsControlDisabled()) { controls = 1; }
        Print(calibration + " controls=" + controls.ToString());
        m_CalibStage = 0;
        m_CalibWait = 0;
        m_CalibDone = true;
        if (!HCDriverMovement.Calibrated && !m_CalibOnDemand && m_CalibRuns < 3)
        {
            m_CalibDone = false;
            m_CalibRetryWait = 15.0;
        }
    }

    // Up to three startup runs; step retries share the four-run session cap. No per-frame logs.
    protected void Calibrate(PlayerBase player, float dt)
    {
        if (m_CalibRetryWait > 0)
        {
            m_CalibRetryWait = m_CalibRetryWait - dt;
            return;
        }
        if (m_CalibStage == 0)
        {
            m_CalibWait = m_CalibWait + dt;
            m_CalibForward = vector.Zero;
            m_CalibForwardFrames = 0;
            m_CalibRightFrames = 0;
            m_CalibRight = vector.Zero;
            m_ForwardSettle = 0;
            m_RightSettle = 0;
            m_ProbeBack = 0;
            HCDriverMovement.Calibrated = false;
            HCDriverMovement.HeadingOffset = 0;
            HCDriverMovement.AngleSign = 1.0;
            // Require ten continuous ready seconds, not ten seconds since loading began.
            if (m_ReadyAge < 10.0)
            {
                if (m_CalibWait < 60.0) { return; }
                m_CalibRuns++;
                FinishCalib(player, vector.Zero, "movement-or-controls-not-ready");
                return;
            }
            m_CalibRuns++;
            HCDriverMovement.Variant = HCDriverMovement.MIRROR;
            BeginCalibProbe(player);
        }
        m_CalibAge = m_CalibAge + dt;
        if (!MovementReady(player) || m_ReadyAge < 10.0)
        {
            FinishCalib(player, m_CalibRight, "readiness-lost");
            return;
        }
        // States 1/2 drive forward/right for 4 s; states 3/4 hold stopped for 2 s.
        if (m_CalibStage == 1 || m_CalibStage == 2)
        {
            SampleProbe(player);
            if (m_CalibAge < 4.0)
            {
                // Native Bot_MovementRandomizer.c:38-39 uses ONE_FRAME speed 3, angle 0.
                HCDriverMovement.Request(3.0, m_ProbeAngle);
                return;
            }
            m_ProbeEnd = player.GetPosition();
            int frames = HCDriverMovement.AppliedFrames - m_CalibApplied;
            if (m_ProbeSamples != 5 || m_ProbeAngleMatches < 3) { m_CalibAnglesMatch = false; }
            if (m_CalibStage == 1)
            {
                m_CalibForward = m_ProbeEnd - m_ProbeStart;
                m_CalibForwardFrames = frames;
                float forwardBearing = Math.Atan2(m_CalibForward[0], m_CalibForward[2]) * Math.RAD2DEG;
                // Retain bearing provisionally; only the settled forward test selects this variant.
                HCDriverMovement.HeadingOffset = HCDriverWalker.Wrap180(forwardBearing - m_CalibCamera);
                m_CalibStage = 3;
            }
            else
            {
                m_CalibRight = m_ProbeEnd - m_ProbeStart;
                m_CalibRightFrames = frames;
                float rightBearing = Math.Atan2(m_CalibRight[0], m_CalibRight[2]) * Math.RAD2DEG;
                m_CalibTurn = HCDriverWalker.Wrap180(rightBearing - m_RightCamera - HCDriverMovement.HeadingOffset);
                if (m_CalibTurn < 0) { HCDriverMovement.AngleSign = -1.0; }
                m_CalibStage = 4;
            }
            HCDriverMovement.Stop();
            m_CalibAge = 0;
            return;
        }
        HCDriverMovement.Stop();
        if (m_CalibAge < 2.0) { return; }
        vector drift = player.GetPosition() - m_ProbeEnd;
        vector displacement = m_ProbeEnd - m_ProbeStart;
        float distance = HCDriverWalker.FlatLength(displacement);
        m_ProbeSettle = HCDriverWalker.FlatLength(drift);
        // Positive projection means returning toward this probe's start after Stop.
        m_ProbeBack = 0;
        if (distance > 0.001) { m_ProbeBack = -(drift[0] * displacement[0] + drift[2] * displacement[2]) / distance; }
        string probe = "fwd";
        if (m_CalibStage == 4) { probe = "right"; m_RightSettle = m_ProbeSettle; }
        else { m_ForwardSettle = m_ProbeSettle; }
        LogProbe(player, probe);
        // Correction = pulled back toward this probe's start. Soak 190t6: a mirror probe moved
        // 8.10 m and drifted 0.23 m forward/sideways after Stop (back_m=-0.15); that is not a
        // server snap, which shows back_m close to moved_m.
        bool corrected = m_ProbeBack > 0.2;
        if (m_CalibStage == 4 && corrected)
        {
            FinishCalib(player, m_CalibRight, "server-correction");
            return;
        }
        if (m_CalibStage == 3)
        {
            if (distance <= 0.3 || corrected)
            {
                // Prefer prediction plus authority, then authority only, then client diagnostic.
                if (HCDriverMovement.Variant < HCDriverMovement.CLIENT_ONLY)
                {
                    HCDriverMovement.Variant++;
                    BeginCalibProbe(player);
                    return;
                }
                string failure = "no-moving-variant";
                if (corrected) { failure = "server-correction"; }
                FinishCalib(player, vector.Zero, failure);
                return;
            }
            m_CalibApplied = HCDriverMovement.AppliedFrames;
            m_CalibMidYaw = player.GetOrientation()[0];
            m_RightCamera = HCDriverWalker.CameraYaw();
            m_CalibAge = 0;
            m_CalibStage = 2;
            ResetProbe(player, 90.0);
            return;
        }
        string reason = "frame-probe";
        if (distance <= 0.3) { reason = "right-no-movement"; }
        else if (!m_CalibAnglesMatch) { reason = "command-angle-mismatch"; }
        // A mirrored strafe (turn near -90) is accepted; AngleSign carries it into the walker.
        else if (Math.AbsFloat(Math.AbsFloat(m_CalibTurn) - 90.0) > 15.0) { reason = "command-angle-motion-mismatch"; }
        HCDriverMovement.Calibrated = reason == "frame-probe";
        FinishCalib(player, m_CalibRight, reason);
    }

    protected int StepSprint(HCDriverStep step, PlayerBase player)
    {
        if (m_StepAge >= step.seconds)
        {
            m_Walker.Release(player);
            if (HCDriverWalker.FlatLength(player.GetPosition() - m_Start) < 0.5) { return HCDriverResult.REFUSED; }
            return HCDriverResult.OK;
        }
        if (!HCDriverMovement.Calibrated || !player.GetCommand_Move()) { return HCDriverResult.REFUSED; }
        if (!player.GetInputController()) { return HCDriverResult.UNSUPPORTED; }
        m_Walker.Forward(player, 3.0);
        return HCDriverResult.RUNNING;
    }

    protected int StepWalk(HCDriverStep step, PlayerBase player, float dt)
    {
        if (m_Stage == 0)
        {
            m_Stage = 1;
            if (!step.to || step.to.Count() < 2)
            {
                m_Text = "walk-needs-to";
                return HCDriverResult.REFUSED;
            }
            m_Walker.Begin(step.to[0], step.to[1], step.gait, step.arrive_m, step.timeout_s);
        }
        return m_Walker.Update(player, dt);
    }

    protected int MenuOpenCode(string name)
    {
        UIManager ui = GetGame().GetUIManager();
        Mission mission = GetGame().GetMission();
        if (!ui || !mission) { m_Text = "no-ui-manager"; return HCDriverResult.UNSUPPORTED; }
        if (name == "map")
        {
            // The M key first (HCGroupGameplay.c OnUpdate runs before the vanilla toggle): with the group
            // frame enabled it opens the Hollow Country map without a map item. Same checks as that key.
            if (ui.GetMenu()) { m_Text = "another-menu-open"; return HCDriverResult.REFUSED; }
            if (GroupMapAllowed())
            {
                ui.EnterScriptedMenu(HCGroupProtocol.MENU_MAP, null);
                return HCDriverResult.RUNNING;
            }
            if (!CfgGameplayHandler.GetMapIgnoreMapOwnership() || CfgGameplayHandler.GetUse3DMap())
            {
                m_Text = "map-needs-item-or-3d-map-and-group-map-off";
                return HCDriverResult.UNSUPPORTED;
            }
            ui.CloseAll();
            ui.EnterScriptedMenu(MENU_MAP, null);
            mission.AddActiveInputExcludes({"map"});
            mission.AddActiveInputRestriction(EInputRestrictors.MAP);
            return HCDriverResult.RUNNING;
        }
        if (name == "inventory")
        {
            mission.ShowInventory();
            return HCDriverResult.RUNNING;
        }
        if (name == "pause")
        {
            mission.Pause();
            return HCDriverResult.RUNNING;
        }
        if (name == "admin")
        {
            // The same path the admin key takes (HCAdminGameplay.c OnUpdate): HCOpen sends the status
            // request and HCTick enters the menu once the server answers an admin.
            if (ui.GetMenu()) { m_Text = "another-menu-open"; return HCDriverResult.REFUSED; }
            HCAdminClient.HCGet().HCOpen();
            return HCDriverResult.RUNNING;
        }
        m_Text = "unknown-menu";
        return HCDriverResult.REFUSED;
    }

    // HCGroupGameplay.c OnUpdate opens HCGroupProtocol.MENU_MAP on UAMapToggle when the group frame is
    // enabled, the player is alive and conscious and no menu is open.
    protected bool GroupMapAllowed()
    {
        PlayerBase player = PlayerBase.Cast(GetGame().GetPlayer());
        if (!player || !player.IsAlive() || player.IsUnconscious()) { return false; }
        HCGroupClient client = HCGroupClient.Get();
        if (!client) { return false; }
        // Same Start/Update entry points as HCGroupGameplay, including its initial SYNC.
        client.Start();
        client.Update();
        HCGroupSnapshot frame = client.GetSnapshot();
        return frame && frame.Enabled;
    }

    protected bool MenuIsOpen(string name)
    {
        UIManager ui = GetGame().GetUIManager();
        if (name == "map") { return ui.IsMenuOpen(MENU_MAP) || ui.IsMenuOpen(HCGroupProtocol.MENU_MAP); }
        if (name == "inventory") { return ui.IsMenuOpen(MENU_INVENTORY); }
        if (name == "admin") { return ui.IsMenuOpen(HCAdminWire.MENU); }
        return GetGame().GetMission().IsPaused();
    }

    protected void MenuClose(string name)
    {
        UIManager ui = GetGame().GetUIManager();
        Mission mission = GetGame().GetMission();
        if (name == "map")
        {
            UIScriptedMenu groupMap = ui.FindMenu(HCGroupProtocol.MENU_MAP);
            if (groupMap) { groupMap.Close(); }
            MapMenu mapMenu = MapMenu.Cast(ui.FindMenu(MENU_MAP));
            if (mapMenu) { mapMenu.CloseMapMenu(); }
            if (ui.IsMenuOpen(MENU_MAP)) { ui.CloseMenu(MENU_MAP); }
        }
        if (name == "inventory") { mission.HideInventory(); }
        if (name == "pause") { mission.Continue(); }
        if (name == "admin")
        {
            UIScriptedMenu adminMenu = ui.FindMenu(HCAdminWire.MENU);
            if (adminMenu) { adminMenu.Close(); }
        }
    }

    // Stages: 0 open, 1 verify and hold, 2 close and check it closed.
    protected int StepMenu(HCDriverStep step)
    {
        if (m_Stage == 0)
        {
            m_Stage = 1;
            m_StepAge = 0;
            int opened = MenuOpenCode(step.name);
            if (opened != HCDriverResult.RUNNING) { return opened; }
            return HCDriverResult.RUNNING;
        }
        if (m_Stage == 1)
        {
            // HCAdminGameplay.c ticks the admin client only after a real key press; the driver opened it
            // without one, so it ticks it until the menu is up (soak 185b: s07 menu-never-opened).
            if (step.name == "admin" && m_Mark != 2) { HCAdminClient.HCGet().HCTick(); }
            if (m_StepAge < 0.5) { return HCDriverResult.RUNNING; }
            // Polled until the hold ends: the admin menu opens only after the server's reply.
            if (m_Mark != 2)
            {
                m_Mark = 1;
                if (MenuIsOpen(step.name)) { m_Mark = 2; }
            }
            if (m_StepAge < step.seconds) { return HCDriverResult.RUNNING; }
            MenuClose(step.name);
            m_Stage = 2;
            m_StepAge = 0;
            return HCDriverResult.RUNNING;
        }
        if (m_StepAge < 0.5) { return HCDriverResult.RUNNING; }
        if (m_Mark == 2)
        {
            if (MenuIsOpen(step.name))
            {
                m_Text = "opened-but-did-not-close";
                return HCDriverResult.REFUSED;
            }
            m_Text = "opened-and-closed";
            return HCDriverResult.OK;
        }
        m_Text = "menu-never-opened";
        return HCDriverResult.REFUSED;
    }

    // Canonical non-negative integer text: no sign, no leading zeros, at most nine digits.
    protected bool DigitsOnly(string text)
    {
        if (text == "") { return true; }
        if (text.Length() > 9) { return false; }
        return text.ToInt().ToString() == text && text.ToInt() >= 0;
    }

    // Stages: 0 send (retried while the 1.1 s spacing or the session holds it back),
    // 1 wait for the reply notice, which carries the server reason.
    protected int StepAdmin(HCDriverStep step)
    {
        HCAdminClient admin = HCAdminClient.HCGet();
        int amount = 0;
        if (!DigitsOnly(step.value))
        {
            m_Text = "value-not-a-number";
            return HCDriverResult.REFUSED;
        }
        if (step.value != "") { amount = step.value.ToInt(); }
        admin.HCListen();
        admin.HCTick();
        // HCTick expires a stale authorized session by calling HCStop (removes its listener).
        admin.HCListen();
        if (m_Stage == 0 && step.cmd != "status" && !admin.HCValid())
        {
            if (admin.HCSend("status"))
            {
                m_Stage = 2;
                m_StepAge = 0;
                m_Mark = admin.HCDriverReplySerial();
            }
            else if (m_StepAge > 12.0)
            {
                m_Text = "session-refresh-not-sendable";
                return HCDriverResult.REFUSED;
            }
            return HCDriverResult.RUNNING;
        }
        if (m_Stage == 0 || m_Stage == 3)
        {
            if (admin.HCSend(step.cmd, amount))
            {
                m_Stage = 1;
                m_StepAge = 0;
                m_Mark = admin.HCDriverReplySerial();
                return HCDriverResult.RUNNING;
            }
            if (m_StepAge > 8.0)
            {
                m_Text = "not-sendable:pending-or-send-spacing";
                return HCDriverResult.REFUSED;
            }
            return HCDriverResult.RUNNING;
        }
        admin.HCTick();
        if (admin.Notice.IndexOf("No server reply") >= 0)
        {
            m_Text = "no-server-reply";
            return HCDriverResult.TIMEOUT;
        }
        if (admin.HCDriverReplySerial() != m_Mark)
        {
            m_Mark = admin.HCDriverReplySerial();
            string notice = admin.HCDriverReplyNotice();
            if (notice.IndexOf("No server reply") >= 0)
            {
                m_Text = "no-server-reply";
                return HCDriverResult.TIMEOUT;
            }
            if (notice.IndexOf("result=refused") >= 0)
            {
                int at = notice.IndexOf("reason=");
                m_Text = "refused";
                if (at >= 0) { m_Text = "refused reason=" + notice.Substring(at + 7, notice.Length() - at - 7); }
                return HCDriverResult.REFUSED;
            }
            if (m_Stage == 2)
            {
                if (!admin.HCValid()) { m_Text = "status-session-not-authorized"; return HCDriverResult.REFUSED; }
                m_AdminRefreshed = true;
                m_Stage = 3;
                m_StepAge = 0;
                return HCDriverResult.RUNNING;
            }
            m_Text = "cmd=" + step.cmd;
            if (m_AdminRefreshed) { m_Text = m_Text + " session=refreshed"; }
            if (notice.IndexOf("fixture=1") >= 0) { m_Text = m_Text + " fixture=1"; }
            return HCDriverResult.OK;
        }
        if (m_StepAge > 15.0)
        {
            m_Text = "client-timeout";
            return HCDriverResult.TIMEOUT;
        }
        return HCDriverResult.RUNNING;
    }

    protected int GroupCode(string notice)
    {
        string prefix = "Server result: ";
        if (notice.IndexOf(prefix) != 0) { return -1; }
        return notice.Substring(prefix.Length(), notice.Length() - prefix.Length()).ToInt();
    }

    // group create_solo and ping. Stages: 0 send, 1 wait for the server result code.
    protected int StepGroup(HCDriverStep step, PlayerBase player)
    {
        HCGroupClient client = HCGroupClient.Get();
        if (!client)
        {
            m_Text = "no-group-client";
            return HCDriverResult.UNSUPPORTED;
        }
        // Same Start/Update entry points as HCGroupGameplay, including its initial SYNC.
        client.Start();
        client.Update();
        HCGroupSnapshot frame = client.GetSnapshot();
        if (m_Stage == 0)
        {
            if (step.kind == "group" && step.op != "create_solo")
            {
                m_Text = "unknown-group-op";
                return HCDriverResult.REFUSED;
            }
            if (frame && frame.Enabled && step.kind == "group" && frame.GroupId >= 1)
            {
                m_Text = "already-in-group";
                return HCDriverResult.REFUSED;
            }
            bool ready = frame && frame.Enabled && !client.IsBusy() && player.IsAlive() && !player.IsUnconscious();
            if (ready && step.kind == "ping")
            {
                ready = frame.Settings && frame.Settings.HCTeamPingEnabled && frame.GroupId >= 1;
            }
            if (ready)
            {
                HCGroupRequest request = new HCGroupRequest;
                if (step.kind == "group")
                {
                    request.Op = HCGroupOp.CREATE;
                    request.Name = "Solo Test";
                }
                else
                {
                    request.Op = HCGroupOp.TEAM_PING;
                    request.Role = 0;
                }
                if (client.Send(request))
                {
                    m_Stage = 1;
                    m_StepAge = 0;
                    return HCDriverResult.RUNNING;
                }
            }
            if (m_StepAge > 30.0)
            {
                m_Text = "group-no-snapshot-after-sync";
                if ((frame && !frame.Enabled) || client.HCDriverServiceDisabled()) { m_Text = "group-disabled-by-server"; }
                if (client.IsBusy()) { m_Text = "group-transaction-pending"; }
                if (step.kind == "ping") { m_Text = "not-in-group-or-ping-disabled"; }
                m_Text = m_Text + client.HCDriverReadiness();
                return HCDriverResult.REFUSED;
            }
            return HCDriverResult.RUNNING;
        }
        if (!client.IsBusy() && m_StepAge > 0.2)
        {
            int serverCode = GroupCode(client.GetNotice());
            if (serverCode == 0)
            {
                m_Text = "server-code=0";
                return HCDriverResult.OK;
            }
            if (serverCode > 0)
            {
                m_Text = "server-code=" + serverCode.ToString();
                return HCDriverResult.REFUSED;
            }
        }
        if (m_StepAge > 15.0)
        {
            m_Text = "no-server-result";
            return HCDriverResult.TIMEOUT;
        }
        return HCDriverResult.RUNNING;
    }

    // The server's own radius answer (HCUseLifecycle.c stores RPC_ENTRY); read-only here.
    protected bool RadiusObserved(string zone)
    {
        MissionGameplay mission = MissionGameplay.Cast(GetGame().GetMission());
        if (!mission) { return false; }
        if (zone == "site") { return mission.HCTestRadiusObserved(HCReleaseRadiusWire.AI_SITE); }
        return mission.HCTestRadiusObserved(HCReleaseRadiusWire.MISSION);
    }

    protected int StepEnter(HCDriverStep step, PlayerBase player, float dt)
    {
        if (m_Stage == 0)
        {
            m_Stage = 1;
            if (step.zone != "site" && step.zone != "mission")
            {
                m_Text = "enter-needs-zone";
                return HCDriverResult.REFUSED;
            }
            m_Enter.Begin(step);
        }
        return m_Enter.Tick(player, dt, m_Walker, RadiusObserved(step.zone));
    }

    protected int StepRoute(HCDriverStep step, PlayerBase player, float dt)
    {
        if (m_Stage == 0)
        {
            m_Stage = 1;
            if (!m_Route.Begin(step))
            {
                m_Text = "route-needs-points";
                return HCDriverResult.REFUSED;
            }
        }
        return m_Route.Tick(player, dt, m_Walker, m_Actions);
    }

    protected int StepCombat(HCDriverStep step, PlayerBase player, float dt)
    {
        if (m_Stage == 0)
        {
            m_Stage = 1;
            m_Combat.Begin(step);
        }
        return m_Combat.Tick(player, dt, m_Walker);
    }

    protected int StepLoot(HCDriverStep step, PlayerBase player, float dt)
    {
        if (m_Stage == 0)
        {
            m_Stage = 1;
            m_Loot.Begin(step);
        }
        return m_Loot.Tick(player, dt, m_Walker);
    }

    protected int StepSurvive(HCDriverStep step, PlayerBase player, float dt)
    {
        if (m_Stage == 0)
        {
            m_Stage = 1;
            m_Survive.Begin(step);
        }
        return m_Survive.Tick(player, dt);
    }

    protected int StepVehicle(HCDriverStep step, PlayerBase player, float dt)
    {
        if (m_Stage == 0)
        {
            m_Stage = 1;
            m_Vehicle.Begin(step);
        }
        return m_Vehicle.Tick(player, dt, m_Walker);
    }

    protected int StepAction(HCDriverStep step, PlayerBase player, float dt)
    {
        if (m_Stage == 0)
        {
            m_Stage = 1;
            m_Actions.Begin(step.name, step.args, step.timeout_s);
        }
        return m_Actions.Tick(player, dt, m_Walker);
    }
}

modded class MissionGameplay
{
    protected ref HCClientDriver m_HCDriver;

    override void OnInit()
    {
        super.OnInit();
        if (GetGame().IsServer()) { return; }
        m_HCDriver = new HCClientDriver;
        m_HCDriver.Init();
    }

    override void OnUpdate(float timeslice)
    {
        super.OnUpdate(timeslice);
        if (m_HCDriver) { m_HCDriver.Tick(timeslice); }
    }

    // Test-only read of the flags HCUseLifecycle.c sets from the server's RPC_ENTRY answer.
    bool HCTestRadiusObserved(int observation)
    {
        if (observation == HCReleaseRadiusWire.AI_SITE) { return m_HCReleaseAISiteObserved; }
        if (observation == HCReleaseRadiusWire.MISSION) { return m_HCReleaseMissionObserved; }
        return false;
    }

    override void OnMissionFinish()
    {
        if (m_HCDriver)
        {
            m_HCDriver.Shutdown();
            m_HCDriver = null;
        }
        super.OnMissionFinish();
    }
}

// Test-only access to the earplugs key handler: the driver cannot press a key, and HCEarplugs.Press
// is the real handler (applies the sound volume and bumps its own counter, which this never touches).
modded class HCEarplugs
{
    static bool HCTestPress()
    {
        if (!s_Client) { return false; }
        s_Client.Press();
        return true;
    }
}
