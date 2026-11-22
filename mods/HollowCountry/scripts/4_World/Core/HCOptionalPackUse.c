// Native scripts-1.30.164289: AnimalBase is a 4_World class with inherited
// EntityAI.EEInit (3_Game/Entities/EntityAI.c:905).
// Object.IsKindOf (3_Game/Entities/Object.c:511) avoids an optional-class dependency.
// Count the first real sighting per feature, never the startup config probe.
// The bicycle_seen sighting was retired with DayZ-Bicycle (owner decision 2026-11-22).
modded class HCModuleReadiness
{
    static bool HCOptionalAnimalSeen;
}

modded class AnimalBase
{
    override void EEInit()
    {
        super.EEInit();
        if (!GetGame() || !GetGame().IsServer()) { return; }
        if (HCModuleReadiness.HCOptionalAnimalSeen) { return; }
        if (IsKindOf("Animal_Otter"))
        {
            HCModuleReadiness.HCOptionalAnimalSeen = true;
            HCModuleReadiness.HCUse("OptionalPacks", "animal_seen");
        }
    }
}
