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
//  group     HCGroupClient (Get, GetSnapshot, IsBusy, GetNotice, Send) with HCGroupRequest
//            Op CREATE / TEAM_PING exactly as the vanilla group UI and HCTeamPingInput send them.
// Per frame: one step update; no allocation beyond the current step; no counter, HCUse or server
// feature entry is touched; the player's name, id and paths are never printed.
class HCClientDriver
{
    protected ref HCDriverScript m_Script;
    protected ref HCDriverWalker m_Walker = new HCDriverWalker;
    protected ref HCDriverActions m_Actions = new HCDriverActions;
    protected bool m_Live;
    protected bool m_Finished;
    protected int m_Index;
    protected bool m_StepOpen;
    protected float m_StepAge;
    protected int m_Stage;
    protected int m_Mark;
    protected string m_Text;
    protected int m_Ok;
    protected int m_Refused;
    protected int m_Unsupported;
    protected int m_Timeout;

    void Init()
    {
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
        if (!m_Live || m_Finished) { return; }
        PlayerBase player = PlayerBase.Cast(GetGame().GetPlayer());
        m_Actions.Abort(player, m_Walker);
        Conclude();
    }

    protected void Conclude()
    {
        m_Finished = true;
        HCDriverLog.Done(m_Script.run_id, m_Script.steps.Count(), m_Ok, m_Refused, m_Unsupported, m_Timeout);
    }

    protected void EndStep(HCDriverStep step, int code, string detail, PlayerBase player)
    {
        m_Actions.Abort(player, m_Walker);
        string stepId = step.id;
        if (stepId == "") { stepId = "s" + (m_Index + 1).ToString(); }
        HCDriverLog.Step(stepId, step.kind, code, detail);
        if (code == HCDriverResult.OK) { m_Ok++; }
        if (code == HCDriverResult.REFUSED) { m_Refused++; }
        if (code == HCDriverResult.UNSUPPORTED) { m_Unsupported++; }
        if (code == HCDriverResult.TIMEOUT) { m_Timeout++; }
        m_Index++;
        m_StepOpen = false;
        if (m_Index >= m_Script.steps.Count()) { Conclude(); }
    }

    // One call per client frame from the MissionGameplay hook.
    void Tick(float timeslice)
    {
        if (!m_Live || m_Finished) { return; }
        PlayerBase player = PlayerBase.Cast(GetGame().GetPlayer());
        if (!player || !player.IsPlayerLoaded()) { return; }
        float dt = Math.Clamp(timeslice, 0.001, 0.25);
        HCDriverStep step = m_Script.steps[m_Index];
        if (!step)
        {
            m_Index++;
            if (m_Index >= m_Script.steps.Count()) { Conclude(); }
            return;
        }
        if (!m_StepOpen)
        {
            m_StepOpen = true;
            m_StepAge = 0;
            m_Stage = 0;
            m_Mark = 0;
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
        else
        {
            code = HCDriverResult.UNSUPPORTED;
            detail = "unknown-kind";
        }
        if (code != HCDriverResult.RUNNING) { EndStep(step, code, detail, player); }
    }

    protected int StepSprint(HCDriverStep step, PlayerBase player)
    {
        if (m_StepAge >= step.seconds)
        {
            m_Walker.Release(player);
            return HCDriverResult.OK;
        }
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
            if (!CfgGameplayHandler.GetMapIgnoreMapOwnership() || CfgGameplayHandler.GetUse3DMap())
            {
                m_Text = "map-needs-item-or-3d-map";
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
        m_Text = "unknown-menu";
        return HCDriverResult.REFUSED;
    }

    protected bool MenuIsOpen(string name)
    {
        UIManager ui = GetGame().GetUIManager();
        if (name == "map") { return ui.IsMenuOpen(MENU_MAP); }
        if (name == "inventory") { return ui.IsMenuOpen(MENU_INVENTORY); }
        return GetGame().GetMission().IsPaused();
    }

    protected void MenuClose(string name)
    {
        UIManager ui = GetGame().GetUIManager();
        Mission mission = GetGame().GetMission();
        if (name == "map")
        {
            MapMenu mapMenu = MapMenu.Cast(ui.FindMenu(MENU_MAP));
            if (mapMenu) { mapMenu.CloseMapMenu(); }
            if (ui.IsMenuOpen(MENU_MAP)) { ui.CloseMenu(MENU_MAP); }
        }
        if (name == "inventory") { mission.HideInventory(); }
        if (name == "pause") { mission.Continue(); }
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
            if (m_StepAge < 0.5) { return HCDriverResult.RUNNING; }
            if (m_Mark == 0)
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
        if (m_Stage == 0)
        {
            admin.HCListen();
            if (admin.HCSend(step.cmd, amount))
            {
                m_Stage = 1;
                m_StepAge = 0;
                m_Mark = admin.Revision;
                return HCDriverResult.RUNNING;
            }
            if (m_StepAge > 8.0)
            {
                m_Text = "not-sendable:" + admin.Notice;
                return HCDriverResult.REFUSED;
            }
            return HCDriverResult.RUNNING;
        }
        admin.HCTick();
        if (admin.Revision != m_Mark && admin.Notice.IndexOf("Request sent") != 0)
        {
            m_Mark = admin.Revision;
            string notice = admin.Notice;
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
            m_Text = "cmd=" + step.cmd;
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
            if (m_StepAge > 15.0)
            {
                m_Text = "client-not-ready";
                if (step.kind == "ping") { m_Text = "not-in-group-or-ping-disabled"; }
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
