// Fix-round RPC native evidence, installed scripts-1.30.164289:
// 3_Game/gameplay.c:104-117 ScriptRPC/Send; 1_Core/proto/Serializer.c:57/58
// Write/Read; 3_Game/Global/Game.c:945 GetPlayers, :1120 IsServer;
// 3_Game/Entities/Man.c:21 GetIdentity. No client gameplay-state requests.
// LC-T107 / EXP-A5. Source authored against installed scripts-1.30.164289:
// 1_Core/proto/EnSystem.c:100 GetYearMonthDayUTC; EnMath.c:413 Round.
// 3_Game/Global/Game.c:930 GetObjectsAtPosition3D, :931 GetWorld, :945 GetPlayers,
// :1093 GetMission; Global/World.c:28 GetDate; gameplay.c:742 GetWorldData.
// 3_Game/WorldData.c:222 GetBaseEnvTemperatureAtObject; Entities/Object.c:287
// GetPosition, :467 GetType, :864 GetSelectionPositionMS, :873 ModelToWorld.
// 4_World/Entities/ItemBase/FireplaceBase/FireplaceIndoor.c:9-11 native hearth/
// chimney selection prefixes; Actions/SingleUse/ActionCreateIndoorFireplace.c:72
// (under 4_World/Classes/UserActionsComponent) reads fireplace_smoke + index.
// 1_Core/proto/EnScript.c:394 Find, :418 InsertAt, :470 RemoveOrdered.
// Also EnScript.c:380/385/407 Count/Clear/Insert; EnConvert.c:30 int.ToString,
// :210 vector.DistanceSq; EnMath3D.c:18 Vector; EnMath.c:553/566 Min/Max;
// EnString.c:240 IndexOf; EnDebug.c:96 Print; gameplay.c:636 GetGame.
// Repo helper HCGroupClock.CalendarUtc supplies checked calendar conversion.
// Preferences admit source by owner decision; EXP-A5 is logged, never qualified
// by this module. No persistence, loot or inventory changes.
// Client-only entity class declared in 4_World so native CreateLight can resolve
// it. Native: Entities/ScriptedLightBase/PointLightBase.c:1; ScriptedLightBase.c:
// 258/303 brightness/radius; PointLightBase/FireplaceLight.c:8-16 light setters.
// 3_Game/Entities/EntityLightSource.c:19/27/47/53/65 shadow/daylight/colours/flare.
class HCSignsWindowLight extends PointLightBase
{
    void HCSignsWindowLight()
    {
        // DuskOrNight owns the dusk boundary, including twilight before native
        // night-only lights become visible. The client removes this at dawn.
        SetVisibleDuringDaylight(true);
        SetRadiusTo(6.0);
        SetBrightnessTo(1.1);
        SetCastShadow(true);
        SetDiffuseColor(1.0, 0.64, 0.3);
        SetAmbientColor(1.0, 0.64, 0.3);
        SetFlareVisible(false);
    }
}

class HCSignsOfLife extends HCModule
{
    static const int MAX_LIT = 4;
    static const int MAX_SMOKE = 2;
    static const int MAX_FLIES = 6;
    static const int MAX_OBJECTS = 512;
    static const int MAX_FORCE_LIT = 24;
    static const float HOUSE_RADIUS = 125.0;
    static const float FLY_RADIUS = 25.0;
    static const float SCAN_SECONDS = 10.0;
    static const float COLD_C = 10.0;

    // Client-only received snapshot. No server ForceLit allocation or sink.
    // HCSignsHoldoutRPC owns the authoritative server snapshot separately.
    static ref array<vector> ForceLit;

    protected int m_Day = -1;
    protected int m_Area;
    protected int m_LitCount;
    protected int m_SmokeCount;
    protected bool m_Summarized;
    protected float m_Clock;
    protected ref array<Man> m_Viewers = new array<Man>;
    protected bool m_Started;
    protected ref HCOperationalStatus m_Operational = new HCOperationalStatus;

    override string GetName() { return "SignsOfLife"; }

    // Wave 16: cached readiness from the live started flag (never hard-coded).
    override HCOperationalStatus HCGetOperationalStatus()
    {
        HCModuleReadiness.HCDerive(m_Operational, m_Started, "", "", "signs_scan_started");
        return m_Operational;
    }
    override bool IsEnabled(HCSettings settings) { return settings && settings.EnableSignsOfLife; }

    override void OnStart(HCSettings settings)
    {
        Print(HCV2Admission.Line("SignsOfLife", true, "EXP-A5", HCV2Gates.Qualified("EXP-A5")));
        m_Day = -1;
        m_Clock = 60.0;
        m_Started = true;
    }

