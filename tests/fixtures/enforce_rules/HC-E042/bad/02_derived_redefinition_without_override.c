class HCModuleBase
{
    void OnStart(string reason)
    {
    }
}

class HCSpawnModule : HCModuleBase
{
    void OnStart(string reason)
    {
        Print(reason);
    }
}
