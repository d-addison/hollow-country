// Dev-only test addon (never shipped). Real walking and real actions for the scripted client driver.
// Native scripts-1.30.164289 proofs:
//  movement  3_Game/human.c:7-12 HumanInputControllerOverrideType {DISABLED, ENABLED, ONE_FRAME};
//            :253 OverrideMovementSpeed (0 idle, 1 walk, 2 run, 3 sprint per :467), :256
//            OverrideMovementAngle (degrees, -180..180 per :459), :259 OverrideAimChangeX
//            (radians per tick per :30); :1458 Human.GetInputController; Object.c:305
//            GetOrientation (yaw degrees). The local player's own controller is the only one used;
//            collisions stay engine-owned. HCDriverMovement applies ONE_FRAME at CommandHandler;
//            navigation uses the measured camera frame and angle sign, with no aim feedback.
//  actions   4_World/Classes/UserActionsComponent/ActionManagerClient.c:804 PerformActionStart
//            (public), :1335 SetIgnoreAutomaticInputEnd, :286 EndActionInput;
//            ActionManagerBase.c:91 GetRunningAction, :214 static GetAction(typename);
//            ActionBase.c:968 Can(player, target, item); ActionTargets.c:125 ActionTarget ctor;
//            DayZPhysics.c:199 RaycastRV (3_Game/Global); CraftingManager.c:136 SetInventoryCraft;
//            Man.c:178 PredictiveTakeEntityToHands; Inventory.c:127 EnumerateInventory;
//            Game.c:930 GetObjectsAtPosition3D; InventoryItem.c:18 GetTunedFrequency;
//            MiscGameplayFunctions.c:778 GetPlayerHeadPosition.
//  melee/fire have no retail native client entry: the player input actions are UAInput reads and
//            UAInput.SyncedOverride exists only under #ifdef INPUT_OVERRIDE, so both steps log
//            result=unsupported and never call server code.
// Per frame: one raycast at most, one small object query on the first frame of a step; the only
// allocations are the per-step arrays. No counter, HCUse or server feature entry is touched.
class HCDriverWalker
{
    protected bool m_Active;
    protected vector m_Target;
    protected float m_Speed;
    protected float m_Arrive;
    protected float m_Timeout;
    protected float m_Elapsed;
    protected float m_Best;
    protected float m_NoProgress;
    protected int m_Sidesteps;
    protected float m_SideLeft;
    protected float m_SideSign = 1.0;
    protected string m_Detail;
    // Route mode: after HANDOVER_SECONDS without progress the walker flags m_Stuck and keeps going;
    // the route's stuck ladder (HCDriverRoute) decides what to do. Begin turns it off.
    static const float HANDOVER_SECONDS = 8.0;
    protected bool m_Handover;
    protected bool m_Stuck;

    bool IsActive()
    {
        return m_Active;
    }

    string Detail()
    {
        return m_Detail;
    }

    void Begin(float x, float z, string gait, float arriveMeters, float timeoutSeconds)
    {
        m_Active = true;
        m_Target = Vector(x, 0, z);
        m_Speed = 2.0;
        if (gait == "walk") { m_Speed = 1.0; }
        if (gait == "sprint") { m_Speed = 3.0; }
        m_Arrive = Math.Max(arriveMeters, 1.0);
        m_Timeout = Math.Max(timeoutSeconds, 1.0);
        m_Elapsed = 0;
        m_Best = 1000000;
        m_NoProgress = 0;
        m_Sidesteps = 0;
        m_SideLeft = 0;
        m_SideSign = 1.0;
        m_Detail = "";
        m_Handover = false;
        m_Stuck = false;
    }

    void HandOverStuck()
    {
        m_Handover = true;
    }

    // True once per stuck spell in route mode.
    bool TakeStuck()
    {
        bool stuck = m_Stuck;
        m_Stuck = false;
        return stuck;
    }

    // Plain forward movement along the current heading (the sprint step).
    void Forward(PlayerBase player, float speed)
    {
        if (!player) { return; }
        HumanInputController input = player.GetInputController();
        if (!input) { return; }
        HCDriverMovement.Request(speed, 0);
    }

    void Release(PlayerBase player)
    {
        m_Active = false;
        HCDriverMovement.Stop();
        if (!player) { return; }
        HumanInputController input = player.GetInputController();
        if (!input) { return; }
        input.OverrideMovementSpeed(HumanInputControllerOverrideType.DISABLED, 0);
        input.OverrideMovementAngle(HumanInputControllerOverrideType.DISABLED, 0);
        input.OverrideAimChangeX(HumanInputControllerOverrideType.DISABLED, 0);
    }

    static float CameraYaw()
    {
        vector facing = GetGame().GetCurrentCameraDirection();
        return Math.Atan2(facing[0], facing[2]) * Math.RAD2DEG;
    }

    static string XZ(vector pos)
    {
        return Math.Round(pos[0]).ToString() + "," + Math.Round(pos[2]).ToString();
    }

    static float FlatLength(vector delta)
    {
        return Math.Sqrt(delta[0] * delta[0] + delta[2] * delta[2]);
    }

