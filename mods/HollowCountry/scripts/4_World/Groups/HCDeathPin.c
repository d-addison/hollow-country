// Entry-local roster port: native scripts-1.30.164289 3_Game/Global/Game.c:945;
// resolver identity/life: Entities/Man.c:21, gameplay.c:368, Entities/Object.c:517.
// HC-26: membership-epoch receipts, bounded lifecycle purge; runtime PENDING.
// Corpse-run pins, server-owned; no entity serialization or client requests.
// Installed scripts-1.30.164289 native evidence:
// 4_World/Entities/ManBase/PlayerBase.c:1214 EEKilled(Object killer),
// 3_Game/Entities/Man.c:21 GetIdentity; 3_Game/gameplay.c:362/368 GetName/GetId;
// 3_Game/Entities/Object.c:287 GetPosition; 3_Game/Global/Game.c:1120 IsServer;
// :934 GetWorldName; :914 GetTickTime;
// 1_Core/proto/EnScript.c:380/394/399/407/463/470 Count/Find/Get/Insert/Remove/RemoveOrdered;
// 1_Core/proto/EnSystem.c:397/525/528/531 FileExist/MakeDirectory/DeleteFile/CopyFile;
// :417/425/443/462 OpenFile/ReadFile/CloseFile/FPrint (via HCGroupIO).
// 1_Core/proto/EnString.c:113/199/240 Substring/Length/IndexOf;
// 3_Game/tools/JsonFileLoader.c:69/85 LoadData/MakeData (via shared stores);
// 1_Core/proto/EnConvert.c:30 ToString.
// 1_Core/proto/EnDebug.c:96 Print.
// HCGroupClock supplies checked UTC; HCGroupJson supplies bounded profile reads.
// Reuse the existing expiry-aware Places channel with a distinct hc-death kind;
// HCGroupPins filters
// by group id AND current membership. Its existing client renderer expires
// these pins even if no further snapshot arrives. No new RPC or client state.
class HCDeathPinRow
{
    int GroupId;
    // Zero is a legacy receipt with unknown membership; never presented.
    int Epoch;
    string PlayerId;
    ref HCGroupPlace Pin;
}

class HCDeathPinState
{
    int Version = 1;
    string WorldName;
    int NextId = 1;
    ref array<ref HCDeathPinRow> Rows = new array<ref HCDeathPinRow>;
}

// Managed: the static s_Instance auto-nulls if the owning ref is replaced without HCStop.
class HCDeathPins : Managed
{
    protected string m_StatusLogLine;
    protected float m_StatusLogAt;
    protected static const string PATH = "$profile:HollowCountry/Groups/death-pins.json";
    protected ref HCDeathPinState m_State;
    protected static HCDeathPins s_Instance;
    protected ref HCWorkBudget m_Work = new HCWorkBudget;
    protected ref HCUnitBudget m_Units = new HCUnitBudget;
    protected int m_PruneCursor;
    protected int m_Expired;
    protected string m_LastRefusal = "none";
    static HCDeathPins Get() { return s_Instance; }

    void HCDeathPins()
    {
        if (!GetGame() || !GetGame().IsServer()) { return; }
        string root = "$profile:HollowCountry";
        if (!FileExist(root) && !MakeDirectory(root)) { return; }
        root = root + "/Groups";
        if (!FileExist(root) && !MakeDirectory(root)) { return; }
        if (!HCRecoverPending() || (!FileExist(PATH) && FileExist(PATH + ".bak")))
        {
            HCLog("death_store_recovery");
            Print("[HollowCountry] V2 map pins death recovery failed; preserved; death pins disabled");
            return;
        }
        if (FileExist(PATH))
        {
            HCDeathPinState loaded = HCReadState(PATH);
            if (!loaded)
            {
                HCLog("death_store_invalid");
                Print("[HollowCountry] V2 map pins death store invalid; preserved; death pins disabled");
                return;
            }
            m_State = loaded;
        }
        else
        {
            m_State = new HCDeathPinState;
            m_State.WorldName = GetGame().GetWorldName();
        }
        s_Instance = this;
        HCLog("none");
    }

    protected HCDeathPinState HCReadState(string path)
    {
        ref HCDeathPinState loaded = new HCDeathPinState;
        string text;
        string error;
        // Same bounded read and validation as HCGroupJson.Load; no native out chain.
        // Native scripts-1.30.164289: 3_Game/gameplay.c:100 ReadFromString.
        JsonSerializer js = new JsonSerializer;
        if (!HCGroupIO.Read(path, 131072, text) || !js.ReadFromString(loaded, text, error)) { return null; }
        if (!loaded || !loaded.Rows || loaded.Rows.Count() > 256) { return null; }
        // Migrate only rows in this private death store, never arbitrary leads.
        array<ref HCDeathPinRow> hcRows1 = loaded.Rows;
        foreach (HCDeathPinRow row : hcRows1)
        {
            if (!row || !row.Pin) { return null; }
            string oldId = row.Pin.Id;
            // Place ids are at most 128 characters (PlaceValid), so a longer id was already refused.
            if (oldId.Length() > 1024) { return null; }
            if (oldId.IndexOf("hc-lead:death:") == 0)
            {
                row.Pin.Id = "hc-death:" + oldId.Substring(14, oldId.Length() - 14);
            }
        }
        if (!HCValidState(loaded)) { return null; }
        return loaded;
    }

