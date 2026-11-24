// Dev-only test addon (never shipped). Get in, start, drive, stop and get out of a car for the scripted
// client driver (kind vehicle). The player walks to the driver door, looks at it (a real raycast
// target) and uses the vanilla get-in, start-engine, stop-engine and get-out actions; the pedals go
// through HCDriverCarInput (4_World, the modded CarScript.OnInput after super). No car is spawned,
// repaired, refuelled or moved by script.
// Native scripts-1.30.164289 proofs:
//  car      3_Game/Global/Game.c:930 GetObjectsAtPosition3D (one query); 3_Game/Vehicles/Transport.c:178
//           CrewSize, :182 CrewPositionIndex, :186 CrewMemberIndex, :190 CrewMember, :194 CrewDriver,
//           :200 CrewEntryWS, :685 GetSeatAnimationType (the driver seat is the crew index whose seat
//           is DayZPlayerConstants.VEHICLESEAT_DRIVER, e.g. InheritedCars/OffroadHatchback.c:121);
//           3_Game/Vehicles/Car.c EngineIsOn, :102 GetSpeedometer, :105 GetSpeedometerAbsolute.
//  actions  Interact/ActionGetInTransport.c:1 (condition: CCTCursorNoRuinCheck target, crew index of
//           the target component free, CanReachSeatFromDoors); Continuous/Vehicles/ActionStartEngine.c:9
//           (driver only; the engine's own OnBeforeEngineStart decides whether it starts);
//           SingleUse/Vehicles/ActionStopEngine.c:1 (below 8 km/h); Interact/ActionGetOutTransport.c:23;
//           3_Game/human.c:1528 GetCommand_Vehicle, HumanCommandVehicle IsGettingIn / IsGettingOut;
//           ActionBase.c:968 Can, ActionManagerClient.c:804 PerformActionStart; DayZPhysics.c:199
//           RaycastRV from MiscGameplayFunctions.c:778 GetPlayerHeadPosition.
// Bounded: one object query, at most RAYS rays (one per frame), fixed waits per stage, a drive of
// `seconds` (at most 60) and a braking stop of at most 8 s; nothing allocated per frame.
class HCDriverVehicle
{
    static const int V_FIND = 0;
    static const int V_WALK = 1;
    static const int V_DOOR = 2;
    static const int V_SEAT = 3;
    static const int V_ENGINE = 4;
    static const int V_DRIVE = 5;
    static const int V_BRAKE = 6;
    static const int V_STOP = 7;
    static const int V_OUT = 8;
    static const int RAYS = 30;
    static const int MAX_CREW = 8;

    protected float m_Range;
    protected float m_Seconds;
    protected float m_Throttle;
    protected float m_Timeout;
    protected float m_Elapsed;
    protected int m_Phase;
    protected float m_PhaseAge;
    protected CarScript m_Car;
    protected int m_DriverSeat;
    protected int m_Ray;
    protected bool m_Started;
    protected bool m_Seated;
    protected bool m_Engine;
    protected bool m_Out;
    protected float m_Drove;
    protected vector m_From;
    protected float m_TopSpeed;
    protected string m_Note;
    protected ref ActionTarget m_Target;
    protected ref ActionTarget m_None;
    protected ref array<Object> m_Near = new array<Object>;
    protected ref array<CargoBase> m_NearCargo = new array<CargoBase>;
    protected ref set<Object> m_Hits = new set<Object>;
    protected string m_Detail;

    string Detail()
    {
        return m_Detail;
    }

    void Begin(HCDriverStep step)
    {
        m_Range = Math.Clamp(step.range_m, 5.0, 80.0);
        m_Seconds = Math.Clamp(step.seconds, 2.0, 60.0);
        m_Throttle = Math.Clamp(step.throttle, 0.1, 1.0);
        m_Timeout = Math.Max(step.timeout_s, 30.0);
        m_Elapsed = 0;
        m_Phase = HCDriverVehicle.V_FIND;
        m_PhaseAge = 0;
        m_Car = null;
        m_DriverSeat = -1;
        m_Ray = 0;
        m_Started = false;
        m_Seated = false;
        m_Engine = false;
        m_Out = false;
        m_Drove = 0;
        m_TopSpeed = 0;
        m_Note = "";
        m_Target = null;
        m_Detail = "";
        HCDriverCarInput.Stop();
    }

