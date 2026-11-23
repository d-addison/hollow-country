class HCStore
{
    ref array<Man> m_Men;
    ref array<Man> Men() { return m_Men; }
    static array<Man> All() { return null; }
}

class HCUse
{
    ref HCStore m_Store;
    void Run()
    {
        array<Man> men = m_Store.Men();
        foreach (int i, Man man : men) { Print(HCStore.All()); }
    }
}
