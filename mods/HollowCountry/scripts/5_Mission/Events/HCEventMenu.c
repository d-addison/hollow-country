// HC-38: inert compatibility type. Old callers cannot build a quest layout.
class HCEventMenu : UIScriptedMenu
{
    override Widget Init()
    {
        return null;
    }
}
