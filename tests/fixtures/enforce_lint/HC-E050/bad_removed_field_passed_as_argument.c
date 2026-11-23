class HCScanBase
{
    int Visited;
    void Take(int value) { Visited = value; }
}

class HCScanTactics : HCScanBase
{
    void Step()
    {
        Take(Budget);
    }
}
