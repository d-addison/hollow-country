// #147: physical discovery, shared world memory, no live quest/marker delivery.
// HCWorld feeds HCLeadModule/HCRadioChatter with its existing delay and caps.
// Native scripts-1.30.164289: 1_Core/proto/EnScript.c:94 Cast;
// 3_Game/Entities/Object.c:215 IsPendingDeletion, :1219 IsRuined;
// 3_Game/Entities/EntityAI.c:885 GetHierarchyParent, :3409 GetCompEM;
// 4_World/Entities/ItemBase/Grenade_Base.c:74 IsPinned;
// 4_World/Entities/Grenade_Base/SmokeGrenadeBase.c:158 Unpin (native Activate
// lifecycle and replicated smoke), :168 OnActivateFinished;
// 3_Game/tools/Component/ComponentEnergyManager.c:768 CanWork.
// Caller owns server/observer checks immediately before HCSmoke. Never create,
// move, refuel or refill a grenade; native energy/lifetime consumes real stock.
class HCSituationSignals
{
    static bool HCPublish(vector position)
    {
        HCWorldModule world = HCWorldModule.Get();
        if (!world) { return false; }
        string place = world.NearestPlace(position);
        if (place == "") { return false; }
        // A real party has stopped/met threats here. Do not claim shots, deaths
        // or a rescue from a route request. Existing wording describes traces.
        return world.AddFact("scene_started", place, 0);
    }

    static bool HCSmoke(Object candidate)
    {
        SmokeGrenadeBase smoke = SmokeGrenadeBase.Cast(candidate);
        if (!smoke || smoke.IsPendingDeletion() || smoke.IsRuined()) { return false; }
        if (smoke.GetHierarchyParent() || !smoke.IsPinned()) { return false; }
        if (!smoke.GetCompEM() || !smoke.GetCompEM().CanWork()) { return false; }
        smoke.Unpin();
        return true;
    }
}
