// HCX AI self-defence and near-miss response (owner bug 2026-11-18: AI "didn't
// seem to mind being punched, shot, or killed").
// Expansion sources read from the installed Expansion-AI Workshop item
// (addons/ai_scripts.pbo, paths below relative to its scripts root) and Expansion-Core
// (addons/core_scripts.pbo, marked CORE). Read-only; nothing is copied.
// Cause: every HCXFaction is a guard faction, so Expansion only lets it fight a
// player who raises a weapon at it (4_World/DayZExpansion_AI/Classes/Targets/
// eAIPlayerTargetInformation.c:163-170), and the HCX stance override of
// CalculateThreat (HCXStance.c) clears the hostile seed Expansion plants on a hit:
//   Entities/DayZPlayerImplement.c:472 EEHitBy -> :514-516 attacker
//     GetTargetInformation().AddFriendlyAI(victim, 120000, true, 1.0);
//   Classes/Targets/eAITargetInformation.c:388 AddFriendlyAI(DayZPlayerImplement
//     player, int maxTime, bool update, float threat): seeds the hit AI at the
//     attacker (:452-453) and group-mates that already track the attacker at the
//     victim position; :339 AddAI(eAIBase, int maxTime, bool initialUpdate, out
//     bool created); :360 GetTargetForAI.
//   Classes/eAIGroup.c:708 AddTarget(DayZPlayerImplement player,
//     eAITargetInformation info, int max_time, bool update, float threat) seeds
//     every member (:737-740) regardless of perception, so it is NOT used here.
// Expansion skips the killing blow (DayZPlayerImplement.c:479-480), so a kill is
// recorded here and nearby mates that already track the killer are seeded at the
// victim's position through the same per-target steps AddTarget uses.
// m_SearchOnLOSLost (Classes/Targets/eAITargetInformationState.c:14) is set true by
// live LOS (Entities/AI/eAIBase.c:8367-8368) but also by every native seed
// (eAITargetInformation.c:457, eAIGroup.c:740, eAIBase.c:4202), so it is not proof
// of perception and is never read here. A grudge applies to an actor only with
// m_LOS (eAITargetInformationState.c:15), LOS within 15 s, or the 20 s native
// hit-direction window after that very actor was seeded (HCXDefencePolicy.Active).
// This file adds only a bounded, expiring per-player grudge, read by the stance
// override before it clears threat (Hostile). Hostility is toward that player
// from that victim group only, never faction-wide.
// Near misses: a bullet passing within 4 m of an actor before the shot ray's first
// hit (one DayZPhysics.RaycastRV with ObjIntersectFire per evaluated shot, 200 m
// cap, as Expansion does at Entities/Weapons/Firearms/Weapon_Base.c:46 and
// eAIBase.c:8217), a loud weapon fired within 12 m, or a native bullet-impact
// noise within 4 m (Entities/Weapons/Firearms/Weapon_Base.c:329 EEFired,
// :404-424 eAI_FirearmEffects -> BULLETIMPACT noise; Classes/ExpansionWorld.c:476-481
// FirearmEffects; 3_Game/DayZExpansion_AI/eAINoiseSystem.c:1-6 eAINoiseType;
// Entities/AI/eAIBase.c:4118 eAI_OnNoiseEvent, :4158,:4184 BULLETIMPACT handling).
// A pass-by needs a clear fire-geometry line from the closest point on the ray to
// the actor. The seed position of a near miss is where the shot was heard (the
// shooter's position at the shot, as the native SHOT noise reports), or the impact
// point; never the live position of the shooter.
// A shot is never aggression when an infected stands within 25 m of the shooter or
// the actor, or died there within 6 s (rescue shots). A first non-lethal hit on a
// friendly or allied actor with infected near is a stray rescue round and excused
// once per 30 s; a second hit or any kill grudges.
// The aim ray uses Expansion_GetAimDirection: vector, no arguments, defined at
// CORE 4_World/DayZExpansion_Core/Entities/ManBase/DayZPlayerImplement.c:523 (head
// bone / orientation, an approximation on a server, same file :521-522); AI side
// uses at eAIPlayerTargetInformation.c:147.
// Reused Expansion hooks: Entities/AI/eAIBase.c:1344 EEHitBy, :1368 EEKilled,
// :466 eAI_GetAll, :969 PlayerIsEnemy; Entities/DayZPlayerImplement.c:106
// GetTargetInformation.
// Bounds: <=64 grudges (oldest evicted), 240/300/90/30 s expiry, per-player 750 ms
// and 6 evaluations per second shot spacing, <=24 actors scanned, <=3 near-miss
// candidates, <=1 shot raycast + <=3 LOS raycasts + <=2 GetObjectsAtPosition3D per
// shot, <=8 recent infected deaths, <=12 actor slots per grudge, pruning <=8
// grudges per tick inside an HCWorkBudget slice. No position writes, no
// teleports, no new noise, no player scans. Flee-or-fight temperament stays
// Expansion's: GetMinDistance (eAIPlayerTargetInformation.c:245-270) still makes
// weak or outgunned actors flee. Offline smoke proves wiring only; native hostility
// is runtime-PENDING.
class HCXGrudge
{
    // eAIGroup is not Managed, so only the id is kept; HCXExpansionBridge.HCGroupById resolves it per use.
    int GroupId;
    PlayerBase Attacker;
    int Until;
    int Kind;
    vector Origin;
    // Weak handles, compared by identity only; a deleted actor's slot ages out at the 12-slot bound.
    ref array<ref HCXAIAgentHold> Actors = new array<ref HCXAIAgentHold>;
    ref array<int> LosAt = new array<int>;
    ref array<int> SeedAt = new array<int>;

