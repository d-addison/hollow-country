class HCProbe
{
    int Pack(int high, int low)
    {
        int packed = (high << 8) | low;
        int mask = packed & 255;
        return mask ^ 3;
    }
}
