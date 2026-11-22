class HCReadBase
{
    void Read(out int value)
    {
        value = 0;
    }
}

class HCReadChild : HCReadBase
{
    override void Read(int value)
    {
    }
}
