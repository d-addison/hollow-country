class HCRecordBase
{
    int Id;

    bool Expired()
    {
        return false;
    }
}

class HCRecord : HCRecordBase
{
}

class HCProbe
{
    bool Read(HCRecord record)
    {
        return record.Id > 0 && record.Expired();
    }
}
