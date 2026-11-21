// Native 1.30.164289 evidence (source availability, runtime still pending):
// DayZAnimal.c:193/664 GetAIAgent/GetInputController, :175/722 command hook;
// AI/AIAgent.c:7 GetGroup; AIGroup.c:14 only GetBehaviour (no animal goal);
// AIGroupBehaviour.c:27 SetWaypoints applies ONLY to infected packs.
// DayZCreatureAIInputController.c:3/9/27 speed/heading/behaviour slot;
// DayZAnimalInputController.c:2-45 native calm/graze/drink/walk enums, :54
// OverrideBehaviourAction. We lease native locomotion inputs, never positions.
// AIWorld.c:98/110/122 path, raycast and sample; Global/World.c:28/116 date/AI;
// Game.c:1176/1180/1196/1197 surface height/type/sea/pond, :449/578/594/611
// config Names reads. EnConvert.c:153/210/353 Normalize/DistanceSq/angles.
// CentralEconomy.c:227-746 has no runtime territory-weight setter: CE respawn
// weighting is untouched. Infected drift below reuses the existing pack owner.
class HCEcologyHerdHome
{
    AIGroup Group;
    vector Anchor;
    vector Food;
    vector Water;
    bool HasFood;
    bool HasWater;
    int Survey;
    int Phase = -1;
    int LastSeen;
}

class HCEcologyCycle
{
    protected static ref HCEcologyCycle s_Active;
    protected ref HCEcologyCycleSettings m_Settings;
    protected ref HCEcologyCycleState m_State;
    protected ref HCEcologyCycleSaveJob m_Save;
    protected ref array<ref HCEcologyHerdHome> m_Herds = new array<ref HCEcologyHerdHome>;
    protected ref array<AnimalBase> m_Movers = new array<AnimalBase>;
    protected ref array<vector> m_Towns = new array<vector>;
    protected ref PGFilter m_Filter = new PGFilter;
    protected ref HCWorkBudget m_Work = new HCWorkBudget;
    protected int m_ActorCursor;
    protected int m_NameCursor;
    protected int m_NameCount;
    protected int m_ReportUtc;
    protected int m_LastUtc;
    protected int m_TownPhase;
    protected int m_InfectedRequests;
    protected int m_InfectedAccepted;
    protected int m_PathTick = -1;
    protected string m_Names;
    protected bool m_Fault;

    bool Open()
    {
        m_Settings = HCEcologyCycleStore.Settings();
        if (!m_Settings) { return false; }
        if (!m_Settings.Enabled) { return true; }
        int utc = HCGroupClock.Utc();
        m_Save = new HCEcologyCycleSaveJob;
        string world = HCBuildIdentity.CanonicalWorld(GetGame().GetWorldName());
        m_State = HCEcologyCycleStore.Open(m_Save, world, utc);
        if (!m_State) { return false; }
        HCSaveScheduler.HCRegister(m_Save);
        // Startup barrier: readiness must follow verified cadence promotion.
        HCSaveScheduler.HCFlush(m_Save);
        if (!m_Save.Committed || m_Save.Failed) { m_Fault = true; return false; }
        m_LastUtc = utc;
        m_Names = "CfgWorlds " + GetGame().GetWorldName() + " Names";
        m_NameCount = Math.Min(GetGame().ConfigGetChildrenCount(m_Names), 512);
        m_Filter.SetFlags(PGPolyFlags.WALK, PGPolyFlags.DISABLED | PGPolyFlags.UNREACHABLE | PGPolyFlags.SWIM | PGPolyFlags.SWIM_SEA | PGPolyFlags.DOOR | PGPolyFlags.INSIDE | PGPolyFlags.SPECIAL, PGPolyFlags.NONE);
        s_Active = this;
        Print("[HC Ecology] cycle=started animals=" + m_Settings.Animals.ToString() + " infected=" + m_Settings.Infected.ToString() + " native_inputs=leased ce_weights=unchanged runtime=PENDING");
        return true;
    }

    bool Healthy() { return !m_Fault && m_Settings && (!m_Settings.Enabled || (m_State && m_Save && !m_Save.Failed)); }
    bool NeedsMigration() { return m_Settings && m_Settings.Enabled && m_Settings.Infected && HCEcologyMigrationQualification.Admitted(); }
    static HCEcologyCycle Active() { return s_Active; }
    bool Ready() { return Healthy() && m_State && m_Save && m_Save.Committed; }

