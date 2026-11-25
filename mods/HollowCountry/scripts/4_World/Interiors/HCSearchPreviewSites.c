// House class geometry only; no supplies or player state.
// Native Math.Sqrt: 1_Core/proto/EnMath.c:305; ActionTarget accessors:
// 4_World/Classes/UserActionsComponent/ActionTargets.c:143-172.
// The class request RPC shares one bounded cache, sender throttle and mission lifecycle.
// Native snapshot 1.30.164289 (all APIs also used by existing House/Event/Group code):
// 3_Game/Entities/Object.c:287 GetPosition, :305 GetOrientation, :467 GetType, :517 IsAlive, :873 ModelToWorld, :874 WorldToModel
// 3_Game/gameplay.c:104-117 ScriptRPC/Send; 1_Core/proto/Serializer.c:57-58 Write/Read
// 3_Game/DayZGame.c:991 Event_OnRPC; 3_Game/Global/Game.c:914 GetTickTime
// 4_World/Static/MiscGameplayFunctions.c:778 GetPlayerHeadPosition.
// CAP-09 and two-client/normal PBO acceptance remain unobserved. Positive house cache lasts
// until LRU pressure; empty replies expire for later server pack loads.
class HCSearchPreviewSite
{
    vector Center;
    float Radius;
}

class HCSearchPreviewEntry
{
    bool Ready;
    bool Requested;
    float SentAt;
    float ReceivedAt;
    ref array<ref HCSearchPreviewSite> Sites = new array<ref HCSearchPreviewSite>;
}

class HCSearchPreviewSites
{
    static const int RPC_REQUEST = 4853901;
    static const int RPC_SITES = 4853902;
    static const int CACHE_LIMIT = 256;
    static const float REQUEST_INTERVAL = 0.5;
    static const float RETRY_AFTER = 3.0;
    static const float EMPTY_RETRY_AFTER = 60.0;
    protected static ref HCSearchPreviewSites s_Instance;
    protected ref map<string, ref HCSearchPreviewEntry> m_Cache = new map<string, ref HCSearchPreviewEntry>;
    protected ref array<string> m_Recency = new array<string>;
    protected bool m_Listening;
    protected float m_NextRequest;

    static HCSearchPreviewSites Get()
    {
        if (!s_Instance) s_Instance = new HCSearchPreviewSites;
        return s_Instance;
    }

    // Same class/shape filter and examined-row cap as Resolve; no entities, I/O or scans.
    static array<ref HCSearchPreviewSite> Collect(string cls)
    {
        array<ref HCSearchPreviewSite> sites = new array<ref HCSearchPreviewSite>;
        if (!GetGame().IsServer() || !HCInteriorTemplates.Loaded()) return sites;
        HCInteriorTemplateClassRow classRow = HCInteriorTemplates.ClassRow(cls);
        if (!classRow || classRow.Search != "covered") return sites;
        HCInteriorTemplate layout = HCInteriorTemplates.Template(cls);
        if (!layout || !layout.SearchSites) return sites;
        int examined;
        foreach (HCInteriorTemplateSearchSite site : layout.SearchSites)
        {
            examined++;
            if (examined > HCSearchHouses.MAX_SITES) break;
            if (!HCSearchHouses.SiteShapeValid(site)) continue;
            HCSearchPreviewSite copy = new HCSearchPreviewSite;
            copy.Center = Vector(site.Center[0], site.Center[1], site.Center[2]);
            copy.Radius = site.Radius;
            sites.Insert(copy);
        }
        return sites;
    }

    void Start()
    {
        if (m_Listening || GetGame().IsServer()) return;
        m_Listening = true;
        DayZGame.Event_OnRPC.Insert(OnRPC);
    }

    void Stop()
    {
        if (m_Listening) DayZGame.Event_OnRPC.Remove(OnRPC);
        m_Listening = false;
        m_Cache.Clear();
        m_Recency.Clear();
        m_NextRequest = 0;
    }

    // Native array Find/Insert/RemoveOrdered: 1_Core/proto/EnScript.c:394/407/470.
    // Both recency work and pressure scans are bounded by CACHE_LIMIT (256).
    void Touch(string key)
    {
        // Per-frame action conditions repeat the newest key: skip the scan.
        int last = m_Recency.Count() - 1;
        if (last >= 0 && m_Recency[last] == key) return;
        int index = m_Recency.Find(key);
        if (index >= 0) m_Recency.RemoveOrdered(index);
        m_Recency.Insert(key);
    }

