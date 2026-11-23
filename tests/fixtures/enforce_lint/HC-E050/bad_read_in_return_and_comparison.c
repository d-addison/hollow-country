class HCScanBase
{
    int Visited;
}

class HCScanTactics : HCScanBase
{
    bool Matches(Object root)
    {
        if (root == Actor) { return true; }
        return Actor != null;
    }
}
