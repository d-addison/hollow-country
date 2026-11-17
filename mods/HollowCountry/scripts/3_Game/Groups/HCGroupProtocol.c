// Original private group protocol. IDs scanned against repository/native 1.30;
// third-party collision freedom and live delivery remain qualification work.
class HCGroupProtocol
{
    static const int VERSION = 1;
    static const int RPC_REQUEST = 4853701;
    static const int RPC_SNAPSHOT = 4853702;
    static const int RPC_REPLY = 4853703;
    static const int MENU_MAP = 48537;
}
enum HCGroupOp
{
    SYNC = 0, CREATE = 1, INVITE = 2, ACCEPT = 3, DECLINE = 4,
    LEAVE = 5, KICK = 6, TRANSFER = 7, DISBAND = 8,
    MARKER_CREATE = 9, MARKER_UPDATE = 10, MARKER_DELETE = 11, RENAME = 12
}
enum HCGroupCode
{
    OK = 0, DISABLED = 1, INVALID = 2, DENIED = 3, CONFLICT = 4,
    LIMIT = 5, NOT_FOUND = 6, STORAGE = 7, RATE = 8, SESSION = 9
}
enum HCGroupSnapshotKind
{
    FULL = 0, POSITIONS = 1, CLEAR = 2
}
