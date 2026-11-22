// H1 helicopters (owner 2026-11-19: flyable helicopters via an approved Workshop
// dependency, active in tools/setup/workshop_mods.json). Policy is
// provider-optional: only vanilla types and config strings are used, no symbol from
// the provider, so the base mod compiles and loads without it. Runtime PENDING.
// Native scripts-1.30.164289 evidence:
// 3_Game/Global/Game.c:449 ConfigGetText(out), :612 ConfigIsExisting, :914
// GetTickTime, :1120 IsServer; 1_Core/proto/EnSystem.c:397 FileExist; EnDebug.c:96
// Print; EnConvert.c:30 int.ToString; EnScript.c:380/394/407/463 array
// Count/Find/Insert/Remove, :852/877/926 map Count/Find/Insert; 3_Game/Entities/Object.c:467 GetType;
// 3_Game/Entities/EntityAI.c:905 EEInit, :1414 EEOnCECreate; 3_Game/Vehicles/
// Transport.c:135 EEDelete; 4_World/Entities/Vehicles/CarScript.c:2412 vanilla
// EEOnCECreate fills 0..35% fuel; 3_Game/Vehicles/Car.c:18 CarFluid, :355
// GetFluidCapacity, :363 GetFluidFraction, :366 Leak.
// ConfigGetText follows config inheritance; Game.c:1437 IsKindOf additionally
// recognises configured CfgVehicles base names. No provider script calls here.
// EntityAI.c:1104 EEKilled; Object.c:287 GetPosition, :517 IsAlive. HCWorldIncidents owns
// incident ranges, lifetimes, caps and member perception; no actors spawn here.
class HCHeliPolicyConfig
{
    int Version = 1;
    // CfgPatches class whose presence means the optional provider is loaded.
    string ProviderPatch = "DayZExpansion_Vehicles_Scripts";
    // CfgVehicles vehicleClass categories OR real CfgVehicles helicopter bases.
    ref array<string> VehicleClasses;
    // Bounded tracking registry (also the per-event work ceiling).
    int MaxTracked = 16;
    // Scarcity target: more live helicopters than this reports degraded.
    int WorldCap = 4;
    // Bounded per-type classification cache.
    int MaxTypeCache = 128;
    // Fuel left after a CE spawn, as a fraction of the tank (vanilla gives 0..0.35).
    float SpawnFuelMaxFraction = 0.1;

    void HCHeliPolicyConfig()
    {
        VehicleClasses = new array<string>;
        VehicleClasses.Insert("Expansion_Helicopter");
        VehicleClasses.Insert("ExpansionHelicopterScript");
        VehicleClasses.Insert("ExpansionGyrocopter");
        VehicleClasses.Insert("ExpansionHatchBird");
        VehicleClasses.Insert("ExpansionMh6");
        VehicleClasses.Insert("ExpansionUh1h");
        VehicleClasses.Insert("ExpansionMerlin");
    }

    // Literal fallbacks mirror the requested registry rows (owner HCHeliPolicyConfig);
    // the registry check applies once the compiled mirror is present.
    bool HCValid()
    {
        if (Version != 1 || !VehicleClasses) { return false; }
        if (VehicleClasses.Count() < 1 || VehicleClasses.Count() > 8) { return false; }
        if (ProviderPatch.Length() < 1 || ProviderPatch.Length() > 64) { return false; }
        for (int classIndex = 0; classIndex < VehicleClasses.Count(); classIndex++)
        {
            if (VehicleClasses[classIndex].Length() < 1 || VehicleClasses[classIndex].Length() > 64) { return false; }
        }
        if (MaxTracked < 1 || MaxTracked > 64 || WorldCap < 0 || WorldCap > 64 || WorldCap > MaxTracked) { return false; }
        if (MaxTypeCache < 1 || MaxTypeCache > 512) { return false; }
        if (SpawnFuelMaxFraction != SpawnFuelMaxFraction) { return false; }
        if (SpawnFuelMaxFraction < 0 || SpawnFuelMaxFraction > 0.35) { return false; }
        if (!HCOperatorSettingsRegistry.HCFind("Helicopters.Version")) { return true; }
        if (!HCOperatorSettingsRegistry.HCValid("Helicopters.Version", Version)) { return false; }
        if (!HCOperatorSettingsRegistry.HCValid("Helicopters.MaxTracked", MaxTracked)) { return false; }
        if (!HCOperatorSettingsRegistry.HCValid("Helicopters.WorldCap", WorldCap)) { return false; }
        if (!HCOperatorSettingsRegistry.HCValid("Helicopters.MaxTypeCache", MaxTypeCache)) { return false; }
        return HCOperatorSettingsRegistry.HCValid("Helicopters.SpawnFuelMaxFraction", SpawnFuelMaxFraction);
    }
}

