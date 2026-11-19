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

    // #58 cross-slot weapon pairs: the same host carrying the other light class
    // (TLRLight on the rail rifles, UniversalLight on the pistols). The rule reads
    // the compiled rows below, so there is no second hand-kept weapon list; each
    // derived pair is only a receipt id and is never admitted by this catalogue.
    static string CrossLightClass(HCTapedLightHostRow row)
    {
        if (!row) { return ""; }
        if (row.LightClass == "UniversalLight" && row.SlotName == "weaponFlashlight") { return "TLRLight"; }
        if (row.LightClass == "TLRLight" && row.SlotName == "pistolFlashlight") { return "UniversalLight"; }
        return "";
    }

    // "" when the row has no approved cross-slot light, else the stable pair id.
    static string CrossPairId(HCTapedLightHostRow row)
    {
        string crossLight = CrossLightClass(row);
        if (crossLight == "") { return ""; }
        return "cross_" + row.HostClass + "_" + crossLight;
    }

    // Every derived pair id, unique, in catalogue row order (startup only).
    static TStringArray CrossPairIds()
    {
        TStringArray ids = new TStringArray;
        array<ref HCTapedLightHostRow> rows = Rows();
        foreach (HCTapedLightHostRow row : rows)
        {
            string pairId = CrossPairId(row);
            if (pairId != "" && ids.Find(pairId) < 0) { ids.Insert(pairId); }
        }
        return ids;
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
        // #58 item 1: proxy-backed config extensions; patched attachment and client checks PENDING.
        // Client/server weapons_firearms.pbo:scout/scout.p3d, native light proxy at byte 8586/8457.
        // See config.cpp evidence and LOCAL_ACCEPTANCE_V1.md; these are not probe-qualified pairs.
        Add(rows, "Scout", "UniversalLight", "weaponFlashlight", "", "");
        Add(rows, "Scout_Chernarus", "UniversalLight", "weaponFlashlight", "", "");
        Add(rows, "Scout_Livonia", "UniversalLight", "weaponFlashlight", "", "");
        // HC-7 / #58: R12 stays PENDING, deliberately absent from these rows.
        // probe-006 R12 has weaponFlashlight and server attachment succeeds,
        // but its scanned proxy list contains only optic_acog. Resolution LOD
        // scanning is incomplete; neither proxy geometry nor client alignment
        // is accepted. See tests/fixtures/runtime/light-proxy-slot-table.json.
        // Slot ancestry/attachment alone cannot admit it or justify a patch.
        s_Rows = rows;
        return s_Rows;
    }
}
