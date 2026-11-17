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
    static bool RadioMatches(HCGroupEquipment source, HCGroupEquipment recipient)
    {
        foreach (float frequency : source.Frequencies)
        {
            if (recipient.Frequencies.Find(frequency) >= 0) return true;
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
        bool blocked = DayZPhysics.RaycastRV(start, finish, contact, normal, component, hits, null, source, false, false, ObjIntersectView, 0.0, CollisionFlags.NEARESTCONTACT);
        if (!blocked) return true;
        return hits.Count() == 1 && hits.Get(0) == recipient;
    }
}
