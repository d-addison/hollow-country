const int HC_GLOBAL_LIMIT = 9;
int g_HCGlobalCursor;

enum HCScanMode
{
    HC_MODE_IDLE,
    HC_MODE_BUSY = 5
}

int HCGlobalHelper() { return HC_GLOBAL_LIMIT; }

class HCScanUser
{
    int Step(HCScanMode mode)
    {
        g_HCGlobalCursor++;
        if (mode == HC_MODE_BUSY) { return HC_GLOBAL_LIMIT; }
        typename kind = HCScanUser;
        return HCGlobalHelper();
    }
}