    static float Wrap180(float degrees)
    {
        float wrapped = degrees;
        while (wrapped > 180.0) { wrapped = wrapped - 360.0; }
        while (wrapped < -180.0) { wrapped = wrapped + 360.0; }
        return wrapped;
    }

    int Update(PlayerBase player, float dt)
    {
        if (!m_Active) { return HCDriverResult.OK; }
        if (!player || !player.IsAlive() || player.IsUnconscious())
        {
            Release(player);
            m_Detail = "player-unavailable";
            return HCDriverResult.REFUSED;
        }
        HumanInputController input = player.GetInputController();
        if (!input)
        {
            Release(player);
            m_Detail = "no-input-controller";
            return HCDriverResult.UNSUPPORTED;
        }
        m_Elapsed = m_Elapsed + dt;
        vector pos = player.GetPosition();
        float dx = m_Target[0] - pos[0];
        float dz = m_Target[2] - pos[2];
        float dist = Math.Sqrt(dx * dx + dz * dz);
        if (dist <= m_Arrive)
        {
            Release(player);
            m_Detail = "arrived remaining_m=" + Math.Round(dist).ToString();
            return HCDriverResult.OK;
        }
        if (m_Elapsed > m_Timeout)
        {
            Release(player);
            m_Detail = "route-timeout remaining_m=" + Math.Round(dist).ToString();
            return HCDriverResult.TIMEOUT;
        }
        // Stuck handling: 20 s without 1 m of progress = a sidestep, twice, then timeout.
        if (dist < m_Best - 1.0)
        {
            m_Best = dist;
            m_NoProgress = 0;
        }
        else
        {
            m_NoProgress = m_NoProgress + dt;
        }
        if (m_Handover && m_NoProgress >= HCDriverWalker.HANDOVER_SECONDS)
        {
            m_Stuck = true;
            m_NoProgress = 0;
            m_Best = dist;
        }
        if (m_NoProgress >= 20.0)
        {
            if (m_Sidesteps >= 2)
            {
                Release(player);
                m_Detail = "stuck sidesteps=2 remaining_m=" + Math.Round(dist).ToString();
                return HCDriverResult.TIMEOUT;
            }
            m_Sidesteps = m_Sidesteps + 1;
            m_SideLeft = 2.0;
            m_SideSign = -m_SideSign;
            m_NoProgress = 0;
            m_Best = dist;
        }
        if (!HCDriverMovement.Calibrated)
        {
            Release(player);
            m_Detail = "movement-uncalibrated";
            return HCDriverResult.REFUSED;
        }
        if (!player.GetCommand_Move())
        {
            Release(player);
            m_Detail = "not-command-move id=" + HCDriverMovement.CommandId.ToString();
            return HCDriverResult.REFUSED;
        }
        // Use the camera/input frame measured at calibration, never body-yaw aim feedback.
        float want = Math.Atan2(dx, dz) * Math.RAD2DEG;
        float frame = HCDriverWalker.CameraYaw() + HCDriverMovement.HeadingOffset;
        float diff = HCDriverWalker.Wrap180(want - frame);
        if (m_SideLeft > 0)
        {
            m_SideLeft = m_SideLeft - dt;
            diff = HCDriverWalker.Wrap180(diff + 90.0 * m_SideSign);
        }
        HCDriverMovement.Request(m_Speed, diff * HCDriverMovement.AngleSign);
        return HCDriverResult.RUNNING;
    }
}

class HCDriverActions
{
    static const int P_PREP = 0;
    static const int P_FIND = 1;
    static const int P_RUN = 2;
    static const int P_SETTLE = 3;
    static const int RAYS = 72;
    static const float REACH = 3.0;
    static const float FIND_RADIUS = 40.0;

    protected string m_Name;
    protected ref HCDriverArgs m_Args;
    protected float m_Timeout;
    protected float m_Elapsed;
    protected float m_Dt;
    protected int m_Phase;
    protected string m_Detail;
    protected bool m_Begun;
    protected float m_HoldRetry;
    protected ItemBase m_Main;
    protected ItemBase m_Second;
    protected Object m_Approach;
    protected int m_Ray;
    protected float m_PhaseAge;
    protected float m_RunAge;
    protected bool m_SawRunning;
    protected int m_Stage;
    protected ref set<Object> m_Hits = new set<Object>;
    protected ref array<EntityAI> m_Inventory = new array<EntityAI>;
    protected ref ActionTarget m_Target;
    protected ActionBase m_Action;
    // Survives Begin: the last Paper a take step picked up (the read and write steps use it).
    protected ItemBase m_LastTaken;
    protected bool m_Crouched;
    protected bool m_Sent;
    // Route door rung: scan only what is in reach where the player stands, never walk to a candidate.
    protected bool m_InReachOnly;

    string Detail()
    {
        return m_Detail;
    }

