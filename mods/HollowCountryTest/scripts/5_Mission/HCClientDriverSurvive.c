// Dev-only test addon (never shipped). Bandage, drink and eat for the scripted client driver (kind
// survive). Reads only what the client shows the player (the bleeding indicator and the HUD's water
// and energy tendencies) and uses the item's own vanilla continuous action, as holding the left
// mouse button with the item in hands does. Nothing is set, healed or counted by the driver.
// Native scripts-1.30.164289 proofs:
//  needs    4_World/Entities/ManBase/PlayerBase.c:1066 IsBleeding (synced bits); HCDriverVitals
//           (HCClientDriverCombat.c: VirtualHud DELM_TDCY_WATER / DELM_TDCY_ENERGY tendency and
//           seriousness, DisplayStatus.c:96, DisplayElementTendency.c:3-27, DisplayStatus.c:1-8 DSLevels).
//  items    ItemBase/BandageDressing.c:1, Rag.c:1; Edible_Base.c:1, Edible_Base/Bottle_Base.c:7,
//           Gear/Drinks/SodaCan_ColorBase.c:1; ItemBase.c:3490 GetQuantity (synced, the proof that a
//           sip or bite happened server-side); Man.c:178 PredictiveTakeEntityToHands.
//  action   3_Game/Entities/Object.c:1230 / ItemBase.c:235 GetActions(ContinuousDefaultActionInput)
//           (ActionInput.c:627), the item's own list: Medical/ActionBandageSelf.c:15 (condition
//           IsBleeding, CCTSelf), ActionDrink.c:9, ActionEat.c:9-64, ActionConsume.c:20
//           (CanEatAndDrink, CanConsumeFood, CanBeConsumed); ActionBase.c:968 Can;
//           ActionManagerClient.c:804 PerformActionStart, :1335 SetIgnoreAutomaticInputEnd, :286
//           EndActionInput (releasing the button after a few seconds of eating or drinking).
// Bounded: at most three tasks, each with an 8 s hand-over and a 30 s (bandage) or 8 s (eat, drink)
// action cap; a short inventory walk per task; nothing allocated per frame.
class HCDriverSurvive
{
    static const int T_BLEED = 0;
    static const int T_WATER = 1;
    static const int T_FOOD = 2;
    static const int T_DONE = 3;
    static const int S_FIND = 0;
    static const int S_HOLD = 1;
    static const int S_RUN = 2;
    static const float HOLD_SECONDS = 8.0;
    static const float CONSUME_SECONDS = 8.0;
    static const float BANDAGE_SECONDS = 30.0;

    protected bool m_Always;
    protected float m_Timeout;
    protected float m_Elapsed;
    protected int m_Task;
    protected int m_Stage;
    protected float m_StageAge;
    protected float m_HandsRetry;
    protected ItemBase m_Item;
    protected float m_QuantityBefore;
    protected bool m_SawRunning;
    protected float m_EndAge;
    protected bool m_Needed;
    protected int m_Bandaged;
    protected int m_Ate;
    protected int m_Drank;
    protected string m_Missing;
    protected ref ActionTarget m_Target;
    protected ref array<EntityAI> m_Inventory = new array<EntityAI>;
    protected string m_Detail;

    string Detail()
    {
        return m_Detail;
    }

    void Begin(HCDriverStep step)
    {
        m_Always = step.mode == "always";
        m_Timeout = Math.Max(step.timeout_s, 10.0);
        m_Elapsed = 0;
        m_Task = HCDriverSurvive.T_BLEED;
        m_Stage = HCDriverSurvive.S_FIND;
        m_StageAge = 0;
        m_Item = null;
        m_QuantityBefore = 0;
        m_SawRunning = false;
        m_Needed = false;
        m_Bandaged = 0;
        m_Ate = 0;
        m_Drank = 0;
        m_Missing = "";
        m_Detail = "";
    }

    protected string Tally()
    {
        string missing = m_Missing;
        if (missing == "") { missing = "none"; }
        return "bandaged=" + m_Bandaged.ToString() + " ate=" + m_Ate.ToString() + " drank=" + m_Drank.ToString() + " missing=" + missing;
    }

    protected int End(PlayerBase player, int code, string prefix)
    {
        if (player)
        {
            ActionManagerClient manager = ActionManagerClient.Cast(player.GetActionManager());
            if (manager)
            {
                manager.SetIgnoreAutomaticInputEnd(false);
                if (manager.GetRunningAction()) { manager.EndActionInput(); }
            }
        }
        m_Detail = prefix + Tally();
        return code;
    }

