// Subscription work is absent while idle. One global retained job, <=32 peers;
// one contributor or RowsPerTick registry rows, one <=64-row RPC per 100 ms pulse.
// Pulse exists only while subscribed (core tick defaults to 1 s). Native:
// 3_Game/Global/Game.c:1550 GetCallQueue; 2_GameLib/tools.c:61/65 CallLater/Remove.
// Native scripts-1.30.164289: gameplay.c:104-117 ScriptRPC.Send;
// 3_Game/DayZGame.c:991 Event_OnRPC; Global/Game.c:914/1120 tick/server;
// Object.c:215/287/467 pending/position/type; Man.c:21 GetIdentity;
// 1_Core/proto/EnSystem.c:106 TickCount. Cooperative native calls cannot preempt.
class HCAdminWorldPeer
{
    PlayerIdentity Identity;
    int Session;
    float Until;
    float RequestAfter;
    float Due;
    int StaticVersion;
    int Sequence;
    vector Centre;
    float Scale;
}

modded class HCAdminModule
{
    protected ref HCAdminWorldConfig m_WorldConfig;
    protected ref array<ref HCAdminWorldPeer> m_WorldPeers = new array<ref HCAdminWorldPeer>;
    protected ref HCAdminWorldCapture m_WorldStatic;
    protected ref HCAdminWorldCapture m_WorldCapture;
    protected ref HCAdminWorldSources m_WorldSources;
    protected HCAdminWorldPeer m_WorldPeer;
    protected ref HCWorkBudget m_WorldWork = new HCPerfSlices("AdminWorld");
    protected int m_WorldStage;
    protected int m_WorldCursor;
    protected int m_WorldSend;
    protected int m_WorldChunk;
    protected int m_WorldRound;
    protected bool m_WorldIsStatic;
    protected int m_WorldCost;
    protected ref array<ref HCAdminMark> m_WorldLoot = new array<ref HCAdminMark>;
    protected float m_WorldLootUntil;
    protected bool m_WorldPulsing;
    protected HCAdminWorldPeer m_WorldLootOwner;

    override protected void HCSend(PlayerIdentity sender, HCAdminReply reply)
    {
        // Capture the existing bounded loot job's final result for M-map layers.
        if (HCWorldAllowed(sender) && reply && reply.Snapshot && reply.Notice.IndexOf("[HC Admin] cmd=lootmap ") == 0)
        {
            m_WorldLootOwner = null;
            m_WorldLoot.Clear();
            for (int index = 0; index < reply.Marks.Count() && index < 512; index++)
            {
                if (reply.Marks[index].Layer == "lootmap") { m_WorldLoot.Insert(reply.Marks[index]); }
            }
            m_WorldLootUntil = GetGame().GetTickTime() + 120;
        }
        super.HCSend(sender, reply);
    }

    // The map is allowlist-only, even when optional console permissions exist.
    bool HCWorldAllowed(PlayerIdentity identity)
    {
        return m_Running && GetGame() && GetGame().IsServer() && identity && m_Admins && m_Admins.PlainIds.Find(identity.GetPlainId()) >= 0;
    }

    override void OnStart(HCSettings settings)
    {
        super.OnStart(settings);
        if (!m_Running) { return; }
        m_WorldConfig = HCAdminWorldConfig.Load();
        DayZGame.Event_OnRPC.Insert(HCWorldReceive);
        m_Status.HCPublish("ready", "allowlist_loaded_m_map_stream_native_admin_client_pending");
    }

    void HCWorldReceive(PlayerIdentity sender, Object target, int rpcType, ParamsReadContext ctx)
    {
        if (rpcType != HCAdminWorldWire.REQUEST || !GetGame() || !GetGame().IsServer()) { return; }
        // BEFORE deserialization/allocation, on EVERY request. No refusal reply.
        if (!HCWorldAllowed(sender) || target || !ctx) { return; }
        HCAdminWorldPeer peer;
        for (int index = 0; index < m_WorldPeers.Count(); index++)
        {
            if (m_WorldPeers[index].Identity.GetPlainId() == sender.GetPlainId()) { peer = m_WorldPeers[index]; break; }
        }
        float now = GetGame().GetTickTime();
        HCAdminWorldRequest request;
        if (!ctx.Read(request) || !request || request.Session < 1) { return; }
        if (!(request.Scale >= 0.001 && request.Scale <= 1000) || !HCDebugSnapshot.HCPositionValid(request.Centre)) { return; }
        if (!request.Open && !peer) { return; }
        if (request.Open && peer && now < peer.RequestAfter) { return; }
        if (!peer)
        {
            if (m_WorldPeers.Count() >= 32) { return; }
            peer = new HCAdminWorldPeer;
            peer.Identity = sender;
            m_WorldPeers.Insert(peer);
        }
        if (peer.Identity != sender)
        {
            peer.Identity = sender;
            peer.Session = 0;
            peer.StaticVersion = 0;
        }
        if (request.Session < peer.Session) { return; }
        peer.RequestAfter = now + 0.5;
        if (!request.Open)
        {
            if (peer.Session == request.Session) { peer.Until = 0; HCWorldCancelLoot(peer); }
            return;
        }
        if (request.LootFilter.Length() > 0 && request.LootFilter.Length() <= 96)
        {
            // Existing job validates the class/prefix, caps queries and owns cooldown.
            if (HCStartLootMap(sender, "lootmap " + request.LootFilter, 0)) { m_WorldLoot.Clear(); m_WorldLootOwner = peer; }
        }
        bool opening = peer.Until <= now || peer.Session != request.Session;
        if (peer.Session != request.Session && m_WorldPeer == peer) { HCWorldCancel(); }
        peer.Session = request.Session;
        peer.Until = now + 15;
        if (!m_WorldPulsing)
        {
            m_WorldPulsing = true;
            GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(HCWorldPulse, 100, true);
        }
        peer.Centre = request.Centre;
        peer.Scale = request.Scale;
        peer.StaticVersion = request.StaticVersion;
        if (opening)
        {
            peer.Due = 0;
            Print("[HC Admin] map_subscribe admin=1 layers=48");
        }
    }

    protected bool HCWorldLive(HCAdminWorldPeer peer)
    {
        if (!peer || peer.Until <= GetGame().GetTickTime() || !HCWorldAllowed(peer.Identity)) { return false; }
        // Reuse the frame-owned roster only while subscribed; <=32 identities.
        array<Man> players = HCPerfPlayers.HCGet();
        int count = Math.Min(players.Count(), 32);
        for (int index = 0; index < count; index++)
        {
            Man player = players[index];
            if (player && player.GetIdentity() && player.GetIdentity().GetId() == peer.Identity.GetId()) { return true; }
        }
        peer.Until = 0;
        return false;
    }

    protected void HCWorldCancel()
    {
        m_WorldPeer = null;
        m_WorldCapture = null;
        m_WorldSources = null;
        m_WorldStage = 0;
        m_WorldCursor = 0;
        m_WorldSend = 0;
        m_WorldChunk = 0;
        m_WorldCost = 0;
    }

    protected void HCWorldChoose()
    {
        float now = GetGame().GetTickTime();
        for (int visit = 0; visit < m_WorldPeers.Count(); visit++)
        {
            if (m_WorldRound >= m_WorldPeers.Count()) { m_WorldRound = 0; }
            HCAdminWorldPeer peer = m_WorldPeers[m_WorldRound];
            m_WorldRound++;
            if (peer.Due > now || !HCWorldLive(peer)) { continue; }
            m_WorldPeer = peer;
            peer.Sequence++;
            peer.Due = now + m_WorldConfig.RefreshSeconds;
            m_WorldIsStatic = peer.StaticVersion != HCAdminWorldCatalog.VERSION;
            m_WorldCapture = new HCAdminWorldCapture(0);
            m_WorldCapture.Limit = m_WorldConfig.MaxRows;
            m_WorldSources = new HCAdminWorldSources;
            m_WorldStage = 2;
            if (m_WorldIsStatic)
            {
                m_WorldStage = 1;
                m_WorldCapture.Limit = HCAdminWorldWire.ROWS;
                if (m_WorldStatic) { m_WorldCapture = m_WorldStatic; m_WorldStage = 7; }
            }
            return;
        }
    }

    protected void HCWorldSendChunk()
    {
        int sendStart = TickCount(0);
        if (!HCWorldLive(m_WorldPeer)) { HCWorldCancel(); return; }
        HCAdminWorldReply reply = new HCAdminWorldReply;
        reply.Session = m_WorldPeer.Session;
        reply.Sequence = m_WorldPeer.Sequence;
        reply.Chunk = m_WorldChunk;
        reply.IsStatic = m_WorldIsStatic;
        reply.CatalogRevision = HCAdminWorldCatalog.VERSION;
        reply.DrawLimit = m_WorldConfig.MaxDraw;
        reply.Total = m_WorldCapture.Rows.Count();
        reply.Truncated = m_WorldCapture.Dropped;
        int end = Math.Min(reply.Total, m_WorldSend + HCAdminWorldWire.CHUNK);
        for (; m_WorldSend < end; m_WorldSend++) { reply.Marks.Insert(m_WorldCapture.Rows[m_WorldSend]); }
        reply.Last = m_WorldSend >= reply.Total;
        ScriptRPC rpc = new ScriptRPC;
        rpc.Write(reply);
        // Identity is checked again immediately before this targeted send.
        if (HCWorldAllowed(m_WorldPeer.Identity)) { rpc.Send(null, HCAdminWorldWire.REPLY, true, m_WorldPeer.Identity); }
        m_WorldChunk++;
        if (!reply.Last) { return; }
        m_WorldCost += TickCount(sendStart);
        if (m_WorldIsStatic) { m_WorldPeer.StaticVersion = HCAdminWorldCatalog.VERSION; }
        if (m_WorldIsStatic) { m_WorldPeer.Due = 0; }
        string summary = "[HC Admin] map_snapshot layers=" + m_WorldCapture.LayerCount().ToString() + " marks=" + reply.Total.ToString();
        summary += " ms=" + HCWorkBudget.HCAdminMilliseconds(m_WorldCost).ToString() + " ticks=" + m_WorldCost.ToString();
        summary += " static=" + m_WorldIsStatic.ToString() + " truncated=" + reply.Truncated.ToString();
        Print("" + summary);
        HCWorldCancel();
    }

    protected void HCWorldTick()
    {
        if (!m_Running || m_WorldPeers.Count() == 0) { return; }
        // Expired peers are removed: no continuing idle roster polls or scans.
        for (int expire = m_WorldPeers.Count() - 1; expire >= 0; expire--)
        {
            if (m_WorldPeers[expire].Until > GetGame().GetTickTime()) { continue; }
            if (m_WorldPeer == m_WorldPeers[expire]) { HCWorldCancel(); }
            HCWorldCancelLoot(m_WorldPeers[expire]);
            m_WorldPeers.Remove(expire);
        }
        if (m_WorldPeers.Count() == 0) { return; }
        if (!m_WorldPeer) { HCWorldChoose(); }
        if (!m_WorldPeer) { return; }
        if (!HCWorldLive(m_WorldPeer)) { HCWorldCancel(); return; }
        if (!HCServer.HCTickWork().HCTake(1)) { return; }
        int start = TickCount(0);
        m_WorldWork.HCReset(m_WorldConfig.RowsPerTick, HCPerfConfig.HCGet().SliceMs);
        if (m_WorldStage == 1)
        {
            while (m_WorldCursor < HCAdminWorldCatalog.COUNT && m_WorldWork.HCContinue())
            {
                HCAdminWorldCatalog.Emit(m_WorldCapture, m_WorldCursor);
                m_WorldCursor++;
            }
            if (m_WorldCursor >= HCAdminWorldCatalog.COUNT) { m_WorldStatic = m_WorldCapture; m_WorldStage = 7; }
        }
        else if (m_WorldStage == 2)
        {
            if (m_WorldCapture.HCCaptureNext()) { m_WorldStage = 3; m_WorldCursor = 0; }
        }
        else if (m_WorldStage == 3)
        {
            while (m_WorldCursor < HCAdminVehicleRegistry.Vehicles.Count() && m_WorldWork.HCContinue())
            {
                Transport vehicle = HCAdminVehicleRegistry.Vehicles[m_WorldCursor];
                m_WorldCursor++;
                if (vehicle && !vehicle.IsPendingDeletion()) { m_WorldCapture.Put("vehicles", vehicle.GetPosition(), vehicle.GetType(), HCAdminVehicleRegistry.Detail(vehicle)); }
            }
            if (m_WorldCursor >= HCAdminVehicleRegistry.Vehicles.Count()) { m_WorldStage = 4; m_WorldCursor = 0; }
        }
        else if (m_WorldStage == 4)
        {
            while (m_WorldCursor < HCAdminVehicleRegistry.Events.Count() && m_WorldWork.HCContinue())
            {
                Object eventObject = HCAdminVehicleRegistry.Events[m_WorldCursor];
                m_WorldCursor++;
                if (eventObject && !eventObject.IsPendingDeletion()) { m_WorldCapture.Put("vanilla-events", eventObject.GetPosition(), eventObject.GetType(), "Live CE crash/gas entity"); }
            }
            if (m_WorldCursor >= HCAdminVehicleRegistry.Events.Count()) { m_WorldStage = 5; m_WorldCursor = 0; }
        }
        else if (m_WorldStage == 5)
        {
            HCEcologyRuntime ecology = HCEcologyRuntime.HCPeek();
            if (!ecology) { m_WorldStage = 8; m_WorldCursor = 0; }
            else
            {
                while (m_WorldCursor < ecology.HCAdminAnimalCount() && m_WorldWork.HCContinue())
                {
                    AnimalBase animal = ecology.HCAdminAnimal(m_WorldCursor);
                    m_WorldCursor++;
                    if (animal && !animal.IsPendingDeletion() && animal.IsAlive()) { m_WorldCapture.Put("ecology", animal.GetPosition(), animal.GetType(), "Live ecology cohort; bounded observed animals, not a world census"); }
                }
                if (m_WorldCursor >= ecology.HCAdminAnimalCount()) { m_WorldStage = 8; m_WorldCursor = 0; }
            }
        }
        else if (m_WorldStage == 8)
        {
            HCInfectedModule infected = HCInfectedModule.Instance;
            if (!infected) { m_WorldStage = 11; m_WorldCursor = 0; }
            else
            {
                while (m_WorldCursor < infected.HCAdminHordeCount() && m_WorldWork.HCContinue())
                {
                    infected.HCAdminHorde(m_WorldCapture, m_WorldCursor);
                    m_WorldCursor++;
                }
                if (m_WorldCursor >= infected.HCAdminHordeCount()) { m_WorldStage = 11; m_WorldCursor = 0; }
            }
        }
        else if (m_WorldStage == 11)
        {
            HCInfectedModule packs = HCInfectedModule.Instance;
            if (!packs) { m_WorldStage = 9; m_WorldCursor = 0; }
            else
            {
                while (m_WorldCursor < packs.HCAdminPackCount() && m_WorldWork.HCContinue())
                {
                    packs.HCAdminPack(m_WorldCapture, m_WorldCursor);
                    m_WorldCursor++;
                }
                if (m_WorldCursor >= packs.HCAdminPackCount()) { m_WorldStage = 9; m_WorldCursor = 0; }
            }
        }
        else if (m_WorldStage == 9)
        {
            HCBuildingClaim claims = HCBuildingClaim.HCGet();
            if (!claims) { m_WorldStage = 10; m_WorldCursor = 0; }
            else
            {
                while (m_WorldCursor < claims.HCAdminClaimCount() && m_WorldWork.HCContinue())
                {
                    claims.HCAdminClaim(m_WorldCapture, m_WorldCursor);
                    m_WorldCursor++;
                }
                if (m_WorldCursor >= claims.HCAdminClaimCount()) { m_WorldStage = 10; m_WorldCursor = 0; }
            }
        }
        else if (m_WorldStage == 10)
        {
            if (GetGame().GetTickTime() > m_WorldLootUntil) { m_WorldLoot.Clear(); }
            while (m_WorldCursor < m_WorldLoot.Count() && m_WorldWork.HCContinue())
            {
                HCAdminMark loot = m_WorldLoot[m_WorldCursor];
                m_WorldCapture.Put("lootmap", loot.Position, loot.Label, loot.Detail + "; latest ground sample, expires after 120 s");
                m_WorldCursor++;
            }
            if (m_WorldCursor >= m_WorldLoot.Count()) { m_WorldStage = 6; }
        }
        else if (m_WorldStage == 6)
        {
            if (m_WorldSources.StepAI(m_WorldCapture, m_WorldConfig.RowsPerTick)) { m_WorldStage = 7; }
        }
        else if (m_WorldStage == 7) { HCWorldSendChunk(); }
        // Per-visit measured cost; high-resolution units use the shared perf rate.
        int cost = TickCount(start);
        if (m_WorldPeer) { m_WorldCost += cost; }
        Print("[HC Admin] map_refresh stage=" + m_WorldStage.ToString() + " ms=" + HCWorkBudget.HCAdminMilliseconds(cost).ToString() + " ticks=" + cost.ToString());
    }

    protected void HCWorldCancelLoot(HCAdminWorldPeer peer)
    {
        if (!peer || m_WorldLootOwner != peer) { return; }
        m_WorldLootOwner = null;
        // Only the M-map-owned ticket-zero query is cancelled; no console job.
        if (m_LootMapTicket == 0)
        {
            m_LootMap = null;
            m_LootMapSender = null;
        }
    }
    void HCWorldPulse()
    {
        HCWorldTick();
        if (!m_Running || m_WorldPeers.Count() == 0)
        {
            GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).Remove(HCWorldPulse);
            m_WorldPulsing = false;
        }
    }
    override void OnTick(float deltaTime)
    {
        if (m_WorldLootOwner && !HCWorldLive(m_WorldLootOwner)) { HCWorldCancelLoot(m_WorldLootOwner); }
        super.OnTick(deltaTime);
    }
    override void OnStop()
    {
        DayZGame.Event_OnRPC.Remove(HCWorldReceive);
        GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).Remove(HCWorldPulse);
        m_WorldPulsing = false;
        HCWorldCancelLoot(m_WorldLootOwner);
        HCWorldCancel();
        m_WorldPeers.Clear();
        m_WorldStatic = null;
        m_WorldLoot.Clear();
        super.OnStop();
    }
}
