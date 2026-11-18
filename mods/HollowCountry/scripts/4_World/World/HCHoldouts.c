// LC-T408, #102. Native evidence: installed scripts-1.30.164289:
// 1_Core/proto/EnSystem.c:397 FileExist, :525 MakeDirectory, :528 DeleteFile,
// :531 CopyFile; 3_Game/tools/JsonFileLoader.c:69 LoadData, :85 MakeData;
// 3_Game/Global/Game.c:703 CreateObjectEx, :930 GetObjectsAtPosition3D,
// :1333 IsBoxColliding; 3_Game/Entities/Object.c:287 GetPosition, :305 GetOrientation,
// :311 SetOrientation, :517 IsAlive, :873 ModelToWorld, :1219 IsRuined;
// 3_Game/Entities/EntityAI.c:885 GetHierarchyParent, :3374 GetPersistentID,
// :3377 SetLifetime, :3384 SetLifetimeMax; 3_Game/CE/CentralEconomy.c:9 ECE_SETUP,
// :17 ECE_CREATEPHYSICS, :28 ECE_KEEPHEIGHT (no nonpersistent/dynamic flags).
// 3_Game/Global/Game.c:1120 IsServer; gameplay.c:636 GetGame;
// 3_Game/Entities/EntityAI.c:1884 GetInventory; Inventory/Inventory.c:138 GetCargo;
// Inventory/Cargo.c:28 GetItemCount, :32 GetItem; 1_Core/proto/EnScript.c:380
// Count, :385 Clear, :394 Find, :407 Insert, :463 Remove, :902 map.Set,
// :917 map.Contains; EnString.c:199 Length, :240 IndexOf;
// EnConvert.c:30 int.ToString, :210 vector.DistanceSq; EnDebug.c:96 Print.
// 3_Game/Entities/EntityAI.c:1104 EEKilled(Object killer), :1248 EECargoOut(EntityAI item);
// 3_Game/Entities/Man.c:21 GetIdentity; 4_World/Entities/ItemBase/Gear/Camping/camping.c:17 WoodenCrate.
// HCV2ThreatStore/HCGroupIO perform bounded serialization/readback. No RenameFile
// exists: temp intent -> verified backup -> copy/readback promotion is fail-closed,
// NOT OS atomic rename/fsync or atomic with Hive. Interrupted saves stop the feature.
// Own catalog is the first 24 unique, covered houses in the authored template pack;
// actual placement, persistence, occupancy, pathing and lights remain UNOBSERVED.

class HCEncounterStore<Class T>
{
    protected string m_Path;
    protected bool m_Fault;

    void HCEncounterStore(string name) { m_Path = "$profile:HollowCountry/" + name + ".json"; }
    bool Healthy() { return !m_Fault; }
    bool Fault()
    {
        if (!m_Fault) Print("[HollowCountry] V2 encounter store inactive: preserve " + m_Path + ", .tmp and .bak; recovery required");
        m_Fault = true;
        return false;
    }

    T Load(T fresh, string collection)
    {
        if (!HCV2ThreatStore<T>.CanOpen(m_Path)) { Fault(); return null; }
        T result;
        if (FileExist(m_Path))
        {
            string encoded = HCWorldStore.Read(m_Path);
            if (encoded.Length() > 262144 || encoded.IndexOf("\"Version\"") < 0 || encoded.IndexOf("\"" + collection + "\"") < 0) { Fault(); return null; }
            if (!HCV2ThreatStore<T>.Load(m_Path, 262144, result)) { Fault(); return null; }
            return result;
        }
        if (!Save(fresh)) return null;
        return fresh;
    }

    bool Save(T data)
    {
        if (m_Fault || !data) return false;
        if (!HCV2ThreatStore<T>.Save(m_Path, data, 262144)) return Fault();
        return true;
    }

}

class HCEncounterCache
{
    vector Position;
    vector Orientation;
    string EntityRef;
    // 0 unmade, 1 creation intent, 2 persistent link, 3 lost/quarantined.
    int Phase;
}