    protected bool Needs(PlayerBase player, int task)
    {
        if (task == HCDriverSurvive.T_BLEED) { return player.IsBleeding(); }
        eDisplayElements element = eDisplayElements.DELM_TDCY_ENERGY;
        if (task == HCDriverSurvive.T_WATER) { element = eDisplayElements.DELM_TDCY_WATER; }
        if (m_Always) { return true; }
        if (HCDriverVitals.Tendency(player, element) < 0) { return true; }
        return HCDriverVitals.Seriousness(player, element) >= DSLevels.WARNING;
    }

    protected bool Fits(ItemBase item, int task)
    {
        if (task == HCDriverSurvive.T_BLEED) { return item.IsKindOf("BandageDressing") || item.IsKindOf("Rag"); }
        bool drink = false;
        if (Bottle_Base.Cast(item) || SodaCan_ColorBase.Cast(item)) { drink = true; }
        if (task == HCDriverSurvive.T_WATER) { return drink && item.GetQuantity() > 0; }
        if (drink || !Edible_Base.Cast(item)) { return false; }
        // Medical edibles (tablets, disinfectant) are not a meal.
        if (item.IsKindOf("DisinfectantSpray") || item.IsKindOf("DisinfectantAlcohol") || item.IsKindOf("TetracyclineAntibiotics") || item.IsKindOf("CharcoalTablets")) { return false; }
        return item.GetQuantity() > 0;
    }

    protected ItemBase Find(PlayerBase player, int task)
    {
        ItemBase held = player.GetItemInHands();
        if (held && !held.IsRuined() && Fits(held, task)) { return held; }
        m_Inventory.Clear();
        player.GetInventory().EnumerateInventory(InventoryTraversalType.PREORDER, m_Inventory);
        for (int index = 0; index < m_Inventory.Count(); index++)
        {
            ItemBase item = ItemBase.Cast(m_Inventory[index]);
            if (!item || item.IsPendingDeletion() || item.IsRuined()) { continue; }
            if (item.GetInventory() && item.GetInventory().IsAttachment()) { continue; }
            if (Fits(item, task)) { return item; }
        }
        return null;
    }

    // The item's own continuous (hold left mouse) action that may run now; null when none.
    protected ActionBase UsableAction(PlayerBase player, ItemBase item)
    {
        array<ActionBase_Basic> actions;
        item.GetActions(ContinuousDefaultActionInput, actions);
        if (!actions) { return null; }
        // A self action has no target object; one target serves every task.
        if (!m_Target) { m_Target = new ActionTarget(null, null, -1, vector.Zero, -1.0); }
        for (int index = 0; index < actions.Count(); index++)
        {
            ActionBase action = ActionBase.Cast(actions[index]);
            if (action && action.Can(player, m_Target, item)) { return action; }
        }
        return null;
    }

    protected string TaskName(int task)
    {
        if (task == HCDriverSurvive.T_BLEED) { return "bandage"; }
        if (task == HCDriverSurvive.T_WATER) { return "drink"; }
        return "food";
    }

    protected void Miss(string reason)
    {
        if (m_Missing == "") { m_Missing = reason; }
        else { m_Missing = m_Missing + "," + reason; }
    }

    protected void Next()
    {
        m_Task++;
        m_Stage = HCDriverSurvive.S_FIND;
        m_StageAge = 0;
        m_Item = null;
    }

    protected void Credit(PlayerBase player)
    {
        if (m_Task == HCDriverSurvive.T_BLEED)
        {
            if (!player.IsBleeding()) { m_Bandaged = 1; }
            else { Miss("still-bleeding"); }
            return;
        }
        bool consumed = !m_Item || m_Item.IsPendingDeletion() || m_Item.GetQuantity() < m_QuantityBefore;
        if (!consumed)
        {
            Miss(TaskName(m_Task) + "-not-consumed");
            return;
        }
        if (m_Task == HCDriverSurvive.T_WATER) { m_Drank = 1; }
        else { m_Ate = 1; }
    }

