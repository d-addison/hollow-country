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

// Additive server-owned group places, serialized by the existing group store.
// Old journals keep the empty initializer; dissolving a group removes its pins.
modded class HCGroupRecord
{
    ref array<string> HCTrailPlaceIds = new array<string>();
}

// The same World-layer DTO extension compiles on server and client. Expiry is
// for lead display between FULL frames; it never holds an actor's position.
modded class HCGroupPlace
{
    int HCPinExpiresUtc = 0;
}

modded class HCGroupRules
{
    override static bool StateValid(HCGroupState state, HCGroupSettings c, string world)
    {
        if (!super.StateValid(state, c, world)) { return false; }
        foreach (HCGroupRecord pinGroup : state.Groups)
        {
            if (!pinGroup.HCTrailPlaceIds || pinGroup.HCTrailPlaceIds.Count() > 48) { return false; }
            array<string> pinIds = new array<string>();
            foreach (string pinId : pinGroup.HCTrailPlaceIds)
            {
                if (pinId.IndexOf("hc-found:") != 0 || !HCGroupRules.TextValid(pinId, 128, false) || pinIds.Find(pinId) >= 0) { return false; }
                pinIds.Insert(pinId);
            }
        }
        return true;
    }

    override static array<ref HCGroupPlace> KnownPlaces(HCGroupState state, HCGroupSettings c, string uid, HCGroupPlaceCatalog catalog)
    {
        array<ref HCGroupPlace> visited = super.KnownPlaces(state, c, uid, catalog);
        HCGroupPins pins = HCGroupPins.Get();
        HCGroupRecord pinGroup = HCGroupRules.FindGroup(state, uid);
        if (!pins || !pinGroup || !c.DiscoveryLayer) { return visited; }
        array<ref HCGroupPlace> combined = new array<ref HCGroupPlace>();
        // Received leads first, then up to 48 discovered shelters. All layers
        // together retain the existing validated MaxDiscoveries wire bound.
        pins.Collect(pinGroup, c.MaxDiscoveries, combined);
        foreach (HCGroupPlace oldPlace : visited)
        {
            if (combined.Count() >= c.MaxDiscoveries) { break; }
            combined.Insert(oldPlace);
        }
        return combined;
    }
}