    void Begin(string name, HCDriverArgs args, float timeoutSeconds)
    {
        m_Name = name;
        m_Args = args;
        if (!m_Args) { m_Args = new HCDriverArgs; }
        m_Timeout = Math.Max(timeoutSeconds, 5.0);
        m_Elapsed = 0;
        m_Phase = HCDriverActions.P_PREP;
        m_PhaseAge = 0;
        m_Detail = "";
        m_Begun = false;
        m_HoldRetry = 0;
        m_Main = null;
        m_Second = null;
        m_Approach = null;
        m_Ray = 0;
        m_SawRunning = false;
        m_Stage = 0;
        m_Target = null;
        m_Action = null;
        m_Sent = false;
        m_InReachOnly = false;
    }

    // The route's door rung: open_door on a door in reach of where the player stands (one ray per
    // frame, RAYS rays), refused no-door-in-reach otherwise. The walker is never started.
    void BeginInReach(string name, float timeoutSeconds)
    {
        Begin(name, null, timeoutSeconds);
        m_InReachOnly = true;
    }

    protected ActionManagerClient Manager(PlayerBase player)
    {
        return ActionManagerClient.Cast(player.GetActionManager());
    }

    // Ends whatever this step started; safe to call at any time.
    void Abort(PlayerBase player, HCDriverWalker walker)
    {
        walker.Release(player);
        if (!player) { return; }
        StandUp(player);
        ActionManagerClient manager = Manager(player);
        if (manager)
        {
            manager.SetIgnoreAutomaticInputEnd(false);
            if (manager.GetRunningAction()) { manager.EndActionInput(); }
        }
    }

    // ActionWorldCraft needs STANCEMASK_CROUCH (ActionWorldCraft.c:43); put the player back afterwards.
    protected void StandUp(PlayerBase player)
    {
        if (!m_Crouched) { return; }
        m_Crouched = false;
        HumanCommandMove move = player.GetCommand_Move();
        if (move) { move.ForceStance(DayZPlayerConstants.STANCEIDX_ERECT); }
    }

    protected int Finish(int code, string detail)
    {
        m_Detail = detail;
        return code;
    }

    protected ItemBase FindHeldOrInventory(PlayerBase player, string type, ItemBase except)
    {
        if (type == "") { return null; }
        ItemBase hands = player.GetItemInHands();
        if (hands && hands != except && hands.IsKindOf(type)) { return hands; }
        m_Inventory.Clear();
        player.GetInventory().EnumerateInventory(InventoryTraversalType.PREORDER, m_Inventory);
        for (int index = 0; index < m_Inventory.Count(); index++)
        {
            ItemBase found = ItemBase.Cast(m_Inventory[index]);
            if (found && found != except && !found.IsPendingDeletion() && found.IsKindOf(type)) { return found; }
        }
        return null;
    }

    // Same as FindHeldOrInventory but never an attachment: a light already mounted on a host is not loose.
    protected ItemBase FindLoose(PlayerBase player, string type, ItemBase except)
    {
        if (type == "") { return null; }
        m_Inventory.Clear();
        player.GetInventory().EnumerateInventory(InventoryTraversalType.PREORDER, m_Inventory);
        for (int index = 0; index < m_Inventory.Count(); index++)
        {
            ItemBase found = ItemBase.Cast(m_Inventory[index]);
            if (!found || found == except || found.IsPendingDeletion() || !found.IsKindOf(type)) { continue; }
            if (found.GetInventory() && found.GetInventory().IsAttachment()) { continue; }
            return found;
        }
        return null;
    }

    // Nearest loose item of a type (or of a class list when the type is "forage") around the player.
    protected ItemBase FindGround(PlayerBase player, string type, float radius)
    {
        array<Object> near = new array<Object>;
        array<CargoBase> nearCargo = new array<CargoBase>;
        GetGame().GetObjectsAtPosition3D(player.GetPosition(), radius, near, nearCargo);
        ItemBase best;
        float bestDistance = 1000000;
        for (int index = 0; index < near.Count(); index++)
        {
            ItemBase candidate = ItemBase.Cast(near[index]);
            if (!candidate || candidate.IsPendingDeletion() || candidate.GetHierarchyParent()) { continue; }
            if (!MatchesGround(candidate, type)) { continue; }
            float distance = vector.Distance(player.GetPosition(), candidate.GetPosition());
            if (distance < bestDistance)
            {
                bestDistance = distance;
                best = candidate;
            }
        }
        return best;
    }

    protected bool MatchesGround(ItemBase candidate, string type)
    {
        if (type != "forage") { return candidate.IsKindOf(type); }
        array<string> classes = {"SambucusBerry", "CaninaBerry", "BoletusMushroom", "MacrolepiotaMushroom", "AmanitaMushroom", "AuriculariaMushroom", "CraterellusMushroom", "PsilocybeMushroom", "Cannabis"};
        for (int index = 0; index < classes.Count(); index++)
        {
            if (candidate.IsKindOf(classes[index])) { return true; }
        }
        return false;
    }

    protected bool Accept(string kind, PlayerBase player, Object object)
    {
        if (!object || object.IsPendingDeletion()) { return false; }
        if (kind == "search") { return House.Cast(object) != null; }
        if (kind == "close_door" || kind == "open_door")
        {
            BuildingBase building = BuildingBase.Cast(object);
            return building && building.GetDoorCount() > 0;
        }
        if (kind == "salvage") { return HCWreckSalvage.Reviewed(object.GetType()); }
        if (kind == "flip") { return CarScript.Cast(object) != null; }
        return false;
    }

