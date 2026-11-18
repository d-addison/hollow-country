// LC-T203 / LC-TRV-03, EXP-T2. Source implementation; native acceptance pending.
// Installed scripts-1.30.164289 API evidence (paths relative to that cache):
// 1_Core/proto/EnSystem.c:397,417,425,443,462,525-531 file IO/exists/mkdir/copy/delete;
// 1_Core/proto/EnScript.c:407,877 array.Insert/map.Find;
// 3_Game/tools/JsonFileLoader.c:69,85 LoadData/MakeData;
// 1_Core/proto/EnString.c:223 Hash; 1_Core/proto/EnMath.c:413 Round;
// 1_Core/proto/EnConvert.c:210 vector.DistanceSq;
// 3_Game/Global/Game.c:539,612,934,1535 config scope/existence/world/time;
// 3_Game/Global/Game.c:1120 IsServer; 3_Game/Entities/Object.c:287,467,517,981
// position/type/alive/destroyed; 3_Game/Entities/Man.c:21 GetIdentity;
// 3_Game/Global/DayZPhysics.c:199 RaycastRV;
// 4_World/Static/MiscGameplayFunctions.c:778 GetPlayerHeadPosition;
// 4_World/Classes/UserActionsComponent/ActionTargets.c:142-171 target getters;
// 4_World/Entities/ManBase/PlayerBase.c:2219,3925,6733 restrained/unconscious/held item;
// 4_World/Entities/DayZPlayerImplement.c:468 IsInVehicle;
// 3_Game/Systems/Inventory/InventoryLocation.c:115 SetGround;
// 3_Game/Systems/Inventory/Inventory.c:333 GameInventory.LocationCreateEntity;
// 1_Core/proto/EnMath3D.c:256 MatrixIdentity4;
// 3_Game/CE/CentralEconomy.c:38,66 ECE_PLACE_ON_SURFACE/RF_DEFAULT;
// 4_World/Entities/ItemBase.c:3319 SetQuantity (one MetalPlate, never a full stack).
// Config review: installed DayZServer/addons/structures_wrecks.pbo config.bin:
// exact 24 hb01/hb02/sed01/sed02 classes below also occur as groups in stock
// mpmissions/dayzOffline.chernarusplus/mapgrouppos.xml. No arbitrary prefix match,
// police/event/aircraft wrecks, driveable Transport or unreviewed DLC classes.
// vehicles_parts.pbo: SparkPlug/CarBattery/CarRadiator/HeadlightH7, scope=2;
// vehicles_wheeled.pbo: HatchbackWheel scope=2; gear_consumables.pbo: MetalPlate
// scope=2 (vanilla scrap proxy; no invented ScrapMetal class); gear_tools.pbo:
// Wrench/Screwdriver/Pliers scope=2. All read directly with existing PBO reader.
// No native RenameFile exists. Use a temp intent + verified backup/copy replacement;
// any unfinished replacement refuses admission, never falls back to old budgets.
// This is a fail-closed logical commit, NOT filesystem-atomic rename or fsync.
// Debit is durable before native creation; a crash/create failure may lose a part,
// never replay/refund it. Native inventory and journal are not one transaction.

class HCWreckSalvageRow
{
    string Key;
    string WreckClass;
    vector Position;
    int Budget = -1;
    int Left = -1;
}

class HCWreckSalvageState
{
    int Version;
    string WorldName;
    ref array<ref HCWreckSalvageRow> Rows;
}

// Frame the exact payload bytes, like the group store receipt. Hash is an
// accidental-corruption check, not an authentication or power-loss guarantee.
class HCWreckSalvageImage
{
    int Version;
    int Length;
    int Hash;
    string Payload;
}

