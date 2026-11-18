// Native 1.30.164289: 4_World/Entities/Firearms/Weapon_Base.c:55 m_fsm
// (protected), :133 empty InitStateMachine, :295 ProcessWeaponEvent,
// :315 ProcessWeaponAbortEvent; Machinegun/M249.c:1 inherits without an FSM.
// Installed Expansion AI 4_World/DayZExpansion_AI/Entities/Weapons/Firearms/
// Weapon_Base.c:639-666 ProcessWeaponEvent dereferences m_fsm at :660;
// :669-684 ProcessWeaponAbortEvent dereferences it at :676. Event m_player
// and eAIBase cast are used at :645-646; native EntityAI.c:882 root player.
// Guard OUR downstream dispatch only; never construct a third-party FSM or
// mutate inventory. Healthy AI and human dispatch keep their existing semantics.
modded class Weapon_Base
{
    protected bool m_HCXMissingFSMReported;

    protected bool HCXRefuseMissingFSM(WeaponEventBase e)
    {
        if (m_fsm) { return false; }
        eAIBase ai;
        if (e) { ai = eAIBase.Cast(e.m_player); }
        if (!ai) { ai = eAIBase.Cast(GetHierarchyRootPlayer()); }
        if (!ai) { return false; }
        if (!m_HCXMissingFSMReported && GetGame() && GetGame().IsServer())
        {
            m_HCXMissingFSMReported = true;
            Print("[HCX Weapon] refused AI event; reason=missing_fsm; weapon=" + GetType() + "; remove this unsupported weapon from the AI; use a validated loadout");
        }
        return true;
    }

    override bool ProcessWeaponEvent(WeaponEventBase e)
    {
        if (HCXRefuseMissingFSM(e)) { return false; }
        return super.ProcessWeaponEvent(e);
    }

    override bool ProcessWeaponAbortEvent(WeaponEventBase e)
    {
        if (HCXRefuseMissingFSM(e)) { return false; }
        return super.ProcessWeaponAbortEvent(e);
    }
}
