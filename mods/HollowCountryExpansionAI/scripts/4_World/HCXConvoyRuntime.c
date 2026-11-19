// #210 road branch: an HC-38 raid/column party already walking its situation
// route may borrow ONE qualified world car (never created, moved, repaired or
// refuelled here), drive bounded road waypoints, stop on contact/stall/timeout
// and dismount to walk. Any failure keeps or returns to the walking caravan.
// Opt out: $profile:HollowCountry/acceptance/convoys.disable.
// Expansion xref (read only, CC BY-NC-ND; nothing copied):
// ai Entities/CarScript.c:58-114 modded OnInput steers when an eAIBase sits in
// seat 0; Entities/AI/eAIBase.c:4404-4412 Notify_Transport, :7419-7425
// StartCommand_Vehicle; Classes/FSM/States/eAIState_Vehicles.c:27-59 followers
// take seats 1+ behind an IN formation leader that is in transport;
// Vehicles/eAIState_GetInVehicle.c:20-28 waits for an idle animation;
// Vehicles/eAIState_GetOutVehicle.c:9-15 GetOutVehicle; Classes/eAIGroup.c:213/241/251
// waypoints, :222/:304 GetWaypoints/GetWaypointBehaviour, :624 GetFormationState,
// :923 GetFormationLeader, :1123 IsInCombat, :1139/:1185 GetMember/Count;
// Entities/DayZPlayerImplement.c:234 GetGroup; core
// Entities/ManBase/DayZPlayerImplement.c:626 Expansion_IsAnimationIdle.
// Native scripts-1.30.164289: 3_Game/Vehicles/Car.c:32 CarGear, :105
// GetSpeedometerAbsolute (km/h), :185/:191/:203/:209 SetSteering/SetThrottle/
// SetBrake/SetHandbrake, :230/:233/:236 EngineIsOn/EngineStart/EngineStop,
// :248/:260 GetGear/ShiftTo, :345/:348 WheelCount/WheelCountPresent;
// Transport.c:175/178/190 HasCrew/CrewSize/CrewMember, :200 CrewEntryWS, :356
// OnInput, :607 IsFlipped; human.c:722 GetOutVehicle, :1528 GetCommand_Vehicle;
// Man.c:859 IsInTransport; EnEntity.c:571 GetParent; Object.c:287/:314/:517/:981
// GetPosition/GetDirection/IsAlive/IsDamageDestroyed; EntityAI.c:1884 GetInventory;
// Inventory.c:138 GetCargo; Cargo.c:28 GetItemCount; 4_World/Entities/Vehicles/
// CarScript.c:1041 OnInput, :1793 CheckOperationalState; Global/Game.c:930
// GetObjectsAtPosition3D, :1535 GetTime; 1_Core/proto/EnMath3D.c:484
// AngleFromPosition (radians); EnSystem.c:397 FileExist; EnDebug.c:96 Print.
// Server-side seating, AI driving physics, door use, replication and two-client
// visibility are all unobserved: runtime=PENDING.
class HCXConvoyRun
{
    string mHCId;
    string mHCPhase = "seek";
    string mHCReason;
    string mHCNote;
    eAIGroup mHCGroup;
    eAIBase mHCLeader;
    CarScript mHCCar;
    HCConvoyPolicy mHCPolicy;
    eAIWaypointBehavior mHCBehaviour;
    ref array<vector> mHCWalk = new array<vector>;
    ref HCXConvoyRoute mHCRoute = new HCXConvoyRoute;
    ref HCConvoyControl mHCControl = new HCConvoyControl;
    vector mHCProgressPos;
    vector mHCDoor;
    int mHCIndex;
    int mHCPhaseAt;
    int mHCScanAt;
    int mHCScans;
    int mHCProgressAt;
    int mHCExitTries;
    bool mHCDrove;
    bool mHCReleased;
    bool mHCForeign;