class HCWreckSalvage
{
    static bool Reviewed(string name)
    {
        // Array lookup: a single 24-term || chain fails natively with "Formula too complex".
        array<string> reviewed = {"Land_Wreck_hb01_aban1_blue", "Land_Wreck_hb01_aban1_green", "Land_Wreck_hb01_aban1_white", "Land_Wreck_hb01_aban2_blue", "Land_Wreck_hb01_aban2_green", "Land_Wreck_hb01_aban2_white", "Land_Wreck_hb02_aban1_black", "Land_Wreck_hb02_aban1_blue", "Land_Wreck_hb02_aban1_red", "Land_Wreck_hb02_aban2_black", "Land_Wreck_hb02_aban2_blue", "Land_Wreck_hb02_aban2_red", "Land_Wreck_sed01_aban1_black", "Land_Wreck_sed01_aban1_white", "Land_Wreck_sed01_aban1_wine", "Land_Wreck_sed01_aban2_black", "Land_Wreck_sed01_aban2_white", "Land_Wreck_sed01_aban2_wine", "Land_Wreck_sed02_aban1_grey", "Land_Wreck_sed02_aban1_red", "Land_Wreck_sed02_aban1_yellow", "Land_Wreck_sed02_aban2_grey", "Land_Wreck_sed02_aban2_red", "Land_Wreck_sed02_aban2_yellow"};
        return reviewed.Find(name) >= 0;
    }

    static bool PositionValid(vector position)
    {
        // Bounds also reject NaN/infinity before rounding to integer decimetres.
        return position[0] >= 0 && position[0] <= 16000 && position[1] >= -500 && position[1] <= 3000 && position[2] >= 0 && position[2] <= 16000;
    }

    static string Key(string name, vector position)
    {
        int x = Math.Round(position[0] * 10);
        int y = Math.Round(position[1] * 10);
        int z = Math.Round(position[2] * 10);
        return name + "|" + x.ToString() + "|" + y.ToString() + "|" + z.ToString();
    }

    static int Roll(string key, int modulus)
    {
        // Reduce before negating, so int.MIN cannot overflow on abs.
        int result = key.Hash() % modulus;
        if (result < 0) result = -result;
        return result;
    }

    static int Budget(string key)
    {
        return Roll(key, 4);
    }

    static string Part(string key, int left)
    {
        int roll = Roll(key + "|part|" + left.ToString(), 100);
        if (roll < 2) return "HatchbackWheel";
        if (roll < 22) return "SparkPlug";
        if (roll < 37) return "CarBattery";
        if (roll < 52) return "CarRadiator";
        if (roll < 72) return "HeadlightH7";
        return "MetalPlate";
    }

    static bool Tool(ItemBase item)
    {
        if (!item || item.IsDamageDestroyed()) return false;
        string name = item.GetType();
        return name == "Wrench" || name == "Screwdriver" || name == "Pliers";
    }

    protected static bool HCWreckRay(PlayerBase player, Object wreck, vector origin, vector endpoint, int geometry)
    {
        vector contact;
        vector normal;
        int component;
        set<Object> hits = new set<Object>;
        // Slightly beyond cursor surface to avoid a ray ending before the mesh.
        vector beyond = endpoint + (endpoint - origin) * 0.05;
        if (!DayZPhysics.RaycastRV(origin, beyond, contact, normal, component, hits, null, player, true, false, geometry)) return false;
        // Review P2: objects behind the wreck must not refuse the action; the
        // contact check still proves the first surface hit is the wreck cursor point.
        return hits.Find(wreck) >= 0 && vector.DistanceSq(contact, endpoint) <= 0.25;
    }

    static bool Allowed(PlayerBase player, ActionTarget target, ItemBase item)
    {
        if (!player || !player.IsAlive() || player.IsUnconscious() || player.IsRestrained() || player.IsInVehicle()) return false;
        if (!Tool(item) || player.GetItemInHands() != item || !target || target.GetParent() || target.GetComponentIndex() < 0) return false;
        Object wreck = target.GetObject();
        if (!wreck || !Reviewed(wreck.GetType()) || Transport.Cast(wreck) || !PositionValid(wreck.GetPosition())) return false;
        vector endpoint = target.GetCursorHitPos();
        vector origin = MiscGameplayFunctions.GetPlayerHeadPosition(player);
        if (!PositionValid(endpoint) || !PositionValid(origin)) return false;
        if (vector.DistanceSq(player.GetPosition(), endpoint) > 4 || vector.DistanceSq(origin, endpoint) > 6.25 || vector.DistanceSq(wreck.GetPosition(), endpoint) > 36) return false;
        return HCWreckRay(player, wreck, origin, endpoint, ObjIntersectView) && HCWreckRay(player, wreck, origin, endpoint, ObjIntersectFire);
    }
}

