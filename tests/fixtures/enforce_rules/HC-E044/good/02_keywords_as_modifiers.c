class HCProbe
{
    static const int LIMIT = 4;
    ref array<string> m_Names = new array<string>;
    autoptr array<int> m_Counts = new array<int>;

    override protected void Run(out int result, notnull Object target)
    {
        result = 0;
    }

    private static void Quiet()
    {
    }
}