// One real, ordinary vanilla crate, never respawned after intent. Runtime handle
// is separate from the DTO; no inventory is serialized, copied or reconstructed.
class HCEncounterCacheIO
{
    EntityAI Handle;

    static bool Valid(HCEncounterCache row)
    {
        if (!row || row.Phase < 0 || row.Phase > 3 || !HCWorldLimits.Position(row.Position)) return false;
        if (row.EntityRef.Length() > 96 || (row.Phase == 2 && row.EntityRef == "")) return false;
        return HCInteriorRules.SaneVector(row.Orientation, 360);
    }

    bool Clear(HCEncounterCache row, Object structure)
    {
        array<Object> excluded = new array<Object>;
        if (structure) excluded.Insert(structure);
        // Room bounds/door keepouts are checked before excluding the building.
        return !GetGame().IsBoxColliding(row.Position + Vector(0, 0.22, 0), row.Orientation, "0.85 0.45 0.65", excluded);
    }

    void Create(HCEncounterCache row)
    {
        // Caller MUST persist Phase=1 first. No ECE_EQUIP flags or cargo creation.
        if (!row || row.Phase != 1 || Handle) return;
        Handle = EntityAI.Cast(GetGame().CreateObjectEx("WoodenCrate", row.Position, ECE_SETUP | ECE_KEEPHEIGHT | ECE_CREATEPHYSICS, RF_IGNORE));
        if (!Handle) { row.Phase = 3; return; }
        Handle.SetOrientation(row.Orientation);
        Handle.SetLifetimeMax(3888000);
        Handle.SetLifetime(3888000);
        LinkCache(row);
    }

    bool LinkCache(HCEncounterCache row)
    {
        if (row.Phase == 0 || row.Phase == 3) return false;
        if (!Handle && row.Phase == 2)
        {
            array<Object> objects = new array<Object>;
            array<CargoBase> cargos = new array<CargoBase>;
            GetGame().GetObjectsAtPosition3D(row.Position, 5, objects, cargos);
            if (objects.Count() > 256) return false;
            foreach (Object object : objects)
            {
                EntityAI candidate = EntityAI.Cast(object);
                if (candidate && candidate.GetType() == "WoodenCrate" && HCSearchSupplyRegistry.PersistentId(candidate) == row.EntityRef)
                {
                    if (Handle) { Handle = null; row.Phase = 3; return false; }
                    Handle = candidate;
                }
            }
        }
        // An unresolved creation intent across a crash is never recreated.
        if (!Handle || Handle.IsRuined() || Handle.GetHierarchyParent() || Handle.GetHierarchyRootPlayer())
        {
            row.Phase = 3;
            return false;
        }
        if (row.Phase == 1)
        {
            string persistentId = HCSearchSupplyRegistry.PersistentId(Handle);
            // Hive may assign its id later; retain this live handle until then.
            if (persistentId == "") return false;
            row.EntityRef = persistentId;
            row.Phase = 2;
        }
        if (HCSearchSupplyRegistry.PersistentId(Handle) != row.EntityRef) { row.Phase = 3; return false; }
        return true;
    }
}

class HCHoldoutRow
{
    ref HCWorldHoldout Ledger = new HCWorldHoldout;
    ref HCEncounterCache Cache = new HCEncounterCache;
    int StockAttempts;
    int StockDay;
    bool Published;
    ref array<string> Contents = new array<string>;
}

class HCHoldoutState
{
    int Version = 1;
    string TemplatePin;
    ref array<ref HCHoldoutRow> Rows = new array<ref HCHoldoutRow>;
}

// Optional signs owner supplies a sink whose ForceLit delegates to its real
// HCSignsOfLife.ForceLit API. This keeps builds valid when that module is absent.
class HCHoldoutLightSink
{
    void ForceLit(string id, vector position, bool lit) {}
}

class HCHoldoutBody
{
    string HoldoutId;
    EntityAI Body;
}

