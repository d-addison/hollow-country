// LC-T415 / EXP-L9, EXP-L4. Installed snapshot evidence:
// 3_Game/Entities/EntityAI.c:882/885 hierarchy; Object.c:1219 IsRuined.
// 3_Game/Entities/Object.c:287/467 position/type; 1_Core/proto/EnConvert.c:210
// vector.DistanceSq; 1_Core/proto/EnDebug.c:96 Print.
// Existing Loot/HCSearchNativeSupply.c:297 has ONLY Transfer(entry, PlayerBase).
// At task start there was no Transfer(entry, EntityAI, actorId). No inventory
// move, cache creation, fake journal success or gate-verdict bypass is authored.
// Unknown/modded lock classifications remain ineligible, even with preference on.
class HCCampTheft
{
    static bool Due(int now, int last)
    {
        return now > 0 && (last == 0 || (now >= last && now - last >= 259200));
    }

    static bool Candidate(ItemBase container, HCCampRecord camp, int now, bool unattended, bool observerClear)
    {
        if (!container || !camp || !unattended || !observerClear || !Due(now, camp.LastTheft)) { return false; }
        if (container.GetType() != "WoodenCrate" || container.IsRuined() || container.GetHierarchyParent() || container.GetHierarchyRootPlayer()) { return false; }
        if (vector.DistanceSq(container.GetPosition(), camp.Position) > 144) { return false; }
        // Even vanilla classification cannot authorize an unjournaled transfer.
        return false;
    }

    static void Admission()
    {
        Print("[HollowCountry] V2 camps theft inactive: non-player journal Transfer overload absent; no items moved; EXP-L9 unverified");
    }
}
