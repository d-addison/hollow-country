// LC-T107 / EXP-A5; native scripts-1.30.164289 evidence (relative to dump):
// 3_Game/Global/Game.c:930 GetObjectsAtPosition3D, :944 GetPlayer, :1125
// IsDedicatedServer; Entities/Object.c:287 GetPosition, :517 IsAlive;
// Entities/EntityAI.c:885 GetHierarchyParent; shared scalar/container native
// APIs are cited in HCSignsOfLife.c.
// 4_World/Entities/ScriptedLightBase/PointLightBase.c:1 PointLightBase;
// ScriptedLightBase.c:227 CreateLight (CLIENT ONLY), :258 SetBrightnessTo,
// :303 SetRadiusTo, :326 Destroy; PointLightBase/FireplaceLight.c:8-16 verifies
// daylight, shadow, flare and colour setters. Native room/chimney anchors and
// other shared APIs are cited in 4_World/Atmosphere/HCSignsOfLife.c.
// 3_Game/Particles/ParticleList.c:43 HOUSE_SMALL_SMOKE, :305 ENV_SWARMING_FLIES;
// Particles/Particle.c:174 PlayInWorld, :266 Stop;
// Effects/EffectParticle/SwarmingFlies.c:1-5 EffSwarmingFlies uses that particle;
// EffectManager.c:70 PlayOnObject, :256 PlaySoundOnObject, :280 DestroyEffect;
// 4_World/Entities/ManBase/PlayerBase.c:9657-9667 vanilla flies particle and
// "Flies_SoundSet" loop. Edible_Base.c:587 IsFoodRotten (under Entities/ItemBase).
// Creatures/{Animals/AnimalBase,Infected/ZombieBase}.c define corpse classes.
// 5_Mission/mission/missionGameplay.c:102/287/266 OnInit/OnUpdate/OnMissionFinish.
// Default-on, client-local preference by task contract: no server settings/RPC.
// Caps count HC-owned sources; vanilla corpse effects remain engine-owned.
// Geometry, perceptibility, engine cleanup and two-client acceptance pending.
class HCSignsOfLifeEffect
{
    Object Source;
    ScriptedLightBase Lamp;
    Particle Smoke;
    ref EffSwarmingFlies Flies;
    ref EffectSound Buzz;

    void Stop()
    {
        if (Lamp) Lamp.Destroy();
        if (Smoke) Smoke.Stop();
        if (Flies) SEffectManager.DestroyEffect(Flies);
        if (Buzz) SEffectManager.DestroyEffect(Buzz);
        Lamp = null;
        Smoke = null;
        Flies = null;
        Buzz = null;
        Source = null;
    }
}

class HCSignsOfLifeClient
{
    protected ref array<ref HCSignsOfLifeEffect> m_Lit = new array<ref HCSignsOfLifeEffect>;
    protected ref array<ref HCSignsOfLifeEffect> m_Smoke = new array<ref HCSignsOfLifeEffect>;
    protected ref array<ref HCSignsOfLifeEffect> m_Flies = new array<ref HCSignsOfLifeEffect>;
    protected float m_ScanClock = 10.0;
    protected float m_CleanClock;
    protected float m_LogClock = 10.0;
    protected int m_LastLit = -1;
    protected int m_LastSmoke = -1;
    protected int m_LastFlies = -1;

    static bool FlySource(Object source)
    {
        if (!source) return false;
        Edible_Base food = Edible_Base.Cast(source);
        // Exposed food only; never buzz through closed inventory containers.
        if (food) return !food.GetHierarchyParent() && food.IsFoodRotten();
        // Review P2: vanilla already plays flies on dead PlayerBase (PlayerBase.c:9651-9669).
        if (ZombieBase.Cast(source) || AnimalBase.Cast(source)) return !source.IsAlive();
        return false;
    }

    void Update(float timeslice)
    {
        if (!GetGame() || GetGame().IsDedicatedServer()) return;
        m_ScanClock += timeslice;
        m_CleanClock += timeslice;
        m_LogClock += timeslice;
        PlayerBase viewer = PlayerBase.Cast(GetGame().GetPlayer());
        if (!viewer || !viewer.IsAlive())
        {
            Clear();
            Report();
            return;
        }
        // Twelve handles at most: remove stream-outs/range exits within 1 s,
        // including during the gap between the bounded native scans.
        if (m_CleanClock >= 1.0)
        {
            m_CleanClock = 0;
            Prune(m_Lit, viewer.GetPosition(), HCSignsOfLife.HOUSE_RADIUS, false);
            Prune(m_Smoke, viewer.GetPosition(), HCSignsOfLife.HOUSE_RADIUS, false);
            Prune(m_Flies, viewer.GetPosition(), HCSignsOfLife.FLY_RADIUS, true);
        }
        if (m_ScanClock >= HCSignsOfLife.SCAN_SECONDS)
        {
            m_ScanClock = 0;
            Scan(viewer);
        }
        Report();
    }

