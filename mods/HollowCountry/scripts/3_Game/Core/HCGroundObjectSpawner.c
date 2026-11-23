// Preserve native creation, scale, persistence flags and callbacks. Context is scoped
// to the synchronous native file-order spawn loop; other layers stay untouched.
modded class ObjectSpawnerHandler
{
    static bool HCGroundLayer;
    static int HCPathgraphMarked;
    static int HCPathgraphSkipped;
    static ref HCGroundSnapStats HCGroundStats;
    static ref HCGroundPlaceStats HCPlaceStats;
    static ref HCGroundLayerJson HCGroundSidecar;
    static int HCGroundRowIndex;

    // #335: vanilla OnGameplayDataHandlerLoad (3_Game/ObjectSpawner.c:71) calls
    // SpawnObjects() unqualified inside the vanilla class, which binds to the vanilla
    // static, so the override below never ran (no "[HC Ground] source=object_spawner"
    // line in any native boot). DayZGame.GlobalsInit (DayZGame.c:1174) enters through
    // the class name, so the entry is re-declared here and its call binds to HC.
    override static void OnGameplayDataHandlerLoad()
    {
        if (g_Game && g_Game.IsServer())
        {
            SpawnObjects();
            g_Game.GetWorld().ProcessMarkedObjectsForPathgraphUpdate();
        }
    }

    override static void SpawnObjects()
    {
        HCGroundStats = new HCGroundSnapStats;
        HCPlaceStats = new HCGroundPlaceStats;
        HCPathgraphMarked = 0;
        HCPathgraphSkipped = 0;
        TStringArray paths = CfgGameplayHandler.GetObjectSpawnersArr();
        if (!paths) { HCGroundStats.Summary("object_spawner"); HCPlaceStats.Summary("object_spawner"); HCPathgraphSummary(); return; }
        foreach (string relativePath : paths)
        {
            HCGroundLayer = relativePath.IndexOf("hollow-country-") == 0;
            string error;
            ObjectSpawnerJson layer;
            if (JsonFileLoader<ObjectSpawnerJson>.LoadFile("$mission:" + relativePath, layer, error))
            {
                if (layer && layer.Objects) { HCSpawnLayer(relativePath, layer.Objects); }
            }
            else { ErrorEx(error); }
            HCGroundLayer = false;
            HCGroundSidecar = null;
        }
        HCGroundStats.Summary("object_spawner");
        HCPlaceStats.Summary("object_spawner");
        HCPathgraphSummary();
        // Native OnGameplayDataHandlerLoad calls ProcessMarkedObjectsForPathgraphUpdate
        // exactly once immediately after this synchronous override returns.
    }

    // Rows go through SpawnObject by index so each can read its ground sidecar row. A layer without a
    // sidecar of the same length (an install from before the sidecar) falls back to the plain snap.
    static void HCSpawnLayer(string relativePath, array<ref ITEM_SpawnerObject> rows)
    {
        HCGroundSidecar = null;
        HCGroundRowIndex = -1;
        if (HCGroundLayer)
        {
            HCPlaceStats.Layers++;
            string sidecarPath = relativePath;
            int length = relativePath.Length();
            if (length > 5 && relativePath.Substring(length - 5, 5) == ".json")
            {
                sidecarPath = relativePath.Substring(0, length - 5) + ".ground.json";
                string sidecarError;
                HCGroundLayerJson sidecar;
                if (FileExist("$mission:" + sidecarPath) && JsonFileLoader<HCGroundLayerJson>.LoadFile("$mission:" + sidecarPath, sidecar, sidecarError))
                {
                    if (sidecar && sidecar.Ground && sidecar.Ground.Count() == rows.Count()) { HCGroundSidecar = sidecar; }
                }
            }
        }
        int count = rows.Count();
        for (int index = 0; index < count; index++)
        {
            if (HCGroundSidecar) { HCGroundRowIndex = index; }
            SpawnObject(rows[index]);
        }
        HCGroundRowIndex = -1;
    }

    static void HCPathgraphSummary()
    {
        Print("" + "[HC Pathgraph] domain=object_spawner marked=" + HCPathgraphMarked.ToString() + " affected=0 skipped_no_geom=" + HCPathgraphSkipped.ToString());
    }
    override static void SpawnObject(ITEM_SpawnerObject item)
    {
        if (!HCGroundLayer || item.name.Contains("\\") || item.name.Contains("/"))
        {
            // Native static-P3D placement is deliberately outside this correction.
            super.SpawnObject(item);
            return;
        }
        int flags = ECE_SETUP | ECE_CREATEPHYSICS | ECE_NOLIFETIME | ECE_DYNAMIC_PERSISTENCY | ECE_OBJECT_SPAWNER;
        if (item.enableCEPersistency)
        {
            flags &= ~ECE_DYNAMIC_PERSISTENCY;
            flags &= ~ECE_NOLIFETIME;
        }
        Object placedObject = g_Game.CreateObjectEx(item.name, vector.ArrayToVec(item.pos), flags, RF_IGNORE);
        if (!placedObject) { PrintToRPT("Object spawner failed to spawn " + item.name); return; }
        placedObject.SetOrientation(vector.ArrayToVec(item.ypr));
        float scale = item.scale;
        if (scale == 0) { scale = 1; }
        if (item.scale != 1) { placedObject.SetScale(scale); }
        placedObject.OnSpawnByObjectSpawner(item);
        // Ground placement (wh-ground): the sidecar row gives the pivot height over the lowest ground under
        // the footprint; the old 25 m ray snap (#335) stays only for a layer without a sidecar.
        if (HCGroundSidecar && HCGroundRowIndex >= 0)
        {
            HCGroundRowJson groundRow = HCGroundSidecar.Ground[HCGroundRowIndex];
            int placed = HCGroundSnap.Place(placedObject, groundRow.pivot, groundRow.embed, groundRow.loot == 1, HCPlaceStats);
            if (placed == HCGroundSnap.PLACE_REFUSED)
            {
                // Refused props are removed: the footprint slope or the height correction broke the rule.
                if (HCPlaceStats.Refused <= 8) { Print("[HC Ground] refused_sample type=" + item.name + " layer_row=" + HCGroundRowIndex.ToString() + " removed=1"); }
                return;
            }
        }
        else
        {
            HCPlaceStats.Placed++;
            HCPlaceStats.Legacy++;
            HCGroundSnap.Snap(placedObject, 25, 0.01, HCGroundStats);
        }
        if (HCPathgraphRefresh.Mark(placedObject)) { HCPathgraphMarked++; }
        else { HCPathgraphSkipped++; }
    }
}
