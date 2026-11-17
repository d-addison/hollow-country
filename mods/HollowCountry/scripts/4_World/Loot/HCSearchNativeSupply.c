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

// Explicit server-owned world-spawner handle registry. There is no radius/world
// discovery, entity creation or inference of CE origin from a type/profile.
// The actual world-spawner must call RegisterOwned with its provenance record.
// Stock CE/proxy acquisition and external SHA validation are NOT supplied here.
class HCSearchSupplyRegistry
{
    protected static ref array<EntityAI> s_Registered = new array<EntityAI>;
    protected ref array<ref HCSearchOwnedSupply> m_Entries = new array<ref HCSearchOwnedSupply>;
    protected string m_SourceId;
    protected string m_SourcePin;
    protected string m_WorldName;
    protected string m_Build;
    protected bool m_Opened;
    protected bool m_Sealed;
    protected bool m_Transferring;

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
        if (m_Opened || !GetGame().IsServer() || !GetCEApi()) return false;
        if (!HCSearchRules.TextValid(sourceId, 128) || !HCSearchRules.PinValid(sourcePin)) return false;
        string actualBuild;
        GetGame().GetVersion(actualBuild);
        if (GetGame().GetWorldName() != worldName || actualBuild != build) return false;
        m_SourceId = sourceId;
        m_SourcePin = sourcePin;
        m_WorldName = worldName;
        m_Build = build;
        m_Opened = true;
        Print("[HC Search Economy] registry provenance is caller-attested; not stock CE qualification");
        return true;
    }

    bool ReadyFor(HCSearchManifest manifest)
    {
        if (!m_Opened || !manifest || !GetGame().IsServer() || !GetCEApi()) return false;
        if (manifest.SourceId != m_SourceId || manifest.SourcePin != m_SourcePin) return false;
        return manifest.WorldName == m_WorldName && manifest.Build == m_Build;
    }

    void Seal() { m_Sealed = true; }

    HCSearchOwnedSupply Find(string supplyId)
    {
        foreach (HCSearchOwnedSupply candidate : m_Entries)
        {
            if (candidate.SupplyId == supplyId) return candidate;
        }
        return null;
    }

    bool RegisterOwned(EntityAI item, string sourceRecordId)
    {
        if (!m_Opened || m_Sealed || m_Transferring || !CandidateValid(item)) return false;
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
        if (original.GetType() != InventoryLocationType.GROUND && original.GetType() != InventoryLocationType.CARGO) return false;
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

    bool Unchanged(HCSearchOwnedSupply supply)
    {
        if (!supply || !supply.ItemHandle || supply.ItemHandle.GetHierarchyRootPlayer()) return false;
        EntityAI item = supply.ItemHandle;
        if (HCSearchSupplyRegistry.PersistentId(item) != supply.SupplyId || item.GetType() != supply.ItemClass) return false;
        if (item.GetQuantity() != supply.Quantity) return false;
        InventoryLocation current = new InventoryLocation;
        return item.GetInventory().GetCurrentInventoryLocation(current) && current.CompareLocationOnly(supply.OriginalLocation);
    }

    bool CanTransfer(HCSearchEntry entry, PlayerBase actor)
    {
        if (!m_Opened || m_Transferring || !entry || !actor) return false;
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

    int Transfer(HCSearchEntry entry, PlayerBase actor)
    {
        if (!CanTransfer(entry, actor)) return 4;
        string actorId = actor.GetIdentity().GetId();
        HCSearchOwnedSupply supply = Find(entry.SupplyId);
        InventoryLocation sourceLocation = new InventoryLocation;
        InventoryLocation destination = new InventoryLocation;
        if (!supply.ItemHandle.GetInventory().GetCurrentInventoryLocation(sourceLocation)) return 4;
        if (!actor.GetInventory().FindFreeLocationFor(supply.ItemHandle, FindInventoryLocationType.CARGO, destination)) return 4;
        if (!sourceLocation.CompareLocationOnly(supply.OriginalLocation)) return 4;
        if (!destination.GetParent()) return 4;
        if (destination.GetParent() != actor && destination.GetParent().GetHierarchyRootPlayer() != actor) return 4;
        // Native inventory preflight invokes item/container scripts. Revalidate
        // after those callbacks, immediately before the single native move.
        if (!actor.IsAlive() || actor.IsUnconscious() || !actor.GetIdentity()) return 4;
        if (actor.GetIdentity().GetId() != actorId || actor.GetIdentity().GetPlayer() != actor) return 4;
        if (!Unchanged(supply)) return 4;
        supply.Attempted = true;
        m_Transferring = true;
        // Installed Inventory.c TakeToDst(SERVER) synchronously moves then sends
        // SYNC_MOVE. Readback remains mandatory; cross-save atomicity unproved.
        bool moved = actor.GetInventory().TakeToDst(InventoryMode.SERVER, sourceLocation, destination);
        m_Transferring = false;
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