    protected Object NearestCandidate(string kind, PlayerBase player)
    {
        array<Object> near = new array<Object>;
        array<CargoBase> nearCargo = new array<CargoBase>;
        GetGame().GetObjectsAtPosition3D(player.GetPosition(), HCDriverActions.FIND_RADIUS, near, nearCargo);
        Object best;
        float bestDistance = 1000000;
        for (int index = 0; index < near.Count(); index++)
        {
            Object candidate = near[index];
            if (!Accept(kind, player, candidate)) { continue; }
            float distance = vector.Distance(player.GetPosition(), candidate.GetPosition());
            if (distance < bestDistance)
            {
                bestDistance = distance;
                best = candidate;
            }
        }
        return best;
    }

    // One ray per frame around the player at head height. Returns true once an accepted object
    // with a usable ActionTarget is found; m_Target is then a real raycast-derived target.
    protected bool ScanStep(string kind, PlayerBase player, ItemBase item)
    {
        int yawIndex = m_Ray % 24;
        int pitchIndex = (m_Ray / 24) % 3;
        m_Ray = m_Ray + 1;
        float yaw = yawIndex * 15.0 * Math.DEG2RAD;
        float pitch = 10.0;
        if (pitchIndex == 1) { pitch = -10.0; }
        if (pitchIndex == 2) { pitch = -35.0; }
        pitch = pitch * Math.DEG2RAD;
        vector begin = MiscGameplayFunctions.GetPlayerHeadPosition(player);
        vector direction = Vector(Math.Sin(yaw) * Math.Cos(pitch), Math.Sin(pitch), Math.Cos(yaw) * Math.Cos(pitch));
        vector end = begin + direction * HCDriverActions.REACH;
        vector contactPos;
        vector contactDir;
        int contactComponent;
        m_Hits.Clear();
        if (!DayZPhysics.RaycastRV(begin, end, contactPos, contactDir, contactComponent, m_Hits, null, player)) { return false; }
        for (int index = 0; index < m_Hits.Count(); index++)
        {
            Object hit = m_Hits[index];
            if (!Accept(kind, player, hit)) { continue; }
            ActionTarget candidate = new ActionTarget(hit, null, contactComponent, contactPos, 1.0);
            if (m_Action && m_Action.Can(player, candidate, item))
            {
                m_Target = candidate;
                return true;
            }
        }
        return false;
    }

    // Starts the action through the real client entry. The caller has checked Can().
    protected void StartAction(PlayerBase player, ActionBase action, ActionTarget target, ItemBase item)
    {
        ActionManagerClient manager = Manager(player);
        manager.SetIgnoreAutomaticInputEnd(true);
        manager.PerformActionStart(action, target, item);
        m_SawRunning = false;
        m_RunAge = 0;
        m_Phase = HCDriverActions.P_RUN;
    }

    // One call per frame; returns RUNNING until the step has a final result.
    int Tick(PlayerBase player, float dt, HCDriverWalker walker)
    {
        if (!player || !player.IsAlive() || player.IsUnconscious()) { return Finish(HCDriverResult.REFUSED, "player-unavailable"); }
        ActionManagerClient manager = Manager(player);
        if (!manager) { return Finish(HCDriverResult.UNSUPPORTED, "no-client-action-manager"); }
        m_Dt = dt;
        m_Elapsed = m_Elapsed + dt;
        m_PhaseAge = m_PhaseAge + dt;
        if (m_Phase == HCDriverActions.P_PREP && m_Begun && m_PhaseAge > 8.0)
        {
            Abort(player, walker);
            return Finish(HCDriverResult.REFUSED, "hands-request-not-confirmed:inventory-busy-or-no-room");
        }
        if (m_Elapsed > m_Timeout)
        {
            Abort(player, walker);
            return Finish(HCDriverResult.TIMEOUT, m_Name + "-phase=" + m_Phase.ToString());
        }
        if (m_Name == "melee") { return Finish(HCDriverResult.UNSUPPORTED, "no-native-client-entry-for-melee-input"); }
        if (m_Name == "fire") { return Finish(HCDriverResult.UNSUPPORTED, "no-native-client-entry-for-fire-input"); }
        if (m_Name == "craft")
        {
            int crafted = TickCraft(player, manager);
            if (crafted != HCDriverResult.RUNNING) { StandUp(player); }
            return crafted;
        }
        if (m_Name == "earplugs") { return TickEarplugs(); }
        if (m_Name == "read") { return TickRead(player, manager); }
        if (m_Name == "write") { return TickWrite(player, manager); }
        if (m_Name == "take") { return TickTake(player, manager, walker, "take"); }
        if (m_Name == "pickup_forage") { return TickTake(player, manager, walker, "forage"); }
        if (m_Name == "mount") { return TickMount(player, manager); }
        if (m_Name == "radio") { return TickRadio(player, manager); }
        if (m_Name == "search" || m_Name == "close_door" || m_Name == "open_door" || m_Name == "salvage" || m_Name == "flip") { return TickScanned(player, manager, walker); }
        return Finish(HCDriverResult.REFUSED, "unknown-action-kind");
    }

