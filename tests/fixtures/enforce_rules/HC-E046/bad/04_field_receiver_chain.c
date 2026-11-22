class HCXGrudge
{
    int GroupId;
}

class HCHolder
{
    ref HCXGrudge m_Grudge;

    int Read()
    {
        return m_Grudge.Group;
    }
}