    int Tick(PlayerBase player, float dt)
    {
        if (!player || !player.IsAlive() || player.IsUnconscious()) { return End(player, HCDriverResult.REFUSED, "player-unavailable "); }
        if (player.IsRestrained()) { return End(player, HCDriverResult.REFUSED, "restrained "); }
        ActionManagerClient manager = ActionManagerClient.Cast(player.GetActionManager());
        if (!manager) { return End(player, HCDriverResult.UNSUPPORTED, "no-client-action-manager "); }
        m_Elapsed = m_Elapsed + dt;
        m_StageAge = m_StageAge + dt;
        if (m_Elapsed > m_Timeout) { return End(player, HCDriverResult.TIMEOUT, TaskName(m_Task) + "-stage=" + m_Stage.ToString() + " "); }
        if (m_Task >= HCDriverSurvive.T_DONE)
        {
            int done = m_Bandaged + m_Ate + m_Drank;
            if (done > 0) { return End(player, HCDriverResult.OK, ""); }
            if (!m_Needed) { return End(player, HCDriverResult.OK, "nothing-needed "); }
            return End(player, HCDriverResult.REFUSED, "none-done ");
        }
        if (m_Stage == HCDriverSurvive.S_FIND)
        {
            if (manager.GetRunningAction()) { return HCDriverResult.RUNNING; }
            if (!Needs(player, m_Task))
            {
                Next();
                return HCDriverResult.RUNNING;
            }
            m_Needed = true;
            m_Item = Find(player, m_Task);
            if (!m_Item)
            {
                Miss("no-" + TaskName(m_Task));
                Next();
                return HCDriverResult.RUNNING;
            }
            HCDriverActions.RequestHands(player, m_Item);
            m_HandsRetry = 1.0;
            m_Stage = HCDriverSurvive.S_HOLD;
            m_StageAge = 0;
            return HCDriverResult.RUNNING;
        }
        if (!m_Item)
        {
            Miss(TaskName(m_Task) + "-gone");
            Next();
            return HCDriverResult.RUNNING;
        }
        if (m_Stage == HCDriverSurvive.S_HOLD)
        {
            if (player.GetItemInHands() != m_Item)
            {
                if (m_StageAge >= m_HandsRetry && m_StageAge < HCDriverSurvive.HOLD_SECONDS)
                {
                    m_HandsRetry = m_StageAge + 1.0;
                    HCDriverActions.RequestHands(player, m_Item);
                }
                if (m_StageAge < HCDriverSurvive.HOLD_SECONDS) { return HCDriverResult.RUNNING; }
                Miss(TaskName(m_Task) + "-not-in-hands");
                Next();
                return HCDriverResult.RUNNING;
            }
            ActionBase action = UsableAction(player, m_Item);
            if (!action)
            {
                if (m_StageAge < 1.5) { return HCDriverResult.RUNNING; }
                Miss(TaskName(m_Task) + "-not-allowed");
                Next();
                return HCDriverResult.RUNNING;
            }
            m_QuantityBefore = m_Item.GetQuantity();
            manager.SetIgnoreAutomaticInputEnd(true);
            manager.PerformActionStart(action, m_Target, m_Item);
            m_SawRunning = false;
            m_EndAge = 0;
            m_Stage = HCDriverSurvive.S_RUN;
            m_StageAge = 0;
            return HCDriverResult.RUNNING;
        }
        // S_RUN: a bandage repeats until the bleeding stops; a meal or a drink is a few seconds of
        // holding the button, then the button is released (EndActionInput).
        float cap = HCDriverSurvive.CONSUME_SECONDS;
        if (m_Task == HCDriverSurvive.T_BLEED) { cap = HCDriverSurvive.BANDAGE_SECONDS; }
        if (manager.GetRunningAction())
        {
            m_SawRunning = true;
            if (m_StageAge < cap) { return HCDriverResult.RUNNING; }
            manager.EndActionInput();
            return HCDriverResult.RUNNING;
        }
        if (!m_SawRunning && m_StageAge < 1.5) { return HCDriverResult.RUNNING; }
        // Give the synced quantity and bleeding bits a moment to arrive before crediting.
        m_EndAge = m_EndAge + dt;
        if (m_EndAge < 1.5) { return HCDriverResult.RUNNING; }
        manager.SetIgnoreAutomaticInputEnd(false);
        if (!m_SawRunning) { Miss(TaskName(m_Task) + "-not-started"); }
        else { Credit(player); }
        Next();
        return HCDriverResult.RUNNING;
    }
}
