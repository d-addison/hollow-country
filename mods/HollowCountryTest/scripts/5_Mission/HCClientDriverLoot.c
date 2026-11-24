// Dev-only test addon (never shipped). Ground looting for the scripted client driver (kind loot).
// Plays like a player: it sees only the loose items the client has streamed in around it, walks to
// them on foot and takes each with the vanilla take action; full pockets drop one junk item first.
// Nothing is spawned, moved server-side or counted by the driver.
// Native scripts-1.30.164289 proofs:
//  find     3_Game/Global/Game.c:930 GetObjectsAtPosition3D (one query per pick, reused arrays);
//           3_Game/Entities/EntityAI.c:885 GetHierarchyParent (null = lying loose), :882
//           GetHierarchyRootPlayer (taken = now under this player, synced).
//  priority 4_World/Classes/Weapons/WeaponManager.c:91 CanAttachMagazine, :132 CanSwapMagazine (a
//           magazine the carried rifle takes); Magazine/AmmunitionPiles.c:2 Ammunition_Base;
//           ItemBase/Edible_Base.c:1 Edible_Base, Edible_Base/Bottle_Base.c:7 Bottle_Base,
//           Gear/Drinks/SodaCan_ColorBase.c:1; ItemBase/BandageDressing.c:1, Rag.c:1,
//           Edible_Base/DisinfectantSpray.c:1, Gear/Medical/DisinfectantAlcohol.c:1,
//           Edible_Base/TetracyclineAntibiotics.c:1, Edible_Base/CharcoalTablets.c:1,
//           Gear/Medical/Morphine.c:1, Gear/Medical/Epinephrine.c:1; Core/Inherited/
//           InventoryItem.c:1187 ItemMap.
//  take     4_World/Classes/UserActionsComponent/Actions/Interact/ActionTakeItem.c:33 ActionCondition
//           (CanAddEntityIntoInventory, CCTObject distance) through ActionBase.c:968 Can and
//           ActionManagerClient.c:804 PerformActionStart, as the F key does.
//  drop     4_World/Entities/ManBase/PlayerBase.c:9104 PredictiveDropEntity (the inventory's drop
//           request); only a junk item, never the driver's own kit or anything on the priority list.
// Bounded: one object query per pick (at most SCAN_CAP objects read), at most max_items takes and
// as many drops, a 64-entry skip map, one take attempt per item; nothing allocated after Begin.
class HCDriverLoot
{
    static const int L_PICK = 0;
    static const int L_WALK = 1;
    static const int L_TAKE = 2;
    static const int L_DROP = 3;
    static const int SCAN_CAP = 512;
    static const int MAX_SKIP = 64;
    static const int TIERS = 6;
    static const float REACH = 1.6;

    protected float m_Range;
    protected int m_Max;
    protected float m_Timeout;
    protected float m_Elapsed;
    protected int m_Phase;
    protected float m_PhaseAge;
    protected ItemBase m_Item;
    protected ItemBase m_Dropped;
    protected bool m_SawRunning;
    protected bool m_DropTried;
    protected int m_Taken;
    protected int m_DroppedCount;
    protected int m_Seen;
    protected int m_Skipped;
    protected int m_TierCount0;
    protected int m_TierCount1;
    protected int m_TierCount2;
    protected int m_TierCount3;
    protected int m_TierCount4;
    protected int m_TierCount5;
    protected ref ActionTarget m_Target;
    protected ref array<Object> m_Near = new array<Object>;
    protected ref array<CargoBase> m_NearCargo = new array<CargoBase>;
    protected ref array<EntityAI> m_Inventory = new array<EntityAI>;
    protected ref map<EntityAI, bool> m_Skip = new map<EntityAI, bool>;
    protected ref array<string> m_Medical = {"BandageDressing", "Rag", "DisinfectantSpray", "DisinfectantAlcohol", "TetracyclineAntibiotics", "CharcoalTablets", "Morphine", "Epinephrine"};
    // The test kit (soak_campaign GEAR_CARRIED and the gear preset): never junk, later steps use it.
    protected ref array<string> m_Kit = {"KitchenKnife", "CamoNet", "PersonalRadio", "Battery9V", "Mich2001Helmet", "TortillaBag", "UniversalLight", "Flashlight", "DuctTape", "Crowbar", "Wrench", "Pliers", "Paper", "Pen_ColorBase"};
    protected string m_Detail;

