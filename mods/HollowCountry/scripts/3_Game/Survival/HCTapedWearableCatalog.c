// HC-23 / #58 part 2: first exact native helmet pair, never runtime acceptance.
// Spec -> plan -> task: tests/unit/test_hc_taped_lights.py and the review manifest
// mission/hollow-country/lights/helmet-mounts.json. JSON is review data, not an
// operator-controlled qualification source. All other pairs refuse explicitly.
// Native scripts-1.30.164289: 1_Core/proto/EnScript.c:380,399,407
// array Count/Get (indexing)/Insert. HC-7 owns the shared row type/Add helper.
class HCTapedWearableCatalog
{
    protected static ref array<ref HCTapedLightHostRow> s_Rows;
    static const string MANIFEST = "24abaeed06c1b28ee12a64be5816f0cf5ffd8f2c9716ac66dc035380c5a13038";

    static bool Supported(HCTapedLightHostRow row)
    {
        if (!row) { return false; }
        if (row.PrerequisiteSlot != "" || row.PrerequisiteClass != "") { return false; }
        return row.HostClass == "Mich2001Helmet" && row.LightClass == "UniversalLight" && row.SlotName == "helmetFlashlight";
    }

    static bool Matches(HCTapedLightHostRow row, string host, string light, string slot)
    {
        if (!Supported(row)) { return false; }
        return row.HostClass == host && row.LightClass == light && row.SlotName == slot;
    }

    static bool ManifestAllowed(array<ref HCTapedLightHostRow> rows)
    {
        if (!rows || rows.Count() != 1) { return false; }
        return Supported(rows[0]);
    }

    static array<ref HCTapedLightHostRow> Rows()
    {
        if (s_Rows) { return s_Rows; }
        array<ref HCTapedLightHostRow> rows = new array<ref HCTapedLightHostRow>;
        HCTapedLightCatalog.Add(rows, "Mich2001Helmet", "UniversalLight", "helmetFlashlight", "", "");
        s_Rows = rows;
        return s_Rows;
    }

    static TStringArray CompatibilityQueue()
    {
        TStringArray rows = new TStringArray;
        rows.Insert("BallisticHelmet_Green");
        rows.Insert("ConstructionHelmet_Orange");
        rows.Insert("GorkaHelmet");
        return rows;
    }

    static string Refusal(string host, string light, string slot)
    {
        if (host != "Mich2001Helmet" || light != "UniversalLight" || slot != "helmetFlashlight") { return "unsupported_helmet_pair"; }
        return "helmet_mount_two_client_pending";
    }

    static bool Qualified()
    {
        // No file, client claim, transform or HC-7 acceptance opt-in can set this.
        return false;
    }
}

// HC-52 spec -> plan -> task: one exact backpack candidate and one separately
// configured cross-slot candidate. Neither is a qualified/native-safe pair.
// Evidence and the geometry queue live in lights/backpack-mounts.json.
// No descendants, 80-pack/228-helmet claims, or operator-provided transforms.
class HCTapedPackCatalog
{
    static bool IsPackHost(string host)
    {
        return host == "TortillaBag";
    }

    static bool KnownPair(string pairId)
    {
        return pairId == "tortilla_universal_mount" || pairId == "tortilla_universal_cross";
    }

    // Every exact pair identity, in boot-line order (startup only).
    static TStringArray PairIds()
    {
        TStringArray ids = new TStringArray;
        ids.Insert("tortilla_universal_mount");
        ids.Insert("tortilla_universal_cross");
        return ids;
    }

    static string SlotName(string pairId)
    {
        if (pairId == "tortilla_universal_mount") { return "helmetFlashlight"; }
        if (pairId == "tortilla_universal_cross") { return "Chemlight"; }
        return "";
    }

    static bool Matches(string pairId, string host, string light, string slotName, bool crossSlot)
    {
        if (host != "TortillaBag" || light != "UniversalLight") { return false; }
        if (pairId == "tortilla_universal_mount") { return slotName == "helmetFlashlight" && !crossSlot; }
        if (pairId == "tortilla_universal_cross") { return slotName == "Chemlight" && crossSlot; }
        return false;
    }

    static bool Qualified(string pairId)
    {
        // Neither native model/proxy geometry nor two-client receipts exist.
        // A settings flag, live slot array or HC-7 opt-in cannot qualify these.
        // HCTapedPackMounts.PairQualified additionally needs the operator
        // setting and a checked per-pair receipt; this gate alone never admits.
        return false;
    }

    static string Refusal(string pairId)
    {
        if (pairId == "tortilla_universal_mount") { return "pack_mount_geometry_pending"; }
        if (pairId == "tortilla_universal_cross") { return "cross_slot_geometry_pending"; }
        return "unsupported_pack_pair";
    }
}