// Event-driven (vehicle init/delete/CE create), O(1) per event, no per-tick work.
// Ambient AI overflight is gated on an observed flight API: Expansion AI drives
// ground vehicles only, and no flight controller is built on unobserved APIs.
class HCHeliPolicy
{
    protected static bool s_Admission;
    // Vehicle init may precede HCServer.Start; stop must never re-admit via callbacks.
    protected static bool s_Active = true;
    protected static bool s_Enabled;
    protected static bool s_Provider;
    protected static bool s_LandingLogged;
    protected static bool s_CrashLogged;
    protected static int s_Overflow;
    protected static int s_Shaped;
    protected static string s_Refusal;
    protected static string s_Line;
    protected static ref HCHeliPolicyConfig s_Config;
    protected static ref HCEncounterStore<HCHeliPolicyConfig> s_Store;
    protected static ref HCOperationalStatus s_Status;
    protected static ref array<CarScript> s_Tracked;
    protected static ref map<string, int> s_Kinds;
    // Registry-owned (HCOperationalContributors keeps the strong ref).
    protected static HCOperationalOwner s_Owner;

    static bool HCClassMatch(array<string> classes, string vehicleClass)
    {
        if (!classes || vehicleClass == "") { return false; }
        for (int matchIndex = 0; matchIndex < classes.Count(); matchIndex++)
        {
            if (classes[matchIndex] == vehicleClass) { return true; }
        }
        return false;
    }

    // Litres to drain so a fresh spawn keeps at most maxFraction of its tank.
    static float HCExcessFuel(float capacity, float fraction, float maxFraction)
    {
        if (capacity <= 0 || fraction <= maxFraction) { return 0; }
        return capacity * fraction - capacity * maxFraction;
    }

    // 0 admitted, 1 already tracked, 2 registry full, 3 no input.
    static int HCAdmit(array<CarScript> tracked, CarScript car, int cap)
    {
        if (!tracked || !car) { return 3; }
        if (tracked.Find(car) >= 0) { return 1; }
        if (tracked.Count() >= cap) { return 2; }
        tracked.Insert(car);
        return 0;
    }

    static string HCDerive(bool started, bool enabled, bool configOk, bool provider, int tracked, int worldCap, int overflow, out string reason)
    {
        if (!started)
        {
            reason = "helicopters_not_started";
            return "off";
        }
        if (!enabled)
        {
            reason = "operator_disabled";
            return "off";
        }
        if (!configOk)
        {
            reason = "HELI_CONFIG_INVALID";
            return "refused";
        }
        if (!provider)
        {
            reason = "HELI_PROVIDER_NOT_LOADED";
            return "off";
        }
        if (overflow > 0)
        {
            reason = "HELI_TRACK_CAP";
            return "degraded";
        }
        if (tracked > worldCap)
        {
            reason = "HELI_OVER_WORLD_CAP";
            return "degraded";
        }
        reason = "provider_loaded_policy_active_runtime_pending";
        return "ready";
    }

    // Server only; opt-out, config and provider are sampled once.
    static bool HCEnabled()
    {
        if (!s_Active) { return false; }
        if (s_Admission) { return s_Enabled && s_Provider && s_Config != null; }
        if (!GetGame() || !GetGame().IsServer()) { return false; }
        s_Admission = true;
        if (!s_Status) { s_Status = new HCOperationalStatus; }
        s_Tracked = new array<CarScript>;
        s_Kinds = new map<string, int>;
        s_Enabled = !FileExist("$profile:HollowCountry/acceptance/helicopters.disable");
        if (s_Enabled) { HCLoadConfig(); }
        if (s_Config) { s_Provider = GetGame().ConfigIsExisting("CfgPatches " + s_Config.ProviderPatch); }
        string providerWord = "absent";
        if (s_Provider) { providerWord = "loaded"; }
        Print(HCV2Admission.Line("Helicopters", s_Enabled, "H1-HELI", false) + " provider=" + providerWord + " overflight=pending_flight_api runtime=PENDING");
        if (s_Enabled && s_Config && !s_Provider) { HCRefuse("HELI_PROVIDER_NOT_LOADED"); }
        HCPublishStatus();
        return s_Enabled && s_Provider && s_Config != null;
    }

