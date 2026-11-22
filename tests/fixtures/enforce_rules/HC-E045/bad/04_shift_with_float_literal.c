class HCProbe
{
    float Scale(int value)
    {
        float scaled = (value << 2) * 0.5;
        return scaled;
    }
}