    static int RealDay()
    {
        int year, month, day;
        GetYearMonthDayUTC(year, month, day);
        int seconds = HCGroupClock.CalendarUtc(year, month, day, 0, 0, 0);
        if (seconds < 0) return -1;
        return seconds / 86400;
    }

    // Small non-overflowing integer mix of decimetre X/Z and UTC epoch day.
    // Y is deliberately excluded so terrain rounding cannot change a site.
    static int HouseHash(vector housePos, int day)
    {
        int x = Math.Round(housePos[0] * 10.0);
        int z = Math.Round(housePos[2] * 10.0);
        x = x % 65521;
        z = z % 65521;
        if (x < 0) x = x + 65521;
        if (z < 0) z = z + 65521;
        int date = day % 65521;
        if (date < 0) date = date + 65521;
        return (x * 31 + z * 17 + date * 13) % 65521;
    }

    static bool IsForced(vector housePos)
    {
        if (!HCSignsOfLife.ForceLit) { return false; }
        int examined = 0;
        foreach (vector forced : HCSignsOfLife.ForceLit)
        {
            if (examined >= HCSignsOfLife.MAX_FORCE_LIT) return false;
            examined = examined + 1;
            if (vector.DistanceSq(forced, housePos) < 0.01) return true;
        }
        return false;
    }

    // Eligibility is independent of observer and query order. Local selection
    // then ranks eligible sites and applies the hard per-area caps, forced first.
    static bool IsLit(vector housePos, int day)
    {
        if (day < 0) return false;
        if (HCSignsOfLife.IsForced(housePos)) return true;
        return HCSignsOfLife.HouseHash(housePos, day) % 16 < 3;
    }

    static bool IsSmoke(vector housePos, int day)
    {
        if (day < 0) return false;
        return HCSignsOfLife.HouseHash(housePos, day) % 8 == 0;
    }

    static bool CanAdd(int count, int cap)
    {
        return count >= 0 && count < cap;
    }

    static bool DuskOrNight()
    {
        int year, month, day, hour, minute;
        GetGame().GetWorld().GetDate(year, month, day, hour, minute);
        return hour >= 18 || hour < 7;
    }

    static bool Cold(Object viewer)
    {
        if (!GetGame().GetMission()) return false;
        WorldData climate = GetGame().GetMission().GetWorldData();
        if (!climate) return false;
        return climate.GetBaseEnvTemperatureAtObject(viewer) < COLD_C;
    }

    static bool HousePoints(Object house, out vector lamp, out vector chimney)
    {
        if (!house || !Building.Cast(house)) return false;
        // Residential houses only; never industrial chimneys or ruined shells.
        string kind = house.GetType();
        if (kind.IndexOf("Land_House_") != 0) return false;
        vector hearth = house.GetSelectionPositionMS("fireplace_point1");
        vector outlet = house.GetSelectionPositionMS("fireplace_smoke1");
        if (hearth == vector.Zero || outlet == vector.Zero) return false;
        // Interior room illumination through its windows, using a real hearth
        // anchor rather than guessed window memory points or fabricated heights.
        lamp = house.ModelToWorld(hearth + Vector(0, 1.0, 0));
        chimney = house.ModelToWorld(outlet);
        return true;
    }

    static bool Before(Object left, Object right, int day)
    {
        vector a = left.GetPosition();
        vector b = right.GetPosition();
        bool forcedA = IsForced(a);
        bool forcedB = IsForced(b);
        if (forcedA != forcedB) return forcedA;
        int rankA = HouseHash(a, day);
        int rankB = HouseHash(b, day);
        if (rankA != rankB) return rankA < rankB;
        if (a[0] != b[0]) return a[0] < b[0];
        if (a[2] != b[2]) return a[2] < b[2];
        return a[1] < b[1];
    }

    // Fixed-size ordered insertion: at most six comparisons, independent of
    // native query order within the bounded result prefix inspected below.
    static void Offer(array<Object> selected, Object source, int day, int cap)
    {
        if (selected.Find(source) >= 0) return;
        int slot = 0;
        while (slot < selected.Count())
        {
            if (Before(source, selected[slot], day)) break;
            slot = slot + 1;
        }
        if (slot >= cap) return;
        selected.InsertAt(source, slot);
        if (selected.Count() > cap) selected.RemoveOrdered(cap);
    }

