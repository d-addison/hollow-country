class HCScanUser
{
    int Step()
    {
        int layer = ObjIntersectFire;
        int input = UAMapToggle;
        int kind = CT_INT;
        string folder = EXPANSION_LOADOUT_FOLDER;
        return layer + input + kind + FLT_MAX;
    }
}
