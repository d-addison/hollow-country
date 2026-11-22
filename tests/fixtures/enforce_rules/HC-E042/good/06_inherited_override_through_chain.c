class HCRootModule
{
    void OnStop(int reason)
    {
    }
}

class HCMidModule : HCRootModule
{
}

class HCLeafModule : HCMidModule
{
    override void OnStop(int reason)
    {
    }
}
