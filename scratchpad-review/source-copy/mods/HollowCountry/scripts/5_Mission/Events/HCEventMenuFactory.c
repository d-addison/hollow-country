modded class MissionBase
{
    override UIScriptedMenu CreateScriptedMenu(int id)
    {
        if (id == HCEventWire.MENU_EVENTS)
        {
            UIScriptedMenu menu = new HCEventMenu;
            menu.SetID(id);
            return menu;
        }
        return super.CreateScriptedMenu(id);
    }
}
