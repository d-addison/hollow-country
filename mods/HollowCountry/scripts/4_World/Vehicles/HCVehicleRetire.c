// #363: upgrade-only retirement. No dependency symbols or calls. Installed
// vehicles_ground_landrover.pbo CfgVehicles: family base -> CarScript.
// AfterStoreLoad (EntityAI.c:1419) runs after children load; EEOnAfterLoad
// (EntityAI.c:1381) restores connected systems instead. The hook only queues.
class HCVehicleRetireJob
{
    CarScript Vehicle; // Weak: native deletion nulls this reference.
    int Moved;
    bool Waiting;
    int AttachmentCursor;
}

class HCVehicleRetire
{
    // wiring_audit ties this single string to dropped.retireBase and vehicles.
    static const string FAMILY_BASE = "Expansion_Landrover_Base";
    static const int QUEUE_CAP = 256;
    static const int MOVES_PER_TICK = 4;
    protected static ref array<ref HCVehicleRetireJob> s_Queue = new array<ref HCVehicleRetireJob>;
    protected static int s_Overflow;
    protected static bool s_Configured;
    protected static bool s_Enabled;

    static void Configure(bool enabled)
    {
        s_Configured = true;
        s_Enabled = enabled;
        if (!enabled) { s_Queue.Clear(); }
    }

    static void Enqueue(CarScript vehicle)
    {
        if (!GetGame() || !GetGame().IsServer() || !vehicle) { return; }
        if (s_Configured && !s_Enabled) { return; }
        if (!vehicle.IsKindOf(FAMILY_BASE)) { return; }
        if (s_Queue.Count() >= QUEUE_CAP) { s_Overflow++; return; }
        HCVehicleRetireJob job = new HCVehicleRetireJob;
        job.Vehicle = vehicle;
        s_Queue.Insert(job);
    }

    static array<ref HCVehicleRetireJob> Jobs() { return s_Queue; }
    static int Overflow() { return s_Overflow; }
}

class HCVehicleRetireModule : HCModule
{
    protected ref HCOperationalStatus m_Operational = new HCOperationalStatus;
    protected ref HCActivityCounters m_Activity = new HCActivityCounters("retired items_moved refused deferred");
    protected ref HCWorkBudget m_Budget = new HCWorkBudget;
    protected int m_Cursor;
    protected int m_Retired;
    protected int m_Moved;
    protected int m_Refused;
    protected int m_RefusalLines;
    protected int m_OverflowSeen;
    protected bool m_Running;
    protected bool m_UpgradeSeen;
    protected bool m_Summary;
    protected float m_Start;

    override string GetName() { return "VehicleRetire"; }
    override bool IsEnabled(HCSettings settings)
    {
        bool enabled = settings && settings.VehicleRetireEnabled;
        HCVehicleRetire.Configure(enabled);
        return enabled;
    }
    override void RegisterUses() { HCModuleReadiness.HCRegisterUse(GetName(), "retired"); }
    override HCOperationalStatus HCGetOperationalStatus()
    {
        HCModuleReadiness.HCDerive(m_Operational, m_Running, "", "", "vehicle_retire_hook_active");
        return m_Operational;
    }
    override void OnStart(HCSettings settings)
    {
        if (!GetGame().IsServer() || m_Running) { return; }
        m_Running = true;
        m_Start = GetGame().GetTickTime();
        Print("[HC Vehicles] retire started per_tick=4 cap=256 upgrade_only=true runtime=PENDING");
    }

    protected void Refuse(string reason)
    {
        m_Refused++;
        m_Activity.HCRefuse(reason);
        if (m_RefusalLines < 16)
        {
            m_RefusalLines++;
            Print("[HC Vehicles] retire_refused reason=" + reason);
        }
    }

    // One bounded player snapshot per visited vehicle; over-cap means wait, never
    // truncate the safety check. HasCrew includes dead/unconscious occupants.
    protected string WaitReason(CarScript vehicle)
    {
        if (vehicle.HasCrew()) { return "crew"; }
        if (vehicle.EngineIsOn()) { return "engine_on"; }
        array<Man> players = new array<Man>;
        GetGame().GetPlayers(players);
        if (players.Count() > 16) { return "player_cap"; }
        for (int index = 0; index < 16 && index < players.Count(); index++)
        {
            Man player = players[index];
            if (player && vector.DistanceSq(player.GetPosition(), vehicle.GetPosition()) <= 2500) { return "player_near"; }
        }
        return "";
    }

