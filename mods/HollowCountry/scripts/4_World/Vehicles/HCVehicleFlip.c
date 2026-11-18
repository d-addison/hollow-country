// #127. Read-only inspection of installed RaG Immersive Vehicles PBO
// (3105330157/Addons/rag_immersive_vehicles.pbo, 2026-11-18):
// rag_car_jack.c and RaGIVVehicleComponent.c implement wheel jacking, no recovery
// action. Native ActionPushCar.c:49 applies a longitudinal push; CarScript.c:2321
// registers it. Neither provides this bounded overturn-recovery action.
// Native scripts-1.30.164289: 1_Core/proto/EnPhysics.c:104 GetVelocity,
// :122 dBodyGetMass, :125 dBodyApplyTorqueImpulse, :141 dBodyApplyImpulse,
// :158 dBodyGetAngularVelocity; EnEntity.c:288 GetTransform;
// 3_Game/Entities/Object.c:215/287/370/874/1219 pending/position/box/model/ruin;
// 3_Game/Vehicles/Car.c:230 EngineIsOn; Transport.c:178/190 CrewSize/CrewMember;
// 3_Game/Global/Game.c:914/945/1120 ticktime/players/server;
// 3_Game/Entities/Man.c:21 GetIdentity; 4_World/Entities/ManBase/PlayerBase.c:
// :2219/3925/6733 restrained/unconscious/hands; DayZPlayerImplement.c:468 vehicle;
// 4_World/Entities/ItemBase/Gear/Tools/Crowbar.c:1 vanilla tool;
// 1_Core/proto/EnScript.c:94/380/399/407/470 cast/count/get/insert/remove;
// EnMath3D.c:18 Vector; gameplay.c:636 GetGame;
// EnConvert.c:182/210 LengthSq/DistanceSq; EnDebug.c:96 Print; EnConvert.c:30 ToString.
// Tick bound: one of <=4 jobs (cursor), one GetPlayers snapshot capped at 32,
// <=32 people + <=16 seats; maximum 3 impulse pairs/job within 12 seconds.
// Idle/off returns before allocation or player queries. No entity transforms,
// velocities or vanilla persistence are overwritten. Force budgets provisional.
class HCFlipJob
{
    CarScript Vehicle;
    PlayerBase Actor;
    int Pulses;
    float Until;
}
class HCVehicleFlipModule : HCModule
{
    protected static HCVehicleFlipModule s_Instance;
    protected ref array<ref HCFlipJob> m_Jobs;
    protected ref array<Man> m_Players;
    protected int m_Cursor;
    protected bool m_AdmissionPrinted;
    static HCVehicleFlipModule Get() { return s_Instance; }
    override string GetName() { return "VehicleFlip"; }
    override bool IsEnabled(HCSettings settings) { return settings && settings.EnableVehicleFlip; }
    override void OnStart(HCSettings settings)
    {
        if (!IsEnabled(settings) || !GetGame().IsServer() || s_Instance) { return; }
        m_Jobs = new array<ref HCFlipJob>;
        m_Players = new array<Man>;
        s_Instance = this;
        if (!m_AdmissionPrinted)
        {
            Print(HCV2Admission.Line("VehicleFlip", true, "W5-127", false));
            m_AdmissionPrinted = true;
        }
    }
    static bool HCCandidate(PlayerBase actor, CarScript vehicle)
    {
        if (!actor || !vehicle || vehicle.IsPendingDeletion() || vehicle.IsRuined()) { return false; }
        if (!actor.IsAlive() || actor.IsUnconscious() || actor.IsRestrained() || actor.IsInVehicle()) { return false; }
        if (vehicle.EngineIsOn() || vector.DistanceSq(actor.GetPosition(), vehicle.GetPosition()) > 25) { return false; }
        vector transform[4];
        vehicle.GetTransform(transform);
        vector up = transform[1];
        if (!(up[1] < 0.3)) { return false; }
        if (!(GetVelocity(vehicle).LengthSq() <= 0.0625)) { return false; }
        return dBodyGetAngularVelocity(vehicle).LengthSq() <= 0.36;
    }
    protected bool HCReady(PlayerBase actor, CarScript vehicle)
    {
        if (!HCCandidate(actor, vehicle) || !actor.GetIdentity()) { return false; }
        int seats = vehicle.CrewSize();
        if (seats > 16) { return false; }
        for (int seat = 0; seat < seats; seat++)
        {
            if (vehicle.CrewMember(seat)) { return false; }
        }
        vector bounds[2];
        if (!vehicle.GetCollisionBox(bounds)) { return false; }
        vector lower = bounds[0] - Vector(0.6, 0.6, 0.6);
        vector upper = bounds[1] + Vector(0.6, 0.6, 0.6);
        int helpers;
        foreach (Man person : m_Players)
        {
            if (!person) { continue; }
            // Include dead/unconscious occupants and bystanders in clearance.
            vector modelPos = vehicle.WorldToModel(person.GetPosition() + Vector(0, 0.9, 0));
            bool insideX = modelPos[0] >= lower[0] && modelPos[0] <= upper[0];
            bool insideY = modelPos[1] >= lower[1] && modelPos[1] <= upper[1];
            bool insideZ = modelPos[2] >= lower[2] && modelPos[2] <= upper[2];
            if (insideX && insideY && insideZ) { return false; }
            PlayerBase helper = PlayerBase.Cast(person);
            if (!helper || !helper.GetIdentity() || !helper.IsAlive() || helper.IsUnconscious()) { continue; }
            if (helper.IsInVehicle() || helper.IsRestrained()) { continue; }
            if (vector.DistanceSq(helper.GetPosition(), vehicle.GetPosition()) <= 25) { helpers++; }
        }
        ItemBase tool = actor.GetItemInHands();
        bool hasTool = tool && Crowbar.Cast(tool) && !tool.IsRuined();
        return helpers >= 3 || hasTool;
    }
    bool HCQueue(PlayerBase actor, CarScript vehicle)
    {
        if (s_Instance != this || !GetGame().IsServer()) { return false; }
        if (!HCCandidate(actor, vehicle) || m_Jobs.Count() >= 4) { return false; }
        float now = GetGame().GetTickTime();
        if (now < vehicle.m_HCFlipAfter) { return false; }
        foreach (HCFlipJob pending : m_Jobs)
        {
            if (pending.Vehicle == vehicle) { return false; }
        }
        m_Players.Clear();
        GetGame().GetPlayers(m_Players);
        if (m_Players.Count() > 32 || !HCReady(actor, vehicle)) { return false; }
        HCFlipJob job = new HCFlipJob;
        job.Actor = actor;
        job.Vehicle = vehicle;
        job.Until = now + 12;
        m_Jobs.Insert(job);
        vehicle.m_HCFlipAfter = now + 30;
        Print("[HollowCountry] W5 vehicle-flip queued pulses<=3 cooldown=30");
        return true;
    }
    override void OnTick(float deltaTime)
    {
        if (s_Instance != this || !m_Jobs || m_Jobs.Count() == 0 || !(deltaTime > 0)) { return; }
        if (m_Cursor >= m_Jobs.Count()) { m_Cursor = 0; }
        HCFlipJob job = m_Jobs.Get(m_Cursor);
        float now = GetGame().GetTickTime();
        m_Players.Clear();
        GetGame().GetPlayers(m_Players);
        bool safe = m_Players.Count() <= 32 && now >= 0 && now < job.Until;
        if (safe) { safe = HCReady(job.Actor, job.Vehicle); }
        if (!safe)
        {
            Print("[HollowCountry] W5 vehicle-flip ended safety-or-expiry");
            m_Jobs.RemoveOrdered(m_Cursor);
            return;
        }
        float mass = dBodyGetMass(job.Vehicle);
        if (!(mass > 0 && mass <= 5000)) { m_Jobs.RemoveOrdered(m_Cursor); return; }
        vector transform[4];
        job.Vehicle.GetTransform(transform);
        vector right = transform[0];
        float direction = 1;
        if (right[1] > 0) { direction = -1; }
        // Rotation about forward changes up in the negative right direction.
        // Select the sign that raises world up; fully inverted chooses one side.
        // Each torque <= mass*0.4 (<=2000); lift <= mass*0.1 (<=500).
        vector axis = transform[2];
        dBodyApplyTorqueImpulse(job.Vehicle, axis * mass * 0.4 * direction);
        dBodyApplyImpulse(job.Vehicle, Vector(0, mass * 0.1, 0));
        job.Pulses++;
        Print("[HollowCountry] W5 vehicle-flip impulse pulse=" + job.Pulses.ToString());
        if (job.Pulses >= 3) { m_Jobs.RemoveOrdered(m_Cursor); }
        else { m_Cursor++; }
    }
    override void OnStop()
    {
        if (s_Instance == this) { s_Instance = null; }
        m_Jobs = null;
        m_Players = null;
    }
}
modded class CarScript
{
    // Transient target cooldown; deliberately absent from native entity storage.
    float m_HCFlipAfter;
}
modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        Register(new HCVehicleFlipModule);
    }
}
