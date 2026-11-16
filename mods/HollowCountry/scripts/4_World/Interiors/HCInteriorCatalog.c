class HCInteriorProp
{
    string Type;
    vector Position;
    vector Orientation;
    bool Searchable;
    vector SearchPoint;

    void HCInteriorProp(string type, vector position, vector orientation, bool searchable, vector searchPoint)
    {
        Type = type;
        Position = position;
        Orientation = orientation;
        Searchable = searchable;
        SearchPoint = searchPoint;
    }
}

class HCInteriorLayout
{
    string Id;
    string History;
    ref array<ref HCInteriorProp> Props = new array<ref HCInteriorProp>;
}

class HCInteriorCatalog
{
    static const string BUILDING = "Land_House_1W01";
    static const int VERSION = 1;

    // Native config classes verified; relative coordinates are UNMEASURED TRIALS.
    // No claim of safe fit, cabinet selection or door clearance. Production gated.
    static HCInteriorLayout Get(int index)
    {
        HCInteriorLayout layout = new HCInteriorLayout;
        if (index == 0)
        {
            layout.Id = "family-pantry-v1";
            layout.History = "family";
            layout.Props.Insert(new HCInteriorProp("StaticObj_Furniture_case_a", "-1.6 0 1.2", "90 0 0", true, "0 0.9 -0.22"));
            layout.Props.Insert(new HCInteriorProp("StaticObj_Furniture_kitchen_chair_a", "-1.4 0 -0.8", "20 0 0", false, "0 0 0"));
        }
        else if (index == 1)
        {
            layout.Id = "family-storage-v1";
            layout.History = "family";
            layout.Props.Insert(new HCInteriorProp("StaticObj_Furniture_case_bedroom_b", "1.6 0 1.2", "270 0 0", true, "0 0.8 -0.22"));
            layout.Props.Insert(new HCInteriorProp("StaticObj_Furniture_PaperBox_01_small_closed", "1.4 0 -0.8", "0 0 0", false, "0 0 0"));
        }
        else if (index == 2)
        {
            layout.Id = "ransacked-storage-v1";
            layout.History = "ransacked";
            layout.Props.Insert(new HCInteriorProp("StaticObj_Furniture_case_a_open", "-1.6 0 1.2", "90 0 0", true, "0 0.9 -0.22"));
            layout.Props.Insert(new HCInteriorProp("StaticObj_Furniture_PaperBox_01_small_ransacked", "-1.4 0 -0.8", "140 0 0", false, "0 0 0"));
        }
        else return null;
        return layout;
    }

    static bool SearchType(string type)
    {
        return type == "StaticObj_Furniture_case_a" || type == "StaticObj_Furniture_case_bedroom_b" || type == "StaticObj_Furniture_case_a_open";
    }

    static bool ItemAllowed(string type)
    {
        return type == "" || type == "Rag" || type == "Battery9V";
    }
}

class HCInteriorCandidate
{
    int Slot = -1; // Stable explicit discriminator, never array index.
    string Type;
    vector Position;
    vector Orientation;

    string Key()
    {
        return Type + "_" + HCInteriorRules.TransformKey(Position, Orientation);
    }

    string Id(int epoch)
    {
        return "chernarusplus_130164289_s1_e" + epoch.ToString() + "_" + Key() + "_d" + Slot.ToString();
    }
}

class HCInteriorConfig
{
    int SchemaVersion;
    string World;
    string Build;
    int Epoch;
    int Seed;
    bool InitializeNewEpoch = false;
    bool DiagnosticPlacementTrial = false;
    bool DiagnosticSearchTrial = false;
    ref array<ref HCInteriorCandidate> Candidates = new array<ref HCInteriorCandidate>;
}

class HCInteriorAssignment
{
    int Slot;
    string InstanceId;
    string LayoutId;
    string History;
    string Item;
}

class HCInteriorManifest
{
    int SchemaVersion;
    int CatalogVersion;
    string World;
    string Build;
    int Epoch;
    int Seed;
    ref array<ref HCInteriorAssignment> Assignments = new array<ref HCInteriorAssignment>;
}

class HCInteriorClaim
{
    int SchemaVersion;
    string SiteId;
    string Item;
    string PlayerId;
    int Phase;
}

class HCInteriorSite
{
    string Id;
    int Slot;
    Object Target;
    vector Point;
    string Item;
    int Phase;
    ActionData Owner;
    float StartedAt;
    float Deadline;
}
