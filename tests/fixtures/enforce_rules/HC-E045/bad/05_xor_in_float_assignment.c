class HCProbe
{
    void Run(int seed)
    {
        float ratio;
        ratio = (seed ^ 7) / 10.0;
        Print(ratio);
    }
}
