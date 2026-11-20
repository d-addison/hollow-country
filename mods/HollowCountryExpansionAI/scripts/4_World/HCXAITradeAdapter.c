// Explicit bounded DFS frames: one child/candidate per charged work unit,
// rather than EnumerateInventory doing an unbounded native traversal first.
// Native Inventory.c:138 GetCargo, :205 AttachmentCount, :220
// GetAttachmentFromIndex; Cargo.c:28/32 GetItemCount/GetItem;
// Entities/Man.c:81 GetHumanInventory; HumanInventory.c:16 GetEntityInHands; inherited EntityAI.c:1884 GetInventory.
class HCXTradeInventoryFrame
{
    EntityAI NodeEntity;
    int Attachment;
    int CargoIndex;
    bool Checked;
}
class HCXTradeInventoryScan
{
    eAIBase Actor;
    string Wanted;
    string Lease;
    ItemBase Found;
    int Visited;
    bool Complete;
    ref array<ref HCXTradeInventoryFrame> Frames = new array<ref HCXTradeInventoryFrame>;

    void HCStart(eAIBase actor, string wanted)
    {
        Actor = actor; Wanted = wanted;
        HCXTradeInventoryFrame root = new HCXTradeInventoryFrame;
        root.NodeEntity = actor;
        Frames.Insert(root);
        EntityAI hands = actor.GetHumanInventory().GetEntityInHands();
        if (hands)
        {
            HCXTradeInventoryFrame held = new HCXTradeInventoryFrame;
            held.NodeEntity = hands;
            Frames.Insert(held);
        }
    }
    void HCRetire()
    {
        Complete = true;
        Actor = null; Found = null;
        Frames.Clear();
    }
    ItemBase HCStep(int limit)
    {
        if (!Actor || !Actor.IsAlive()) { HCRetire(); return null; }
        if (Found && Found.GetHierarchyRootPlayer() == Actor && !Found.IsRuined()) { return Found; }
        Found = null;
        if (Complete) { return null; }
        while (Frames.Count() > 0 && Visited < limit)
        {
            if (!HCServer.HCTickWork().HCTakeFor(HCUnitBudget.HC_WORK_TRADE, 1)) { return null; }
            HCXTradeInventoryFrame frame = Frames[Frames.Count() - 1];
            EntityAI entity = frame.NodeEntity;
            if (!entity) { Frames.RemoveOrdered(Frames.Count() - 1); continue; }
            if (!frame.Checked)
            {
                frame.Checked = true;
                Visited++;
                ItemBase candidate = ItemBase.Cast(entity);
                if (candidate && candidate.GetType() == Wanted && !candidate.IsRuined() && candidate.GetHierarchyRootPlayer() == Actor) { Found = candidate; return Found; }
                continue;
            }
            EntityAI child;
            if (frame.Attachment < entity.GetInventory().AttachmentCount())
            {
                child = entity.GetInventory().GetAttachmentFromIndex(frame.Attachment);
                frame.Attachment++;
            }
            else
            {
                CargoBase cargo = entity.GetInventory().GetCargo();
                if (cargo && frame.CargoIndex < cargo.GetItemCount())
                {
                    child = cargo.GetItem(frame.CargoIndex);
                    frame.CargoIndex++;
                }
                else { Frames.RemoveOrdered(Frames.Count() - 1); continue; }
            }
            if (child && Frames.Count() < limit)
            {
                HCXTradeInventoryFrame nextFrame = new HCXTradeInventoryFrame;
                nextFrame.NodeEntity = child;
                Frames.Insert(nextFrame);
            }
        }
        Complete = true;
        return null;
    }
}