    bool HCOpen(string id, eAIGroup group, HCConvoyPolicy policy, int now)
    {
        if (!group || !policy) { return false; }
        mHCId = id;
        mHCGroup = group;
        mHCPolicy = policy;
        mHCLeader = eAIBase.Cast(group.GetFormationLeader());
        if (!mHCLeader) { return false; }
        if (!mHCLeader.IsAlive()) { return false; }
        array<vector> route = group.GetWaypoints();
        if (!route || route.Count() < 1) { return false; }
        foreach (vector point : route) { mHCWalk.Insert(point); }
        mHCBehaviour = group.GetWaypointBehaviour();
        mHCPhase = "seek";
        mHCPhaseAt = now;
        return true;
    }

    void HCStep(int now)
    {
        if (HCHolding() && HCForeignDriver())
        {
            HCYield(now);
            return;
        }
        if (mHCPhase == "seek") { HCSeek(now); }
        else if (mHCPhase == "approach") { HCApproach(now); }
        else if (mHCPhase == "board") { HCBoard(now); }
        else if (mHCPhase == "drive") { HCDrive(now); }
        else if (mHCPhase == "stop") { HCStopStep(now); }
        else if (mHCPhase == "exit") { HCExit(now); }
    }

    void HCPhase(string phase, int now)
    {
        mHCPhase = phase;
        mHCPhaseAt = now;
    }

    void HCNote(string reason)
    {
        if (mHCNote == reason) { return; }
        mHCNote = reason;
        Print("[HC Convoy] " + reason + " road_branch=walking_caravan runtime=PENDING");
    }

    bool HCAlive()
    {
        if (!mHCLeader) { return false; }
        return mHCLeader.IsAlive();
    }

    // Phases in which this run may write car inputs.
    bool HCHolding()
    {
        if (mHCForeign || !mHCCar) { return false; }
        return mHCPhase == "board" || mHCPhase == "drive" || mHCPhase == "stop" || mHCPhase == "exit";
    }

    // Seat 0 holding anyone but our bound AI leader (a player or any other
    // human) means the car is theirs: stop writing to it at once.
    bool HCForeignDriver()
    {
        Human driver = mHCCar.CrewMember(0);
        if (!driver) { return false; }
        return driver != mHCLeader;
    }

    // Release the car without a brake, handbrake or engine write; only our own
    // seated members are asked to leave through the native get-out command.
    void HCYield(int now)
    {
        mHCForeign = true;
        mHCReason = "CONVOY_FOREIGN_DRIVER";
        Print("[HC Convoy] CONVOY_FOREIGN_DRIVER id=" + mHCId + " car_released road_branch=walking_caravan runtime=PENDING");
        HCExitCrew();
        mHCExitTries = 0;
        HCPhase("exit", now);
    }

    // Every living member still parented to the bound car.
    int HCSeatedCrew()
    {
        int seated = 0;
        int count = mHCGroup.Count();
        for (int index = 0; index < count; index++)
        {
            DayZPlayerImplement member = mHCGroup.GetMember(index);
            if (!member) { continue; }
            if (!member.IsAlive()) { continue; }
            if (member.GetParent() == mHCCar) { seated++; }
        }
        return seated;
    }

    void HCExitCrew()
    {
        int count = mHCGroup.Count();
        for (int index = 0; index < count; index++)
        {
            DayZPlayerImplement member = mHCGroup.GetMember(index);
            if (!member) { continue; }
            if (!member.IsAlive()) { continue; }
            if (member.GetParent() != mHCCar) { continue; }
            HumanCommandVehicle seat = member.GetCommand_Vehicle();
            if (seat) { seat.GetOutVehicle(); }
        }
    }

    vector HCDestination()
    {
        return mHCWalk[mHCWalk.Count() - 1];
    }

    int HCMembers()
    {
        int alive = 0;
        int count = mHCGroup.Count();
        for (int index = 0; index < count; index++)
        {
            DayZPlayerImplement member = mHCGroup.GetMember(index);
            if (member && member.IsAlive()) { alive++; }
        }
        return alive;
    }

    int HCAboard()
    {
        int seated = 0;
        int count = mHCGroup.Count();
        for (int index = 0; index < count; index++)
        {
            DayZPlayerImplement member = mHCGroup.GetMember(index);
            if (!member) { continue; }
            if (!member.IsAlive()) { continue; }
            if (member.GetParent() == mHCCar) { seated++; }
        }
        return seated;
    }

