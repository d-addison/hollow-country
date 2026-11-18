// LC-T412/413. Installed scripts-1.30.164289 native/script evidence:
// 3_Game/Global/Game.c:930 GetObjectsAtPosition3D, :1176 SurfaceY;
// 3_Game/Entities/Object.c:215/287/467/511/1219 deletion/position/type/kind/ruin;
// 3_Game/Entities/Entity.c:12 GetAnimationPhase; EntityAI.c:885 parent,
// :882 root player, :1897 attachment, :3374 persistent ID, :3409 GetCompEM;
// inventory :1884; 3_Game/Systems/Inventory/Inventory.c:138 GetCargo.
// 4_World/Entities/ItemBase/TentBase.c:22/461 PITCHED/GetState;
// ItemBase/BaseBuildingBase.c:882 GetConstruction; Classes/ConstructionBase.c:1173 IsPartConstructed; ItemBase/BaseBuildingBase/Fence.c:405/411
// wall_base_down/up; ItemBase/BaseBuildingBase/Totem.c:285 flag_mast;
// ItemBase/TrapBase.c:155 IsActive; Core/Inherited/InventoryItem.c:18/22
// GetTunedFrequency/IsReceiving; 3_Game/tools/Component/ComponentEnergyManager.c:925
// IsWorking. Hard cap 128 results; oversize areas fail closed without tier gain.
// 1_Core/proto/EnScript.c:94/380/394/407 cast/count/find/insert;
// 1_Core/proto/EnConvert.c:30 int.ToString. Stored member refs cap 64.
class HCCampScan
{
    bool Shelter;
    bool Storage;
    bool RaisedFlag;
    bool Garden;
    bool Kitchen;
    bool HasRadio;
    bool Camo;
    bool CallingMegaphone;
    bool Tripwire;
    bool HighFire;
    int Traps;
    int Walls;
    int Lights;
    int Chemlights;
    string Flag;
    ref array<ItemBase> Crates = new array<ItemBase>();
    ref array<string> Items = new array<string>();

    static string RefOf(EntityAI item)
    {
        if (!item) { return ""; }
        int first;
        int second;
        int third;
        int fourth;
        item.GetPersistentID(first, second, third, fourth);
        if (first == 0 && second == 0 && third == 0 && fourth == 0) { return ""; }
        return first.ToString() + ":" + second.ToString() + ":" + third.ToString() + ":" + fourth.ToString();
    }

    static bool Powered(ItemBase item)
    {
        return item && item.GetCompEM() && item.GetCompEM().IsWorking();
    }

    static bool StorageItem(ItemBase item)
    {
        return item && (item.IsKindOf("WoodenCrate") || item.IsKindOf("SeaChest") || item.IsKindOf("Barrel_ColorBase"));
    }

    static HCCampScan Read(vector position, bool burning)
    {
        array<Object> objects = new array<Object>();
        array<CargoBase> cargos = new array<CargoBase>();
        GetGame().GetObjectsAtPosition3D(position, 12, objects, cargos);
        if (objects.Count() > 128 || cargos.Count() > 128) { return null; }
        HCCampScan scan = new HCCampScan;
        float ground = GetGame().SurfaceY(position[0], position[2]);
        scan.HighFire = burning && ground > GetGame().SurfaceY(position[0] + 20, position[2]) + 2 && ground > GetGame().SurfaceY(position[0] - 20, position[2]) + 2;
        foreach (Object nearby : objects)
        {
            ItemBase item = ItemBase.Cast(nearby);
            if (!item || item.IsPendingDeletion() || item.IsRuined()) { continue; }
            if (item.IsKindOf("Megaphone") && Powered(item)) { scan.CallingMegaphone = true; }
            if (item.GetHierarchyRootPlayer()) { continue; }
            string itemRef = RefOf(item);
            if (itemRef != "" && scan.Items.Count() < HCWorldLimits.CAMP_MEMBERS && scan.Items.Find(itemRef) < 0) { scan.Items.Insert(itemRef); }
            TentBase tent = TentBase.Cast(item);
            if (tent && tent.GetState() == TentBase.PITCHED)
            {
                scan.Shelter = true;
                if (tent.FindAttachmentBySlotName("CamoNet")) { scan.Camo = true; }
            }
            if (StorageItem(item) && !item.GetHierarchyParent()) { scan.Storage = true; }
            if (item.IsKindOf("WoodenCrate") && !item.GetHierarchyParent() && scan.Crates.Count() < 8) { scan.Crates.Insert(item); }
            if (item.IsKindOf("CamoNet") && !item.GetHierarchyParent()) { scan.Camo = true; }
            if (item.IsKindOf("GardenPlot") || item.IsKindOf("Greenhouse")) { scan.Garden = true; }
            if (item.IsKindOf("Pot") || item.IsKindOf("Cauldron") || item.IsKindOf("FryingPan")) { scan.Kitchen = true; }
            TerritoryFlag pole = TerritoryFlag.Cast(item);
            if (pole && pole.FindAttachmentBySlotName("Material_FPole_Flag"))
            {
                float mast = pole.GetAnimationPhase("flag_mast");
                if (mast < 0.1) { scan.RaisedFlag = true; scan.Flag = "welcome"; }
                else if (mast < 0.9) { scan.Flag = "caution"; }
                else { scan.Flag = "closed"; }
            }
            Fence fence = Fence.Cast(item);
            if (fence && fence.GetConstruction())
            {
                if (fence.GetConstruction().IsPartConstructed("wall_base_down")) { scan.Walls++; }
                if (fence.GetConstruction().IsPartConstructed("wall_base_up")) { scan.Walls++; }
            }
            TrapBase trap = TrapBase.Cast(item);
            if (trap && trap.IsActive())
            {
                scan.Traps++;
                if (trap.IsKindOf("TripwireTrap")) { scan.Tripwire = true; }
            }
            if (Powered(item))
            {
                if (item.IsKindOf("Chemlight_ColorBase")) { scan.Chemlights++; scan.Lights++; }
                else if (item.IsKindOf("PortableGasLamp") || item.IsKindOf("Spotlight") || item.IsKindOf("Roadflare")) { scan.Lights++; }
            }
            TransmitterBase radio = TransmitterBase.Cast(item);
            // Authored Travellers channel: first native frequency (87.8 MHz).
            if (radio && Powered(radio) && radio.IsReceiving() && radio.GetTunedFrequency() > 87.79 && radio.GetTunedFrequency() < 87.81) { scan.HasRadio = true; }
        }
        return scan;
    }

    bool Hidden(bool burning)
    {
        return !burning && Lights == 0 && Camo && !CallingMegaphone && !HasRadio;
    }

    string Signal(bool burning)
    {
        if (Hidden(burning)) { return "lights-out"; }
        if (Tripwire) { return "tripwire"; }
        if (CallingMegaphone) { return "megaphone"; }
        if (Chemlights >= 3) { return "chemlight-trail"; }
        if (HighFire) { return "signal-fire"; }
        if (Flag != "") { return "flag-" + Flag; }
        return "quiet";
    }
}