    // Cargo first, containers whole. A moved direct child carries every nested
    // descendant, so there is no recursive walk, index snapshot or copied item.
    protected EntityAI FirstChild(HCVehicleRetireJob job)
    {
        GameInventory inventory = job.Vehicle.GetInventory();
        CargoBase cargo = inventory.GetCargo();
        if (cargo && cargo.GetItemCount() > 0) { return cargo.GetItem(0); }
        int count = inventory.AttachmentCount();
        if (count == 0) { return null; }
        // Wheels last, with at most 16 attachment inspections per visit. A long
        // scan yields across ticks; removal resets the cursor as indices shift.
        for (int scan = 0; scan < 16; scan++)
        {
            if (job.AttachmentCursor >= count)
            {
                job.AttachmentCursor = 0;
                return inventory.GetAttachmentFromIndex(count - 1);
            }
            EntityAI attachment = inventory.GetAttachmentFromIndex(job.AttachmentCursor);
            job.AttachmentCursor++;
            if (attachment && !attachment.IsKindOf("CarWheel"))
            {
                job.AttachmentCursor = 0;
                return attachment;
            }
        }
        return null;
    }

    protected bool Empty(CarScript vehicle)
    {
        GameInventory inventory = vehicle.GetInventory();
        CargoBase cargo = inventory.GetCargo();
        return inventory.AttachmentCount() == 0 && (!cargo || cargo.GetItemCount() == 0);
    }

    // Four candidate points, about 2.55 m from the current vehicle centre. Geometry rays
    // ignore the vehicle but start at its centre; support and bounds are checked
    // before touching the inventory. Refuse unusual/wide vehicles and water.
    protected bool Destination(CarScript vehicle, EntityAI item, int moved, out InventoryLocation destination)
    {
        vector lower;
        vector upper;
        float bottomY;
        if (!HCGroundSnap.Bounds(vehicle, lower, upper, bottomY)) { return false; }
        float side = Math.Max(Math.AbsFloat(lower[0]), Math.AbsFloat(upper[0]));
        if (side > 2.2) { return false; }
        vector itemLower;
        vector itemUpper;
        float itemBottom;
        if (!HCGroundSnap.Bounds(item, itemLower, itemUpper, itemBottom)) { return false; }
        float pivot = item.GetPosition()[1] - itemBottom;
        vector origin = vehicle.GetPosition();
        // Explicitly exclude attached doors/wheels as well as the chassis. A
        // door is an entity of its own; it must not hide a wall beyond it.
        GameInventory inventory = vehicle.GetInventory();
        int attachments = inventory.AttachmentCount();
        if (attachments > 32) { return false; }
        array<Object> excluded = new array<Object>;
        excluded.Insert(vehicle);
        excluded.Insert(item);
        for (int slot = 0; slot < 32 && slot < attachments; slot++)
        {
            EntityAI attached = inventory.GetAttachmentFromIndex(slot);
            if (attached) { excluded.Insert(attached); }
        }
        for (int attempt = 0; attempt < 4; attempt++)
        {
            float sign = 1;
            if ((moved + attempt) % 2 == 1) { sign = -1; }
            float along = 0.5;
            if (attempt > 1) { along = -0.5; }
            vector spot = vehicle.ModelToWorld(Vector(sign * 2.5, 0, along));
            float distanceSq = vector.DistanceSq(Vector(origin[0], 0, origin[2]), Vector(spot[0], 0, spot[2]));
            if (distanceSq < 1 || distanceSq > 9) { continue; }
            if (GetGame().SurfaceIsSea(spot[0], spot[2]) || GetGame().SurfaceIsPond(spot[0], spot[2])) { continue; }
            vector contact;
            bool terrain;
            if (!HCGroundSnap.Support(spot + Vector(0, 0.5, 0), vehicle, 3, contact, terrain)) { continue; }
            vector rayFrom = origin + Vector(0, 0.5, 0);
            vector rayTo = contact + Vector(0, 0.5, 0);
            RaycastRVParams query = new RaycastRVParams(rayFrom, rayTo, vehicle);
            query.type = ObjIntersectGeom;
            query.flags = CollisionFlags.NEARESTCONTACT;
            array<ref RaycastRVResult> hits = new array<ref RaycastRVResult>;
            if (DayZPhysics.RaycastRVProxy(query, hits, excluded) && hits.Count() > 0) { continue; }
            vector transform[4];
            item.GetTransform(transform);
            transform[3] = contact + Vector(0, pivot + 0.03, 0);
            destination = new InventoryLocation;
            destination.SetGround(item, transform);
            return true;
        }
        return false;
    }