    void Close()
    {
        foreach (AnimalBase animal : m_Movers) { if (animal) { animal.HCEcologyRelease(); } }
        m_Movers.Clear();
        if (m_Save)
        {
            HCSaveScheduler.HCFlush(m_Save);
            HCSaveScheduler.HCUnregister(m_Save);
        }
        if (s_Active == this) { s_Active = null; }
    }

    // One path maximum across animal and infected callers in each core tick.
    // Use the shared pool directly: the assigned Ecology scope cannot add a
    // consumer ID to core. A refused request resumes on a later core tick.
    bool TakePath()
    {
        int now = GetGame().GetTime();
        if (m_PathTick == now) { return false; }
        if (!HCServer.HCTickWork().HCTake(1)) { return false; }
        // One admitted native query consumes the remainder of this local slice.
        // Charge its fixed conservative cost after shared admission so a
        // 256-unit operation can run in the 32-unit pool. No forced slot used.
        HCServer.HCTickWork().HCCharge(255);
        m_PathTick = now;
        return true;
    }

    void Tick()
    {
        if (!m_Settings || !m_Settings.Enabled || !Healthy()) { return; }
        HCSaveScheduler.HCPumpFallback(m_Save);
        if (!Ready()) { return; }
        int utc = HCGroupClock.Utc();
        if (utc < m_LastUtc) { m_Fault = true; Close(); return; }
        m_LastUtc = utc;
        m_TownPhase = (utc - m_State.EpochUtc) / (m_Settings.TownShiftDays * 86400);
        // Names are inspected incrementally, one source row per tick. Only
        // settlement types qualify, never arbitrary hills or player positions.
        if (m_NameCursor < m_NameCount && HCServer.HCTickWork().HCTake(1)) { ReadTown(); }
        int index = m_Movers.Count() - 1;
        while (index >= 0)
        {
            AnimalBase mover = m_Movers[index];
            if (!mover || !mover.HCEcologyLeased()) { m_Movers.RemoveOrdered(index); }
            index--;
        }
        m_Work.HCReset(HCPerfConfig.HCGet().EcologyRowsPerTick, HCPerfConfig.HCGet().SliceMs);
        int rows = 0;
        while (m_Settings.Animals && rows < HCPerfConfig.HCGet().EcologyRowsPerTick && m_Work.HCContinue())
        {
            if (!HCServer.HCTickWork().HCTake(1)) { break; }
            AnimalBase animal = HCEcologyRuntime.HCCycleAnimal(m_ActorCursor);
            rows++;
            if (!animal) { break; }
            Visit(animal, utc);
        }
        if (utc >= m_ReportUtc)
        {
            int drinking = 0;
            int grazing = 0;
            foreach (AnimalBase active : m_Movers)
            {
                if (!active) { continue; }
                if (active.HCEcologyAction() == DayZAnimalBehaviourAction.DRINKING_INPUT) { drinking++; }
                if (active.HCEcologyAction() == DayZAnimalBehaviourAction.GRAZE_ON_SPOT_INPUT) { grazing++; }
            }
            Print("[HC Ecology] herds=" + m_Herds.Count().ToString() + " moving=" + (m_Movers.Count() - drinking - grazing).ToString() + " drinking=" + drinking.ToString() + " grazing=" + grazing.ToString() + " infected_town_shift=" + m_TownPhase.ToString() + " towns=" + m_Towns.Count().ToString() + " infected_requests=" + m_InfectedRequests.ToString() + " infected_accepted=" + m_InfectedAccepted.ToString() + " counts=leases runtime=PENDING");
            m_ReportUtc = utc + m_Settings.SummarySeconds;
        }
    }

    protected void ReadTown()
    {
        string child;
        int index = m_NameCursor;
        m_NameCursor++;
        if (!GetGame().ConfigGetChildName(m_Names, index, child)) { return; }
        string path = m_Names + " " + child;
        string type;
        GetGame().ConfigGetText(path + " type", type);
        if (type != "NameCityCapital" && type != "NameCity" && type != "NameVillage") { return; }
        array<float> xy = new array<float>;
        GetGame().ConfigGetFloatArray(path + " position", xy);
        if (m_Towns.Count() >= 64 || xy.Count() != 2) { return; }
        vector point = Vector(xy[0], 0, xy[1]);
        if (!InWorld(point)) { return; }
        point[1] = GetGame().SurfaceY(point[0], point[2]);
        m_Towns.Insert(point);
    }

