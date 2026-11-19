// House class geometry and requested cabinet-local search point only; no supplies or player state.
// Native Math.Sqrt: 1_Core/proto/EnMath.c:305; ActionTarget accessors:
// 4_World/Classes/UserActionsComponent/ActionTargets.c:143-172.
// Cabinet RPCs share the existing bounded cache, sender throttle and mission lifecycle.
// Native snapshot 1.30.164289 (all APIs also used by existing House/Event/Group code):
// 3_Game/Entities/Object.c:287 GetPosition, :305 GetOrientation, :467 GetType, :517 IsAlive, :873 ModelToWorld, :874 WorldToModel
// 3_Game/gameplay.c:104-117 ScriptRPC/Send; 1_Core/proto/Serializer.c:57-58 Write/Read
// 3_Game/DayZGame.c:991 Event_OnRPC; 3_Game/Global/Game.c:914 GetTickTime
// 4_World/Static/MiscGameplayFunctions.c:778 GetPlayerHeadPosition.
// CAP-09 and two-client/normal PBO acceptance remain unobserved. Positive house cache lasts
// one mission; cabinet positives expire after RETRY_AFTER; empty replies expire so a later server pack load can be discovered.
class HCSearchPreviewSite
{
    vector Center;
    float Radius;
}

class HCSearchPreviewEntry
{
    bool Ready;
    bool Requested;
    bool Pilot;
    Object Cabinet;
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

    // Instance key is computed from an already visible object. The server still resolves
    // its own site handle; a class match or client key never grants inventory authority.
    static string PilotKey(Object cabinet)
    {
        if (!cabinet || !HCInteriorCatalog.SearchType(cabinet.GetType())) return "";
        return cabinet.GetType() + "_" + HCInteriorRules.TransformKey(cabinet.GetPosition(), cabinet.GetOrientation());
    }

    static array<ref HCSearchPreviewSite> CollectPilot(PlayerBase player, Object cabinet)
    {
        array<ref HCSearchPreviewSite> sites = new array<ref HCSearchPreviewSite>;
        if (!GetGame().IsServer() || PilotKey(cabinet) == "") return sites;
        HCInteriorsModule module = HCInteriorsModule.Get();
        if (!module) return sites;
        HCInteriorSite boundSite = module.HCLootKnownPilotSite(player, cabinet);
        if (!boundSite || !player) return sites;
        if (vector.DistanceSq(player.GetPosition(), boundSite.Point) > HCSearchHouses.BIND_RADIUS_SQ) return sites;
        HCSearchPreviewSite copy = new HCSearchPreviewSite;
        copy.Center = cabinet.WorldToModel(boundSite.Point);
        // Existing server standing-distance limit; no wider search or supply scan.
        copy.Radius = Math.Sqrt(HCSearchHouses.BIND_RADIUS_SQ);
        sites.Insert(copy);
        return sites;
    }

    bool PilotMatches(PlayerBase player, ActionTarget target)
    {
        if (!player || !player.IsAlive() || !target || target.GetParent() || target.GetComponentIndex() < 0) return false;
        Object cabinet = target.GetObject();
        string key = PilotKey(cabinet);
        if (key == "") return false;
        HCSearchPreviewEntry entry = EntryForTarget(key, cabinet);
        if (!entry || entry.Sites.Count() != 1) return false;
        HCSearchPreviewSite site = entry.Sites[0];
        vector point = cabinet.ModelToWorld(site.Center);
        if (vector.DistanceSq(player.GetPosition(), point) > HCSearchHouses.BIND_RADIUS_SQ) return false;
        // Same native cursor/head bound as the original action and ValidateTarget.
        return vector.DistanceSq(MiscGameplayFunctions.GetPlayerHeadPosition(player), target.GetCursorHitPos()) <= 3.24;
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
        return EntryForTarget(cls, null);
    }

    HCSearchPreviewEntry PendingPreview(HCSearchPreviewEntry entry)
    {
        // Keep an already known site while renewing membership. A three-second
        // cache renewal must not cancel the six-second continuous action.
        // A negative server reply replaces Sites and immediately removes preview.
        if (entry && entry.Pilot && entry.Sites.Count() > 0) return entry;
        return null;
    }

    // Bounded pressure sweep: map access/removal in native 1_Core/proto/EnScript.c:887,897,906.
    // Completed negatives and unsent empty entries can yield to an unseen target.
    // Pending requests and positive sites retain their identity and reply destination.
    void ReclaimNegative()
    {
        int index = m_Cache.Count() - 1;
        while (index >= 0)
        {
            HCSearchPreviewEntry cached = m_Cache.GetElement(index);
            if ((!cached.Requested || cached.Ready) && cached.Sites.Count() == 0)
            {
                string key = m_Cache.GetKey(index);
                m_Cache.Remove(key);
                return;
            }
            index = index - 1;
        }
    }

    HCSearchPreviewEntry EntryForTarget(string cls, Object cabinet)
    {
        if (!m_Listening || !HCSearchRules.TextValid(cls, 128)) return null;
        HCSearchPreviewEntry entry = m_Cache.Get(cls);
        if (!entry)
        {
            if (m_Cache.Count() >= CACHE_LIMIT) ReclaimNegative();
            if (m_Cache.Count() >= CACHE_LIMIT) return null;
            entry = new HCSearchPreviewEntry;
            entry.Cabinet = cabinet;
            m_Cache.Set(cls, entry);
        }
        if (entry.Cabinet != cabinet) return null;
        float now = GetGame().GetTickTime();
        if (entry.Ready)
        {
            if (entry.Sites.Count() > 0 && (!entry.Pilot || now - entry.ReceivedAt < RETRY_AFTER)) return entry;
            if (entry.Sites.Count() == 0 && now - entry.ReceivedAt < EMPTY_RETRY_AFTER) return entry;
            entry.Ready = false;
            entry.Requested = false;
        }
        if (now < m_NextRequest) return PendingPreview(entry);
        if (entry.Requested && now - entry.SentAt < RETRY_AFTER) return PendingPreview(entry);
        entry.Pilot = cabinet != null;
        entry.Requested = true;
        entry.SentAt = now;
        m_NextRequest = now + REQUEST_INTERVAL;
        ScriptRPC rpc = new ScriptRPC;
        rpc.Write(cls);
        rpc.Send(cabinet, RPC_REQUEST, true);
        // A throttled request can time out, but Preview never overlaps normal requests.
        return PendingPreview(entry);
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
        if (!m_Listening || !GetGame().IsServer() || !sender || rpcType != HCSearchPreviewSites.RPC_REQUEST || !ctx) return;
        PlayerBase player = PlayerBase.Cast(sender.GetPlayer());
        if (!player || player.GetIdentity() != sender) return;
        HCSearchPreviewPeer peer = PeerOf(sender);
        // Admission precedes payload parsing/lookup, including malformed requests.
        if (!peer || !peer.Budget.Accept(GetGame().GetTickTime())) return;
        string cls;
        if (!ctx.Read(cls) || !HCSearchRules.TextValid(cls, 128)) return;
        array<ref HCSearchPreviewSite> sites;
        if (target)
        {
            if (cls != HCSearchPreviewSites.PilotKey(target)) return;
            sites = HCSearchPreviewSites.CollectPilot(player, target);
        }
        else
        {
            sites = HCSearchPreviewSites.Collect(cls);
        }
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
