// #118 settlement decay. Native references in scripts-1.30.164289:
// 3_Game/Global/Game.c:612 ConfigIsExisting, :703 CreateObjectEx, :705
// ObjectDelete, :930 GetObjectsAtPosition3D, :945 GetPlayers, :1176 SurfaceY,
// :1180 SurfaceGetType, :1196/1197 water veto, :934 GetWorldName;
// 3_Game/Entities/Object.c:287 GetPosition, :358 ClippingInfo;
// 3_Game/CE/CentralEconomy.c:9,28,30,31 setup/height/lifetime/no-persistence.
// 1_Core/proto/EnScript.c:380,385,407 arrays; EnMath.c:225,553,566
// AbsFloat/Min/Max; EnConvert.c:30,210 int.ToString/vector.DistanceSq;
// EnString.c:171,240 ToLower/IndexOf; EnDebug.c:96 Print.
// Persistence reuses HCV2ThreatStore: EnSystem.c:397,417,425,443,462,525,
// 528,531 and JsonFileLoader.c:69,85. No native rename exists: retained temp
// intent + verified backup/copy, NOT OS-atomic rename. Interrupted load closes.
// No game assets, loot, door edits or native acceptance evidence are included.
class HCSettlementTown
{
    string Id;
    int LastDay = -1;
    int Ransack = -1;
    int Barricades = -1;
    int Remains = -1;
    int Notices = -1;
}

class HCSettlementState
{
    int Version = -1;
    int Epoch;
    int SavedUtc;
    string WorldName;
    ref array<ref HCSettlementTown> Towns = new array<ref HCSettlementTown>;
}

class HCSettlementDecayStore
{
    static const string PATH = "$profile:HollowCountry/settlement-decay.json";
    bool Save(HCSettlementState state)
    {
        return HCV2ThreatStore<HCSettlementState>.Save(PATH, state, 16384);
    }
}

// This is an additional distance-only gate for authored waypoint/prop changes,
// NOT a resolution of the diagnostic gate's unknown entity lifecycle provider.
// It never marks spectator/optics/CE ownership evidence known. A full kilometre
// veto around both endpoints is conservative; camera qualification stays pending.
modded class HCObserverTransitionGate
{
    static bool V2Quiet(vector from, vector toward, float now, float quiet, out float clearSince)
    {
        if (!Finite(now) || now < 0 || !HCInfectedStore.ValidPosition(from) || !HCInfectedStore.ValidPosition(toward))
        {
            clearSince = -1;
            return false;
        }
        array<Man> players = new array<Man>;
        GetGame().GetPlayers(players);
        if (players.Count() > 16) { clearSince = -1; return false; }
        foreach (Man observer : players)
        {
            if (!observer) { clearSince = -1; return false; }
            vector position = observer.GetPosition();
            if (!HCInfectedStore.ValidPosition(position) || vector.DistanceSq(position, from) <= 1440000 || vector.DistanceSq(position, toward) <= 1440000)
            {
                clearSince = -1;
                return false;
            }
        }
        if (clearSince < 0 || clearSince > now) { clearSince = now; }
        return now - clearSince >= quiet;
    }
}

class HCSettlementDecay : HCModule
{
    protected static HCSettlementDecay s_Instance;
    protected ref HCSettlementState m_State;
    protected ref HCSettlementDecayStore m_Store;
    protected ref HCWorldData m_Catalog;
    protected ref array<Object> m_Props = new array<Object>;
    protected ref array<int> m_PropSlots = new array<int>;
    protected ref array<float> m_Clear = new array<float>;
    protected ref array<ref HCWorldFact> m_Facts = new array<ref HCWorldFact>;
    protected bool m_Fault;
    protected int m_Cursor;
    protected float m_Elapsed;

    override string GetName() { return "SettlementDecay"; }
    override bool IsEnabled(HCSettings settings) { return settings && settings.EnableWorld; }

    static int RansackAfter(int prior, int day, int severity)
    {
        int age = 0;
        if (day >= 3) { age = 1; }
        if (day >= 7) { age = 2; }
        if (day >= 14) { age = 3; }
        return Math.Min(3, Math.Max(prior, Math.Max(age, severity)));
    }

    // Read-only integration hooks: consumers call only BEFORE furnishing or
    // before adding a signs-of-life site. Already furnished houses stay intact.
    static string HistoryFor(vector position, string fallback)
    {
        HCSettlementTown town = At(position);
        if (!town || town.Ransack < 1) { return fallback; }
        if (town.Ransack >= 2) { return "ransacked"; }
        return "abandoned";
    }

    static bool AllowLitWindow(vector position)
    {
        HCSettlementTown town = At(position);
        return !town || town.Ransack < 2;
    }