    // Per-actor perception slot (LOS memory and native seed time), at most 12.
    int ActorSlot(eAIBase ai, bool create)
    {
        for (int index = 0; index < Actors.Count(); index++)
        {
            if (HCXExpansionBridge.HCAgentSame(Actors.Get(index), ai)) { return index; }
        }
        if (!create || !ai) { return -1; }
        if (Actors.Count() >= 12)
        {
            Actors.RemoveOrdered(0);
            LosAt.RemoveOrdered(0);
            SeedAt.RemoveOrdered(0);
        }
        Actors.Insert(HCXExpansionBridge.HCAgentHold(ai));
        LosAt.Insert(0);
        SeedAt.Insert(0);
        return Actors.Count() - 1;
    }

    void NoteSeed(eAIBase ai, int nowMs)
    {
        int slot = ActorSlot(ai, true);
        if (slot >= 0) { SeedAt.Set(slot, nowMs); }
    }
}

class HCXShotGate
{
    PlayerBase Player;
    int Next;
    int NextImpact;
    int ExcusedUntil;
}

class HCXDefence
{
    protected static bool s_Running;
    protected static ref array<ref HCXGrudge> s_Grudges = new array<ref HCXGrudge>;
    protected static ref array<ref HCXShotGate> s_Gates = new array<ref HCXShotGate>;
    protected static ref array<vector> s_DeathPos = new array<vector>;
    protected static ref array<int> s_DeathAt = new array<int>;
    protected static ref HCWorkBudget s_Budget = new HCWorkBudget;
    protected static int s_Cursor;
    protected static int s_WindowStart;
    protected static int s_WindowCount;
    protected static int s_Hits;
    protected static int s_Kills;
    protected static int s_NearMisses;
    protected static int s_Excused;
    protected static int s_RescueHits;
    protected static int s_Refused;
    protected static int s_Evicted;
    protected static int s_Expired;
    protected static int s_Applied;
    protected static int s_Logged;
    protected static float s_SummaryAfter;
    protected static bool s_FirstHit;
    protected static bool s_FirstKill;
    protected static bool s_FirstMiss;
    protected static bool s_FirstExcuse;
    protected static bool s_FirstApplied;

    static void Start()
    {
        s_Grudges.Clear();
        s_Gates.Clear();
        s_DeathPos.Clear();
        s_DeathAt.Clear();
        s_Cursor = 0;
        s_Running = true;
        s_SummaryAfter = GetGame().GetTickTime() + 60;
    }

    static void Stop()
    {
        s_Running = false;
        s_Grudges.Clear();
        s_Gates.Clear();
        s_DeathPos.Clear();
        s_DeathAt.Clear();
    }

    static bool Running() { return s_Running; }

    static int Count() { return s_Grudges.Count(); }

