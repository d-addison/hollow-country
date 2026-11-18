// W5 #128/#129/#130 shared policies; no tick or entity storage.
// Native evidence: scripts-1.30.164289/4_World/Classes/FoodStage/FoodStage.c:1-8
// (FoodStageType); 2_GameLib/gameLib.c:4 GetGame;
// 3_Game/Global/Game.c:1120 IsServer, :1535 GetTime;
// 3_Game/Entities/Man.c:21 GetIdentity; 3_Game/gameplay.c:368 GetId;
// 1_Core/proto/EnString.c:86 ToAscii, :199 Length, :240 IndexOf, :448 Get.
// Shared by meals and forage: server check and monotonic session seconds.
// Shared by forage/progression: capped reward/refill policy. Candidate tuning,
// never measured budgets or native acceptance. UTC uses HCGroupClock.Utc.
class HCSurvivalPolicy
{
    static int MealExpiry(bool enabled, int stage, float temperature, float amount, int now)
    {
        if (!enabled || now < 0) { return 0; }
        bool cooked = stage == FoodStageType.BAKED || stage == FoodStageType.BOILED;
        if (stage == FoodStageType.DRIED) { cooked = true; }
        if (!cooked) { return 0; }
        if (!(temperature >= 30 && temperature <= 200)) { return 0; }
        if (!(amount > 0 && amount <= 10000)) { return 0; }
        return now + 600;
    }

    static float MealHeat(int now, int expires)
    {
        if (now < 0 || expires <= now) { return 0; }
        return 0.05;
    }

    static bool CanRefill(bool itemPresent, int cellLive, int totalLive, int now, int ready)
    {
        if (itemPresent || now < ready) { return false; }
        if (now < 1 || ready < 0) { return false; }
        if (cellLive < 0 || cellLive >= 3) { return false; }
        if (totalLive < 0 || totalLive >= 40) { return false; }
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
        return 1800 - (180 * score) / 100;
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

    static string HCIdentityKey(PlayerBase player)
    {
        if (!HCIsServer() || !player) { return ""; }
        PlayerIdentity identity = player.GetIdentity();
        if (!identity) { return ""; }
        string raw = identity.GetId();
        if (raw.Length() < 16 || raw.Length() > 64) { return ""; }
        // Lossless hex encoding avoids collisions from removing/replacing unsafe
        // characters. This key is only a JSON field value, never a path or log.
        string digits = "0123456789abcdef";
        string key = "p";
        for (int keyIndex = 0; keyIndex < raw.Length(); keyIndex++)
        {
            int code = raw.Get(keyIndex).ToAscii();
            if (code < 33 || code > 126) { return ""; }
            int high = code / 16;
            key = key + digits.Get(high) + digits.Get(code - high * 16);
        }
        return key;
    }
}
