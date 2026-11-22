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

    // Native config classes verified; relative coordinates are UNMEASURED TRIALS used only by
    // the DIAG storage probe and the offline measured-record tool. No claim of safe fit.
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
        return type == "StaticObj_Furniture_case_a" || type == "StaticObj_Furniture_case_a_open" || type == "StaticObj_Furniture_case_bedroom_b" || type == "StaticObj_Furniture_almara" || type == "StaticObj_Furniture_almara_open" || type == "StaticObj_Furniture_library_a" || type == "StaticObj_Furniture_table_drawer" || type == "StaticObj_Furniture_kitchen_unit_a_DZ" || type == "StaticObj_Furniture_metalcrate" || type == "StaticObj_Misc_WoodenCrate";
    }

    static bool ItemAllowed(string type)
    {
        return type == "" || type == "Rag" || type == "Battery9V";
    }
}

class HCInteriorCandidate
{
    int SlotId = -1; // Stable explicit discriminator, never array index.
    string Type;
    vector Position;
    vector Orientation;

    string Key()
    {
        return Type + "_" + HCInteriorRules.TransformKey(Position, Orientation);
    }

    string Id(int epoch)
    {
        return "chernarusplus_130164289_s1_e" + epoch.ToString() + "_" + Key() + "_d" + SlotId.ToString();
    }
}

class HCInteriorConfig
{
    int SchemaVersion;
    string MapName;
    string Build;
    int Epoch;
    int Seed;
    bool InitializeNewEpoch = false;
    // Explicit one-way journal migration only. Never rerolls layouts or allocations.
    bool MigrateLegacyJournal = false;
}

class HCInteriorAssignment
{
    int SlotId;
    string InstanceId;
    string LayoutId;
    string History;
    // Externally qualified record digest participates in exact manifest
    // comparison. Changed measured records require explicit epoch handling.
    string MeasuredRecordSha256;
    string Item;
}

class HCInteriorManifest
{
    int SchemaVersion;
    int CatalogVersion;
    string MapName;
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
    // Forensic output reference only; zero IDs may precede native persistence.
    // Never used to recreate, relocate, delete or take ownership of player loot.
    int OutputA;
    int OutputB;
    int OutputC;
    int OutputD;
}

class HCInteriorSite
{
    string Id;
    int SlotId;
    Object Target;
    vector Point;
    string Item;
    int Phase;
    ActionData Owner;
    float StartedAt;
    float Deadline;
}
