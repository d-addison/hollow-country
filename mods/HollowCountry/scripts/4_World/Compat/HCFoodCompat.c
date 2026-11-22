// #232 variety packs: food and cooking pack compatibility. Vanilla classes only; the
// packs are detected at runtime by a config class, so a missing pack changes nothing.
// Native scripts-1.30.164289: 3_Game/Entities/EntityAI.c:2270 InitTemperature
// (protected; reads GetMission().GetWorldData() and, when UseConfigInitTemperature()
// is true, EntityAIType.m_VarTemperatureInit), :2265 UseConfigInitTemperature, :935
// (called from the entity init when CanHaveTemperature() on a server),
// 4_World/Classes/Cooking/Cooking.c:117 CookWithEquipment, 4_World/Entities/ItemBase
// Edible_Base.c (no InitTemperature override in 1.30), 3_Game/Global/Game.c
// ConfigIsExisting/IsServer/IsMultiplayer, EnString.c Contains/IndexOf/Substring.
// The food pack's items, boxes and bundles all derive from vanilla item classes with a
// "_DON" tag in the type name; the guard covers both Edible_Base and Inventory_Base.
class HCFoodCompat
{
    // 0 unknown, 1 present, 2 absent. A pack cannot appear mid-session.
    protected static int s_Present;
    protected static int s_RefusalsSeen;

    static bool Present()
    {
        if (s_Present == 0)
        {
            s_Present = 2;
            if (GetGame() && GetGame().ConfigIsExisting("CfgVehicles Foodbox_DON_Cans")) { s_Present = 1; }
        }
        return s_Present == 1;
    }

    // The 1.30 InitTemperature contract: a mission with world data, and a typed
    // entity config when the config temperature is used. Returns the reason the
    // contract fails (no_mission, no_world_data, no_entity_type) or "" when it holds.
    static string ContractFailure(EntityAI item)
    {
        if (!GetGame() || !GetGame().GetMission()) { return "no_mission"; }
        if (!GetGame().GetMission().GetWorldData()) { return "no_world_data"; }
        if (item && item.UseConfigInitTemperature() && !EntityAIType.Cast(item.GetEntityType())) { return "no_entity_type"; }
        return "";
    }

    // True for pack food entities: the pack is present and the type carries the tag.
    static bool Applies(EntityAI item)
    {
        if (!Present() || !item) { return false; }
        return item.GetType().IndexOf("_DON") >= 0;
    }

    // Checks the contract for a pack entity; a failure is counted and reported once.
    static bool Admit(EntityAI item)
    {
        string reason = ContractFailure(item);
        if (reason == "") { return true; }
        Refused(reason);
        return false;
    }

    // Pass-through evidence: pack food went through the guard and the contract held.
    static void Guarded()
    {
        HCModuleReadiness.HCUse("FoodCompat", "food_compat_guard");
    }

    // A refusal skipped the temperature init instead of dereferencing a null. The
    // counter registers on first refusal (a fault counter is not expected in normal
    // play); the first refusal of each reason prints one line.
    static void Refused(string reason)
    {
        HCModuleReadiness.HCUse("FoodCompat", "food_compat_refused");
        int bit = 0;
        if (reason == "no_mission") { bit = 1; }
        if (reason == "no_world_data") { bit = 2; }
        if (reason == "no_entity_type") { bit = 4; }
        if (bit == 0 || (s_RefusalsSeen & bit) != 0) { return; }
        s_RefusalsSeen = s_RefusalsSeen | bit;
        Print("[HC Food] food_compat_refused reason=" + reason);
    }
}

class HCFoodCompatModule : HCModule
{
    protected bool m_Started;
    protected ref HCOperationalStatus m_Operational = new HCOperationalStatus;

    override string GetName() { return "FoodCompat"; }

    override HCOperationalStatus HCGetOperationalStatus()
    {
        HCModuleReadiness.HCDerive(m_Operational, m_Started, "", "", "food_compat_started");
        return m_Operational;
    }

    // Enabled only with the food pack present; the release audit then expects the counter.
    override bool IsEnabled(HCSettings settings)
    {
        return HCFoodCompat.Present();
    }

    override void RegisterUses()
    {
        HCModuleReadiness.HCRegisterUse("FoodCompat", "food_compat_guard");
    }

    override void OnStart(HCSettings settings)
    {
        if (!m_Started && HCFoodCompat.Present() && GetGame() && GetGame().IsServer())
        {
            m_Started = true;
            HCReached.Mark("food_compat.started");
        }
    }

    override void OnStop() { m_Started = false; }
}

// Cooking pack probe and counters. A separate module so the cooking pack alone enables
// its own audit rows (the food pack need not be present).
class HCCookingCompat
{
    // 0 unknown, 1 present, 2 absent. A pack cannot appear mid-session.
    protected static int s_Present;

