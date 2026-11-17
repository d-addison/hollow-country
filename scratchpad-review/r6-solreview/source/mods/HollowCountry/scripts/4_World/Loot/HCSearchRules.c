class HCSearchRules
{
    static bool TextValid(string value, int limit)
    {
        if (value.Length() < 1 || value.Length() > limit || limit > 768) return false;
        string alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-:+/=";
        int index;
        while (index < value.Length())
        {
            if (alphabet.IndexOf(value.Get(index)) < 0) return false;
            index++;
        }
        return true;
    }

    static bool PinValid(string value)
    {
        if (value.Length() != 64) return false;
        string alphabet = "0123456789abcdef";
        int index;
        while (index < 64)
        {
            if (alphabet.IndexOf(value.Get(index)) < 0) return false;
            index++;
        }
        return true;
    }

    static bool ManifestValid(HCSearchManifest manifest)
    {
        if (!manifest || manifest.Version != 1 || !manifest.Entries) return false;
        if (manifest.Epoch < 1 || manifest.Epoch > 1000000) return false;
        if (manifest.Entries.Count() < 1 || manifest.Entries.Count() > 4096) return false;
        if (!HCSearchRules.TextValid(manifest.WorldName, 128) || !HCSearchRules.TextValid(manifest.Build, 64)) return false;
        if (!HCSearchRules.TextValid(manifest.SourceId, 128) || !HCSearchRules.PinValid(manifest.SourcePin)) return false;
        map<string, bool> sites = new map<string, bool>;
        map<string, bool> supplies = new map<string, bool>;
        foreach (HCSearchEntry entry : manifest.Entries)
        {
            if (!entry || !HCSearchRules.TextValid(entry.SiteId, 768)) return false;
            if (sites.Contains(entry.SiteId)) return false;
            sites.Set(entry.SiteId, true);
            if (entry.SupplyId == "" && entry.ItemClass == "") continue;
            if (!HCSearchRules.TextValid(entry.SupplyId, 64) || !HCSearchRules.TextValid(entry.ItemClass, 128)) return false;
            if (supplies.Contains(entry.SupplyId)) return false;
            supplies.Set(entry.SupplyId, true);
        }
        return true;
    }
}
