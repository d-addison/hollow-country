// #56 W1.3: exact installed vanilla pair data, NOT production acceptance.
// Derived read-only by tools.audit.taped_light_report.build_report from probe-006
// and probe-004 classification. See tests/unit/test_taped_light_v1_evidence.py.
// No subclass inference or case normalization is allowed at the admission edge.
class HCTapedLightHostRow
{
    string HostClass;
    string LightClass;
    string SlotName;
    string PrerequisiteSlot;
    string PrerequisiteClass;
}

class HCTapedLightCatalog
{
    protected static ref array<ref HCTapedLightHostRow> s_Rows;
    static const string MANIFEST = "9d54882a47c096a27e8ec5ad0022a6f11673d7e4a8d43769e4d4524e90a8f6dd";
    static const string OBSERVATIONS = "609722ff6e1463241257c7565b9d3842cf1f47505a7f757c1d79ca44c479fe88";

    static bool Matches(HCTapedLightHostRow row, string host, string light, string slot)
    {
        if (!row) { return false; }
        return row.HostClass == host && row.LightClass == light && row.SlotName == slot;
    }

    static void Add(array<ref HCTapedLightHostRow> rows, string host, string light, string slot, string prerequisiteSlot, string prerequisiteClass)
    {
        HCTapedLightHostRow row = new HCTapedLightHostRow;
        row.HostClass = host;
        row.LightClass = light;
        row.SlotName = slot;
        row.PrerequisiteSlot = prerequisiteSlot;
        row.PrerequisiteClass = prerequisiteClass;
        rows.Insert(row);
    }

    static array<ref HCTapedLightHostRow> Rows()
    {
        if (s_Rows) { return s_Rows; }
        array<ref HCTapedLightHostRow> rows = new array<ref HCTapedLightHostRow>;
        Add(rows, "AK101", "UniversalLight", "weaponFlashlight", "weaponHandguardAK", "AK_RailHndgrd");
        Add(rows, "AK101_Black", "UniversalLight", "weaponFlashlight", "weaponHandguardAK", "AK_RailHndgrd");
        Add(rows, "AK101_Green", "UniversalLight", "weaponFlashlight", "weaponHandguardAK", "AK_RailHndgrd");
        Add(rows, "AK74", "UniversalLight", "weaponFlashlight", "weaponHandguardAK", "AK_RailHndgrd");
        Add(rows, "AK74_Black", "UniversalLight", "weaponFlashlight", "weaponHandguardAK", "AK_RailHndgrd");
        Add(rows, "AK74_Green", "UniversalLight", "weaponFlashlight", "weaponHandguardAK", "AK_RailHndgrd");
        Add(rows, "AKM", "UniversalLight", "weaponFlashlight", "weaponHandguardAK", "AK_RailHndgrd");
        Add(rows, "AKM_Gold", "UniversalLight", "weaponFlashlight", "weaponHandguardAK", "AK_RailHndgrd");
        Add(rows, "ASVAL", "UniversalLight", "weaponFlashlight", "", "");
        Add(rows, "Aug", "UniversalLight", "weaponFlashlight", "", "");
        Add(rows, "Colt1911", "TLRLight", "pistolFlashlight", "", "");
        Add(rows, "CZ75", "TLRLight", "pistolFlashlight", "", "");
        Add(rows, "Engraved1911", "TLRLight", "pistolFlashlight", "", "");
        Add(rows, "FNX45", "TLRLight", "pistolFlashlight", "", "");
        Add(rows, "FNX45_arrow", "TLRLight", "pistolFlashlight", "", "");
        Add(rows, "Glock19", "TLRLight", "pistolFlashlight", "", "");
        Add(rows, "Glock19_Tan", "TLRLight", "pistolFlashlight", "", "");
        Add(rows, "M4A1", "UniversalLight", "weaponFlashlight", "weaponHandguardM4", "M4_RISHndgrd");
        Add(rows, "M4A1_Black", "UniversalLight", "weaponFlashlight", "weaponHandguardM4", "M4_RISHndgrd");
        Add(rows, "M4A1_Green", "UniversalLight", "weaponFlashlight", "weaponHandguardM4", "M4_RISHndgrd");
        Add(rows, "MP5K", "UniversalLight", "weaponFlashlight", "weaponHandguardMP5", "MP5_RailHndgrd");
        Add(rows, "SCARH", "UniversalLight", "weaponFlashlight", "", "");
        Add(rows, "SCARH_Black", "UniversalLight", "weaponFlashlight", "", "");
        Add(rows, "SCARL", "UniversalLight", "weaponFlashlight", "", "");
        Add(rows, "SCARL_Black", "UniversalLight", "weaponFlashlight", "", "");
        Add(rows, "UMP45", "UniversalLight", "weaponFlashlight", "", "");
        s_Rows = rows;
        return s_Rows;
    }
}