    int HCCargo(CarScript car)
    {
        if (!car.GetInventory()) { return 0; }
        if (!car.GetInventory().GetCargo()) { return 0; }
        return car.GetInventory().GetCargo().GetItemCount();
    }

    vector HCDoor(CarScript car)
    {
        vector door;
        vector facing;
        car.CrewEntryWS(0, door, facing);
        return door;
    }

    string HCProblem(CarScript car)
    {
        HCXAISiteDirector director = HCXAISiteDirector.Active();
        if (!director) { return "CONVOY_OBSERVER_GATE_MISSING"; }
        float nearest = director.NearestPlayer(car.GetPosition());
        return HCConvoyRules.HCVehicleProblem(mHCPolicy, car.IsDamageDestroyed(), car.CheckOperationalState(), car.WheelCount(), car.WheelCountPresent(), car.HasCrew(), car.IsFlipped(), car.CrewSize(), HCMembers(), HCCargo(car), nearest);
    }

    // One bounded native radius query; only already-present CarScript objects
    // are considered. Nothing is spawned when no car qualifies.
    CarScript HCPick(vector origin)
    {
        array<Object> nearby = new array<Object>();
        array<CargoBase> proxies = new array<CargoBase>();
        GetGame().GetObjectsAtPosition3D(origin, mHCPolicy.SeekMeters, nearby, proxies);
        // Native query allocates before this bound; target-load cost unmeasured.
        if (nearby.Count() > mHCPolicy.SeekObjects)
        {
            HCNote("CONVOY_SEEK_SCAN_CAP");
            return null;
        }
        CarScript best = null;
        float bestGap = mHCPolicy.SeekMeters + 1;
        foreach (Object candidate : nearby)
        {
            CarScript car = CarScript.Cast(candidate);
            if (!car) { continue; }
            string problem = HCProblem(car);
            if (problem != "")
            {
                HCNote(problem);
                continue;
            }
            float gap = HCXConvoyRoute.HCFlat(origin, car.GetPosition());
            if (gap < bestGap)
            {
                best = car;
                bestGap = gap;
            }
        }
        return best;
    }

    void HCSeek(int now)
    {
        if (!HCAlive()) { HCWalk("CONVOY_PARTY_LOST"); return; }
        if (mHCScans > 0 && now - mHCScanAt < mHCPolicy.SeekSeconds * 1000) { return; }
        if (mHCScans >= mHCPolicy.MaxSeekScans) { HCWalk("CONVOY_NO_QUALIFIED_WORLD_VEHICLE"); return; }
        if (!HCServer.HCTickWork().HCTakeFor(HCUnitBudget.HC_WORK_SITUATIONS, 8)) { return; }
        mHCScanAt = now;
        mHCScans++;
        if (HCXConvoyRoute.HCFlat(mHCLeader.GetPosition(), HCDestination()) < mHCPolicy.MinDriveMeters) { HCWalk("CONVOY_DESTINATION_NEAR"); return; }
        CarScript car = HCPick(mHCLeader.GetPosition());
        if (!car) { return; }
        if (!mHCRoute.HCPlan(car.GetPosition(), HCDestination(), mHCPolicy)) { HCWalk(mHCRoute.mHCReason); return; }
        mHCCar = car;
        mHCDoor = HCDoor(car);
        // A one-point HALT is a native walking request to the driver door.
        mHCGroup.ClearWaypoints();
        mHCGroup.AddWaypoint(mHCDoor);
        mHCGroup.SetWaypointBehaviour(eAIWaypointBehavior.HALT);
        HCPhase("approach", now);
        Print("[HC Convoy] vehicle_selected id=" + mHCId + " runtime=PENDING");
    }

