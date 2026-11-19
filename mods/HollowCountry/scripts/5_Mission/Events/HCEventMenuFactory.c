// HC-38: retire only the reserved quest menu ID; preserve native dispatch.
// Native scripts-1.30.164289: 5_Mission/mission/missionBase.c:198
// CreateScriptedMenu(int id). No scripted quest menu is constructed.
modded class MissionBase
{
    override UIScriptedMenu CreateScriptedMenu(int id)
    {
        if (id == HCEventWire.MENU_EVENTS) { return null; }
        return super.CreateScriptedMenu(id);
    }
}
