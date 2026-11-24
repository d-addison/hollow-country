// Dev-only test addon (never shipped). The scripted client driver's pedals and wheel for the one car
// the local player is driving (kind vehicle). The driver step fills HCDriverCarInput; the modded
// CarScript.OnInput below applies it after the vanilla input, exactly where the DIAG drive mode of
// CarScript.c:1041-1207 sets the same controls. Nothing runs on the server, for another car, for a
// car the local player is not driving, or when no driver step is active.
// Native scripts-1.30.164289 proofs: 3_Game/Vehicles/Transport.c:356 `void OnInput(float dt) {}`;
// 4_World/Entities/Vehicles/CarScript.c:1041 `override void OnInput(float dt)` (calls super at
// :1043); 3_Game/Vehicles/Car.c SetSteering(float, bool = false), SetThrottle(float),
// SetBrake(float, float = 0, bool = false), SetHandbrake(float), :248 GetGear, :260 ShiftTo(int), :266 GearboxGetType, CarGear
// (Car.c:32: REVERSE, NEUTRAL, FIRST, ...); Transport.c:194 CrewDriver. The setters are proto
// native and are only called, never overridden.
// Per frame: one comparison when idle; four native setter calls while driving.
class HCDriverCarInput
{
    static bool s_Active;
    static CarScript s_Car;
    static float s_Throttle;
    static float s_Steering;
    static float s_Brake;

    static void Drive(CarScript car, float throttle, float steering, float brake)
    {
        HCDriverCarInput.s_Car = car;
        HCDriverCarInput.s_Throttle = Math.Clamp(throttle, 0.0, 1.0);
        HCDriverCarInput.s_Steering = Math.Clamp(steering, -1.0, 1.0);
        HCDriverCarInput.s_Brake = Math.Clamp(brake, 0.0, 1.0);
        HCDriverCarInput.s_Active = false;
        if (car) { HCDriverCarInput.s_Active = true; }
    }

    static void Stop()
    {
        HCDriverCarInput.s_Active = false;
        HCDriverCarInput.s_Car = null;
        HCDriverCarInput.s_Throttle = 0;
        HCDriverCarInput.s_Steering = 0;
        HCDriverCarInput.s_Brake = 0;
    }
}

modded class CarScript
{
    override void OnInput(float dt)
    {
        super.OnInput(dt);
        if (!HCDriverCarInput.s_Active || HCDriverCarInput.s_Car != this) { return; }
        if (GetGame().IsDedicatedServer()) { return; }
        Man driver = GetGame().GetPlayer();
        if (!driver || CrewDriver() != driver) { return; }
        // Manual gearbox only, as the DIAG drive (CarScript.c:1159-1199) does: first gear to pull away; the
        // automatic box picks its own gear.
        if (GearboxGetType() == CarGearboxType.MANUAL && HCDriverCarInput.s_Throttle > 0 && GetGear() < CarGear.FIRST) { ShiftTo(CarGear.FIRST); }
        SetThrottle(HCDriverCarInput.s_Throttle);
        SetSteering(HCDriverCarInput.s_Steering);
        SetBrake(HCDriverCarInput.s_Brake);
        SetHandbrake(0.0);
    }
}
