// W5 #128. Tick bound: zero work; native consumption and environment callbacks
// do constant work for that player. Disabled path returns before allocation.
// Installed scripts-1.30.164289 native evidence:
// 4_World/Entities/ItemBase/Edible_Base.c:95-109 Consume -> OnConsume,
// :531 GetFoodStageType; 4_World/Entities/ItemBase.c:2600 GetFoodStage;
// 3_Game/Entities/EntityAI.c:2442 GetTemperature; Object.c:517 IsAlive;
// 4_World/Classes/Environment/Environment.c:92 m_Player, :96 m_PlayerHeat,
// :1253 ProcessHeatComfort, :1329 movement heat /100 before native smoothing
// and clamping. Only that calculation sees +5 heat (= +0.05 comfort), not
// drying, movement, stamina or inventory. Native stomach warming also remains.
// Shared runtime evidence is in HCSurvivalPolicy.c; EnDebug.c:96 Print.
// No persistence/sync fields; server's native heat stat owns replication.
class HCMealBuffsModule : HCModule
{
    static bool HCActive;
    static int HCGeneration;

    override string GetName() { return "MealBuffs"; }
    override bool IsEnabled(HCSettings settings) { return settings && settings.EnableMealBuffs; }

    override void OnStart(HCSettings settings)
    {
        Print(HCV2Admission.Line("MealBuffs", settings.EnableMealBuffs, "W5-128", false));
        if (!settings.EnableMealBuffs || !HCSurvivalRuntime.HCIsServer()) { return; }
        HCGeneration = HCGeneration + 1;
        HCActive = true;
    }

    override void OnStop() { HCActive = false; }
}

modded class PlayerBase
{
    protected int m_HCMealExpires;
    protected int m_HCMealGeneration;

    float HCMealHeatBonus()
    {
        if (!HCMealBuffsModule.HCActive) { return 0; }
        if (!HCSurvivalRuntime.HCIsServer() || !IsAlive()) { return 0; }
        if (m_HCMealGeneration != HCMealBuffsModule.HCGeneration) { return 0; }
        return HCSurvivalPolicy.MealHeat(HCSurvivalRuntime.HCSessionSeconds(), m_HCMealExpires);
    }

    void HCGrantWarmMeal(int stage, float temperature, float amount)
    {
        if (!HCMealBuffsModule.HCActive) { return; }
        if (!HCSurvivalRuntime.HCIsServer() || !IsAlive()) { return; }
        int expires = HCSurvivalPolicy.MealExpiry(true, stage, temperature, amount, HCSurvivalRuntime.HCSessionSeconds());
        if (expires == 0) { return; }
        bool fresh = HCMealHeatBonus() == 0;
        m_HCMealExpires = expires;
        m_HCMealGeneration = HCMealBuffsModule.HCGeneration;
        if (fresh) { Print("[HC MealBuffs] granted duration=600 heat=0.05 refresh-only; runtime acceptance pending"); }
    }
}

modded class Edible_Base
{
    override void OnConsume(float amount, PlayerBase consumer)
    {
        // Keep native temperature damage and all quantity/stomach behaviour.
        super.OnConsume(amount, consumer);
        if (!HCMealBuffsModule.HCActive) { return; }
        if (!HCSurvivalRuntime.HCIsServer() || !consumer) { return; }
        if (!GetFoodStage()) { return; }
        consumer.HCGrantWarmMeal(GetFoodStageType(), GetTemperature(), amount);
    }
}

modded class Environment
{
    override protected void ProcessHeatComfort()
    {
        if (!HCMealBuffsModule.HCActive)
        {
            super.ProcessHeatComfort();
            return;
        }
        float savedHeat = m_PlayerHeat;
        if (m_Player) { m_PlayerHeat = savedHeat + m_Player.HCMealHeatBonus() * 100; }
        super.ProcessHeatComfort();
        m_PlayerHeat = savedHeat;
    }
}

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        Register(new HCMealBuffsModule);
    }
}
