// Native API citations are in HCEcologyCycle.c. Per-frame work is constant:
// no terrain/path/player queries here. Expiry and native threat always release
// our three input overrides, even if the module loses its shared work slice.
modded class AnimalBase
{
    protected float m_HCEcologyUntil;
    protected vector m_HCEcologyGoal;
    protected int m_HCEcologyAction;
    protected bool m_HCEcologyInputs;

    bool HCEcologyCalm()
    {
        DayZAnimalInputController controller = GetInputController();
        if (!controller || controller.IsDead() || controller.IsAttack() || controller.IsAlerted()) { return false; }
        int slot = controller.GetBehaviourSlot();
        return slot == DayZAnimalBehaviourSlot.CALM || slot == DayZAnimalBehaviourSlot.CALM_RESTING || slot == DayZAnimalBehaviourSlot.CALM_GRAZING || slot == DayZAnimalBehaviourSlot.CALM_TRAVELLING || slot == DayZAnimalBehaviourSlot.DRINKING;
    }
    bool HCEcologyLeased() { return GetGame() && m_HCEcologyUntil > GetGame().GetTickTime(); }
    int HCEcologyAction() { return m_HCEcologyAction; }
    void HCEcologyLease(vector goal, int action, float until)
    {
        m_HCEcologyGoal = goal;
        m_HCEcologyAction = action;
        m_HCEcologyUntil = until;
    }
    void HCEcologyRelease()
    {
        m_HCEcologyUntil = 0;
        if (!m_HCEcologyInputs) { return; }
        m_HCEcologyInputs = false;
        DayZAnimalInputController controller = GetInputController();
        if (!controller) { return; }
        controller.OverrideHeading(false, 0);
        controller.OverrideMovementSpeed(false, 0);
        controller.OverrideBehaviourAction(false, 0);
    }
    override bool ModCommandHandlerBefore(float pDt, int pCurrentCommandID, bool pCurrentCommandFinished)
    {
        bool consumed = super.ModCommandHandlerBefore(pDt, pCurrentCommandID, pCurrentCommandFinished);
        if (!GetGame() || !GetGame().IsServer()) { return consumed; }
        if (consumed || pCurrentCommandFinished || pCurrentCommandID != DayZAnimalConstants.COMMANDID_MOVE || !IsAlive() || !HCEcologyLeased() || !HCEcologyCycle.Active() || !HCEcologyCalm())
        {
            HCEcologyRelease();
            return consumed;
        }
        DayZAnimalInputController controller = GetInputController();
        vector delta = m_HCEcologyGoal - GetPosition();
        delta[1] = 0;
        bool walking = m_HCEcologyAction == DayZAnimalBehaviourAction.WALKING_INPUT;
        if (walking && delta.Length() < 0.5) { HCEcologyRelease(); return consumed; }
        controller.OverrideBehaviourAction(true, m_HCEcologyAction);
        float speed = 0;
        if (walking) { speed = 1; }
        controller.OverrideMovementSpeed(true, speed);
        if (walking) { controller.OverrideHeading(true, delta.VectorToAngles()[0] * Math.DEG2RAD); }
        else { controller.OverrideHeading(false, 0); }
        m_HCEcologyInputs = true;
        return consumed;
    }
}
