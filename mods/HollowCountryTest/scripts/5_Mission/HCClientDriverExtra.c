// Dev-only driver extensions. Native scripts-1.30.164289 evidence:
// 3_Game/Global/Game.c:930 GetObjectsAtPosition3D, :731-732 camera; Object.c:287
// GetPosition, :873 ModelToWorld; Building.c:31 GetDoorCount; human.c:268 OverrideRaise;
// 4_World/Entities/DayZPlayerImplement.c:4005 IsRaised. Existing walker/actions/combat
// retain their native citations. No feature counters are manufactured by the driver.
modded class HCDriverStep
{
    string site;
    float range_min_m;
    float range_max_m;
}

// Reuse the real take/search actions, restricting their candidates to this step's target.
class HCDriverExtraActions : HCDriverActions
{
    House SearchHouse;
    bool LeadOnly;

    override protected bool MatchesGround(ItemBase candidate, string type)
    {
        // Paper's ledger id/text are server-owned (HCNoteLedger.c:415-424;
        // native Paper.c:3-7,34-37 has no net variable for note contents). The
        // scene phase supplies the lead; select its exact vanilla class, never
        // a writable-note subclass. Only the server HC Use lines prove identity.
        if (LeadOnly) { return candidate.GetType() == "Paper"; }
        return super.MatchesGround(candidate, type);
    }

    override protected bool Accept(string kind, PlayerBase player, Object object)
    {
        if (kind == "search") { return object && object == SearchHouse; }
        return super.Accept(kind, player, object);
    }
}

class HCDriverRaise : HCDriverCombat
{
    protected float m_Held;
    protected float m_NextCheck;
    protected ref HCWorkBudget m_RaiseBudget = new HCWorkBudget;

    void BeginRaise(HCDriverStep step)
    {
        Begin(step);
        m_Held = 0;
        m_NextCheck = 0;
    }

    override void Release(PlayerBase player)
    {
#ifndef SERVER
        super.Release(player);
#endif
    }

    override protected int End(PlayerBase player, HCDriverWalker walker, int code, string prefix)
    {
        Release(player);
        walker.Release(player);
        m_Detail = prefix;
        return code;
    }

    protected bool Neutral(PlayerBase player, eAIBase actor)
    {
        if (!actor || !HCXExpansionBridge.HCBaseIsAlive(actor)) { return false; }
        // HCXStance.Owns also reads the server-only EncountersEnabled preference.
        // On a client inspect the replicated group and HC faction through the bridge;
        // unknown/non-HC groups are never guessed neutral.
        eAIGroup group = HCXExpansionBridge.HCDayZPlayerImplementGetGroup(actor);
        if (!group) { return false; }
        eAIFaction faction = HCXExpansionBridge.HCGroupGetFaction(group);
        if (!HCXFactions.Known(HCXFactions.Id(faction))) { return false; }
        if (HCXStance.Relation(actor, player) < 0) { return false; }
        return group != HCXExpansionBridge.HCDayZPlayerImplementGetGroup(player);
    }

