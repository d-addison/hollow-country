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
    static const string SIPHON_RECEIPT = "siphon_receipt_mismatch";
    static const string SIPHON_DIAGNOSTIC = "siphon_diagnostic_unavailable";
    static const string TAPED_LIGHT_MOUNT = "taped_light_mount_unavailable";
    static const string TAPED_LIGHT_REMOVE = "taped_light_remove_unavailable";
}
