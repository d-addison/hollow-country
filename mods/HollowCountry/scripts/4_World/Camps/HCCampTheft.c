// LC-T415 / EXP-L9, EXP-L4. EnableCamps admits via HCCampModule.OnStart;
// verdict is diagnostic only. Native acceptance/compile remain PENDING.
// Installed scripts-1.30.164289 evidence:
// 3_Game/Global/Game.c:546 ConfigGetType, :558 ConfigGetTextArray,
// :612 ConfigIsExisting; Plugins/PluginBase/PluginConfigViewer.c:186 CT_ARRAY;
// 3_Game/Entities/Object.c:287 GetPosition, :467 GetType, :630/636
// IsWeapon/IsMeleeWeapon, :1219 IsRuined; EntityAI.c:882/885 hierarchy,
// :1884 GetInventory; Systems/Inventory/Inventory.c:138 GetCargo, :205
// AttachmentCount; Cargo.c:28/32 count/item; Inventory.c:276 FindFreeLocationFor,
// :1057 TakeToDst (InventoryMode.SERVER), via HCSearchSupplyRegistry.Transfer.
// 1_Core/proto/EnConvert.c:210 DistanceSq, :30 int.ToString; EnDebug.c:96 Print.
// Installed gear_camping.pbo config.bin CfgVehicles/WoodenCrate (RAP body
// 0x1f397): parent Container_Base, no declared attachments; camping.c:17
// WoodenCrate inherits DeployableContainer_Base. Effective config is checked
// again in-game. Any attachment or configured attachment slot is ineligible;
// no assumptions about locks supplied by other mods and no third-party assets.
class HCCampTheft
{
    static bool Due(int now, int last)
    {
        return now > 0 && (last == 0 || (now >= last && now - last >= 259200));
    }

    static bool Unlocked(ItemBase container)
    {
        if (!container || container.GetType() != "WoodenCrate" || !container.GetInventory()) return false;
        if (!GetGame().ConfigIsExisting("CfgVehicles WoodenCrate")) return false;
        if (GetGame().ConfigIsExisting("CfgVehicles WoodenCrate attachments") && GetGame().ConfigGetType("CfgVehicles WoodenCrate attachments") != CT_ARRAY) return false;
        TStringArray slots = new TStringArray;
        GetGame().ConfigGetTextArray("CfgVehicles WoodenCrate attachments", slots);
        // Vanilla has no lock slots. Any changed layout is unknown, including
        // an empty slot that might be controlled by an optional lock provider.
        return slots.Count() == 0 && container.GetInventory().AttachmentCount() == 0;
    }

    static bool Candidate(ItemBase container, HCCampRecord camp, int now, bool unattended, bool observerClear)
    {
        if (!container || !camp || !unattended || !observerClear || !Due(now, camp.LastTheft)) return false;
        if (!HCLockTable.CampUnlocked(container) || container.IsRuined()) { return false; }
        if (container.GetHierarchyParent() || container.GetHierarchyRootPlayer()) return false;
        vector containerPosition = container.GetPosition();
        return vector.DistanceSq(containerPosition, camp.Position) <= 144;
    }

    static bool SafeItem(EntityAI item)
    {
        return item && !item.IsRuined() && !item.IsWeapon() && !item.IsMeleeWeapon() && item.GetInventory() && !item.GetInventory().GetCargo() && !item.GetHierarchyRootPlayer();
    }

    // Existing, real persistent caches only. No cache/item creation or replay.
    static EntityAI Destination(vector position, out string cacheId)
    {
        cacheId = "";
        HCDeadDrops drops = HCDeadDrops.Get();
        if (drops)
        {
            for (int dropIndex = 0; dropIndex < drops.Count(); dropIndex++)
            {
                EntityAI dropCache = drops.Cache(dropIndex);
                if (!dropCache) continue;
                vector dropCachePosition = dropCache.GetPosition();
                if (vector.DistanceSq(dropCachePosition, position) <= 144) continue;
                if (!HCObserverTransitionGate.CanTransition(dropCachePosition, 500)) continue;
                if (!HCLockTable.CampUnlocked(ItemBase.Cast(dropCache))) { continue; }
                cacheId = drops.CacheId(dropIndex);
                return dropCache;
            }
        }
        HCHoldouts holdouts = HCHoldouts.Get();
        if (!holdouts) return null;
        for (int homeIndex = 0; homeIndex < holdouts.Count(); homeIndex++)
        {
            EntityAI homeCache = holdouts.Cache(homeIndex);
            if (!homeCache) continue;
            vector homeCachePosition = homeCache.GetPosition();
            if (vector.DistanceSq(homeCachePosition, position) <= 144) continue;
            if (!HCObserverTransitionGate.CanTransition(homeCachePosition, 500)) continue;
            if (!HCLockTable.CampUnlocked(ItemBase.Cast(homeCache))) { continue; }
            cacheId = holdouts.CacheId(homeIndex);
            return homeCache;
        }
        return null;
    }

    protected static bool s_HCScavengeRefusal;

    static void Step(HCCampModule module, HCCampRecord camp, HCCampScan scan, int now)
    {
        // HC-34: pressure and unattended crates are not a carrier or a route.
        // The previous source -> distant cache transfer is retired. Players
        // retain normal native inventory theft. AI theft must travel through
        // the same admitted HC-10 party and single-custody round trip.
        if (!module || !camp || s_HCScavengeRefusal) { return; }
        s_HCScavengeRefusal = true;
        Print("[HC Plan] HC-34 party=camp-theft phase=refused cargo_owner=native-source state=refused count=0 refusal=ABSTRACT_THEFT_RETIRED runtime=PENDING");
    }
}
