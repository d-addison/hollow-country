class HCProbe
{
    bool Has(int flags, int bit)
    {
        bool present = (flags & bit) != 0;
        return present;
    }
}
