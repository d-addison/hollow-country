class HCScanBase
{
    void OnDone() {}
}

class HCScanUser : HCScanBase
{
    void Step(ScriptCaller caller)
    {
        caller.Register(OnDone);
    }
}
