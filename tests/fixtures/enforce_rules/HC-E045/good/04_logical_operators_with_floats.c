class HCProbe
{
    bool Near(float distance, bool a, bool b)
    {
        bool near = distance < 2.5 && (a || b);
        return near;
    }
}
