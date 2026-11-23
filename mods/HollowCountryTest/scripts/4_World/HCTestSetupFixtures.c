// Dev-only test addon (never shipped). Setup-only admin fixtures: each creates a starting
// state with vanilla placement APIs, logs fixture=1, and the real HC feature code then runs
// on its own schedule. No counter is bumped, faked or credited here; no player is moved.
// Server side only, honours EnableSmokeFixtures (HCAdminFixtures.HCEnabled), one object set
// per fixture (a repeat call deletes only the objects this provider created, held weakly).
// Native scripts-1.30.164289: 3_Game/Global/Game.c:703 CreateObjectEx, :705 ObjectDelete,
// :930 GetObjectsAtPosition3D, :1176 SurfaceY, :1177 SurfaceRoadY, :1180 SurfaceGetType,
// :1188 SurfaceGetNormal, :1196/1197 SurfaceIsSea/Pond, :1333 IsBoxColliding;
// 3_Game/CE/CentralEconomy.c:31/38 ECE_NOPERSISTENCY_WORLD/ECE_PLACE_ON_SURFACE;
// 3_Game/Entities/Object.c:294/311/370 SetPosition/SetOrientation/GetCollisionBox;
// 3_Game/Entities/EntityAI.c:3955 OnDebugSpawn (full parts and fluids);
// 3_Game/Vehicles/Car.c EngineIsOn, Transport.c CrewSize/CrewMember;
// 1_Core/proto/EnPhysics.c:104/158 GetVelocity/dBodyGetAngularVelocity;
// 4_World/Entities/ItemBase/TentBase.c:21/511/542 PITCHED/Pack/Pitch (Pitch is what
// OnPlacementComplete calls, TentBase.c:823); FireplaceBase.c:1760 StartFire, :1639 IsBurning;
// Fireplace.c:225 EEItemAttached registers attached fuel; ItemBase.c:3398 SetQuantityMax.
// Placement rules: HCAdminPlacement.HCClear (no building door, obstacle, player or sea within
// its clearance), no road surface, slope <= 0.3 m per metre, a clear box, 6-15 m from the admin.
class HCTestSetupFixtures : HCAdminFixtureProvider
{
    protected static ref HCTestSetupFixtures s_Provider;
    // Weak handles: the engine nulls them when the object is deleted elsewhere.
    protected Object m_Car;
    protected Object m_Tent;
    protected Object m_Crate;
    protected Object m_Fire;
    protected Object m_Wreck;

    static void HCRegisterOnce()
    {
        if (s_Provider) { return; }
        HCTestSetupFixtures provider = new HCTestSetupFixtures;
        if (HCAdminFixtures.HCRegister(provider)) { s_Provider = provider; }
    }

    static bool HCOwns(string command)
    {
        return command == "fx_car_side" || command == "fx_camp_setup" || command == "fx_wreck";
    }

    override bool HCFixture(string command, vector pos, out string reason)
    {
        // Unknown commands leave reason untouched so the next provider is asked.
        if (!HCOwns(command)) { return false; }
        string created = "none";
        bool done = false;
        reason = "EnableSmokeFixtures-off";
        if (HCAdminFixtures.HCEnabled())
        {
            reason = "server-only";
            if (GetGame() && GetGame().IsServer())
            {
                reason = "position-invalid";
                if (HCDebugSnapshot.HCPositionValid(pos) && pos[1] == pos[1])
                {
                    if (command == "fx_car_side") { done = HCCarSide(pos, reason, created); }
                    if (command == "fx_camp_setup") { done = HCCampSetup(pos, reason, created); }
                    if (command == "fx_wreck") { done = HCWreck(pos, reason, created); }
                }
            }
        }
        string result = "refused";
        if (done) { result = "ok"; }
        Print("[HC Fixture] cmd=" + command + " fixture=1 result=" + result + " reason=" + reason + " class=" + created);
        return done;
    }

    override void HCFixtureKit(array<string> lines)
    {
        // Read-only: a fixture is available whenever smoke fixtures are on. No placement here.
        array<string> commands = {"fx_car_side", "fx_camp_setup", "fx_wreck"};
        string value = "0";
        string why = "EnableSmokeFixtures-off";
        if (HCAdminFixtures.HCEnabled())
        {
            value = "1";
            why = "setup-only-test-addon";
        }
        foreach (string command : commands)
        {
            lines.Insert(command + " available=" + value + " reason=" + why + " fixture=1");
        }
    }

    // ---- shared helpers ---------------------------------------------------------------