    protected bool HCRecoverPending()
    {
        string temporary = PATH + ".tmp";
        if (!FileExist(temporary)) { return true; }
        HCDeathPinState staged = HCReadState(temporary);
        if (!staged)
        {
            // An interrupted staging write has not touched the live image.
            // Preserve malformed evidence unless the primary is still valid.
            HCDeathPinState primary = HCReadState(PATH);
            if (!primary) { return false; }
            return DeleteFile(temporary);
        }
        // HCV2ThreatStore retains the verified intent until promotion/readback
        // completes. Retry a partial promotion from that validated image.
        // Native CopyFile is NOT an atomic rename or an fsync guarantee.
        string expected;
        string actual;
        if (!HCGroupIO.Read(temporary, 131072, expected)) { return false; }
        if (FileExist(PATH) && !DeleteFile(PATH)) { return false; }
        if (!CopyFile(temporary, PATH)) { return false; }
        if (!HCGroupIO.Read(PATH, 131072, actual) || actual != expected) { return false; }
        return DeleteFile(temporary);
    }

    protected bool HCValidState(HCDeathPinState state)
    {
        if (!state || state.Version != 1 || !state.Rows) { return false; }
        if (state.WorldName != GetGame().GetWorldName()) { return false; }
        if (state.NextId < 1 || state.NextId > 1000000000 || state.Rows.Count() > 256) { return false; }
        map<string, bool> seen = new map<string, bool>;
        map<string, bool> pinIds = new map<string, bool>;
        array<ref HCDeathPinRow> hcRows2 = state.Rows;
        foreach (HCDeathPinRow row : hcRows2)
        {
            if (!row || row.GroupId < 1 || !HCGroupRules.TextValid(row.PlayerId, 128, false)) { return false; }
            if (row.Epoch < 0 || row.Epoch > 1000000000) { return false; }
            if (seen.Contains(row.PlayerId) || !HCGroupRules.PlaceValid(row.Pin)) { return false; }
            if (pinIds.Contains(row.Pin.Id)) { return false; }
            if (row.Pin.Id.IndexOf("hc-death:") != 0 || row.Pin.HCPinExpiresUtc < 1) { return false; }
            seen.Set(row.PlayerId, true);
            pinIds.Set(row.Pin.Id, true);
        }
        return true;
    }

    protected void HCPrune(int now, string replacedPlayer = "")
    {
        int index = m_State.Rows.Count() - 1;
        while (index >= 0)
        {
            HCDeathPinRow row = m_State.Rows.Get(index);
            bool expired = row.Pin.HCPinExpiresUtc <= now;
            if (expired || row.PlayerId == replacedPlayer)
            {
                m_State.Rows.Remove(index);
                if (m_Expired < 1000000) { m_Expired++; }
            }
            index = index - 1;
        }
    }

    // Called by existing membership/disconnect/refresh Broadcast, no new tick.
    // Deferred cleanup never grants permission: HCCollect checks epoch again.
    void HCInvalidate(map<string, PlayerBase> hcPlayers)
    {
        if (!m_State) { return; }
        HCGroupService service = HCGroupService.Get();
        m_Work.HCReset(32);
        m_Units.HCReset(32);
        int remaining = m_State.Rows.Count();
        int now = HCGroupClock.Utc();
        while (remaining > 0 && m_Work.HCContinue() && m_Units.HCTake(1))
        {
            if (m_PruneCursor >= m_State.Rows.Count()) { m_PruneCursor = 0; }
            HCDeathPinRow row = m_State.Rows.Get(m_PruneCursor);
            remaining--;
            HCGroupRecord group;
            if (service) { group = service.HCPresentationGroup(row.PlayerId); }
            if (!group || group.Id != row.GroupId || group.Epoch != row.Epoch || now < 1 || row.Pin.HCPinExpiresUtc <= now)
            {
                m_State.Rows.RemoveOrdered(m_PruneCursor);
                if (m_Expired < 1000000) { m_Expired++; }
                continue;
            }
            m_PruneCursor++;
        }
        // Read-side pruning is ephemeral; next real death barrier persists it.
        // Old disk receipts still fail epoch/TTL checks after restart.
        HCLog("none");
    }
    void HCLog(string reason)
    {
        if (reason != "none") { m_LastRefusal = reason; }
        float now = GetGame().GetTickTime();
        string state = "ready";
        if (!m_State) { state = "refused"; }
        string statusLine = "[HC Plan] HC-26 group_recipients=0 expired=" + m_Expired.ToString() + " refused=" + m_LastRefusal + " state=" + state + " component=death_pins runtime=PENDING";
        // First receipt, changed content, or one unchanged heartbeat per 30 minutes.
        float statusNow = now;
        if (statusLine != m_StatusLogLine || statusNow < m_StatusLogAt || statusNow - m_StatusLogAt >= 1800)
        {
            Print("" + statusLine);
            m_StatusLogLine = statusLine;
            m_StatusLogAt = statusNow;
        }
        m_LastRefusal = "none";
    }
    void HCStop()
    {
        if (s_Instance == this) { s_Instance = null; }
        m_State = null;
    }

