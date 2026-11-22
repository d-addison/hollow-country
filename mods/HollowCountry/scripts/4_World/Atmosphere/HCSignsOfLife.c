// Native scripts-1.30.164289: 1_Core/proto/EnSystem.c:397 FileExist;
// 3_Game/tools/JsonFileLoader.c:69 LoadData; EnDebug.c:96 Print.
// EnConvert.c:30,115 int/float.ToString; EnDebug.c:96 Print.
// Bounded HCGroupIO read; absent/invalid fields retain constructor defaults.
class HCSignsConfig
{
    int MaxFlies = 6;
    int MaxObjects = 512;
    int MaxForceLit = 24;
    float HouseRadius = 125;
    float FlyRadius = 25;
    float ScanSeconds = 10;
    float ColdC = 10;
    float SummarySeconds = 60;
    int SummaryAreas = 6;
    int SnapshotPlayers = 90;
    protected static ref HCSignsConfig s_Config;
    static HCSignsConfig HCGet()
    {
        if (s_Config) { return s_Config; }
        HCOperatorSettingsRegistry.HCLocalPolicyInit();
        s_Config = new HCSignsConfig;
        string path = "$profile:HollowCountry/signs-of-life.json";
        if (FileExist(path))
        {
            string text;
            string error;
            HCSignsConfig decoded;
            if (HCGroupIO.Read(path, 4096, text) && JsonFileLoader<HCSignsConfig>.LoadData(text, decoded, error) && decoded)
                s_Config.HCApply(decoded, text);
            else
                Print("[HC Config] HCSignsConfig invalid_json defaults_restored runtime=PENDING");
        }
        Print("[HC Config] HCSignsConfig objects=" + s_Config.MaxObjects.ToString() + " flies=" + s_Config.MaxFlies.ToString() + " forced=" + s_Config.MaxForceLit.ToString() + " runtime=PENDING");
        Print("[HC Config] HCSignsConfig house_m=" + s_Config.HouseRadius.ToString() + " fly_m=" + s_Config.FlyRadius.ToString() + " scan_s=" + s_Config.ScanSeconds.ToString() + " runtime=PENDING");
        Print("[HC Config] HCSignsConfig summary_s=" + s_Config.SummarySeconds.ToString() + " areas=" + s_Config.SummaryAreas.ToString() + " cold_c=" + s_Config.ColdC.ToString() + " players=" + s_Config.SnapshotPlayers.ToString() + " runtime=PENDING");
        return s_Config;
    }
    void HCApply(HCSignsConfig decoded, string text)
    {
        if (HCJsonFields.Has(text, "MaxFlies"))
        {
            if (HCOperatorSettingsRegistry.HCValid("SignsOfLife.MaxFlies", decoded.MaxFlies)) { MaxFlies = decoded.MaxFlies; }
            else { Print("[HC Config] SignsOfLife.MaxFlies invalid_range default_retained runtime=PENDING"); }
        }
        if (HCJsonFields.Has(text, "MaxObjects"))
        {
            if (HCOperatorSettingsRegistry.HCValid("SignsOfLife.MaxObjects", decoded.MaxObjects)) { MaxObjects = decoded.MaxObjects; }
            else { Print("[HC Config] SignsOfLife.MaxObjects invalid_range default_retained runtime=PENDING"); }
        }
        if (HCJsonFields.Has(text, "MaxForceLit"))
        {
            if (HCOperatorSettingsRegistry.HCValid("SignsOfLife.MaxForceLit", decoded.MaxForceLit)) { MaxForceLit = decoded.MaxForceLit; }
            else { Print("[HC Config] SignsOfLife.MaxForceLit invalid_range default_retained runtime=PENDING"); }
        }
        if (HCJsonFields.Has(text, "HouseRadius"))
        {
            if (HCOperatorSettingsRegistry.HCValid("SignsOfLife.HouseRadius", decoded.HouseRadius)) { HouseRadius = decoded.HouseRadius; }
            else { Print("[HC Config] SignsOfLife.HouseRadius invalid_range default_retained runtime=PENDING"); }
        }
        if (HCJsonFields.Has(text, "FlyRadius"))
        {
            if (HCOperatorSettingsRegistry.HCValid("SignsOfLife.FlyRadius", decoded.FlyRadius)) { FlyRadius = decoded.FlyRadius; }
            else { Print("[HC Config] SignsOfLife.FlyRadius invalid_range default_retained runtime=PENDING"); }
        }
        if (HCJsonFields.Has(text, "ScanSeconds"))
        {
            if (HCOperatorSettingsRegistry.HCValid("SignsOfLife.ScanSeconds", decoded.ScanSeconds)) { ScanSeconds = decoded.ScanSeconds; }
            else { Print("[HC Config] SignsOfLife.ScanSeconds invalid_range default_retained runtime=PENDING"); }
        }
        if (HCJsonFields.Has(text, "ColdC"))
        {
            if (HCOperatorSettingsRegistry.HCValid("SignsOfLife.ColdC", decoded.ColdC)) { ColdC = decoded.ColdC; }
            else { Print("[HC Config] SignsOfLife.ColdC invalid_range default_retained runtime=PENDING"); }
        }
        if (HCJsonFields.Has(text, "SummarySeconds"))
        {
            if (HCOperatorSettingsRegistry.HCValid("SignsOfLife.SummarySeconds", decoded.SummarySeconds)) { SummarySeconds = decoded.SummarySeconds; }
            else { Print("[HC Config] SignsOfLife.SummarySeconds invalid_range default_retained runtime=PENDING"); }
        }
        if (HCJsonFields.Has(text, "SummaryAreas"))
        {
            if (HCOperatorSettingsRegistry.HCValid("SignsOfLife.SummaryAreas", decoded.SummaryAreas)) { SummaryAreas = decoded.SummaryAreas; }
            else { Print("[HC Config] SignsOfLife.SummaryAreas invalid_range default_retained runtime=PENDING"); }
        }
        if (HCJsonFields.Has(text, "SnapshotPlayers"))
        {
            if (HCOperatorSettingsRegistry.HCValid("SignsOfLife.SnapshotPlayers", decoded.SnapshotPlayers)) { SnapshotPlayers = decoded.SnapshotPlayers; }
            else { Print("[HC Config] SignsOfLife.SnapshotPlayers invalid_range default_retained runtime=PENDING"); }
        }
    }
}

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
// W69: fireplace presentation is entirely native (HCHearthFires.c evidence).
// Occupied holdout snapshots are ordering hints and cannot create a light/fire.
class HCSignsOfLife extends HCModule
{
    static int MAX_FLIES = 6;
    static int MAX_OBJECTS = 512;
    static int MAX_FORCE_LIT = 24;
    static float HOUSE_RADIUS = 125;
    static float FLY_RADIUS = 25;
    static float SCAN_SECONDS = 10;
    static float COLD_C = 10;

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
        HCApplySettings();
        HCHearthFires.HCStart();
        m_Day = -1;
        m_Clock = HCSignsConfig.HCGet().SummarySeconds;
        m_Started = true;
    }

    static void HCApplySettings()
    {
        HCSignsConfig config = HCSignsConfig.HCGet();
        HCSignsOfLife.MAX_FLIES = config.MaxFlies;
        HCSignsOfLife.MAX_OBJECTS = config.MaxObjects;
        HCSignsOfLife.MAX_FORCE_LIT = config.MaxForceLit;
        HCSignsOfLife.HOUSE_RADIUS = config.HouseRadius;
        HCSignsOfLife.FLY_RADIUS = config.FlyRadius;
        HCSignsOfLife.SCAN_SECONDS = config.ScanSeconds;
        HCSignsOfLife.COLD_C = config.ColdC;
    }

    static int RealDay()
    {
        HCApplySettings();
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
        array<vector> forcedPositions = HCSignsOfLife.ForceLit;
        foreach (vector forced : forcedPositions)
        {
            if (examined >= HCSignsOfLife.MAX_FORCE_LIT) return false;
            examined = examined + 1;
            if (vector.DistanceSq(forced, housePos) < 0.01) return true;
        }
        return false;
    }

    // Occupancy and the daily hash never establish a burning hearth. The hash
    // remains a deterministic ordering aid only; native fires own all visuals.
    static bool IsLit(Object house, int day)
    {
        return HCHearthFires.HCHasBurning(house);
    }

    static bool IsSmoke(Object house, int day)
    {
        return HCHearthFires.HCHasBurning(house);
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
        return climate.GetBaseEnvTemperatureAtObject(viewer) < HCSignsOfLife.COLD_C;
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

    // Fixed-size ordered insertion bounded by the caller cap, independent of
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
        HCApplySettings();
        lit.Clear();
        smoke.Clear();
        if (!viewer || day < 0) return;
        ref array<Object> objects = new array<Object>;
        ref array<CargoBase> proxies = new array<CargoBase>;
        vector center = viewer.GetPosition();
        GetGame().GetObjectsAtPosition3D(center, HCSignsOfLife.HOUSE_RADIUS, objects, proxies);
        bool night = DuskOrNight();
        bool cold = Cold(viewer);
        int count = Math.Min(objects.Count(), HCSignsOfLife.MAX_OBJECTS);
        HCWorkBudget houseBudget = new HCPerfSlices("SignsHearths");
        houseBudget.HCReset(HCHearthConfig.HCGet().HousesPerScan);
        int housesExamined = 0;
        for (int i = 0; i < count; i++)
        {
            Object candidate = objects[i];
            vector lamp, chimney;
            if (!HousePoints(candidate, lamp, chimney)) continue;
            vector position = candidate.GetPosition();
            if (vector.DistanceSq(position, center) > HCSignsOfLife.HOUSE_RADIUS * HCSignsOfLife.HOUSE_RADIUS) continue;
            if (housesExamined >= HCHearthConfig.HCGet().HousesPerScan) { break; }
            if (!houseBudget.HCContinue()) { break; }
            if (GetGame().IsServer() && !HCServer.HCTickWork().HCTakeFor(HCUnitBudget.HC_WORK_SIGNS_OF_LIFE, 1)) { break; }
            housesExamined = housesExamined + 1;
            if (night && IsLit(candidate, day)) Offer(lit, candidate, day, HCHearthConfig.HCGet().MaxLit);
            if (cold && IsSmoke(candidate, day)) Offer(smoke, candidate, day, HCHearthConfig.HCGet().MaxSmoke);
        }
    }

    override void OnTick(float deltaTime)
    {
        if (!m_Started) { return; }
        HCHearthFires.HCTick();
        m_Clock += deltaTime;
        if (m_Clock < HCSignsConfig.HCGet().SummarySeconds) return;
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
        // Daily summary is a bounded sample of configured player areas, one
        // query per tick. Counts are peak per-area policy slots in that sample,
        // never claims of effects observed or entities spawned on the server.
        if (m_Area < m_Viewers.Count() && m_Area < HCSignsConfig.HCGet().SummaryAreas)
        {
            ref array<Object> lit = new array<Object>;
            ref array<Object> smoke = new array<Object>;
            SelectHouses(m_Viewers[m_Area], today, lit, smoke);
            HCReached.Mark("signs_of_life.area_sample");
            m_LitCount = Math.Max(m_LitCount, lit.Count());
            m_SmokeCount = Math.Max(m_SmokeCount, smoke.Count());
            m_Area++;
            return;
        }
        string litSummary = "n/a day";
        if (DuskOrNight()) { litSummary = m_LitCount.ToString(); }
        Print("[HollowCountry] V2 signs of life day=" + m_Day.ToString() + " lit=" + litSummary + " smoke=" + m_SmokeCount.ToString() + " cap=" + HCHearthConfig.HCGet().MaxLit.ToString());
        m_Summarized = true;
        m_Clock = 0;
        m_Viewers.Clear();
    }

    override void OnStop()
    {
        m_Started = false;
        HCHearthFires.HCStop();
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
// 3_Game/Entities/Object.c:287 GetPosition;
// 1_Core/proto/EnConvert.c:210 vector.DistanceSq.
// 4853903 was unused in mods/ when assigned. Two-client acceptance pending.
class HCSignsHoldoutRPC
{
    static const int RPC_HOLDOUTS = 4853903;
    protected static ref array<vector> s_Occupied = new array<vector>;

    static void SendTo(PlayerIdentity identity, PlayerBase player)
    {
        if (!GetGame().IsServer() || !identity || !player) { return; }
        if (player.GetIdentity() != identity || s_Occupied.Count() > 24) { return; }
        // Same ambience radius as client house scans, with a 25 m edge margin.
        // Filter before serialization; remote house coordinates never go on wire.
        float radius = HCSignsConfig.HCGet().HouseRadius + 25.0;
        vector center = player.GetPosition();
        array<vector> nearby = new array<vector>;
        array<vector> occupied = s_Occupied;
        foreach (vector position : occupied)
        {
            if (vector.DistanceSq(position, center) <= radius * radius) { nearby.Insert(position); }
        }
        ScriptRPC rpc = new ScriptRPC;
        // An empty snapshot explicitly clears positions from the previous area.
        rpc.Write(nearby.Count());
        foreach (vector nearbyPosition : nearby) { rpc.Write(nearbyPosition); }
        // Null target avoids waiting for the player entity to replicate.
        rpc.Send(null, HCSignsHoldoutRPC.RPC_HOLDOUTS, true, identity);
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
        if (changed)
        {
            s_Occupied.Clear();
            foreach (vector position : positions) { s_Occupied.Insert(position); }
        }
        // Refresh on every publish even if occupancy is unchanged: recipients
        // can move into/out of range. Work stays <=24 positions per capped peer.
        array<Man> players = new array<Man>;
        GetGame().GetPlayers(players);
        int playerCount = Math.Min(players.Count(), HCSignsConfig.HCGet().SnapshotPlayers);
        for (int playerIndex = 0; playerIndex < playerCount; playerIndex++)
        {
            PlayerBase player = PlayerBase.Cast(players[playerIndex]);
            if (player) { SendTo(player.GetIdentity(), player); }
        }
        if (changed) { Print("[HollowCountry] V2 signs of life holdout snapshot=" + s_Occupied.Count().ToString()); }
    }
}