    void HCApproach(int now)
    {
        if (!HCAlive()) { HCWalk("CONVOY_PARTY_LOST"); return; }
        if (!mHCCar) { HCWalk("CONVOY_VEHICLE_LOST"); return; }
        string problem = HCProblem(mHCCar);
        if (problem != "") { HCWalk(problem); return; }
        mHCRoute.HCStep();
        if (mHCRoute.mHCPhase == "failed") { HCWalk(mHCRoute.mHCReason); return; }
        if (now - mHCPhaseAt > mHCPolicy.ApproachSeconds * 1000) { HCWalk("CONVOY_APPROACH_TIMEOUT"); return; }
        if (HCXConvoyRoute.HCFlat(mHCLeader.GetPosition(), mHCDoor) > mHCPolicy.BoardMeters) { return; }
        if (mHCRoute.mHCPhase != "ready") { return; }
        if (mHCGroup.GetFormationState() != eAIGroupFormationState.IN) { HCWalk("CONVOY_FORMATION_NOT_IN"); return; }
        if (!mHCLeader.Expansion_IsAnimationIdle()) { return; }
        // The leader stands at the door; the installed command handler plays
        // the native get-in. Followers board through Expansion's own FSM.
        mHCLeader.Notify_Transport(mHCCar, 0);
        HCPhase("board", now);
    }

    void HCBoard(int now)
    {
        if (!HCAlive() || !mHCCar) { HCStop("CONVOY_BOARD_LOST", now); return; }
        if (mHCGroup.IsInCombat()) { HCStop("CONVOY_CONTACT", now); return; }
        if (now - mHCPhaseAt > mHCPolicy.BoardSeconds * 1000) { HCStop("CONVOY_BOARD_TIMEOUT", now); return; }
        if (mHCCar.CrewMember(0) != mHCLeader) { return; }
        if (HCAboard() < HCMembers()) { return; }
        mHCIndex = 0;
        mHCProgressAt = now;
        mHCProgressPos = mHCCar.GetPosition();
        mHCDrove = true;
        HCPhase("drive", now);
        Print("[HC Convoy] driving id=" + mHCId + " runtime=PENDING");
    }

    bool HCForeignCrew()
    {
        int seats = mHCCar.CrewSize();
        for (int seat = 0; seat < seats; seat++)
        {
            Human crew = mHCCar.CrewMember(seat);
            if (!crew) { continue; }
            DayZPlayerImplement rider = DayZPlayerImplement.Cast(crew);
            if (!rider) { return true; }
            if (rider.GetGroup() != mHCGroup) { return true; }
        }
        return false;
    }

    string HCDriveProblem()
    {
        if (!mHCCar) { return "CONVOY_VEHICLE_LOST"; }
        if (mHCCar.IsDamageDestroyed()) { return "CONVOY_VEHICLE_DESTROYED"; }
        if (!HCAlive()) { return "CONVOY_DRIVER_LOST"; }
        if (mHCCar.CrewMember(0) != mHCLeader) { return "CONVOY_DRIVER_LOST"; }
        if (mHCCar.IsFlipped()) { return "CONVOY_VEHICLE_FLIPPED"; }
        if (!mHCCar.EngineIsOn() && !mHCCar.CheckOperationalState()) { return "CONVOY_VEHICLE_NOT_OPERATIONAL"; }
        if (mHCGroup.IsInCombat()) { return "CONVOY_CONTACT"; }
        if (HCForeignCrew()) { return "CONVOY_FOREIGN_CREW"; }
        return "";
    }

    vector HCLast()
    {
        array<vector> path = mHCRoute.mHCPath;
        return path[path.Count() - 1];
    }

    void HCDrive(int now)
    {
        string problem = HCDriveProblem();
        if (problem != "") { HCStop(problem, now); return; }
        vector position = mHCCar.GetPosition();
        if (mHCIndex >= mHCRoute.mHCPath.Count() - 1 && HCXConvoyRoute.HCFlat(position, HCLast()) <= mHCPolicy.ArriveMeters) { HCStop("CONVOY_ARRIVED", now); return; }
        float moved = HCXConvoyRoute.HCFlat(position, mHCProgressPos);
        if (moved >= mHCPolicy.StallMeters)
        {
            mHCProgressPos = position;
            mHCProgressAt = now;
        }
        else if (HCConvoyRules.HCStalled(mHCPolicy, moved, now - mHCProgressAt)) { HCStop("CONVOY_STALLED", now); return; }
        if (now - mHCPhaseAt > mHCPolicy.MaxDriveSeconds * 1000) { HCStop("CONVOY_DRIVE_TIMEOUT", now); return; }
    }

