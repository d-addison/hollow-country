// A server-only catalog. No unvisited catalog is included in any RPC DTO.
class HCGroupPlaces
{
    static HCGroupPlaceCatalog Load()
    {
        string path = "$profile:HollowCountry/Groups/places.json";
        HCGroupPlaceCatalog catalog;
        if (FileExist(path))
        {
            if (!HCGroupJson<HCGroupPlaceCatalog>.Load(path, 65536, catalog)) return null;
        }
        else
        {
            catalog = NativeNames();
        }
        if (!catalog || catalog.SchemaVersion != 1 || !catalog.Places || catalog.Places.Count() > 256) return null;
        array<string> ids = new array<string>();
        float worldSize = GetGame().GetWorld().GetWorldSize();
        foreach (HCGroupPlace place : catalog.Places)
        {
            if (!HCGroupRules.PlaceValid(place) || ids.Find(place.Id) >= 0) return null;
            if (place.Position[0] > worldSize || place.Position[2] > worldSize) return null;
            ids.Insert(place.Id);
        }
        return catalog;
    }

    static HCGroupPlaceCatalog NativeNames()
    {
        HCGroupPlaceCatalog catalog = new HCGroupPlaceCatalog;
        string root = "CfgWorlds " + GetGame().GetWorldName() + " Names";
        int count = GetGame().ConfigGetChildrenCount(root);
        if (count < 0) return null;
        if (count > 512)
        {
            Print("[HC Groups] native Names truncated: examining first 512 entries");
            count = 512;
        }
        for (int i = 0; i < count; i++)
        {
            string child;
            if (!GetGame().ConfigGetChildName(root, i, child)) return null;
            string entry = root + " " + child;
            string title;
            GetGame().ConfigGetText(entry + " name", title);
            array<float> coords = new array<float>();
            GetGame().ConfigGetFloatArray(entry + " position", coords);
            if (title == "" || coords.Count() != 2) continue;
            HCGroupPlace place = new HCGroupPlace;
            place.Id = child;
            place.Name = title;
            place.Position = Vector(coords.Get(0), 0, coords.Get(1));
            if (!HCGroupRules.PlaceValid(place)) continue;
            if (catalog.Places.Count() >= 256)
            {
                Print("[HC Groups] native Names truncated: catalog limit 256");
                break;
            }
            catalog.Places.Insert(place);
        }
        return catalog;
    }
}