    bool HCPublish(HCGroupRecord group, string uid, string playerName, vector position)
    {
        if (!m_State || !group || group.Members.Find(uid) < 0) { return false; }
        int now = HCGroupClock.Utc();
        if (!HCGroupRules.DeadlineFits(now, 7200) || now < 1) { return false; }
        if (m_State.NextId >= 1000000000) { return false; }
        HCDeathPinRow row = new HCDeathPinRow;
        row.GroupId = group.Id;
        row.Epoch = group.Epoch;
        row.PlayerId = uid;
        row.Pin = new HCGroupPlace;
        row.Pin.Id = "hc-death:" + m_State.NextId.ToString();
        row.Pin.Name = "Where " + playerName + " fell";
        // Native names are untrusted display text; retain the wire bound.
        if (!HCGroupRules.TextValid(row.Pin.Name, 64, false)) { row.Pin.Name = "Where a group member fell"; }
        row.Pin.Position = position;
        row.Pin.Radius = 40;
        row.Pin.HCPinExpiresUtc = now + 7200;
        if (!HCGroupRules.PlaceValid(row.Pin)) { return false; }
        HCPrune(now, uid);
        if (m_State.Rows.Count() >= 256) { return false; }
        m_State.Rows.Insert(row);
        m_State.NextId = m_State.NextId + 1;
        if (!HCRecoverPending() || !HCV2ThreatStore<HCDeathPinState>.Save(PATH, m_State, 131072))
        {
            Print("[HollowCountry] V2 map pins death save failed; current pin remains session-only; preserve pending files");
        }
        return true;
    }

    void HCCollect(HCGroupRecord group, int cap, array<ref HCGroupPlace> output, map<string, PlayerBase> hcPlayers)
    {
        if (!m_State || !group || !output || cap < 1) { return; }
        int now = HCGroupClock.Utc();
        if (now < 1) { return; }
        HCPrune(now);
        HCGroupStringIndex members = new HCGroupStringIndex(group.Members);
        array<ref HCDeathPinRow> hcRows3 = m_State.Rows;
        foreach (HCDeathPinRow row : hcRows3)
        {
            if (output.Count() >= cap) { break; }
            if (row.GroupId != group.Id || row.Epoch != group.Epoch || !members.Has(row.PlayerId)) { continue; }
            if (HCGroupVisibility.HCSnapshotActive())
            {
                HCGroupService service = HCGroupService.Get();
                if (!service || !service.HCPresentationAllows(HCGroupVisibility.HCRecipient(), row.Pin, hcPlayers)) { continue; }
            }
            output.Insert(row.Pin);
        }
    }
}

modded class PlayerBase
{
    override void EEKilled(Object killer)
    {
        // Match the existing Ecology hook's before-super observation pattern:
        // retain identity before native corpse/mission cleanup runs.
        // Both handlers need an identity; skip the roster build for AI and logged-out bodies.
        PlayerIdentity hcFellIdentity = GetIdentity();
        if (GetGame() && GetGame().IsServer() && hcFellIdentity)
        {
            map<string, PlayerBase> hcPlayers = HCGroupService.HCBuildPlayers();
            HCGroupService groups = HCGroupService.Get();
            if (groups) { groups.HCPresentationFell(this, hcPlayers); }
            HCGroupPins pins = HCGroupPins.Get();
            if (pins) { pins.HCPlayerFell(this, hcPlayers); }
        }
        super.EEKilled(killer);
    }
}

// Reuse existing module stop and group replacement frames; Groups can remain on.
modded class HCGroupPins
{
    override void OnStop()
    {
        map<string, PlayerBase> hcPlayers = HCGroupService.HCBuildPlayers();
        if (m_DeathPins) { m_DeathPins.HCStop(); }
        super.OnStop();
        HCGroupService groups = HCGroupService.Get();
        if (groups) { groups.Broadcast(hcPlayers); }
    }
}
