class HCRecordBase
{
    int Id;
}

class HCRecord : HCRecordBase
{
    int Until;
}

class HCProbe
{
    int Read(HCRecord record)
    {
        return record.Expires;
    }
}
