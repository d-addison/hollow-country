class HCStore
{
    ref array<Man> m_Men;
    ref array<Man> Men() { return m_Men; }
    static array<Man> All() { return null; }
}

modded class HCStore
{
    void Extra() {}
}

class HCUse
{
    ref HCStore m_Store;
    void Run()
    {
        foreach (Man man : HCStore.All()) { Print(man); }
    }
}