    int TickRaise(HCDriverStep step, PlayerBase player, float dt, HCDriverWalker walker)
    {
#ifdef SERVER
        return HCDriverResult.UNSUPPORTED;
#else
        m_Elapsed += dt;
        if (m_Elapsed >= step.timeout_s) { return End(player, walker, HCDriverResult.TIMEOUT, "reason=raise-timeout fire=none "); }
        HumanInputController input = player.GetInputController();
        if (!input || !Weapon_Base.Cast(player.GetItemInHands())) { return End(player, walker, HCDriverResult.REFUSED, "reason=held-weapon-required fire=none "); }
        if (!m_Target)
        {
            m_NextCheck -= dt;
            if (m_NextCheck > 0) { return HCDriverResult.RUNNING; }
            m_NextCheck = 1;
            m_Near.Clear();
            m_NearCargo.Clear();
            GetGame().GetObjectsAtPosition3D(player.GetPosition(), 150, m_Near, m_NearCargo);
            float best = 1000000;
            m_RaiseBudget.HCReset(256);
            for (int i = 0; i < m_Near.Count() && m_RaiseBudget.HCContinue(); i++)
            {
                eAIBase actor = eAIBase.Cast(m_Near[i]);
                if (!Neutral(player, actor)) { continue; }
                float distance = vector.DistanceSq(player.GetPosition(), HCXExpansionBridge.HCBaseGetPosition(actor));
                if (distance < best) { best = distance; m_Target = actor; }
            }
            if (!m_Target) { return HCDriverResult.RUNNING; }
        }
        if (!Neutral(player, eAIBase.Cast(m_Target)))
        {
            m_Target = null;
            m_Held = 0;
            Release(player);
            walker.Release(player);
            return HCDriverResult.RUNNING;
        }
        vector delta = player.GetPosition() - m_Target.GetPosition();
        float gap = HCDriverWalker.FlatLength(delta);
        if (gap < step.range_min_m || gap > step.range_max_m)
        {
            m_Held = 0;
            Release(player);
            if (!walker.IsActive())
            {
                if (gap < 1) { delta = Vector(1, 0, 0); gap = 1; }
                vector to = m_Target.GetPosition() + delta * ((step.range_min_m + step.range_max_m) * 0.5 / gap);
                walker.Begin(to[0], to[2], "walk", 2, Math.Max(1, step.timeout_s - m_Elapsed));
            }
            int walked = walker.Update(player, dt);
            if (walked != HCDriverResult.OK && walked != HCDriverResult.RUNNING) { return End(player, walker, walked, "reason=raise-approach fire=none "); }
            return HCDriverResult.RUNNING;
        }
        walker.Release(player);
        input.OverrideRaise(HumanInputControllerOverrideType.ENABLED, true);
        bool aimed = Aim(player, input, dt);
        // One LOS test per half second, as in combat; never counts time behind a wall.
        m_LosAge += dt;
        if (m_LosAge >= 0.5)
        {
            m_LosAge = 0;
            m_Counted = InSight(player, m_Target);
        }
        if (aimed && player.IsRaised() && m_Counted) { m_Held += dt; }
        else { m_Held = 0; }
        if (m_Held >= step.seconds) { return End(player, walker, HCDriverResult.OK, "reason=raised-neutral fire=none "); }
        return HCDriverResult.RUNNING;
#endif
    }
}

// Vanilla respawn entry, identical to the respawn dialogue's MenuRequestRespawn.
// Native 5_Mission/GUI/InGameMenu.c:339-365: GameRespawn performs RespawnPlayer,
// death-screen cleanup, DestroyAllMenus, SetPlayerRespawning and Continue.
modded class InGameMenu
{
    void HCDriverRespawn()
    {
#ifndef SERVER
        GameRespawn(true);
#endif
    }
}

class HCDriverExtra
{
    protected static ref HCDriverExtra s_Instance;
    protected ref HCDriverWalker m_Walker = new HCDriverWalker;
    protected float m_StepAge;
    protected int m_Stage;
    protected string m_Text;

    static void Prepare()
    {
        if (!s_Instance) { s_Instance = new HCDriverExtra; }
        s_Instance.LoadSites();
    }

    // Startup-only, outside the tick path. Native JsonFileLoader.c:7 LoadFile.
    protected void LoadSites()
    {
        string error;
        HCXAISitePolicy policy;
        if (!JsonFileLoader<HCXAISitePolicy>.LoadFile(HCXAIDefaults.Shipped() + HCXAIDefaults.SitesFile(), policy, error) || !policy || !policy.Sites) { return; }
        HCWorkBudget budget = new HCWorkBudget;
        budget.HCReset(4096);
        foreach (HCXAISite row : policy.Sites)
        {
            if (!budget.HCContinue()) { break; }
            if (row && row.Waypoints && row.Waypoints.Count() > 0) { m_ExtraAnchors.Set(row.Id, row.Waypoints[0]); }
        }
    }

    static int Run(HCDriverStep step, PlayerBase player, float dt, bool begin, out string detail)
    {
        if (!s_Instance) { s_Instance = new HCDriverExtra; }
        int result = s_Instance.TickExtra(step, player, dt, begin);
        detail = s_Instance.m_Text;
        return result;
    }

    static void Stop(PlayerBase player)
    {
        if (s_Instance) { s_Instance.ExtraEnd(player, HCDriverResult.REFUSED, "shutdown"); }
    }

