// Reuse the existing native action. Allocation failure cleans only fresh results.
modded class ActionDeCraftDrysackBag
{
    protected bool m_HCFinishing;

    protected bool HCValidDrysack(ItemBase item, PlayerBase player)
    {
        if (!item || !player || !player.IsAlive() || player.IsUnconscious())
            return false;
        if (item.IsRuined() || item.IsSetForDeletion() || !item.IsEmpty())
            return false;
        if (!item.GetInventory())
            return false;
        if (item.GetHierarchyRootPlayer() != player || item.GetInventory().IsAttachment())
            return false;
        string sourceType = item.GetType();
        return sourceType == "DrysackBag_Green" || sourceType == "DrysackBag_Orange" || sourceType == "DrysackBag_Yellow";
    }

    override bool ActionCondition(PlayerBase player, ActionTarget target, ItemBase item)
    {
        return HCValidDrysack(item, player) && super.ActionCondition(player, target, item);
    }

    override void OnFinishProgressServer(ActionData action_data)
    {
        if (!GetGame() || !GetGame().IsServer() || !action_data)
            return;
        if (m_HCFinishing)
        {
            HCCraftRefusal.ActionRefuse(action_data, HCRefusal.BUSY);
            return;
        }
        if (!HCValidDrysack(action_data.m_MainItem, action_data.m_Player))
        {
            HCCraftRefusal.ActionRefuse(action_data, HCCraftRefusal.INPUTS);
            return;
        }
        m_HCFinishing = true;
        ItemBase source = action_data.m_MainItem;
        string outputType = "WaterproofBag_" + source.ConfigGetString("color");
        EntityAI bagResult = action_data.m_Player.SpawnEntityOnGroundRaycastDispersed(outputType);
        EntityAI ropeResult = action_data.m_Player.SpawnEntityOnGroundRaycastDispersed("Rope");
        // N2 3_Game/Entities/EntityAI.c:812: refuse deferred-deleting results.
        if (!bagResult || !ropeResult || bagResult.IsSetForDeletion() || ropeResult.IsSetForDeletion())
        {
            if (bagResult)
                bagResult.Delete();
            if (ropeResult)
                ropeResult.Delete();
            m_HCFinishing = false;
            HCCraftRefusal.ActionRefuse(action_data, HCCraftRefusal.OUTPUT);
            return;
        }
        // N3 4_World/Static/MiscGameplayFunctions.c:271,296,319:
        // select agents + health, exclude generic variables (quantity/energy).
        // N3 4_World/Classes/UserActionsComponent/Actions/Continuous/
        // ActionDeCraftDrysackBag.c:44,50,53 (spawn, properties, delete).
        // Wetness: N2 4_World/Entities/ItemBase.c:3692,3721.
        // Keep each fresh result's native quantity and the native bag colour.
        MiscGameplayFunctions.TransferItemProperties(source, bagResult, true, false, true);
        MiscGameplayFunctions.TransferItemProperties(source, ropeResult, true, false, true);
        bagResult.SetWet(source.GetWet());
        ropeResult.SetWet(source.GetWet());
        source.Delete();
        m_HCFinishing = false;
    }
}
