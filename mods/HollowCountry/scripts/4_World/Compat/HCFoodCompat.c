// #232 variety packs: food and cooking pack compatibility. Vanilla classes only; the
// packs are detected at runtime by a config class, so a missing pack changes nothing.
// Native scripts-1.30.164289: 3_Game/Entities/EntityAI.c:2270 InitTemperature
// (protected; reads GetMission().GetWorldData() and, when UseConfigInitTemperature()
// is true, EntityAIType.m_VarTemperatureInit), :2265 UseConfigInitTemperature,
// 4_World/Entities/ItemBase/Edible_Base.c (no InitTemperature override in 1.30),
// 3_Game/Global/Game.c ConfigIsExisting/IsServer/IsMultiplayer, EnString.c Contains.
// Pack food classes are Edible_Base children whose type names carry a "_DON" tag.
class HCFoodCompat
{
    // 0 unknown, 1 present, 2 absent. A pack cannot appear mid-session.
    protected static int s_Present;

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
    // entity config when the config temperature is used. Anything else is refused
    // rather than dereferenced.
    static bool ContractHolds(EntityAI item)
    {
        if (!item || !GetGame() || !GetGame().GetMission() || !GetGame().GetMission().GetWorldData()) { return false; }
        if (item.UseConfigInitTemperature() && !EntityAIType.Cast(item.GetEntityType())) { return false; }
        return true;
    }

    static void Guarded()
    {
        HCModuleReadiness.HCUse("FoodCompat", "food_compat_guard");
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

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        Register(new HCFoodCompatModule);
    }
}

// Pack food runs the 1.30 temperature initialisation only when its contract holds;
// a refusal leaves the item at its default temperature (never a crash). Other food
// and every non-pack item take the unmodified vanilla path.
modded class Edible_Base
{
    override protected void InitTemperature()
    {
        if (!HCFoodCompat.Present() || GetType().IndexOf("_DON") < 0)
        {
            super.InitTemperature();
            return;
        }
        if (!HCFoodCompat.ContractHolds(this))
        {
            HCFoodCompat.Guarded();
            return;
        }
        super.InitTemperature();
        HCFoodCompat.Guarded();
    }
}

// The cooking pack ships its config to clients with a custom RPC and applies it from
// any sender. A client must never replace the server copy (recipe switches, agent
// chances, dish temperature): a multiplayer server drops that RPC. 1638955238 is
// the pack's published RPC id (a protocol constant, not pack code).
modded class PlayerBase
{
    override void OnRPC(PlayerIdentity sender, int rpc_type, ParamsReadContext ctx)
    {
        if (rpc_type == 1638955238 && GetGame() && GetGame().IsServer() && GetGame().IsMultiplayer())
        {
            HCModuleReadiness.HCUse("FoodCompat", "cookz_config_rpc_refused");
            return;
        }
        super.OnRPC(sender, rpc_type, ctx);
    }
}
