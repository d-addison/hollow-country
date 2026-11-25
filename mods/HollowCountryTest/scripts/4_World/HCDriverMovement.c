// Client input is queued by MissionGameplay.OnUpdate and consumed at the player command callback.
// Native PlayerBase.c:3206 exact script signature; never override a proto native method.
class HCDriverMovement
{
    static bool Pending;
    static float Speed;
    static float Angle;
    static int CommandId;
    static int AppliedFrames;
    static bool Calibrated;
    static float AngleSign = 1.0;
    static float HeadingOffset;

    static void Request(float speed, float angle)
    {
        Speed = speed;
        Angle = angle;
        Pending = true;
    }

    static void Stop()
    {
        Pending = false;
    }
}

#ifndef SERVER
modded class PlayerBase
{
    override void CommandHandler(float pDt, int pCurrentCommandID, bool pCurrentCommandFinished)
    {
        if (this == GetGame().GetPlayer())
        {
            HCDriverMovement.CommandId = pCurrentCommandID;
            if (HCDriverMovement.Pending)
            {
                // Consume once even when a command transition prevents applying this frame.
                // A menu/action must not leave an old walk queued for a later command.
                HCDriverMovement.Pending = false;
                HumanInputController input = GetInputController();
                if (GetCommand_Move() && input)
                {
                    input.OverrideMovementSpeed(HumanInputControllerOverrideType.ONE_FRAME, HCDriverMovement.Speed);
                    input.OverrideMovementAngle(HumanInputControllerOverrideType.ONE_FRAME, HCDriverMovement.Angle);
                    if (HCDriverMovement.AppliedFrames < 1000000) { HCDriverMovement.AppliedFrames++; }
                }
            }
        }
        super.CommandHandler(pDt, pCurrentCommandID, pCurrentCommandFinished);
    }
}
#endif
