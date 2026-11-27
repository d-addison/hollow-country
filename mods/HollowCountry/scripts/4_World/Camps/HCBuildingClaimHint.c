// #239: the claim and release actions were offered on every lockpick door (car wrecks too),
// because the client preview skipped the server-only group and claim checks. The server
// condition then failed and the ring stopped with no message. The server now tells only
// the actor's own client whether its group may claim and which building the group holds.
// Preview only: HCBuildingClaim.HCRequest re-reads group, role and claim at completion and
// owns every refusal. The client never holds or sends claim or group state.
// Native scripts-1.30.164289: 3_Game/gameplay.c:104-117 ScriptRPC/Send;
// 1_Core/proto/Serializer.c:57-58 Write/Read; 3_Game/DayZGame.c:991 Event_OnRPC;
// 3_Game/Global/Game.c:1120 IsServer; 3_Game/Entities/Object.c:287/467 GetPosition/GetType;
// 3_Game/gameplay.c:368 GetId; 3_Game/Entities/Man.c:21 GetIdentity.
// RPC id check before assignment: rg -n --max-filesize 10M '4853921' mods found no match.
class HCBuildingClaimHint
{
    static const int RPC_HINT = 4853921;
    // Unchanged hints are resent this often so a reconnect or a lost packet heals.
    static const int RESEND_SECONDS = 30;
    protected static ref HCBuildingClaimHint s_Instance;
    protected bool m_Listening;
    protected bool m_Manager;
    protected bool m_Holds;
    protected string m_Type;
    protected vector m_Position;
    // Server: last hint text and online second sent, per identity id.
    protected ref map<string, string> m_SentKey = new map<string, string>;
    protected ref map<string, int> m_SentAt = new map<string, int>;
    protected ref map<int, ref HCBuildingClaimRecord> m_ByGroup = new map<int, ref HCBuildingClaimRecord>;

    static HCBuildingClaimHint Get()
    {
        if (!s_Instance) { s_Instance = new HCBuildingClaimHint; }
        return s_Instance;
    }

    void Start()
    {
        if (m_Listening || !GetGame() || GetGame().IsServer()) { return; }
        m_Listening = true;
        DayZGame.Event_OnRPC.Insert(OnRPC);
    }

    void Stop()
    {
        if (m_Listening) { DayZGame.Event_OnRPC.Remove(OnRPC); }
        m_Listening = false;
        m_Manager = false;
        m_Holds = false;
        m_Type = "";
    }

    // Client preview: Claim only for a group owner or officer whose group holds no claim;
    // Release only on the building the group holds.
    bool HCAllows(Building building, bool release)
    {
        if (!building || !m_Manager) { return false; }
        if (!release) { return !m_Holds; }
        if (!m_Holds || building.GetType() != m_Type) { return false; }
        return vector.DistanceSq(building.GetPosition(), m_Position) <= 0.25;
    }

    void OnRPC(PlayerIdentity sender, Object target, int rpcType, ParamsReadContext ctx)
    {
        if (rpcType != RPC_HINT || !m_Listening || sender || !ctx || GetGame().IsServer()) { return; }
        PlayerBase viewer = PlayerBase.Cast(GetGame().GetPlayer());
        if (!viewer || target != viewer) { return; }
        bool manager;
        bool holds;
        string type;
        vector position;
        if (!ctx.Read(manager) || !ctx.Read(holds) || !ctx.Read(type) || !ctx.Read(position)) { return; }
        if (type.Length() > 128) { return; }
        m_Manager = manager;
        m_Holds = holds;
        m_Type = type;
        m_Position = position;
    }

    // Group id -> its claim row, rebuilt once per round (a group holds at most one claim).
    void HCIndex(array<ref HCBuildingClaimRecord> claims)
    {
        m_ByGroup.Clear();
        if (!claims) { return; }
        foreach (HCBuildingClaimRecord row : claims)
        {
            if (row) { m_ByGroup.Set(row.GroupId, row); }
        }
    }

    // Server: one hint per online player, sent when it changes or every RESEND_SECONDS.
    // Bounded by the caller's player cap; each player costs one group lookup and one map read.
    // Call HCIndex first in the same round.
    void HCSend(PlayerBase player, HCGroupService groups, int onlineSeconds, bool force, map<string, PlayerBase> hcPlayers)
    {
        if (!player || !player.GetIdentity() || !groups) { return; }
        int groupId = groups.HCClaimActorGroup(player, true, hcPlayers);
        bool manager = groupId > 0;
        bool holds = false;
        string type = "";
        vector position = "0 0 0";
        HCBuildingClaimRecord row;
        if (manager) { row = m_ByGroup.Get(groupId); }
        if (row)
        {
            holds = true;
            position = row.Position;
            type = HCTypeOf(row.BuildingId);
        }
        string key = groupId.ToString() + "|" + type + "|" + position.ToString();
        string uid = player.GetIdentity().GetId();
        if (!force && m_SentKey.Get(uid) == key && onlineSeconds - m_SentAt.Get(uid) < RESEND_SECONDS) { return; }
        m_SentKey.Set(uid, key);
        m_SentAt.Set(uid, onlineSeconds);
        ScriptRPC rpc = new ScriptRPC;
        rpc.Write(manager);
        rpc.Write(holds);
        rpc.Write(type);
        rpc.Write(position);
        rpc.Send(player, RPC_HINT, true, player.GetIdentity());
    }

    // Drop rows for players who left; bounded by the online player cap.
    void HCPrune(array<Man> people)
    {
        if (m_SentKey.Count() <= people.Count()) { return; }
        m_SentKey.Clear();
        m_SentAt.Clear();
    }

    // BuildingId is world:type:x:y:z:yaw:pitch:roll (HCBuildingClaim.HCIdentity).
    static string HCTypeOf(string buildingId)
    {
        array<string> parts = new array<string>();
        buildingId.Split(":", parts);
        if (parts.Count() != 8) { return ""; }
        return parts[1];
    }
}
