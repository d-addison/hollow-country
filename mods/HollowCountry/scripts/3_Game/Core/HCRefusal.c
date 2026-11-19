// Shared stable refusal codes; no World types, so every later script layer sees them.
class HCRefusal
{
    static const string SERVICE = "service";
    static const string BUSY = "busy";
    static const string CAPACITY = "capacity";
    static const string NO_SITE = "no_site";
    static const string NOTHING = "nothing";
    static const string HANDS = "hands";
    static const string SESSION = "session_changed";
    static const string TOO_EARLY = "too_early";
    static const string SUPPLY = "supply_changed";
    static const string STORAGE = "storage_unavailable";
    static const string FLIP = "flip_unavailable";
    static const string SALVAGE = "salvage_unavailable";
    static const string SIPHON = "siphon_unavailable";
    static const string SIPHON_CLOSED = "siphon_closed";
    static const string SIPHON_FULL = "siphon_full";
    static const string SIPHON_LIQUID = "siphon_liquid";
    static const string SIPHON_RANGE = "siphon_range";
    static const string SIPHON_LOS = "siphon_los";
    static const string SIPHON_MOVING = "siphon_moving";
    static const string SIPHON_RESTRAINED = "siphon_restrained";
    static const string SIPHON_OFF = "siphon_service_off";
    static const string SIPHON_RECEIPT = "siphon_receipt_mismatch";
    static const string SIPHON_DIAGNOSTIC = "siphon_diagnostic_unavailable";
    static const string TAPED_LIGHT_MOUNT = "taped_light_mount_unavailable";
    static const string TAPED_LIGHT_REMOVE = "taped_light_remove_unavailable";

    static string SiphonMessage(string reason)
    {
        if (reason == SIPHON_CLOSED) return "Open the fuel container first.";
        if (reason == SIPHON_FULL) return "The fuel container is full.";
        if (reason == SIPHON_LIQUID) return "Use a container that accepts gasoline.";
        if (reason == SIPHON_RANGE) return "Move closer to the fuel tank.";
        if (reason == SIPHON_LOS) return "The fuel tank is obstructed.";
        if (reason == SIPHON_MOVING) return "Stop the vehicle first.";
        if (reason == SIPHON_RESTRAINED) return "Free your hands before siphoning.";
        if (reason == SIPHON_OFF) return "Fuel siphoning is unavailable on this server.";
        return "Cannot siphon fuel now; check the car, container and server availability.";
    }
}

// Optional caller-owned result: checks can report a cause without global state.
// No World types; usable from every layer alongside the shared reason codes.
class HCRefusalResult
{
    string Reason;

    bool Refuse(string reason)
    {
        Reason = reason;
        return false;
    }
}
