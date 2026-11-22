// Clear: a player roster is bounded by the server slots.
class HCFixRosterModule
{
    protected ref array<Man> m_Players = new array<Man>;

    void OnTick()
    {
        foreach (Man person : m_Players)
        {
            person.SetPosition(person.GetPosition());
        }
    }
}