    protected int TickExtra(HCDriverStep step, PlayerBase player, float dt, bool begin)
    {
#ifdef SERVER
        m_Text = "reason=client-only";
        return HCDriverResult.UNSUPPORTED;
#else
        if (begin) { m_Stage = 0; m_StepAge = 0; m_Text = ""; m_ExtraHold = 0; }
        m_StepAge += dt;
        if (step.kind == "search_site") { return StepSearchSite(step, player, dt); }
        if (step.kind == "take_lead") { return StepTakeLead(step, player, dt); }
        if (step.kind == "raise") { return StepRaise(step, player, dt); }
        if (step.kind == "hold_ring") { return StepHoldRing(step, player, dt); }
        return StepRespawn(step, player, dt);
#endif
    }

    protected ref HCDriverExtraActions m_ExtraActions = new HCDriverExtraActions;
    protected ref HCDriverRaise m_ExtraRaise = new HCDriverRaise;
    protected House m_ExtraHouse;
    protected ref HCDriverRoute m_ExtraRoute = new HCDriverRoute;
    protected ref array<Object> m_ExtraNear = new array<Object>;
    protected ref array<CargoBase> m_ExtraCargo = new array<CargoBase>;
    protected ref map<string, vector> m_ExtraAnchors = new map<string, vector>;
    protected vector m_ExtraAnchor;
    protected vector m_ExtraSearchCenter;
    protected int m_ExtraCursor;
    protected float m_ExtraBest;
    protected float m_ExtraHold;
    protected ref HCWorkBudget m_ExtraBudget = new HCWorkBudget;

    protected int ExtraEnd(PlayerBase player, int code, string reason)
    {
        m_ExtraActions.Abort(player, m_Walker);
        m_ExtraRaise.Release(player);
        m_Walker.Release(player);
        m_Text = "reason=" + reason;
        return code;
    }

    protected int StepHoldRing(HCDriverStep step, PlayerBase player, float dt)
    {
        if (m_StepAge >= step.timeout_s) { return ExtraEnd(player, HCDriverResult.TIMEOUT, "ring-timeout"); }
        if (m_Stage == 0)
        {
            if (!step.to || step.to.Count() != 2) { return ExtraEnd(player, HCDriverResult.REFUSED, "ring-needs-point"); }
            m_ExtraHold = 0;
            m_Walker.Begin(step.to[0], step.to[1], "jog", 5, step.timeout_s);
            m_Stage = 1;
        }
        if (m_Stage == 1)
        {
            int result = m_Walker.Update(player, dt);
            if (result == HCDriverResult.RUNNING) { return result; }
            if (result != HCDriverResult.OK) { return ExtraEnd(player, result, "ring-approach"); }
            m_Stage = 2;
        }
        vector delta = player.GetPosition() - Vector(step.to[0], 0, step.to[1]);
        if (HCDriverWalker.FlatLength(delta) > 10) { return ExtraEnd(player, HCDriverResult.REFUSED, "ring-drift"); }
        m_ExtraHold += dt;
        if (m_ExtraHold >= step.hold_s) { return ExtraEnd(player, HCDriverResult.OK, "ring-held"); }
        return HCDriverResult.RUNNING;
    }

    protected int StepTakeLead(HCDriverStep step, PlayerBase player, float dt)
    {
        if (m_StepAge >= step.timeout_s) { return ExtraEnd(player, HCDriverResult.TIMEOUT, "lead-timeout"); }
        if (m_Stage == 0)
        {
            m_ExtraActions.LeadOnly = true;
            HCDriverArgs args = new HCDriverArgs;
            args.type = "Paper";
            m_ExtraActions.Begin("take", args, step.timeout_s);
            m_Stage = 1;
        }
        int result = m_ExtraActions.Tick(player, dt, m_Walker);
        if (result == HCDriverResult.RUNNING) { return result; }
        if (m_Stage == 1 && result == HCDriverResult.OK)
        {
            m_ExtraActions.Abort(player, m_Walker);
            HCDriverArgs writeArgs = new HCDriverArgs;
            writeArgs.use = "taken";
            m_ExtraActions.Begin("write", writeArgs, Math.Max(1, step.timeout_s - m_StepAge));
            m_Stage = 2;
            return HCDriverResult.RUNNING;
        }
        m_Text = "reason=lead-candidate-" + m_ExtraActions.Detail();
        m_ExtraActions.Abort(player, m_Walker);
        return result;
    }

