class HCXGrudge
{
    int GroupId;
    int Until;
}

class HCProbe
{
    int Read(HCXGrudge grudge)
    {
        return grudge.GroupId + grudge.Until;
    }
}