    // Same predictive inventory requests as a player drag. The caller bounds/retries the request.
    static void RequestHands(PlayerBase player, ItemBase item)
    {
        if (!item || player.GetItemInHands() == item || !ScriptInputUserData.CanStoreInputUserData()) { return; }
        ItemBase held = player.GetItemInHands();
        if (held)
        {
            if (!player.PredictiveSwapEntities(held, item) && ScriptInputUserData.CanStoreInputUserData())
            {
                player.PredictiveTakeEntityToInventory(FindInventoryLocationType.ANY, held);
            }
        }
        else { player.PredictiveTakeEntityToHands(item); }
    }

    // Puts an item in hands through the native predictive entry; true once it is held.
    protected bool Hold(PlayerBase player, ItemBase item)
    {
        if (player.GetItemInHands() == item) { return true; }
        // A predictive request can be refused while input data is busy (Man.c:180).
        // Retry at one-second intervals; swap when hands are occupied (Man.c:422).
        if (!m_Begun || m_PhaseAge >= m_HoldRetry)
        {
            m_Begun = true;
            m_HoldRetry = m_PhaseAge + 1.0;
            HCDriverActions.RequestHands(player, item);
        }
        return false;
    }

    // Waits for a started action to run and end. Returns RUNNING, OK or REFUSED.
    protected int Settle(PlayerBase player, ActionManagerClient manager, float dt)
    {
        m_RunAge = m_RunAge + dt;
        if (manager.GetRunningAction())
        {
            m_SawRunning = true;
            return HCDriverResult.RUNNING;
        }
        if (m_SawRunning || m_RunAge > 1.5)
        {
            manager.SetIgnoreAutomaticInputEnd(false);
            if (m_SawRunning) { return Finish(HCDriverResult.OK, "completed-client-side"); }
            return Finish(HCDriverResult.OK, "instant-client-side");
        }
        return HCDriverResult.RUNNING;
    }

    protected int TickCraft(PlayerBase player, ActionManagerClient manager)
    {
        if (m_Phase == HCDriverActions.P_PREP)
        {
            m_Main = FindHeldOrInventory(player, m_Args.item1, null);
            if (!m_Main) { return Finish(HCDriverResult.REFUSED, "item-missing:" + m_Args.item1); }
            m_Second = FindHeldOrInventory(player, m_Args.item2, m_Main);
            if (!m_Second) { return Finish(HCDriverResult.REFUSED, "item-missing:" + m_Args.item2); }
            if (!Hold(player, m_Main)) { return HCDriverResult.RUNNING; }
            m_Phase = HCDriverActions.P_FIND;
            m_Begun = false;
            m_HoldRetry = 0;
        }
        if (m_Phase == HCDriverActions.P_FIND)
        {
            if (player.GetItemInHands() != m_Main) { return HCDriverResult.RUNNING; }
            if (!player.IsPlayerInStance(DayZPlayerConstants.STANCEMASK_CROUCH))
            {
                HumanCommandMove move = player.GetCommand_Move();
                if (move)
                {
                    move.ForceStance(DayZPlayerConstants.STANCEIDX_CROUCH);
                    m_Crouched = true;
                }
                return HCDriverResult.RUNNING;
            }
            if (!player.GetCraftingManager().SetInventoryCraft(-1, m_Main, m_Second)) { return Finish(HCDriverResult.REFUSED, "no-valid-recipe"); }
            m_Action = ActionManagerBase.GetAction(ActionWorldCraft);
            m_Target = new ActionTarget(m_Second, null, -1, vector.Zero, -1.0);
            if (player.GetCraftingManager().IsInventoryCraft() && m_Action && m_Action.Can(player, m_Target, m_Main))
            {
                StartAction(player, m_Action, m_Target, m_Main);
                return HCDriverResult.RUNNING;
            }
            // Instant recipes were sent by SetInventoryCraft itself over the native craft RPC.
            m_Phase = HCDriverActions.P_SETTLE;
            m_PhaseAge = 0;
            return HCDriverResult.RUNNING;
        }
        if (m_Phase == HCDriverActions.P_RUN) { return Settle(player, manager, m_Dt); }
        if (m_PhaseAge > 3.0)
        {
            if (!m_Main || !m_Second) { return Finish(HCDriverResult.OK, "instant-recipe-consumed-inputs"); }
            return Finish(HCDriverResult.REFUSED, "craft-not-performed");
        }
        return HCDriverResult.RUNNING;
    }