    void ReclaimIdle()
    {
        PlayerBase viewer = PlayerBase.Cast(GetGame().GetPlayer());
        string activeKey;
        // Native PlayerBase.c:1887 GetActionManager (4_World/Entities/ManBase).
        if (viewer && viewer.GetActionManager()) activeKey = viewer.GetActionManager().HCSearchPreviewActiveKey();
        for (int index = 0; index < m_Recency.Count() && index < CACHE_LIMIT; index++)
        {
            string key = m_Recency[index];
            HCSearchPreviewEntry cached = m_Cache.Get(key);
            if (key == activeKey || (cached.Requested && !cached.Ready)) continue;
            // Oldest eligible entry, positive or empty. Never redirect an outstanding
            // reply or discard the cache entry used by a running search action.
            m_Cache.Remove(key);
            m_Recency.RemoveOrdered(index);
            return;
        }
    }

    // A known positive entry is reused until LRU pressure; a pending or throttled request
    // yields no preview, and a negative reply replaces Sites and removes it at once.
    HCSearchPreviewEntry EntryFor(string cls)
    {
        if (!m_Listening || !HCSearchRules.TextValid(cls, 128)) return null;
        HCSearchPreviewEntry entry = m_Cache.Get(cls);
        if (!entry)
        {
            if (m_Cache.Count() >= CACHE_LIMIT) ReclaimIdle();
            if (m_Cache.Count() >= CACHE_LIMIT) return null;
            entry = new HCSearchPreviewEntry;
            m_Cache.Set(cls, entry);
        }
        Touch(cls);
        float now = GetGame().GetTickTime();
        if (entry.Ready)
        {
            if (entry.Sites.Count() > 0) return entry;
            if (now - entry.ReceivedAt < EMPTY_RETRY_AFTER) return entry;
            entry.Ready = false;
            entry.Requested = false;
        }
        if (now < m_NextRequest) return null;
        if (entry.Requested && now - entry.SentAt < RETRY_AFTER) return null;
        entry.Requested = true;
        entry.SentAt = now;
        m_NextRequest = now + REQUEST_INTERVAL;
        ScriptRPC rpc = new ScriptRPC;
        rpc.Write(cls);
        rpc.Send(null, RPC_REQUEST, true);
        return null;
    }

    bool Matches(PlayerBase player, ActionTarget target, House building)
    {
        vector orientation = building.GetOrientation();
        if (!HCInteriorRules.TiltAcceptable(orientation, HCInteriorRules.MAX_HOUSE_TILT_DEGREES)) { return false; }
        HCSearchPreviewEntry entry = EntryFor(building.GetType());
        if (!entry) return false;
        vector offset = building.WorldToModel(target.GetCursorHitPos());
        vector standing = player.GetPosition();
        foreach (HCSearchPreviewSite site : entry.Sites)
        {
            if (vector.DistanceSq(offset, site.Center) > site.Radius * site.Radius) continue;
            vector world = building.ModelToWorld(site.Center);
            if (vector.DistanceSq(standing, world) > HCSearchHouses.BIND_RADIUS_SQ) continue;
            return true;
        }
        return false;
    }

    void OnRPC(PlayerIdentity sender, Object target, int rpcType, ParamsReadContext ctx)
    {
        if (!m_Listening || GetGame().IsServer() || sender || rpcType != RPC_SITES || !ctx) return;
        PlayerBase viewer = PlayerBase.Cast(GetGame().GetPlayer());
        if (!viewer || target != viewer) return;
        string cls;
        int count;
        if (!ctx.Read(cls) || !HCSearchRules.TextValid(cls, 128)) return;
        HCSearchPreviewEntry entry = m_Cache.Get(cls);
        if (!entry || !entry.Requested || entry.Ready) return;
        if (!ctx.Read(count) || count < 0 || count > HCSearchHouses.MAX_SITES) return;
        // Read individual bounded pairs, not a client-allocated unbounded wire array.
        array<ref HCSearchPreviewSite> sites = new array<ref HCSearchPreviewSite>;
        int index;
        while (index < count)
        {
            vector center;
            float radius;
            if (!ctx.Read(center) || !ctx.Read(radius)) return;
            if (!HCInteriorRules.SaneVector(center, 1024.0) || !(radius >= 0.25 && radius <= 8.0)) return;
            HCSearchPreviewSite site = new HCSearchPreviewSite;
            site.Center = center;
            site.Radius = radius;
            sites.Insert(site);
            index++;
        }
        entry.Sites = sites;
        entry.ReceivedAt = GetGame().GetTickTime();
        entry.Ready = true;
    }
}