class HCHoldouts : HCModule
{
    protected static HCHoldouts s_Instance;
    protected static ref HCHoldoutLightSink s_Lights;
    protected ref HCEncounterStore<HCHoldoutState> m_Store;
    protected ref HCHoldoutState m_State;
    protected ref array<ref HCEncounterCacheIO> m_Caches = new array<ref HCEncounterCacheIO>;
    protected ref array<ref HCHoldoutBody> m_Bodies = new array<ref HCHoldoutBody>;
    protected int m_Next;
    protected float m_Elapsed;
    protected bool m_Ready;
    protected bool m_Dirty;
    protected int m_Reports;
    protected bool m_WaitReported;

    static HCHoldouts Get() { if (s_Instance && s_Instance.m_Ready) { return s_Instance; } return null; }
    static void BindSignsOfLife(HCHoldoutLightSink sink) { s_Lights = sink; }

    static void CargoRemoved(EntityAI container)
    {
        HCHoldouts module = HCHoldouts.Get();
        if (!module || !GetGame().IsServer()) return;
        for (int cacheIndex = 0; cacheIndex < module.Count(); cacheIndex++)
        {
            HCHoldoutRow row = module.m_State.Rows[cacheIndex];
            if (module.m_Caches[cacheIndex].Handle == container && (row.Ledger.State == "OCCUPIED" || row.Ledger.State == "ALERT"))
            {
                module.Raid(cacheIndex);
                return;
            }
        }
    }

    static void OccupantKilled(EntityAI body)
    {
        HCHoldouts module = HCHoldouts.Get();
        if (!module || !GetGame().IsServer()) return;
        foreach (HCHoldoutBody binding : module.m_Bodies)
        {
            if (binding.Body != body) continue;
            for (int holdoutIndex = 0; holdoutIndex < module.Count(); holdoutIndex++)
            {
                if (module.m_State.Rows[holdoutIndex].Ledger.Id == binding.HoldoutId)
                {
                    module.Raid(holdoutIndex);
                    return;
                }
            }
        }
    }
    override string GetName() { return "Holdouts"; }
    override bool IsEnabled(HCSettings settings) { return settings && settings.EnableEncounters; }
    int Count() { if (!m_State) { return 0; } return m_State.Rows.Count(); }

    override void OnStart(HCSettings settings)
    {
        Print(HCV2Admission.Line("Holdouts", true, "EXP-L4", HCV2Gates.Qualified("EXP-L4")));
        m_Store = new HCEncounterStore<HCHoldoutState>("holdouts");
        m_State = m_Store.Load(new HCHoldoutState, "Rows");
        if (!m_State || m_State.Version != 1 || !m_State.Rows || m_State.Rows.Count() > 24) return;
        map<string, bool> ids = new map<string, bool>;
        int occupied = 0;
        foreach (HCHoldoutRow row : m_State.Rows)
        {
            if (!row || !row.Ledger || !HCEncounterCacheIO.Valid(row.Cache) || ids.Contains(row.Ledger.Id) || !HCWorldLimits.Token(row.Ledger.Id) || !HCWorldLimits.Token(row.Ledger.HouseClass) || !HCWorldLimits.Position(row.Ledger.HousePos)) return;
            if (row.Ledger.State != "DORMANT" && row.Ledger.State != "OCCUPIED" && row.Ledger.State != "ALERT" && row.Ledger.State != "RAIDED" && row.Ledger.State != "ABANDONED") return;
            if (row.Ledger.Since < 0 || row.Ledger.ReoccupyAfter < 0 || row.Ledger.Occupants < 0 || row.Ledger.Occupants > 3 || row.StockAttempts < 0 || row.StockAttempts > 3 || row.StockDay < 0 || !row.Contents || row.Contents.Count() > 32) return;
            if (row.Ledger.State == "RAIDED" && row.Ledger.ReoccupyAfter - row.Ledger.Since < 604800) return;
            ids.Set(row.Ledger.Id, true);
            if (row.Ledger.Occupants > 0)
            {
                if (!SiteAvailable(row)) return;
                occupied++;
            }
            m_Caches.Insert(new HCEncounterCacheIO);
        }
        if (occupied > 6) { m_Store.Fault(); return; }
        s_Instance = this;
        m_Ready = true;
        Print("[HollowCountry] V2 holdouts ready catalog_cap=24 occupied_cap=6 raid_lockout=604800s; bodies require materializer");
        if (!s_Lights) Print("[HollowCountry] V2 holdouts lit-window bridge pending HCSignsOfLife.ForceLit");
    }

