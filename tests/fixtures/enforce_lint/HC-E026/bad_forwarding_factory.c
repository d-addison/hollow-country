class HCThing {}

class HCFactory
{
    static array<float> Make() { return new array<float>; }
    static array<float> Local() { array<float> values = new array<float>; return values; }
    static array<float> Forward() { return Local(); }
    static HCThing Object() { return new HCThing; }
    static array<float> Borrow() { return Saved; }
    static array<float> Saved;
}
class HCUse
{
    void Check(array<float> values) {}
    void CheckThing(HCThing thing) {}
    void Run()
    {
        Check(HCFactory.Forward());
    }
}
