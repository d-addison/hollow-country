// Supplementary local attention graph. All emissions originate in the installed
// native animation voice path. Receiving a clue never forces a sound or creates
// a synthetic NoiseTarget. Each next hop waits for a real native vocalization.
// Stimulus category/provenance contract: HCHordeStimulus.c. Only actual local
// native voice supplies provenance 1; strength halves per hop, expiry is rooted.
// Native surface inspected in the installed scripts-1.30.164289 snapshot at
// ~/.cache/hollow-country/native-scripts/scripts-1.30.164289/:
// 3_Game/gameplay.c:636 GetGame; 3_Game/Global/Game.c:1120 IsServer;
// 3_Game/Entities/Object.c:517 IsAlive, :287 GetPosition;
// 4_World/Entities/Creatures/Infected/ZombieBase.c:182 GetMindStateSynced;
// :556 native voice callback; 3_Game/Entities/DayZInfected.c:13 MINDSTATE_CALM;
// 3_Game/constants.c:33/:34 fire/view geometry constants;
// 1_Core/proto/EnMath.c:553 Math.Min; 1_Core/proto/EnConvert.c:210 DistanceSq;
// 3_Game/Global/DayZPhysics.c:199 RaycastRV (out locals declared before calls);
// 1_Core/proto/EnScript.c:380/:385/:394/:407/:463 array Count/Clear/Find/Insert/Remove,
// :743/:744 set Count/Clear. Geometry is a conservative relay gate, not proof of
// native hearing or rendered audio. Two-client runtime qualification is pending.
class HCAlertRoot
{
    int RootId;
    float RootObserved;
    float RootExpires;
    ref array<ZombieBase> Recipients = new array<ZombieBase>;
    ref array<ZombieBase> Emitters = new array<ZombieBase>;
}

class HCAlertEmission
{
    ZombieBase Emitter;
    ref HCAlertRoot Root;
    ref HCInfectedClue Clue;
    int StartCursor;
    int Scanned;
}

class HCAlertChain
{
    protected ref array<ref HCAlertRoot> m_Roots = new array<ref HCAlertRoot>;
    protected ref array<ref HCAlertEmission> m_Queue = new array<ref HCAlertEmission>;
    protected int m_NextRootId = 1;
    protected int m_RecipientCursor;

    protected HCAlertRoot FindRoot(int id)
    {
        foreach (HCAlertRoot root : m_Roots)
        {
            if (root.RootId == id)
                return root;
        }
        return null;
    }

    protected void Expire(float now)
    {
        // Both arrays have fixed hard caps, independently of entity count.
        for (int q = m_Queue.Count() - 1; q >= 0; q--)
        {
            if (!m_Queue[q].Clue.IsLive(now) || now - m_Queue[q].Clue.Observed > 2)
                m_Queue.Remove(q);
        }
        for (int r = m_Roots.Count() - 1; r >= 0; r--)
        {
            if (HCInfectedPolicy.RootSlotReusable(now, m_Roots[r].RootExpires))
                m_Roots.Remove(r);
        }
    }

    void NativeEmission(HCInfectedActor actor, int eventId, float now, int queueCap, int trackedCount)
    {
        if (!GetGame().IsServer() || !actor || !actor.InfectedEntity || !actor.InfectedEntity.IsAlive())
            return;
        Expire(now);
        queueCap = Math.Min(queueCap, 16);
        if (queueCap < 1 || m_Queue.Count() >= queueCap || trackedCount < 1 || trackedCount > 24)
            return;
        HCAlertRoot root;
        int hops = 0;
        float strength = 1;
        if (actor.Heard && actor.Heard.IsLive(now))
        {
            root = FindRoot(actor.HeardRootId);
            // An exhausted/duplicate/expired inherited root cannot become a
            // fresh root during the same live clue. No TTL reset or echo loop.
            if (!root || root.Emitters.Find(actor.InfectedEntity) >= 0)
                return;
            if (!HCInfectedPolicy.MayRelay(now, root.RootObserved, root.RootExpires, actor.Heard.Hops, actor.Heard.Strength, true, true))
                return;
            hops = actor.Heard.Hops;
            strength = actor.Heard.Strength;
        }
        else
        {
            // Ambient calm grunts are real sounds but are not threat evidence
            // for a new supplementary alarm root.
            if (actor.InfectedEntity.GetMindStateSynced() == DayZInfectedConstants.MINDSTATE_CALM)
                return;
            if (m_Roots.Count() >= 8 || m_NextRootId >= 2000000000)
                return;
            root = new HCAlertRoot;
            root.RootId = m_NextRootId++;
            root.RootObserved = now;
            root.RootExpires = now + Math.Min(actor.ClueLifetime, 30);
            root.Recipients.Insert(actor.InfectedEntity);
            m_Roots.Insert(root);
            // The seed cannot hear itself or relay its own root again.
            actor.Heard = new HCInfectedClue;
            actor.Heard.Provenance = 1;
            actor.Heard.Observed = now;
            actor.Heard.Expires = root.RootExpires;
            actor.Heard.Hops = 0;
            actor.HeardRootId = root.RootId;
            actor.Heard.Origin = actor.InfectedEntity.GetPosition();
            actor.HeardExternally = false;
        }
        if (!HCInfectedPolicy.MayRelay(now, root.RootObserved, root.RootExpires, hops, strength, true, true))
            return;
        HCAlertEmission emission = new HCAlertEmission;
        emission.Emitter = actor.InfectedEntity;
        emission.StartCursor = m_RecipientCursor % trackedCount;
        m_RecipientCursor = HCInfectedPolicy.NextAdoptionCursor(m_RecipientCursor, trackedCount);
        emission.Root = root;
        emission.Clue = new HCInfectedClue;
        emission.Clue.Provenance = 1;
        emission.Clue.Origin = actor.InfectedEntity.GetPosition();
        if (!HCInfectedStore.ValidPosition(emission.Clue.Origin))
            return;
        emission.Clue.Observed = now;
        emission.Clue.Expires = root.RootExpires;
        emission.Clue.Hops = hops + 1;
        emission.Clue.Strength = HCInfectedPolicy.Attenuate(strength);
        emission.Clue.EventId = eventId;
        root.Emitters.Insert(actor.InfectedEntity);
        m_Queue.Insert(emission);
    }

