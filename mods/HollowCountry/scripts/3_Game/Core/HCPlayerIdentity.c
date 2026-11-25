// Native scripts-1.30.164289, inspected read-only:
// 3_Game/gameplay.c:338 PlayerIdentityBase, :368 GetId, :388 PlayerIdentity.
// RPC senders and player identities can wrap the same player in different script refs.
class HCPlayerIdentity
{
    static bool Same(PlayerIdentity a, PlayerIdentity b)
    {
        if (!a || !b) return false;
        string id = a.GetId();
        return id != "" && id == b.GetId();
    }
}
