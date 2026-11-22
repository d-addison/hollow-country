// Native scripts-1.30.164289: 1_Core/proto/EnScript.c:902/917 map Set/Contains.
// Native 1.30.164289: 3_Game/Global/Game.c:1550 GetCallQueue; 2_GameLib/tools.c:65 ScriptCallQueue.Remove(func);
// 3_Game/Entities/Object.c:467 GetType; 3_Game/Global/Game.c:703 CreateObjectEx.
// Reviewed context groups for a bound search site, built by HCSearchHouses from the pack and
// the measured record. SourcePin binds the source manifest; script checks binding/syntax, not
// SHA-256 authenticity.
class HCInteriorSearchContext
{
    string InstanceId;
    string LayoutId;
    string History;
    string Room;
    string GroupId;
    string SourcePin;
    string EvidencePin;
    string MeasuredRecordSha256;
    ref array<string> Items = new array<string>;
}

// Core host of the interior layers: template pack load and placement, the measured catalog,
// pathgraph refresh, coverage, perf slices and self-tests are modded onto this class. The
// House search itself is HCSearchHouses, reached through the search hook overrides. The legacy
// interiors.json pilot is retired: the file is ignored, never read, deleted or required.
class HCInteriorsModule : HCModule
{
    // Set by the template-load tick once the pack is loaded; every layer guards on it.
    protected static HCInteriorsModule s_Instance;
    protected ref array<Object> m_Objects = new array<Object>;

    static HCInteriorsModule Get()
    {
        return s_Instance;
    }

    override string GetName()
    {
        return "Interiors";
    }

    override bool IsEnabled(HCSettings settings)
    {
        return settings && settings.EnableInteriors;
    }

    override void OnStart(HCSettings settings)
    {
        if (!GetGame().IsServer() || !IsEnabled(settings) || s_Instance) return;
        HCInteriorQueryConfig.HCGet();
        #ifdef DIAG_DEVELOPER
        if (!HCInteriorSelfTests.Run())
        {
            Print("[HC Interiors] algorithm self-tests failed; disabled");
            return;
        }
        #endif
        // An interiors.json left by an earlier release is neither loaded nor removed.
        if (FileExist("$profile:HollowCountry/interiors.json"))
        {
            Print("[HC Interiors] legacy pilot retired: interiors.json ignored");
        }
    }

    int InspectProp(vector point, vector orientation, string type, out Object reusable)
    {
        reusable = null;
        array<Object> objects = new array<Object>;
        // Every furnished prop uses this orphan check. Avoid enumerating the
        // building's unused cargo proxies on every slot (#275).
        GetGame().GetObjectsAtPosition3D(point, 0.75, objects, null);
        if (objects.Count() > 256) return 3;
        int matches;
        int ownedCount;
        bool exact = true;
        foreach (Object object : objects)
        {
            if (!object || object.GetType() != type || vector.DistanceSq(object.GetPosition(), point) >= 0.0625) continue;
            matches++;
            // Only exact nearby type/position matches need an ownership lookup;
            // the retained prop array is capped by MaxFurnishedProps (<=1500).
            if (m_Objects.Find(object) >= 0)
            {
                ownedCount++;
                reusable = object;
            }
            if (HCInteriorRules.TransformKey(object.GetPosition(), object.GetOrientation()) != HCInteriorRules.TransformKey(point, orientation)) exact = false;
        }
        int decision = HCInteriorRules.OrphanDecision(true, matches, ownedCount, exact);
        if (decision != 1) reusable = null;
        return decision;
    }

    // Search hooks for the search action. The House service (HCSearchHouseHook) answers every
    // House target and every action it owns; any other target is refused here with a reason.
    bool CanStart(PlayerBase player, ActionTarget target)
    {
        Object subject;
        if (target) subject = target.GetObject();
        HCRefusalReport.RefusalMessage(player, HCRefusal.SERVICE, subject, "Search unavailable: the search service is not ready on this server.");
        return false;
    }

    bool CanContinue(ActionData data)
    {
        return false;
    }

    void BeginSearch(ActionData data)
    {
        HCInteriorActionData action = HCInteriorActionData.Cast(data);
        if (!action)
        {
            HCRefusalReport.ActionRefusalMessage(data, HCRefusal.SESSION, "Search stopped; target or session changed.");
            return;
        }
        CanStart(data.m_Player, data.m_Target);
    }

    void CommitSearch(ActionData data)
    {
        if (!GetGame().IsServer()) { return; }
        if (data && data.m_Player) { HCRefusalReport.ActionRefusalMessage(data, HCRefusal.SESSION, "Search stopped; target or session changed."); }
    }

    void EndSearch(ActionData data)
    {
    }

    override void OnStop()
    {
        // Cancel 100 ms updates before deleting owned props. Installed native 1.30.164289:
        // 3_Game/Global/Game.c:1550 GetCallQueue; 2_GameLib/tools.c:65 ScriptCallQueue.Remove(func).
        // Remove matches every queued call of a target, so only the HC-owned
        // target is removed: vanilla tents, fireplaces and base building queue
        // UpdatePathgraphRegionByObject themselves and must keep their updates.
        if (GetGame())
        {
            GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).Remove(HCInteriorTemplatePlacement.HCTimedPathgraph);
        }
        HCInteriorMeasuredCatalog.MeasuredClear();
        // Owned nonpersistent decorations only. Never remove generated/player items.
        foreach (Object object : m_Objects)
        {
            if (object) GetGame().ObjectDelete(object);
        }
        m_Objects.Clear();
        if (s_Instance == this) s_Instance = null;
    }
}

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        // The search binder stays registered first so its House service is up before the Interiors template tick reports readiness.
        Register(new HCSearchBinding);
        Register(new HCInteriorsModule);
    }
}

// Optional startup-only query preference; missing fields retain registry defaults.
// Native JsonFileLoader.c:69 LoadData; EnSystem.c:397 FileExist.
class HCInteriorQueryConfig
{
    bool UseSphereLookup = true;
    protected static ref HCInteriorQueryConfig s_Config;

    static HCInteriorQueryConfig HCGet()
    {
        if (s_Config) { return s_Config; }
        HCOperatorSettingsRegistry.HCInteriorQueryInit();
        s_Config = new HCInteriorQueryConfig;
        string path = "$profile:HollowCountry/interiors-query.json";
        if (!FileExist(path)) { return s_Config; }
        string text;
        string error;
        HCInteriorQueryConfig decoded;
        if (!HCGroupIO.Read(path, 1024, text) || !JsonFileLoader<HCInteriorQueryConfig>.LoadData(text, decoded, error) || !decoded)
        {
            Print("[HC Interiors] interiors-query.json unreadable; query defaults retained runtime=PENDING");
            return s_Config;
        }
        if (HCJsonFields.Has(text, "UseSphereLookup") && HCOperatorSettingsRegistry.HCValid("InteriorsQuery.UseSphereLookup", decoded.UseSphereLookup))
        {
            s_Config.UseSphereLookup = decoded.UseSphereLookup;
        }
        return s_Config;
    }
}
