// Original bounded public protocol. IDs scanned against this repository and
// installed native 1.30, not a promise of third-party collision freedom.
enum HCEventWire
{
    VERSION = 1,
    RPC_REQUEST = 4853801,
    RPC_VIEW = 4853802,
    MENU_EVENTS = 48538
}
enum HCEventWireOp
{
    BROWSE = 0,
    JOIN = 1,
    LEAVE = 2
}
enum HCEventWireCode
{
    RATE = 8,
    SESSION = 9,
    ORDER = 10,
    DISABLED = 11
}
class HCEventWireRequest
{
    int Version = 1;
    int Op = 0;
    string Session;
    int RequestId = 0;
    int Ticket = 0;
    int EventId = 0;
}
class HCEventPublicRow
{
    int EventId = 0;
    int Revision = 0;
    int Family = 0;
    string Title;
    int Status = 0;
    int Progress = 0;
    int Goal = 0;
    int Participants = 0;
    int MaxParticipants = 0;
    int RemainingSeconds = 0;
    bool Joined = false;
}
class HCEventPublicView
{
    int Version = 1;
    string Session;
    int Sequence = 0;
    int Ticket = 0;
    int Code = 0;
    bool Enabled = false;
    int LastRequest = 0;
    int ReceiptId = 0;
    int ReceiptOp = 0;
    int ReceiptEventId = 0;
    int ReceiptCode = 0;
    ref array<ref HCEventPublicRow> Rows = new array<ref HCEventPublicRow>();
}
