class HCScanUser
{
    void Step(Object target)
    {
        PackedHelper(target);
        PackedClass.Run(target);
        PackedOther holder = new PackedOther();
        ref array<PackedItem> items = new array<PackedItem>;
        map<string, PackedItem> byName;
        items.Insert(PackedItem.Cast(target));
    }
}
