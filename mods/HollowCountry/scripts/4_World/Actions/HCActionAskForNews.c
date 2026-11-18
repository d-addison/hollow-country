// HC-5: server gesture cooldown. Dialogue/action registrations removed.
// Native scripts-1.30.164289: 3_Game/Global/Game.c:1120 IsServer, :1535 GetTime;
// 3_Game/Entities/Man.c:21 GetIdentity; 3_Game/gameplay.c:368 GetId.
class HCSignalReceipt
{
    string Recipient;
    int At;
}
// Shared finite gesture cooldown, replacing the former notification cooldown.
// No standing, no inventory, no client-owned state. Expired rows alone are pruned.
class HCSignalCooldown
{
    protected static ref array<ref HCSignalReceipt> s_Notices = new array<ref HCSignalReceipt>();
    static void Reset() { s_Notices.Clear(); }
    static bool Allowed(PlayerBase player)
    {
        if (!GetGame() || !GetGame().IsServer() || !player || !player.GetIdentity()) { return false; }
        int nowMs = GetGame().GetTime();
        if (nowMs < 0) { return false; }
        string recipient = player.GetIdentity().GetId();
        foreach (HCSignalReceipt prior : s_Notices)
        {
            if (nowMs < prior.At || (prior.Recipient == recipient && nowMs - prior.At < 30000)) { return false; }
        }
        int prune = s_Notices.Count() - 1;
        while (prune >= 0)
        {
            if (nowMs - s_Notices[prune].At >= 30000) { s_Notices.Remove(prune); }
            prune--;
        }
        if (s_Notices.Count() >= 128) { return false; }
        return true;
    }
    // Server callbacks are synchronous: test availability, perform the emote,
    // then claim. A refused native gesture never spends the player's cooldown.
    static bool Claim(PlayerBase player)
    {
        if (!HCSignalCooldown.Allowed(player)) { return false; }
        int nowMs = GetGame().GetTime();
        HCSignalReceipt receipt = new HCSignalReceipt();
        receipt.Recipient = player.GetIdentity().GetId();
        receipt.At = nowMs;
        s_Notices.Insert(receipt);
        return true;
    }
}
// Compatibility hook retained for the core lifecycle; dialogue/action removed.
class HCAskForNews
{
    static void Configure(bool enabled) {}
}
