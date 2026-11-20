// W5 #128/#129/#130 shared policies; no tick or entity storage.
// Native evidence: scripts-1.30.164289/2_GameLib/gameLib.c:4 GetGame;
// 3_Game/Global/Game.c:1120 IsServer, :1535 GetTime;
// 3_Game/Entities/Man.c:21 GetIdentity; 3_Game/gameplay.c:368 GetId;
// 1_Core/proto/EnString.c:86 ToAscii, :199 Length, :240 IndexOf, :448 Get.
// Shared by forage/progression: server check and monotonic session seconds.
// Shared by forage/progression: capped reward/refill policy. Candidate tuning,
// never measured budgets or native acceptance. UTC uses HCGroupClock.Utc.
class HCSurvivalPolicy
{
    static int MealExpiry(bool enabled, int stage, float temperature, float amount, int now)
    {
        // HC-2 / #150: compatibility tombstone. Legacy callers cannot grant heat.
        return 0;
    }

    static float MealHeat(int now, int expires)
    {
        // Includes a previously granted, unexpired meal: native thermal inputs only.
        return 0;
    }

    static bool CanRefill(bool itemPresent, int cellLive, int totalLive, int now, int ready)
    {
        if (itemPresent || now < ready) { return false; }
        if (now < 1 || ready < 0) { return false; }
        if (cellLive < 0 || cellLive >= HCForageConfig.Get().CellCap) { return false; }
        if (totalLive < 0 || totalLive >= HCForageConfig.Get().TotalCap) { return false; }
        return true;
    }

    static int DecayedFamiliarity(int score, int days)
    {
        if (score < 0) { score = 0; }
        if (score > 100) { score = 100; }
        if (days < 0) { days = 0; }
        if (days >= score) { return 0; }
        return score - days;
    }

    static int ForageDelay(int familiarity)
    {
        int score = DecayedFamiliarity(familiarity, 0);
        return HCForageConfig.Get().DelaySeconds - (HCForageConfig.Get().FamiliarityReductionSeconds * score) / 100;
    }
}

class HCSurvivalRuntime
{
    static bool HCIsServer()
    {
        if (!GetGame()) { return false; }
        return GetGame().IsServer();
    }

    static int HCSessionSeconds()
    {
        int milliseconds = GetGame().GetTime();
        // Wrapped native millisecond clocks fail closed until mission restart.
        if (milliseconds < 0) { return -1; }
        return milliseconds / 1000;
    }

    // N17: 3_Game/Entities/EntityAI.c:3374 GetPersistentID(out int x4).
    // Native persistence owns generation identity. No account ID, session object
    // address, random guess or living position is used as a character key.
    // All-zero allocation is unknown and refuses familiarity. Stability across
    // native save/load/death is an acceptance experiment, never offline proof.
    static string HCCharacterKey(PlayerBase player)
    {
        if (!HCIsServer() || !player) { return ""; }
        int part1;
        int part2;
        int part3;
        int part4;
        player.GetPersistentID(part1, part2, part3, part4);
        if (part1 == 0 && part2 == 0 && part3 == 0 && part4 == 0) { return ""; }
        return "c:" + part1.ToString() + ":" + part2.ToString() + ":" + part3.ToString() + ":" + part4.ToString();
    }

    static string HCIdentityKey(PlayerBase player)
    {
        string reason;
        return HCIdentityKeyChecked(player, reason);
    }

    // Reasons are fixed tokens only. Never include identity values in receipts.
    static string HCIdentityKeyChecked(PlayerBase player, out string reason)
    {
        reason = "";
        if (!HCIsServer()) { reason = "not_server"; return ""; }
        if (!player) { reason = "no_player"; return ""; }
        PlayerIdentity identity = player.GetIdentity();
        if (!identity) { reason = "identity_detached"; return ""; }
        string raw = identity.GetId();
        reason = "identity_length";
        if (raw.Length() < 16 || raw.Length() > 64) { return ""; }
        reason = "";
        // Lossless hex encoding avoids collisions from removing/replacing unsafe
        // characters. This key is only a JSON field value, never a path or log.
        string digits = "0123456789abcdef";
        string key = "p";
        for (int keyIndex = 0; keyIndex < raw.Length(); keyIndex++)
        {
            int code = raw.Get(keyIndex).ToAscii();
            if (code < 33 || code > 126) { reason = "identity_encoding"; return ""; }
            int high = code / 16;
            key = key + digits.Get(high) + digits.Get(code - high * 16);
        }
        return key;
    }
}
