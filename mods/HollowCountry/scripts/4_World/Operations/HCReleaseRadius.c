// Server evidence for one current radius. A character must be observed outside
// and later inside the same radius; spawning inside supplies no observation.
class HCReleaseRadius
{
    protected ref array<Man> m_Outside = new array<Man>;
    protected ref array<Man> m_NextOutside = new array<Man>;

    void HCSample(vector centre, float radius, int observation)
    {
        if (!GetGame() || !GetGame().IsServer() || radius <= 0) { return; }
        array<Man> players = HCPerfPlayers.HCGet();
        float radiusSq = radius * radius;
        m_NextOutside.Clear();
        for (int index = 0; index < players.Count() && index < 64; index++)
        {
            Man man = players[index];
            PlayerBase player = PlayerBase.Cast(man);
            if (!player || !player.IsAlive() || !player.GetIdentity() || player.HCHasReleaseRadius(observation)) { continue; }
            vector position = player.GetPosition();
            position[1] = centre[1];
            if (vector.DistanceSq(position, centre) > radiusSq) { m_NextOutside.Insert(man); }
            else if (m_Outside.Find(man) >= 0) { player.HCSendReleaseRadius(observation); }
        }
        m_Outside.Copy(m_NextOutside);
        m_NextOutside.Clear();
    }
}

modded class PlayerBase
{
    protected bool m_HCReleaseAISiteEntered;
    protected bool m_HCReleaseMissionEntered;

    bool HCHasReleaseRadius(int observation)
    {
        if (observation == HCReleaseRadiusWire.AI_SITE) { return m_HCReleaseAISiteEntered; }
        if (observation == HCReleaseRadiusWire.MISSION) { return m_HCReleaseMissionEntered; }
        return true;
    }

    void HCSendReleaseRadius(int observation)
    {
        if (!GetGame() || !GetGame().IsServer() || HCHasReleaseRadius(observation)) { return; }
        PlayerIdentity recipient = GetIdentity();
        if (!recipient) { return; }
        if (observation == HCReleaseRadiusWire.AI_SITE) { m_HCReleaseAISiteEntered = true; }
        else { m_HCReleaseMissionEntered = true; }
        ScriptRPC rpc = new ScriptRPC;
        rpc.Write(observation);
        rpc.Send(null, HCReleaseRadiusWire.RPC_ENTRY, true, recipient);
    }
}
