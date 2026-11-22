class HCActorBase
{
}

class HCActorChild : HCActorBase
{
}

class HCReactBase
{
    void React(HCActorBase actor)
    {
    }

    protected int Score()
    {
        return 0;
    }
}

class HCReactChild : HCReactBase
{
    override void React(HCActorChild actor)
    {
    }

    override bool Score()
    {
        return true;
    }
}