    protected bool ClearGeometry(vector origin, ZombieBase emitter, ZombieBase recipient)
    {
        vector contact, normal;
        int component;
        ref set<Object> hits = new set<Object>;
        vector point = recipient.GetPosition() + "0 1.4 0";
        bool hit = DayZPhysics.RaycastRV(origin + "0 1.4 0", point, contact, normal, component, hits, null, emitter, true, false, ObjIntersectView);
        if (!hit || hits.Count() == 0 || hits[0] != recipient)
            return false;
        hits.Clear();
        hit = DayZPhysics.RaycastRV(origin + "0 1.4 0", point, contact, normal, component, hits, null, emitter, true, false, ObjIntersectFire);
        return hit && hits.Count() > 0 && hits[0] == recipient;
    }

    int ProcessPending(array<ref HCInfectedActor> actors, float now, int work)
    {
        Expire(now);
        int spent = 0;
        if (!GetGame().IsServer() || !actors || actors.Count() < 1 || actors.Count() > 24)
            return spent;
        // One bounded tracked recipient per work item, up to two geometry tests.
        // No GetPlayers/global entity enumeration or unbounded spatial result.
        while (spent < work && m_Queue.Count() > 0)
        {
            spent++;
            HCAlertEmission emission = m_Queue[0];
            if (!emission.Emitter || !emission.Emitter.IsAlive() || emission.Scanned >= actors.Count() || emission.Root.Recipients.Count() >= 12)
            {
                m_Queue.Remove(0);
                continue;
            }
            // Rotate across emissions: the short two-second processing window
            // must not always favor the first registered actors under overload.
            int index = (emission.StartCursor + emission.Scanned) % actors.Count();
            emission.Scanned++;
            HCInfectedActor actor = actors[index];
            if (!actor.InfectedEntity || !actor.InfectedEntity.IsAlive() || actor.InfectedEntity == emission.Emitter)
                continue;
            float distanceSq = vector.DistanceSq(emission.Clue.Origin, actor.InfectedEntity.GetPosition());
            // Conservative pilot radius; never an assertion about sound range.
            float radius = 15 * emission.Clue.Strength;
            bool duplicate = emission.Root.Recipients.Find(actor.InfectedEntity) >= 0;
            if (duplicate || distanceSq > radius * radius || now < actor.NextHearing)
                continue;
            bool geometry = ClearGeometry(emission.Clue.Origin, emission.Emitter, actor.InfectedEntity);
            if (!HCInfectedPolicy.MayHearRelay(now, emission.Root.RootExpires, emission.Clue.Hops, emission.Clue.Strength, distanceSq, emission.Root.Recipients.Count(), 12, duplicate, true, geometry, actor.NextHearing))
                continue;
            emission.Root.Recipients.Insert(actor.InfectedEntity);
            actor.Heard = emission.Clue;
            actor.HeardRootId = emission.Root.RootId;
            actor.HeardExternally = true;
            actor.SearchAttempts = 0;
            actor.Clue = emission.Clue;
            actor.NextHearing = now + 10;
        }
        return spent;
    }
}