    protected int TickTake(PlayerBase player, ActionManagerClient manager, HCDriverWalker walker, string flavor)
    {
        if (m_Phase == HCDriverActions.P_PREP)
        {
            float radius = HCDriverActions.FIND_RADIUS;
            string type = m_Args.type;
            if (flavor == "forage")
            {
                radius = HCDriverActions.FIND_RADIUS;
                type = "forage";
            }
            m_Main = FindGround(player, type, radius);
            if (!m_Main) { return Finish(HCDriverResult.REFUSED, "no-item-within-" + Math.Round(radius).ToString() + "m"); }
            m_Phase = HCDriverActions.P_FIND;
            m_PhaseAge = 0;
        }
        if (m_Phase == HCDriverActions.P_FIND)
        {
            if (!m_Main) { return Finish(HCDriverResult.REFUSED, "item-gone"); }
            float distance = vector.Distance(player.GetPosition(), m_Main.GetPosition());
            if (distance > 2.0)
            {
                if (!walker.IsActive()) { walker.Begin(m_Main.GetPosition()[0], m_Main.GetPosition()[2], "walk", 1.5, 60); }
                int walked = walker.Update(player, m_Dt);
                if (walked == HCDriverResult.RUNNING) { return walked; }
                if (walked != HCDriverResult.OK) { return Finish(walked, "approach-" + walker.Detail()); }
                return HCDriverResult.RUNNING;
            }
            m_Action = ActionManagerBase.GetAction(ActionTakeItem);
            m_Target = new ActionTarget(m_Main, null, -1, vector.Zero, -1.0);
            if (!m_Action || !m_Action.Can(player, m_Target, null)) { return Finish(HCDriverResult.REFUSED, "take-not-allowed-here"); }
            StartAction(player, m_Action, m_Target, null);
            return HCDriverResult.RUNNING;
        }
        int settled = Settle(player, manager, m_Dt);
        if (settled == HCDriverResult.OK && m_Main && !m_Main.GetHierarchyParent()) { return Finish(HCDriverResult.REFUSED, "item-still-on-ground"); }
        if (settled == HCDriverResult.OK && flavor == "take" && m_Main && m_Main.IsKindOf("Paper")) { m_LastTaken = m_Main; }
        return settled;
    }

    protected int TickMount(PlayerBase player, ActionManagerClient manager)
    {
        if (m_Phase == HCDriverActions.P_PREP)
        {
            m_Main = FindHeldOrInventory(player, m_Args.target, null);
            if (!m_Main) { return Finish(HCDriverResult.REFUSED, "host-missing:" + m_Args.target); }
            m_Second = FindLoose(player, m_Args.item, m_Main);
            if (!m_Second) { return Finish(HCDriverResult.REFUSED, "item-missing:" + m_Args.item); }
            if (!Hold(player, m_Main)) { return HCDriverResult.RUNNING; }
            m_Phase = HCDriverActions.P_FIND;
        }
        if (m_Phase == HCDriverActions.P_FIND)
        {
            if (player.GetItemInHands() != m_Main) { return HCDriverResult.RUNNING; }
            m_Action = ActionManagerBase.GetAction(HCActionMountTapedLight);
            m_Target = new ActionTarget(null, null, -1, vector.Zero, -1.0);
            if (!m_Action || !m_Action.Can(player, m_Target, m_Main)) { return Finish(HCDriverResult.REFUSED, "mount-not-allowed:needs-light-and-tape"); }
            StartAction(player, m_Action, m_Target, m_Main);
            return HCDriverResult.RUNNING;
        }
        return Settle(player, manager, m_Dt);
    }

    protected void CloseNoteMenu()
    {
        UIManager ui = GetGame().GetUIManager();
        if (!ui || !ui.IsMenuOpen(MENU_NOTE)) { return; }
        UIScriptedMenu noteMenu = ui.FindMenu(MENU_NOTE);
        if (noteMenu) { noteMenu.Close(); }
    }

    // The earplugs key handler (HCEarplugs.Press, through the test addon's HCTestPress). Four presses
    // cycle the level 1, 2, 3 and back to out, so the client profile preference ends unchanged.
    protected int TickEarplugs()
    {
        for (int press = 0; press < 4; press++)
        {
            if (!HCEarplugs.HCTestPress()) { return Finish(HCDriverResult.REFUSED, "earplugs-client-not-started"); }
        }
        return Finish(HCDriverResult.OK, "pressed-4x-level-back-to-out");
    }

    // ActionReadPaper from the hands (the Paper the last take step picked up, else any Paper).
    protected int TickRead(PlayerBase player, ActionManagerClient manager)
    {
        if (m_Phase == HCDriverActions.P_PREP)
        {
            m_Main = m_LastTaken;
            if (!m_Main || m_Main.IsPendingDeletion()) { m_Main = FindHeldOrInventory(player, "Paper", null); }
            if (!m_Main) { return Finish(HCDriverResult.REFUSED, "paper-missing"); }
            if (!Hold(player, m_Main)) { return HCDriverResult.RUNNING; }
            m_Phase = HCDriverActions.P_FIND;
        }
        if (m_Phase == HCDriverActions.P_FIND)
        {
            if (player.GetItemInHands() != m_Main) { return HCDriverResult.RUNNING; }
            m_Action = ActionManagerBase.GetAction(ActionReadPaper);
            m_Target = new ActionTarget(null, null, -1, vector.Zero, -1.0);
            if (!m_Action || !m_Action.Can(player, m_Target, m_Main)) { return Finish(HCDriverResult.REFUSED, "read-not-allowed"); }
            StartAction(player, m_Action, m_Target, m_Main);
            return HCDriverResult.RUNNING;
        }
        if (m_Phase == HCDriverActions.P_RUN)
        {
            int settled = Settle(player, manager, m_Dt);
            if (settled == HCDriverResult.RUNNING) { return settled; }
            if (settled != HCDriverResult.OK) { return settled; }
            m_Phase = HCDriverActions.P_SETTLE;
            m_PhaseAge = 0;
            return HCDriverResult.RUNNING;
        }
        // The server's reply opens the vanilla note menu; give it a moment, then close it.
        if (m_PhaseAge < 2.5) { return HCDriverResult.RUNNING; }
        CloseNoteMenu();
        return Finish(HCDriverResult.OK, "read-started-note-menu-closed");
    }

