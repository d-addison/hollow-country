class HCRecord
{
    int Until;
}

class HCProbe
{
    void Run(HCRecord record)
    {
        record.Expires = 5;
    }
}
