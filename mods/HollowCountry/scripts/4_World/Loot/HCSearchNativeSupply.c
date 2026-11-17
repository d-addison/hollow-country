class HCSearchOwnedSupply
{
    EntityAI ItemHandle;
    string SupplyId;
    string SourceRecordId;
    string ItemClass;
    float Quantity;
    bool Attempted;
    ref InventoryLocation OriginalLocation;
}

// Explicit server-owned handle registry. This class does no radius/world discovery,
// entity creation or inference of CE origin from a type/profile: its caller
// (HCSearchSupplyProvider, over reviewed volumes only) calls RegisterOwned with a
// provenance record. External SHA validation is NOT supplied here.
class HCSearchSupplyRegistry
{
    protected static ref array<EntityAI> s_Registered = new array<EntityAI>;
    // Strong references keep every registry (and so its handle bookkeeping) alive until
    // it is retired; a non-ref element would silently expire to null while its handles
    // stayed pinned in s_Registered. At most one registry is bound to a live economy.
    protected static ref array<ref HCSearchSupplyRegistry> s_Registries = new array<ref HCSearchSupplyRegistry>;
    protected ref array<ref HCSearchOwnedSupply> m_Entries = new array<ref HCSearchOwnedSupply>;
    protected string m_SourceId;
    protected string m_SourcePin;
    protected string m_WorldName;
    protected string m_Build;
    protected bool m_Opened;
    protected bool m_Sealed;
    protected bool m_Transferring;
    // Retire() arrived while a transfer was in flight; applied when it completes.
    protected bool m_RetirePending;
    // The economy this registry was sealed into (weak: the economy owns the registry).
    protected HCSearchEconomy m_Owner;

    static bool CandidateValid(EntityAI item)
    {
        if (!item || !GetGame().IsServer() || !GetCEApi()) return false;
        if (!item.IsInventoryItem()) return false;
        if (item.IsMan() || item.IsAnimal() || item.IsZombie()) return false;
        CEItemProfile profile = item.GetEconomyProfile();
        return profile && profile.GetNominal() > 0;
    }

    static string PersistentId(EntityAI item)
    {
        if (!item) return "";
        int first, second, third, fourth;
        item.GetPersistentID(first, second, third, fourth);
        if (first == 0 && second == 0 && third == 0 && fourth == 0) return "";
        return first.ToString() + "_" + second.ToString() + "_" + third.ToString() + "_" + fourth.ToString();
    }

    bool BindSource(string sourceId, string sourcePin, string worldName, string build)
    {
        if (m_Opened || m_Sealed || !GetGame().IsServer() || !GetCEApi()) return false;
        if (!HCSearchRules.TextValid(sourceId, 128) || !HCSearchRules.PinValid(sourcePin)) return false;
        string actualBuild;
        GetGame().GetVersion(actualBuild);
        // The engine reports its full version (1.30.164289.70 natively); the caller passes the
        // build the manifest will carry. Both must be admitted builds, and the registry
        // always records the canonical pin so every later compare is build-text independent.
        if (!HCBuildIdentity.SameWorld(GetGame().GetWorldName(), worldName)) return false;
        if (!HCBuildIdentity.Matches(actualBuild) || !HCBuildIdentity.Matches(build)) return false;
        // A stopped lifecycle was retired by its economy and an abandoned unbound plan
        // is retired here, so untouched supplies can be rebound. A registry bound to a
        // LIVE economy is never retired by a replacement: the bind is refused instead.
        // Depletion lives in the journal, never in this registry.
        if (!HCSearchSupplyRegistry.ClaimLifecycle(this)) return false;
        m_SourceId = sourceId;
        m_SourcePin = sourcePin;
        m_WorldName = HCBuildIdentity.CanonicalWorld(worldName);
        m_Build = HCBuildIdentity.Canonical();
        m_Opened = true;
        Print("[HC Search Economy] registry provenance is caller-attested; not stock CE qualification");
        return true;
    }

    bool ReadyFor(HCSearchManifest manifest)
    {
        if (!m_Opened || !manifest || !GetGame().IsServer() || !GetCEApi()) return false;
        if (manifest.SourceId != m_SourceId || manifest.SourcePin != m_SourcePin) return false;
        return HCBuildIdentity.SameWorld(manifest.WorldName, m_WorldName) && HCBuildIdentity.SameBuild(manifest.Build, m_Build);
    }

    void Seal(HCSearchEconomy owner)
    {
        m_Owner = owner;
        m_Sealed = true;
    }

    // True only while bound to an economy that is still serving. An economy that
    // stopped, failed terminally (journal I/O) or no longer exists no longer owns the
    // lifecycle: its registry becomes reclaimable by the next ClaimLifecycle/Abandon,
    // which retires it (deferred while a transfer is in flight). Journal evidence is
    // untouched, so consumed or quarantined sites stay terminal on rebind.
    bool Owning()
    {
        if (!m_Opened || !m_Sealed || !m_Owner) return false;
        return m_Owner.Serving();
    }