    protected void HCDelete(Object item)
    {
        if (item && !item.IsPendingDeletion()) { GetGame().ObjectDelete(item); }
    }

    protected bool HCRoad(vector point)
    {
        if (Math.AbsFloat(GetGame().SurfaceRoadY(point[0], point[2]) - GetGame().SurfaceY(point[0], point[2])) > 0.02) { return true; }
        string surface;
        GetGame().SurfaceGetType(point[0], point[2], surface);
        surface.ToLower();
        if (surface.IndexOf("asphalt") >= 0 || surface.IndexOf("concrete") >= 0 || surface.IndexOf("road") >= 0) { return true; }
        return false;
    }

    // One ground point: open flat ground, off roads, nothing within the shared clearance and a
    // free box of the given footprint above it. Position y is the terrain height.
    protected bool HCPointOk(vector point, float footprint)
    {
        if (!HCDebugSnapshot.HCPositionValid(point)) { return false; }
        if (GetGame().SurfaceIsSea(point[0], point[2]) || GetGame().SurfaceIsPond(point[0], point[2])) { return false; }
        vector normal = GetGame().SurfaceGetNormal(point[0], point[2]);
        if (normal[1] < 0.95) { return false; }
        if (HCRoad(point)) { return false; }
        if (!HCAdminPlacement.HCClear(point)) { return false; }
        array<Object> excluded = new array<Object>;
        if (GetGame().IsBoxColliding(point + Vector(0, 1.6, 0), vector.Zero, Vector(footprint, 2.4, footprint), excluded)) { return false; }
        return true;
    }

    protected vector HCRing(vector origin, float angle, float radius)
    {
        vector point = origin + Vector(Math.Cos(angle) * radius, 0, Math.Sin(angle) * radius);
        point[1] = GetGame().SurfaceY(point[0], point[2]);
        return point;
    }

    // At most 12 candidates on a golden-angle spiral between minRadius and maxRadius.
    protected bool HCFreeSpot(vector origin, float minRadius, float maxRadius, float footprint, out vector spot)
    {
        float span = maxRadius - minRadius;
        for (int attempt = 0; attempt < 12; attempt++)
        {
            int step = attempt % 4;
            float radius = minRadius + span * step / 3;
            vector candidate = HCRing(origin, attempt * 2.399963, radius);
            if (HCPointOk(candidate, footprint))
            {
                spot = candidate;
                return true;
            }
        }
        return false;
    }

    // ---- fx_car_side --------------------------------------------------------------------
    // HCVehicleFlipModule.HCCandidate / HCReady eligibility and what this satisfies:
    //   up[1] < 0.3          roll 90 gives up[1] ~ 0: satisfied, verified after the roll.
    //   speed <= 0.25 m/s    parked, no engine, body at rest: satisfied (checked on existing cars).
    //   angular <= 0.6 rad/s same: satisfied.
    //   engine off, no crew  checked before rolling, never rolls an occupied car.
    //   no one in the box    the admin stays >= 4 m away; helpers are the test client's business.
    // Not satisfied here, by design: reach (ReachMeters <= 5 m from the actor) and the crowbar in
    // hands (or 3 helpers). The driver walks to the car and holds a crowbar; no teleport.

    protected CarScript HCNearestParked(vector pos)
    {
        array<Object> objects = new array<Object>;
        array<CargoBase> proxies = new array<CargoBase>;
        GetGame().GetObjectsAtPosition3D(pos, 40, objects, proxies);
        int count = Math.Min(objects.Count(), 512);
        CarScript best;
        float bestSq = 1700;
        for (int index = 0; index < count; index++)
        {
            CarScript car = CarScript.Cast(objects[index]);
            if (!car || car.IsPendingDeletion() || car.IsRuined() || car.GetHierarchyParent()) { continue; }
            if (car.EngineIsOn()) { continue; }
            float distanceSq = vector.DistanceSq(car.GetPosition(), pos);
            if (distanceSq < 16 || distanceSq >= bestSq) { continue; }
            vector transform[4];
            car.GetTransform(transform);
            vector up = transform[1];
            if (up[1] < 0.5) { continue; }
            if (GetVelocity(car).LengthSq() > 0.0625 || dBodyGetAngularVelocity(car).LengthSq() > 0.36) { continue; }
            int seats = car.CrewSize();
            if (seats > 16) { continue; }
            bool occupied = false;
            for (int seat = 0; seat < seats; seat++)
            {
                if (car.CrewMember(seat)) { occupied = true; }
            }
            if (occupied) { continue; }
            best = car;
            bestSq = distanceSq;
        }
        return best;
    }