    // The real player behind a weapon, item or fist, or null. AI attackers have no
    // identity and never provoke a grudge (Expansion handles AI versus AI).
    static PlayerBase AttackerOf(EntityAI source)
    {
        if (!source) { return null; }
        PlayerBase attacker = PlayerBase.Cast(source.GetHierarchyRoot());
        if (!attacker || attacker.IsInherited(eAIBase)) { return null; }
        if (!attacker.GetIdentity() || !attacker.IsAlive()) { return null; }
        return attacker;
    }

    // Keyed by group id (never reused by the provider's counter). The grudge keeps no
    // group handle: the prune pass resolves the id and drops the grudge once the group is gone.
    protected static HCXGrudge Find(eAIGroup group, PlayerBase attacker)
    {
        if (!group || !attacker) { return null; }
        int groupId = HCXExpansionBridge.HCGroupGetID(group);
        for (int index = 0; index < s_Grudges.Count(); index++)
        {
            HCXGrudge grudge = s_Grudges.Get(index);
            if (grudge && grudge.GroupId == groupId && grudge.Attacker == attacker) { return grudge; }
        }
        return null;
    }

    protected static HCXGrudge Record(eAIGroup group, PlayerBase attacker, vector origin, int kind, int nowMs)
    {
        if (!group || !attacker) { return null; }
        int until = nowMs + HCXDefencePolicy.HoldMs(kind);
        HCXGrudge grudge = Find(group, attacker);
        if (grudge)
        {
            if (until > grudge.Until) { grudge.Until = until; }
            if (kind < grudge.Kind) { grudge.Kind = kind; }
            grudge.Origin = origin;
            return grudge;
        }
        int evict = HCXDefencePolicy.EvictIndex(s_Grudges.Count(), HCXDefencePolicy.GRUDGE_CAP);
        if (evict >= 0)
        {
            s_Grudges.RemoveOrdered(evict);
            s_Evicted++;
        }
        grudge = new HCXGrudge();
        grudge.GroupId = HCXExpansionBridge.HCGroupGetID(group);
        grudge.Attacker = attacker;
        grudge.Until = until;
        grudge.Kind = kind;
        grudge.Origin = origin;
        s_Grudges.Insert(grudge);
        return grudge;
    }

    // Called by the stance override before it clears an unseen threat. True only
    // while this actor's group holds an unexpired grudge against this player and
    // the actor perceived the attacker: live LOS, LOS within 15 s, or the 20 s
    // native hit-direction window after this actor itself was seeded.
    static bool Hostile(eAIBase ai, PlayerBase player, eAITargetInformationState state)
    {
        if (!s_Running || !ai || !player || !state) { return false; }
        // A downed or dead player is never pursued further.
        if (!player.IsAlive() || player.IsUnconscious()) { return false; }
        eAIGroup group = HCXExpansionBridge.HCDayZPlayerImplementGetGroup(ai);
        if (!group || group == HCXExpansionBridge.HCDayZPlayerImplementGetGroup(player)) { return false; }
        HCXGrudge grudge = Find(group, player);
        if (!grudge || grudge.Kind == HCXDefencePolicy.KIND_RESCUE) { return false; }
        int nowMs = GetGame().GetTime();
        int slot = grudge.ActorSlot(ai, state.m_LOS);
        int lastLos = 0;
        int seededAt = 0;
        if (slot >= 0)
        {
            if (state.m_LOS) { grudge.LosAt.Set(slot, nowMs); }
            lastLos = grudge.LosAt.Get(slot);
            seededAt = grudge.SeedAt.Get(slot);
        }
        float distance = vector.Distance(HCXExpansionBridge.HCBaseGetPosition(ai), grudge.Origin);
        if (!HCXDefencePolicy.Active(nowMs, grudge.Until, distance, state.m_LOS, lastLos, seededAt)) { return false; }
        s_Applied++;
        if (!s_FirstApplied)
        {
            s_FirstApplied = true;
            Print("[HCX Defence] first self-defence threat applied kind=" + grudge.Kind.ToString() + " (native hostility PENDING observation)");
        }
        return true;
    }

