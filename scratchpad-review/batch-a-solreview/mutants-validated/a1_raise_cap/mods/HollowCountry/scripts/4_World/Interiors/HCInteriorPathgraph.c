// A1: pathgraph update after a batch of interior props.
// Vanilla precedent for objects that appear at runtime: TentBase.c:797,
// BaseBuildingBase.c:814 and FireplaceBase.c:1783 each call
//   g_Game.GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(g_Game.UpdatePathgraphRegionByObject, 100, false, this)
// (CGame.UpdatePathgraphRegionByObject, 3_Game/Global/Game.c:1293, null-checks the
// object and updates the region of its clipping radius). The spawn flag
// ECE_UPDATEPATHGRAPH alone is not observed to rebuild the region, so the same
// short deferred call is made once per prop this module created. No queue is
// retained and no world scan is made. Offline tests prove neither the rebuild
// nor the infected routing around props; that needs a local DayZDiag run.
class HCInteriorPathgraph
{
    // A layout places at most 5 props (HCInteriorsModule.m_PropLimit); the cap is a backstop.
    static const int MAX_OBJECTS = 800;
    static const int DELAY_MS = 100;

    // Returns how many deferred updates were queued. Call only after the whole
    // batch was placed, oriented and recorded; never for a rolled-back layout.
    static int Schedule(array<Object> placed)
    {
        if (!placed || !GetGame() || !GetGame().IsServer()) return 0;
        int count = Math.Min(placed.Count(), MAX_OBJECTS);
        int scheduled = 0;
        int index = 0;
        while (index < count)
        {
            Object placedObject = placed[index];
            index++;
            if (!placedObject) continue;
            GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(GetGame().UpdatePathgraphRegionByObject, DELAY_MS, false, placedObject);
            scheduled++;
        }
        Print("[HC Interiors] pathgraph update queued for " + scheduled.ToString() + " of " + placed.Count().ToString() + " placed prop(s)");
        return scheduled;
    }
}