    bool SaveChanged()
    {
        if (!m_Dirty) return true;
        if (!m_Store.Save(m_State)) { m_Ready = false; return false; }
        m_Dirty = false;
        return true;
    }

    bool SiteAvailable(HCHoldoutRow candidate)
    {
        foreach (HCHoldoutRow occupiedSite : m_State.Rows)
        {
            if (!occupiedSite || !occupiedSite.Ledger) return false;
            if (occupiedSite == candidate || occupiedSite.Ledger.Occupants == 0) continue;
            if (occupiedSite.Ledger.Id == candidate.Ledger.Id || vector.DistanceSq(occupiedSite.Ledger.HousePos, candidate.Ledger.HousePos) <= 1) return false;
        }
        return true;
    }

    // AddHoldout is insert-only; the world owner has no general upsert seam.
    // Publish a bounded fact for every transition until that seam is available.
    void PublishState(HCHoldoutRow row)
    {
        HCWorldModule world = HCWorldModule.Get();
        if (!world) return;
        if (row.Ledger.CacheRef != row.Cache.EntityRef)
        {
            row.Ledger.CacheRef = row.Cache.EntityRef;
            m_Dirty = true;
        }
        if (!row.Published && row.Cache.Phase == 2)
        {
            row.Published = world.AddHoldout(row.Ledger);
            if (row.Published) m_Dirty = true;
        }
        if (row.Ledger.State == "RAIDED")
        {
            if (!world.MarkHoldoutRaided(row.Ledger.Id)) world.AddFact("RAIDED", row.Ledger.PlaceId, 2);
            return;
        }
        if (row.Ledger.State == "ABANDONED")
        {
            world.AddFact("ABANDONED", row.Ledger.PlaceId, 1);
            return;
        }
        string stateKind = row.Ledger.State;
        stateKind.ToLower();
        world.AddFact("holdout_" + stateKind, row.Ledger.PlaceId, 1);
    }

    // Catalog comes from authored template-pack world rows, never a world scan.
    // Work is chunked at 32 rows; first 24 distinct covered houses are retained.
    protected int m_CatalogCursor;
    void FillCatalog()
    {
        HCWorldModule world = HCWorldModule.Get();
        array<ref HCInteriorFurnishRow> authored = HCInteriorTemplates.FurnishRows();
        if (!world || !authored || m_State.Rows.Count() >= 24) return;
        int work = 0;
        bool changed = false;
        while (work < 32 && m_CatalogCursor < authored.Count() && m_State.Rows.Count() < 24)
        {
            HCInteriorFurnishRow site = authored[m_CatalogCursor];
            m_CatalogCursor++;
            work++;
            HCInteriorTemplateClassRow classRow = HCInteriorTemplates.ClassRow(site.BuildingClass);
            HCInteriorTemplate layout = HCInteriorTemplates.Template(site.BuildingClass);
            if (!classRow || classRow.Search != "covered" || !layout || layout.Rooms.Count() < 1) continue;
            vector position = HCInteriorTemplates.AsVector(site.Position);
            string id = "hc-house-" + site.SlotId.ToString();
            bool known = false;
            foreach (HCHoldoutRow existing : m_State.Rows) { if (existing.Ledger.Id == id || existing.Ledger.HousePos == position) known = true; }
            if (known) continue;
            HCHoldoutRow row = new HCHoldoutRow;
            row.Ledger.Id = id;
            row.Ledger.HouseClass = site.BuildingClass;
            row.Ledger.HousePos = position;
            row.Ledger.PlaceId = world.NearestPlace(position);
            row.Ledger.PlaceId.ToLower();
            row.Ledger.FactionId = "locals";
            row.Ledger.Since = HCWorldClock.UTC();
            row.StockDay = HCEscalationClock.Day();
            row.Cache.Position = position;
            row.Cache.Orientation = Vector(site.Yaw, 0, 0);
            m_State.Rows.Insert(row);
            m_Caches.Insert(new HCEncounterCacheIO);
            changed = true;
        }
        if (changed)
        {
            m_State.TemplatePin = HCInteriorTemplates.SourcePin();
            m_Dirty = true;
            if (!SaveChanged()) return;
            else Print("[HollowCountry] V2 holdouts catalog houses=" + Count().ToString() + "/24");
        }
    }

