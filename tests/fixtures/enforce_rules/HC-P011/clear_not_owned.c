// Clear: the collection is a parameter, not a collection the module owns.
class HCFixParameterModule
{
    void Move(array<Object> props)
    {
        foreach (Object prop : props)
        {
            prop.SetPosition("0 0 0");
        }
    }

    void OnTick()
    {
        array<Object> local = new array<Object>;
        Move(local);
    }
}