    static HCSettlementTown At(vector position)
    {
        if (!s_Instance || s_Instance.m_Fault || !s_Instance.m_State) { return null; }
        HCWorldModule world = HCWorldModule.Get();
        if (!world) { return null; }
        string nearest = world.NearestPlace(position);
        HCWorldPlace place = s_Instance.m_Catalog.Place(nearest);
        if (!place) { return null; }
        foreach (HCSettlementTown row : s_Instance.m_State.Towns)
        {
            if (row.Id == place.Id) { return row; }
        }
        return null;
    }

    protected void Fail()
    {
        m_Fault = true;
        if (s_Instance == this) { s_Instance = null; }
        Print("[HollowCountry] V2 settlement decay disabled: persistence/clock/schema fault; preserve settlement-decay.json, .tmp and .bak");
    }

    override void OnStart(HCSettings settings)
    {
        Print(HCV2Admission.Line("SettlementDecay", true, "EXP-S4", HCV2Gates.Qualified("EXP-S4")));
        m_Store = new HCSettlementDecayStore;
        // World may start after us; resolve it on the bounded module tick.
    }

    protected bool Valid(HCWorldModule world, int now)
    {
        if (!m_State || m_State.Version != 1 || m_State.Epoch != world.Epoch() || m_State.WorldName != GetGame().GetWorldName()) { return false; }
        if (m_State.SavedUtc < m_State.Epoch || m_State.SavedUtc > now || !m_State.Towns || m_State.Towns.Count() != m_Catalog.Places.Count()) { return false; }
        for (int townIndex = 0; townIndex < m_State.Towns.Count(); townIndex++)
        {
            HCSettlementTown town = m_State.Towns[townIndex];
            if (!town || town.Id != m_Catalog.Places[townIndex].Id || town.LastDay < -1 || town.LastDay > world.Day()) { return false; }
            if (town.Ransack < 0 || town.Ransack > 3 || town.Barricades < 0 || town.Barricades > 2 || town.Remains < 0 || town.Remains > 1 || town.Notices < 0 || town.Notices > 1) { return false; }
        }
        return true;
    }

    protected bool Initialize(HCWorldModule world, int now)
    {
        m_Catalog = HCWorldData.Fresh(world.Epoch());
        if (!HCV2ThreatStore<HCSettlementState>.CanOpen(HCSettlementDecayStore.PATH)) { return false; }
        if (FileExist(HCSettlementDecayStore.PATH))
        {
            if (!HCV2ThreatStore<HCSettlementState>.Load(HCSettlementDecayStore.PATH, 16384, m_State) || !Valid(world, now)) { return false; }
        }
        else
        {
            m_State = new HCSettlementState;
            m_State.Version = 1;
            m_State.Epoch = world.Epoch();
            m_State.SavedUtc = now;
            m_State.WorldName = GetGame().GetWorldName();
            foreach (HCWorldPlace place : m_Catalog.Places)
            {
                HCSettlementTown row = new HCSettlementTown;
                row.Id = place.Id;
                row.Ransack = 0;
                row.Barricades = 0;
                row.Remains = 0;
                row.Notices = 0;
                m_State.Towns.Insert(row);
            }
            if (!Persist()) { return false; }
        }
        foreach (HCSettlementTown initialized : m_State.Towns)
        {
            m_Clear.Insert(-1);
            m_PropSlots.Insert(0);
        }
        s_Instance = this;
        return true;
    }

    protected bool Persist()
    {
        return m_Store.Save(m_State);
    }

    protected int Severity(HCWorldModule world, string id)
    {
        world.GetRecentFacts(7 * HCWorldLimits.DAY, m_Facts);
        int severity = 0;
        foreach (HCWorldFact fact : m_Facts)
        {
            // Only damaging events change history; a courier/peaceful visit
            // must not ransack a town merely because it has a severity number.
            bool damage = fact.Kind == "holdout_raided" || fact.Kind == "settlement_raided" || fact.Kind == "faction_clash" || fact.Kind.IndexOf("pushed_") >= 0;
            if (fact.PlaceId == id && damage && fact.Severity > severity) { severity = fact.Severity; }
        }
        return severity;
    }