    string Detail()
    {
        return m_Detail;
    }

    void Begin(HCDriverStep step)
    {
        m_Range = Math.Clamp(step.range_m, 5.0, 80.0);
        m_Max = Math.Max(Math.Min(step.max_items, 10), 1);
        m_Timeout = Math.Max(step.timeout_s, 10.0);
        m_Elapsed = 0;
        m_Phase = HCDriverLoot.L_PICK;
        m_PhaseAge = 0;
        m_Item = null;
        m_Dropped = null;
        m_SawRunning = false;
        m_DropTried = false;
        m_Taken = 0;
        m_DroppedCount = 0;
        m_Seen = 0;
        m_Skipped = 0;
        m_TierCount0 = 0;
        m_TierCount1 = 0;
        m_TierCount2 = 0;
        m_TierCount3 = 0;
        m_TierCount4 = 0;
        m_TierCount5 = 0;
        m_Target = null;
        m_Skip.Clear();
        m_Detail = "";
    }

    protected string Tally()
    {
        string kinds = m_TierCount0.ToString() + "/" + m_TierCount1.ToString() + "/" + m_TierCount2.ToString() + "/" + m_TierCount3.ToString() + "/" + m_TierCount4.ToString() + "/" + m_TierCount5.ToString();
        return "taken=" + m_Taken.ToString() + " dropped=" + m_DroppedCount.ToString() + " seen=" + m_Seen.ToString() + " skipped=" + m_Skipped.ToString() + " mag/ammo/food/drink/med/map=" + kinds;
    }

    protected int End(PlayerBase player, HCDriverWalker walker, int code, string prefix)
    {
        walker.Release(player);
        if (player)
        {
            ActionManagerClient manager = ActionManagerClient.Cast(player.GetActionManager());
            if (manager) { manager.SetIgnoreAutomaticInputEnd(false); }
        }
        m_Detail = prefix + Tally();
        return code;
    }

    protected bool KindOfAny(ItemBase item, array<string> classes)
    {
        for (int index = 0; index < classes.Count(); index++)
        {
            if (item.IsKindOf(classes[index])) { return true; }
        }
        return false;
    }

    protected Weapon_Base CarriedWeapon(PlayerBase player)
    {
        Weapon_Base held = Weapon_Base.Cast(player.GetItemInHands());
        if (held) { return held; }
        m_Inventory.Clear();
        player.GetInventory().EnumerateInventory(InventoryTraversalType.PREORDER, m_Inventory);
        for (int index = 0; index < m_Inventory.Count(); index++)
        {
            Weapon_Base found = Weapon_Base.Cast(m_Inventory[index]);
            if (found) { return found; }
        }
        return null;
    }

    // 0 magazine the rifle takes, 1 ammunition, 2 food, 3 drink, 4 medical, 5 map; -1 not wanted.
    protected int Tier(PlayerBase player, ItemBase item, Weapon_Base weapon)
    {
        Magazine mag = Magazine.Cast(item);
        if (mag)
        {
            if (Ammunition_Base.Cast(item)) { return 1; }
            if (!weapon) { return -1; }
            WeaponManager manager = player.GetWeaponManager();
            if (!manager) { return -1; }
            if (manager.CanAttachMagazine(weapon, mag, false) || manager.CanSwapMagazine(weapon, mag, false)) { return 0; }
            return -1;
        }
        if (KindOfAny(item, m_Medical)) { return 4; }
        if (Bottle_Base.Cast(item) || SodaCan_ColorBase.Cast(item)) { return 3; }
        if (Edible_Base.Cast(item)) { return 2; }
        if (ItemMap.Cast(item)) { return 5; }
        return -1;
    }

