class HCFixtureRowJson
{
    void Row(string text) {}

    void Emit(int i, string id, string y, int w, int s, int h, int t, int b, int o)
    {
        Row("{\"i\":" + i.ToString() + ",\"id\":\"" + id + "\",\"y\":[" + y + "],\"w\":" + w.ToString() + ",\"s\":" + s.ToString() + ",\"h\":" + h.ToString() + ",\"n\":[" + t.ToString() + "," + b.ToString() + "," + o.ToString() + "]}");
    }
}