class HCWreckSalvageModule : HCModule
{
    static const string PATH = "$profile:HollowCountry/wreck-salvage.json";
    static const int MAX_BYTES = 2097152;
    static const int MAX_WRECKS = 4096;
    protected static HCWreckSalvageModule s_Instance;
    protected bool m_Active;
    protected bool m_Busy;
    protected ref HCWreckSalvageState m_State;
    protected ref map<string, int> m_Index = new map<string, int>;
    protected ref array<ref HCWreckSalvageActionData> m_Sessions = new array<ref HCWreckSalvageActionData>;

    static HCWreckSalvageModule Get() { return s_Instance; }
    override string GetName() { return "WreckSalvage"; }
    override bool IsEnabled(HCSettings settings) { return settings && settings.EnableTravel; }

    bool Fault()
    {
        m_Active = false;
        Print("[HollowCountry] V2 wreck salvage inactive: journal/config fault; preserve journal, tmp and backup for recovery");
        return false;
    }

    static string Read(string path)
    {
        FileHandle handle = OpenFile(path, FileMode.READ);
        if (!handle) return "";
        string text;
        int count = ReadFile(handle, text, MAX_BYTES + 1);
        CloseFile(handle);
        if (count < 1 || count > MAX_BYTES || text.Length() > MAX_BYTES) return "";
        return text;
    }

    protected bool Valid(HCWreckSalvageState state)
    {
        if (!state || state.Version != 1 || !HCBuildIdentity.SameWorld(state.WorldName, GetGame().GetWorldName()) || !state.Rows || state.Rows.Count() > MAX_WRECKS) return false;
        map<string, bool> seen = new map<string, bool>;
        foreach (HCWreckSalvageRow row : state.Rows)
        {
            if (!row || !HCWreckSalvage.Reviewed(row.WreckClass) || !HCWreckSalvage.PositionValid(row.Position)) return false;
            // Review P2: never recompute the key from the JSON-reloaded float position,
            // which may round to another decimetre and fault the whole ledger on restart.
            if (row.Key == "" || seen.Contains(row.Key)) return false;
            if (row.Budget != HCWreckSalvage.Budget(row.Key) || row.Left < 0 || row.Left > row.Budget) return false;
            seen.Set(row.Key, true);
        }
        return true;
    }

    bool Load()
    {
        if (!FileExist("$profile:HollowCountry") && !MakeDirectory("$profile:HollowCountry")) return Fault();
        // An interrupted write is never an empty/new world. No backup rollback.
        if (FileExist(PATH + ".tmp")) return Fault();
        string error;
        if (FileExist(PATH))
        {
            string text = Read(PATH);
            HCWreckSalvageImage image;
            if (text == "" || !JsonFileLoader<HCWreckSalvageImage>.LoadData(text, image, error) || !image || image.Version != 1) return Fault();
            if (image.Length < 1 || image.Length != image.Payload.Length() || image.Hash != image.Payload.Hash()) return Fault();
            if (!JsonFileLoader<HCWreckSalvageState>.LoadData(image.Payload, m_State, error) || !Valid(m_State)) return Fault();
        }
        else
        {
            if (FileExist(PATH + ".bak")) return Fault();
            m_State = new HCWreckSalvageState;
            m_State.Version = 1;
            m_State.WorldName = HCBuildIdentity.CanonicalWorld(GetGame().GetWorldName());
            m_State.Rows = new array<ref HCWreckSalvageRow>;
            if (!Save()) return false;
        }
        for (int index = 0; index < m_State.Rows.Count(); index++)
            m_Index.Set(m_State.Rows[index].Key, index);
        return true;
    }