    // Takes the feet off the pedals; safe at any time.
    void Release()
    {
        HCDriverCarInput.Stop();
    }

    protected string Tally()
    {
        int seated = 0;
        if (m_Seated) { seated = 1; }
        int engine = 0;
        if (m_Engine) { engine = 1; }
        int left = 0;
        if (m_Out) { left = 1; }
        return "seated=" + seated.ToString() + " engine=" + engine.ToString() + " drove_m=" + Math.Round(m_Drove).ToString() + " top_kmh=" + Math.Round(m_TopSpeed).ToString() + " out=" + left.ToString();
    }

    protected int End(PlayerBase player, HCDriverWalker walker, int code, string prefix)
    {
        HCDriverCarInput.Stop();
        walker.Release(player);
        if (player)
        {
            ActionManagerClient manager = ActionManagerClient.Cast(player.GetActionManager());
            if (manager) { manager.SetIgnoreAutomaticInputEnd(false); }
        }
        string note = "";
        if (m_Note != "") { note = " note=" + m_Note; }
        m_Detail = prefix + Tally() + note;
        return code;
    }

    protected void Enter(int phase)
    {
        m_Phase = phase;
        m_PhaseAge = 0;
        m_Started = false;
    }

    protected int DriverSeat(CarScript car)
    {
        int count = Math.Min(car.CrewSize(), HCDriverVehicle.MAX_CREW);
        for (int index = 0; index < count; index++)
        {
            if (car.GetSeatAnimationType(index) == DayZPlayerConstants.VEHICLESEAT_DRIVER) { return index; }
        }
        return -1;
    }

    // Nearest intact car with a free driver seat inside the range.
    protected CarScript FindCar(PlayerBase player)
    {
        m_Near.Clear();
        m_NearCargo.Clear();
        GetGame().GetObjectsAtPosition3D(player.GetPosition(), m_Range, m_Near, m_NearCargo);
        CarScript best;
        float bestDistance = 1000000;
        int count = Math.Min(m_Near.Count(), 512);
        for (int index = 0; index < count; index++)
        {
            CarScript car = CarScript.Cast(m_Near[index]);
            if (!car || car.IsRuined() || car.IsPendingDeletion()) { continue; }
            int seat = DriverSeat(car);
            if (seat < 0 || car.CrewMember(seat)) { continue; }
            float distance = vector.Distance(player.GetPosition(), car.GetPosition());
            if (distance < bestDistance)
            {
                bestDistance = distance;
                best = car;
            }
        }
        return best;
    }

    // One ray per frame from the head through the driver door toward the car body, a 5 x 6 grid of
    // heights and side offsets; true once the hit component is the driver seat and the get-in may run.
    protected bool LookAtDoor(PlayerBase player, ActionBase getIn)
    {
        int column = m_Ray % 5;
        int row = (m_Ray / 5) % 6;
        m_Ray++;
        vector entry;
        vector entryDir;
        m_Car.CrewEntryWS(m_DriverSeat, entry, entryDir);
        vector center = m_Car.GetPosition();
        vector side = center - entry;
        side[1] = 0;
        float length = side.Length();
        if (length < 0.1) { return false; }
        side = side / length;
        vector across = Vector(side[2], 0, -side[0]);
        vector aim = entry + side * 0.8 + across * ((column - 2) * 0.35) + Vector(0, 0.3 + row * 0.25, 0);
        vector begin = MiscGameplayFunctions.GetPlayerHeadPosition(player);
        vector end = begin + (aim - begin) * 1.5;
        vector contactPos;
        vector contactDir;
        int contactComponent;
        m_Hits.Clear();
        if (!DayZPhysics.RaycastRV(begin, end, contactPos, contactDir, contactComponent, m_Hits, null, player, true)) { return false; }
        // Sorted: the contact component belongs to the nearest hit, which has to be the car itself.
        if (m_Hits.Count() == 0 || m_Hits.Get(0) != m_Car) { return false; }
        if (m_Car.CrewPositionIndex(contactComponent) != m_DriverSeat) { return false; }
        ActionTarget candidate = new ActionTarget(m_Car, null, contactComponent, contactPos, 1.0);
        if (!getIn.Can(player, candidate, null)) { return false; }
        m_Target = candidate;
        return true;
    }

