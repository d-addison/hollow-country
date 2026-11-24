// W6 runtime site guard, 3_Game half. Composed site rows carry customString "hcsite:<site>:<part>".
// Native evidence scripts-1.30.164289: 3_Game/ObjectSpawner.c:48-53 spawn flags and :100-108 ITEM_SpawnerObject
// (customString); 3_Game/DayZ/DayZGame.c:1174 GlobalsInit enters the spawner before storage load and before
// any HC module; 3_Game/tools/JsonFileLoader.c:69 LoadData; 1_Core/proto/EnSystem.c:397 FileExist;
// 1_Core/proto/EnString.c:113/199 Substring/Length, :171 ToLower; Game.c:934 GetWorldName; EnDebug.c:96 Print.
// Only sites recorded admitted for the installed LayerSet in the profile state spawn here. Every other site
// row is held in HCSiteDeferred; the 4_World HCSiteGuard decides after storage load and spawns through
// HCSpawnDeferred. Site pieces are non-persistent (enableCEPersistency=false), so deferring or skipping a row
// never strands a stored object. A torn or interrupted state file cannot be recovered here (3_Game has only
// HCGroupIO.Read/HCLooksWholeObject): the state is unknown, so every site defers and the guard recovers it.
class HCSiteManifestSite
{
    string Id;
    ref array<float> Centre = new array<float>;
    float Radius;
    int Parts;
    ref array<ref array<float>> Hard = new array<ref array<float>>;
    ref array<ref array<float>> Loot = new array<ref array<float>>;
    int FortRing;
}

// Installed read-only manifest ($mission:hollow-country-overlays/sites.json, written by the composer).
class HCSiteManifest
{
    int Version;
    string LayerSet;
    ref array<ref HCSiteManifestSite> Sites = new array<ref HCSiteManifestSite>;
    ref array<ref array<float>> Retired = new array<ref array<float>>;
}

class HCSiteDecision
{
    string Site;
    int State;
    string Reason;
    int Attempts;
}

class HCSiteSweep
{
    string From;
    int Total;
    int Cursor;
    bool Done;
    int Snapped;
    int Kept;
    ref array<int> Skipped = new array<int>;
    // Source boxes of a previous layer set, copied here so they survive the LootBoxes overwrite.
    // A legacy sweep reads the manifest's Retired list instead (too large for the state file).
    ref array<ref array<float>> Boxes = new array<ref array<float>>;
}

// $profile:HollowCountry/sites.json (version 1). State 0 undecided or retry, 1 admitted, 2 refused.
class HCSiteState
{
    int Version;
    string WorldName;
    string LayerSet;
    int Boots;
    ref array<ref HCSiteDecision> Decisions = new array<ref HCSiteDecision>;
    ref array<ref array<float>> LootBoxes = new array<ref array<float>>;
    string PrevLayerSet;
    ref HCSiteSweep Sweep = new HCSiteSweep;
}

// What the spawner needs from the state: the layer set and the admitted site ids.
class HCSiteStateView
{
    bool Known;
    string LayerSet;
    ref map<string, bool> Admitted = new map<string, bool>;
}

// Shared format checks for the manifest and the state (both script layers).
class HCSiteFormat
{
    static const int MAX_SITES = 128;
    static const int MAX_PARTS = 1800;
    static const int MAX_LOOT = 300;
    static const int MAX_RETIRED = 4000;
    static const int MAX_STATE_BOXES = 400;
    static const int MANIFEST_BYTES = 262144;
    static const int STATE_BYTES = 262144;
    static const string MANIFEST_PATH = "$mission:hollow-country-overlays/sites.json";
    static const string STATE_PATH = "$profile:HollowCountry/sites.json";

    static bool IsHex64(string text)
    {
        if (text.Length() != 64) { return false; }
        string lowered = text;
        lowered.ToLower();
        string digits = "0123456789abcdef";
        for (int index = 0; index < 64; index++)
        {
            if (digits.IndexOf(lowered.Substring(index, 1)) < 0) { return false; }
        }
        return true;
    }

    static string WorldName()
    {
        string name = GetGame().GetWorldName();
        name.ToLower();
        return name;
    }

    // A 2-D box row: [x, z, halfX, halfZ, yawDeg].
    static bool BoxRowValid(array<float> row)
    {
        if (!row || row.Count() != 5) { return false; }
        if (!(row[0] >= 0 && row[0] <= 30000 && row[1] >= 0 && row[1] <= 30000)) { return false; }
        return row[2] > 0 && row[2] <= 50 && row[3] > 0 && row[3] <= 50;
    }