    protected bool HCRoll(CarScript car, out string reason)
    {
        vector box[2];
        reason = "car-bounds-unavailable";
        if (!car.GetCollisionBox(box)) { return false; }
        float half = Math.Max(Math.AbsFloat(box[0][0]), Math.AbsFloat(box[1][0])) + 0.05;
        vector origin = car.GetPosition();
        vector orientation = car.GetOrientation();
        car.SetOrientation(Vector(orientation[0], 0, 90));
        car.SetPosition(Vector(origin[0], origin[1] + half, origin[2]));
        vector transform[4];
        car.GetTransform(transform);
        vector up = transform[1];
        reason = "roll-not-applied";
        if (!(up[1] < 0.3))
        {
            car.SetOrientation(orientation);
            car.SetPosition(origin);
            return false;
        }
        return true;
    }

    protected bool HCCarSide(vector pos, out string reason, out string created)
    {
        HCDelete(m_Car);
        m_Car = null;
        CarScript existing = HCNearestParked(pos);
        if (existing)
        {
            created = existing.GetType();
            if (!HCRoll(existing, reason)) { return false; }
            reason = "rolled-existing;up-lt-0.3,speed-0,engine-off;reach-5m-and-crowbar-needed";
            return true;
        }
        vector spot;
        reason = "no-free-ground-8-15m";
        if (!HCFreeSpot(pos, 8, 15, 6, spot)) { return false; }
        created = "CivilianSedan";
        CarScript spawned = CarScript.Cast(GetGame().CreateObjectEx("CivilianSedan", spot, ECE_PLACE_ON_SURFACE | ECE_NOPERSISTENCY_WORLD));
        reason = "car-create-refused";
        if (!spawned) { return false; }
        spawned.OnDebugSpawn();
        if (!HCRoll(spawned, reason))
        {
            HCDelete(spawned);
            return false;
        }
        m_Car = spawned;
        reason = "rolled-new;up-lt-0.3,speed-0,engine-off;reach-5m-and-crowbar-needed";
        return true;
    }

    // ---- fx_camp_setup ------------------------------------------------------------------
    // HCCampModule recognises a camp when a burning, unparented FireplaceBase sits within
    // sqrt(CampBindDistanceSq) <= 12 m of a grouped player (Candidate); HCCampScan.Read then
    // looks 12 m around the fire for a PITCHED TentBase (Shelter) and an unparented storage
    // item (pitched tent, WoodenCrate, SeaChest or barrel). HCCampModule.HCRespawnPosition
    // re-reads the same scan and needs FireFor (same class, <= 1 m), tier >= 1 (storage), no
    // other group's camp within 100 m. Set: Fireplace with Firewood and Sticks, lit with the
    // vanilla StartFire; MediumTent pitched with TentBase.Pitch; one WoodenCrate. The fire sits
    // 7 m from the admin so the admin is inside the 12 m bind radius.
    // Required of the test client, not done here: be in a group (driver: group create_solo).

    protected void HCClearCamp()
    {
        HCDelete(m_Fire);
        HCDelete(m_Tent);
        HCDelete(m_Crate);
        m_Fire = null;
        m_Tent = null;
        m_Crate = null;
    }

    protected bool HCCampSpots(vector pos, out vector firePos, out vector tentPos, out vector cratePos)
    {
        for (int attempt = 0; attempt < 12; attempt++)
        {
            float angle = attempt * 2.399963;
            vector candidate = HCRing(pos, angle, 7);
            if (!HCPointOk(candidate, 2)) { continue; }
            // The tent goes on the far side of the fire first so it never ends up near the admin.
            for (int tentTry = 0; tentTry < 4; tentTry++)
            {
                vector tentCandidate = HCRing(candidate, angle + tentTry * 1.5708, 5);
                float tentFromAdmin = vector.DistanceSq(tentCandidate, pos);
                if (tentFromAdmin < 36 || tentFromAdmin > 225) { continue; }
                if (!HCPointOk(tentCandidate, 5)) { continue; }
                for (int crateTry = 0; crateTry < 4; crateTry++)
                {
                    vector crateCandidate = HCRing(candidate, angle + 0.785 + crateTry * 1.5708, 3.2);
                    float crateFromAdmin = vector.DistanceSq(crateCandidate, pos);
                    if (crateFromAdmin < 36 || crateFromAdmin > 225) { continue; }
                    if (vector.DistanceSq(crateCandidate, tentCandidate) < 16) { continue; }
                    if (!HCPointOk(crateCandidate, 1.5)) { continue; }
                    firePos = candidate;
                    tentPos = tentCandidate;
                    cratePos = crateCandidate;
                    return true;
                }
            }
        }
        return false;
    }