    HCSearchOwnedSupply Find(string supplyId)
    {
        foreach (HCSearchOwnedSupply candidate : m_Entries)
        {
            if (candidate.SupplyId == supplyId) return candidate;
        }
        return null;
    }

    // Make `opening` the only registry in the process-wide list. Expired entries are
    // dropped, an unbound (abandoned) predecessor is retired, and a predecessor that is
    // still bound to a live economy blocks the claim without being touched.
    static bool ClaimLifecycle(HCSearchSupplyRegistry opening)
    {
        int index = s_Registries.Count() - 1;
        while (index >= 0)
        {
            HCSearchSupplyRegistry previous = s_Registries[index];
            index = index - 1;
            if (!previous) continue;
            if (previous == opening) continue;
            if (previous.Owning()) return false;
            if (!previous.Retire()) return false;
        }
        index = s_Registries.Count() - 1;
        while (index >= 0)
        {
            if (!s_Registries[index]) s_Registries.Remove(index);
            index = index - 1;
        }
        if (s_Registries.Find(opening) < 0) s_Registries.Insert(opening);
        return true;
    }

    bool RegisterOwned(EntityAI item, string sourceRecordId)
    {
        if (!m_Opened || m_Sealed || m_Transferring || !CandidateValid(item)) return false;
        // Forget handles of deleted entities (the engine nulls script references to
        // them) so they stop counting toward the bounds. A pruned supply is simply
        // unavailable: Find() no longer returns it and nothing is ever recreated.
        int position = s_Registered.Count() - 1;
        while (position >= 0)
        {
            if (!s_Registered[position]) s_Registered.Remove(position);
            position = position - 1;
        }
        position = m_Entries.Count() - 1;
        while (position >= 0)
        {
            if (!m_Entries[position].ItemHandle) m_Entries.Remove(position);
            position = position - 1;
        }
        if (m_Entries.Count() >= 4096 || s_Registered.Count() >= 4096) return false;
        if (!HCSearchRules.TextValid(sourceRecordId, 128) || item.GetHierarchyRootPlayer()) return false;
        string supplyId = HCSearchSupplyRegistry.PersistentId(item);
        if (supplyId == "" || Find(supplyId) || s_Registered.Find(item) >= 0) return false;
        foreach (HCSearchOwnedSupply previous : m_Entries)
        {
            if (previous.SourceRecordId == sourceRecordId) return false;
        }
        float quantity = item.GetQuantity();
        if (!(quantity >= 0.0 && quantity <= 1000000000.0)) return false;
        InventoryLocation original = new InventoryLocation;
        if (!item.GetInventory().GetCurrentInventoryLocation(original) || !original.IsValid()) return false;
        // PROXYCARGO is native building (proxy) cargo, where stock CE static loot may
        // sit. Installed InventoryLocation.c declares it; the real move from it is
        // still unobserved. Attachments/hands/vehicle/unknown stay refused.
        if (original.GetType() != InventoryLocationType.GROUND && original.GetType() != InventoryLocationType.CARGO && original.GetType() != InventoryLocationType.PROXYCARGO) return false;
        HCSearchOwnedSupply supply = new HCSearchOwnedSupply;
        supply.ItemHandle = item;
        supply.SupplyId = supplyId;
        supply.SourceRecordId = sourceRecordId;
        supply.ItemClass = item.GetType();
        supply.Quantity = quantity;
        supply.OriginalLocation = original;
        m_Entries.Insert(supply);
        s_Registered.Insert(item);
        return true;
    }

    // Shutdown/abandon cleanup: relinquish ownership and disable this registry for good
    // (ReadyFor/CanTransfer/Transfer/RegisterOwned/BindSource all refuse afterwards).
    // Touches no entity, inventory or journal. While a transfer is in flight the native
    // move is never interrupted and ownership never overlaps: retirement is recorded and
    // applied the moment that transfer returns, and false is returned meanwhile.
    bool Retire()
    {
        if (m_Transferring)
        {
            m_RetirePending = true;
            return false;
        }
        ForgetHandles();
        m_Opened = false;
        m_Sealed = true;
        m_RetirePending = false;
        int listed = s_Registries.Find(this);
        if (listed >= 0) s_Registries.Remove(listed);
        return true;
    }

    protected void ForgetHandles()
    {
        foreach (HCSearchOwnedSupply released : m_Entries)
        {
            if (!released.ItemHandle) continue;
            int position = s_Registered.Find(released.ItemHandle);
            if (position >= 0) s_Registered.Remove(position);
        }
        m_Entries.Clear();
    }