    void HCStop(string reason, int now)
    {
        mHCReason = reason;
        HCPhase("stop", now);
        Print("[HC Convoy] stopping id=" + mHCId + " reason=" + reason + " runtime=PENDING");
    }

    void HCStopStep(int now)
    {
        bool slow = true;
        if (mHCCar && mHCCar.GetSpeedometerAbsolute() > mHCPolicy.StopKmh) { slow = false; }
        if (!slow && now - mHCPhaseAt < mHCPolicy.StopSeconds * 1000) { return; }
        HCDismount();
        mHCExitTries = 0;
        HCPhase("exit", now);
    }

    // Brakes hold while anyone may still be seated; the crew leaves through the
    // native get-out command only. Never SetPosition, never delete the car.
    void HCDismount()
    {
        if (mHCCar && !mHCForeign)
        {
            mHCCar.SetThrottle(0);
            mHCCar.SetBrake(1);
            mHCCar.SetHandbrake(1);
            if (mHCCar.EngineIsOn()) { mHCCar.EngineStop(); }
        }
        if (mHCCar) { HCExitCrew(); }
    }

    // The run and its one slot stay held while any member is seated. Each
    // ExitSeconds window re-asks the still-seated members; after ExitAttempts
    // windows the run gives up with a named reason (never a teleport).
    void HCExit(int now)
    {
        if (mHCCar && HCSeatedCrew() > 0)
        {
            if (now - mHCPhaseAt <= mHCPolicy.ExitSeconds * 1000) { return; }
            mHCExitTries++;
            if (mHCExitTries >= mHCPolicy.ExitAttempts)
            {
                HCNote("CONVOY_DISMOUNT_TIMEOUT");
                if (mHCReleased)
                {
                    mHCPhase = "done";
                    return;
                }
                HCWalk("CONVOY_DISMOUNT_TIMEOUT");
                return;
            }
            HCDismount();
            mHCPhaseAt = now;
            return;
        }
        if (mHCReleased)
        {
            mHCPhase = "done";
            return;
        }
        HCWalk(mHCReason);
    }

    // Before driving the whole saved route resumes; after driving only the
    // situation destination remains, walked from wherever the car stopped.
    void HCWalk(string reason)
    {
        mHCReason = reason;
        mHCPhase = "walk";
        if (!mHCGroup) { return; }
        mHCGroup.ClearWaypoints();
        if (mHCDrove) { mHCGroup.AddWaypoint(HCDestination()); }
        else
        {
            array<vector> walk = mHCWalk;
            foreach (vector point : walk) { mHCGroup.AddWaypoint(point); }
        }
        mHCGroup.SetWaypointBehaviour(mHCBehaviour);
    }

    void HCRelease(int now)
    {
        mHCReleased = true;
        if (mHCPhase == "board" || mHCPhase == "drive" || mHCPhase == "stop" || mHCPhase == "exit")
        {
            if (!mHCForeign) { mHCReason = "CONVOY_SITUATION_ENDED"; }
            HCDismount();
            mHCExitTries = 0;
            HCPhase("exit", now);
            return;
        }
        mHCPhase = "done";
    }

    void HCHoldBrake()
    {
        HCConvoyRules.HCControl(mHCPolicy, 0, mHCCar.GetSpeedometerAbsolute(), 0, true, mHCControl);
        mHCCar.SetSteering(mHCControl.Steering);
        mHCCar.SetThrottle(mHCControl.Throttle);
        mHCCar.SetBrake(mHCControl.Brake);
        if (mHCCar.GetSpeedometerAbsolute() <= mHCPolicy.StopKmh) { mHCCar.SetHandbrake(1); }
    }

