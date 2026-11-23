class HCScanLimits
{
    static const int HC_SCAN_LIMIT = 8;
}

class HCScanUser : HCScanLimits
{
    int Limit()
    {
        return HC_SCAN_LIMIT + HC_SCAN_OLD_LIMIT;
    }
}
