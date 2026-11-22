// Pristine and worn firearms never jam (owner 2026-11-20); damaged and worse keep the
// native chance. Weapon_Base.JamCheck (native 1.30.164289 Weapon_Base.c:366) is the only
// jam roll (WeaponManager.c:494) and no vanilla subclass overrides it, so one hook covers
// vanilla and modded firearms. The threshold is config, read the same on client and
// server so predicted and authoritative rolls agree:
// CfgHollowCountry >> Firearms >> noJamMaxHealthLevel (GameConstants.STATE_PRISTINE 0,
// STATE_WORN 1, STATE_DAMAGED 2, ...; -1 restores native jamming everywhere).
class HCWeaponJam
{
    protected static bool s_HCLoaded;
    protected static int s_HCMaxLevel = 1;

    static int MaxLevel()
    {
        if (!s_HCLoaded && GetGame())
        {
            s_HCLoaded = true;
            string path = "CfgHollowCountry Firearms noJamMaxHealthLevel";
            s_HCMaxLevel = HCConfigHelper.GetInt(path, s_HCMaxLevel);
        }
        return s_HCMaxLevel;
    }
}

modded class Weapon_Base
{
    override bool JamCheck(int muzzleIndex)
    {
        int hcHealthLevel = GetHealthLevel();
        if (hcHealthLevel >= 0 && hcHealthLevel <= HCWeaponJam.MaxLevel()) { return false; }
        return super.JamCheck(muzzleIndex);
    }
}
