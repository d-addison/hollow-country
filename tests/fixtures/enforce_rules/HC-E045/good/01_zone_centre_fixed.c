class HCMissionBeacon
{
    static void ZoneCentre(string id, vector site, float radius, float fraction, out float zoneX, out float zoneZ, out float offset)
    {
        int hash = id.Hash();
        int lowBits = hash & 65535;
        int highShift = hash >> 16;
        int highBits = highShift & 32767;
        float angle = lowBits / 65536.0 * Math.PI2;
        float unit = highBits / 32767.0;
        offset = radius * fraction * (0.3 + 0.7 * unit);
        zoneX = site[0] + Math.Cos(angle) * offset;
        zoneZ = site[2] + Math.Sin(angle) * offset;
    }
}