    // Called from CarScript.OnInput after super (native + Expansion) for this
    // one car only: O(1), no allocation, no scan.
    void HCInput()
    {
        if (!HCHolding()) { return; }
        // Checked before every write: a player in the driver seat owns the car.
        if (HCForeignDriver())
        {
            HCYield(GetGame().GetTime());
            return;
        }
        if (mHCPhase == "board" || mHCPhase == "stop" || mHCPhase == "exit")
        {
            HCHoldBrake();
            return;
        }
        if (mHCPhase != "drive") { return; }
        array<vector> path = mHCRoute.mHCPath;
        if (path.Count() < 1) { return; }
        vector position = mHCCar.GetPosition();
        if (mHCIndex < path.Count() - 1 && HCXConvoyRoute.HCFlat(position, path[mHCIndex]) <= mHCPolicy.NodeReachMeters) { mHCIndex++; }
        vector aim = path[mHCIndex];
        vector level = Vector(aim[0], position[1], aim[2]);
        float angle = Math3D.AngleFromPosition(position, mHCCar.GetDirection(), level);
        float remaining = HCXConvoyRoute.HCFlat(position, path[path.Count() - 1]);
        HCConvoyRules.HCControl(mHCPolicy, angle, mHCCar.GetSpeedometerAbsolute(), remaining, false, mHCControl);
        if (!mHCCar.EngineIsOn()) { mHCCar.EngineStart(); }
        if (mHCCar.GetGear() != CarGear.FIRST) { mHCCar.ShiftTo(CarGear.FIRST); }
        mHCCar.SetSteering(mHCControl.Steering);
        mHCCar.SetThrottle(mHCControl.Throttle);
        mHCCar.SetBrake(mHCControl.Brake);
        mHCCar.SetHandbrake(0);
    }
}

class HCXConvoyService
{
    protected static ref HCXConvoyService s_Service;
    ref HCXConvoyRun mHCRun;
    ref HCOperationalStatus mHCStatus = new HCOperationalStatus;
    HCConvoyPolicy mHCPolicy;
    bool mHCDisabled;
    string mHCRefused;
    string mHCLogged;

    static HCXConvoyService HCGet() { return s_Service; }

    static void HCOpenService()
    {
        if (s_Service) { return; }
        s_Service = new HCXConvoyService;
        s_Service.HCAdmit();
    }

    static void HCCloseService()
    {
        if (!s_Service) { return; }
        if (s_Service.mHCRun) { s_Service.mHCRun.HCRelease(GetGame().GetTime()); }
        s_Service = null;
    }

    void HCAdmit()
    {
        mHCDisabled = FileExist("$profile:HollowCountry/acceptance/convoys.disable");
        Print(HCV2Admission.Line("Convoys", !mHCDisabled, "convoys", false) + " runtime=PENDING");
        if (!mHCDisabled) { mHCPolicy = HCConvoyPolicy.HCGet(); }
        HCRefreshStatus();
    }

    bool HCRefuse(string reason)
    {
        if (mHCRefused == reason) { return false; }
        mHCRefused = reason;
        Print("[HC Convoy] " + reason + " road_branch=walking_caravan runtime=PENDING");
        return false;
    }

    string HCRoads()
    {
        HCXAICaravanRoads roads = HCXAICaravanRoads.HCGet();
        if (!roads) { return "CONVOY_ROAD_NETWORK_NOT_OPENED"; }
        if (roads.Phase == "cold" || roads.Phase == "loading") { return "CONVOY_ROAD_NETWORK_LOADING"; }
        if (roads.Phase == "failed") { return "CONVOY_ROAD_NETWORK_UNAVAILABLE"; }
        if (roads.Nodes.Count() < 2) { return "CONVOY_ROAD_NETWORK_UNAVAILABLE"; }
        return "";
    }

    void HCRefreshStatus()
    {
        string state = "ready";
        string reason = "convoy_world_vehicle_driving_native_acceptance_pending";
        string roads = HCRoads();
        if (mHCDisabled)
        {
            state = "off";
            reason = "operator_disabled";
        }
        else if (!mHCPolicy)
        {
            state = "refused";
            reason = "CONVOY_POLICY_INVALID";
        }
        else if (roads == "CONVOY_ROAD_NETWORK_LOADING")
        {
            state = "requested";
            reason = roads;
        }
        else if (roads != "")
        {
            state = "degraded";
            reason = roads;
        }
        mHCStatus.HCPublish(state, reason);
        string line = state + " reason=" + reason;
        if (line == mHCLogged) { return; }
        mHCLogged = line;
        Print("[HC Convoy] status=" + line + " runtime=PENDING");
    }