    protected void Visual(int index, int now)
    {
        if (m_Props.Count() >= 24 || m_PropSlots[index] >= 4) { return; }
        HCSettlementTown town = m_State.Towns[index];
        if (town.Ransack < 1) { return; }
        int slot = m_PropSlots[index];
        if (slot == 1 && town.Remains == 0) { return; }
        if (slot == 2 && town.Notices == 0) { return; }
        if (slot == 3 && town.Barricades == 0) { return; }
        vector point = m_Catalog.Places[index].Position;
        // Candidate offsets are design inputs, never surveyed-safe coordinates.
        // Runtime vetoes reject water, roads, slope and occupied geometry.
        if (slot == 0) { point = point + "420 0 120"; }
        if (slot == 1) { point = point + "-420 0 120"; }
        if (slot == 2) { point = point + "120 0 420"; }
        if (slot == 3) { point = point + "120 0 -420"; }
        point[1] = GetGame().SurfaceY(point[0], point[2]);
        float clearSince = m_Clear[index];
        // Seconds within the UTC day keep float precision (a raw UTC stamp has 128 s steps);
        // a midnight wrap only restarts the quiet wait.
        bool quiet = HCObserverTransitionGate.V2Quiet(point, point, now % 86400, 60, clearSince);
        m_Clear[index] = clearSince;
        if (!quiet) { return; }
        // Each slot is attempted only once per boot. Failed geometry is never
        // retried every tick; neither an orphan nor a foreign prop is adopted.
        m_PropSlots[index]++;
        m_Clear[index] = -1;
        if (!HCWorldLimits.Position(point) || GetGame().SurfaceIsSea(point[0], point[2]) || GetGame().SurfaceIsPond(point[0], point[2])) { return; }
        string surface;
        GetGame().SurfaceGetType(point[0], point[2], surface);
        surface.ToLower();
        if (surface.IndexOf("grass") < 0) { return; }
        float sx = GetGame().SurfaceY(point[0] + 3, point[2]);
        float sz = GetGame().SurfaceY(point[0], point[2] + 3);
        if (Math.AbsFloat(sx - point[1]) > 0.2 || Math.AbsFloat(sz - point[1]) > 0.2) { return; }
        array<Object> nearby = new array<Object>;
        array<CargoBase> cargo = new array<CargoBase>;
        GetGame().GetObjectsAtPosition3D(point, 40, nearby, cargo);
        if (nearby.Count() > 0 || cargo.Count() > 0) { return; }
        string type = "StaticObj_Garbage_GroundSq_3m_NoLC";
        if (slot == 1) { type = "StaticObj_Furniture_fireplace_grill"; }
        if (slot == 2) { type = "StaticObj_Misc_NoticeBoard1"; }
        if (slot == 3) { type = "StaticObj_Misc_Barricade"; }
        if (!GetGame().ConfigIsExisting("CfgVehicles " + type)) { return; }
        // Decorative static-only classes from the installed vanilla catalog.
        // No ECE_CREATEPHYSICS/UPDATEPATHGRAPH, inventory or CE persistence.
        int flags = ECE_SETUP | ECE_KEEPHEIGHT | ECE_NOLIFETIME | ECE_NOPERSISTENCY_WORLD;
        Object prop = GetGame().CreateObjectEx(type, point, flags);
        if (!prop) { return; }
        vector box[2];
        prop.ClippingInfo(box);
        vector size = box[1] - box[0];
        if (!(size[0] > 0 && size[0] <= 6 && size[1] >= 0 && size[1] <= 3 && size[2] > 0 && size[2] <= 6))
        {
            GetGame().ObjectDelete(prop);
            return;
        }
        m_Props.Insert(prop);
    }

    override void OnTick(float deltaTime)
    {
        if (m_Fault || !(deltaTime > 0)) { return; }
        m_Elapsed += Math.Min(deltaTime, 60);
        if (m_Elapsed < 10) { return; }
        m_Elapsed = 0;
        HCWorldModule world = HCWorldModule.Get();
        if (!world) { return; }
        int now = HCWorldClock.UTC();
        if (now < world.Epoch()) { Fail(); return; }
        if (!m_State && !Initialize(world, now)) { Fail(); return; }
        if (m_State.Epoch != world.Epoch() || now < m_State.SavedUtc) { Fail(); return; }
        int index = m_Cursor;
        m_Cursor = (m_Cursor + 1) % m_State.Towns.Count();
        HCSettlementTown town = m_State.Towns[index];
        int changed = 0;
        int before = town.Ransack + town.Barricades + town.Remains + town.Notices;
        town.Ransack = RansackAfter(town.Ransack, HCEscalationClock.Day(), Severity(world, town.Id));
        if (town.Ransack >= 1) { town.Remains = 1; town.Notices = 1; }
        if (town.Ransack >= 2) { town.Barricades = Math.Max(town.Barricades, 1); }
        if (HCEscalationClock.Pressure("raiders") >= 0.55 && town.Ransack >= 2) { town.Barricades = 2; }
        if (before != town.Ransack + town.Barricades + town.Remains + town.Notices) { changed = 1; }
        if (town.LastDay != world.Day() || changed > 0)
        {
            town.LastDay = world.Day();
            m_State.SavedUtc = now;
            if (!Persist()) { Fail(); return; }
            int towns = m_State.Towns.Count();
            Print("[HollowCountry] V2 settlement decay towns=" + towns.ToString() + " changed=" + changed.ToString());
        }
        Visual(index, now);
    }

    override void OnStop()
    {
        if (s_Instance == this) { s_Instance = null; }
        // Native nonpersistent scenery is cleaned with the mission; do not
        // delete visible props during an ordinary observer's session.
        m_State = null;
    }
}

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        Register(new HCSettlementDecay);
    }
}
