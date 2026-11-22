// HCMissionBeacon.ZoneCentre before a33d66f6.
class HCMissionBeacon
{
    static void ZoneCentre(string id, vector site, float radius, float fraction, out float zoneX, out float zoneZ, out float offset)
    {
        int hash = id.Hash();
        float angle = (hash & 65535) / 65536.0 * Math.PI2;
        offset = radius * fraction * angle;
    }
}
