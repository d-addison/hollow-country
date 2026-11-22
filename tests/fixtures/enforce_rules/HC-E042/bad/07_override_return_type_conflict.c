class HCCountBase
{
    int Count()
    {
        return 0;
    }
}

class HCCountChild : HCCountBase
{
    override string Count()
    {
        return "";
    }
}