    protected void CountTier(int tier)
    {
        if (tier == 0) { m_TierCount0++; }
        if (tier == 1) { m_TierCount1++; }
        if (tier == 2) { m_TierCount2++; }
        if (tier == 3) { m_TierCount3++; }
        if (tier == 4) { m_TierCount4++; }
        if (tier == 5) { m_TierCount5++; }
    }

    protected void Skip(EntityAI item)
    {
        m_Skipped++;
        if (m_Skip.Count() >= HCDriverLoot.MAX_SKIP) { m_Skip.Clear(); }
        if (item) { m_Skip.Set(item, true); }
    }

    // Best loose item in range: lowest tier first, then nearest; null when nothing is wanted.
    protected ItemBase Pick(PlayerBase player, out int bestTier)
    {
        Weapon_Base weapon = CarriedWeapon(player);
        m_Near.Clear();
        m_NearCargo.Clear();
        GetGame().GetObjectsAtPosition3D(player.GetPosition(), m_Range, m_Near, m_NearCargo);
        vector origin = player.GetPosition();
        ItemBase best;
        float bestScore = 1000000;
        bestTier = -1;
        int count = Math.Min(m_Near.Count(), HCDriverLoot.SCAN_CAP);
        for (int index = 0; index < count; index++)
        {
            ItemBase candidate = ItemBase.Cast(m_Near[index]);
            if (!candidate || candidate.IsPendingDeletion() || candidate.IsRuined()) { continue; }
            if (candidate.GetHierarchyParent() || m_Skip.Contains(candidate)) { continue; }
            vector at = candidate.GetPosition();
            // Another floor of a building is not reachable by a straight walk.
            if (Math.AbsFloat(at[1] - origin[1]) > 2.5) { continue; }
            int tier = Tier(player, candidate, weapon);
            if (tier < 0) { continue; }
            float score = tier * 1000 + vector.Distance(origin, at);
            if (score < bestScore)
            {
                bestScore = score;
                best = candidate;
                bestTier = tier;
            }
        }
        return best;
    }

    // One carried item that is neither kit nor wanted, lying in a cargo (never worn, held or attached).
    protected ItemBase Junk(PlayerBase player)
    {
        m_Inventory.Clear();
        player.GetInventory().EnumerateInventory(InventoryTraversalType.PREORDER, m_Inventory);
        for (int index = 0; index < m_Inventory.Count(); index++)
        {
            ItemBase item = ItemBase.Cast(m_Inventory[index]);
            if (!item || item.IsPendingDeletion() || item == player.GetItemInHands()) { continue; }
            if (!item.GetInventory() || item.GetInventory().IsAttachment()) { continue; }
            if (Magazine.Cast(item) || Weapon_Base.Cast(item) || Clothing.Cast(item) || Edible_Base.Cast(item) || ItemMap.Cast(item)) { continue; }
            if (KindOfAny(item, m_Kit) || KindOfAny(item, m_Medical)) { continue; }
            return item;
        }
        return null;
    }

