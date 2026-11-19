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
    // Empty on the audited rows; a cross-slot weapon row carries its stable pair id.
    string PairId;
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
    // the compiled rows below; explicit receipt keys survive future host renames.
    // This catalogue still admits nothing itself; HCTapedPackMounts admits an exact
    // pair (receipt gate plus native slot check) and the attach site asks it.
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
        if (CrossLightClass(row) == "") { return ""; }
        // Durable receipt keys. A future class rename changes the selector only;
        // retain the literal key so existing opt-outs and checks keep their identity.
        if (row.HostClass == "AK101") { return "cross_AK101_TLRLight"; }
        if (row.HostClass == "AK101_Black") { return "cross_AK101_Black_TLRLight"; }
        if (row.HostClass == "AK101_Green") { return "cross_AK101_Green_TLRLight"; }
        if (row.HostClass == "AK74") { return "cross_AK74_TLRLight"; }
        if (row.HostClass == "AK74_Black") { return "cross_AK74_Black_TLRLight"; }
        if (row.HostClass == "AK74_Green") { return "cross_AK74_Green_TLRLight"; }
        if (row.HostClass == "AKM") { return "cross_AKM_TLRLight"; }
        if (row.HostClass == "AKM_Gold") { return "cross_AKM_Gold_TLRLight"; }
        if (row.HostClass == "ASVAL") { return "cross_ASVAL_TLRLight"; }
        if (row.HostClass == "Aug") { return "cross_Aug_TLRLight"; }
        if (row.HostClass == "Colt1911") { return "cross_Colt1911_UniversalLight"; }
        if (row.HostClass == "CZ75") { return "cross_CZ75_UniversalLight"; }
        if (row.HostClass == "Engraved1911") { return "cross_Engraved1911_UniversalLight"; }
        if (row.HostClass == "FNX45") { return "cross_FNX45_UniversalLight"; }
        if (row.HostClass == "FNX45_arrow") { return "cross_FNX45_arrow_UniversalLight"; }
        if (row.HostClass == "Glock19") { return "cross_Glock19_UniversalLight"; }
        if (row.HostClass == "Glock19_Tan") { return "cross_Glock19_Tan_UniversalLight"; }
        if (row.HostClass == "M4A1") { return "cross_M4A1_TLRLight"; }
        if (row.HostClass == "M4A1_Black") { return "cross_M4A1_Black_TLRLight"; }
        if (row.HostClass == "M4A1_Green") { return "cross_M4A1_Green_TLRLight"; }
        if (row.HostClass == "MP5K") { return "cross_MP5K_TLRLight"; }
        if (row.HostClass == "SCARH") { return "cross_SCARH_TLRLight"; }
        if (row.HostClass == "SCARH_Black") { return "cross_SCARH_Black_TLRLight"; }
        if (row.HostClass == "SCARL") { return "cross_SCARL_TLRLight"; }
        if (row.HostClass == "SCARL_Black") { return "cross_SCARL_Black_TLRLight"; }
        if (row.HostClass == "UMP45") { return "cross_UMP45_TLRLight"; }
        if (row.HostClass == "Scout") { return "cross_Scout_TLRLight"; }
        if (row.HostClass == "Scout_Chernarus") { return "cross_Scout_Chernarus_TLRLight"; }
        if (row.HostClass == "Scout_Livonia") { return "cross_Scout_Livonia_TLRLight"; }
        return "";
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

    // The cross-slot row for one catalogue row (same host, slot and rail
    // prerequisite, the other light class, the stable pair id), or null. A fresh
    // object each call: callers use it only after an exact match or at startup.
    static HCTapedLightHostRow CrossRowFor(HCTapedLightHostRow source)
    {
        string pairId = CrossPairId(source);
        if (pairId == "") { return null; }
        HCTapedLightHostRow derived = new HCTapedLightHostRow;
        derived.HostClass = source.HostClass;
        derived.LightClass = CrossLightClass(source);
        derived.SlotName = source.SlotName;
        derived.PrerequisiteSlot = source.PrerequisiteSlot;
        derived.PrerequisiteClass = source.PrerequisiteClass;
        derived.PairId = pairId;
        return derived;
    }

    // Row for one stable pair id, or null for an unknown id.
    static HCTapedLightHostRow CrossRow(string pairId)
    {
        if (pairId == "") { return null; }
        array<ref HCTapedLightHostRow> rows = Rows();
        foreach (HCTapedLightHostRow row : rows)
        {
            if (CrossPairId(row) == pairId) { return CrossRowFor(row); }
        }
        return null;
    }

    // Exact host class + cross light class lookup for the attach site: no
    // allocation until one catalogue row matches, no case folding or inference.
    static HCTapedLightHostRow CrossRowMatch(string hostType, string lightType)
    {
        array<ref HCTapedLightHostRow> rows = Rows();
        foreach (HCTapedLightHostRow row : rows)
        {
            if (row.HostClass == hostType && CrossLightClass(row) == lightType) { return CrossRowFor(row); }
        }
        return null;
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
