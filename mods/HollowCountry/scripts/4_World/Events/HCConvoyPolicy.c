// #210 road branch: convoy operator policy and pure driving rules. No module
// slot or mission payload. Override every field in $profile:HollowCountry/convoys.json;
// otherwise the source defaults below are the named configuration.
// Native scripts-1.30.164289: 1_Core/proto/EnSystem.c:397 FileExist;
// 3_Game/tools/JsonFileLoader.c:69 LoadData; EnDebug.c:96 Print;
// 1_Core/proto/EnMath.c:12 PI, :225 AbsFloat, :540 Clamp.
// These rules only shape bounded inputs. Car physics, AI seating and driving
// remain runtime=PENDING until observed in DayZ.
class HCConvoyControl
{
    float Steering;
    float Throttle;
    float Brake;
}

class HCConvoyPolicy
{
    // Zero-filled/missing ints or NaN floats fail validation; nothing uncaps work.
    int Version = 1;
    int MaxConvoys = 1;
    int SeekObjects = 256;
    int MaxSeekScans = 8;
    int MaxRouteNodes = 128;
    int MaxPlanNodes = 4000;
    int RoadNodesPerTick = 256;
    int RoadNodesPerWorkUnit = 8;
    float SeekMeters = 60;
    float SeekSeconds = 15;
    float PlayerClaimMeters = 150;
    float BoardMeters = 4;
    float ApproachSeconds = 120;
    float BoardSeconds = 60;
    float ExitSeconds = 10;
    float NodeReachMeters = 8;
    float ArriveMeters = 20;
    float DismountMeters = 120;
    float MaxApproachMeters = 60;
    float MinDriveMeters = 150;
    float MaxDriveMeters = 1500;
    float DetourMeters = 400;
    float CruiseKmh = 25;
    float TurnKmh = 10;
    float SpeedBandKmh = 3;
    float TurnRadians = 0.5;
    float SteerGain = 2;
    float Throttle = 0.6;
    float BrakeStrength = 0.6;
    float StopKmh = 2;
    float StopSeconds = 8;
    float StallMeters = 3;
    float StallSeconds = 15;
    float MaxDriveSeconds = 600;

    protected static ref HCConvoyPolicy s_Instance;
    protected static bool s_Loaded;
    protected static bool s_Logged;

    static HCConvoyPolicy HCGet()
    {
        if (s_Loaded) { return s_Instance; }
        s_Loaded = true;
        HCConvoyPolicy policy = new HCConvoyPolicy;
        string path = "$profile:HollowCountry/convoys.json";
        if (FileExist(path))
        {
            string encoded;
            string error;
            if (!HCGroupIO.Read(path, 4096, encoded)) { HCInvalid(); return null; }
            if (!HCFields(encoded)) { HCInvalid(); return null; }
            if (!JsonFileLoader<HCConvoyPolicy>.LoadData(encoded, policy, error)) { HCInvalid(); return null; }
        }
        if (!HCValid(policy)) { HCInvalid(); return null; }
        s_Instance = policy;
        if (!HCOperatorSettingsRegistry.HCFind("Convoys.Version"))
        {
            Print("[HC Convoy] CONVOY_SETTINGS_REGISTRY_PENDING local_policy_validated runtime=PENDING");
        }
        return s_Instance;
    }

