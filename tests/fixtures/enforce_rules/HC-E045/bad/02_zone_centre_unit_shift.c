class HCMissionBeacon
{
    static float Unit(int hash)
    {
        float unit = ((hash >> 16) & 32767) / 32767.0;
        return unit;
    }
}