    // Seeds one actor on the aggressor's target information the way Expansion's own
    // AddTarget does per member (eAIGroup.c:731-743), at a position that was heard
    // or seen, never the aggressor's live position.
    protected static void SeedTarget(eAITargetInformation info, eAIBase actor, int holdMs, float threat, vector at)
    {
        if (!info || !actor) { return; }
        bool created;
        eAITarget target = HCXExpansionBridge.HCTargetInformationAddAI(info, actor, holdMs, false, created);
        if (!target) { return; }
        if (!created) { HCXExpansionBridge.HCTargetUpdateFoundAtTime(target); }
        if (threat > target.m_ThreatLevelActive)
        {
            if (!target.m_SearchOnLOSLost)
            {
                HCXExpansionBridge.HCTargetSetInitial(target, threat, at);
                target.m_SearchOnLOSLost = true;
            }
            else
            {
                HCXExpansionBridge.HCTargetSetThreat(target, threat);
            }
        }
    }

    // Expansion already seeded the hit AI's group (EEHitBy -> AddFriendlyAI); this
    // keeps the stance override from clearing it for the grudge duration, unless the
    // hit is a first stray round on a friendly during a rescue.
    static void OnHit(eAIBase victim, EntityAI source)
    {
        if (!s_Running || !victim || !HCXExpansionBridge.HCBaseIsAlive(victim) || !HCXStance.Owns(victim)) { return; }
        PlayerBase attacker = AttackerOf(source);
        if (!attacker) { return; }
        eAIGroup group = HCXExpansionBridge.HCDayZPlayerImplementGetGroup(victim);
        if (!group || group == HCXExpansionBridge.HCDayZPlayerImplementGetGroup(attacker)) { return; }
        int nowMs = GetGame().GetTime();
        HCXGrudge prior = Find(group, attacker);
        int priorUntil = 0;
        if (prior) { priorUntil = prior.Until; }
        // Infected are looked up only for a possible excuse: friendly actor and no
        // live record for this pair, so at most one lookup pair per 30 s per pair.
        if (HCXStance.Relation(victim, attacker) >= 0 && nowMs >= priorUntil)
        {
            int infectedShooter = InfectedNear(attacker.GetPosition(), nowMs);
            int infectedActor = 0;
            if (infectedShooter == 0) { infectedActor = InfectedNear(HCXExpansionBridge.HCBaseGetPosition(victim), nowMs); }
            if (HCXDefencePolicy.RescueHitExcused(true, infectedShooter + infectedActor, HCXExpansionBridge.HCBaseIsDamageDestroyed(victim), nowMs, priorUntil))
            {
                Record(group, attacker, HCXExpansionBridge.HCBaseGetPosition(victim), HCXDefencePolicy.KIND_RESCUE, nowMs);
                s_RescueHits++;
                if (!s_FirstExcuse)
                {
                    s_FirstExcuse = true;
                    Print("[HCX Defence] first excused_rescue_hit: friendly hit with infected near");
                }
                return;
            }
        }
        HCXGrudge grudge = Record(group, attacker, HCXExpansionBridge.HCBaseGetPosition(victim), HCXDefencePolicy.KIND_HIT, nowMs);
        if (grudge) { grudge.NoteSeed(victim, nowMs); }
        HCModuleReadiness.HCUse("AISelfDefence", "hit_reaction");
        s_Hits++;
        if (!s_FirstHit)
        {
            s_FirstHit = true;
            Print("[HCX Defence] first player hit on group " + HCXExpansionBridge.HCGroupGetName(group) + " grudge=" + HCXDefencePolicy.HoldMs(HCXDefencePolicy.KIND_HIT).ToString() + "ms");
        }
    }

