// Entry-local roster port: native scripts-1.30.164289 3_Game/Global/Game.c:945;
// resolver identity/life: Entities/Man.c:21, gameplay.c:368, Entities/Object.c:517.
// #256 look-at ping. Native 1.30: DayZPhysics.c:199 RaycastRV;
// Object.c:238 GetBonePositionWS; human.c:1417 GetBoneIndexByName;
// Game.c:914 GetTickTime; existing group RPC identity/session/replay envelope.
// No persistence, new module, player positions in payloads, or map pins.
class HCGroupPingWire
{
    static const int RPC = 4853704;
    static const int LOOK = 3; // TEAM_PING Role discriminator; 0..2 remain status pings.
    int GroupId;
    int Epoch;
    string Session;
    ref array<vector> Points = new array<vector>;
    ref array<int> Expires = new array<int>;
    int Now; // server UTC at send; clients keep only the remaining lifetime
}
class HCGroupPingRow
{
    int GroupId;
    int Epoch;
    vector Point;
    int Expires;
}
class HCGroupPingCooldown
{
    string Account;
    float After;
}
modded class HCGroupService
{
    protected ref array<ref HCGroupPingRow> m_HCLookPings = new array<ref HCGroupPingRow>;

    protected ref array<ref HCGroupPingCooldown> m_HCLookCooldowns = new array<ref HCGroupPingCooldown>;

    // Bounded by 90 connected peers; retain receipts across reconnect/group changes.
    bool HCAdmitLookPing(string account, float tick)
    {
        if (!(tick >= 0)) { return false; }
        for (int index = m_HCLookCooldowns.Count() - 1; index >= 0; index--)
        {
            HCGroupPingCooldown receipt = m_HCLookCooldowns.Get(index);
            if (receipt.After <= tick) { m_HCLookCooldowns.RemoveOrdered(index); continue; }
            if (receipt.Account == account) { return false; }
        }
        if (m_HCLookCooldowns.Count() >= 90) { return false; }
        HCGroupPingCooldown admitted = new HCGroupPingCooldown;
        admitted.Account = account;
        admitted.After = tick + 5;
        m_HCLookCooldowns.Insert(admitted);
        return true;
    }

    HCGroupRecord HCLookGroup(HCGroupPeer peer, map<string, PlayerBase> hcPlayers)
    {
        if (!m_Healthy || !m_Config || !m_Config.Enabled || !m_State || !Live(peer, hcPlayers)) { return null; }
        PlayerBase hcPeerPlayer;
        if (peer) hcPeerPlayer = HCPlayerOf(hcPlayers, peer.Id);
        PlayerIdentity hcPeerIdentity;
        if (hcPeerPlayer) hcPeerIdentity = hcPeerPlayer.GetIdentity();
        HCGroupPeer hcFoundPeer1 = Peer(peer.Id);
        if (!hcPeerPlayer || !hcPeerIdentity || hcFoundPeer1 != peer || hcPeerIdentity.GetId() != peer.Id) { return null; }
        if (!hcPeerPlayer.IsAlive() || hcPeerPlayer.IsUnconscious()) { return null; }
        return HCGroupRules.FindGroup(m_State, peer.Id);
    }

    override int HCLookPing(HCGroupPeer peer, HCGroupRequest request, map<string, PlayerBase> hcPlayers)
    {
        HCGroupRecord group = HCLookGroup(peer, hcPlayers);
        if (!group || !m_Config.HCTeamPingEnabled) { return HCGroupCode.DENIED; }
        if (request.ExpectedRevision != m_State.Revision) { return HCGroupCode.CONFLICT; }
        float tick = GetGame().GetTickTime();
        // Failed geometry also consumes the cooldown; at most one ray per 5 s.
        if (!HCAdmitLookPing(peer.Id, tick)) { return HCGroupCode.RATE; }
        if (!HCGroupRules.PositionValid(request.Position)) { return HCGroupCode.INVALID; }
        PlayerBase hcPeerPlayer;
        if (peer) hcPeerPlayer = HCPlayerOf(hcPlayers, peer.Id);
        vector origin = hcPeerPlayer.GetBonePositionWS(hcPeerPlayer.GetBoneIndexByName("Head"));
        vector direction = request.Position - origin;
        float distance = direction.Length();
        if (!(distance >= 1 && distance <= 300)) { return HCGroupCode.INVALID; }
        direction.Normalize();
        vector finish = origin + direction * Math.Min(300, distance + 1);
        vector contact;
        vector normal;
        int component;
        // Never accept a point through geometry. Persist/relay the server hit,
        // not the client coordinate (third-person camera offsets can be refused).
        if (!DayZPhysics.RaycastRV(origin, finish, contact, normal, component, null, null, hcPeerPlayer, false, false, ObjIntersectView)) { return HCGroupCode.INVALID; }
        if (!HCGroupRules.PositionValid(contact) || vector.Distance(contact, request.Position) > 2) { return HCGroupCode.INVALID; }
        int now = HCGroupClock.Utc();
        if (!HCGroupRules.DeadlineFits(now, 10)) { return HCGroupCode.DENIED; }
        int active;
        int oldest = -1;
        // <=270 rows: validated MaxGroups<=90, three live points per group.
        for (int i = m_HCLookPings.Count() - 1; i >= 0; i--)
        {
            HCGroupPingRow row = m_HCLookPings.Get(i);
            if (row.Expires <= now || row.Expires > now + 10)
            {
                m_HCLookPings.RemoveOrdered(i);
                continue;
            }
        }
        for (int j = 0; j < m_HCLookPings.Count(); j++)
        {
            HCGroupPingRow current = m_HCLookPings.Get(j);
            if (current.GroupId != group.Id || current.Epoch != group.Epoch) { continue; }
            active++;
            if (oldest < 0) { oldest = j; }
        }
        if (active >= 3) { m_HCLookPings.RemoveOrdered(oldest); }
        if (m_HCLookPings.Count() >= 270) { return HCGroupCode.LIMIT; }
        HCGroupPingRow admitted = new HCGroupPingRow;
        admitted.GroupId = group.Id;
        admitted.Epoch = group.Epoch;
        admitted.Point = contact;
        admitted.Expires = now + 10;
        m_HCLookPings.Insert(admitted);
        ref array<ref HCGroupPingRow> groupPoints = new array<ref HCGroupPingRow>;
        array<ref HCGroupPingRow> hcRows1 = m_HCLookPings;
        foreach (HCGroupPingRow candidate : hcRows1)
        {
            if (groupPoints.Count() >= 3) { break; }
            if (candidate.GroupId == group.Id && candidate.Epoch == group.Epoch) { groupPoints.Insert(candidate); }
        }
        // At most 90 peers, three points each. No global broadcast or entity scan.
        array<ref HCGroupPeer> hcRows2 = m_Peers;
        foreach (HCGroupPeer recipient : hcRows2)
        {
            HCGroupRecord memberGroup = HCLookGroup(recipient, hcPlayers);
            if (!memberGroup || memberGroup.Id != group.Id || memberGroup.Epoch != group.Epoch) { continue; }
            PlayerBase hcRecipientPlayer = HCPlayerOf(hcPlayers, recipient.Id);
            if (!hcRecipientPlayer) continue;
            PlayerIdentity hcRecipientIdentity;
            HCGroupPingWire frame = new HCGroupPingWire;
            frame.GroupId = group.Id;
            frame.Epoch = group.Epoch;
            frame.Session = recipient.Session;
            frame.Now = now;
            foreach (HCGroupPingRow point : groupPoints)
            {
                if (frame.Points.Count() >= 3) { break; }
                if (point.GroupId != group.Id || point.Epoch != group.Epoch) { continue; }
                if (vector.Distance(hcRecipientPlayer.GetPosition(), point.Point) > 1000) { continue; }
                frame.Points.Insert(point.Point);
                frame.Expires.Insert(point.Expires);
            }
            ScriptRPC rpc = new ScriptRPC;
            rpc.Write(frame);
            hcRecipientIdentity = hcRecipientPlayer.GetIdentity();
            if (!hcRecipientIdentity) continue;
            rpc.Send(null, HCGroupPingWire.RPC, true, hcRecipientIdentity);
        }
        return HCGroupCode.OK;
    }
    override void Stop(map<string, PlayerBase> hcPlayers)
    {
        m_HCLookPings.Clear();
        m_HCLookCooldowns.Clear();
        super.Stop(hcPlayers);
    }
}
