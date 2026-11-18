// Class-level geometry only: never sends instance positions, supplies or player state.
// Native snapshot 1.30.164289 (all APIs also used by existing House/Event/Group code):
// 3_Game/Entities/Object.c:287 GetPosition, :305 GetOrientation, :873 ModelToWorld, :874 WorldToModel
// 3_Game/gameplay.c:104-117 ScriptRPC/Send; 1_Core/proto/Serializer.c:57-58 Write/Read
// 3_Game/DayZGame.c:991 Event_OnRPC; 3_Game/Global/Game.c:914 GetTickTime
// CAP-09 and two-client/normal PBO acceptance remain unobserved. Positive cache lasts
// one mission; empty replies expire so a later server pack load can be discovered.
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
        m_NextRequest = 0;
    }

    HCSearchPreviewEntry EntryFor(string cls)
    {
        if (!m_Listening || !HCSearchRules.TextValid(cls, 128)) return null;
        HCSearchPreviewEntry entry = m_Cache.Get(cls);
        if (!entry)
        {
            // Pending and negative entries share the same hard cap. At capacity refuse
            // new classes until mission finish; never evict an in-flight class.
            if (m_Cache.Count() >= CACHE_LIMIT) return null;
            entry = new HCSearchPreviewEntry;
            m_Cache.Set(cls, entry);
        }
        float now = GetGame().GetTickTime();
        if (entry.Ready)
        {
            if (entry.Sites.Count() > 0 || now - entry.ReceivedAt < EMPTY_RETRY_AFTER) return entry;
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
        // A throttled request can time out, but Preview never overlaps normal requests.
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
            if (!player || player.GetIdentity() != tracked.Identity)
                m_Peers.Remove(index);
            else if (tracked.Identity == sender)
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
        if (!m_Listening || !GetGame().IsServer() || target || !sender || rpcType != HCSearchPreviewSites.RPC_REQUEST || !ctx) return;
        PlayerBase player = PlayerBase.Cast(sender.GetPlayer());
        if (!player || player.GetIdentity() != sender) return;
        HCSearchPreviewPeer peer = PeerOf(sender);
        // Admission precedes payload parsing/lookup, including malformed requests.
        if (!peer || !peer.Budget.Accept(GetGame().GetTickTime())) return;
        string cls;
        if (!ctx.Read(cls) || !HCSearchRules.TextValid(cls, 128)) return;
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