    // A hard piece row: [x, surveyY, z, halfX, halfY, halfZ, yawDeg, cornerSpread]. surveyY <= 0 is a
    // per-site survey_missing refusal, not a manifest fault.
    static bool HardRowValid(array<float> row)
    {
        if (!row || row.Count() != 8) { return false; }
        if (!(row[0] >= 0 && row[0] <= 30000 && row[2] >= 0 && row[2] <= 30000)) { return false; }
        if (!(row[3] > 0 && row[3] <= 100 && row[4] > 0 && row[4] <= 100 && row[5] > 0 && row[5] <= 100)) { return false; }
        return row[7] >= 0 && row[7] <= 50;
    }

    // Empty reason = the manifest is within every cap and shape.
    static string ManifestFault(HCSiteManifest manifest)
    {
        if (!manifest || manifest.Version != 1) { return "version"; }
        if (!IsHex64(manifest.LayerSet)) { return "layer_set"; }
        if (!manifest.Sites || manifest.Sites.Count() < 1 || manifest.Sites.Count() > HCSiteFormat.MAX_SITES) { return "site_count"; }
        int parts;
        int loot;
        map<string, bool> seen = new map<string, bool>;
        foreach (HCSiteManifestSite site : manifest.Sites)
        {
            if (!site || site.Id == "" || site.Id.Length() > 64 || seen.Contains(site.Id)) { return "site_id"; }
            seen.Set(site.Id, true);
            if (site.Id.IndexOf(":") >= 0) { return "site_id"; }
            if (!site.Centre || site.Centre.Count() != 3 || !(site.Radius > 0 && site.Radius <= 200)) { return "site_shape"; }
            if (site.Parts < 1 || site.Parts > HCSiteFormat.MAX_PARTS) { return "parts"; }
            if (site.FortRing < 0 || site.FortRing > 500) { return "fort_ring"; }
            parts = parts + site.Parts;
            if (!site.Hard || site.Hard.Count() > site.Parts) { return "hard_rows"; }
            foreach (array<float> hard : site.Hard) { if (!HardRowValid(hard)) { return "hard_rows"; } }
            if (!site.Loot) { return "loot_rows"; }
            loot = loot + site.Loot.Count();
            foreach (array<float> box : site.Loot) { if (!BoxRowValid(box)) { return "loot_rows"; } }
        }
        if (parts > HCSiteFormat.MAX_PARTS) { return "parts"; }
        if (loot > HCSiteFormat.MAX_LOOT) { return "loot_rows"; }
        if (!manifest.Retired || manifest.Retired.Count() > HCSiteFormat.MAX_RETIRED) { return "retired_rows"; }
        foreach (array<float> retired : manifest.Retired) { if (!BoxRowValid(retired)) { return "retired_rows"; } }
        return "";
    }

    // Shape and cap checks only; membership of site ids in the manifest is the guard's job.
    static bool StateValid(HCSiteState state)
    {
        if (!state || state.Version != 1 || state.WorldName != HCSiteFormat.WorldName()) { return false; }
        if (state.LayerSet != "" && state.LayerSet != "legacy" && !IsHex64(state.LayerSet)) { return false; }
        if (state.PrevLayerSet != "" && state.PrevLayerSet != "legacy" && !IsHex64(state.PrevLayerSet)) { return false; }
        if (state.Boots < 0 || !state.Decisions || state.Decisions.Count() > HCSiteFormat.MAX_SITES) { return false; }
        map<string, bool> seen = new map<string, bool>;
        foreach (HCSiteDecision decision : state.Decisions)
        {
            if (!decision || decision.Site == "" || decision.Site.Length() > 64 || seen.Contains(decision.Site)) { return false; }
            seen.Set(decision.Site, true);
            if (decision.State < 0 || decision.State > 2 || decision.Attempts < 0 || decision.Attempts > 1000000) { return false; }
            if (decision.Reason.Length() > 64) { return false; }
        }
        if (!state.LootBoxes || state.LootBoxes.Count() > HCSiteFormat.MAX_STATE_BOXES) { return false; }
        foreach (array<float> box : state.LootBoxes) { if (!BoxRowValid(box)) { return false; } }
        HCSiteSweep sweep = state.Sweep;
        if (!sweep || sweep.Total < 0 || sweep.Cursor < 0 || sweep.Cursor > sweep.Total || sweep.Snapped < 0 || sweep.Kept < 0) { return false; }
        if (sweep.From.Length() > 64 || !sweep.Skipped || sweep.Skipped.Count() > HCSiteFormat.MAX_RETIRED) { return false; }
        if (!sweep.Boxes || sweep.Boxes.Count() > HCSiteFormat.MAX_STATE_BOXES) { return false; }
        foreach (array<float> sweepBox : sweep.Boxes) { if (!BoxRowValid(sweepBox)) { return false; } }
        foreach (int skipped : sweep.Skipped) { if (skipped < 0 || skipped >= sweep.Total) { return false; } }
        return true;
    }
}

