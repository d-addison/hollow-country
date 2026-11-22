class HCNotes
{
    int WaitCount;

    // void Wait() is reserved by the engine.
    void Describe()
    {
        string text = "void Wait() {}";
        WaitCount++;
    }
}