    // Expansion skips the killing blow, so seed nearby living members that already
    // track the killer at the victim's position (the hit direction, never the
    // killer's live position). Members without a target on the killer find them
    // through native perception, which the grudge then lets them act on.
    static void OnKill(eAIBase victim, Object killer)
    {
        if (!s_Running || !victim || !HCXStance.Owns(victim)) { return; }
        PlayerBase attacker = AttackerOf(EntityAI.Cast(killer));
        if (!attacker) { return; }
        eAIGroup group = HCXExpansionBridge.HCDayZPlayerImplementGetGroup(victim);
        if (!group || group == HCXExpansionBridge.HCDayZPlayerImplementGetGroup(attacker)) { return; }
        int nowMs = GetGame().GetTime();
        vector origin = HCXExpansionBridge.HCBaseGetPosition(victim);
        HCXGrudge grudge = Record(group, attacker, origin, HCXDefencePolicy.KIND_KILL, nowMs);
        if (!grudge) { return; }
        s_Kills++;
        eAITargetInformation info = HCXExpansionBridge.HCDayZPlayerImplementGetTargetInformation(attacker);
        if (info)
        {
            int limit = HCXExpansionBridge.HCGroupCount(group);
            if (limit > 16) { limit = 16; }
            for (int seat = 0; seat < limit; seat++)
            {
                eAIBase mate = eAIBase.Cast(HCXExpansionBridge.HCGroupGetMember(group, seat));
                if (!mate || mate == victim || !HCXExpansionBridge.HCBaseIsAlive(mate) || HCXExpansionBridge.HCBaseIsUnconscious(mate)) { continue; }
                if (vector.Distance(HCXExpansionBridge.HCBaseGetPosition(mate), origin) > HCXDefencePolicy.ORIGIN_REACH) { continue; }
                if (!HCXExpansionBridge.HCTargetInformationGetTargetForAI(info, mate)) { continue; }
                SeedTarget(info, mate, HCXDefencePolicy.HoldMs(HCXDefencePolicy.KIND_KILL), 1.0, origin);
                grudge.NoteSeed(mate, nowMs);
            }
        }
        if (!s_FirstKill)
        {
            s_FirstKill = true;
            Print("[HCX Defence] first group member killed by a player group=" + HCXExpansionBridge.HCGroupGetName(group) + " grudge=" + HCXDefencePolicy.HoldMs(HCXDefencePolicy.KIND_KILL).ToString() + "ms");
        }
    }

    // Recent infected deaths excuse a rescue shot whose bullet already killed the
    // infected before the impact is evaluated.
    static void NoteInfectedDeath(vector position)
    {
        if (!s_Running) { return; }
        if (s_DeathPos.Count() >= 8)
        {
            s_DeathPos.RemoveOrdered(0);
            s_DeathAt.RemoveOrdered(0);
        }
        s_DeathPos.Insert(position);
        s_DeathAt.Insert(GetGame().GetTime());
    }

    protected static int InfectedNear(vector position, int nowMs)
    {
        for (int deathIndex = 0; deathIndex < s_DeathPos.Count(); deathIndex++)
        {
            if (nowMs - s_DeathAt.Get(deathIndex) <= 6000 && vector.Distance(position, s_DeathPos.Get(deathIndex)) <= HCXDefencePolicy.INFECTED_RADIUS) { return 1; }
        }
        array<Object> objects = new array<Object>;
        array<CargoBase> proxies = new array<CargoBase>;
        GetGame().GetObjectsAtPosition3D(position, HCXDefencePolicy.INFECTED_RADIUS, objects, proxies);
        for (int objectIndex = 0; objectIndex < objects.Count() && objectIndex < 256; objectIndex++)
        {
            ZombieBase infected = ZombieBase.Cast(objects.Get(objectIndex));
            if (infected && infected.IsAlive()) { return 1; }
        }
        return 0;
    }

    // One server raycast against fire geometry. Returns the contact distance from
    // the start, or -1 when nothing is hit. Objects in `allowed` count as a clear
    // line (the target itself).
    protected static float RayDistance(vector begin, vector end, Object ignore, Object allowed)
    {
        vector contact;
        vector normal;
        int component;
        set<Object> hits = new set<Object>;
        if (!DayZPhysics.RaycastRV(begin, end, contact, normal, component, hits, null, ignore, true, false, ObjIntersectFire)) { return -1; }
        if (allowed && hits.Find(allowed) >= 0) { return -1; }
        return vector.Distance(begin, contact);
    }

    // True when fire geometry stands between the two points (the target excluded).
    protected static bool Blocked(vector begin, vector end, Object ignore, Object target)
    {
        float full = vector.Distance(begin, end);
        float contact = RayDistance(begin, end, ignore, target);
        return contact >= 0 && contact < full - 0.5;
    }

