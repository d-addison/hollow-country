// Test-only allocation: scanned against the repo's global RPC inventory (HC-E054).
// Native scripts-1.30.164289: 3_Game/gameplay.c:104-117 ScriptRPC.Send;
// 1_Core/proto/Serializer.c:57-58 Write/Read. No product RPC is reused.
class HCDriverMoveWire
{
    // Direction selects schema: client request = serial/speed/angle/lease/apply;
    // owner-only server close reply = serial/reason. Both ends reject stale serials.
    static const int RPC_MOVE = 4854091;
}
