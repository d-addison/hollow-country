// Preserve native creation, scale, persistence flags and callbacks. Context is scoped
// to the synchronous native file-order spawn loop; other layers stay untouched.
modded class ObjectSpawnerHandler
{
    static bool HCGroundLayer;
    static int HCPathgraphMarked;
    static int HCPathgraphSkipped;
    static ref HCGroundSnapStats HCGroundStats;

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
        // #335: HC layers store one flat height per site (offline estimate), so small
        // props on a slope can sit up to ~25 m above the ground; a 3 m window left them
        // floating (no_hit). Every HC layer prop gets the 25 m window; the ray still
        // stops at the first surface below and the rise stays bounded.
        float drop = 25;
        HCGroundSnap.Snap(placedObject, drop, 0.01, HCGroundStats);
        if (HCPathgraphRefresh.Mark(placedObject)) { HCPathgraphMarked++; }
        else { HCPathgraphSkipped++; }
    }
}
