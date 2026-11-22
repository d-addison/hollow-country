// 5898e1e8: HCXGrudge lost Group (GroupId remained); the reader was not updated.
class HCXGrudge
{
    int GroupId;
    int Until;
}

class HCXDefence
{
    ref array<ref HCXGrudge> m_Grudges = new array<ref HCXGrudge>;

    bool Matches(int actorGroupId)
    {
        foreach (HCXGrudge grudge : m_Grudges)
        {
            if (grudge.Group != null) { return true; }
        }
        return false;
    }
}