    protected static HCXShotGate Gate(PlayerBase shooter)
    {
        for (int index = 0; index < s_Gates.Count(); index++)
        {
            HCXShotGate held = s_Gates.Get(index);
            if (held && held.Player == shooter) { return held; }
        }
        if (s_Gates.Count() >= 16)
        {
            for (int prune = s_Gates.Count() - 1; prune >= 0; prune--)
            {
                HCXShotGate stale = s_Gates.Get(prune);
                if (!stale || !stale.Player || !stale.Player.IsAlive()) { s_Gates.RemoveOrdered(prune); }
            }
            if (s_Gates.Count() >= 16) { return null; }
        }
        HCXShotGate gate = new HCXShotGate();
        gate.Player = shooter;
        s_Gates.Insert(gate);
        return gate;
    }

    protected static bool WindowAllows(int nowMs, int nextMs)
    {
        if (nowMs - s_WindowStart >= 1000)
        {
            s_WindowStart = nowMs;
            s_WindowCount = 0;
        }
        if (!HCXDefencePolicy.ShotAllowed(nowMs, nextMs, s_WindowCount, HCXDefencePolicy.SHOT_WINDOW_CAP))
        {
            s_Refused++;
            return false;
        }
        s_WindowCount++;
        return true;
    }

    // Records a near-miss grudge and seeds the actor on the shooter's target
    // information at the heard position (shot or impact), then lets Hostile lift it.
    protected static void Provoke(eAIBase actor, PlayerBase shooter, int nowMs, vector heardAt)
    {
        eAIGroup group = HCXExpansionBridge.HCDayZPlayerImplementGetGroup(actor);
        if (!group) { return; }
        eAITargetInformation info = HCXExpansionBridge.HCDayZPlayerImplementGetTargetInformation(shooter);
        if (!info) { return; }
        HCXGrudge grudge = Record(group, shooter, HCXExpansionBridge.HCBaseGetPosition(actor), HCXDefencePolicy.KIND_MISS, nowMs);
        if (!grudge) { return; }
        SeedTarget(info, actor, HCXDefencePolicy.HoldMs(HCXDefencePolicy.KIND_MISS), HCXDefencePolicy.FIGHT_THREAT, heardAt);
        grudge.NoteSeed(actor, nowMs);
        s_NearMisses++;
        if (!s_FirstMiss)
        {
            s_FirstMiss = true;
            Print("[HCX Defence] first near miss on group " + HCXExpansionBridge.HCGroupGetName(group) + " grudge=" + HCXDefencePolicy.HoldMs(HCXDefencePolicy.KIND_MISS).ToString() + "ms");
        }
    }

    protected static void NoteExcuse(HCXShotGate gate, int nowMs)
    {
        gate.ExcusedUntil = nowMs + 8000;
        s_Excused++;
        if (!s_FirstExcuse)
        {
            s_FirstExcuse = true;
            Print("[HCX Defence] first shot excused: infected near the shooter or the actor");
        }
    }

