// Passive server-only lifecycle registry, never a world scan. Transport covers
// CarScript, BoatScript, Motorbike and provider transport descendants (helis).
// Native scripts-1.30.164289: 3_Game/Vehicles/Transport.c:66-68,135;
// Entities/EntityAI.c:905 EEInit; Object.c:287/467/1219 position/type/ruined;
// Vehicles/Car.c:230, Boat.c:95, Motorbike.c:163 EngineIsOn.
// EEInit/EEDelete hooks (4_World Admin/HCAdminVehicleHooks.c; the engine
// refuses 'modded class Transport') retain <=2048 vehicles and <=256 event entities.
// No polling when no admin map is subscribed. Overflow is shown in map details.
class HCAdminVehicleRegistry
{
    static ref array<Transport> Vehicles = new array<Transport>;
    static ref array<Object> Events = new array<Object>;
    static int Overflow;
    static void Add(Transport vehicle)
    {
        if (!GetGame() || !GetGame().IsServer() || !vehicle || Vehicles.Find(vehicle) >= 0) { return; }
        if (Vehicles.Count() >= 2048) { Overflow++; return; }
        Vehicles.Insert(vehicle);
    }
    static void Remove(Transport vehicle)
    {
        int index = Vehicles.Find(vehicle);
        if (index >= 0) { Vehicles.Remove(index); }
    }
    static void AddEvent(Object eventObject)
    {
        if (!GetGame() || !GetGame().IsServer() || !eventObject || Events.Find(eventObject) >= 0) { return; }
        if (Events.Count() >= 256) { Overflow++; return; }
        Events.Insert(eventObject);
    }
    static void RemoveEvent(Object eventObject)
    {
        int index = Events.Find(eventObject);
        if (index >= 0) { Events.Remove(index); }
    }
    static string Detail(Transport vehicle)
    {
        string detail = "engine=n/a";
        Car car = Car.Cast(vehicle);
        Boat boat = Boat.Cast(vehicle);
        Motorbike bike = Motorbike.Cast(vehicle);
        if (car) { detail = "engine=" + car.EngineIsOn().ToString(); }
        else if (boat) { detail = "engine=" + boat.EngineIsOn().ToString(); }
        else if (bike) { detail = "engine=" + bike.EngineIsOn().ToString(); }
        return detail + "; ruined=" + vehicle.IsRuined().ToString() + "; registry_overflow=" + Overflow.ToString();
    }
}
