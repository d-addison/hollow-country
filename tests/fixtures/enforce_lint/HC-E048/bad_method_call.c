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
        foreach (Man man : m_Store.Men()) { Print(man); }
    }
}