// HC-35 trade port for the Expansion AI addon (wave 16). Original code; Expansion
// is read, never copied. Trade is AI-to-AI only: both parties are pre-bound HC-10
// leases whose transient site patrols this addon already qualified. No player,
// no minted cargo or teleport. The producer supplies a bounded installed-road route.
// Native/Expansion citations (installed sources, inspected locally):
// 3_Game/Systems/Inventory/Inventory.c:127 EnumerateInventory; 3_Game/gameplay.c:5
// InventoryTraversalType.PREORDER; eAIGroup.c:1139 GetMember, :1185 Count;
// DayZPlayerImplement.c:234 GetGroup; eAIBase.c:10860/10867 Expansion_SetEmote /
// Expansion_PlayEmote (void; the callback serial in HCXEmoteObservation observes it);
// eAIBase.c:9755 RaiseWeapon; native PlayerBase.c:1892 GetEmoteManager;
// Classes/EmoteManager.c:1026 CanPlayEmote; 3_Game/constants.c:368
// ID_EMOTE_GREETING; 3_Game/Entities/Man.c:21 GetIdentity.
// Bound by the modded HCXAIAdapter below (same start/stop as the other addon ports).
// Greeting acknowledgements read HCSignalGreetingSerial + HCSignalGesture from HC-5;
// native/two-client acceptance remains pending. The producer supplies a funded
// road plan; an unsolicited distant pair still declines with a named reason.
class HCXAITradeAdapter : HCTradeInventory
{
    protected ref HCTradeGestureGate m_Gestures = new HCTradeGestureGate();
    protected bool m_RouteNoted;
    protected ref array<ref HCXTradeInventoryScan> m_Scans = new array<ref HCXTradeInventoryScan>;
    ref HCXAICaravanAdapter Walker;
    HCXAITradeProducer Producer;
    string ProducerFault;
    string PlannedLeft;
    string PlannedRight;

    protected bool HCDirectorRuns()
    {
        HCXAISiteDirector director = HCXAISiteDirector.Active();
        if (!director || director.Phase() != "run") { return false; }
        return HCXAIQualification.EncountersEnabled();
    }

    // The qualified live patrol group a funded lease already owns.
    eAIGroup HCLeaseGroup(string lease)
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
    protected ItemBase HCCarried(eAIBase actor, string itemClass, string lease)
    {
        if (!actor || !Recipe) { return null; }
        array<ref HCXTradeInventoryScan> scans = m_Scans;
        foreach (HCXTradeInventoryScan scan : scans)
        {
            if (scan.Actor == actor && scan.Wanted == itemClass) { return scan.HCStep(Recipe.InventoryScanLimit); }
        }
        if (m_Scans.Count() >= HCAILimits.SIZE_CEILING * 2) { return null; }
        HCXTradeInventoryScan created = new HCXTradeInventoryScan;
        created.Lease = lease;
        created.HCStart(actor, itemClass);
        m_Scans.Insert(created);
        return created.HCStep(Recipe.InventoryScanLimit);
    }

    // Retire stale cursors even when HCHolder skips their dead/deleted actor.
    // GetGroup evidence: installed DayZPlayerImplement.c:234 (see above).
    void HCRetireInvalidScans()
    {
        array<ref HCXTradeInventoryScan> scans = m_Scans;
        foreach (HCXTradeInventoryScan scan : scans)
        {
            if (!scan.Actor || !scan.Actor.IsAlive()) { scan.HCRetire(); continue; }
            eAIGroup group = HCLeaseGroup(scan.Lease);
            if (!group || scan.Actor.GetGroup() != group) { scan.HCRetire(); }
        }
    }
    void HCResetScans()
    {
        array<ref HCXTradeInventoryScan> scans = m_Scans;
        foreach (HCXTradeInventoryScan scan : scans) { scan.HCRetire(); }
        m_Scans.Clear();
    }
    bool HCScansComplete()
    {
        HCRetireInvalidScans();
        if (m_Scans.Count() == 0) { return true; }
        array<ref HCXTradeInventoryScan> scans = m_Scans;
        foreach (HCXTradeInventoryScan scan : scans) { if (!scan.Complete && !scan.Found) { return false; } }
        return true;
    }

    eAIBase HCHolder(string lease, string itemClass, out ItemBase found)
    {
        found = null;
        HCRetireInvalidScans();
        eAIGroup group = HCLeaseGroup(lease);
        if (!group) { return null; }
        int count = group.Count();
        if (count < 1 || count > HCAILimits.SIZE_CEILING) { return null; }
        for (int member = 0; member < count; member++)
        {
            eAIBase actor = eAIBase.Cast(group.GetMember(member));
            if (!actor || !actor.IsAlive() || actor.GetIdentity()) { continue; }
            found = HCCarried(actor, itemClass, lease);
            if (found) { return actor; }
        }
        return null;
    }