    static bool HCFields(string encoded)
    {
        if (!HCJsonFields.Has(encoded, "Version") || !HCJsonFields.Has(encoded, "MaxConvoys") || !HCJsonFields.Has(encoded, "SeekObjects") || !HCJsonFields.Has(encoded, "MaxSeekScans") || !HCJsonFields.Has(encoded, "MaxRouteNodes") || !HCJsonFields.Has(encoded, "MaxPlanNodes") || !HCJsonFields.Has(encoded, "RoadNodesPerTick")) { return false; }
        if (!HCJsonFields.Has(encoded, "RoadNodesPerWorkUnit") || !HCJsonFields.Has(encoded, "SeekMeters") || !HCJsonFields.Has(encoded, "SeekSeconds") || !HCJsonFields.Has(encoded, "PlayerClaimMeters") || !HCJsonFields.Has(encoded, "BoardMeters") || !HCJsonFields.Has(encoded, "ApproachSeconds") || !HCJsonFields.Has(encoded, "BoardSeconds")) { return false; }
        if (!HCJsonFields.Has(encoded, "ExitSeconds") || !HCJsonFields.Has(encoded, "NodeReachMeters") || !HCJsonFields.Has(encoded, "ArriveMeters") || !HCJsonFields.Has(encoded, "DismountMeters") || !HCJsonFields.Has(encoded, "MaxApproachMeters") || !HCJsonFields.Has(encoded, "MinDriveMeters") || !HCJsonFields.Has(encoded, "MaxDriveMeters")) { return false; }
        if (!HCJsonFields.Has(encoded, "DetourMeters") || !HCJsonFields.Has(encoded, "CruiseKmh") || !HCJsonFields.Has(encoded, "TurnKmh") || !HCJsonFields.Has(encoded, "SpeedBandKmh") || !HCJsonFields.Has(encoded, "TurnRadians") || !HCJsonFields.Has(encoded, "SteerGain") || !HCJsonFields.Has(encoded, "Throttle")) { return false; }
        return HCJsonFields.Has(encoded, "BrakeStrength") && HCJsonFields.Has(encoded, "StopKmh") && HCJsonFields.Has(encoded, "StopSeconds") && HCJsonFields.Has(encoded, "StallMeters") && HCJsonFields.Has(encoded, "StallSeconds") && HCJsonFields.Has(encoded, "MaxDriveSeconds");
    }

    static void HCInvalid()
    {
        if (s_Logged) { return; }
        s_Logged = true;
        Print("[HC Convoy] CONVOY_POLICY_INVALID road_branch=walking_caravan runtime=PENDING");
    }

    static bool HCNumbers(HCConvoyPolicy policy)
    {
        // NaN is the only value that differs from itself.
        if (policy.SeekMeters != policy.SeekMeters || policy.SeekSeconds != policy.SeekSeconds || policy.PlayerClaimMeters != policy.PlayerClaimMeters || policy.BoardMeters != policy.BoardMeters) { return false; }
        if (policy.ApproachSeconds != policy.ApproachSeconds || policy.BoardSeconds != policy.BoardSeconds || policy.ExitSeconds != policy.ExitSeconds || policy.NodeReachMeters != policy.NodeReachMeters) { return false; }
        if (policy.ArriveMeters != policy.ArriveMeters || policy.DismountMeters != policy.DismountMeters || policy.MaxApproachMeters != policy.MaxApproachMeters || policy.MinDriveMeters != policy.MinDriveMeters) { return false; }
        if (policy.MaxDriveMeters != policy.MaxDriveMeters || policy.DetourMeters != policy.DetourMeters || policy.CruiseKmh != policy.CruiseKmh || policy.TurnKmh != policy.TurnKmh) { return false; }
        if (policy.SpeedBandKmh != policy.SpeedBandKmh || policy.TurnRadians != policy.TurnRadians || policy.SteerGain != policy.SteerGain || policy.Throttle != policy.Throttle) { return false; }
        if (policy.BrakeStrength != policy.BrakeStrength || policy.StopKmh != policy.StopKmh || policy.StopSeconds != policy.StopSeconds || policy.StallMeters != policy.StallMeters) { return false; }
        return policy.StallSeconds == policy.StallSeconds && policy.MaxDriveSeconds == policy.MaxDriveSeconds;
    }

