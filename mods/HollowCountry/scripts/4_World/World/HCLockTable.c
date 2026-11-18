// W5 #76: conservative storage classification; server inventory remains owner.
// Native scripts-1.30.164289: 3_Game/Entities/Object.c:467 GetType, :511 IsKindOf;
// Entities/EntityAI.c:1884 GetInventory, :1897 FindAttachmentBySlotName;
// Systems/Inventory/Inventory.c:205 AttachmentCount, :220 GetAttachmentFromIndex.
// Native lock classes: 4_World/Entities/ItemBase/CombinationLock.c:25 and
// CodeLock.c:1 DigitalCodeLock. Attached locks protect even while opened/unset.
// Installed gear_camping.pbo config.bin CfgVehicles, RAP body offsets:
// Fence 0x9049 attachments includes Att_CombinationLock and Att_CodeLock;
// CombinationLock 0x1c620 inventorySlot includes Att_CombinationLock (and
// Att_CombinationLock1_Wood/Metal through Att_CombinationLock10_Wood/Metal).
// Tents Medium 0x8f8/Large 0x2336/Car 0x43dd/Party 0x5a4c use CamoNet,Lights;
// WoodenCrate 0x1f397 declares no attachments. No third-party slot is assumed.
// Per query: two named-slot lookups, <=32 attachment checks. No ticking/scans.
class HCLockTable
{
    static const int UNKNOWN = -1;
    static const int UNLOCKED = 0;
    static const int LOCKED = 1;

    static bool StorageType(ItemBase container)
    {
        if (container.IsKindOf("TentBase")) { return true; }
        if (container.IsKindOf("Fence")) { return true; }
        return container.GetType() == "WoodenCrate";
    }

    static int Classify(ItemBase container)
    {
        if (!container || !container.GetInventory()) { return UNKNOWN; }
        if (!StorageType(container)) { return UNKNOWN; }
        if (container.FindAttachmentBySlotName("Att_CombinationLock")) { return LOCKED; }
        if (container.FindAttachmentBySlotName("Att_CodeLock")) { return LOCKED; }
        int count = container.GetInventory().AttachmentCount();
        if (count > 32) { return UNKNOWN; }
        bool unknownAttachment = false;
        int attachmentIndex = 0;
        while (attachmentIndex < count)
        {
            EntityAI attachment = container.GetInventory().GetAttachmentFromIndex(attachmentIndex);
            if (!attachment) { return UNKNOWN; }
            if (attachment.IsKindOf("CombinationLock")) { return LOCKED; }
            if (attachment.IsKindOf("DigitalCodeLock")) { return LOCKED; }
            // Decoration/structural attachments do not prove a lock absent.
            // Unknown optional providers fail closed through this disposition.
            unknownAttachment = true;
            attachmentIndex++;
        }
        if (unknownAttachment) { return UNKNOWN; }
        return UNLOCKED;
    }

    static bool CampUnlocked(ItemBase container)
    {
        if (Classify(container) != UNLOCKED) { return false; }
        // Preserve the inspected no-slot/no-attachment WoodenCrate allowlist.
        // Tents and gates are classified for callers, never theft destinations.
        return HCCampTheft.Unlocked(container);
    }
}