    bool Unchanged(HCSearchOwnedSupply supply)
    {
        if (!supply || !supply.ItemHandle || supply.ItemHandle.GetHierarchyRootPlayer()) return false;
        EntityAI item = supply.ItemHandle;
        if (HCSearchSupplyRegistry.PersistentId(item) != supply.SupplyId || item.GetType() != supply.ItemClass) return false;
        if (item.GetQuantity() != supply.Quantity) return false;
        InventoryLocation current = new InventoryLocation;
        return item.GetInventory().GetCurrentInventoryLocation(current) && current.CompareLocationOnly(supply.OriginalLocation);
    }

    // FindFreeLocationFor runs item/container scripts, so the whole check is a guarded
    // callback window: Retire/Stop arriving inside it is deferred and applied after.
    bool CanTransfer(HCSearchEntry entry, PlayerBase actor)
    {
        if (!m_Opened || m_Transferring || m_RetirePending) return false;
        m_Transferring = true;
        bool allowed = Preflight(entry, actor);
        m_Transferring = false;
        if (m_RetirePending) Retire();
        return allowed && m_Opened;
    }

    protected bool Preflight(HCSearchEntry entry, PlayerBase actor)
    {
        if (!m_Opened || !entry || !actor) return false;
        if (!GetGame().IsServer() || !GetCEApi() || !actor.IsAlive() || actor.IsUnconscious()) return false;
        if (!actor.GetIdentity() || actor.GetIdentity().GetPlayer() != actor) return false;
        HCSearchOwnedSupply supply = Find(entry.SupplyId);
        if (!supply || supply.Attempted || supply.ItemClass != entry.ItemClass || !Unchanged(supply)) return false;
        if (!supply.ItemHandle.IsTakeable()) return false;
        // Native inventory paths retain normal local pickup distance. No remote
        // escrow delivery, teleport or hidden relocation to make this succeed.
        float distance = vector.DistanceSq(actor.GetPosition(), supply.ItemHandle.GetPosition());
        if (!(distance >= 0.0 && distance <= 6.25)) return false;
        InventoryLocation destination = new InventoryLocation;
        return actor.GetInventory().FindFreeLocationFor(supply.ItemHandle, FindInventoryLocationType.CARGO, destination);
    }

    // The transfer, including every native callback (preflight, FindFreeLocationFor,
    // TakeToDst), runs with m_Transferring set so no retirement or rebind can overlap it.
    int Transfer(HCSearchEntry entry, PlayerBase actor)
    {
        if (m_Transferring || m_RetirePending) return 4;
        m_Transferring = true;
        int result = Move(entry, actor);
        m_Transferring = false;
        if (m_RetirePending) Retire();
        return result;
    }

    protected int Move(HCSearchEntry entry, PlayerBase actor)
    {
        if (!Preflight(entry, actor)) return 4;
        string actorId = actor.GetIdentity().GetId();
        HCSearchOwnedSupply supply = Find(entry.SupplyId);
        InventoryLocation sourceLocation = new InventoryLocation;
        InventoryLocation destination = new InventoryLocation;
        if (!supply.ItemHandle.GetInventory().GetCurrentInventoryLocation(sourceLocation)) return 4;
        if (!actor.GetInventory().FindFreeLocationFor(supply.ItemHandle, FindInventoryLocationType.CARGO, destination)) return 4;
        if (!sourceLocation.CompareLocationOnly(supply.OriginalLocation)) return 4;
        if (!destination.GetParent()) return 4;
        if (destination.GetParent() != actor && destination.GetParent().GetHierarchyRootPlayer() != actor) return 4;
        // Native inventory preflight invokes item/container scripts. Revalidate the
        // actor, the source AND this registry's ownership after those callbacks,
        // immediately before the single native move.
        if (!m_Opened || m_RetirePending || Find(entry.SupplyId) != supply || s_Registered.Find(supply.ItemHandle) < 0) return 4;
        if (!actor.IsAlive() || actor.IsUnconscious() || !actor.GetIdentity()) return 4;
        if (actor.GetIdentity().GetId() != actorId || actor.GetIdentity().GetPlayer() != actor) return 4;
        if (!Unchanged(supply)) return 4;
        supply.Attempted = true;
        // Installed Inventory.c TakeToDst(SERVER) synchronously moves then sends
        // SYNC_MOVE. Readback remains mandatory; cross-save atomicity unproved.
        bool moved = actor.GetInventory().TakeToDst(InventoryMode.SERVER, sourceLocation, destination);
        EntityAI item = supply.ItemHandle;
        if (!item || HCSearchSupplyRegistry.PersistentId(item) != supply.SupplyId) return 3;
        if (item.GetType() != supply.ItemClass || item.GetQuantity() != supply.Quantity) return 3;
        if (moved && item.GetHierarchyRootPlayer() == actor) return 2;
        if (!moved && Unchanged(supply)) return 4;
        // Never move loot back out of a player's inventory, create compensation,
        // or reset Attempted based on a failed/ambiguous native return value.
        Print("[HC Search Economy] native transfer uncertain; allocation held, no refund/replay");
        return 3;
    }
}