    // Authored snapshot for a later materializer/lead owner, never a mutable
    // reference into this module's persistent state.
    HCWorldHoldout Snapshot(int index)
    {
        if (!m_Ready || index < 0 || index >= Count()) return null;
        HCWorldHoldout copy;
        string encoded;
        string error;
        if (!JsonFileLoader<HCWorldHoldout>.MakeData(m_State.Rows[index].Ledger, encoded, error)) return null;
        if (!JsonFileLoader<HCWorldHoldout>.LoadData(encoded, copy, error)) return null;
        return copy;
    }

    string PlaceId(int index)
    {
        if (index < 0 || index >= Count()) return "";
        return m_State.Rows[index].Ledger.PlaceId;
    }

    Object Structure(int index)
    {
        if (index < 0 || index >= Count()) return null;
        HCInteriorFurnishRow pose = new HCInteriorFurnishRow;
        pose.BuildingClass = m_State.Rows[index].Ledger.HouseClass;
        vector position = m_State.Rows[index].Ledger.HousePos;
        pose.Position.Insert(position[0]); pose.Position.Insert(position[1]); pose.Position.Insert(position[2]);
        return HCInteriorTemplatePlacement.Resolve(pose);
    }

    string CacheId(int index)
    {
        if (index < 0 || index >= Count()) return "";
        return m_State.Rows[index].Ledger.Id;
    }

    EntityAI Cache(int index)
    {
        if (index < 0 || index >= Count() || m_State.Rows[index].Cache.Phase != 2) return null;
        EntityAI handle = m_Caches[index].Handle;
        if (!handle || handle.IsRuined() || handle.GetHierarchyParent() || handle.GetHierarchyRootPlayer()) return null;
        return handle;
    }

    int Occupied()
    {
        int occupied = 0;
        foreach (HCHoldoutRow row : m_State.Rows) { if (row.Ledger.State == "OCCUPIED" || row.Ledger.State == "ALERT") occupied++; }
        return occupied;
    }

    // Small crate footprint in an authored room corner, outside every keepout
    // including 0.6 m around doors. Refuse when room geometry cannot contain it.
    bool CacheSpot(Object structure, HCHoldoutRow row)
    {
        HCInteriorTemplate layout = HCInteriorTemplates.Template(row.Ledger.HouseClass);
        if (!layout) return false;
        int examined = 0;
        foreach (HCInteriorTemplateRoom room : layout.Rooms)
        {
            examined++;
            if (examined > 16) break;
            vector spot = Vector(room.Min[0] + 0.55, room.FloorY + 0.03, room.Min[2] + 0.45);
            array<float> minimum = {spot[0] - 0.45, spot[1], spot[2] - 0.35};
            array<float> maximum = {spot[0] + 0.45, spot[1] + 0.5, spot[2] + 0.35};
            if (!HCInteriorTemplates.Inside(minimum, room.Min, room.Max) || !HCInteriorTemplates.Inside(maximum, room.Min, room.Max)) continue;
            bool clear = true;
            foreach (HCInteriorTemplateKeepOut keepout : layout.KeepOuts)
            {
                if (HCInteriorTemplates.Intersects(minimum, maximum, keepout.Min, keepout.Max, 0.6)) clear = false;
            }
            if (!clear) continue;
            row.Cache.Position = structure.ModelToWorld(spot);
            row.Cache.Orientation = structure.GetOrientation();
            HCEncounterCacheIO probe = new HCEncounterCacheIO;
            if (probe.Clear(row.Cache, structure)) return true;
        }
        return false;
    }

