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
        if (!Unlocked(container) || container.IsRuined()) return false;
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
                if (!Unlocked(ItemBase.Cast(dropCache))) continue;
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
            if (!Unlocked(ItemBase.Cast(homeCache))) continue;
            cacheId = holdouts.CacheId(homeIndex);
            return homeCache;
        }
        return null;
    }

    static void Step(HCCampModule module, HCCampRecord camp, HCCampScan scan, int now)
    {
        if (!module || !camp || !scan || HCEscalationClock.Day() < 1 || !HCWorldModule.Get()) return;
        if (HCEscalationClock.Pressure("raiders") < 0.7 || !Due(now, camp.LastTheft) || module.NearMembers(camp, 300) != 0) return;
        if (!HCObserverTransitionGate.CanTransition(camp.Position, 500)) return;
        // Cheap check first: no crate means no destination search (up to 18 observer queries).
        if (!scan.Crates || scan.Crates.Count() == 0) return;
        string cacheId;
        EntityAI destination = Destination(camp.Position, cacheId);
        if (!destination) return;
        // An invalid journal actor id would fault the shared cache-move journal
        // used by pickers and dead drops; refuse the theft instead.
        string actorId = camp.Id + "-to-" + cacheId;
        if (!HCSearchRules.TextValid(actorId, 128)) return;
        int moved;
        bool charged;
        HCCacheMoves mover = HCCacheMoves.Shared();
        // Scan supplied by the bounded camp scanner: <=8 crates, <=32 items
        // per crate. Two attempted journal moves at most, including failures.
        int attempts;
        bool ambiguous;
        foreach (ItemBase crate : scan.Crates)
        {
            if (attempts >= 2 || ambiguous) break;
            if (!Candidate(crate, camp, now, true, true) && !charged) continue;
            // After the persisted cooldown reservation, recheck storage safety.
            // Split checks: long mixed ||-chains crashed the native server (shelters, compile 152).
            if (!Unlocked(crate) || crate.IsRuined()) continue;
            if (crate.GetHierarchyParent() || crate.GetHierarchyRootPlayer()) continue;
            vector crateNow = crate.GetPosition();
            if (vector.DistanceSq(crateNow, camp.Position) > 144) continue;
            CargoBase cargo = crate.GetInventory().GetCargo();
            if (!cargo || cargo.GetItemCount() > 32) continue;
            array<string> allowed = new array<string>;
            for (int itemIndex = 0; itemIndex < cargo.GetItemCount(); itemIndex++)
            {
                EntityAI item = cargo.GetItem(itemIndex);
                if (!SafeItem(item)) continue;
                string supplyId = HCSearchSupplyRegistry.PersistentId(item);
                if (HCDeadDrops.TheftAllowed(crate, supplyId)) allowed.Insert(supplyId);
            }
            if (allowed.Count() == 0) continue;
            if (!charged)
            {
                // Reserve cooldown BEFORE any callback; a crash never retries
                // this theft. Individual items have immutable claim/attempt/result.
                camp.LastTheft = now;
                if (!module.Commit(now)) return;
                charged = true;
            }
            while (attempts < 2 && Unlocked(crate))
            {
                int phase = mover.TakeOne(crate, destination, actorId, allowed);
                attempts++;
                if (phase == 2) moved++;
                // 0/4 are terminal no-ops. 3 is ambiguous: stop, never replay.
                if (phase == 3) ambiguous = true;
                if (phase != 2) break;
            }
        }
        if (!charged) return;
        if (moved > 0)
        {
            module.Fact(camp, "STOLEN", 1); // supplies went missing at the fact's place
            module.Tell(camp, "Someone has been through your crates");
        }
        Print("[HollowCountry] V2 camps theft camp=" + camp.Id + " items=" + moved.ToString() + " cache=" + cacheId);
    }
}
