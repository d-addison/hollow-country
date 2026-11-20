// #256: server-owned visual affiliation, within the existing sites lifecycle.
// Native 1.30.164289: EntityAI.FindAttachmentBySlotName/SetTakeable;
// GameInventory.CreateAttachment; Game.CreateObjectEx/ObjectDelete/SurfaceY;
// StaticFlagPole.FullyBuild; TerritoryFlag.AnimateFlagEx; CentralEconomy.c
// ECE_NOPERSISTENCY_WORLD/CHAR. Installed Expansion eAIDynamicPatrol calls
// SetupAI after loadout application; patrol m_Faction is the resolved identity.
modded class HCXAISiteState
{
    StaticFlagPole HCAffiliationPole;
    bool HCAffiliationAttempted;
}

// FullyBuild normally spawns a loose construction kit. Suppress that only for
// our scenery, and keep its decorative flag out of the loot economy. Ordinary
// vanilla/editor poles retain native behaviour. No storage hooks or refresh time.
modded class StaticFlagPole
{
    bool HCAffiliationMarker;

    override ItemBase CreateConstructionKit()
    {
        if (HCAffiliationMarker) { return null; }
        return super.CreateConstructionKit();
    }

    override void AnimateFlagEx(float delta, PlayerBase player = null)
    {
        if (HCAffiliationMarker && player) { return; }
        super.AnimateFlagEx(delta, player);
    }

    override void AddRefresherTime01(float fraction)
    {
        if (HCAffiliationMarker) { return; }
        super.AddRefresherTime01(fraction);
    }

    override bool CanReleaseAttachment(EntityAI attachment)
    {
        if (HCAffiliationMarker) { return false; }
        return super.CanReleaseAttachment(attachment);
    }
}

class HCXAffiliationCues
{
    protected int m_Cursor;
    protected ref array<ref HCXAISiteState> m_Marked = new array<ref HCXAISiteState>();
    protected int m_CleanupCursor;
    static const int MAX_POLES = 16;

    static string Armband(string faction)
    {
        if (faction == "Locals") { return "Armband_Green"; }
        if (faction == "Volunteers") { return "Armband_Blue"; }
        if (faction == "Scavengers") { return "Armband_Yellow"; }
        if (faction == "Raiders") { return "Armband_Red"; }
        if (faction == "Travellers") { return "Armband_White"; }
        return "";
    }

    static string Flag(string faction)
    {
        if (faction == "Locals") { return "Flag_NAPA"; }
        if (faction == "Volunteers") { return "Flag_CDF"; }
        if (faction == "Scavengers") { return "Flag_Bear"; }
        if (faction == "Raiders") { return "Flag_Chedaki"; }
        if (faction == "Travellers") { return "Flag_White"; }
        return "";
    }

    static void Actor(eAIBase ai, eAIFaction faction)
    {
        if (!GetGame().IsServer() || !ai || !faction || !ai.GetInventory()) { return; }
        string wanted = Armband(HCXFactions.Id(faction));
        if (wanted == "") { return; }
        ai.HCWarningActor = true;
        EntityAI existing = ai.FindAttachmentBySlotName("Armband");
        if (existing && existing.GetType() == wanted) { return; }
        // This hook runs only at spawn, after the provider's role loadout.
        if (existing) { GetGame().ObjectDelete(existing); }
        EntityAI made = ai.GetInventory().CreateAttachment(wanted);
        if (!made) { Print("[HC AI cues] armband attachment refused class=" + wanted + " runtime=PENDING"); }
    }