class HCSearchPreviewBudget
{
    float Window;
    int Count;

    bool Accept(float now)
    {
        if (now != now || now < Window || now > 1000000000) return false;
        if (now - Window >= 1.0)
        {
            Window = now;
            Count = 0;
        }
        if (Count >= 4) return false;
        Count++;
        return true;
    }
}

class HCSearchPreviewPeer
{
    PlayerIdentity Identity;
    ref HCSearchPreviewBudget Budget = new HCSearchPreviewBudget;
}

class HCSearchPreviewServer
{
    protected bool m_Listening;
    protected ref array<ref HCSearchPreviewPeer> m_Peers = new array<ref HCSearchPreviewPeer>;

    void Start()
    {
        if (m_Listening || !GetGame().IsServer()) return;
        Print("[HC Search Cabinets] site-known RPC listening; server binding required runtime=PENDING");
        m_Listening = true;
        DayZGame.Event_OnRPC.Insert(OnRPC);
    }

    void Stop()
    {
        if (m_Listening) DayZGame.Event_OnRPC.Remove(OnRPC);
        m_Listening = false;
        m_Peers.Clear();
    }

    HCSearchPreviewPeer PeerOf(PlayerIdentity sender)
    {
        HCSearchPreviewPeer found;
        int index = m_Peers.Count() - 1;
        while (index >= 0)
        {
            HCSearchPreviewPeer tracked = m_Peers[index];
            // A disconnected identity is released by the engine, so the weak pointer reads null.
            PlayerBase player;
            if (tracked.Identity) player = PlayerBase.Cast(tracked.Identity.GetPlayer());
            if (!player || !HCPlayerIdentity.Same(player.GetIdentity(), tracked.Identity))
                m_Peers.Remove(index);
            else if (HCPlayerIdentity.Same(tracked.Identity, sender))
                found = tracked;
            index = index - 1;
        }
        if (found) return found;
        if (m_Peers.Count() >= 90) return null;
        HCSearchPreviewPeer peer = new HCSearchPreviewPeer;
        peer.Identity = sender;
        m_Peers.Insert(peer);
        return peer;
    }

    void OnRPC(PlayerIdentity sender, Object target, int rpcType, ParamsReadContext ctx)
    {
        if (!m_Listening || !GetGame().IsServer() || !sender || rpcType != HCSearchPreviewSites.RPC_REQUEST || !ctx) return;
        PlayerBase player = PlayerBase.Cast(sender.GetPlayer());
        if (!player || !HCPlayerIdentity.Same(player.GetIdentity(), sender)) return;
        HCSearchPreviewPeer peer = PeerOf(sender);
        // Admission precedes payload parsing/lookup, including malformed requests.
        if (!peer || !peer.Budget.Accept(GetGame().GetTickTime())) return;
        string cls;
        if (!ctx.Read(cls) || !HCSearchRules.TextValid(cls, 128)) return;
        // Only the class request is served; a request that names a target object is dropped.
        if (target) return;
        array<ref HCSearchPreviewSite> sites = HCSearchPreviewSites.Collect(cls);
        ScriptRPC rpc = new ScriptRPC;
        rpc.Write(cls);
        rpc.Write(sites.Count());
        foreach (HCSearchPreviewSite site : sites)
        {
            rpc.Write(site.Center);
            rpc.Write(site.Radius);
        }
        rpc.Send(player, HCSearchPreviewSites.RPC_SITES, true, sender);
    }
}

// Read only the native action context; no client inventory or server authority.
// Native 4_World/Classes/UserActionsComponent/ActionManagerBase.c:61,91-96;
// ActionBase.c:34,39 m_Action/m_Target; ActionTargets.c:143 GetObject.
modded class ActionManagerBase
{
    string HCSearchPreviewActiveKey()
    {
        if (!m_CurrentActionData || !HCActionSearchInterior.Cast(m_CurrentActionData.m_Action) || !m_CurrentActionData.m_Target) return "";
        ActionTarget target = m_CurrentActionData.m_Target;
        House house = HCSearchHouses.HouseOf(target);
        if (house) return house.GetType();
        return "";
    }
}
