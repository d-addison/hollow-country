// Entry-local roster port: native scripts-1.30.164289 3_Game/Global/Game.c:945;
// resolver identity/life: Entities/Man.c:21, gameplay.c:368, Entities/Object.c:517.
// A server-only catalog. No unvisited catalog is included in any RPC DTO.
// Native snapshot scripts-1.30.164289: 3_Game/Global/Game.c:449,578,594,611
// (config reads), :931,934 (world); 3_Game/Global/World.c:82 (world size);
// 1_Core/proto/EnScript.c:380,394,407 (arrays), EnString.c:199 (Length).
// Static override syntax: 3_Game/Particles/ParticleManager/ParticleSource.c:240.
// EnString.c:240 (IndexOf) for namespaced durable pin ids.
// 1_Core/proto/EnSystem.c:397 (FileExist), EnMath3D.c:18 (Vector),
// EnDebug.c:96 (Print). Existing HCGroupJson uses
// 3_Game/tools/JsonFileLoader.c:69,85 (LoadData/MakeData).
// Persistence and snapshot extensions below use the existing group journal
// and FULL Places RPC. No new store, RPC, or client discovery authority.
class HCGroupPlaces
{
    static HCGroupPlaceCatalog Load()
    {
        string path = "$profile:HollowCountry/Groups/places.json";
        ref HCGroupPlaceCatalog catalog = new HCGroupPlaceCatalog;
        if (FileExist(path))
        {
            string text;
            string error;
            // Native scripts-1.30.164289: 3_Game/gameplay.c:100; same bounded
            // HCGroupIO read and validation as the previous HCGroupJson.Load path.
            JsonSerializer js = new JsonSerializer;
            if (!HCGroupIO.Read(path, 65536, text) || !js.ReadFromString(catalog, text, error)) return null;
        }
        else
        {
            catalog = NativeNames();
        }
        if (!catalog || catalog.SchemaVersion != 1 || !catalog.Places || catalog.Places.Count() > 256) return null;
        map<string, bool> ids = new map<string, bool>();
        float worldSize = GetGame().GetWorld().GetWorldSize();
        array<ref HCGroupPlace> hcRows1 = catalog.Places;
        foreach (HCGroupPlace place : hcRows1)
        {
            if (!HCGroupRules.PlaceValid(place) || ids.Contains(place.Id)) return null;
            if (place.Position[0] > worldSize || place.Position[2] > worldSize) return null;
            ids.Set(place.Id, true);
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
            string title = HCConfigHelper.GetText(entry + " name", "");
            array<float> coords = new array<float>();
            HCConfigHelper.GetFloatList(entry + " position", coords);
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

// HCGroupRecord.HCTrailPlaceIds and HCGroupPlace.HCPinExpiresUtc live in
// 3_Game/Groups/HCGroupData.c: Enforce cannot mod a 3_Game class from 4_World.
modded class HCGroupRules
{
    override static bool StateValid(HCGroupState state, HCGroupSettings c, string world)
    {
        if (!super.StateValid(state, c, world)) { return false; }
        array<ref HCGroupRecord> hcRows2 = state.Groups;
        foreach (HCGroupRecord pinGroup : hcRows2)
        {
            if (!pinGroup.HCTrailPlaceIds || pinGroup.HCTrailPlaceIds.Count() > 48) { return false; }
            map<string, bool> pinIds = new map<string, bool>();
            array<string> hcRows3 = pinGroup.HCTrailPlaceIds;
            foreach (string pinId : hcRows3)
            {
                if (pinId.IndexOf("hc-found:") != 0 || !HCGroupRules.TextValid(pinId, 128, false) || pinIds.Contains(pinId)) { return false; }
                pinIds.Set(pinId, true);
            }
        }
        return true;
    }

    override static array<ref HCGroupPlace> KnownPlaces(HCGroupState state, HCGroupSettings c, string uid, HCGroupPlaceCatalog catalog, array<Man> hcRoster = null)
    {
        if (!hcRoster)
        {
            hcRoster = new array<Man>;
            GetGame().GetPlayers(hcRoster);
        }
        array<ref HCGroupPlace> visited = super.KnownPlaces(state, c, uid, catalog, hcRoster);
        HCGroupPins pins = HCGroupPins.Get();
        HCGroupRecord pinGroup = HCGroupRules.FindGroup(state, uid);
        if (!pins || !pinGroup || !c.DiscoveryLayer) { return visited; }
        array<ref HCGroupPlace> combined = new array<ref HCGroupPlace>();
        // Received leads first, then up to 48 discovered shelters. All layers
        // together retain the existing validated MaxDiscoveries wire bound.
        pins.Collect(pinGroup, c.MaxDiscoveries, combined, hcRoster);
        foreach (HCGroupPlace oldPlace : visited)
        {
            if (combined.Count() >= c.MaxDiscoveries) { break; }
            combined.Insert(oldPlace);
        }
        return combined;
    }
}
