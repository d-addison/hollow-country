class HCFixtureRowSteps
{
    void Emit(int i, string id, string y, int w, int s, int h, int t, int b, int o)
    {
        string row = "{\"i\":" + i.ToString() + ",\"id\":\"" + id + "\"";
        row = row + ",\"y\":[" + y + "],\"w\":" + w.ToString();
        row = row + ",\"s\":" + s.ToString() + ",\"h\":" + h.ToString();
        row = row + ",\"n\":[" + t.ToString() + "," + b.ToString() + "," + o.ToString() + "]}";
        Print(row);
    }
}
