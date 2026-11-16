modded class ZombieBase
{
    protected bool m_HCLoadedFromStorage;

    bool HCLoadedFromStorage()
    {
        return m_HCLoadedFromStorage;
    }

    override void AfterStoreLoad()
    {
        super.AfterStoreLoad();
        m_HCLoadedFromStorage = true;
        if (GetGame().IsServer() && HCInfectedModule.Instance)
            HCInfectedModule.Instance.Track(this);
    }

    int HCIndividualStance()
    {
        return m_StanceVariation;
    }

    override void EOnInit(IEntity other, int extra)
    {
        super.EOnInit(other, extra);
        if (GetGame().IsServer() && HCInfectedModule.Instance)
            HCInfectedModule.Instance.Track(this);
    }

    override protected void ProcessSoundVoiceEvent(AnimSoundVoiceEvent sound_event, out AbstractWave aw)
    {
        // Exactly one native render/hearing path, including native environment
        // attenuation. A noise parameter is not proof a human client heard it.
        super.ProcessSoundVoiceEvent(sound_event, aw);
        if (GetGame().IsServer() && HCInfectedModule.Instance)
            HCInfectedModule.Instance.NativeVoice(this, sound_event);
    }

    override bool FightLogic(int pCurrentCommandID, DayZInfectedInputController pInputController, float pDt)
    {
        if (GetGame().IsServer() && HCInfectedModule.Instance && HCInfectedModule.Instance.ContactGuardEnabled())
        {
            // Experimental invocation filter, default off. The source damage
            // calls live in super.FightLogic's WasHit branch, but early return
            // neither cancels COMMANDID_ATTACK nor proves a hit cannot be queued
            // for a later frame. A dedicated wall-hit trial is still required.
            if (pCurrentCommandID == DayZInfectedConstants.COMMANDID_ATTACK && m_ActualTarget)
            {
                bool reachable = CanAttackToPosition(m_ActualTarget.GetPosition());
                if (HCInfectedPolicy.SuppressStrike(true, true, reachable))
                    return true;
            }
        }
        return super.FightLogic(pCurrentCommandID, pInputController, pDt);
    }
    // Native EEHitBy, crawl transition, command handler, locomotion, footsteps,
    // damage, doors and pursuit remain intact. No unsupported waypoint API.
}
