class HCScanUser
{
    int Visited;

    int Step(int limit, array<int> values)
    {
        int first = 1, second = first + 1;
        int third, fourth;
        third = fourth = second;
        foreach (int index, int value : values)
        {
            Visited += value + index;
        }
        for (int slot = 0; slot < limit; slot++)
        {
            Visited += slot;
        }
        return first + second + third + fourth + limit;
    }
}
