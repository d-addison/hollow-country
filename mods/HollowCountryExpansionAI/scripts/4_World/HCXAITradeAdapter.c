// HC-35 trade port for the Expansion AI addon (wave 16). Original code; Expansion
// is read, never copied. Trade is AI-to-AI only: both parties are pre-bound HC-10
// leases whose transient site patrols this addon already qualified. No player,
// no minted cargo, no teleport, no commanded route.
// Native/Expansion citations (installed sources, inspected locally):
// 3_Game/Systems/Inventory/Inventory.c:127 EnumerateInventory; 3_Game/gameplay.c:5
// InventoryTraversalType.PREORDER; eAIGroup.c:1139 GetMember, :1185 Count;
// DayZPlayerImplement.c:234 GetGroup; eAIBase.c:10860/10867 Expansion_SetEmote /
// Expansion_PlayEmote (void; the callback serial in HCXEmoteObservation observes it);
// 3_Game/constants.c:368 ID_EMOTE_GREETING; 3_Game/Entities/Man.c:21 GetIdentity.
// Bound by the modded HCXAIAdapter below (same start/stop as the other addon ports).
// Evidence wording: the emote acknowledgement is admitted UNVERIFIED (server-side
// emote callback counted on both actors; no client ack). The walking rendezvous has
// no surveyed route, so the adapter trades only when the two parties are already
// within the recipe's transfer range; otherwise it logs TRADE_RENDEZVOUS_ROUTE_UNSURVEYED
// once and declines. No unsurveyed route is ever commanded. runtime=PENDING.
class HCXAITradeAdapter : HCTradeInventory
{
    protected ref HCTradeGestureGate m_Gestures = new HCTradeGestureGate();
    protected bool m_RouteNoted;

    protected bool HCDirectorRuns()
    {
        HCXAISiteDirector director = HCXAISiteDirector.Active();
        if (!director || director.Phase() != "run") { return false; }
        return HCXAIQualification.EncountersEnabled();
    }

    // The qualified live patrol group a funded lease already owns.
    protected eAIGroup HCLeaseGroup(string lease)
    {
        HCXAISiteDirector director = HCXAISiteDirector.Active();
        if (!director) { return null; }
        array<ref HCXAISiteState> states = director.States();
        foreach (HCXAISiteState state : states)
        {
            if (!state || !state.Transient || state.ProposalId != lease) { continue; }
            if (!state.Qualified || state.Failed || !state.Patrol || !state.Patrol.m_HCLive) { continue; }
            return state.Patrol.m_Group;
        }
        return null;
    }

    // First existing item of this class an actor carries, scanning at most the
    // recipe's named InventoryScanLimit entries. Nothing is created or moved.
    protected ItemBase HCCarried(eAIBase actor, string itemClass)
    {
        array<EntityAI> held = new array<EntityAI>();
        actor.GetInventory().EnumerateInventory(InventoryTraversalType.PREORDER, held);
        int limit = held.Count();
        if (limit > Recipe.InventoryScanLimit) { limit = Recipe.InventoryScanLimit; }
        for (int index = 0; index < limit; index++)
        {
            ItemBase candidate = ItemBase.Cast(held[index]);
            if (candidate && candidate.GetType() == itemClass && !candidate.IsRuined()) { return candidate; }
        }
        return null;
    }

    protected eAIBase HCHolder(string lease, string itemClass, out ItemBase found)
    {
        found = null;
        eAIGroup group = HCLeaseGroup(lease);
        if (!group) { return null; }
        int count = group.Count();
        if (count < 1 || count > HCAILimits.SIZE_CEILING) { return null; }
        for (int member = 0; member < count; member++)
        {
            eAIBase actor = eAIBase.Cast(group.GetMember(member));
            if (!actor || !actor.IsAlive() || actor.GetIdentity()) { continue; }
            found = HCCarried(actor, itemClass);
            if (found) { return actor; }
        }
        return null;
    }

    override bool HCReady() { return HCDirectorRuns(); }
    override string HCRefusal() { return "TRADE_SITE_DIRECTOR_NOT_RUNNING"; }