    bool Save()
    {
        if (!GetGame() || !GetGame().IsServer() || !Valid(m_State) || FileExist(PATH + ".tmp")) return Fault();
        string text;
        string error;
        HCWreckSalvageImage image = new HCWreckSalvageImage;
        image.Version = 1;
        if (!JsonFileLoader<HCWreckSalvageState>.MakeData(m_State, image.Payload, error)) return Fault();
        image.Length = image.Payload.Length();
        image.Hash = image.Payload.Hash();
        if (!JsonFileLoader<HCWreckSalvageImage>.MakeData(image, text, error) || text.Length() < 1 || text.Length() > MAX_BYTES) return Fault();
        FileHandle handle = OpenFile(PATH + ".tmp", FileMode.WRITE);
        if (!handle) return Fault();
        FPrint(handle, text);
        CloseFile(handle);
        if (Read(PATH + ".tmp") != text) return Fault();
        if (FileExist(PATH))
        {
            string oldText = Read(PATH);
            if (oldText == "") return Fault();
            if (FileExist(PATH + ".bak") && !DeleteFile(PATH + ".bak")) return Fault();
            if (!CopyFile(PATH, PATH + ".bak") || Read(PATH + ".bak") != oldText) return Fault();
            if (!DeleteFile(PATH)) return Fault();
        }
        if (!CopyFile(PATH + ".tmp", PATH) || Read(PATH) != text) return Fault();
        // This is the logical commit point. A remaining temp always blocks load.
        if (!DeleteFile(PATH + ".tmp")) return Fault();
        return true;
    }

    override void OnStart(HCSettings settings)
    {
        Print(HCV2Admission.Line("WreckSalvage", true, "EXP-T2", HCV2Gates.Qualified("EXP-T2")));
        s_Instance = this;
        m_Active = false;
        m_Index.Clear();
        m_Sessions.Clear();
        m_Busy = false;
        if (!GetGame() || !GetGame().IsServer() || !IsEnabled(settings)) return;
        if (!HCBuildIdentity.SameWorld(GetGame().GetWorldName(), "chernarusplus")) { Fault(); return; }
        array<string> parts = {"SparkPlug", "CarBattery", "CarRadiator", "HeadlightH7", "HatchbackWheel", "MetalPlate", "Wrench", "Screwdriver", "Pliers"};
        foreach (string part : parts)
        {
            if (!GetGame().ConfigIsExisting("CfgVehicles " + part) || GetGame().ConfigGetInt("CfgVehicles " + part + " scope") != 2) { Fault(); return; }
        }
        if (!Load()) return;
        m_Active = true;
        int remaining = 0;
        foreach (HCWreckSalvageRow row : m_State.Rows) remaining += row.Left;
        // Counts are enrolled wrecks, discovered lazily at an attempted salvage;
        // a fresh map starts at 0 without a whole-world scan.
        Print("[HollowCountry] V2 wreck salvage wrecks=" + m_State.Rows.Count().ToString() + " parts_left=" + remaining.ToString());
    }

    int Enroll(Object wreck)
    {
        if (!m_Active || !wreck) return -1;
        string key = HCWreckSalvage.Key(wreck.GetType(), wreck.GetPosition());
        int existing;
        if (m_Index.Find(key, existing)) return existing;
        if (m_State.Rows.Count() >= MAX_WRECKS) return -1;
        HCWreckSalvageRow row = new HCWreckSalvageRow;
        row.Key = key;
        row.WreckClass = wreck.GetType();
        row.Position = wreck.GetPosition();
        row.Budget = HCWreckSalvage.Budget(key);
        row.Left = row.Budget;
        int index = m_State.Rows.Insert(row);
        if (!Save()) return -1;
        m_Index.Set(key, index);
        return index;
    }

    // Single server-thread debit. Completion calls this once before item creation.
    // No refund even if saving/native creation fails: uncertainty cannot add loot.
    bool Debit(int index)
    {
        if (!m_Active || index < 0 || index >= m_State.Rows.Count()) return false;
        if (m_State.Rows[index].Left <= 0) return false;
        m_State.Rows[index].Left = m_State.Rows[index].Left - 1;
        if (!Save()) { m_Active = false; return false; }
        return true;
    }

    bool CanStart(PlayerBase player, ActionTarget target, ItemBase item)
    {
        if (!GetGame() || !GetGame().IsServer() || !m_Active || m_Busy || !player || !player.GetIdentity()) return false;
        if (!HCWreckSalvage.Allowed(player, target, item)) return false;
        int index = Enroll(target.GetObject());
        return index >= 0 && m_State.Rows[index].Left > 0;
    }

