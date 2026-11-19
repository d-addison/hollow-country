// #210: reuse the shared inventory cursor/frame lifecycle, matching native
// SmokeGrenadeBase subclasses instead of one trade recipe's exact class.
// Native scripts-1.30.164289: 1_Core/proto/EnScript.c:94 Cast,
// :380 Count, :407 Insert, :470 RemoveOrdered;
// 3_Game/Entities/EntityAI.c:882 GetHierarchyRootPlayer, :1884 GetInventory;
// Entities/Object.c:517 IsAlive, :1219 IsRuined; Systems/Inventory/Inventory.c:138 GetCargo,
// :205 AttachmentCount, :220 GetAttachmentFromIndex; Cargo.c:28 GetItemCount,
// :32 GetItem. HCStart/HCRetire citations remain on HCXTradeInventoryScan.
class HCW38SituationSmokeStock : HCXTradeInventoryScan
{
    override ItemBase HCStep(int limit)
    {
        if (!Actor || !Actor.IsAlive()) { HCRetire(); return null; }
        if (Found && Found.GetHierarchyRootPlayer() == Actor && !Found.IsRuined()) { return Found; }
        Found = null;
        if (Complete) { return null; }
        while (Frames.Count() > 0 && Visited < limit)
        {
            if (!HCServer.HCTickWork().HCTakeFor(HCUnitBudget.HC_WORK_SITUATIONS, 1)) { return null; }
            HCXTradeInventoryFrame frame = Frames[Frames.Count() - 1];
            EntityAI entity = frame.NodeEntity;
            if (!entity) { Frames.RemoveOrdered(Frames.Count() - 1); continue; }
            if (!frame.Checked)
            {
                frame.Checked = true;
                Visited++;
                SmokeGrenadeBase candidate = SmokeGrenadeBase.Cast(entity);
                if (candidate && !candidate.IsRuined() && candidate.GetHierarchyRootPlayer() == Actor) { Found = candidate; return Found; }
                continue;
            }
            EntityAI child;
            if (frame.Attachment < entity.GetInventory().AttachmentCount())
            {
                child = entity.GetInventory().GetAttachmentFromIndex(frame.Attachment);
                frame.Attachment++;
            }
            else
            {
                CargoBase cargo = entity.GetInventory().GetCargo();
                if (cargo && frame.CargoIndex < cargo.GetItemCount())
                {
                    child = cargo.GetItem(frame.CargoIndex);
                    frame.CargoIndex++;
                }
                else { Frames.RemoveOrdered(Frames.Count() - 1); continue; }
            }
            if (child && Frames.Count() < limit)
            {
                HCXTradeInventoryFrame nextFrame = new HCXTradeInventoryFrame;
                nextFrame.NodeEntity = child;
                Frames.Insert(nextFrame);
            }
        }
        Complete = true;
        return null;
    }
}