    override bool HCBind(HCTradeState row)
    {
        HCClear();
        m_Gestures.HCReset();
        m_RouteNoted = false;
        if (!row || !Recipe || !HCReady()) { return false; }
        ItemBase leftFound;
        ItemBase rightFound;
        eAIBase leftHolder = HCHolder(row.LeftLease, Recipe.LeftClass, leftFound);
        eAIBase rightHolder = HCHolder(row.RightLease, Recipe.RightClass, rightFound);
        if (!leftHolder || !rightHolder || leftHolder == rightHolder) { return false; }
        LeftActor = leftHolder;
        RightActor = rightHolder;
        LeftItem = leftFound;
        RightItem = rightFound;
        if (HCInventoryBound(row)) { return true; }
        HCClear();
        return false;
    }

    override bool HCBeginWalk(HCTradeState row)
    {
        if (HCAtMeeting()) { return true; }
        if (!m_RouteNoted)
        {
            m_RouteNoted = true;
            Print("[HC Plan] HC-35 adapter trade=ai_only walk=declined refusal=TRADE_RENDEZVOUS_ROUTE_UNSURVEYED parties_not_within_transfer_range runtime=PENDING");
        }
        return false;
    }

    protected void HCRequestGreeting(eAIBase actor)
    {
        if (!actor || !actor.GetEmoteManager()) { return; }
        actor.RaiseWeapon(false);
        if (!actor.GetEmoteManager().CanPlayEmote(EmoteConstants.ID_EMOTE_GREETING)) { return; }
        actor.Expansion_SetEmote(EmoteConstants.ID_EMOTE_GREETING, true, 1500);
        actor.Expansion_PlayEmote();
    }

    // Both actors must advance their server emote-callback serial after the baseline
    // taken at arming. A request alone is never an observation; requests are capped
    // by the recipe's GestureRequests. Client acknowledgement is not consulted.
    override bool HCObservedGestures(HCTradeState row)
    {
        eAIBase left = eAIBase.Cast(LeftActor);
        eAIBase right = eAIBase.Cast(RightActor);
        if (!row || !left || !right || !left.GetEmoteManager() || !right.GetEmoteManager()) { return false; }
        string key = HCTradeGestureGate.HCKey(row);
        if (!m_Gestures.HCArmedFor(key))
        {
            m_Gestures.HCArm(key, left.GetEmoteManager().HCSignalSerial(), right.GetEmoteManager().HCSignalSerial(), Recipe.GestureRequests);
        }
        if (m_Gestures.HCObserved(left.GetEmoteManager().HCSignalSerial(), right.GetEmoteManager().HCSignalSerial())) { return true; }
        if (m_Gestures.HCTakeRequest())
        {
            HCRequestGreeting(left);
            HCRequestGreeting(right);
        }
        return m_Gestures.HCObserved(left.GetEmoteManager().HCSignalSerial(), right.GetEmoteManager().HCSignalSerial());
    }
}

// Binds the trade port and the HC-37 combat port with the addon's other ports.
// Locals, not `new X` arguments (native compiler trap). A rejected/replaced owner
// never binds or clears the live owner's ports.
modded class HCXAIAdapter
{
    protected ref HCXFactionCombatAdapter m_HCCombatPort;

    override void OnStart(HCSettings settings)
    {
        super.OnStart(settings);
        if (!GetGame() || !GetGame().IsServer()) { return; }
        if (HCXAIService.Adapter() == this)
        {
            HCXAITradeAdapter tradePort = new HCXAITradeAdapter();
            HCAITrade.HCBindProvider(tradePort);
            m_HCCombatPort = new HCXFactionCombatAdapter();
            HCXFactionCombatAdapter combatPort = m_HCCombatPort;
            HCFactionConflict.HCInstallCombatPort(combatPort);
        }
    }

    override void OnStop()
    {
        if (HCXAIService.Adapter() == this)
        {
            HCAITrade.HCBindProvider(null);
            HCFactionConflict.HCRemoveCombatPort(m_HCCombatPort);
            m_HCCombatPort = null;
        }
        super.OnStop();
    }
}