    protected bool InWorld(vector point)
    {
        int size = GetGame().GetWorld().GetWorldSize();
        return HCEcologyRuntimeRules.PositionValid(point) && point[0] > 0 && point[2] > 0 && point[0] < size && point[2] < size;
    }

    protected HCEcologyHerdHome Home(AnimalBase animal, int utc)
    {
        if (!animal.GetAIAgent()) { return null; }
        AIGroup group = animal.GetAIAgent().GetGroup();
        if (!group) { return null; }
        foreach (HCEcologyHerdHome home : m_Herds)
        {
            if (home.Group == group) { home.LastSeen = utc; return home; }
        }
        // Retire unseen identities, never move old bodies or restore handles.
        for (int i = m_Herds.Count() - 1; i >= 0; i--)
        {
            if (utc - m_Herds[i].LastSeen > 3600) { m_Herds.RemoveOrdered(i); }
        }
        if (m_Herds.Count() >= m_Settings.MaxHerds) { return null; }
        HCEcologyHerdHome fresh = new HCEcologyHerdHome;
        fresh.Group = group;
        fresh.Anchor = animal.GetPosition();
        fresh.LastSeen = utc;
        m_Herds.Insert(fresh);
        return fresh;
    }

    protected void Survey(HCEcologyHerdHome home, int utc)
    {
        int phase = (utc - m_State.EpochUtc) / (m_Settings.HerdDriftHours * 3600);
        if (home.Phase != phase)
        {
            home.Phase = phase;
            home.HasFood = false;
            home.HasWater = false;
            home.Survey = 0;
        }
        // A slow continuous home bias (240 m orbit over four drift intervals),
        // not a sudden destination jump. Four terrain samples per visited row.
        float angle = ((float)(utc - m_State.EpochUtc) / (m_Settings.HerdDriftHours * 3600)) * Math.PI * 0.5;
        vector center = home.Anchor + Vector(Math.Sin(angle) * 240, 0, (Math.Cos(angle) - 1) * 240);
        for (int i = 0; i < 4; i++)
        {
            int sample = home.Survey % 256;
            home.Survey++;
            // Integer steps first: Enforce refuses '%' inside a float expression.
            int column = sample % 16;
            int ring = sample / 16;
            float bearing = column * Math.PI / 8;
            float radius = 16 + ring * 16;
            vector point = center + Vector(Math.Sin(bearing) * radius, 0, Math.Cos(bearing) * radius);
            if (!InWorld(point) || GetGame().SurfaceIsSea(point[0], point[2]) || GetGame().SurfaceIsPond(point[0], point[2])) { continue; }
            point[1] = GetGame().SurfaceY(point[0], point[2]);
            // A land point next to classified inland water is a shore candidate;
            // native navmesh still has to admit its actual approach.
            bool shore = GetGame().SurfaceIsPond(point[0] + 2, point[2]) || GetGame().SurfaceIsPond(point[0] - 2, point[2]) || GetGame().SurfaceIsPond(point[0], point[2] + 2) || GetGame().SurfaceIsPond(point[0], point[2] - 2);
            if (shore && !home.HasWater) { home.Water = point; home.HasWater = true; }
            string surface;
            GetGame().SurfaceGetType(point[0], point[2], surface);
            bool field = FieldSurface(surface);
            if (!field && ForestSurface(surface))
            {
                string edge;
                GetGame().SurfaceGetType(point[0] + 12, point[2], edge);
                field = FieldSurface(edge);
                if (!field)
                {
                    GetGame().SurfaceGetType(point[0], point[2] + 12, edge);
                    field = FieldSurface(edge);
                }
            }
            if (field && !home.HasFood) { home.Food = point; home.HasFood = true; }
        }
    }

    protected bool FieldSurface(string surface)
    {
        if (surface.Length() > 128) { return false; }
        surface.ToLower();
        return surface.IndexOf("grass") >= 0;
    }

    protected bool ForestSurface(string surface)
    {
        if (surface.Length() > 128) { return false; }
        surface.ToLower();
        return surface.IndexOf("cp_conifer_") == 0 || surface.IndexOf("cp_broadleaf_") == 0;
    }