    void Purge()
    {
        int now = GetGame().GetTime();
        for (int index = m_Sessions.Count() - 1; index >= 0; index--)
        {
            HCWreckSalvageActionData data = m_Sessions[index];
            if (!data || data.Completed || !data.m_Player || !data.Wreck || now < data.StartedMs || now - data.StartedMs > 30000)
                m_Sessions.Remove(index);
        }
    }

    void Begin(HCWreckSalvageActionData data)
    {
        if (!data || data.Completed || !CanStart(data.m_Player, data.m_Target, data.m_MainItem)) return;
        Purge();
        if (m_Sessions.Count() >= 16) return;
        string key = HCWreckSalvage.Key(data.m_Target.GetObject().GetType(), data.m_Target.GetObject().GetPosition());
        foreach (HCWreckSalvageActionData session : m_Sessions)
        {
            if (session == data || session.Key == key || session.m_Player == data.m_Player) return;
        }
        data.Key = key;
        data.Wreck = data.m_Target.GetObject();
        data.Tool = data.m_MainItem;
        data.Index = Enroll(data.Wreck);
        data.StartedMs = GetGame().GetTime();
        if (data.Index >= 0) m_Sessions.Insert(data);
    }

    bool Continuing(HCWreckSalvageActionData data)
    {
        if (!GetGame() || !GetGame().IsServer() || !m_Active || m_Busy || !data || data.Completed || m_Sessions.Find(data) < 0) return false;
        if (!data.m_Target || data.m_Target.GetObject() != data.Wreck || data.m_MainItem != data.Tool || !data.m_Player || !data.m_Player.GetIdentity()) return false;
        int now = GetGame().GetTime();
        if (now < data.StartedMs || now - data.StartedMs > 30000) return false;
        if (!HCWreckSalvage.Allowed(data.m_Player, data.m_Target, data.Tool)) return false;
        if (data.Key != HCWreckSalvage.Key(data.Wreck.GetType(), data.Wreck.GetPosition())) return false;
        return data.Index >= 0 && data.Index < m_State.Rows.Count() && m_State.Rows[data.Index].Key == data.Key && m_State.Rows[data.Index].Left > 0;
    }

    void Complete(HCWreckSalvageActionData data)
    {
        if (!Continuing(data) || GetGame().GetTime() - data.StartedMs < 7500) return;
        data.Completed = true;
        m_Busy = true;
        HCWreckSalvageRow row = m_State.Rows[data.Index];
        string partType = HCWreckSalvage.Part(row.Key, row.Left);
        if (!Debit(data.Index)) { m_Busy = false; return; }
        // Server only, native ground inventory creation exactly at actor's feet.
        // Tool stays in hands; no client inventory state or retry/fallback spawn.
        InventoryLocation ground = new InventoryLocation;
        vector transform[4];
        Math3D.MatrixIdentity4(transform);
        transform[3] = data.m_Player.GetPosition();
        ground.SetGround(null, transform);
        ItemBase part = ItemBase.Cast(GameInventory.LocationCreateEntity(ground, partType, ECE_PLACE_ON_SURFACE, RF_DEFAULT));
        m_Busy = false;
        if (!part)
        {
            Print("[HollowCountry] V2 wreck salvage create failed; debit retained class=" + row.WreckClass + " part=" + partType);
            return;
        }
        if (partType == "MetalPlate") part.SetQuantity(1);
        HCSearchNoise.Emit(data.m_Player);
        Print("[HollowCountry] V2 wreck salvaged class=" + row.WreckClass + " part=" + partType + " left=" + row.Left.ToString());
    }

    void End(HCWreckSalvageActionData data)
    {
        int index = m_Sessions.Find(data);
        if (index >= 0) m_Sessions.Remove(index);
    }

    override void OnTick(float deltaTime)
    {
        if (m_Active) Purge(); // At most 16 sessions; no world scans.
    }

    override void OnStop()
    {
        // Every mutation already saved synchronously before a reward; do not
        // overwrite a faulted journal during shutdown.
        if (m_Active) Save();
        m_Active = false;
        m_Sessions.Clear();
        s_Instance = null;
    }
}

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        Register(new HCWreckSalvageModule);
    }
}
