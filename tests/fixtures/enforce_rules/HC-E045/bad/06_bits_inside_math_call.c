class HCProbe
{
    float Wave(int hash)
    {
        return Math.Sin((hash & 255) * 0.1);
    }
}
