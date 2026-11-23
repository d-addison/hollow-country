class HCFixtureRowCall
{
    void Row(string text) {}

    void Emit(string a, string b, string c, string d, string e, string f, string g, string h, string i)
    {
        Row("a" + a + "b" + b + "c" + c + "d" + d + "e" + e + "f" + f + "g" + g + "h" + h + "i" + i);
    }
}
