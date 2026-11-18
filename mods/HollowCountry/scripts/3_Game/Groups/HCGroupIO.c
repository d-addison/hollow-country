// Bounded profile file IO shared by 4_World modules. It lives in 3_Game so
// every 4_World file sees it regardless of compile order (DayZ 021 boot:
// 'Bad type HCGroupJson' from Groups/HCDeathPin.c compiled before HCGroupStore.c).
class HCGroupIO
{
    static bool Read(string path, int limit, out string text)
    {
        FileHandle handle = OpenFile(path, FileMode.READ);
        if (!handle) return false;
        int count = ReadFile(handle, text, limit + 1);
        CloseFile(handle);
        return count > 0 && count <= limit && text.Length() > 0 && text.Length() <= limit;
    }

    static bool WriteNew(string path, string text, int limit)
    {
        if (FileExist(path)) return false;
        if (text.Length() < 1 || text.Length() > limit) return false;
        FileHandle handle = OpenFile(path, FileMode.WRITE);
        if (!handle) return false;
        FPrint(handle, text);
        CloseFile(handle);
        string actual;
        return HCGroupIO.Read(path, limit, actual) && actual == text;
    }
}

class HCGroupJson<Class T>
{
    static bool Load(string path, int limit, out T data)
    {
        string text;
        string error;
        return HCGroupIO.Read(path, limit, text) && JsonFileLoader<T>.LoadData(text, data, error);
    }

    static bool WriteNew(string path, T data, int limit)
    {
        string text;
        string error;
        return JsonFileLoader<T>.MakeData(data, text, error) && HCGroupIO.WriteNew(path, text, limit);
    }
}