    // Materializer integration: bind only its admitted ordinary, killable body.
    // No immunity, equipment changes, loot controller or body creation here.
    bool BindOccupant(string id, EntityAI body)
    {
        if (!m_Ready || !body || !body.IsMan() || !body.IsAlive() || m_Bodies.Count() >= 18) return false;
        PlayerBase human = PlayerBase.Cast(body);
        if (human && human.GetIdentity()) return false;
        int boundCount = 0;
        foreach (HCHoldoutBody bound : m_Bodies)
        {
            if (bound.Body == body) return false;
            if (bound.HoldoutId == id && bound.Body && bound.Body.IsAlive()) boundCount++;
        }
        foreach (HCHoldoutRow row : m_State.Rows)
        {
            if (row.Ledger.Id != id || (row.Ledger.State != "OCCUPIED" && row.Ledger.State != "ALERT")) continue;
            if (boundCount >= row.Ledger.Occupants || vector.DistanceSq(body.GetPosition(), row.Ledger.HousePos) > 900) return false;
            HCHoldoutBody binding = new HCHoldoutBody;
            binding.HoldoutId = id;
            binding.Body = body;
            m_Bodies.Insert(binding);
            return true;
        }
        return false;
    }

    // Provider must release a living lease BEFORE deleting it. Null handles are
    // not proof of death and are never counted as kills.
    void ReleaseOccupant(EntityAI body)
    {
        for (int releaseIndex = m_Bodies.Count() - 1; releaseIndex >= 0; releaseIndex--)
        {
            if (m_Bodies[releaseIndex].Body == body) m_Bodies.Remove(releaseIndex);
        }
    }

    bool LootRemoved(int index)
    {
        EntityAI cache = Cache(index);
        if (!cache || !cache.GetInventory() || !cache.GetInventory().GetCargo()) return false;
        CargoBase cargo = cache.GetInventory().GetCargo();
        if (cargo.GetItemCount() > 32) return false;
        array<string> present = new array<string>;
        for (int itemIndex = 0; itemIndex < cargo.GetItemCount(); itemIndex++)
            present.Insert(HCSearchSupplyRegistry.PersistentId(cargo.GetItem(itemIndex)));
        foreach (string prior : m_State.Rows[index].Contents) { if (present.Find(prior) < 0) return true; }
        return false;
    }

    void SnapshotContents(int index)
    {
        EntityAI cache = Cache(index);
        if (!cache || !cache.GetInventory() || !cache.GetInventory().GetCargo()) return;
        CargoBase cargo = cache.GetInventory().GetCargo();
        if (cargo.GetItemCount() > 32) return;
        array<string> contents = new array<string>;
        for (int itemIndex = 0; itemIndex < cargo.GetItemCount(); itemIndex++)
        {
            string id = HCSearchSupplyRegistry.PersistentId(cargo.GetItem(itemIndex));
            if (id != "") contents.Insert(id);
        }
        bool changed = contents.Count() != m_State.Rows[index].Contents.Count();
        if (!changed)
        {
            for (int compareIndex = 0; compareIndex < contents.Count(); compareIndex++)
                if (contents[compareIndex] != m_State.Rows[index].Contents[compareIndex]) changed = true;
        }
        if (!changed) return;
        m_State.Rows[index].Contents = contents;
        m_Dirty = true;
    }

