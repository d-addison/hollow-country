modded class ZombieBase
{
    protected bool m_HCLoadedFromStorage;
    protected HCInfectedModule m_HCRegistrationOwner;
    protected bool m_HCRegistered;
    protected int m_HCRegistrationRound = -1;

    void HCRegisterActive()
    {
        HCInfectedModule current = HCInfectedModule.Instance;
        if (current != m_HCRegistrationOwner)
        {
            m_HCRegistrationOwner = current;
            m_HCRegistered = false;
            m_HCRegistrationRound = -1;
        }
        if (!current || m_HCRegistered || !GetGame().IsServer() || !IsAlive())
        {
            return;
        }
        int round = current.RegistrationRound();
        if (round == m_HCRegistrationRound)
        {
            return;
        }
        m_HCRegistrationRound = round;
        // One retry per core round; Track owns the shared bounded scan budget.
        // No retained startup queue or world/population scan.
        m_HCRegistered = current.Track(this);
    }

    // Parameter names must match the engine prototype (DayZCreatureAI).
    override bool ModCommandHandlerBefore(float pDt, int pCurrentCommandID, bool pCurrentCommandFinished)
    {
        bool consumed = super.ModCommandHandlerBefore(pDt, pCurrentCommandID, pCurrentCommandFinished);
        HCRegisterActive();
        return consumed;
    }

    bool HCLoadedFromStorage()
    {
        return m_HCLoadedFromStorage;
    }

    override void AfterStoreLoad()
    {
        super.AfterStoreLoad();
        m_HCLoadedFromStorage = true;
        HCRegisterActive();
    }

    int HCIndividualStance()
    {
        return m_StanceVariation;
    }

    override void EOnInit(IEntity other, int extra)
    {
        super.EOnInit(other, extra);
        HCRegisterActive();
    }

    override protected void ProcessSoundVoiceEvent(AnimSoundVoiceEvent sound_event, out AbstractWave aw)
    {
        // Exactly one native render/hearing path, including native environment
        // attenuation. A noise parameter is not proof a human client heard it.
        if (GetGame().IsServer()) { super.ProcessSoundVoiceEvent(sound_event, aw); }
        if (GetGame().IsServer() && HCInfectedModule.Instance)
            HCInfectedModule.Instance.NativeVoice(this, sound_event);
    }

    override bool FightLogic(int pCurrentCommandID, DayZInfectedInputController pInputController, float pDt)
    {
        if (GetGame().IsServer() && HCInfectedModule.Instance && HCInfectedModule.Instance.ContactGuardEnabled())
        {
            // Experimental invocation filter; qualification remains unresolved. The source damage
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
