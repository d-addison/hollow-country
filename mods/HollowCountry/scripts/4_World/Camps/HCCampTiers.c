// LC-T412 / EXP-L7. Pure classification; no item/stat/permission outputs.
// Native snapshot scripts-1.30.164289: 1_Core/proto/EnDebug.c:96 Print
// (diagnostics live in the module); this policy calls no native methods.
class HCCampTiers
{
    static int Evaluate(bool hearth, bool shelter, bool storage, bool flag, bool food, bool kitchen, int walls, int lights, bool radio)
    {
        if (!hearth || !shelter || !storage) { return 0; }
        if (!flag || !food || !kitchen) { return 1; }
        if (walls < 3 || lights < 2 || !radio) { return 2; }
        return 3;
    }

    static int Decayed(int tier, int now, int lastLit)
    {
        if (now < lastLit || lastLit < 1) { return 0; }
        int steps = (now - lastLit) / 172800;
        if (steps >= tier) { return 0; }
        return tier - steps;
    }
}
