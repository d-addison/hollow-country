// #276. Original adapter; installed Expansion APIs inspected, no provider code.
// eAI_Targeting completes LOS before the later eAI_UpdateFSM in both update modes.
// Native 1.30: RequestSoundEvent replicates a voice event without a combat action.
class HCXWarningShout
{
    static const int COOLDOWN_MS = 60000;
    static const int MAX_PLAYERS = 64;
    protected static ref map<string, int> s_PlayerWarnings = new map<string, int>();

    // Session-only opaque identity keys: no logging, persistence or retained players.
    // Never evict an unexpired cooldown to admit another player.
    static bool AdmitPlayer(PlayerBase player, int now)
    {
        PlayerIdentity identity = player.GetIdentity();
        if (!identity) { return false; }
        string key = identity.GetId();
        if (key == "") { return false; }
        int previous;
        if (s_PlayerWarnings.Find(key, previous))
        {
            if (now - previous < COOLDOWN_MS) { return false; }
        }
        else if (s_PlayerWarnings.Count() >= MAX_PLAYERS)
        {
            for (int i = 0; i < MAX_PLAYERS; i++)
            {
                string retiredKey = s_PlayerWarnings.GetKey(i);
                int retiredTime = s_PlayerWarnings.GetElement(i);
                if (now - retiredTime < COOLDOWN_MS) { continue; }
                s_PlayerWarnings.Remove(retiredKey);
                break;
            }
            if (s_PlayerWarnings.Count() >= MAX_PLAYERS) { return false; }
        }
        s_PlayerWarnings.Set(key, now);
        return true;
    }
}

modded class eAIBase
{
    bool HCWarningActor;
    int HCXLastWarning = -60000;

    // Native 1.30: PlayerBase.c:6924 MessageStatus, :7779 RequestSoundEvent
    // (sound API also used by the preceding #276 adapter).
    bool HCXWarnPlayer(PlayerBase player, int now)
    {
        if (!HCWarningActor || now - HCXLastWarning < HCXWarningShout.COOLDOWN_MS) { return false; }
        if (!HCXWarningShout.AdmitPlayer(player, now)) { return false; }
        HCXLastWarning = now;
        RequestSoundEvent(EPlayerSoundEventID.MELEE_ATTACK_HEAVY);
        player.MessageStatus("Stay back. Lower your weapon and move away.");
        Print("[HollowCountry] Stance warning: shout + text; keep back 40m; runtime=PENDING");
        return true;
    }
}
