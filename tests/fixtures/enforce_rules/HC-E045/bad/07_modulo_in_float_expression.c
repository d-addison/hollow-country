class HCProbeSpot
{
    float Radius(int attempt, float minRadius, float maxRadius)
    {
        float radius = minRadius + (maxRadius - minRadius) * (attempt % 4) / 3;
        return radius;
    }
}