    void Step(array<ref HCXAISiteState> states, HCXAISiteDirector director)
    {
        if (!states || states.Count() == 0 || !director) { return; }
        // Rotation can remove a state before its normal cursor visit. Retain
        // at most MAX_POLES owners and check one retired owner per tick.
        if (m_Marked.Count() > 0)
        {
            if (m_CleanupCursor >= m_Marked.Count()) { m_CleanupCursor = 0; }
            HCXAISiteState retired = m_Marked[m_CleanupCursor];
            m_CleanupCursor++;
            if (states.Find(retired) < 0 || !retired.Patrol || !retired.Patrol.m_Group || retired.Patrol.m_Group.Count() == 0) { this.Remove(retired); }
        }
        if (m_Cursor >= states.Count()) { m_Cursor = 0; }
        HCXAISiteState state = states[m_Cursor];
        m_Cursor++;
        if (!state || state.Transient) { return; }
        HCXAISitePatrol patrol = state.Patrol;
        bool occupied = patrol && patrol.m_Group && patrol.m_Group.Count() > 0;
        if (!occupied)
        {
            this.Remove(state);
            return;
        }
        if (state.HCAffiliationAttempted || m_Marked.Count() >= MAX_POLES) { return; }
        string flagClass = Flag(HCXFactions.Id(patrol.m_Group.GetFaction()));
        if (flagClass == "") { return; }
        vector anchor = patrol.m_Position;
        if (state.HouseObject) { anchor = state.HouseObject.GetPosition(); }
        vector at = anchor + Vector(8, 0, 8);
        at[1] = GetGame().SurfaceY(at[0], at[2]);
        // No scenery pop-in near an observer. Never move an existing actor.
        if (director.NearestPlayer(at) < 200 || director.SeenByPlayer(at)) { return; }
        state.HCAffiliationAttempted = true;
        array<Object> nearby = new array<Object>();
        array<CargoBase> cargos = new array<CargoBase>();
        GetGame().GetObjectsAtPosition(at, 3, nearby, cargos);
        if (nearby.Count() > 64) { return; }
        foreach (Object obstacle : nearby)
        {
            // Conservative door/building veto; do not force a pole through a site.
            if (obstacle && House.Cast(obstacle)) { return; }
        }
        Object placed = GetGame().CreateObjectEx("StaticFlagPole", at, ECE_SETUP | ECE_KEEPHEIGHT | ECE_NOLIFETIME | ECE_NOPERSISTENCY_WORLD | ECE_NOPERSISTENCY_CHAR);
        StaticFlagPole pole = StaticFlagPole.Cast(placed);
        if (!pole)
        {
            if (placed) { GetGame().ObjectDelete(placed); }
            return;
        }
        HCGroundSnap.Snap(pole);
        pole.HCAffiliationMarker = true;
        pole.SetAllowDamage(false);
        pole.FullyBuild();
        EntityAI banner = pole.GetInventory().CreateAttachment(flagClass);
        if (!banner) { GetGame().ObjectDelete(pole); return; }
        banner.SetTakeable(false);
        pole.AnimateFlagEx(0);
        state.HCAffiliationPole = pole;
        m_Marked.Insert(state);
        Print("[HC AI cues] site=" + state.Site.Id + " flag=" + flagClass + " runtime=PENDING");
    }

    protected void Remove(HCXAISiteState state)
    {
        if (state.HCAffiliationPole) { GetGame().ObjectDelete(state.HCAffiliationPole); }
        state.HCAffiliationPole = null;
        state.HCAffiliationAttempted = false;
        m_Marked.RemoveItem(state);
    }

    void Stop()
    {
        while (m_Marked.Count() > 0)
        {
            HCXAISiteState state = m_Marked[0];
            this.Remove(state);
        }
        m_Cursor = 0;
        m_CleanupCursor = 0;
    }
}

// Charge work to the existing director's slot; the helper is not a second
// consumer. Keep the owned site file's hooks additive and limited to calls.
modded class HCXAISiteDirector
{
    protected ref HCXAffiliationCues m_HCAffiliationCues = new HCXAffiliationCues();

    override void Step()
    {
        super.Step();
        if (!GetGame() || !GetGame().IsServer() || m_Phase != "run") { return; }
        if (!HCServer.HCTickWork().HCTakeAISlice(HCUnitBudget.HC_AI_CUES, HCUnitBudget.HC_WORK_AI_SITES, 2)) { return; }
        m_HCAffiliationCues.Step(m_States, this);
    }

    override void Stop()
    {
        m_HCAffiliationCues.Stop();
        super.Stop();
    }
}