    protected bool HCCampSetup(vector pos, out string reason, out string created)
    {
        HCClearCamp();
        vector firePos;
        vector tentPos;
        vector cratePos;
        reason = "no-free-ground-6-15m";
        if (!HCCampSpots(pos, firePos, tentPos, cratePos)) { return false; }
        created = "Fireplace+MediumTent+WoodenCrate";
        FireplaceBase fire = FireplaceBase.Cast(GetGame().CreateObjectEx("Fireplace", firePos, ECE_PLACE_ON_SURFACE | ECE_NOPERSISTENCY_WORLD));
        TentBase tent = TentBase.Cast(GetGame().CreateObjectEx("MediumTent", tentPos, ECE_PLACE_ON_SURFACE | ECE_NOPERSISTENCY_WORLD));
        ItemBase crate = ItemBase.Cast(GetGame().CreateObjectEx("WoodenCrate", cratePos, ECE_PLACE_ON_SURFACE | ECE_NOPERSISTENCY_WORLD));
        m_Fire = fire;
        m_Tent = tent;
        m_Crate = crate;
        reason = "camp-object-create-refused";
        if (!fire || !tent || !crate)
        {
            HCClearCamp();
            return false;
        }
        EntityAI wood = fire.GetInventory().CreateAttachment("Firewood");
        EntityAI sticks = fire.GetInventory().CreateAttachment("WoodenStick");
        ItemBase woodItem = ItemBase.Cast(wood);
        ItemBase stickItem = ItemBase.Cast(sticks);
        if (woodItem) { woodItem.SetQuantityMax(); }
        if (stickItem) { stickItem.SetQuantityMax(); }
        reason = "fuel-attach-refused";
        if (!woodItem)
        {
            HCClearCamp();
            return false;
        }
        tent.Pitch(true);
        reason = "tent-not-pitched";
        if (tent.GetState() != TentBase.PITCHED)
        {
            HCClearCamp();
            return false;
        }
        fire.StartFire();
        reason = "fire-not-lit-wind-or-wet";
        if (!fire.IsBurning())
        {
            HCClearCamp();
            return false;
        }
        reason = "camp-set;tent-pitched,crate,fire-lit;group-and-real-camp-scan-do-the-rest";
        return true;
    }

    // ---- fx_wreck -----------------------------------------------------------------------
    // HCWreckSalvage.Allowed accepts a non-Transport object whose type is in the reviewed
    // list (HCWreckSalvage.Reviewed) at a valid position, reached by the salvage action with a
    // Wrench, Screwdriver or Pliers in hands. HCWreckSalvageModule.Enroll then adds the journal
    // row at this position. One reviewed class is placed; the class is asserted against the
    // shipped list so a list change refuses here instead of placing a dead prop.

    protected bool HCWreck(vector pos, out string reason, out string created)
    {
        HCDelete(m_Wreck);
        m_Wreck = null;
        string wreckClass = "Land_Wreck_sed01_aban1_black";
        created = wreckClass;
        reason = "wreck-class-not-reviewed";
        if (!HCWreckSalvage.Reviewed(wreckClass)) { return false; }
        vector spot;
        reason = "no-free-ground-8-15m";
        if (!HCFreeSpot(pos, 8, 15, 7, spot)) { return false; }
        reason = "wreck-position-invalid";
        if (!HCWreckSalvage.PositionValid(spot)) { return false; }
        Object wreck = GetGame().CreateObjectEx(wreckClass, spot, ECE_SETUP | ECE_CREATEPHYSICS | ECE_NOLIFETIME | ECE_NOPERSISTENCY_WORLD, RF_IGNORE);
        reason = "wreck-create-refused";
        if (!wreck) { return false; }
        wreck.SetOrientation(Vector(35, 0, 0));
        reason = "ground-snap-refused";
        if (!HCGroundSnap.Snap(wreck, 5, 0.01))
        {
            HCDelete(wreck);
            return false;
        }
        m_Wreck = wreck;
        reason = "wreck-set;reviewed-class,salvage-needs-wrench-screwdriver-or-pliers-within-2m";
        return true;
    }
}

modded class HCAdminModule
{
    override void OnStart(HCSettings settings)
    {
        super.OnStart(settings);
        if (GetGame() && GetGame().IsServer()) { HCTestSetupFixtures.HCRegisterOnce(); }
    }
}