    protected int StepSearchSite(HCDriverStep step, PlayerBase player, float dt)
    {
        if (m_StepAge >= step.timeout_s) { return ExtraEnd(player, HCDriverResult.TIMEOUT, "search-site-timeout"); }
        if (m_Stage == 0)
        {
            if (!m_ExtraAnchors.Find(step.site, m_ExtraAnchor)) { return ExtraEnd(player, HCDriverResult.REFUSED, "site-data-unavailable-or-unknown"); }
            m_Walker.Begin(m_ExtraAnchor[0], m_ExtraAnchor[2], "jog", 15, step.timeout_s);
            m_Stage = 10;
        }
        if (m_Stage == 10)
        {
            int approached = m_Walker.Update(player, dt);
            if (approached == HCDriverResult.RUNNING) { return approached; }
            if (approached != HCDriverResult.OK) { return ExtraEnd(player, approached, "site-approach"); }
            m_ExtraNear.Clear();
            m_ExtraCargo.Clear();
            GetGame().GetObjectsAtPosition3D(m_ExtraAnchor, 150, m_ExtraNear, m_ExtraCargo);
            m_ExtraCursor = 0;
            m_ExtraBest = 100000000;
            m_ExtraHouse = null;
            m_Stage = 1;
        }
        if (m_Stage == 1)
        {
            // At most eight candidate checks per frame; no repeated world scan.
            m_ExtraBudget.HCReset(8);
            while (m_ExtraCursor < m_ExtraNear.Count() && m_ExtraBudget.HCContinue())
            {
                House house = House.Cast(m_ExtraNear[m_ExtraCursor]);
                m_ExtraCursor++;
                if (!house || house.GetDoorCount() < 1) { continue; }
                float distance = vector.DistanceSq(m_ExtraAnchor, house.GetPosition());
                if (distance < m_ExtraBest) { m_ExtraBest = distance; m_ExtraHouse = house; }
            }
            if (m_ExtraCursor < m_ExtraNear.Count()) { return HCDriverResult.RUNNING; }
            if (!m_ExtraHouse) { return ExtraEnd(player, HCDriverResult.REFUSED, "site-no-enterable-house"); }
            m_Stage = 2;
        }
        if (m_Stage == 2)
        {
            // The ordinary action preview exposes admitted storage geometry, never supplies.
            HCSearchPreviewEntry preview = HCSearchPreviewSites.Get().EntryFor(m_ExtraHouse.GetType());
            if (!preview || !preview.Ready) { return HCDriverResult.RUNNING; }
            if (preview.Sites.Count() == 0) { return ExtraEnd(player, HCDriverResult.REFUSED, "house-no-search-storage"); }
            vector center = m_ExtraHouse.ModelToWorld(preview.Sites[0].Center);
            m_ExtraSearchCenter = center;
            // Native Building.c:73 GetDoorSoundPos supplies the entrance, not a position write.
            vector door = m_ExtraHouse.GetDoorSoundPos(0);
            HCDriverStep route = new HCDriverStep;
            route.points = {door[0], door[2], center[0], center[2]};
            route.gait = "walk";
            route.arrive_m = 1;
            route.timeout_s = Math.Max(1, step.timeout_s - m_StepAge);
            m_ExtraRoute.Begin(route);
            m_Stage = 3;
        }
        if (m_Stage == 3)
        {
            int walked = m_ExtraRoute.Tick(player, dt, m_Walker, m_ExtraActions);
            if (walked == HCDriverResult.RUNNING) { return walked; }
            if (walked != HCDriverResult.OK) { return ExtraEnd(player, walked, "search-interior-approach"); }
            // Route arrival is at least 2 m; storage's cursor condition needs 1.8 m.
            m_Walker.Begin(m_ExtraSearchCenter[0], m_ExtraSearchCenter[2], "walk", 0.6, Math.Max(1, step.timeout_s - m_StepAge));
            m_Stage = 31;
        }
        if (m_Stage == 31)
        {
            int precise = m_Walker.Update(player, dt);
            if (precise == HCDriverResult.RUNNING) { return precise; }
            if (precise != HCDriverResult.OK) { return ExtraEnd(player, precise, "search-storage-approach"); }
            m_ExtraActions.SearchHouse = m_ExtraHouse;
            m_ExtraActions.BeginInReach("search", Math.Max(1, step.timeout_s - m_StepAge));
            m_Stage = 4;
        }
        int result = m_ExtraActions.Tick(player, dt, m_Walker);
        if (result == HCDriverResult.RUNNING) { return result; }
        m_Text = "reason=search-site-" + m_ExtraActions.Detail();
        m_ExtraActions.Abort(player, m_Walker);
        return result;
    }