    int Tick(PlayerBase player, float dt, HCDriverWalker walker)
    {
        if (!player || !player.IsAlive() || player.IsUnconscious()) { return End(player, walker, HCDriverResult.REFUSED, "player-unavailable "); }
        if (player.IsRestrained()) { return End(player, walker, HCDriverResult.REFUSED, "restrained "); }
        ActionManagerClient manager = ActionManagerClient.Cast(player.GetActionManager());
        if (!manager) { return End(player, walker, HCDriverResult.UNSUPPORTED, "no-client-action-manager "); }
        m_Elapsed = m_Elapsed + dt;
        m_PhaseAge = m_PhaseAge + dt;
        if (m_Elapsed > m_Timeout)
        {
            if (m_Taken > 0) { return End(player, walker, HCDriverResult.OK, ""); }
            return End(player, walker, HCDriverResult.TIMEOUT, "nothing-taken ");
        }
        if (m_Phase == HCDriverLoot.L_PICK)
        {
            if (m_Taken >= m_Max) { return End(player, walker, HCDriverResult.OK, ""); }
            int tier;
            m_Item = Pick(player, tier);
            if (!m_Item)
            {
                if (m_Taken > 0) { return End(player, walker, HCDriverResult.OK, ""); }
                if (m_Seen > 0) { return End(player, walker, HCDriverResult.REFUSED, "could-not-take "); }
                return End(player, walker, HCDriverResult.REFUSED, "no-loot-within-" + Math.Round(m_Range).ToString() + "m ");
            }
            m_Seen++;
            CountTier(tier);
            m_DropTried = false;
            m_Phase = HCDriverLoot.L_WALK;
            m_PhaseAge = 0;
            vector at = m_Item.GetPosition();
            walker.Begin(at[0], at[2], "walk", 1.2, 60);
        }
        if (!m_Item || m_Item.IsPendingDeletion())
        {
            walker.Release(player);
            m_Phase = HCDriverLoot.L_PICK;
            return HCDriverResult.RUNNING;
        }
        if (m_Phase == HCDriverLoot.L_WALK)
        {
            if (vector.Distance(player.GetPosition(), m_Item.GetPosition()) > HCDriverLoot.REACH)
            {
                int walked = walker.Update(player, dt);
                if (walked == HCDriverResult.RUNNING) { return walked; }
                if (walked != HCDriverResult.OK)
                {
                    Skip(m_Item);
                    m_Phase = HCDriverLoot.L_PICK;
                    return HCDriverResult.RUNNING;
                }
            }
            walker.Release(player);
            if (manager.GetRunningAction()) { return HCDriverResult.RUNNING; }
            ActionBase take = ActionManagerBase.GetAction(ActionTakeItem);
            m_Target = new ActionTarget(m_Item, null, -1, vector.Zero, -1.0);
            if (!take) { return End(player, walker, HCDriverResult.UNSUPPORTED, "no-take-action "); }
            if (!take.Can(player, m_Target, null))
            {
                // Pockets full: drop one junk item once, then try the same item again.
                if (!m_DropTried)
                {
                    m_DropTried = true;
                    m_Dropped = Junk(player);
                    if (m_Dropped && m_DroppedCount < m_Max && player.PredictiveDropEntity(m_Dropped))
                    {
                        m_Phase = HCDriverLoot.L_DROP;
                        m_PhaseAge = 0;
                        return HCDriverResult.RUNNING;
                    }
                }
                Skip(m_Item);
                m_Phase = HCDriverLoot.L_PICK;
                return HCDriverResult.RUNNING;
            }
            manager.SetIgnoreAutomaticInputEnd(true);
            manager.PerformActionStart(take, m_Target, null);
            m_SawRunning = false;
            m_Phase = HCDriverLoot.L_TAKE;
            m_PhaseAge = 0;
            return HCDriverResult.RUNNING;
        }
        if (m_Phase == HCDriverLoot.L_DROP)
        {
            if (m_Dropped && m_Dropped.GetHierarchyRootPlayer() == player && m_PhaseAge < 3.0) { return HCDriverResult.RUNNING; }
            if (m_Dropped && m_Dropped.GetHierarchyRootPlayer() != player) { m_DroppedCount++; }
            m_Dropped = null;
            m_Phase = HCDriverLoot.L_WALK;
            m_PhaseAge = 0;
            return HCDriverResult.RUNNING;
        }
        // L_TAKE: the take is confirmed only by the synced hierarchy (the item is now under the player).
        if (manager.GetRunningAction())
        {
            m_SawRunning = true;
            if (m_PhaseAge < 10.0) { return HCDriverResult.RUNNING; }
        }
        if (m_Item.GetHierarchyRootPlayer() == player)
        {
            manager.SetIgnoreAutomaticInputEnd(false);
            m_Taken++;
            m_Phase = HCDriverLoot.L_PICK;
            return HCDriverResult.RUNNING;
        }
        if (m_PhaseAge < 3.0) { return HCDriverResult.RUNNING; }
        manager.SetIgnoreAutomaticInputEnd(false);
        Skip(m_Item);
        m_Phase = HCDriverLoot.L_PICK;
        return HCDriverResult.RUNNING;
    }
}