    override string HCOperationalFault()
    {
        if (ProducerFault != "") { return ProducerFault; }
        HCXAICaravanRoads roads = HCXAICaravanRoads.HCGet();
        if (roads && roads.Phase == "failed") { return roads.Reason; }
        return "";
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
        if (Walker && row.LeftLease == PlannedLeft && Walker.LeftActor != LeftActor) { HCClear(); return false; }
        if (HCInventoryBound(row)) { return true; }
        HCClear();
        return false;
    }

    override bool HCBeginWalk(HCTradeState row)
    {
        if (Producer && !Producer.HCDepart(row)) { return false; }
        if (HCAtMeeting()) { return true; }
        if (row && Walker && row.LeftLease == PlannedLeft && row.RightLease == PlannedRight)
        {
            if (!Walker.HCHoldPartner(RightActor)) { return false; }
            if (Walker.HCRequest(false)) { return true; }
            Walker.HCReleasePartner();
            return false;
        }
        if (!m_RouteNoted)
        {
            m_RouteNoted = true;
            Print("[HC Plan] HC-35 adapter walk=waiting reason=TRADE_RENDEZVOUS_ROUTE_UNSURVEYED runtime=PENDING");
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

    protected bool HCNewGreetings(eAIBase left, eAIBase right)
    {
        if (left.GetEmoteManager().HCSignalGesture() != EmoteConstants.ID_EMOTE_GREETING || right.GetEmoteManager().HCSignalGesture() != EmoteConstants.ID_EMOTE_GREETING) { return false; }
        return m_Gestures.HCObserved(left.GetEmoteManager().HCSignalGreetingSerial(), right.GetEmoteManager().HCSignalGreetingSerial());
    }

    // Both actors must advance their server emote-callback serial after the baseline
    // taken at arming. A request alone is never an observation; requests are capped
    // by the recipe's GestureRequests. Client acknowledgement is not consulted.
    override bool HCObservedGestures(HCTradeState row)
    {
        eAIBase left = eAIBase.Cast(LeftActor);
        eAIBase right = eAIBase.Cast(RightActor);
        if (!row || !left || !right || !left.GetEmoteManager() || !right.GetEmoteManager()) { return false; }
        // Each side must see the other (fresh geometry); a greeting through a wall is not an exchange.
        if (!HCXStance.Visible(left, right) || !HCXStance.Visible(right, left)) { return false; }
        string key = HCTradeGestureGate.HCKey(row);
        if (!m_Gestures.HCArmedFor(key))
        {
            m_Gestures.HCArm(key, left.GetEmoteManager().HCSignalGreetingSerial(), right.GetEmoteManager().HCSignalGreetingSerial(), Recipe.GestureRequests);
        }
        if (HCNewGreetings(left, right)) { return true; }
        if (m_Gestures.HCTakeRequest())
        {
            HCRequestGreeting(left);
            HCRequestGreeting(right);
        }
        return HCNewGreetings(left, right);
    }
}

// Binds the trade port and the HC-37 combat port with the addon's other ports.
// Locals, not `new X` arguments (native compiler trap). A rejected/replaced owner
// never binds or clears the live owner's ports.
modded class HCXAIAdapter
{
    protected ref HCXFactionCombatAdapter m_HCCombatPort;
    protected ref HCXAITradeProducer m_HCTradeProducer;

    override void OnStart(HCSettings settings)
    {
        super.OnStart(settings);
        if (!GetGame() || !GetGame().IsServer()) { return; }
        if (HCXAIService.Adapter() == this)
        {
            HCXAITradeAdapter tradePort = new HCXAITradeAdapter();
            HCAITrade.HCBindProvider(tradePort);
            if (m_Caravan && m_Caravan.m_Enabled && m_Caravan.m_Corridor)
            {
                HCXAICaravanRoads.HCOpen(m_Caravan.m_Corridor);
                m_HCTradeProducer = new HCXAITradeProducer;
                m_HCTradeProducer.HCOpen(tradePort);
            }
            m_HCCombatPort = new HCXFactionCombatAdapter();
            HCXFactionCombatAdapter combatPort = m_HCCombatPort;
            HCFactionConflict.HCInstallCombatPort(combatPort);
        }
    }

    override void OnTick(float deltaTime)
    {
        super.OnTick(deltaTime);
        if (HCXAIService.Adapter() != this || !m_HCTradeProducer) { return; }
        m_HCTradeProducer.HCStep();
    }

    override void OnStop()
    {
        if (HCXAIService.Adapter() == this)
        {
            if (m_HCTradeProducer) { m_HCTradeProducer.HCClose(); m_HCTradeProducer = null; }
            HCXAICaravanRoads.HCClose();
            HCAITrade.HCBindProvider(null);
            HCFactionConflict.HCRemoveCombatPort(m_HCCombatPort);
            m_HCCombatPort = null;
        }
        super.OnStop();
    }
}

// #145 funded producer: one candidate pair per core tick, one physical exchange
// slot, infrequent successful departures. Uses the director's current HC-10
// claims and HC-16 detached funded views; never offers JSON identities/stock.
// Native calls reuse the inspected evidence above, plus Game.c:914 GetTickTime
// (through UTC clock), EntityAI.c:882 GetHierarchyRootPlayer, Object.c:517
// IsAlive. No native create, split, refund, loot reward or teleport call.
class HCXAITradeProducer
{
    ref HCXAITradeAdapter m_Port;
    ref HCTradeRecipe m_Recipe;
    ref HCTradeLossData m_Losses;
    ref HCEncounterStore<HCTradeLossData> m_Store;
    int m_LeftIndex;
    int m_RightIndex = 1;
    int m_LastOffer;
    int m_ReturnAt;
    string m_LeftLease;
    string m_RightLease;
    string m_LeftHome;
    string m_RightHome;
    string m_Refusal;
    string m_JourneyKey;
    bool m_Opened;
    bool m_Failed;
    bool m_Planning;
    bool m_Travelling;
    bool m_Returning;
    PlayerBase m_Carrier;
    PlayerBase m_Partner;
    ItemBase m_Outbound;
    ItemBase m_Inbound;

    void HCOpen(HCXAITradeAdapter port)
    {
        m_Port = port;
        port.Producer = this;
        Print("[HC Plan] HC-35 producer=started funded_pairs=bounded existing_cargo=only runtime=PENDING");
    }
    void HCRefuse(string reason)
    {
        if (m_Failed && m_Port) { m_Port.ProducerFault = reason; }
        if (m_Refusal == reason) { return; }
        m_Refusal = reason;
        Print("[HC Plan] HC-35 producer=waiting reason=" + reason + " runtime=PENDING");
    }
    bool HCLoad()
    {
        if (m_Failed) { return false; }
        if (m_Opened) { return true; }
        HCAITrade trade = HCAITrade.HCGet();
        if (!trade || !trade.HCRecipe()) { return false; }
        m_Recipe = trade.HCRecipe();
        m_Port.Recipe = m_Recipe;
        m_Store = new HCEncounterStore<HCTradeLossData>("hc35-caravan-losses");
        HCTradeLossData empty = new HCTradeLossData;
        m_Losses = m_Store.Load(empty, "Rows");
        if (!m_Losses || m_Losses.Version != 1 || !m_Losses.Rows || m_Losses.Rows.Count() > m_Recipe.MaxLossReceipts)
        {
            m_Failed = true; HCRefuse("TRADE_LOSS_STORE_INVALID"); return false;
        }
        array<ref HCTradeLossRow> receipts = m_Losses.Rows;
        map<string, bool> keys = new map<string, bool>();
        foreach (HCTradeLossRow receipt : receipts)
        {
            if (!receipt || !HCWorldLimits.Token(receipt.Key) || !HCWorldLimits.Token(receipt.LeftCamp) || !HCWorldLimits.Token(receipt.RightCamp) || receipt.LeftCamp == receipt.RightCamp || receipt.Debit < 1 || receipt.Debit > m_Recipe.MinimumCampReserve || (receipt.Phase != "complete" && receipt.Phase != "journey") || keys.Contains(receipt.Key))
            {
                m_Failed = true; HCRefuse("TRADE_LOSS_INTENT_RECONCILIATION_REQUIRED"); return false;
            }
            keys.Set(receipt.Key, true);
        }
        if (!HCRecoverJourneys()) { return false; }
        m_Opened = true;
        return true;
    }
    // Persist camp identities BEFORE movement. No transient actor/item handle
    // is a restart identity; an interrupted journey becomes a loss, never cargo.
    bool HCDepart(HCTradeState state)
    {
        if (!state || !m_Store || m_Failed) { return false; }
        string key = state.Id + ":" + state.StartedAt.ToString();
        if (m_JourneyKey == key) { return true; }
        if (m_Losses.Rows.Count() >= m_Recipe.MaxLossReceipts) { return false; }
        HCTradeLossRow journey = new HCTradeLossRow;
        journey.Key = key; journey.LeftCamp = m_LeftHome; journey.RightCamp = m_RightHome;
        journey.Debit = m_Recipe.LossSupplyDebit; journey.Phase = "journey";
        m_Losses.Rows.Insert(journey);
        if (!m_Store.Save(m_Losses)) { m_Failed = true; HCRefuse("TRADE_JOURNEY_WRITE_FAILED"); return false; }
        m_JourneyKey = key;
        return true;
    }
    bool HCRecordLoss(HCTradeLossRow loss)
    {
        if (loss.Phase == "complete") { return true; }
        if (loss.Phase == "journey") { loss.Phase = "new"; }
        HCTradeLossBarrier barrier = new HCTradeLossBarrier;
        barrier.m_Row = loss; barrier.m_Data = m_Losses;
        barrier.m_Store = m_Store; barrier.m_Ready = true;
        if (!barrier.HCApply()) { m_Failed = true; HCRefuse("TRADE_LOSS_INTENT_RECONCILIATION_REQUIRED"); return false; }
        Print("[HC Caravan] loss=recorded both_camps_debited=1 relationship=damaged_once cargo=physical_no_reward runtime=PENDING");
        return true;
    }
    bool HCRecoverJourneys()
    {
        array<ref HCTradeLossRow> receipts = m_Losses.Rows;
        int reconciled = 0;
        bool recovered = true;
        foreach (HCTradeLossRow journey : receipts)
        {
            if (journey.Phase != "journey") { continue; }
            HCHoldouts homes = HCHoldouts.Get();
            // Wait for the existing allocation owner before writing debit intent.
            if (!homes || !homes.HCTradeCanDebit(journey.LeftCamp, journey.RightCamp)) { recovered = false; break; }
            if (!HCRecordLoss(journey)) { recovered = false; break; }
            reconciled++;
        }
        // One summary line for every journey reconciled in this pass.
        if (reconciled > 0) { Print("[HC Caravan] restart=journey_loss_reconciled cargo_created=0 runtime=PENDING"); }
        return recovered;
    }
    bool HCSettleJourney()
    {
        if (m_JourneyKey == "") { return true; }
        int receiptIndex = m_Losses.Rows.Count() - 1;
        while (receiptIndex >= 0)
        {
            HCTradeLossRow receipt = m_Losses.Rows[receiptIndex];
            if (receipt.Key == m_JourneyKey && receipt.Phase == "journey") { m_Losses.Rows.RemoveOrdered(receiptIndex); }
            receiptIndex -= 1;
        }
        if (!m_Store.Save(m_Losses)) { m_Failed = true; HCRefuse("TRADE_JOURNEY_WRITE_FAILED"); return false; }
        m_JourneyKey = "";
        return true;
    }
    int HCRelationship(string leftCamp, string rightCamp, int factionRelation)
    {
        int relation = factionRelation;
        array<ref HCTradeLossRow> receipts = m_Losses.Rows;
        foreach (HCTradeLossRow receipt : receipts)
        {
            if (receipt.Phase != "complete") { continue; }
            if ((receipt.LeftCamp == leftCamp && receipt.RightCamp == rightCamp) || (receipt.LeftCamp == rightCamp && receipt.RightCamp == leftCamp)) { relation--; }
        }
        return relation;
    }
    void HCLoss(HCTradeState state)
    {
        if (!state || state.Id == "") { return; }
        bool exchanged = state.Phase == "complete" && state.Transfer == "reciprocal_confirmed";
        // Intent/quarantine cannot establish custody. Confirmed swaps reverse
        // the carrier's cargo; the delivered item is no longer caravan stock.
        if (!exchanged && state.Phase != "meeting" && state.Phase != "cancelled" && state.Phase != "rolled_back") { return; }
        // These were retained at departure. A deleted body/item is loss of
        // that established custody, never permission to reconstruct the cargo.
        bool lost = !m_Carrier || !m_Carrier.IsAlive();
        if (exchanged)
        {
            if (!m_Inbound) { lost = true; }
            else if (m_Inbound.IsRuined() || m_Inbound.GetQuantity() < state.RightQuantity || m_Inbound.GetHierarchyRootPlayer() != m_Carrier) { lost = true; }
        }
        else
        {
            if (!m_Partner || !m_Outbound || !m_Inbound) { lost = true; }
            else
            {
                if (!m_Partner.IsAlive() || m_Outbound.IsRuined() || m_Inbound.IsRuined()) { lost = true; }
                if (m_Outbound.GetQuantity() < state.LeftQuantity || m_Inbound.GetQuantity() < state.RightQuantity) { lost = true; }
                if (m_Outbound.GetHierarchyRootPlayer() != m_Carrier || m_Inbound.GetHierarchyRootPlayer() != m_Partner) { lost = true; }
            }
        }
        if (!lost) { return; }
        string key = state.Id + ":" + state.StartedAt.ToString();
        array<ref HCTradeLossRow> receipts = m_Losses.Rows;
        foreach (HCTradeLossRow prior : receipts) { if (prior.Key == key) { HCRecordLoss(prior); return; } }
        if (m_Losses.Rows.Count() >= m_Recipe.MaxLossReceipts) { m_Failed = true; HCRefuse("TRADE_LOSS_RECEIPT_CAP"); return; }
        HCTradeLossRow loss = new HCTradeLossRow;
        loss.Key = key; loss.LeftCamp = m_LeftHome; loss.RightCamp = m_RightHome;
        loss.Debit = m_Recipe.LossSupplyDebit;
        m_Losses.Rows.Insert(loss);
        HCRecordLoss(loss);
    }
    void HCNextPair(int count)
    {
        m_RightIndex++;
        if (m_RightIndex >= count) { m_LeftIndex++; m_RightIndex = m_LeftIndex + 1; }
        if (m_LeftIndex >= count - 1) { m_LeftIndex = 0; m_RightIndex = 1; }
    }
    void HCCandidate()
    {
        HCXAISiteDirector director = HCXAISiteDirector.Active();
        HCHoldouts camps = HCHoldouts.Get();
        HCWorldModule world = HCWorldModule.Get();
        HCXAICaravanRoads roads = HCXAICaravanRoads.HCGet();
        if (!director || director.Phase() != "run" || !camps || !world || !roads || roads.Phase != "idle") { return; }
        array<ref HCXAISiteState> states = director.States();
        int count = states.Count();
        if (count < 2) { return; }
        if (m_RightIndex >= count || m_LeftIndex >= count - 1) { m_LeftIndex = 0; m_RightIndex = 1; }
        if (!HCServer.HCTickWork().HCTakeFor(HCUnitBudget.HC_WORK_AI_TRADE_PRODUCER, 1)) { return; }
        HCXAISiteState left = states[m_LeftIndex];
        HCXAISiteState right = states[m_RightIndex];
        HCNextPair(count);
        if (!left || !right || !left.Transient || !right.Transient || !left.Qualified || !right.Qualified || left.Failed || right.Failed) { return; }
        eAIGroup leftGroup = m_Port.HCLeaseGroup(left.ProposalId);
        eAIGroup rightGroup = m_Port.HCLeaseGroup(right.ProposalId);
        if (!leftGroup || !rightGroup || leftGroup.Count() < m_Recipe.MinimumCampMembers || rightGroup.Count() < m_Recipe.MinimumCampMembers) { return; }
        HCAIPartyIdentity leftIdentity = HCWorldMaterializer.HCIdentity(left.ProposalId);
        HCAIPartyIdentity rightIdentity = HCWorldMaterializer.HCIdentity(right.ProposalId);
        HCAICampRoutineView leftHome = camps.HCRoutineView(leftIdentity);
        HCAICampRoutineView rightHome = camps.HCRoutineView(rightIdentity);
        if (!leftHome || !rightHome || !leftHome.Home || !rightHome.Home) { return; }
        int relation = HCRelationship(leftHome.Home.Id, rightHome.Home.Id, world.Relation(leftHome.Home.FactionId, rightHome.Home.FactionId));
        if (!HCTradeOfferPolicy.HCEligible(leftHome.Home.Id, rightHome.Home.Id, relation, leftHome.Supply, rightHome.Supply, m_Recipe.MinimumCampReserve)) { return; }
        // Retain a selected candidate while its inventory traversal yields.
        // Otherwise another actor could evict its work before deeper cargo was visited.
        m_LeftLease = left.ProposalId; m_RightLease = right.ProposalId;
        m_LeftHome = leftHome.Home.Id; m_RightHome = rightHome.Home.Id;
        m_Port.HCResetScans();
        m_Planning = true;
    }
    void HCPlan()
    {
        HCXAICaravanRoads roads = HCXAICaravanRoads.HCGet();
        if (!roads) { return; }
        if (!m_Port.HCLeaseGroup(m_LeftLease) || !m_Port.HCLeaseGroup(m_RightLease)) { HCClearTrip(); return; }
        if (m_Carrier && (!m_Carrier.IsAlive() || !m_Partner || !m_Partner.IsAlive())) { HCClearTrip(); return; }
        if (!m_Carrier)
        {
            ItemBase leftStock;
            ItemBase rightStock;
            eAIBase leftActor = m_Port.HCHolder(m_LeftLease, m_Recipe.LeftClass, leftStock);
            eAIBase rightActor = m_Port.HCHolder(m_RightLease, m_Recipe.RightClass, rightStock);
            if (!leftActor || !rightActor || !leftStock || !rightStock)
            {
                // Fully scanned candidate without cargo is finite refusal;
                // pending budget work retains its own actor/frame cursor.
                if (m_Port.HCScansComplete()) { HCClearTrip(); }
                return;
            }
            HCHoldouts camps = HCHoldouts.Get();
            if (!camps) { HCClearTrip(); return; }
            HCAICampRoutineView source = camps.HCRoutineView(HCWorldMaterializer.HCIdentity(m_LeftLease));
            HCAICampRoutineView destination = camps.HCRoutineView(HCWorldMaterializer.HCIdentity(m_RightLease));
            if (!source || !destination || !source.Home || !destination.Home) { HCClearTrip(); return; }
            float envelope = roads.Config.MaxApproachMeters * roads.Config.MaxApproachMeters;
            if (vector.DistanceSq(leftActor.GetPosition(), source.Home.HousePos) > envelope || vector.DistanceSq(rightActor.GetPosition(), destination.Home.HousePos) > envelope || vector.DistanceSq(leftActor.GetPosition(), rightActor.GetPosition()) > roads.Config.MaxJourneyMeters * roads.Config.MaxJourneyMeters)
            {
                HCClearTrip(); HCRefuse("TRADE_CAMP_APPROACH_OR_JOURNEY_RANGE"); return;
            }
            m_Port.Walker = new HCXAICaravanAdapter;
            m_Port.Walker.Corridor = roads.Config;
            if (!m_Port.Walker.HCPrepare(m_LeftLease, leftActor, rightActor.GetPosition())) { m_Port.Walker = null; HCClearTrip(); return; }
            m_Carrier = leftActor; m_Partner = rightActor;
            m_Outbound = leftStock; m_Inbound = rightStock;
            m_Port.PlannedLeft = m_LeftLease; m_Port.PlannedRight = m_RightLease;
            return;
        }
        if (roads.Phase == "idle" || roads.Phase == "failed") { HCClearTrip(); return; }
        if (roads.Phase != "ready") { return; }
        HCAITrade trade = HCAITrade.HCGet();
        m_LastOffer = HCWorldClock.UTC();
        if (!trade || !trade.HCBegin(m_LeftLease, m_RightLease)) { HCClearTrip(); return; }
        m_Planning = false; m_Travelling = true;
        Print("[HC Caravan] departure=funded_pair road_waypoints=requested actual_cargo=retained runtime=PENDING");
    }
    void HCClearTrip()
    {
        if (m_Port.Walker && (m_Travelling || m_JourneyKey != ""))
        {
            if (!m_Port.Walker.HCRestoreRoute()) { return; }
            if (m_Port.Walker.m_PartnerGroup) { return; }
        }
        if (!HCSettleJourney()) { return; }
        m_Planning = false; m_Travelling = false; m_Returning = false;
        m_Carrier = null; m_Partner = null; m_Outbound = null; m_Inbound = null;
        m_Port.Walker = null; m_Port.HCResetScans(); m_Port.HCClear();
        m_Port.PlannedLeft = ""; m_Port.PlannedRight = "";
        m_LeftLease = ""; m_RightLease = "";
        m_LeftHome = ""; m_RightHome = "";
        HCXAICaravanRoads roads = HCXAICaravanRoads.HCGet();
        if (roads && roads.Phase != "failed" && roads.Phase != "loading") { roads.Phase = "idle"; }
    }
    void HCStep()
    {
        if (!m_Port || !HCLoad()) { return; }
        HCAITrade trade = HCAITrade.HCGet();
        if (!trade) { return; }
        HCOperationalStatus status = trade.HCGetOperationalStatus();
        if (!status || status.HCState() == "off") { return; }
        HCXAICaravanRoads roads = HCXAICaravanRoads.HCGet();
        if (!roads) { HCRefuse("CARAVAN_ROAD_PROVIDER_ABSENT"); return; }
        roads.HCStep();
        if (m_Travelling)
        {
            HCTradeState state = trade.HCState();
            // The loss observer accepts only established pre/post-swap custody.
            HCLoss(state);
            if (trade.HCTrading()) { return; }
            if (!m_Carrier || !m_Carrier.IsAlive())
            {
                if (m_Port.Walker.HCRestoreRoute()) { HCClearTrip(); }
                return;
            }
            m_Port.Walker.HCReleasePartner();
            if (!m_Returning)
            {
                if (!m_Port.Walker.HCRequest(true)) { return; }
                m_Returning = true; m_ReturnAt = HCWorldClock.UTC();
            }
            float range = roads.Config.ArrivalRangeMeters;
            if (vector.DistanceSq(m_Carrier.GetPosition(), m_Port.Walker.m_From) <= range * range)
            {
                if (m_Port.Walker.HCRestoreRoute()) { HCClearTrip(); }
            }
            else if (HCWorldClock.UTC() - m_ReturnAt >= roads.Config.ReturnTimeoutSeconds)
            {
                HCRefuse("CARAVAN_RETURN_TIMEOUT_NO_FORCED_RECOVERY");
                if (m_Port.Walker.HCRestoreRoute()) { HCClearTrip(); }
            }
            return;
        }
        if (m_Planning) { HCPlan(); return; }
        if (m_Losses.Rows.Count() >= m_Recipe.MaxLossReceipts) { HCRefuse("TRADE_LOSS_RECEIPT_CAP"); return; }
        if (status.HCState() != "ready" || trade.HCTrading() || !HCTradeOfferPolicy.HCDue(HCWorldClock.UTC(), m_LastOffer, m_Recipe.OfferIntervalSeconds)) { return; }
        HCCandidate();
    }
    void HCClose() { if (m_Port) { m_Port.Producer = null; } m_Port = null; m_Store = null; m_Losses = null; }
}