    protected int StepRaise(HCDriverStep step, PlayerBase player, float dt)
    {
        if (m_Stage == 0) { m_ExtraRaise.BeginRaise(step); m_Stage = 1; }
        int result = m_ExtraRaise.TickRaise(step, player, dt, m_Walker);
        m_Text = m_ExtraRaise.Detail();
        return result;
    }

    protected int StepRespawn(HCDriverStep step, PlayerBase player, float dt)
    {
#ifdef SERVER
        return ExtraEnd(player, HCDriverResult.UNSUPPORTED, "respawn-client-only");
#else
        if (m_StepAge >= step.timeout_s) { return ExtraEnd(player, HCDriverResult.TIMEOUT, "respawn-timeout"); }
        if (m_Stage == 0)
        {
            if (player.IsAlive()) { return ExtraEnd(player, HCDriverResult.REFUSED, "respawn-needs-death"); }
            // Native UIManager/mission entry is the same menu used by the death screen:
            // 3_Game/tools/UIManager.c:4 EnterScriptedMenu, :160 FindMenu; InGameMenu.c:339-365 above.
            InGameMenu menu = InGameMenu.Cast(GetGame().GetUIManager().FindMenu(MENU_INGAME));
            if (!menu) { menu = InGameMenu.Cast(GetGame().GetUIManager().EnterScriptedMenu(MENU_INGAME, null)); }
            if (!menu) { return ExtraEnd(player, HCDriverResult.REFUSED, "respawn-menu-unavailable"); }
            m_Stage = 1;
            menu.HCDriverRespawn();
            return HCDriverResult.RUNNING;
        }
        // HCCampRespawnMission.CreateCharacter selects the eligible camp automatically;
        // vanilla offers random/custom character, not a camp selection menu.
        Mission mission = GetGame().GetMission();
        bool ready = player.IsAlive() && !player.IsUnconscious() && player.GetCommand_Move() && player.GetInputController() && mission && !mission.IsControlDisabled();
        if (ready) { m_ExtraHold += dt; }
        else { m_ExtraHold = 0; }
        if (m_ExtraHold >= 2) { return ExtraEnd(player, HCDriverResult.OK, "respawn-movement-ready"); }
        return HCDriverResult.RUNNING;
#endif
    }
}

modded class HCClientDriver
{
    override void Init()
    {
#ifndef SERVER
        HCDriverExtra.Prepare();
#endif
        super.Init();
    }

    // Respawning temporarily removes the local player. The base runner waits for
    // a loaded player before dispatch, so keep this step's timeout alive in that gap.
    override void Tick(float timeslice)
    {
        if (m_Live && !m_Finished && m_CalibDone && m_StepOpen && m_Script && m_Index < m_Script.steps.Count())
        {
            HCDriverStep step = m_Script.steps[m_Index];
            if (step && step.kind == "respawn")
            {
                PlayerBase player = PlayerBase.Cast(GetGame().GetPlayer());
                if (!player || !player.IsPlayerLoaded())
                {
                    m_StepAge += Math.Clamp(timeslice, 0.001, 0.25);
                    HCDriverMovement.Stop();
                    if (m_StepAge >= step.timeout_s)
                    {
                        HCDriverExtra.Stop(player);
                        EndStep(step, HCDriverResult.TIMEOUT, "reason=respawn-player-unavailable", player);
                    }
                    return;
                }
                if (m_StepAge >= step.timeout_s)
                {
                    HCDriverExtra.Stop(player);
                    EndStep(step, HCDriverResult.TIMEOUT, "reason=respawn-timeout", player);
                    return;
                }
            }
        }
        super.Tick(timeslice);
    }

    override void Shutdown()
    {
        PlayerBase player = PlayerBase.Cast(GetGame().GetPlayer());
        HCDriverExtra.Stop(player);
        super.Shutdown();
    }
}