    protected static void HCLoadConfig()
    {
        s_Store = new HCEncounterStore<HCHeliPolicyConfig>("helicopters");
        HCHeliPolicyConfig fresh = new HCHeliPolicyConfig;
        s_Config = s_Store.Load(fresh, "VehicleClasses");
        string text = s_Store.HCTakeLoadedText();
        if (text != "" && (!HCJsonFields.Has(text, "MaxTracked") || !HCJsonFields.Has(text, "WorldCap") || !HCJsonFields.Has(text, "MaxTypeCache") || !HCJsonFields.Has(text, "SpawnFuelMaxFraction"))) { s_Config = null; }
        if (!s_Config || !s_Config.HCValid())
        {
            s_Config = null;
            HCRefuse("HELI_CONFIG_INVALID");
        }
    }

    static bool HCIsHelicopter(string typeName)
    {
        int kind = 0;
        if (s_Kinds.Find(typeName, kind)) { return kind == 1; }
        string vehicleClass = "";
        vehicleClass = HCConfigHelper.GetText("CfgVehicles " + typeName + " vehicleClass", "");
        kind = 2;
        if (HCClassMatch(s_Config.VehicleClasses, vehicleClass)) { kind = 1; }
        // Operators may select a provider base instead of its editor category.
        array<string> configuredBases = s_Config.VehicleClasses;
        foreach (string configuredBase : configuredBases)
        {
            if (GetGame().IsKindOf(typeName, configuredBase)) { kind = 1; }
        }
        if (s_Kinds.Count() < s_Config.MaxTypeCache) { s_Kinds.Insert(typeName, kind); }
        return kind == 1;
    }

    static void HCTrack(CarScript car)
    {
        if (!car || !HCEnabled() || !car.IsAlive()) { return; }
        if (!HCIsHelicopter(car.GetType())) { return; }
        int admitted = HCAdmit(s_Tracked, car, s_Config.MaxTracked);
        if (admitted == 2)
        {
            if (!car.m_HCHeliOverflow)
            {
                car.m_HCHeliOverflow = true;
                s_Overflow++;
            }
            HCRefuse("HELI_TRACK_CAP");
        }
        if (admitted == 0 && car.m_HCHeliOverflow)
        {
            car.m_HCHeliOverflow = false;
            s_Overflow--;
        }
        if (admitted == 0 || admitted == 2) { HCPublishStatus(); }
    }

    static void HCUntrack(CarScript car)
    {
        if (!car || !s_Tracked) { return; }
        bool wasOverflow = car.m_HCHeliOverflow;
        if (wasOverflow)
        {
            car.m_HCHeliOverflow = false;
            s_Overflow--;
        }
        int index = s_Tracked.Find(car);
        if (index < 0 && !wasOverflow) { return; }
        if (index >= 0) { s_Tracked.Remove(index); }
        HCPublishStatus();
    }

    // Scarcity on fresh CE spawns only: persisted vehicles keep their saved fuel.
    static void HCSpawnFuel(CarScript car)
    {
        HCTrack(car);
        if (!car || !HCEnabled()) { return; }
        if (!HCIsHelicopter(car.GetType())) { return; }
        float capacity = car.GetFluidCapacity(CarFluid.FUEL);
        float retainedFraction = s_Config.SpawnFuelMaxFraction;
        // Native EntityAI.c:1897 FindAttachmentBySlotName. Installed gear
        // config.bin: ExpansionIgniterPlug.inventorySlot = ExpansionIgniterPlug;
        // gyrocopters use the native SparkPlug slot instead. Missing ignition
        // means a dry salvage spawn; otherwise preserve the configured fuel cap.
        if (!car.FindAttachmentBySlotName("ExpansionIgniterPlug") && !car.FindAttachmentBySlotName("SparkPlug")) { retainedFraction = 0; }
        float excess = HCExcessFuel(capacity, car.GetFluidFraction(CarFluid.FUEL), retainedFraction);
        if (excess <= 0) { return; }
        car.Leak(CarFluid.FUEL, excess);
        s_Shaped++;
        if (s_Shaped == 1) { Print("[HC Helicopters] spawn_fuel_capped type=" + car.GetType() + " runtime=PENDING"); }
    }