    static void SelectHouses(Object viewer, int day, array<Object> lit, array<Object> smoke)
    {
        lit.Clear();
        smoke.Clear();
        if (!viewer || day < 0) return;
        ref array<Object> objects = new array<Object>;
        ref array<CargoBase> proxies = new array<CargoBase>;
        vector center = viewer.GetPosition();
        GetGame().GetObjectsAtPosition3D(center, HOUSE_RADIUS, objects, proxies);
        bool night = DuskOrNight();
        bool cold = Cold(viewer);
        int count = Math.Min(objects.Count(), MAX_OBJECTS);
        for (int i = 0; i < count; i++)
        {
            Object candidate = objects[i];
            vector lamp, chimney;
            if (!HousePoints(candidate, lamp, chimney)) continue;
            vector position = candidate.GetPosition();
            if (vector.DistanceSq(position, center) > HOUSE_RADIUS * HOUSE_RADIUS) continue;
            if (night && IsLit(position, day)) Offer(lit, candidate, day, MAX_LIT);
            if (cold && IsSmoke(position, day)) Offer(smoke, candidate, day, MAX_SMOKE);
        }
    }

    override void OnTick(float deltaTime)
    {
        m_Clock += deltaTime;
        if (m_Clock < 60.0) return;
        int today = RealDay();
        if (today < 0) return;
        if (today != m_Day)
        {
            m_Day = today;
            m_Area = 0;
            m_LitCount = 0;
            m_SmokeCount = 0;
            m_Summarized = false;
            m_Viewers.Clear();
            GetGame().GetPlayers(m_Viewers);
        }
        if (m_Summarized) { m_Clock = 0; return; }
        // Daily summary is a bounded sample of at most six player areas, one
        // query per tick. Counts are peak per-area policy slots in that sample,
        // never claims of effects observed or entities spawned on the server.
        if (m_Area < m_Viewers.Count() && m_Area < 6)
        {
            ref array<Object> lit = new array<Object>;
            ref array<Object> smoke = new array<Object>;
            SelectHouses(m_Viewers[m_Area], today, lit, smoke);
            m_LitCount = Math.Max(m_LitCount, lit.Count());
            m_SmokeCount = Math.Max(m_SmokeCount, smoke.Count());
            m_Area++;
            return;
        }
        string litSummary = "n/a day";
        if (DuskOrNight()) { litSummary = m_LitCount.ToString(); }
        Print("[HollowCountry] V2 signs of life day=" + m_Day.ToString() + " lit=" + litSummary + " smoke=" + m_SmokeCount.ToString() + " cap=" + MAX_LIT.ToString());
        m_Summarized = true;
        m_Clock = 0;
        m_Viewers.Clear();
    }

    override void OnStop()
    {
        m_Started = false;
        m_Viewers.Clear();
    }
}

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        Register(new HCSignsOfLife);
    }
}

// One-way server snapshot; no client requests, inventory or entity creation.
// Native scripts-1.30.164289: 3_Game/gameplay.c:104-117 ScriptRPC.Send;
// 1_Core/proto/Serializer.c:57 Write, :58 Read; 3_Game/Global/Game.c:945
// GetPlayers, :1120 IsServer; Entities/Man.c:21 GetIdentity;
// 1_Core/proto/EnScript.c:380/385/407 Count/Clear/Insert.
// 4853903 was unused in mods/ when assigned. Two-client acceptance pending.
class HCSignsHoldoutRPC
{
    static const int RPC_HOLDOUTS = 4853903;
    protected static ref array<vector> s_Occupied = new array<vector>;

    static void SendTo(PlayerIdentity identity, PlayerBase player)
    {
        if (!GetGame().IsServer() || !identity || !player) { return; }
        if (player.GetIdentity() != identity || s_Occupied.Count() > 24) { return; }
        ScriptRPC rpc = new ScriptRPC;
        rpc.Write(s_Occupied.Count());
        foreach (vector position : s_Occupied) { rpc.Write(position); }
        // Null target avoids waiting for the player entity to replicate.
        rpc.Send(null, RPC_HOLDOUTS, true, identity);
    }

    static void Publish(array<vector> positions)
    {
        if (!GetGame().IsServer() || !positions || positions.Count() > 24) { return; }
        bool changed = positions.Count() != s_Occupied.Count();
        for (int compareIndex = 0; compareIndex < positions.Count(); compareIndex++)
        {
            if (!HCWorldLimits.Position(positions[compareIndex])) { return; }
            if (!changed)
            {
                if (positions[compareIndex] != s_Occupied[compareIndex]) { changed = true; }
            }
        }
        if (!changed) { return; }
        s_Occupied.Clear();
        foreach (vector position : positions) { s_Occupied.Insert(position); }
        array<Man> players = new array<Man>;
        GetGame().GetPlayers(players);
        int playerCount = Math.Min(players.Count(), 90);
        for (int playerIndex = 0; playerIndex < playerCount; playerIndex++)
        {
            PlayerBase player = PlayerBase.Cast(players[playerIndex]);
            if (player) { SendTo(player.GetIdentity(), player); }
        }
        Print("[HollowCountry] V2 signs of life holdout snapshot=" + s_Occupied.Count().ToString());
    }
}