    bool HCOffer(string id, string profile, eAIGroup group)
    {
        if (mHCDisabled || !mHCPolicy) { return false; }
        if (profile != "raid" && profile != "column") { return false; }
        // MaxConvoys is validated to exactly one run slot.
        if (mHCRun) { return HCRefuse("CONVOY_CAP"); }
        string roads = HCRoads();
        if (roads != "") { return HCRefuse(roads); }
        HCXConvoyRun run = new HCXConvoyRun;
        if (!run.HCOpen(id, group, mHCPolicy, GetGame().GetTime())) { return HCRefuse("CONVOY_PARTY_NOT_QUALIFIED"); }
        mHCRun = run;
        mHCRefused = "";
        Print("[HC Convoy] offered id=" + id + " profile=" + profile + " runtime=PENDING");
        return true;
    }

    // Cheap no-op when off or idle: no scan, no allocation.
    void HCStep()
    {
        if (mHCDisabled) { return; }
        HCRefreshStatus();
        if (!mHCRun) { return; }
        mHCRun.HCStep(GetGame().GetTime());
        if (mHCRun.mHCPhase != "walk" && mHCRun.mHCPhase != "done") { return; }
        Print("[HC Convoy] ended id=" + mHCRun.mHCId + " reason=" + mHCRun.mHCReason + " road_branch=walking_caravan runtime=PENDING");
        mHCRun = null;
    }

    void HCRelease(string id)
    {
        if (!mHCRun || mHCRun.mHCId != id) { return; }
        mHCRun.HCRelease(GetGame().GetTime());
        if (mHCRun.mHCPhase == "done") { mHCRun = null; }
    }

    void HCInput(CarScript car)
    {
        if (!mHCRun) { return; }
        if (mHCRun.mHCCar != car) { return; }
        mHCRun.HCInput();
    }
}

// Static hooks for HCW38SituationRuntime (lead-owned) and status snapshots.
class HCXConvoyRuntime
{
    static bool HCOffer(HCW38SituationBinding binding)
    {
        HCXConvoyService service = HCXConvoyService.HCGet();
        if (!service || !binding) { return false; }
        return service.HCOffer(binding.Id, binding.Profile, binding.Group);
    }

    static void HCRelease(string id)
    {
        HCXConvoyService service = HCXConvoyService.HCGet();
        if (service) { service.HCRelease(id); }
    }

    static void HCInput(CarScript car)
    {
        HCXConvoyService service = HCXConvoyService.HCGet();
        if (service) { service.HCInput(car); }
    }

    static HCOperationalStatus HCGetOperationalStatus()
    {
        HCXConvoyService service = HCXConvoyService.HCGet();
        if (!service) { return null; }
        return service.mHCStatus;
    }
}

// Uses the existing adapter lifecycle; no additional module slot.
modded class HCXAIAdapter
{
    override void OnStart(HCSettings settings)
    {
        super.OnStart(settings);
        if (!GetGame() || !GetGame().IsServer() || HCXAIService.Adapter() != this)
        {
            Print("[HC Convoy] CONVOY_ADAPTER_NOT_SERVER_OWNER road_branch=walking_caravan runtime=PENDING");
            return;
        }
        HCXConvoyService.HCOpenService();
    }

    override void OnTick(float deltaTime)
    {
        super.OnTick(deltaTime);
        if (HCXAIService.Adapter() != this) { return; }
        HCXConvoyService service = HCXConvoyService.HCGet();
        if (service) { service.HCStep(); }
    }

    override void OnStop()
    {
        if (HCXAIService.Adapter() == this) { HCXConvoyService.HCCloseService(); }
        super.OnStop();
    }
}

// Runs after the native and Expansion input links (requiredAddons order), so
// the convoy's bounded values are the last written for its one car.
modded class CarScript
{
    override void OnInput(float dt)
    {
        super.OnInput(dt);
        HCXConvoyRuntime.HCInput(this);
    }
}