    // Existing incident policy supplies all ranges/lifetimes. A landing is a
    // visual scene, never a fabricated crash sound. Retire before changing kind:
    // HCFindSame deliberately coalesces all incidents with the same anchor.
    static void HCIncident(CarScript car, bool crashed)
    {
        if (!car || !HCEnabled() || !HCIsHelicopter(car.GetType())) { return; }
        HCWorldIncidents.HCRetire(car);
        string incidentKind = "scene";
        if (crashed) { incidentKind = "crash"; }
        int incidentId = HCWorldIncidents.HCPublish(incidentKind, car.GetPosition(), 0, 0, car);
        if (incidentId == 0)
        {
            HCRefuse("HELI_INCIDENT_NOT_PUBLISHED");
            return;
        }
        HCRefuse("");
        bool firstIncident = !s_LandingLogged;
        if (crashed) { firstIncident = !s_CrashLogged; }
        if (firstIncident)
        {
            Print("[HC Helicopters] incident=" + incidentKind + " source=vehicle_hook runtime=PENDING");
            if (crashed) { s_CrashLogged = true; }
            else { s_LandingLogged = true; }
        }
    }

    static void HCPublishStatus()
    {
        if (!s_Status) { s_Status = new HCOperationalStatus; }
        int trackedCount = 0;
        if (s_Tracked) { trackedCount = s_Tracked.Count(); }
        int worldCap = 0;
        if (s_Config) { worldCap = s_Config.WorldCap; }
        // Overflow identities live on the vehicles, not in an unbounded registry.
        // Count survivors even before their next callback can use a freed slot.
        int population = trackedCount + s_Overflow;
        int excessTracked = 0;
        if (s_Config && population > s_Config.MaxTracked) { excessTracked = population - s_Config.MaxTracked; }
        bool configOk = s_Config != null;
        string reason = "";
        string state = HCDerive(s_Admission && s_Active, s_Enabled, configOk, s_Provider, population, worldCap, excessTracked, reason);
        s_Status.HCPublish(state, reason);
        if (s_Owner && GetGame()) { s_Owner.HCObserve(s_Enabled && s_Active, s_Status, GetGame().GetTickTime()); }
        string line = "[HC Helicopters] " + state + " reason=" + reason + " tracked=" + trackedCount.ToString();
        if (line == s_Line) { return; }
        s_Line = line;
        Print("" + line);
    }

    static HCOperationalStatus HCGetOperationalStatus()
    {
        HCPublishStatus();
        return s_Status;
    }

    static void HCRefuse(string reason)
    {
        if (s_Refusal == reason) { return; }
        s_Refusal = reason;
        if (reason == "") { return; }
        Print("[HC Helicopters] reason=" + reason + " runtime=PENDING");
    }

    static void HCStart()
    {
        s_Active = true;
        HCEnabled();
        s_Owner = HCOperationalContributors.HCRegisterOwner("Helicopters");
        HCPublishStatus();
    }

    static void HCStop()
    {
        s_Active = false;
        HCPublishStatus();
        if (s_Owner && GetGame()) { s_Owner.HCStop(GetGame().GetTickTime()); }
        s_Owner = null;
    }
}

// Non-module lifecycle hook (HCAtmosphereLifecycle pattern): no module slot used.
// Registers after super.Start(), which resets the contributor registry first.
modded class HCServer
{
    override void Start()
    {
        super.Start();
        HCHeliPolicy.HCStart();
#ifdef EXPANSIONMODVEHICLE
        Print("[HC Helicopters] incident_hooks=crash_and_landing perception=existing_incident_policy runtime=PENDING");
        Print("[HC Vehicles] legacy_roster=unavailable classes=TT650,250N,OldBike,An2 reason=installed_scope_zero_obsolete_provider runtime=PENDING");
#else
        Print("[HC Helicopters] landing_hook=missing_vehicle_script_provider crash_hook=native runtime=PENDING");
#endif
    }

    override void Stop()
    {
        HCHeliPolicy.HCStop();
        super.Stop();
    }
}

// Every vehicle pays one cached type lookup on init; only configured helicopter
// classes are tracked. Super runs first so vanilla/provider fuel is set before capping.
modded class CarScript
{
    // One server-owned identity bit per overflow vehicle; no extra reference list.
    bool m_HCHeliOverflow;
    bool m_HCHeliCrashPublished;

    override void EEInit()
    {
        super.EEInit();
        HCHeliPolicy.HCTrack(this);
    }

    override void EEDelete(EntityAI parent)
    {
        HCWorldIncidents.HCRetire(this);
        HCHeliPolicy.HCUntrack(this);
        super.EEDelete(parent);
    }

    override void EEKilled(Object killer)
    {
        super.EEKilled(killer);
        if (m_HCHeliCrashPublished) { return; }
        m_HCHeliCrashPublished = true;
        HCHeliPolicy.HCUntrack(this);
        HCHeliPolicy.HCIncident(this, true);
    }

    override void EEOnCECreate()
    {
        super.EEOnCECreate();
        HCHeliPolicy.HCSpawnFuel(this);
    }
}