    // Server-side fired-shot check (called from Weapon_Base.EEFired). One cheap pass
    // over the already-maintained AI list, one shot raycast, no world scan.
    static void OnShot(Weapon_Base weapon)
    {
        if (!s_Running || !weapon) { return; }
        PlayerBase shooter = PlayerBase.Cast(weapon.GetHierarchyRootPlayer());
        if (!shooter || shooter.IsInherited(eAIBase) || !shooter.GetIdentity() || !shooter.IsAlive()) { return; }
        int nowMs = GetGame().GetTime();
        HCXShotGate gate = Gate(shooter);
        if (!gate) { s_Refused++; return; }
        if (!WindowAllows(nowMs, gate.Next)) { return; }
        gate.Next = nowMs + HCXDefencePolicy.SHOT_SPACING_MS;
        array<eAIBase> actors = HCXExpansionBridge.HCBaseGetAll();
        if (!actors || actors.Count() == 0) { return; }
        bool loud = !weapon.IsKindOf("Archery_Base");
        ItemBase suppressor = weapon.GetAttachedSuppressor();
        if (suppressor && !suppressor.IsDamageDestroyed()) { loud = false; }
        vector aim = shooter.Expansion_GetAimDirection();
        if (aim.Length() < 0.5) { aim = shooter.GetDirection(); }
        aim = aim.Normalized();
        vector shooterPos = shooter.GetPosition();
        vector eye = shooterPos + Vector(0, 1.6, 0);
        // The pass-by ray ends at the first fire-geometry hit (one raycast).
        float passEnd = HCXDefencePolicy.PassEnd(RayDistance(eye, eye + aim * HCXDefencePolicy.PASS_REACH, shooter, null));
        int infectedShooter = -1;
        int candidates = 0;
        int rays = 0;
        map<int, bool> provoked = new map<int, bool>();
        s_Budget.HCReset(24, 2);
        for (int actorIndex = 0; actorIndex < actors.Count(); actorIndex++)
        {
            if (!s_Budget.HCContinue() || candidates >= 3) { break; }
            eAIBase actor = actors.Get(actorIndex);
            if (!actor || !HCXExpansionBridge.HCBaseIsAlive(actor) || HCXExpansionBridge.HCBaseIsUnconscious(actor) || !HCXStance.Owns(actor)) { continue; }
            eAIGroup group = HCXExpansionBridge.HCDayZPlayerImplementGetGroup(actor);
            if (!group || group == HCXExpansionBridge.HCDayZPlayerImplementGetGroup(shooter) || provoked.Contains(HCXExpansionBridge.HCGroupGetID(group))) { continue; }
            vector chest = HCXExpansionBridge.HCBaseGetPosition(actor) + Vector(0, 1.1, 0);
            vector toActor = chest - eye;
            float shooterDistance = toActor.Length();
            if (shooterDistance > 250) { continue; }
            float along = vector.Dot(toActor, aim);
            float perp = (toActor - aim * along).Length();
            int nearKind = HCXDefencePolicy.Classify(along, perp, shooterDistance, loud, passEnd);
            if (nearKind == HCXDefencePolicy.NEAR_NONE) { continue; }
            // A wall between the ray and the actor ends the near miss.
            if (nearKind == HCXDefencePolicy.NEAR_PASS)
            {
                if (rays >= HCXDefencePolicy.RAYCASTS_PER_SHOT - 1) { continue; }
                rays++;
                if (Blocked(eye + aim * along, chest, shooter, actor)) { continue; }
            }
            candidates++;
            if (nowMs < gate.ExcusedUntil) { s_Excused++; break; }
            if (infectedShooter < 0) { infectedShooter = InfectedNear(shooterPos, nowMs); }
            int infectedActor = 0;
            if (infectedShooter == 0) { infectedActor = InfectedNear(HCXExpansionBridge.HCBaseGetPosition(actor), nowMs); }
            if (HCXDefencePolicy.Excused(infectedShooter, infectedActor))
            {
                NoteExcuse(gate, nowMs);
                break;
            }
            provoked.Set(HCXExpansionBridge.HCGroupGetID(group), true);
            Provoke(actor, shooter, nowMs, shooterPos);
        }
    }

    // Native bullet-impact noise (eAIBase.eAI_OnNoiseEvent, BULLETIMPACT): a bullet
    // that landed within 4 m of this actor is a near miss unless infected are near.
    static void OnImpact(eAIBase actor, EntityAI source, vector position)
    {
        if (!s_Running || !actor || position == vector.Zero) { return; }
        if (vector.Distance(HCXExpansionBridge.HCBaseGetPosition(actor) + Vector(0, 1.0, 0), position) > HCXDefencePolicy.PASS_RADIUS) { return; }
        if (!HCXExpansionBridge.HCBaseIsAlive(actor) || HCXExpansionBridge.HCBaseIsUnconscious(actor) || !HCXStance.Owns(actor)) { return; }
        PlayerBase shooter = AttackerOf(source);
        if (!shooter || HCXExpansionBridge.HCDayZPlayerImplementGetGroup(actor) == HCXExpansionBridge.HCDayZPlayerImplementGetGroup(shooter)) { return; }
        int nowMs = GetGame().GetTime();
        HCXShotGate gate = Gate(shooter);
        if (!gate) { s_Refused++; return; }
        if (nowMs < gate.ExcusedUntil) { s_Excused++; return; }
        if (!WindowAllows(nowMs, gate.NextImpact)) { return; }
        gate.NextImpact = nowMs + HCXDefencePolicy.SHOT_SPACING_MS;
        int infectedShooter = InfectedNear(shooter.GetPosition(), nowMs);
        int infectedActor = 0;
        if (infectedShooter == 0) { infectedActor = InfectedNear(HCXExpansionBridge.HCBaseGetPosition(actor), nowMs); }
        if (HCXDefencePolicy.Excused(infectedShooter, infectedActor))
        {
            NoteExcuse(gate, nowMs);
            return;
        }
        Provoke(actor, shooter, nowMs, position);
    }