    static bool Present()
    {
        if (s_Present == 0)
        {
            s_Present = 2;
            if (GetGame() && GetGame().ConfigIsExisting("CfgVehicles CookZ_EmptyCan")) { s_Present = 1; }
        }
        return s_Present == 1;
    }

    // A pack dish type: pack prefix, not an opened-can leftover. Type names are short.
    static bool IsDishType(string typeName)
    {
        return typeName.IndexOf("CookZ_") == 0 && typeName.IndexOf("_Opened") < 0;
    }

    // True when the pot cargo holds a finished pack dish (not an opened-can leftover).
    // Bounded by the cargo size of one pot.
    static bool HasDish(ItemBase pot)
    {
        if (!pot || !pot.GetInventory()) { return false; }
        CargoBase cargo = pot.GetInventory().GetCargo();
        if (!cargo) { return false; }
        int count = cargo.GetItemCount();
        for (int i = 0; i < count && i < 32; i++)
        {
            EntityAI entry = cargo.GetItem(i);
            if (!entry) { continue; }
            if (IsDishType(entry.GetType())) { return true; }
        }
        return false;
    }
}

class HCCookingCompatModule : HCModule
{
    protected bool m_Started;
    protected ref HCOperationalStatus m_Operational = new HCOperationalStatus;

    override string GetName() { return "CookingCompat"; }

    override HCOperationalStatus HCGetOperationalStatus()
    {
        HCModuleReadiness.HCDerive(m_Operational, m_Started, "", "", "cooking_compat_started");
        return m_Operational;
    }

    // Enabled only with the cooking pack present.
    override bool IsEnabled(HCSettings settings)
    {
        return HCCookingCompat.Present();
    }

    override void RegisterUses()
    {
        HCModuleReadiness.HCRegisterUse("CookingCompat", "cooking_dish_cooked");
    }

    override void OnStart(HCSettings settings)
    {
        if (!m_Started && HCCookingCompat.Present() && GetGame() && GetGame().IsServer())
        {
            m_Started = true;
            HCReached.Mark("cooking_compat.started");
        }
    }

    override void OnStop() { m_Started = false; }
}

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        Register(new HCFoodCompatModule);
        Register(new HCCookingCompatModule);
    }
}

// Pack food (items, loot boxes, bundles) runs the 1.30 temperature initialisation only
// when its contract holds; a refusal leaves the item at its default temperature (never
// a crash). Every other entity takes the unmodified vanilla path. EntityAI lives in
// 3_Game and cannot be modded from 4_World, so the two 4_World item roots the pack
// uses are covered: Edible_Base (food) and Inventory_Base (boxes and bundles).
modded class Edible_Base
{
    override protected void InitTemperature()
    {
        if (!HCFoodCompat.Applies(this))
        {
            super.InitTemperature();
            return;
        }
        if (!HCFoodCompat.Admit(this)) { return; }
        super.InitTemperature();
        HCFoodCompat.Guarded();
    }
}

modded class Inventory_Base
{
    override protected void InitTemperature()
    {
        if (!HCFoodCompat.Applies(this))
        {
            super.InitTemperature();
            return;
        }
        if (!HCFoodCompat.Admit(this)) { return; }
        super.InitTemperature();
        HCFoodCompat.Guarded();
    }
}

// Evidence that the cooking pack's dish path ran: a cooking pass that changed a
// stage and left a finished pack dish in the pot. Counts only; the result is unchanged.
// Needs HC loaded above the cooking pack (the pack's dish path does not call super).
modded class Cooking
{
    override int CookWithEquipment(ItemBase cooking_equipment, float cooking_time_coef = 1)
    {
        int result = super.CookWithEquipment(cooking_equipment, cooking_time_coef);
        if (result == 1 && HCCookingCompat.Present() && HCCookingCompat.HasDish(cooking_equipment))
        {
            HCModuleReadiness.HCUse("CookingCompat", "cooking_dish_cooked");
        }
        return result;
    }
}

// The cooking pack ships its config to clients with a custom RPC and applies it from
// any sender. A client must never replace the server copy (recipe switches, agent
// chances, dish temperature): a multiplayer server drops that RPC. 1638955238 is
// the pack's published RPC id (a protocol constant, not pack code). The pack handles
// the RPC after calling super, so this drop only takes effect when HC loads above the
// cooking pack. The counter registers on first refusal and has no activity row.
modded class PlayerBase
{
    override void OnRPC(PlayerIdentity sender, int rpc_type, ParamsReadContext ctx)
    {
        if (rpc_type == 1638955238 && GetGame() && GetGame().IsServer() && GetGame().IsMultiplayer())
        {
            if (HCCookingCompat.Present()) { HCModuleReadiness.HCUse("CookingCompat", "cooking_config_rpc_refused"); }
            return;
        }
        super.OnRPC(sender, rpc_type, ctx);
    }
}
