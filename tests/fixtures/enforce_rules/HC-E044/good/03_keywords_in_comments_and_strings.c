class HCProbe
{
    // foreach (Object owned : list) is a compile error
    void Run()
    {
        string text = "foreach (Object owned : list)";
        int owner = 0;
        int eventCount = 1;
        Print(text);
    }
}