    // The writable-notes pack's write action (ActionWritePaper: pen in hands, Paper as target), then the
    // very RPC the vanilla note menu sends on OK (NoteMenu.c:121). args.use = taken (the Paper the last
    // take step picked up) or gear (another Paper from the inventory). A lead note is refused by HC on
    // the server (HCNotesCompat); a plain Paper passes through (write_rpc_passed).
    protected int TickWrite(PlayerBase player, ActionManagerClient manager)
    {
        if (m_Phase == HCDriverActions.P_PREP)
        {
            m_Second = FindHeldOrInventory(player, "Paper", m_LastTaken);
            if (m_Args.use == "taken") { m_Second = m_LastTaken; }
            if (!m_Second || m_Second.IsPendingDeletion()) { return Finish(HCDriverResult.REFUSED, "paper-missing:" + m_Args.use); }
            m_Main = FindHeldOrInventory(player, "Pen_Black", null);
            if (!m_Main) { return Finish(HCDriverResult.REFUSED, "item-missing:Pen_Black"); }
            if (!Hold(player, m_Main)) { return HCDriverResult.RUNNING; }
            m_Phase = HCDriverActions.P_FIND;
        }
        if (m_Phase == HCDriverActions.P_FIND)
        {
            if (player.GetItemInHands() != m_Main) { return HCDriverResult.RUNNING; }
            m_Action = ActionManagerBase.GetAction(ActionWritePaper);
            m_Target = new ActionTarget(m_Second, null, -1, vector.Zero, -1.0);
            if (!m_Action || !m_Action.Can(player, m_Target, m_Main)) { return Finish(HCDriverResult.REFUSED, "write-not-allowed:needs-pen-and-paper"); }
            StartAction(player, m_Action, m_Target, m_Main);
            return HCDriverResult.RUNNING;
        }
        // The action loops until ended; the server has initialised the note data by the time it runs.
        m_RunAge = m_RunAge + m_Dt;
        if (m_RunAge < 1.5) { return HCDriverResult.RUNNING; }
        if (!m_Sent)
        {
            m_Sent = true;
            Param1<string> text = new Param1<string>("soak note");
            m_Second.RPCSingleParam(ERPCs.RPC_WRITE_NOTE_CLIENT, text, true);
            m_RunAge = 0;
            return HCDriverResult.RUNNING;
        }
        if (m_RunAge < 2.0) { return HCDriverResult.RUNNING; }
        CloseNoteMenu();
        manager.SetIgnoreAutomaticInputEnd(false);
        if (manager.GetRunningAction()) { manager.EndActionInput(); }
        return Finish(HCDriverResult.OK, "write-action-started-rpc-sent");
    }

    // GetTunedFrequency is declared on ItemTransmitter, not ItemBase (native compile, soak 178 boot 3).
    protected float TunedFrequency(ItemBase item)
    {
        TransmitterBase radio;
        if (!Class.CastTo(radio, item)) { return -1.0; }
        return radio.GetTunedFrequency();
    }

