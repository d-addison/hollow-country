// Native: 3_Game/Entities/EntityAI.c:1414 EEOnCECreate, :1104 EEKilled.
// Native: 4_World/Entities/ItemBase.c:987 EEItemLocationChanged;
// 3_Game/Systems/Inventory/InventoryLocation.c:52 GetParent.
// EntityAI.c:1413 explicitly says CE/Debug. This is a candidate signal only,
// not a durable CE allocator receipt. Persisted entities have no new-CE flag;
// no attempt is made to infer origin from class, persistent ID or CE profile.
// The flag lives in memory only and is cleared by any real move of the item (old location not
// UNKNOWN), so a case that was carried, placed or stored anywhere is never a candidate again
// (the scene cache fill requires it: HCEventCacheFill.Step).
modded class ItemBase
{
    protected bool m_HCEventEconomyCandidate;
    override void EEOnCECreate()
    {
        super.EEOnCECreate();
        if (GetGame() && GetGame().IsServer()) { m_HCEventEconomyCandidate = true; }
    }
    override void EEItemLocationChanged(notnull InventoryLocation oldLoc, notnull InventoryLocation newLoc)
    {
        super.EEItemLocationChanged(oldLoc, newLoc);
        // The CE event case never moves legitimately: any real move (the old location is known, not
        // the UNKNOWN of a freshly created object) ends the candidacy, wherever it goes next.
        if (m_HCEventEconomyCandidate && oldLoc.GetType() != InventoryLocationType.UNKNOWN && GetGame() && GetGame().IsServer())
        {
            m_HCEventEconomyCandidate = false;
        }
        if (!GetGame() || !GetGame().IsServer() || !HCEventQualification.Admitted()) { return; }
        HCEventModule module = HCEventModule.Get();
        if (!module) { return; }
        PlayerBase previousCarrier;
        EntityAI previousParent = oldLoc.GetParent();
        if (previousParent) { previousCarrier = PlayerBase.Cast(previousParent.GetHierarchyRootPlayer()); }
        module.ItemLocationChanged(this, previousCarrier, newLoc.GetParent());
    }
    bool HCEventEconomyCandidate()
    {
        return m_HCEventEconomyCandidate;
    }
}
modded class ZombieBase
{
    protected bool m_HCEventEconomyCandidate;
    override void EEOnCECreate()
    {
        super.EEOnCECreate();
        if (GetGame() && GetGame().IsServer()) { m_HCEventEconomyCandidate = true; }
    }
    bool HCEventEconomyCandidate()
    {
        return m_HCEventEconomyCandidate;
    }
    override void EEKilled(Object killer)
    {
        super.EEKilled(killer);
        if (!GetGame() || !GetGame().IsServer() || !HCEventQualification.Admitted()) { return; }
        HCEventModule module = HCEventModule.Get();
        if (!module) { return; }
        PlayerBase participant = PlayerBase.Cast(killer);
        if (!participant)
        {
            EntityAI source = EntityAI.Cast(killer);
            if (source) { participant = PlayerBase.Cast(source.GetHierarchyRootPlayer()); }
        }
        // Only a currently enrolled live server handle can attribute this death.
        // Unattributed/environmental deaths remain unresolved, never guessed.
        if (participant) { module.InfectedKilled(this, participant); }
    }
}
