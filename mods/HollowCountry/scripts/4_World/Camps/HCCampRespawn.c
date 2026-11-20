// #126. No periodic work. Per fresh-character request: <=32 camps, <=32 players,
// <=128 fire candidates, one local threat query (reject >128), <=16 safe positions.
// Cooldown validation/reservation: <=256 rows; no work on core ticks.
// Installed scripts-1.30.164289 native evidence:
// 3_Game/gameplay.c:636 GetGame; Global/Game.c:930 GetObjectsAtPosition3D, :945 GetPlayers, :1120 IsServer,
// :934 GetWorldName, :1176 SurfaceY, :1188 SurfaceGetNormal, :1196/1197 sea/pond,
// :1333 IsBoxColliding; Entities/Object.c:215/287/517 deletion/position/alive;
// Entities/Man.c:21 GetIdentity; gameplay.c:368 GetId;
// 1_Core/proto/EnMath.c:331/343 Sin/Cos; EnConvert.c:210 DistanceSq;
// EnMath3D.c:18 Vector; EnScript.c:94/380/394/399/407/470 Cast/Count/Find/Get/Insert/RemoveOrdered;
// EnSystem.c:397 FileExist; EnDebug.c:96 Print; EnConvert.c:30 ToString.
// Persistence uses existing HCV2ThreatStore (HCGroupIO bounded intent/readback).
// No living-character position writes, vanilla entity save fields or client data.
class HCCampRespawnUse
{
    string Account;
    int At;
}
class HCCampRespawnState
{
    int Version = 1;
    string WorldName;
    int SavedUtc;
    ref array<ref HCCampRespawnUse> Uses = new array<ref HCCampRespawnUse>;
}

class HCCampRespawnModule : HCModule
{
    protected static HCCampRespawnModule s_Instance;
    protected ref HCCampRespawnState m_State;
    protected bool m_AdmissionPrinted;
    protected ref HCOperationalStatus m_Status = new HCOperationalStatus;
    static const string PATH = "$profile:HollowCountry/camp-respawn.json";
    static HCCampRespawnModule Get() { return s_Instance; }
    override string GetName() { return "CampRespawn"; }
    override HCOperationalStatus HCGetOperationalStatus() { return m_Status; }
    // Start-time refusal: HC-1 reads the status, the log line is one boot line.
    // Reasons: clock_unavailable, store_unavailable, state_unreadable, state_invalid.
    void HCStartRefused(string reason)
    {
        m_Status.HCPublish("refused", reason);
        Print("[HollowCountry] W5 camp-respawn start refused reason=" + reason + "; vanilla fallback");
    }
    override bool IsEnabled(HCSettings settings)
    {
        if (!settings || !settings.EnableCampRespawn) { return false; }
        return settings.EnableCamps && settings.EnableGroups;
    }
    override void OnStart(HCSettings settings)
    {
        if (!IsEnabled(settings) || !GetGame().IsServer() || s_Instance) { return; }
        if (!m_AdmissionPrinted)
        {
            Print(HCV2Admission.Line("CampRespawn", true, "W5-126", false));
            m_AdmissionPrinted = true;
        }
        int now = HCGroupClock.Utc();
        if (now < 1)
        {
            HCStartRefused("clock_unavailable");
            return;
        }
        if (!HCV2ThreatStore<HCCampRespawnState>.CanOpen(PATH))
        {
            HCStartRefused("store_unavailable");
            return;
        }
        if (FileExist(PATH))
        {
            if (!HCV2ThreatStore<HCCampRespawnState>.Load(PATH, 65536, m_State))
            {
                HCStartRefused("state_unreadable");
                return;
            }
        }
        else
        {
            m_State = new HCCampRespawnState;
            m_State.WorldName = GetGame().GetWorldName();
            m_State.SavedUtc = now;
        }
        if (!HCValid(now))
        {
            m_State = null;
            HCStartRefused("state_invalid");
            return;
        }
        s_Instance = this;
        m_Status.HCPublish("ready", "cooldown_store_loaded_native_acceptance_pending");
        Print("[HollowCountry] W5 camp-respawn source ready; native acceptance pending");
    }
    protected bool HCValid(int now)
    {
        if (!m_State || m_State.Version != 1 || !m_State.Uses) { return false; }
        if (m_State.WorldName != GetGame().GetWorldName() || m_State.Uses.Count() > 256) { return false; }
        if (m_State.SavedUtc < 1 || m_State.SavedUtc > now) { return false; }
        array<string> accounts = new array<string>;
        foreach (HCCampRespawnUse row : m_State.Uses)
        {
            if (!row || !HCGroupRules.TextValid(row.Account, 128, false)) { return false; }
            if (row.At < 1 || row.At > now || accounts.Find(row.Account) >= 0) { return false; }
            accounts.Insert(row.Account);
        }
        return true;
    }
    // Called only by the fresh-character MissionServer path before CreatePlayer.
    bool HCChoose(PlayerIdentity identity, out vector position)
    {
        if (s_Instance != this || !identity || !GetGame().IsServer()) { return false; }
        int now = HCGroupClock.Utc();
        if (!HCValid(now))
        {
            s_Instance = null;
            m_Status.HCPublish("refused", "state_invalid");
            return false;
        }
        int last;
        HCCampRespawnUse previous;
        string account = identity.GetId();
        if (!HCGroupRules.TextValid(account, 128, false)) { return false; }
        foreach (HCCampRespawnUse row : m_State.Uses)
        {
            if (row.Account == account) { last = row.At; previous = row; }
        }
        HCCampModule camps = HCCampModule.Get();
        if (!camps || !camps.HCRespawnPosition(account, now, last, position)) { return false; }
        // Reserve durably before creation. A failed native CreatePlayer consumes
        // the reservation conservatively; never permit a restart cooldown bypass.
        for (int index = m_State.Uses.Count() - 1; index >= 0; index--)
        {
            HCCampRespawnUse expired = m_State.Uses.Get(index);
            if (expired != previous && now - expired.At >= 1800) { m_State.Uses.RemoveOrdered(index); }
        }
        if (!previous)
        {
            if (m_State.Uses.Count() >= 256) { return false; }
            previous = new HCCampRespawnUse;
            previous.Account = account;
            m_State.Uses.Insert(previous);
        }
        previous.At = now;
        m_State.SavedUtc = now;
        if (!HCV2ThreatStore<HCCampRespawnState>.Save(PATH, m_State, 65536))
        {
            s_Instance = null;
            m_Status.HCPublish("refused", "storage_fault");
            Print("[HollowCountry] W5 camp-respawn storage fault; vanilla fallback");
            return false;
        }
        Print("[HollowCountry] W5 camp-respawn reserved cooldown=1800 fresh-character-only=1");
        HCReached.Mark("camp_respawn.reserved");
        return true;
    }
    override void OnStop()
    {
        if (s_Instance == this) { s_Instance = null; }
        m_State = null;
        m_Status.HCStop();
    }
}

