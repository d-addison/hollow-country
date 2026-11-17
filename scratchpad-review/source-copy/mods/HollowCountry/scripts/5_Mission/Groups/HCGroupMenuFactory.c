// Follow native MissionBase dispatch; preserve every other mod/native menu.
modded class MissionBase
{
    override UIScriptedMenu CreateScriptedMenu(int id)
    {
        if (id == HCGroupProtocol.MENU_MAP)
        {
            UIScriptedMenu menu = new HCGroupMapMenu;
            menu.SetID(id);
            return menu;
        }
        return super.CreateScriptedMenu(id);
    }
}
