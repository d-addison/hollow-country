// Installed scripts-1.30.164289 evidence:
// 3_Game/Entities/EntityAI.c:1472 CanReceiveAttachment(EntityAI,int),
// :1484 CanLoadAttachment(EntityAI) (storage restore has its own callback),
// :1496 CanPutAsAttachment(EntityAI), :1540 CanDetachAttachment(EntityAI),
// :1199 EEItemDetached(EntityAI,string), :2732 IsStoreLoad().
// 3_Game/Entities/Object.c:511 IsKindOf(string) (inherited added slots).
// 4_World/Entities/ItemBase.c:3768 overrides IsStoreLoad; :4154/:4178
// native item checks. Switchable_Base/TLRLight.c:18 and UniversalLight.c:25
// call super.CanPutAsAttachment: preserve their holster/rail constraints.
class HCTapedLightJournalImage
{
    int Sequence;
    ref HCTapedLightState State;
}

// One synchronous server action owns one exact object/slot permit. It is never
// replicated and cannot be created by native drag, a client or a config flag.
class HCTapedLightPermit
{
    protected static EntityAI s_Host;
    protected static EntityAI s_Light;
    protected static int s_Slot = -1;

    static bool Begin(EntityAI host, EntityAI light, HCTapedLightBinding binding)
    {
        if (!GetGame() || !GetGame().IsServer() || s_Host || !host || !light || !binding) { return false; }
        if (!HCTapedLightAdmission.Admitted() || !HCTapedLightService.PairAllowed(binding)) { return false; }
        s_Host = host;
        s_Light = light;
        s_Slot = InventorySlots.GetSlotIdFromString(binding.SlotName);
        return true;
    }
    static void End()
    {
        s_Host = null;
        s_Light = null;
        s_Slot = -1;
    }
    static bool Owns(EntityAI host, EntityAI light, int slotId)
    {
        if (!GetGame() || !GetGame().IsServer()) { return false; }
        return s_Host == host && s_Light == light && s_Slot == slotId;
    }
    static bool Restoring(EntityAI host, EntityAI light)
    {
        return GetGame() && GetGame().IsServer() && host && light && (host.IsStoreLoad() || light.IsStoreLoad());
    }
    // Protect the added slot relations even for an unknown host/pair. A
    // catalog/admission lookup here would accidentally open opted-out rows.
    static bool Added(EntityAI host, EntityAI light, int slotId)
    {
        if (!host || !light) { return false; }
        if (light.IsKindOf("TLRLight")) { return slotId == InventorySlots.GetSlotIdFromString("weaponFlashlight"); }
        if (!light.IsKindOf("UniversalLight")) { return false; }
        if (slotId == InventorySlots.GetSlotIdFromString("pistolFlashlight") || slotId == InventorySlots.GetSlotIdFromString("Chemlight")) { return true; }
        return host.IsKindOf("TortillaBag") && slotId == InventorySlots.GetSlotIdFromString("helmetFlashlight");
    }
    static bool Receive(EntityAI host, EntityAI light, int slotId)
    {
        if (!Added(host, light, slotId) || Restoring(host, light)) { return true; }
        return Owns(host, light, slotId);
    }
    // CanPutAsAttachment supplies no destination slot. Keep any native-slot
    // candidate available; CanReceiveAttachment enforces the actual slot.
    static bool Put(EntityAI host, EntityAI light)
    {
        if (!host || !light) { return true; }
        bool pistolLight = light.IsKindOf("TLRLight");
        if (!pistolLight && !light.IsKindOf("UniversalLight")) { return true; }
        if (Restoring(host, light)) { return true; }
        if (s_Host == host && s_Light == light && Owns(host, light, s_Slot)) { return true; }
        TStringArray slots = new TStringArray;
        // Existing qualification adapter uses ConfigGetTextArray for these
        // same arrays; native 3_Game/Global/Game.c:558 ConfigGetTextArray.
        string root = "CfgVehicles";
        if (Weapon_Base.Cast(host)) { root = "CfgWeapons"; }
        GetGame().ConfigGetTextArray(root + " " + host.GetType() + " attachments", slots);
        if (pistolLight) { return slots.Find("pistolFlashlight") >= 0; }
        if (slots.Find("weaponFlashlight") >= 0) { return true; }
        return !host.IsKindOf("TortillaBag") && slots.Find("helmetFlashlight") >= 0;
    }
}

// EntityAI is declared in 3_Game; a modded class must live in its own script
// module, so the 4_World hooks go on ItemBase (4_World/Entities/ItemBase.c:23,
// overrides CanReceiveAttachment at :4178) and Weapon_Base
// (4_World/Entities/Firearms/Weapon_Base.c:38, EEItemDetached at :1115). Every
// taped-light host is one of the two; the gate stays identical on both.
modded class ItemBase
{
    override bool CanPutAsAttachment(EntityAI parent)
    {
        return super.CanPutAsAttachment(parent) && HCTapedLightPermit.Put(parent, this);
    }
    override bool CanDetachAttachment(EntityAI parent)
    {
        // Native detach remains available, including operator opt-out. The
        // physical EEItemDetached callback retires HC custody without a refund.
        return super.CanDetachAttachment(parent);
    }
    override bool CanReceiveAttachment(EntityAI attachment, int slotId)
    {
        return super.CanReceiveAttachment(attachment, slotId) && HCTapedLightPermit.Receive(this, attachment, slotId);
    }
    override void EEItemDetached(EntityAI item, string slot_name)
    {
        super.EEItemDetached(item, slot_name);
        if (!HCTapedLightPermit.Restoring(this, item)) { HCTapedLightRuntime.Detached(this, item, slot_name); }
    }
    // CanLoadAttachment intentionally inherits the native storage callback.
}

modded class Weapon_Base
{
    override bool CanReceiveAttachment(EntityAI attachment, int slotId)
    {
        return super.CanReceiveAttachment(attachment, slotId) && HCTapedLightPermit.Receive(this, attachment, slotId);
    }
    override void EEItemDetached(EntityAI item, string slot_name)
    {
        super.EEItemDetached(item, slot_name);
        if (!HCTapedLightPermit.Restoring(this, item)) { HCTapedLightRuntime.Detached(this, item, slot_name); }
    }
}
