class HCProbeSpot
{
    float Radius(int attempt, float minRadius, float maxRadius)
    {
        int ring = attempt % 4;
        float radius = minRadius + (maxRadius - minRadius) * ring / 3.0;
        Print("ring 50% done");
        return radius;
    }
}
