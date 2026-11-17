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
        if (m_HCFinishing || !HCValidDrysack(action_data.m_MainItem, action_data.m_Player))
            return;
        m_HCFinishing = true;
        ItemBase source = action_data.m_MainItem;
        string outputType = "WaterproofBag_" + source.ConfigGetString("color");
        EntityAI bagResult = action_data.m_Player.SpawnEntityOnGroundRaycastDispersed(outputType);
        EntityAI ropeResult = action_data.m_Player.SpawnEntityOnGroundRaycastDispersed("Rope");
        if (!bagResult || !ropeResult)
        {
            if (bagResult)
                bagResult.Delete();
            if (ropeResult)
                ropeResult.Delete();
            m_HCFinishing = false;
            return;
        }
        // Preserve native properties/colors and delete only after both exist.
        MiscGameplayFunctions.TransferItemProperties(source, bagResult);
        MiscGameplayFunctions.TransferItemProperties(source, ropeResult);
        source.Delete();
        m_HCFinishing = false;
    }
}
