// Optional tuning only; absent keys retain declared defaults (native JSON zero-fills).
// Native scripts-1.30.164289: 1_Core/proto/EnSystem.c:397 FileExist;
// 3_Game/tools/JsonFileLoader.c:69 LoadData; 1_Core/proto/EnDebug.c:96 Print.
// EnConvert.c:3,30 bool/int.ToString; EnScript.c:380/407/463 Count/Insert/Remove.
// HCGroupIO.Read owns bounded native file IO; HCJsonFields owns key presence.
class HCSignalConfig
{
    bool Enabled = true;
    int CooldownMs = 30000;
    int MaxNotices = 128;
    protected static ref HCSignalConfig s_Config;

    bool HCNormalize(string text)
    {
        bool invalid = false;
        if (!HCJsonFields.Has(text, "Enabled")) { this.Enabled = true; }
        if (!HCJsonFields.Has(text, "MaxNotices")) { this.MaxNotices = 128; }
        if (!HCOperatorSettingsRegistry.HCValid("Signals.MaxNotices", this.MaxNotices)) { this.MaxNotices = 128; invalid = true; }
        if (!HCJsonFields.Has(text, "CooldownMs")) { this.CooldownMs = 30000; }
        if (!HCOperatorSettingsRegistry.HCValid("Signals.CooldownMs", this.CooldownMs)) { this.CooldownMs = 30000; invalid = true; }
        return invalid;
    }
    void HCReport()
    {
        Print("[HC Config] HCSignalConfig enabled=" + Enabled.ToString() + " cooldown_ms=" + CooldownMs.ToString() + " notices=" + MaxNotices.ToString() + " runtime=PENDING");
    }
    static HCSignalConfig Get()
    {
        if (s_Config) { return s_Config; }
        HCOperatorSettingsRegistry.HCLocalPolicyInit();
        s_Config = new HCSignalConfig;
        string path = "$profile:HollowCountry/signals.json";
        if (!FileExist(path)) { s_Config.HCReport(); return s_Config; }
        string text;
        string error;
        HCSignalConfig loaded;
        if (!HCGroupIO.Read(path, 16384, text) || !JsonFileLoader<HCSignalConfig>.LoadData(text, loaded, error) || !loaded)
        {
            Print("[HC Config] HCSignalConfig invalid_json defaults_restored runtime=PENDING");
            s_Config.HCReport();
            return s_Config;
        }
        bool invalid = loaded.HCNormalize(text);
        s_Config = loaded;
        if (invalid) { Print("[HC Config] HCSignalConfig invalid_range defaults_restored runtime=PENDING"); }
        s_Config.HCReport();
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
        if (!HCSignalConfig.Get().Enabled) { return false; }
        int nowMs = GetGame().GetTime();
        if (nowMs < 0) { return false; }
        string recipient = player.GetIdentity().GetId();
        array<ref HCSignalReceipt> notices = s_Notices;
        foreach (HCSignalReceipt prior : notices)
        {
            if (nowMs < prior.At || (prior.Recipient == recipient && nowMs - prior.At < HCSignalConfig.Get().CooldownMs)) { return false; }
        }
        int prune = s_Notices.Count() - 1;
        while (prune >= 0)
        {
            if (nowMs - s_Notices[prune].At >= HCSignalConfig.Get().CooldownMs) { s_Notices.Remove(prune); }
            prune--;
        }
        if (s_Notices.Count() >= HCSignalConfig.Get().MaxNotices) { return false; }
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
