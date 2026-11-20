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
    protected int m_HCWarningTime;
    protected bool m_HCHasWarned;
    protected PlayerBase m_HCWarningContact;

    override void eAI_Targeting(float pDt, EntityAI entityInHands, bool checkLOS = true)
    {
        super.eAI_Targeting(pDt, entityInHands, checkLOS);
        if (!GetGame() || !GetGame().IsServer() || !HCWarningActor) { return; }
        // A simulation-disabled update explicitly skips LOS; never use that cache.
        if (!checkLOS) { return; }
        eAITarget contact;
        if (TargetCount() > 0) { contact = GetTarget(); }
        PlayerBase player;
        if (contact) { player = PlayerBase.Cast(contact.GetEntity()); }
        if (!player || player.IsAI() || !player.IsAlive() || !eAI_HasLOS() || vector.DistanceSq(GetPosition(), player.GetPosition()) > 6400)
        {
            m_HCWarningContact = null;
            return;
        }
        if (m_HCWarningContact == player) { return; }
        // Eligibility and hostility are re-checked every targeting pass, so a
        // player who turns hostile while in view can still be warned.
        if (!IsAlive() || IsUnconscious() || IsRestrained() || IsFighting() || m_eAI_IsFightingFSM || IsRaised()) { return; }
        if (GetThreatToSelf() >= 0.4 || !PlayerIsEnemy(player)) { return; }
        // One attempt per eligible hostile contact, even when a cooldown refuses it.
        m_HCWarningContact = player;
        int now = GetGame().GetTime();
        if (m_HCHasWarned && now - m_HCWarningTime < HCXWarningShout.COOLDOWN_MS) { return; }
        if (!HCXWarningShout.AdmitPlayer(player, now)) { return; }
        m_HCHasWarned = true;
        m_HCWarningTime = now;
        // Native heavy-melee vocalisation only: no swing, gesture, raised-weapon
        // change, target rewrite, threat suppression or engagement timer.
        RequestSoundEvent(EPlayerSoundEventID.MELEE_ATTACK_HEAVY);
    }
}