    protected void Start(ActionManagerClient manager, ActionBase action, ActionTarget target)
    {
        manager.SetIgnoreAutomaticInputEnd(true);
        manager.PerformActionStart(action, target, null);
        m_Started = true;
    }

    int Tick(PlayerBase player, float dt, HCDriverWalker walker)
    {
        if (!player || !player.IsAlive() || player.IsUnconscious()) { return End(player, walker, HCDriverResult.REFUSED, "player-unavailable "); }
        ActionManagerClient manager = ActionManagerClient.Cast(player.GetActionManager());
        if (!manager) { return End(player, walker, HCDriverResult.UNSUPPORTED, "no-client-action-manager "); }
        if (!m_None) { m_None = new ActionTarget(null, null, -1, vector.Zero, -1.0); }
        m_Elapsed = m_Elapsed + dt;
        m_PhaseAge = m_PhaseAge + dt;
        HumanCommandVehicle vehicle = player.GetCommand_Vehicle();
        if (m_Elapsed > m_Timeout && m_Phase < HCDriverVehicle.V_BRAKE)
        {
            // Out of time: stop driving and get out the normal way before the step ends.
            if (!m_Seated) { return End(player, walker, HCDriverResult.TIMEOUT, "phase=" + m_Phase.ToString() + " "); }
            m_Note = "timeout";
            HCDriverCarInput.Drive(m_Car, 0, 0, 1.0);
            Enter(HCDriverVehicle.V_BRAKE);
        }
        if (m_Elapsed > m_Timeout + 30.0) { return End(player, walker, HCDriverResult.TIMEOUT, "phase=" + m_Phase.ToString() + " "); }
        if (m_Phase == HCDriverVehicle.V_FIND)
        {
            if (vehicle) { return End(player, walker, HCDriverResult.REFUSED, "already-in-a-vehicle "); }
            if (player.IsRestrained()) { return End(player, walker, HCDriverResult.REFUSED, "restrained "); }
            m_Car = FindCar(player);
            if (!m_Car) { return End(player, walker, HCDriverResult.REFUSED, "no-free-car-within-" + Math.Round(m_Range).ToString() + "m "); }
            m_DriverSeat = DriverSeat(m_Car);
            vector entry;
            vector entryDir;
            m_Car.CrewEntryWS(m_DriverSeat, entry, entryDir);
            walker.Begin(entry[0], entry[2], "walk", 0.8, 90);
            Enter(HCDriverVehicle.V_WALK);
            return HCDriverResult.RUNNING;
        }
        if (!m_Car || m_Car.IsPendingDeletion()) { return End(player, walker, HCDriverResult.REFUSED, "car-gone "); }
        if (m_Phase == HCDriverVehicle.V_WALK)
        {
            int walked = walker.Update(player, dt);
            if (walked == HCDriverResult.RUNNING) { return walked; }
            walker.Release(player);
            // A short miss is fine: the door ray scan decides whether the seat is in reach.
            m_Ray = 0;
            Enter(HCDriverVehicle.V_DOOR);
            return HCDriverResult.RUNNING;
        }
        if (m_Phase == HCDriverVehicle.V_DOOR)
        {
            if (!m_Started)
            {
                ActionBase getIn = ActionManagerBase.GetAction(ActionGetInTransport);
                if (!getIn) { return End(player, walker, HCDriverResult.UNSUPPORTED, "no-get-in-action "); }
                if (m_Ray >= HCDriverVehicle.RAYS) { return End(player, walker, HCDriverResult.REFUSED, "driver-door-not-usable "); }
                if (!LookAtDoor(player, getIn)) { return HCDriverResult.RUNNING; }
                Start(manager, getIn, m_Target);
                return HCDriverResult.RUNNING;
            }
            if (vehicle && !vehicle.IsGettingIn() && m_Car.CrewDriver() == player)
            {
                manager.SetIgnoreAutomaticInputEnd(false);
                m_Seated = true;
                Enter(HCDriverVehicle.V_ENGINE);
                return HCDriverResult.RUNNING;
            }
            if (m_PhaseAge < 12.0) { return HCDriverResult.RUNNING; }
            return End(player, walker, HCDriverResult.REFUSED, "get-in-not-completed ");
        }
        if (!vehicle && m_Phase < HCDriverVehicle.V_OUT) { return End(player, walker, HCDriverResult.REFUSED, "left-the-car "); }
        if (m_Phase == HCDriverVehicle.V_ENGINE)
        {
            if (m_Car.EngineIsOn())
            {
                m_Engine = true;
                manager.SetIgnoreAutomaticInputEnd(false);
                m_From = m_Car.GetPosition();
                HCDriverCarInput.Drive(m_Car, m_Throttle, 0, 0);
                Enter(HCDriverVehicle.V_DRIVE);
                return HCDriverResult.RUNNING;
            }
            if (!m_Started)
            {
                ActionBase startEngine = ActionManagerBase.GetAction(ActionStartEngine);
                if (startEngine && startEngine.Can(player, m_None, null))
                {
                    Start(manager, startEngine, m_None);
                    return HCDriverResult.RUNNING;
                }
                m_Note = "start-not-allowed";
                Enter(HCDriverVehicle.V_OUT);
                return HCDriverResult.RUNNING;
            }
            if (manager.GetRunningAction() && m_PhaseAge < 12.0) { return HCDriverResult.RUNNING; }
            if (m_PhaseAge < 3.0) { return HCDriverResult.RUNNING; }
            // The engine refused (missing battery, plugs or fuel decide in OnBeforeEngineStart).
            manager.SetIgnoreAutomaticInputEnd(false);
            m_Note = "engine-did-not-start";
            Enter(HCDriverVehicle.V_OUT);
            return HCDriverResult.RUNNING;
        }
        if (m_Phase == HCDriverVehicle.V_DRIVE)
        {
            float speed = m_Car.GetSpeedometerAbsolute();
            if (speed > m_TopSpeed) { m_TopSpeed = speed; }
            m_Drove = vector.Distance(m_From, m_Car.GetPosition());
            if (!m_Car.EngineIsOn()) { m_Note = "stalled"; }
            if (m_PhaseAge < m_Seconds && m_Car.EngineIsOn()) { return HCDriverResult.RUNNING; }
            HCDriverCarInput.Drive(m_Car, 0, 0, 1.0);
            Enter(HCDriverVehicle.V_BRAKE);
            return HCDriverResult.RUNNING;
        }
        if (m_Phase == HCDriverVehicle.V_BRAKE)
        {
            m_Drove = vector.Distance(m_From, m_Car.GetPosition());
            if (m_Car.GetSpeedometerAbsolute() > 1.0 && m_PhaseAge < 8.0) { return HCDriverResult.RUNNING; }
            Enter(HCDriverVehicle.V_STOP);
            return HCDriverResult.RUNNING;
        }
        if (m_Phase == HCDriverVehicle.V_STOP)
        {
            if (!m_Started)
            {
                ActionBase stopEngine = ActionManagerBase.GetAction(ActionStopEngine);
                if (m_Car.EngineIsOn() && stopEngine && stopEngine.Can(player, m_None, null))
                {
                    Start(manager, stopEngine, m_None);
                    return HCDriverResult.RUNNING;
                }
                Enter(HCDriverVehicle.V_OUT);
                return HCDriverResult.RUNNING;
            }
            if ((manager.GetRunningAction() || m_Car.EngineIsOn()) && m_PhaseAge < 4.0) { return HCDriverResult.RUNNING; }
            manager.SetIgnoreAutomaticInputEnd(false);
            HCDriverCarInput.Stop();
            Enter(HCDriverVehicle.V_OUT);
            return HCDriverResult.RUNNING;
        }
        // V_OUT: the vanilla get-out; the step ends once the player stands outside.
        HCDriverCarInput.Stop();
        if (!vehicle)
        {
            m_Out = true;
            return End(player, walker, HCDriverResult.OK, "");
        }
        if (!m_Started)
        {
            if (vehicle.IsTransitioning() && m_PhaseAge < 6.0) { return HCDriverResult.RUNNING; }
            ActionBase getOut = ActionManagerBase.GetAction(ActionGetOutTransport);
            if (getOut && getOut.Can(player, m_None, null))
            {
                Start(manager, getOut, m_None);
                return HCDriverResult.RUNNING;
            }
            if (m_PhaseAge < 6.0) { return HCDriverResult.RUNNING; }
            return End(player, walker, HCDriverResult.REFUSED, "get-out-not-allowed ");
        }
        if (m_PhaseAge < 12.0) { return HCDriverResult.RUNNING; }
        return End(player, walker, HCDriverResult.REFUSED, "get-out-not-completed ");
    }
}