    protected void Visit(AnimalBase animal, int utc)
    {
        // Herbivore herds only: no wolves, bears, pets or ambient birds/rodents.
        string species = animal.GetType();
        bool herbivore = species.IndexOf("Animal_Cervus") == 0 || species.IndexOf("Animal_Capreolus") == 0 || species.IndexOf("Animal_Bos") == 0 || species.IndexOf("Animal_Ovis") == 0 || species.IndexOf("Animal_Capra") == 0 || species.IndexOf("Animal_Sus") == 0;
        if (!herbivore || !animal.IsAlive() || !animal.HCEcologyCalm()) { return; }
        HCEcologyHerdHome home = Home(animal, utc);
        if (!home) { return; }
        Survey(home, utc);
        int year; int month; int day; int hour; int minute;
        GetGame().GetWorld().GetDate(year, month, day, hour, minute);
        bool water = (hour >= 5 && hour < 8) || (hour >= 17 && hour < 20);
        if ((water && !home.HasWater) || (!water && !home.HasFood)) { return; }
        if (!animal.HCEcologyLeased() && m_Movers.Count() >= m_Settings.MaxMovers) { return; }
        vector goal = home.Food;
        int action = DayZAnimalBehaviourAction.GRAZE_ON_SPOT_INPUT;
        if (water) { goal = home.Water; action = DayZAnimalBehaviourAction.DRINKING_INPUT; }
        vector from = animal.GetPosition();
        float arrivalSq = 9;
        if (water) { arrivalSq = 2.25; }
        if (vector.DistanceSq(from, goal) <= arrivalSq)
        {
            Lease(animal, goal, action, 20);
            return;
        }
        if (!TakePath()) { return; }
        vector direction = goal - from;
        direction[1] = 0;
        if (direction.Length() > 80) { direction.Normalize(); goal = from + direction * 80; }
        goal[1] = GetGame().SurfaceY(goal[0], goal[2]);
        AIWorld world = GetGame().GetWorld().GetAIWorld();
        vector sampled;
        if (!world || !world.SampleNavmeshPosition(goal, 3, m_Filter, sampled)) { return; }
        TVectorArray path = new TVectorArray;
        if (!world.FindPath(from, sampled, m_Filter, path) || path.Count() < 2 || path.Count() > 32) { return; }
        vector next = path[1];
        if (vector.DistanceSq(next, from) < 0.25 && path.Count() > 2) { next = path[2]; }
        vector delta = next - from;
        if (delta.Length() < 0.5) { return; }
        // The lease cannot outlive this short straight navmesh segment.
        delta.Normalize();
        vector step = from + delta * Math.Min(4, vector.Distance(from, next));
        vector hit; vector normal;
        if (world.RaycastNavMesh(from, step, m_Filter, hit, normal)) { return; }
        Lease(animal, step, DayZAnimalBehaviourAction.WALKING_INPUT, 1.25);
    }

    protected void Lease(AnimalBase animal, vector goal, int action, float seconds)
    {
        if (!animal.HCEcologyLeased() && m_Movers.Find(animal) < 0) { m_Movers.Insert(animal); }
        animal.HCEcologyLease(goal, action, GetGame().GetTickTime() + seconds);
    }

    // Environmental route goal, deliberately separate from sensory clues.
    // The same town phase survives restart. Pressure towns rotate over days;
    // one existing cohort takes at most one 80 m native step per 10 minutes.
    bool InfectedGoal(vector from, out vector goal)
    {
        if (!Ready() || !m_Settings.Infected || m_NameCursor < m_NameCount || m_Towns.Count() < 2) { return false; }
        // All cohorts share the same environmental pressure town for two UTC
        // days. Wait until the bounded catalog scan finishes so its changing
        // count cannot change a target during initial collection.
        int target = m_TownPhase % m_Towns.Count();
        vector delta = m_Towns[target] - from;
        delta[1] = 0;
        if (delta.Length() < 16) { return false; }
        delta.Normalize();
        goal = from + delta * 80;
        goal[1] = GetGame().SurfaceY(goal[0], goal[2]);
        return InWorld(goal);
    }
    int InfectedInterval() { return m_Settings.InfectedStepSeconds; }
    void InfectedRequested(int result)
    {
        if (m_InfectedRequests < 1000000000) { m_InfectedRequests++; }
        if (result == 2 && m_InfectedAccepted < 1000000000) { m_InfectedAccepted++; }
    }
}