    // Maintenance: at most 8 grudges per tick, expired or orphaned ones removed.
    static void Tick()
    {
        if (!s_Running) { return; }
        int nowMs = GetGame().GetTime();
        s_Budget.HCReset(8);
        int deferred = 0;
        for (int pass = 0; pass < s_Grudges.Count() && pass < HCXDefencePolicy.GRUDGE_CAP; pass++)
        {
            if (s_Cursor >= s_Grudges.Count()) { s_Cursor = 0; }
            if (!s_Budget.HCContinue())
            {
                deferred = s_Grudges.Count() - pass;
                break;
            }
            HCXGrudge grudge = s_Grudges.Get(s_Cursor);
            HCReached.Mark("ai_defence.grudge");
            if (!grudge || nowMs >= grudge.Until || !HCXExpansionBridge.HCGroupById(grudge.GroupId) || !grudge.Attacker || !grudge.Attacker.IsAlive())
            {
                s_Grudges.RemoveOrdered(s_Cursor);
                s_Expired++;
            }
            else
            {
                s_Cursor++;
            }
        }
        s_Budget.HCDeferred("HCXDefence", deferred);
        float tickNow = GetGame().GetTickTime();
        int signature = s_Hits + s_Kills + s_NearMisses + s_Excused + s_RescueHits + s_Refused + s_Evicted + s_Expired + s_Applied;
        if (tickNow >= s_SummaryAfter && signature != s_Logged)
        {
            s_SummaryAfter = tickNow + 60;
            s_Logged = signature;
            Print("[HCX Defence] grudges=" + s_Grudges.Count().ToString() + "/" + HCXDefencePolicy.GRUDGE_CAP.ToString() + " hits=" + s_Hits.ToString() + " kills=" + s_Kills.ToString() + " near_misses=" + s_NearMisses.ToString() + " excused_infected=" + s_Excused.ToString() + " excused_rescue_hit=" + s_RescueHits.ToString() + " refused=" + s_Refused.ToString() + " evicted=" + s_Evicted.ToString() + " expired=" + s_Expired.ToString() + " applied=" + s_Applied.ToString());
        }
    }
}

class HCXDefenceModule : HCModule
{
    protected ref HCOperationalStatus m_Operational = new HCOperationalStatus;

    override string GetName() { return "AISelfDefence"; }

    // Wave 16: started = the grudge service is running (HCXDefence.Running), never hard-coded.
    override HCOperationalStatus HCGetOperationalStatus()
    {
        HCModuleReadiness.HCDerive(m_Operational, HCXDefence.Running(), "", "", "defence_grudge_service_running");
        return m_Operational;
    }
    override bool IsEnabled(HCSettings settings) { return settings && settings.EnableEncounters; }
    override void OnStart(HCSettings settings)
    {
        if (!GetGame().IsServer() || !IsEnabled(settings)) { return; }
        if (HCXDefence.Running())
        {
            Print("[HCX Defence] start ignored: already running");
            return;
        }
        HCXDefence.Start();
        Print(HCV2Admission.Line("AISelfDefence", true, "W7-AIDEF", false));
        Print("[HCX Defence] started grudges<=64 expiry hit=240s kill=300s miss=90s rescue_excuse=30s near_miss=4m/12m infected_excuse=25m runtime=PENDING");
    }
    override void OnTick(float deltaTime) { HCXDefence.Tick(); }
    override void OnStop() { HCXDefence.Stop(); }
}



modded class Weapon_Base
{
    override void EEFired(int muzzleType, int mode, string ammoType)
    {
        super.EEFired(muzzleType, mode, ammoType);
        if (GetGame() && GetGame().IsServer()) { HCXDefence.OnShot(this); }
    }
}

modded class ZombieBase
{
    override void EEKilled(Object killer)
    {
        super.EEKilled(killer);
        if (GetGame() && GetGame().IsServer()) { HCXDefence.NoteInfectedDeath(GetPosition()); }
    }
}

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        Register(new HCXDefenceModule());
    }
}
// Expansion AI hook implementations live in HCXExpansionBridge.c.