    // Called by the encounter/stance owner only for a local observed threat.
    bool Alert(string id)
    {
        if (!m_Ready) return false;
        foreach (HCHoldoutRow row : m_State.Rows)
        {
            if (row.Ledger.Id != id || row.Ledger.State != "OCCUPIED") continue;
            row.Ledger.State = "ALERT";
            row.Ledger.Since = HCWorldClock.UTC();
            m_Dirty = true;
            if (!SaveChanged()) return false;
            PublishState(row);
            return SaveChanged();
        }
        return false;
    }

    void Raid(int index)
    {
        HCHoldoutRow row = m_State.Rows[index];
        if (row.Ledger.State == "RAIDED") return;
        row.Ledger.State = "RAIDED";
        row.Ledger.Occupants = 0;
        row.Ledger.Since = HCWorldClock.UTC();
        row.Ledger.ReoccupyAfter = row.Ledger.Since + 604800;
        row.Ledger.Routine = "LOCKOUT";
        row.Contents.Clear();
        m_Dirty = true;
        if (!SaveChanged()) return;
        PublishState(row);
        if (!SaveChanged()) return;
        Print("[HollowCountry] V2 holdout raided id=" + row.Ledger.Id + " lockout=604800s");
    }

    override void OnTick(float deltaTime)
    {
        if (!m_Ready || !HCWorldModule.Get()) return;
        m_Elapsed += deltaTime;
        if (m_Elapsed < 10) return;
        m_Elapsed = 0;
        if (!HCInteriorTemplates.Loaded())
        {
            if (!m_WaitReported) Print("[HollowCountry] V2 holdouts waiting for authored covered template houses");
            m_WaitReported = true;
            return;
        }
        if (m_State.TemplatePin != "" && m_State.TemplatePin != HCInteriorTemplates.SourcePin()) { m_Ready = false; Print("[HollowCountry] V2 holdouts template pin changed; recovery required"); return; }
        FillCatalog();
        if (!m_Ready || Count() == 0 || HCEscalationClock.Day() < 1) return;
        if (m_Next >= Count()) m_Next = 0;
        int index = m_Next;
        m_Next++;
        HCHoldoutRow row = m_State.Rows[index];
        int now = HCWorldClock.UTC();
        if (now < row.Ledger.Since || now < 1) { m_Ready = false; return; }
        Object structure = Structure(index);
        if (!structure) return;
        if (row.Cache.Phase == 0 && HCObserverTransitionGate.CanTransition(row.Ledger.HousePos, 500) && CacheSpot(structure, row) && HCObserverTransitionGate.CanTransition(row.Cache.Position, 500))
        {
            row.Cache.Phase = 1;
            m_Dirty = true;
            if (!SaveChanged()) return;
            m_Caches[index].Create(row.Cache);
            m_Dirty = true;
        }
        int cachePhase = row.Cache.Phase;
        string cacheRef = row.Cache.EntityRef;
        if (row.Cache.Phase != 0) m_Caches[index].LinkCache(row.Cache);
        if (cachePhase != row.Cache.Phase || cacheRef != row.Cache.EntityRef) m_Dirty = true;
        if ((row.Ledger.State == "OCCUPIED" || row.Ledger.State == "ALERT") && LootRemoved(index)) Raid(index);
        if (row.Cache.Phase == 3 && (row.Ledger.State == "OCCUPIED" || row.Ledger.State == "ALERT")) Raid(index);
        if (!m_Ready) return;
        string previousState = row.Ledger.State;
        if (row.Ledger.State == "RAIDED" && now >= row.Ledger.ReoccupyAfter)
        {
            row.Ledger.State = "DORMANT";
            row.Ledger.Since = now;
        }
        if (row.Ledger.State == "DORMANT" && Occupied() < 6 && SiteAvailable(row) && Cache(index))
        {
            row.Ledger.State = "OCCUPIED";
            row.Ledger.Occupants = 1;
            row.Ledger.Since = now;
            row.Ledger.Routine = "SHELTER";
        }
        if (row.Ledger.State == "ALERT" && now - row.Ledger.Since >= 3600) row.Ledger.State = "OCCUPIED";
        for (int bodyIndex = m_Bodies.Count() - 1; bodyIndex >= 0; bodyIndex--)
        {
            HCHoldoutBody binding = m_Bodies[bodyIndex];
            if (binding.HoldoutId != row.Ledger.Id) continue;
            if (!binding.Body) { m_Bodies.Remove(bodyIndex); continue; }
            if (binding.Body.IsAlive()) continue;
            m_Bodies.Remove(bodyIndex);
            Raid(index);
            if (!m_Ready) return;
            previousState = row.Ledger.State;
        }
        if (row.Ledger.State == "OCCUPIED" && HCEscalationClock.Day() >= 14 && HCEscalationClock.Pressure("raiders") >= 0.9)
        {
            row.Ledger.State = "ABANDONED";
            row.Ledger.Occupants = 0;
            row.Ledger.Since = now;
        }
        if (!m_Ready) return;
        if (row.Ledger.State != previousState)
        {
            m_Dirty = true;
            PublishState(row);
        }
        if (row.Ledger.State == "OCCUPIED" || row.Ledger.State == "ALERT")
        {
            HCSearchHouses houses = HCSearchBinding.Houses();
            // Three lifetime attempts, one per real day. No replenishment on raid.
            if (houses && Cache(index) && row.StockAttempts < 3 && HCEscalationClock.Day() > 0 && HCEscalationClock.Day() >= row.StockDay && HCObserverTransitionGate.CanTransition(row.Cache.Position, 500))
            {
                int siteNumber = row.StockAttempts;
                row.StockAttempts++;
                row.StockDay = HCEscalationClock.Day() + 1;
                m_Dirty = true;
                if (!SaveChanged()) return;
                int phase = houses.V2Visit(structure, Cache(index), row.Ledger.Id, siteNumber);
                if (phase == 3) { row.StockAttempts = 3; m_Dirty = true; }
                if (m_Reports < 12)
                {
                    m_Reports++;
                    Print("[HollowCountry] V2 holdout stock id=" + row.Ledger.Id + " phase=" + phase.ToString());
                }
            }
        }
        if (row.Ledger.State == "OCCUPIED" || row.Ledger.State == "ALERT") SnapshotContents(index);
        if (row.Ledger.CacheRef != row.Cache.EntityRef)
        {
            row.Ledger.CacheRef = row.Cache.EntityRef;
            m_Dirty = true;
        }
        HCWorldModule world = HCWorldModule.Get();
        if (world && !row.Published && row.Cache.Phase == 2)
        {
            row.Published = world.AddHoldout(row.Ledger);
            if (row.Published) m_Dirty = true;
        }
        if (s_Lights) s_Lights.ForceLit(row.Ledger.Id, row.Ledger.HousePos, row.Ledger.State == "OCCUPIED" || row.Ledger.State == "ALERT");
        SaveChanged();
    }

    override void OnStop()
    {
        // Flush changes marked by native callbacks since the last tick; a faulted store stays unwritten.
        if (m_Ready && m_State) SaveChanged();
        if (s_Lights && m_State)
        {
            foreach (HCHoldoutRow row : m_State.Rows) s_Lights.ForceLit(row.Ledger.Id, row.Ledger.HousePos, false);
        }
        m_Ready = false;
        m_Bodies.Clear();
        if (s_Instance == this) s_Instance = null;
    }
}

// Native server callbacks supplement the restart snapshots. Foreign crates and
// unbound players/AI pass straight through; ordinary inventory and corpse loot
// remain engine-owned. No custom action, immunity or player RPC is involved.
modded class WoodenCrate
{
    override void EECargoOut(EntityAI item)
    {
        super.EECargoOut(item);
        HCDeadDrops.CargoRemoved(this, item);
        HCHoldouts.CargoRemoved(this);
    }
}

modded class PlayerBase
{
    override void EEKilled(Object killer)
    {
        HCHoldouts.OccupantKilled(this);
        super.EEKilled(killer);
    }
}

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        Register(new HCHoldouts);
    }
}