// Preserve native creation, scale, persistence flags and callbacks. Context is scoped
// to the synchronous native file-order spawn loop; other layers stay untouched.
modded class ObjectSpawnerHandler
{
    static const int HC_SITE_DEFER_CAP = 2000;
    static bool HCGroundLayer;
    static int HCPathgraphMarked;
    static int HCPathgraphSkipped;
    static ref HCGroundSnapStats HCGroundStats;
    static ref HCGroundPlaceStats HCPlaceStats;
    static ref HCGroundLayerJson HCGroundSidecar;
    static int HCGroundRowIndex;
    // W6 site routing state (see the header comment).
    static bool HCSiteManifestOk;
    static bool HCSiteManifestPresent;
    static bool HCSiteKnown;
    static bool HCSiteBypass;
    static int HCSiteDeferredRows;
    static int HCSiteAdmittedRows;
    static int HCSiteOverflow;
    static int HCLastResult;
    static Object HCLastPlaced;
    static ref HCGroundRowJson HCSiteRowOverride;
    static ref HCSiteManifest HCSiteManifestData;
    static ref HCSiteStateView HCSiteView;
    static ref map<string, int> HCSiteParts;
    static ref map<string, int> HCSiteSeen;
    static ref map<string, string> HCSiteInvalid;
    static ref map<string, string> HCSiteCreateFailed;
    static ref map<string, ref array<ref ITEM_SpawnerObject>> HCSiteDeferred;
    static ref map<string, ref array<ref HCGroundRowJson>> HCSiteDeferredGround;

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
        HCSiteLoadViews();
        TStringArray paths = CfgGameplayHandler.GetObjectSpawnersArr();
        if (!paths) { HCGroundStats.Summary("object_spawner"); HCPlaceStats.Summary("object_spawner"); HCPathgraphSummary(); HCSiteSummary(); return; }
        // Pass 1 (only with a valid manifest): tally composed rows over every HC layer so a mismatch is known
        // before the first site piece spawns.
        if (HCSiteManifestOk)
        {
            foreach (string scanPath : paths)
            {
                if (scanPath.IndexOf("hollow-country-") != 0) { continue; }
                string scanError;
                ObjectSpawnerJson scanLayer;
                if (JsonFileLoader<ObjectSpawnerJson>.LoadFile("$mission:" + scanPath, scanLayer, scanError))
                {
                    if (scanLayer && scanLayer.Objects) { HCSitePrescan(scanLayer.Objects); }
                }
            }
            HCSiteFinishPrescan();
        }
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
        HCSiteSummary();
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

    // ---- W6 site routing -------------------------------------------------------------------------------

    // Site id of a composed row ("hcsite:<site>:<part>"), or empty for every other row.
    static string HCSiteIdOf(ITEM_SpawnerObject item)
    {
        string tag = item.customString;
        if (tag.IndexOf("hcsite:") != 0) { return ""; }
        string rest = tag.Substring(7, tag.Length() - 7);
        int colon = rest.IndexOf(":");
        if (colon < 1) { return ""; }
        return rest.Substring(0, colon);
    }

    // Loads the installed manifest and the profile state. The state is "unknown" (Known=false, so every site
    // defers) when a .tmp exists, when the primary is missing but a .bak exists, or when it fails the shape check.
    // An absent state with no .tmp/.bak is a known empty state (first boot).
    static void HCSiteLoadViews()
    {
        HCSiteManifestOk = false;
        HCSiteManifestPresent = false;
        HCSiteKnown = false;
        HCSiteDeferredRows = 0;
        HCSiteAdmittedRows = 0;
        HCSiteOverflow = 0;
        HCSiteManifestData = null;
        HCSiteView = new HCSiteStateView;
        HCSiteParts = new map<string, int>;
        HCSiteSeen = new map<string, int>;
        HCSiteInvalid = new map<string, string>;
        HCSiteCreateFailed = new map<string, string>;
        HCSiteDeferred = new map<string, ref array<ref ITEM_SpawnerObject>>;
        HCSiteDeferredGround = new map<string, ref array<ref HCGroundRowJson>>;
        HCSiteManifestPresent = FileExist(HCSiteFormat.MANIFEST_PATH);
        if (HCSiteManifestPresent)
        {
            HCSiteManifest manifest;
            if (HCGroupJson<HCSiteManifest>.Load(HCSiteFormat.MANIFEST_PATH, HCSiteFormat.MANIFEST_BYTES, manifest))
            {
                if (HCSiteFormat.ManifestFault(manifest) == "")
                {
                    HCSiteManifestOk = true;
                    HCSiteManifestData = manifest;
                    foreach (HCSiteManifestSite site : manifest.Sites) { HCSiteParts.Set(site.Id, site.Parts); }
                }
            }
        }
        string statePath = HCSiteFormat.STATE_PATH;
        bool tmpExists = FileExist(statePath + ".tmp");
        bool primaryExists = FileExist(statePath);
        bool bakExists = FileExist(statePath + ".bak");
        if (tmpExists || (!primaryExists && bakExists)) { return; }
        if (!primaryExists) { HCSiteKnown = true; return; }
        HCSiteState state;
        if (!HCGroupIO.HCLooksWholeObject(statePath, HCSiteFormat.STATE_BYTES)) { return; }
        if (!HCGroupJson<HCSiteState>.Load(statePath, HCSiteFormat.STATE_BYTES, state)) { return; }
        if (!HCSiteFormat.StateValid(state)) { return; }
        HCSiteKnown = true;
        HCSiteView.Known = true;
        HCSiteView.LayerSet = state.LayerSet;
        if (!HCSiteManifestOk || state.LayerSet != HCSiteManifestData.LayerSet) { return; }
        foreach (HCSiteDecision decision : state.Decisions)
        {
            if (decision.State == 1 && HCSiteParts.Contains(decision.Site)) { HCSiteView.Admitted.Set(decision.Site, true); }
        }
    }

    static void HCSiteMarkInvalid(string siteId, string reason)
    {
        if (!HCSiteInvalid.Contains(siteId)) { HCSiteInvalid.Set(siteId, reason); }
    }

    // Per-row checks that need no world access: unknown site id, CE persistence, missing survey height.
    static void HCSitePrescan(array<ref ITEM_SpawnerObject> rows)
    {
        foreach (ITEM_SpawnerObject row : rows)
        {
            string siteId = HCSiteIdOf(row);
            if (siteId == "") { continue; }
            if (!HCSiteParts.Contains(siteId)) { HCSiteMarkInvalid(siteId, "manifest_mismatch"); continue; }
            int seen = 0;
            if (HCSiteSeen.Contains(siteId)) { seen = HCSiteSeen.Get(siteId); }
            HCSiteSeen.Set(siteId, seen + 1);
            if (row.enableCEPersistency) { HCSiteMarkInvalid(siteId, "ce_persistent_row"); }
            else if (row.pos[1] <= 0) { HCSiteMarkInvalid(siteId, "survey_missing"); }
        }
    }

    static void HCSiteFinishPrescan()
    {
        foreach (string siteId, int parts : HCSiteParts)
        {
            int seen = 0;
            if (HCSiteSeen.Contains(siteId)) { seen = HCSiteSeen.Get(siteId); }
            if (seen != parts) { HCSiteMarkInvalid(siteId, "manifest_mismatch"); }
        }
    }

    // True = spawn this row now. Everything else is kept for the guard pass (fail closed).
    static bool HCSiteRoute(string siteId, ITEM_SpawnerObject item)
    {
        if (HCSiteManifestOk && HCSiteKnown && HCSiteView.Admitted.Contains(siteId) && !HCSiteInvalid.Contains(siteId)) { return true; }
        if (HCSiteDeferredRows >= HC_SITE_DEFER_CAP)
        {
            HCSiteOverflow++;
            HCSiteMarkInvalid(siteId, "manifest_mismatch");
            return false;
        }
        if (!HCSiteDeferred.Contains(siteId))
        {
            HCSiteDeferred.Set(siteId, new array<ref ITEM_SpawnerObject>);
            HCSiteDeferredGround.Set(siteId, new array<ref HCGroundRowJson>);
        }
        HCSiteDeferred.Get(siteId).Insert(item);
        HCGroundRowJson ground;
        if (HCGroundSidecar && HCGroundRowIndex >= 0) { ground = HCGroundSidecar.Ground[HCGroundRowIndex]; }
        HCSiteDeferredGround.Get(siteId).Insert(ground);
        HCSiteDeferredRows++;
        return false;
    }

    // One log line per site, on its first deferred row.
    static void HCSiteNoteDeferred(string siteId)
    {
        array<ref ITEM_SpawnerObject> rows;
        if (HCSiteDeferred.Find(siteId, rows) && rows.Count() == 1)
        {
            Print("[HC Sites] deferred site=" + siteId + " reason=awaiting_guard");
        }
    }

    // The guard spawns one deferred row. Returns the placed object (null for a static-p3d row, a refusal or a
    // failed creation); HCLastResult is 0 spawned, 1 creation failed, 2 refused by the ground placement.
    static Object HCSpawnDeferred(ITEM_SpawnerObject item, HCGroundRowJson ground)
    {
        bool oldLayer = HCGroundLayer;
        HCGroundLayer = true;
        HCSiteBypass = true;
        HCSiteRowOverride = ground;
        HCLastPlaced = null;
        HCLastResult = 0;
        if (!HCPlaceStats) { HCPlaceStats = new HCGroundPlaceStats; }
        if (!HCGroundStats) { HCGroundStats = new HCGroundSnapStats; }
        SpawnObject(item);
        HCSiteBypass = false;
        HCSiteRowOverride = null;
        HCGroundLayer = oldLayer;
        return HCLastPlaced;
    }

    static void HCSiteSummary()
    {
        Print("[HC Ground] sites source=object_spawner manifest=" + HCSiteManifestOk.ToString() + " state_known=" + HCSiteKnown.ToString() + " deferred=" + HCSiteDeferredRows.ToString() + " admitted_rows=" + HCSiteAdmittedRows.ToString() + " invalid_sites=" + HCSiteInvalid.Count().ToString() + " overflow=" + HCSiteOverflow.ToString());
        foreach (string siteId, string reason : HCSiteInvalid) { Print("[HC Ground] site_invalid site=" + siteId + " reason=" + reason); }
    }

    override static void SpawnObject(ITEM_SpawnerObject item)
    {
        string siteId = "";
        if (HCGroundLayer) { siteId = HCSiteIdOf(item); }
        if (siteId != "" && !HCSiteBypass && !HCSiteRoute(siteId, item))
        {
            HCSiteNoteDeferred(siteId);
            return;
        }
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
        if (!placedObject)
        {
            PrintToRPT("Object spawner failed to spawn " + item.name);
            if (siteId != "")
            {
                HCLastResult = 1;
                if (!HCSiteCreateFailed.Contains(siteId)) { HCSiteCreateFailed.Set(siteId, item.name); }
            }
            return;
        }
        placedObject.SetOrientation(vector.ArrayToVec(item.ypr));
        float scale = item.scale;
        if (scale == 0) { scale = 1; }
        if (item.scale != 1) { placedObject.SetScale(scale); }
        placedObject.OnSpawnByObjectSpawner(item);
        // Ground placement (wh-ground): the sidecar row gives the pivot height over the lowest ground under
        // the footprint; the old 25 m ray snap (#335) stays only for a layer without a sidecar.
        HCGroundRowJson groundRow = HCSiteRowOverride;
        if (!groundRow && HCGroundSidecar && HCGroundRowIndex >= 0) { groundRow = HCGroundSidecar.Ground[HCGroundRowIndex]; }
        if (groundRow)
        {
            string refusalReason;
            int placed = HCGroundSnap.Place(placedObject, groundRow.pivot, groundRow.embed, groundRow.loot == 1, HCPlaceStats, refusalReason);
            if (placed == HCGroundSnap.PLACE_REFUSED)
            {
                HCPlaceStats.ReportRemoval(item.name, HCGroundRowIndex, refusalReason);
                if (siteId != "") { HCLastResult = 2; }
                return;
            }
        }
        else
        {
            HCPlaceStats.Placed++;
            HCPlaceStats.Legacy++;
            HCGroundSnap.Snap(placedObject, 25, 0.01, HCGroundStats);
        }
        if (siteId != "")
        {
            HCLastPlaced = placedObject;
            if (!HCSiteBypass) { HCSiteAdmittedRows++; }
        }
        if (HCPathgraphRefresh.Mark(placedObject)) { HCPathgraphMarked++; }
        else { HCPathgraphSkipped++; }
    }
}