    static bool HCValid(HCConvoyPolicy policy)
    {
        if (!policy || policy.Version != 1 || policy.MaxConvoys != 1) { return false; }
        if (!HCNumbers(policy)) { return false; }
        if (policy.SeekObjects < 1 || policy.SeekObjects > 1024 || policy.MaxSeekScans < 1 || policy.MaxSeekScans > 32) { return false; }
        if (policy.MaxRouteNodes < 2 || policy.MaxRouteNodes > 256 || policy.MaxPlanNodes < 2 || policy.MaxPlanNodes > 40000) { return false; }
        if (policy.RoadNodesPerTick < 1 || policy.RoadNodesPerTick > 1024 || policy.RoadNodesPerWorkUnit < 1 || policy.RoadNodesPerWorkUnit > 64) { return false; }
        if (policy.SeekMeters < 5 || policy.SeekMeters > 200 || policy.SeekSeconds < 1 || policy.SeekSeconds > 300) { return false; }
        if (policy.PlayerClaimMeters < 50 || policy.PlayerClaimMeters > 1000 || policy.BoardMeters < 1 || policy.BoardMeters > 10) { return false; }
        if (policy.ApproachSeconds < 10 || policy.ApproachSeconds > 600 || policy.BoardSeconds < 5 || policy.BoardSeconds > 300) { return false; }
        if (policy.ExitSeconds < 1 || policy.ExitSeconds > 120 || policy.NodeReachMeters < 1 || policy.NodeReachMeters > 50) { return false; }
        if (policy.ArriveMeters < 1 || policy.ArriveMeters > 100 || policy.DismountMeters < 0 || policy.DismountMeters > 500) { return false; }
        if (policy.MaxApproachMeters < 5 || policy.MaxApproachMeters > 200 || policy.MinDriveMeters < 50 || policy.MinDriveMeters > 2000) { return false; }
        if (policy.MaxDriveMeters < policy.MinDriveMeters || policy.MaxDriveMeters > 5000 || policy.DetourMeters < 0 || policy.DetourMeters > 2000) { return false; }
        if (policy.CruiseKmh < 5 || policy.CruiseKmh > 60 || policy.TurnKmh < 3 || policy.TurnKmh > policy.CruiseKmh) { return false; }
        if (policy.SpeedBandKmh < 1 || policy.SpeedBandKmh > 20 || policy.TurnRadians <= 0 || policy.TurnRadians > 1.6) { return false; }
        if (policy.SteerGain <= 0 || policy.SteerGain > 8 || policy.Throttle <= 0 || policy.Throttle > 1) { return false; }
        if (policy.BrakeStrength <= 0 || policy.BrakeStrength > 1 || policy.StopKmh <= 0 || policy.StopKmh > 10) { return false; }
        if (policy.StopSeconds < 1 || policy.StopSeconds > 60 || policy.StallMeters <= 0 || policy.StallMeters > 50) { return false; }
        return policy.StallSeconds >= 3 && policy.StallSeconds <= 120 && policy.MaxDriveSeconds >= 30 && policy.MaxDriveSeconds <= 1800;
    }
}

class HCConvoyRules
{
    // A world car qualifies only when nobody uses, claims or stores in it. The
    // empty-cargo rule is a conservative ownership heuristic, not ownership proof.
    static string HCVehicleProblem(HCConvoyPolicy p, bool destroyed, bool operational, int wheels, int present, bool crewed, bool flipped, int seats, int members, int cargo, float nearestPlayer)
    {
        if (destroyed) { return "CONVOY_VEHICLE_DESTROYED"; }
        if (crewed) { return "CONVOY_VEHICLE_CREWED"; }
        if (nearestPlayer < p.PlayerClaimMeters) { return "CONVOY_VEHICLE_PLAYER_NEAR"; }
        if (cargo > 0) { return "CONVOY_VEHICLE_HAS_CARGO"; }
        if (!operational) { return "CONVOY_VEHICLE_NOT_OPERATIONAL"; }
        if (wheels < 1 || present < wheels) { return "CONVOY_VEHICLE_WHEELS_MISSING"; }
        if (flipped) { return "CONVOY_VEHICLE_FLIPPED"; }
        if (seats < members) { return "CONVOY_VEHICLE_SEATS"; }
        return "";
    }

    // angle is the native signed bearing to the next road point in radians.
    // Outputs are clamped to the native <0,1>/<-1,1> ranges.
    static void HCControl(HCConvoyPolicy p, float angle, float speedKmh, float remainingMeters, bool stopping, HCConvoyControl c)
    {
        if (stopping)
        {
            c.Steering = 0;
            c.Throttle = 0;
            c.Brake = 1;
            return;
        }
        c.Steering = Math.Clamp(angle / Math.PI * p.SteerGain, -1, 1);
        float target = p.CruiseKmh;
        if (Math.AbsFloat(angle) > p.TurnRadians || remainingMeters < 2 * p.ArriveMeters) { target = p.TurnKmh; }
        c.Throttle = 0;
        c.Brake = 0;
        if (speedKmh > target + p.SpeedBandKmh)
        {
            c.Brake = p.BrakeStrength;
            return;
        }
        if (speedKmh > target) { return; }
        c.Throttle = p.Throttle;
    }

    static bool HCStalled(HCConvoyPolicy p, float moved, int elapsedMs)
    {
        if (moved >= p.StallMeters) { return false; }
        return elapsedMs >= p.StallSeconds * 1000;
    }
}
