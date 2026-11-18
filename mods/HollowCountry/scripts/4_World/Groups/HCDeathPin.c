// Corpse-run pins, server-owned; no entity serialization or client requests.
// Installed scripts-1.30.164289 native evidence:
// 4_World/Entities/ManBase/PlayerBase.c:1214 EEKilled(Object killer),
// 3_Game/Entities/Man.c:21 GetIdentity; 3_Game/gameplay.c:362/368 GetName/GetId;
// 3_Game/Entities/Object.c:287 GetPosition; 3_Game/Global/Game.c:1120 IsServer;
// :934 GetWorldName;
// 1_Core/proto/EnScript.c:380/394/399/407/463 Count/Find/Get/Insert/Remove;
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

class HCDeathPins
{
    protected static const string PATH = "$profile:HollowCountry/Groups/death-pins.json";
    protected ref HCDeathPinState m_State;

    void HCDeathPins()
    {
        if (!GetGame() || !GetGame().IsServer()) { return; }
        string root = "$profile:HollowCountry";
        if (!FileExist(root) && !MakeDirectory(root)) { return; }
        root = root + "/Groups";
        if (!FileExist(root) && !MakeDirectory(root)) { return; }
        if (!HCRecoverPending() || (!FileExist(PATH) && FileExist(PATH + ".bak")))
        {
            Print("[HollowCountry] V2 map pins death recovery failed; preserved; death pins disabled");
            return;
        }
        if (FileExist(PATH))
        {
            HCDeathPinState loaded = HCReadState(PATH);
            if (!loaded)
            {
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
    }

    protected HCDeathPinState HCReadState(string path)
    {
        HCDeathPinState loaded;
        if (!HCGroupJson<HCDeathPinState>.Load(path, 131072, loaded)) { return null; }
        if (!loaded || !loaded.Rows || loaded.Rows.Count() > 256) { return null; }
        // Migrate only rows in this private death store, never arbitrary leads.
        foreach (HCDeathPinRow row : loaded.Rows)
        {
            if (!row || !row.Pin) { return null; }
            string oldId = row.Pin.Id;
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
            if (!HCReadState(PATH)) { return false; }
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
        array<string> seen = new array<string>;
        array<string> pinIds = new array<string>;
        foreach (HCDeathPinRow row : state.Rows)
        {
            if (!row || row.GroupId < 1 || !HCGroupRules.TextValid(row.PlayerId, 128, false)) { return false; }
            if (seen.Find(row.PlayerId) >= 0 || !HCGroupRules.PlaceValid(row.Pin)) { return false; }
            if (pinIds.Find(row.Pin.Id) >= 0) { return false; }
            if (row.Pin.Id.IndexOf("hc-death:") != 0 || row.Pin.HCPinExpiresUtc < 1) { return false; }
            seen.Insert(row.PlayerId);
            pinIds.Insert(row.Pin.Id);
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
            if (expired || row.PlayerId == replacedPlayer) { m_State.Rows.Remove(index); }
            index = index - 1;
        }
    }

    bool HCPublish(HCGroupRecord group, string uid, string playerName, vector position)
    {
        if (!m_State || !group || group.Members.Find(uid) < 0) { return false; }
        int now = HCGroupClock.Utc();
        if (!HCGroupRules.DeadlineFits(now, 7200) || now < 1) { return false; }
        if (m_State.NextId >= 1000000000) { return false; }
        HCDeathPinRow row = new HCDeathPinRow;
        row.GroupId = group.Id;
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

    void HCCollect(HCGroupRecord group, int cap, array<ref HCGroupPlace> output)
    {
        if (!m_State || !group || !output) { return; }
        int now = HCGroupClock.Utc();
        if (now < 1) { return; }
        HCPrune(now);
        foreach (HCDeathPinRow row : m_State.Rows)
        {
            if (output.Count() >= cap) { break; }
            if (row.GroupId != group.Id || group.Members.Find(row.PlayerId) < 0) { continue; }
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
        if (GetGame() && GetGame().IsServer())
        {
            HCGroupPins pins = HCGroupPins.Get();
            if (pins) { pins.HCPlayerFell(this); }
        }
        super.EEKilled(killer);
    }
}
