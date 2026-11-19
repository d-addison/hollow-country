// Optional tuning only; absent keys retain declared defaults (native JSON zero-fills).
// Native scripts-1.30.164289: 1_Core/proto/EnSystem.c:397 FileExist;
// 3_Game/tools/JsonFileLoader.c:69 LoadData; 1_Core/proto/EnDebug.c:96 Print.
// HCGroupIO.Read owns bounded native file IO; HCJsonFields owns key presence.
class HCSignalConfig
{
    int CooldownMs = 30000;
    protected static ref HCSignalConfig s_Config;

    bool HCNormalize(string text)
    {
        bool invalid = false;
        if (!HCJsonFields.Has(text, "CooldownMs")) { this.CooldownMs = 30000; }
        if (!(this.CooldownMs >= 1000 && this.CooldownMs <= 3600000)) { this.CooldownMs = 30000; invalid = true; }
        return invalid;
    }
    static HCSignalConfig Get()
    {
        if (s_Config) { return s_Config; }
        s_Config = new HCSignalConfig;
        string path = "$profile:HollowCountry/signals.json";
        if (!FileExist(path)) { return s_Config; }
        string text;
        string error;
        HCSignalConfig loaded;
        if (!HCGroupIO.Read(path, 16384, text) || !JsonFileLoader<HCSignalConfig>.LoadData(text, loaded, error) || !loaded)
        {
            Print("[HC Config] HCSignalConfig invalid_json defaults_restored runtime=PENDING");
            return s_Config;
        }
        bool invalid = loaded.HCNormalize(text);
        s_Config = loaded;
        if (invalid) { Print("[HC Config] HCSignalConfig invalid_range defaults_restored runtime=PENDING"); }
        return s_Config;
    }
}

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
            if (nowMs < prior.At || (prior.Recipient == recipient && nowMs - prior.At < HCSignalConfig.Get().CooldownMs)) { return false; }
        }
        int prune = s_Notices.Count() - 1;
        while (prune >= 0)
        {
            if (nowMs - s_Notices[prune].At >= HCSignalConfig.Get().CooldownMs) { s_Notices.Remove(prune); }
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