    protected int TickRadio(PlayerBase player, ActionManagerClient manager)
    {
        float wanted = m_Args.freq.ToFloat();
        if (m_Phase == HCDriverActions.P_PREP)
        {
            m_Main = FindHeldOrInventory(player, "PersonalRadio", null);
            if (!m_Main) { m_Main = FindHeldOrInventory(player, "BaseRadio", null); }
            if (!m_Main || !m_Main.IsTransmitter()) { return Finish(HCDriverResult.REFUSED, "no-transmitter-item"); }
            if (!Hold(player, m_Main)) { return HCDriverResult.RUNNING; }
            m_Phase = HCDriverActions.P_FIND;
            m_Stage = 0;
        }
        if (m_Phase == HCDriverActions.P_FIND)
        {
            if (player.GetItemInHands() != m_Main) { return HCDriverResult.RUNNING; }
            if (Math.AbsFloat(TunedFrequency(m_Main) - wanted) < 0.05) { return Finish(HCDriverResult.OK, "tuned-freq=" + m_Args.freq); }
            if (!m_Main.GetCompEM() || !m_Main.GetCompEM().IsWorking())
            {
                if (m_Stage == 0)
                {
                    m_Stage = 1;
                    m_Action = ActionManagerBase.GetAction(ActionTurnOnTransmitter);
                    m_Target = new ActionTarget(null, null, -1, vector.Zero, -1.0);
                    if (!m_Action || !m_Action.Can(player, m_Target, m_Main)) { return Finish(HCDriverResult.REFUSED, "radio-cannot-switch-on:needs-battery"); }
                    manager.PerformActionStart(m_Action, m_Target, m_Main);
                    m_PhaseAge = 0;
                }
                if (m_PhaseAge > 4.0) { return Finish(HCDriverResult.REFUSED, "radio-stayed-off"); }
                return HCDriverResult.RUNNING;
            }
            m_Action = ActionManagerBase.GetAction(ActionTuneFrequency);
            m_Target = new ActionTarget(null, null, -1, vector.Zero, -1.0);
            if (!m_Action || !m_Action.Can(player, m_Target, m_Main)) { return Finish(HCDriverResult.REFUSED, "tune-not-allowed-here"); }
            StartAction(player, m_Action, m_Target, m_Main);
            return HCDriverResult.RUNNING;
        }
        // Tuning repeats once a second until the wanted frequency is reached, then the input ends.
        if (Math.AbsFloat(TunedFrequency(m_Main) - wanted) < 0.05)
        {
            manager.SetIgnoreAutomaticInputEnd(false);
            manager.EndActionInput();
            return Finish(HCDriverResult.OK, "tuned-freq=" + m_Args.freq);
        }
        return HCDriverResult.RUNNING;
    }

    // search, close_door, open_door, salvage, flip: find a real target by raycast (walking toward the
    // nearest candidate while scanning), then start the action through the client manager.
    protected int TickScanned(PlayerBase player, ActionManagerClient manager, HCDriverWalker walker)
    {
        if (m_Phase == HCDriverActions.P_PREP)
        {
            if (m_Name == "salvage")
            {
                m_Main = FindHeldOrInventory(player, m_Args.item, null);
                if (!m_Main) { return Finish(HCDriverResult.REFUSED, "tool-missing:" + m_Args.item); }
                if (!Hold(player, m_Main)) { return HCDriverResult.RUNNING; }
            }
            if (m_Name == "flip")
            {
                m_Main = FindHeldOrInventory(player, m_Args.item, null);
                if (m_Main && !Hold(player, m_Main)) { return HCDriverResult.RUNNING; }
            }
            if (m_Name == "salvage") { m_Action = ActionManagerBase.GetAction(HCActionSalvageWreck); }
            if (m_Name == "flip") { m_Action = ActionManagerBase.GetAction(HCActionFlipVehicle); }
            if (m_Name == "search") { m_Action = ActionManagerBase.GetAction(HCActionSearchInterior); }
            if (m_Name == "close_door") { m_Action = ActionManagerBase.GetAction(ActionCloseDoors); }
            // ActionOpenDoors.c:1 (ActionCondition :40 GetDoorIndex(target.GetComponentIndex()), :52
            // CanDoorBeOpened); Building.c:28 GetDoorIndex, :34 IsDoorOpen, :55 IsDoorLocked. A locked or
            // open door fails Can() and is never forced.
            if (m_Name == "open_door") { m_Action = ActionManagerBase.GetAction(ActionOpenDoors); }
            if (!m_Action) { return Finish(HCDriverResult.UNSUPPORTED, "action-class-not-registered"); }
            if (!m_InReachOnly)
            {
                m_Approach = NearestCandidate(m_Name, player);
                if (!m_Approach) { return Finish(HCDriverResult.REFUSED, "no-candidate-within-40m"); }
            }
            m_Phase = HCDriverActions.P_FIND;
            m_PhaseAge = 0;
            m_Ray = 0;
        }
        if (m_Phase == HCDriverActions.P_FIND)
        {
            if (ScanStep(m_Name, player, m_Main))
            {
                walker.Release(player);
                StartAction(player, m_Action, m_Target, m_Main);
                return HCDriverResult.RUNNING;
            }
            if (m_InReachOnly)
            {
                if (m_Ray < HCDriverActions.RAYS) { return HCDriverResult.RUNNING; }
                return Finish(HCDriverResult.REFUSED, "no-door-in-reach");
            }
            if (!m_Approach) { return Finish(HCDriverResult.REFUSED, "candidate-gone"); }
            if (!walker.IsActive()) { walker.Begin(m_Approach.GetPosition()[0], m_Approach.GetPosition()[2], "walk", 2.0, 60); }
            int walked = walker.Update(player, m_Dt);
            if (walked == HCDriverResult.RUNNING) { return walked; }
            if (m_Ray < HCDriverActions.RAYS) { return HCDriverResult.RUNNING; }
            return Finish(HCDriverResult.REFUSED, "no-target-in-reach:" + m_Approach.GetType());
        }
        int settled = Settle(player, manager, m_Dt);
        if (settled == HCDriverResult.OK && m_Name == "close_door" && m_Stage == 0) { return settled; }
        return settled;
    }
}
