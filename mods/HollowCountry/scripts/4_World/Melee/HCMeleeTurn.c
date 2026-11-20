// MEL-16 turn while swinging (client-predicted on the owner client and the server).
// Native evidence, scripts-1.30.164289 (paths relative to the scripts root):
// - 4_World/Entities/DayZPlayerImplement.c:1634-1715 HeadingModel: during
//   COMMANDID_MELEE2 vanilla reaches RotateOrient (:1715); it is "replayed after
//   correction" (:1633), so it is part of the predicted human simulation.
// - 4_World/Entities/DayZPlayerImplementHeading.c:67-118 RotateOrient: vanilla
//   itself writes SDayZPlayerHeadingModel.m_fOrientationAngle and returns true,
//   but only past CONST_ROTLIMIT (pi*0.95, :65), so the body stays locked mid-swing.
// - 4_World/Entities/ManBase/PlayerBase.c:8640-8675 PlayerBase.HeadingModel
//   (action/emote locks) runs first through super and is left untouched.
// - 3_Game/dayzplayer.c:1097-1103 SDayZPlayerHeadingModel fields; :699 COMMANDID_MELEE2.
// - 3_Game/human.c:556-585 HumanCommandMelee2 GetCurrentHitType/IsFinisher.
// - 3_Game/Entities/Man.c:21 GetIdentity; 4_World/Entities/ManBase.c:10 IsControlledPlayer.
// - 1_Core/proto/EnMath.c:198 ModFloat, :225 AbsFloat, Clamp; PI2/PI_HALF/DEG2RAD.
// Only the yaw (orientation) follows the aim, at a capped rate; translation stays
// with the native Melee2 root motion. No position is written anywhere.
// The rates are literals compiled into both peers (spec section 7 option 1), so the
// prediction matches without sync. A later melee client sync may assign these
// statics on both peers before play; nothing here reads the server profile.
class HCMeleeTurn
{
    static bool Enabled = true;
    static float LightRateDeg = 200.0;
    static float HeavyRateDeg = 120.0;
    static float LogTurnDeg = 20.0;
    protected static int s_Logged;

    // Radians per second for the running swing, or 0 when turning is not allowed.
    static float HCRate(HumanCommandMelee2 melee)
    {
        if (!HCMeleeTurn.Enabled || !melee || melee.IsFinisher()) { return 0; }
        int hitType = melee.GetCurrentHitType();
        if (hitType == HumanCommandMelee2.HIT_TYPE_LIGHT) { return HCMeleeTurn.LightRateDeg * Math.DEG2RAD; }
        if (hitType == HumanCommandMelee2.HIT_TYPE_HEAVY) { return HCMeleeTurn.HeavyRateDeg * Math.DEG2RAD; }
        return 0;
    }

    // Wraps into [-pi, pi]; ModFloat keeps this loop-free for unnormalised angles.
    static float HCWrap(float angle)
    {
        float wrapped = Math.ModFloat(angle, Math.PI2);
        if (wrapped > Math.PI) { wrapped -= Math.PI2; }
        else if (wrapped < -Math.PI) { wrapped += Math.PI2; }
        return wrapped;
    }

    // Server evidence only, capped by Melee.LogLimit; never called per frame after the first log.
    static void HCLog(float degrees)
    {
        if (!GetGame().IsServer() || !HCMeleeModule.Active()) { return; }
        if (s_Logged >= HCMeleeConfig.HCGet().LogLimit) { return; }
        s_Logged++;
        int whole = Math.Round(degrees);
        Print("[HC Melee] swing_turn count=" + s_Logged.ToString() + " deg=" + whole.ToString());
    }
}

modded class PlayerBase
{
    protected float m_HCMeleeTurned;
    protected bool m_HCMeleeTurnLogged;

    override bool HeadingModel(float pDt, SDayZPlayerHeadingModel pModel)
    {
        bool modified = super.HeadingModel(pDt, pModel);
        if (pModel.m_iCurrentCommandID != DayZPlayerConstants.COMMANDID_MELEE2)
        {
            m_HCMeleeTurned = 0;
            m_HCMeleeTurnLogged = false;
            return modified;
        }
        if (!HCMeleeTurn.Enabled || pDt <= 0 || !IsAlive()) { return modified; }
        // super refreshed m_MovementState (DayZPlayerImplement.c:1641). Standing swings only:
        // prone kicks and finishers keep the native lock.
        int stance = m_MovementState.m_iStanceIdx;
        if (stance != DayZPlayerConstants.STANCEIDX_RAISEDERECT && stance != DayZPlayerConstants.STANCEIDX_ERECT) { return modified; }
        // Real players only; AI characters keep their own heading logic. The same
        // answer holds on the owner client (controlled) and the server (identity).
        if (!GetIdentity() && !IsControlledPlayer()) { return modified; }

        float rate = HCMeleeTurn.HCRate(GetCommand_Melee2());
        if (rate <= 0) { return modified; }

        float diff = HCMeleeTurn.HCWrap(pModel.m_fHeadingAngle - pModel.m_fOrientationAngle);
        // Same unwrap continuity as RotateOrient (DayZPlayerImplementHeading.c:83-90).
        if (m_fLastHeadingDiff < -Math.PI_HALF && diff > 0) { diff -= Math.PI2; }
        else if (m_fLastHeadingDiff > Math.PI_HALF && diff < 0) { diff += Math.PI2; }

        float maxStep = rate * pDt;
        float step = Math.Clamp(diff, -maxStep, maxStep);
        if (Math.AbsFloat(step) < 0.0005) { return modified; }

        pModel.m_fOrientationAngle = pModel.m_fOrientationAngle + step;
        m_fLastHeadingDiff = diff - step;

        if (!m_HCMeleeTurnLogged && GetGame().IsServer())
        {
            m_HCMeleeTurned += Math.AbsFloat(step);
            if (m_HCMeleeTurned >= HCMeleeTurn.LogTurnDeg * Math.DEG2RAD)
            {
                m_HCMeleeTurnLogged = true;
                HCMeleeTurn.HCLog(m_HCMeleeTurned * Math.RAD2DEG);
            }
        }
        return true;
    }
}