modded class HCGroupService
{
    string HCRespawnGroup(string account)
    {
        if (!m_Healthy || !m_State) { return ""; }
        HCGroupRecord group = HCGroupRules.FindGroup(m_State, account);
        if (!group) { return ""; }
        return group.Id.ToString();
    }
}

modded class HCCampModule
{
    bool HCRespawnPosition(string account, int now, int last, out vector position)
    {
        if (!m_Running || !m_Data) { return false; }
        HCGroupService groups = HCGroupService.Get();
        if (!groups) { return false; }
        string groupId = groups.HCRespawnGroup(account);
        if (groupId == "") { return false; }
        HCCampRecord selected;
        foreach (HCCampRecord camp : m_Data.Camps)
        {
            if (camp.GroupId == groupId) { selected = camp; break; }
        }
        if (!selected || !FireFor(selected)) { return false; }
        int liveTier = HCCampTiers.Decayed(selected.Tier, now, selected.LastLit);
        if (!HCCampTiers.HCRespawnEligible(liveTier, selected.ProbePhase > 0, now, last)) { return false; }
        // Re-read established native structures; stale stored tiers cannot admit.
        HCCampScan scan = HCCampScan.Read(selected.Position, false);
        if (!scan || !scan.Shelter || !scan.Storage) { return false; }
        foreach (HCCampRecord otherCamp : m_Data.Camps)
        {
            if (otherCamp.GroupId != groupId && vector.DistanceSq(otherCamp.Position, selected.Position) <= 10000) { return false; }
        }
        array<Man> players = new array<Man>;
        GetGame().GetPlayers(players);
        if (players.Count() > 32) { return false; }
        foreach (Man person : players)
        {
            PlayerBase player = PlayerBase.Cast(person);
            if (!player || !player.IsAlive()) { continue; }
            // Any existing living avatar for this identity refuses the shortcut.
            if (player.GetIdentity() && player.GetIdentity().GetId() == account) { return false; }
            if (vector.DistanceSq(player.GetPosition(), selected.Position) <= 10000 && GroupId(player) != groupId) { return false; }
        }
        array<Object> objects = new array<Object>;
        array<CargoBase> cargo = new array<CargoBase>;
        GetGame().GetObjectsAtPosition3D(selected.Position, 100, objects, cargo);
        if (objects.Count() > 128) { return false; }
        foreach (Object hazard : objects)
        {
            // Fail closed for nearby infected, animals and non-player AI men.
            bool creature = DayZInfected.Cast(hazard) || DayZAnimal.Cast(hazard);
            Man human = Man.Cast(hazard);
            if (creature && hazard.IsAlive()) { return false; }
            if (human && human.IsAlive() && !human.GetIdentity()) { return false; }
        }
        array<Object> excluded = new array<Object>;
        for (int attempt = 0; attempt < 16; attempt++)
        {
            float angle = attempt * 2.399963;
            float radius = 20 + attempt * 3;
            vector candidate = selected.Position + Vector(Math.Cos(angle) * radius, 0, Math.Sin(angle) * radius);
            candidate[1] = GetGame().SurfaceY(candidate[0], candidate[2]);
            if (!HCGroupRules.PositionValid(candidate)) { continue; }
            if (vector.DistanceSq(candidate, selected.Position) > 22500) { continue; }
            if (GetGame().SurfaceIsSea(candidate[0], candidate[2]) || GetGame().SurfaceIsPond(candidate[0], candidate[2])) { continue; }
            vector normal = GetGame().SurfaceGetNormal(candidate[0], candidate[2]);
            if (normal[1] < 0.9) { continue; }
            bool unsafe = false;
            foreach (Man observer : players)
            {
                PlayerBase outsider = PlayerBase.Cast(observer);
                if (!outsider || !outsider.IsAlive()) { continue; }
                if (GroupId(outsider) != groupId && vector.DistanceSq(outsider.GetPosition(), candidate) <= 10000) { unsafe = true; break; }
            }
            foreach (HCCampRecord neighbourCamp : m_Data.Camps)
            {
                if (neighbourCamp.GroupId != groupId && vector.DistanceSq(neighbourCamp.Position, candidate) <= 10000) { unsafe = true; break; }
            }
            if (unsafe) { continue; }
            if (GetGame().IsBoxColliding(candidate + Vector(0, 1.05, 0), vector.Zero, Vector(1.2, 2, 1.2), excluded)) { continue; }
            position = candidate + Vector(0, 0.1, 0);
            return true;
        }
        return false;
    }
}
modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        Register(new HCCampRespawnModule);
    }
}
