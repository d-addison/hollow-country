// Native scripts-1.30.164289: 4_World/Entities/ManBase/PlayerBase.c:3206-3211 signature/super;
// :3513-3515 and Systems/Bot/Bot_MovementRandomizer.c:38-39 apply ONE_FRAME after super.
// 3_Game/human.c:7-12: ENABLED persists until DISABLED; ONE_FRAME expires next callback.
class HCDriverMovement
{
    static const int POST_SUPER = 0;
    static const int PERSISTENT = 1;
    static const int PRE_SUPER = 2;
    static int Variant;
    static bool Pending;
    static float Speed;
    static float Angle;
    static int CommandId;
    static int AppliedFrames;
    static bool Calibrated;
    static float AngleSign = 1.0;
    static float HeadingOffset;
    static PlayerBase Owner;
    static bool Enabled;
    static float AppliedSpeed;
    static float AppliedAngle;
    static float Lease;

    static string VariantName()
    {
        if (Variant == POST_SUPER) { return "one-frame-post-super"; }
        if (Variant == PERSISTENT) { return "enabled"; }
        return "one-frame-pre-super";
    }

    static void Request(float speed, float angle)
    {
        Speed = speed;
        Angle = angle;
        Pending = true;
        Lease = 0.5;
    }

    static void Stop()
    {
        Pending = false;
        Lease = 0;
        // Clear the original controller even when GetPlayer has changed/disconnected.
        // Native human.c:253/256; DISABLED is required for persistent overrides (:10).
        if (Owner)
        {
            HumanInputController input = Owner.GetInputController();
            if (input)
            {
                input.OverrideMovementSpeed(HumanInputControllerOverrideType.DISABLED, 0);
                input.OverrideMovementAngle(HumanInputControllerOverrideType.DISABLED, 0);
            }
        }
        Owner = null;
        Enabled = false;
    }

    static bool Guard(PlayerBase player, float dt)
    {
        Lease = Lease - dt;
        // Native 3_Game/Global/Game.c:1093 GetMission; 3_Game/gameplay.c:792 IsControlDisabled.
        Mission mission = GetGame().GetMission();
        if (player != GetGame().GetPlayer() || !player.IsAlive() || player.IsUnconscious() || !player.GetCommand_Move() || !player.GetInputController() || !mission || mission.IsControlDisabled() || Lease <= 0)
        {
            Stop();
            return false;
        }
        return true;
    }

    static void Consume(PlayerBase player)
    {
        if (!Pending) { return; }
        Pending = false;
        if (Owner && Owner != player) { Stop(); return; }
        Owner = player;
        HumanInputController input = player.GetInputController();
        if (!input || !player.GetCommand_Move()) { Stop(); return; }
        if (Variant == PERSISTENT)
        {
            // Set once at start, then only when the requested speed/angle changes.
            if (!Enabled || AppliedSpeed != Speed || AppliedAngle != Angle)
            {
                input.OverrideMovementSpeed(HumanInputControllerOverrideType.ENABLED, Speed);
                input.OverrideMovementAngle(HumanInputControllerOverrideType.ENABLED, Angle);
                AppliedSpeed = Speed;
                AppliedAngle = Angle;
                Enabled = true;
            }
        }
        else
        {
            input.OverrideMovementSpeed(HumanInputControllerOverrideType.ONE_FRAME, Speed);
            input.OverrideMovementAngle(HumanInputControllerOverrideType.ONE_FRAME, Angle);
        }
        if (AppliedFrames < 1000000) { AppliedFrames++; }
    }
}

#ifndef SERVER
modded class PlayerBase
{
    override void CommandHandler(float pDt, int pCurrentCommandID, bool pCurrentCommandFinished)
    {
        bool localDriver = this == GetGame().GetPlayer() || this == HCDriverMovement.Owner;
        if (localDriver)
        {
            HCDriverMovement.CommandId = pCurrentCommandID;
            if (HCDriverMovement.Guard(this, pDt) && HCDriverMovement.Variant == HCDriverMovement.PRE_SUPER) { HCDriverMovement.Consume(this); }
        }
        super.CommandHandler(pDt, pCurrentCommandID, pCurrentCommandFinished);
        if (localDriver && HCDriverMovement.Variant != HCDriverMovement.PRE_SUPER)
        {
            // Recheck command/death/control transitions made by super without aging the lease twice.
            if (HCDriverMovement.Guard(this, 0)) { HCDriverMovement.Consume(this); }
        }
    }
}
#endif