    protected bool MoveOne(HCVehicleRetireJob job, EntityAI item)
    {
        if (!item || item.IsPendingDeletion() || item.GetHierarchyParent() != job.Vehicle)
        {
            Refuse("child_location");
            return false;
        }
        InventoryLocation source = new InventoryLocation;
        InventoryLocation destination;
        if (!item.GetInventory().GetCurrentInventoryLocation(source) || !source.IsValid())
        {
            Refuse("source_location");
            return false;
        }
        if (!Destination(job.Vehicle, item, job.Moved, destination))
        {
            Refuse("ground_support");
            return false;
        }
        if (!GameInventory.LocationCanMoveEntity(source, destination))
        {
            Refuse("move_locked");
            return false;
        }
        if (!item.ServerTakeToDst(source, destination))
        {
            Refuse("move_failed");
            return false;
        }
        InventoryLocation actual = new InventoryLocation;
        if (item.GetHierarchyParent() || !item.GetInventory().GetCurrentInventoryLocation(actual) || actual.GetType() != InventoryLocationType.GROUND)
        {
            Refuse("move_not_ground");
            return false;
        }
        // Counts native root transfers, including a container's entire contents.
        job.Moved++;
        m_Moved++;
        m_Activity.Add("items_moved");
        if (!HCGroundSnap.Snap(item, 0.5, 0.03))
        {
            Refuse("ground_snap");
            return false;
        }
        return true;
    }

    // True finishes this job for the boot (retired, vanished or refused). False
    // retains it for later ticks. Only this method can delete, and only the car.
    protected bool Visit(HCVehicleRetireJob job)
    {
        CarScript vehicle = job.Vehicle;
        if (!vehicle || vehicle.IsPendingDeletion()) { return true; }
        if (vehicle.GetHierarchyParent()) { Refuse("vehicle_nested"); return true; }
        string wait = WaitReason(vehicle);
        if (wait != "")
        {
            if (!job.Waiting) { job.Waiting = true; m_Activity.Add("deferred"); }
            return false;
        }
        job.Waiting = false;
        m_Budget.HCReset(HCVehicleRetire.MOVES_PER_TICK, HCPerfConfig.HCGet().SliceMs);
        while (m_Budget.HCContinue())
        {
            EntityAI child = FirstChild(job);
            if (!child) { break; }
            if (!MoveOne(job, child)) { return true; }
        }
        if (!Empty(vehicle)) { return false; }
        // Revalidate after inventory callbacks; none can license player deletion.
        if (vehicle.GetHierarchyParent()) { Refuse("vehicle_nested"); return true; }
        if (WaitReason(vehicle) != "") { return false; }
        if (!Empty(vehicle)) { Refuse("not_empty"); return true; }
        string type = vehicle.GetType();
        GetGame().ObjectDelete(vehicle);
        m_Retired++;
        m_Activity.Add("retired");
        HCModuleReadiness.HCUse(GetName(), "retired");
        if (m_Retired <= 16) { Print("[HC Vehicles] retired class=" + type + " items_moved=" + job.Moved.ToString()); }
        return true;
    }

    override void OnTick(float deltaTime)
    {
        if (!m_Running || !GetGame().IsServer()) { return; }
        // Startup grace; core ticks only after all module start hooks return.
        if (GetGame().GetTickTime() - m_Start < 10) { return; }
        array<ref HCVehicleRetireJob> jobs = HCVehicleRetire.Jobs();
        if (m_Activity.HCDue(deltaTime)) { m_Activity.HCLog("[HC Vehicles] retire", " pending=" + jobs.Count().ToString()); }
        int overflow = HCVehicleRetire.Overflow();
        if (!m_UpgradeSeen && (jobs.Count() > 0 || overflow > 0))
        {
            m_UpgradeSeen = true;
            Print("[HC Vehicles] retire upgrade_pending");
        }
        if (overflow > m_OverflowSeen)
        {
            m_Refused += overflow - m_OverflowSeen - 1;
            m_OverflowSeen = overflow;
            Refuse("queue_full");
        }
        if (jobs.Count() == 0) { return; }
        if (m_Cursor >= jobs.Count()) { m_Cursor = 0; }
        HCVehicleRetireJob job = jobs[m_Cursor];
        if (Visit(job))
        {
            // HC-ORDER: unordered ok; round robin has no FIFO contract.
            jobs.Remove(m_Cursor);

        }
        else { m_Cursor++; }
    }

    protected void Summary()
    {
        if (m_Summary) { return; }
        m_Summary = true;
        Print("[HC Vehicles] retire summary retired=" + m_Retired.ToString() + " items_moved=" + m_Moved.ToString() + " refused=" + m_Refused.ToString());
    }
    override void OnStop()
    {
        Summary();
        m_Activity.HCLog("[HC Vehicles] retire", " shutdown=true");
        m_Running = false;
    }
}

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        Register(new HCVehicleRetireModule);
    }
}

modded class CarScript
{
    protected bool m_HCRetireQueued;
    override void AfterStoreLoad()
    {
        super.AfterStoreLoad();
        if (m_HCRetireQueued) { return; }
        m_HCRetireQueued = true;
        HCVehicleRetire.Enqueue(this);
    }
}
