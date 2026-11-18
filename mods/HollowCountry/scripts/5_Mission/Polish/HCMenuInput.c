// Shared input handling for HC scripted menus (playtest 2026-11-18: the admin window let the
// mouse turn the character, and Escape did nothing). Uses the vanilla pattern from
// missionGameplay.c ShowChat/HideChat and the in-game menu: exclude the "menu" input group while
// open, release it with bForceSupress on close, and close on UAUIBack like MapMenu.Update.
class HCMenuInput
{
    static void Lock()
    {
        Mission mission = GetGame().GetMission();
        if (mission) { mission.AddActiveInputExcludes({"menu"}); }
    }

    static void Unlock()
    {
        Mission mission = GetGame().GetMission();
        if (mission) { mission.RemoveActiveInputExcludes({"menu"}, true); }
    }

    static bool BackPressed()
    {
        if (!GetUApi()) { return false; }
        UAInput back = GetUApi().GetInputByID(UAUIBack);
        return back && back.LocalPress();
    }
}
