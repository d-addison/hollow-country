// Native scripts-1.30.164289: AnimalBase, CarScript and ItemBase are
// 4_World classes with inherited EntityAI.EEInit (3_Game/Entities/EntityAI.c:905).
// Object.IsKindOf (3_Game/Entities/Object.c:511) avoids an optional-class dependency.
// Count actual entity initialization, never the startup config probe.
modded class AnimalBase
{
    override void EEInit()
    {
        super.EEInit();
        if (!GetGame() || !GetGame().IsServer()) { return; }
        if (IsKindOf("Animal_Otter")) { HCModuleReadiness.HCUse("OptionalPacks", "animal_seen"); }
    }
}

modded class CarScript
{
    override void EEInit()
    {
        super.EEInit();
        if (!GetGame() || !GetGame().IsServer()) { return; }
        if (IsKindOf("Old_Bike")) { HCModuleReadiness.HCUse("OptionalPacks", "bicycle_seen"); }
    }
}

modded class ItemBase
{
    override void EEInit()
    {
        super.EEInit();
        if (!GetGame() || !GetGame().IsServer()) { return; }
        if (IsKindOf("Old_Bike")) { HCModuleReadiness.HCUse("OptionalPacks", "bicycle_seen"); }
    }
}
