// Preserve native creation, scale, persistence flags and callbacks. Context is scoped
// to the synchronous native file-order spawn loop; other layers stay untouched.
modded class ObjectSpawnerHandler
{
    static bool HCGroundLayer;
    static int HCPathgraphMarked;
    static int HCPathgraphSkipped;
    static ref HCGroundSnapStats HCGroundStats;

    override static void SpawnObjects()
    {
        HCGroundStats = new HCGroundSnapStats;
        HCPathgraphMarked = 0;
        HCPathgraphSkipped = 0;
        TStringArray paths = CfgGameplayHandler.GetObjectSpawnersArr();
        if (!paths) { HCGroundStats.Summary("object_spawner"); HCPathgraphSummary(); return; }
        foreach (string relativePath : paths)
        {
            HCGroundLayer = relativePath.IndexOf("hollow-country-") == 0;
            string error;
            ObjectSpawnerJson layer;
            if (JsonFileLoader<ObjectSpawnerJson>.LoadFile("$mission:" + relativePath, layer, error))
            {
                if (layer && layer.Objects)
                {
                    foreach (ITEM_SpawnerObject row : layer.Objects) { SpawnObject(row); }
                }
            }
            else { ErrorEx(error); }
            HCGroundLayer = false;
        }
        HCGroundStats.Summary("object_spawner");
        HCPathgraphSummary();
        // Native OnGameplayDataHandlerLoad calls ProcessMarkedObjectsForPathgraphUpdate
        // exactly once immediately after this synchronous override returns.
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
        float drop = 3;
        if (item.name.IndexOf("Land_") == 0 || item.name.IndexOf("StaticObj_") == 0) { drop = 25; }
        HCGroundSnap.Snap(placedObject, drop, 0.01, HCGroundStats);
        if (HCPathgraphRefresh.Mark(placedObject)) { HCPathgraphMarked++; }
        else { HCPathgraphSkipped++; }
    }
}
