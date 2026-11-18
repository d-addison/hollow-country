// World is the lowest layer that can see PlayerBase and ActionData. Codes live in Game.
// Inspected installed native scripts-1.30.164289 (not runtime delivery evidence):
// 4_World/Entities/ManBase/PlayerBase.c:6924 MessageStatus -> :6911 Message;
// :6915 server branch g_Game.ChatMP(this, text, style) targets the recipient.
// 3_Game/Global/Game.c:1034 ChatMP(Man recipient, string text, string colorClass);
// :914 GetTickTime (seconds), :1120 IsServer. No custom RPC or client inventory state.
class HCRefusalWindow
{
    PlayerBase Actor; // Weak engine handle: never retain a disconnected player.
    string Reason;
    float ToldAt;
}

class HCRefusalReport
{
    static const float WINDOW_SECONDS = 5.0;
    static const int MAX_WINDOWS = 128;
    protected static ref array<ref HCRefusalWindow> s_Windows = new array<ref HCRefusalWindow>;

    // Bounded O(MAX_WINDOWS), action-driven only. Expiry/clock rollback releases slots.
    // At saturation preserve live windows and suppress new pairs until a slot expires;
    // clearing/evicting live pairs would let a burst bypass the message/log limiter.
    // Keys use object identity, including identity-less native diagnostic actors. Never
    // read/store/print a player id, and never let unrelated anonymous players collide.
    static bool RefusalMessage(PlayerBase player, string reason, Object subject, string text)
    {
        if (!GetGame() || !GetGame().IsServer() || !player || reason == "" || text == "") return false;
        float now = GetGame().GetTickTime();
        int index = s_Windows.Count() - 1;
        while (index >= 0)
        {
            HCRefusalWindow known = s_Windows[index];
            if (!known.Actor || now < known.ToldAt || now - known.ToldAt >= WINDOW_SECONDS)
            {
                s_Windows.Remove(index);
            }
            else if (known.Actor == player && known.Reason == reason)
            {
                return false;
            }
            index = index - 1;
        }
        if (s_Windows.Count() >= MAX_WINDOWS) return false;
        ref HCRefusalWindow window = new HCRefusalWindow;
        window.Actor = player;
        window.Reason = reason;
        window.ToldAt = now;
        // Reserve before native messaging to guard reentry.
        s_Windows.Insert(window);
        string cls = "none";
        if (subject) cls = subject.GetType();
        Print("[HC Refusal] refused reason=" + reason + " class=" + cls);
        player.MessageStatus(text);
        return true;
    }

    static void TargetRefusalMessage(PlayerBase player, ActionTarget target, Object held, string reason, string text)
    {
        Object subject = held;
        if (target && target.GetObject()) subject = target.GetObject();
        RefusalMessage(player, reason, subject, text);
    }

    static void ActionRefusalMessage(ActionData data, string reason, string text)
    {
        if (!data) return;
        TargetRefusalMessage(data.m_Player, data.m_Target, data.m_MainItem, reason, text);
    }
}
