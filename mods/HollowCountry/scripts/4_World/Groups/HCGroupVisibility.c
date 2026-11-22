// Native 1.30 evidence: see scratchpad-review/v1-groups/REPORT.md.
// Inventory is read only. Over-budget equipment fails closed.
class HCGroupEquipment
{
    bool HasMap;
    bool HasGPS;
    ref array<float> Frequencies = new array<float>();

    static HCGroupEquipment Read(PlayerBase player)
    {
        HCGroupEquipment equipment = new HCGroupEquipment;
        equipment.HasMap = CfgGameplayHandler.GetMapIgnoreMapOwnership();
        equipment.HasGPS = CfgGameplayHandler.GetMapIgnoreNavItemsOwnership();
        if (!player || !player.IsAlive() || !player.GetInventory()) return equipment;
        if (player.GetInventory().CountInventory() > 512) return equipment;
        array<EntityAI> items = new array<EntityAI>();
        player.GetInventory().EnumerateInventory(InventoryTraversalType.PREORDER, items);
        if (items.Count() > 512) return equipment;
        foreach (EntityAI entity : items)
        {
            ItemBase item = ItemBase.Cast(entity);
            if (!item || item.IsRuined() || item.GetHierarchyRootPlayer() != player) continue;
            if (ItemMap.Cast(item)) equipment.HasMap = true;
            ItemGPS gps = ItemGPS.Cast(item);
            if (gps && gps.IsTurnedOn()) equipment.HasGPS = true;
            // Restrict to handheld PersonalRadio (including inherited variants),
            // excluding static/base transceivers and entertainment receivers.
            PersonalRadio handheld = PersonalRadio.Cast(item);
            if (!handheld || !handheld.IsTransmitter() || !handheld.GetCompEM()) continue;
            if (!handheld.GetCompEM().IsWorking()) continue;
            float frequency = handheld.GetTunedFrequency();
            if (!(frequency > 0.0 && frequency <= 1000.0)) continue;
            if (equipment.Frequencies.Find(frequency) < 0 && equipment.Frequencies.Count() < 8)
                equipment.Frequencies.Insert(frequency);
        }
        return equipment;
    }
}

class HCGroupVisibility
{
    // Synchronous server snapshot scope. A missing/invalid transport recipient
    // fails closed; out-of-transport collection remains available to bounded
    // server diagnostics. Save/restore supports nested calls without a scan.
    protected static bool s_InSnapshot;
    protected static string s_Recipient;
    static bool HCSnapshotActive() { return s_InSnapshot; }
    static string HCRecipient() { return s_Recipient; }
    static void HCSnapshot(bool active, string uid)
    {
        s_InSnapshot = active;
        s_Recipient = uid;
    }

    // HC-26: use the existing validated MaxIconDistance, default ~1000 m
    // (native network bubble / ordinary rifle report scale). No new range.
    static bool HCWithinRange(vector source, vector recipient, float maximum)
    {
        if (!(maximum > 0) || !HCGroupRules.PositionValid(source) || !HCGroupRules.PositionValid(recipient)) { return false; }
        float dx = source[0] - recipient[0];
        float dy = source[1] - recipient[1];
        float dz = source[2] - recipient[2];
        return dx * dx + dy * dy + dz * dz <= maximum * maximum;
    }

    static bool RadioMatches(HCGroupEquipment source, HCGroupEquipment recipient)
    {
        // Read admits at most eight exact float frequencies. Float set keys are
        // unsupported natively; make both scan bounds explicit (<=64 comparisons).
        for (int sourceIndex = 0; sourceIndex < 8; sourceIndex++)
        {
            if (sourceIndex >= source.Frequencies.Count()) break;
            for (int recipientIndex = 0; recipientIndex < 8; recipientIndex++)
            {
                if (recipientIndex >= recipient.Frequencies.Count()) break;
                if (source.Frequencies[sourceIndex] == recipient.Frequencies[recipientIndex]) return true;
            }
        }
        return false;
    }

    static bool HasLOS(PlayerBase source, PlayerBase recipient)
    {
        // Current head positions account for crouching/prone. Unknown bones
        // fail closed; no standing-height approximation over low cover.
        int sourceBone = source.GetBoneIndexByName("Head");
        int recipientBone = recipient.GetBoneIndexByName("Head");
        if (sourceBone < 0 || recipientBone < 0) return false;
        vector start = source.GetBonePositionWS(sourceBone);
        vector finish = recipient.GetBonePositionWS(recipientBone);
        if (!HCGroupRules.PositionValid(start) || !HCGroupRules.PositionValid(finish)) return false;
        vector contact;
        vector normal;
        int component;
        set<Object> hits = new set<Object>();
        Object parent = Object.Cast(source.GetParent());
        if (parent != recipient.GetParent()) parent = null;
        bool blocked = DayZPhysics.RaycastRV(start, finish, contact, normal, component, hits, parent, source, false, false, ObjIntersectView, 0.0, CollisionFlags.NEARESTCONTACT);
        if (!blocked) return true;
        return hits.Count() == 1 && hits.Get(0) == recipient;
    }
}
