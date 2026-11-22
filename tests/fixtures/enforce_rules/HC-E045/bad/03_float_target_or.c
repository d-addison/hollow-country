class HCProbe
{
    void Run(int flags)
    {
        float mask = flags | 4;
        Print(mask);
    }
}