    protected void Scan(PlayerBase viewer)
    {
        int day = HCSignsOfLife.RealDay();
        if (day < 0) { Clear(); return; }
        ref array<Object> lit = new array<Object>;
        ref array<Object> smoke = new array<Object>;
        ref array<Object> flies = new array<Object>;
        HCSignsOfLife.SelectHouses(viewer, day, lit, smoke);
        ref array<Object> objects = new array<Object>;
        ref array<CargoBase> proxies = new array<CargoBase>;
        vector center = viewer.GetPosition();
        GetGame().GetObjectsAtPosition3D(center, HCSignsOfLife.FLY_RADIUS, objects, proxies);
        int count = Math.Min(objects.Count(), HCSignsOfLife.MAX_OBJECTS);
        for (int i = 0; i < count; i++)
        {
            Object candidate = objects[i];
            if (!FlySource(candidate)) continue;
            if (vector.DistanceSq(candidate.GetPosition(), center) > HCSignsOfLife.FLY_RADIUS * HCSignsOfLife.FLY_RADIUS) continue;
            HCSignsOfLife.Offer(flies, candidate, day, HCSignsOfLife.MAX_FLIES);
        }
        Reconcile(m_Lit, lit, 0, HCSignsOfLife.MAX_LIT);
        Reconcile(m_Smoke, smoke, 1, HCSignsOfLife.MAX_SMOKE);
        Reconcile(m_Flies, flies, 2, HCSignsOfLife.MAX_FLIES);
    }

    protected void Prune(array<ref HCSignsOfLifeEffect> handles, vector center, float radius, bool checkFood)
    {
        int index = handles.Count() - 1;
        while (index >= 0)
        {
            HCSignsOfLifeEffect active = handles[index];
            bool keep = false;
            if (active.Source)
            {
                keep = vector.DistanceSq(active.Source.GetPosition(), center) <= radius * radius;
                if (checkFood && !FlySource(active.Source)) keep = false;
            }
            if (!keep)
            {
                active.Stop();
                handles.RemoveOrdered(index);
            }
            index--;
        }
    }

    protected bool HasSource(array<ref HCSignsOfLifeEffect> handles, Object source)
    {
        foreach (HCSignsOfLifeEffect handle : handles)
        {
            if (handle.Source == source) return true;
        }
        return false;
    }

    protected void Reconcile(array<ref HCSignsOfLifeEffect> handles, array<Object> wanted, int kind, int cap)
    {
        // Remove first so day/time/temperature transitions cannot exceed caps.
        int oldIndex = handles.Count() - 1;
        while (oldIndex >= 0)
        {
            HCSignsOfLifeEffect previous = handles[oldIndex];
            if (!previous.Source || wanted.Find(previous.Source) < 0)
            {
                previous.Stop();
                handles.RemoveOrdered(oldIndex);
            }
            oldIndex--;
        }
        foreach (Object source : wanted)
        {
            if (!HCSignsOfLife.CanAdd(handles.Count(), cap)) break;
            if (!source || HasSource(handles, source)) continue;
            HCSignsOfLifeEffect created = new HCSignsOfLifeEffect;
            created.Source = source;
            if (kind == 0 || kind == 1)
            {
                vector lamp, chimney;
                if (!HCSignsOfLife.HousePoints(source, lamp, chimney)) continue;
                if (kind == 0) created.Lamp = ScriptedLightBase.CreateLight(HCSignsWindowLight, lamp);
                if (kind == 1) created.Smoke = Particle.PlayInWorld(ParticleList.HOUSE_SMALL_SMOKE, chimney);
                if (!created.Lamp && !created.Smoke) continue;
            }
            else
            {
                created.Flies = new EffSwarmingFlies;
                SEffectManager.PlayOnObject(created.Flies, source, "0 0.25 0");
                // No fade-out tail: replacing a source must not overlap old buzz
                // loops with the six newly admitted ones (EffectSound.c:640).
                created.Buzz = SEffectManager.PlaySoundOnObject("Flies_SoundSet", source, 1.0, 0.0, true);
            }
            handles.Insert(created);
        }
    }

    protected void ClearHandles(array<ref HCSignsOfLifeEffect> handles)
    {
        foreach (HCSignsOfLifeEffect active : handles) active.Stop();
        handles.Clear();
    }

    void Clear()
    {
        ClearHandles(m_Lit);
        ClearHandles(m_Smoke);
        ClearHandles(m_Flies);
    }

    protected void Report()
    {
        // At most one changed-count line per scan interval, plus finish cleanup.
        if (m_LogClock < HCSignsOfLife.SCAN_SECONDS) return;
        int lit = m_Lit.Count();
        int smoke = m_Smoke.Count();
        int flies = m_Flies.Count();
        if (lit == m_LastLit && smoke == m_LastSmoke && flies == m_LastFlies) return;
        m_LogClock = 0;
        m_LastLit = lit;
        m_LastSmoke = smoke;
        m_LastFlies = flies;
        Print("[HollowCountry] V2 client signs of life lit=" + lit.ToString() + " smoke=" + smoke.ToString() + " flies=" + flies.ToString());
    }

    void Stop()
    {
        Clear();
        HCSignsOfLife.ForceLit.Clear();
        m_LogClock = HCSignsOfLife.SCAN_SECONDS;
        Report();
    }
}

modded class MissionGameplay
{
    protected ref HCSignsOfLifeClient m_HCSignsOfLife;

    override void OnInit()
    {
        super.OnInit();
        if (!GetGame().IsDedicatedServer()) m_HCSignsOfLife = new HCSignsOfLifeClient;
    }

    override void OnUpdate(float timeslice)
    {
        super.OnUpdate(timeslice);
        if (m_HCSignsOfLife) m_HCSignsOfLife.Update(timeslice);
    }

    override void OnMissionFinish()
    {
        if (m_HCSignsOfLife) m_HCSignsOfLife.Stop();
        m_HCSignsOfLife = null;
        super.OnMissionFinish();
    }
}
