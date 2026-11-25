// Dev-only cellar walk; no position writes, feature admission or counter writes.
// Native scripts-1.30.164289: 3_Game/Global/Game.c:930 GetObjectsAtPosition3D
// (one radius query/step), :1176 SurfaceY, :1535 GetTime; Entities/Object.c:287
// GetPosition, :370 GetCollisionBox (model bounds), :467 GetType, :873 ModelToWorld;
// Entities/Building.c:31 GetDoorCount, :34 IsDoorOpen, :73 GetDoorSoundPos (world);
// Entities/Man.c:37 IsSoundInsideBuilding; Global/DayZPhysics.c:199 RaycastRV,
// :130-143 first contact/normal, ignore parameters, ObjIntersectGeom;
// 1_Core/proto/EnConvert.c:169 Length, :210 DistanceSq; EnScript.c:394 Find,
// :418 InsertAt, :463 Remove, :902 map.Set, :917 map.Contains. Four downward rays/building,
// four buildings maximum, one ray/tick, 16 total. Existing route/actions retain
// native citations and use only the player's own input and vanilla door action.
modded class HCDriverStep
{
    ref array<string> classes_from;
}

// Restrict the existing door scanner to this building; no unrelated door opens.
class HCDriverCellarActions : HCDriverActions
{
    Building TargetBuilding;

    override protected bool Accept(string kind, PlayerBase player, Object object)
    {
        if (kind == "open_door" && object != TargetBuilding) { return false; }
        return super.Accept(kind, player, object);
    }
}

class HCDriverCellar
{
    protected static ref HCDriverCellar s_Instance;
    protected ref array<Object> m_Near = new array<Object>;
    protected ref array<CargoBase> m_Cargo = new array<CargoBase>;
    protected ref array<Building> m_Candidates = new array<Building>;
    protected ref map<string, bool> m_Classes = new map<string, bool>;
    protected ref set<Object> m_Hits = new set<Object>;
    protected ref HCWorkBudget m_Budget = new HCWorkBudget;
    protected ref HCDriverRoute m_Route = new HCDriverRoute;
    protected ref HCDriverCellarActions m_Doors = new HCDriverCellarActions;
    protected ref array<vector> m_Track = new array<vector>;
    protected Building m_Building;
    protected vector m_Origin;
    protected vector m_Outside;
    protected vector m_Inside;
    protected vector m_Floor;
    protected vector m_Min;
    protected vector m_Max;
    protected int m_Started;
    protected int m_Scan;
    protected int m_Pick;
    protected int m_Phase;
    protected int m_Ray;
    protected int m_Door;
    protected int m_LastInsideSample;
    protected float m_Depth;
    protected float m_Held;
    protected float m_ObservedDepth;
    protected bool m_HeldInside;
    protected bool m_FoundFloor;
    protected bool m_RouteBlocked;
    protected string m_Tried;

    void Begin(HCDriverStep step, PlayerBase player)
    {
        m_Candidates.Clear();
        m_Track.Clear();
        m_Origin = player.GetPosition();
        m_Started = GetGame().GetTime();
        m_Scan = 0;
        m_Pick = 0;
        m_Phase = 0;
        m_Held = 0;
        m_LastInsideSample = 0;
        m_HeldInside = false;
        m_FoundFloor = false;
        m_RouteBlocked = false;
        m_Tried = "";
        m_Classes.Clear();
        if (step.classes_from && step.classes_from.Count() <= 64)
        {
            for (int c = 0; c < step.classes_from.Count() && c < 64; c++) { m_Classes.Set(step.classes_from[c], true); }
        }
        // Native Game.c:930; client guard is on Run. Never re-query during this step.
        GetGame().GetObjectsAtPosition3D(m_Origin, Math.Clamp(step.range_m, 5, 150), m_Near, m_Cargo);
    }

    protected float Remaining(HCDriverStep step)
    {
        return Math.Max(1, step.timeout_s - (GetGame().GetTime() - m_Started) * 0.001);
    }

    protected int End(PlayerBase player, HCDriverWalker walker, bool success, out string detail)
    {
        m_Doors.Abort(player, walker);
        detail = "reason=no-cellar-floor";
        if (m_FoundFloor || m_HeldInside || m_RouteBlocked) { detail = "reason=cellar-route-blocked"; }
        if (success)
        {
            detail = "returned";
            Print("[HC Driver] cellar building=" + m_Building.GetType() + " pos=<" + HCDriverWalker.XZ(m_Building.GetPosition()) + "> depth_m=" + m_ObservedDepth.ToString() + " result=ok");
            return HCDriverResult.OK;
        }
        Print("[HC Driver] cellar result=refused " + detail + " tried=" + m_Tried);
        return HCDriverResult.REFUSED;
    }

    protected void RouteTo(HCDriverStep step, HCDriverWalker walker, PlayerBase player, vector target)
    {
        walker.Release(player);
        HCDriverStep route = new HCDriverStep;
        vector start = player.GetPosition();
        route.points = {start[0], start[2], target[0], target[2]};
        route.gait = "walk";
        route.arrive_m = 2;
        route.timeout_s = Math.Min(Remaining(step), 40);
        m_Route.Begin(route);
    }

    protected void ReturnRoute(HCDriverStep step, HCDriverWalker walker, PlayerBase player)
    {
        m_Doors.Abort(player, walker);
        HCDriverStep route = new HCDriverStep;
        route.points = new array<float>;
        vector current = player.GetPosition();
        route.points.Insert(current[0]);
        route.points.Insert(current[2]);
        for (int i = m_Track.Count() - 1; i >= 0 && i < 63; i--)
        {
            route.points.Insert(m_Track[i][0]);
            route.points.Insert(m_Track[i][2]);
        }
        route.gait = "walk";
        route.arrive_m = 2;
        route.timeout_s = Remaining(step);
        m_Route.Begin(route);
        m_Phase = 7;
    }

    protected bool Pick(HCDriverStep step, PlayerBase player, HCDriverWalker walker)
    {
        if (m_Pick >= m_Candidates.Count()) { return false; }
        m_Building = m_Candidates[m_Pick];
        m_Pick++;
        if (!m_Building) { m_Phase = 1; return true; }
        m_Doors.TargetBuilding = m_Building;
        if (m_Tried != "") { m_Tried += ";"; }
        m_Tried += m_Building.GetType() + "@<" + HCDriverWalker.XZ(m_Building.GetPosition()) + ">";
        m_Door = -1;
        float nearest = 1000000000;
        // Native Building.c:31,73. Bound door enumeration independently of object count.
        for (int d = 0; d < m_Building.GetDoorCount() && d < 32; d++)
        {
            float distance = vector.DistanceSq(player.GetPosition(), m_Building.GetDoorSoundPos(d));
            if (distance < nearest) { nearest = distance; m_Door = d; }
        }
        m_Ray = 0;
        m_Depth = 2;
        m_Held = 0;
        m_Track.Clear();
        if (m_Door < 0) { m_RouteBlocked = true; m_Phase = 1; return true; }
        vector door = m_Building.GetDoorSoundPos(m_Door);
        vector toward = m_Building.GetPosition() - door;
        toward[1] = 0;
        float length = toward.Length();
        if (length < 0.1) { m_RouteBlocked = true; m_Phase = 1; return true; }
        toward = toward / length;
        m_Outside = door - toward * 3;
        m_Inside = door + toward * 3;
        m_Track.Insert(m_Outside);
        RouteTo(step, walker, player, door);
        m_Phase = 2;
        return true;
    }

    protected void Probe(PlayerBase player)
    {
        // Two interior columns, two starting depths: the second ray starts below
        // the shallow ground floor. Only a real upward-facing building hit counts.
        float fraction = 0.35;
        if (m_Ray >= 2) { fraction = 0.65; }
        vector interiorPoint = m_Min + (m_Max - m_Min) * fraction;
        vector point = m_Building.ModelToWorld(interiorPoint);
        float terrain = GetGame().SurfaceY(point[0], point[2]);
        float offset = 0.05;
        if (m_Ray % 2 == 1) { offset = 2.05; }
        vector start = Vector(point[0], terrain - offset, point[2]);
        vector end = Vector(point[0], terrain - 12, point[2]);
        vector contact;
        vector normal;
        int component;
        m_Hits.Clear();
        m_Ray++;
        if (!DayZPhysics.RaycastRV(start, end, contact, normal, component, m_Hits, null, player, true, false, ObjIntersectGeom)) { return; }
        float depth = terrain - contact[1];
        if (m_Hits.Count() == 0 || m_Hits.Get(0) != m_Building || normal[1] < 0.5 || depth <= m_Depth) { return; }
        m_Depth = depth;
        m_Floor = contact;
        m_FoundFloor = true;
    }

    static int Run(HCDriverStep step, PlayerBase player, float dt, HCDriverWalker walker, bool begin, out string detail)
    {
        if (!s_Instance) { s_Instance = new HCDriverCellar; }
        return s_Instance.Tick(step, player, dt, walker, begin, detail);
    }

    int Tick(HCDriverStep step, PlayerBase player, float dt, HCDriverWalker walker, bool begin, out string detail)
    {
#ifdef SERVER
        detail = "client-only";
        return HCDriverResult.UNSUPPORTED;
#else
        if (begin) { Begin(step, player); }
        if ((GetGame().GetTime() - m_Started) * 0.001 >= step.timeout_s) { return End(player, walker, false, detail); }
        if (m_Phase > 1 && !m_Building) { m_RouteBlocked = true; return End(player, walker, false, detail); }
        if (m_Phase == 0)
        {
            if (!step.classes_from || step.classes_from.Count() < 1 || step.classes_from.Count() > 64) { return End(player, walker, false, detail); }
            m_Budget.HCReset(64);
            while (m_Scan < m_Near.Count() && m_Budget.HCContinue())
            {
                Building candidate = Building.Cast(m_Near[m_Scan]);
                m_Scan++;
                if (!candidate || !m_Classes.Contains(candidate.GetType())) { continue; }
                float distance = vector.DistanceSq(m_Origin, candidate.GetPosition());
                if (distance > step.range_m * step.range_m) { continue; }
                int at = 0;
                while (at < m_Candidates.Count() && at < 4 && vector.DistanceSq(m_Origin, m_Candidates[at].GetPosition()) <= distance) { at++; }
                if (at < 4) { m_Candidates.InsertAt(candidate, at); }
                if (m_Candidates.Count() > 4) { m_Candidates.Remove(4); }
            }
            if (m_Scan < m_Near.Count()) { return HCDriverResult.RUNNING; }
            m_Near.Clear();
            m_Cargo.Clear();
            m_Phase = 1;
        }
        if (m_Phase == 1)
        {
            if (!Pick(step, player, walker)) { return End(player, walker, false, detail); }
            return HCDriverResult.RUNNING;
        }
        if (m_Phase == 2 || m_Phase == 4 || m_Phase == 6 || m_Phase == 7)
        {
            int walked = m_Route.Tick(player, dt, walker, m_Doors);
            if (m_Phase == 6 && vector.DistanceSq(player.GetPosition(), m_Track[m_Track.Count() - 1]) >= 4)
            {
                if (m_Track.Count() >= 62) { m_RouteBlocked = true; ReturnRoute(step, walker, player); return HCDriverResult.RUNNING; }
                m_Track.Insert(player.GetPosition());
            }
            if (walked == HCDriverResult.RUNNING) { return walked; }
            if (walked != HCDriverResult.OK) { m_RouteBlocked = true; return End(player, walker, false, detail); }
            if (m_Phase == 7)
            {
                if (m_HeldInside) { return End(player, walker, !player.IsSoundInsideBuilding(), detail); }
                m_Phase = 1;
                return HCDriverResult.RUNNING;
            }
            if (m_Phase == 2)
            {
                // Record the actual approach side, rather than assuming the model centre
                // points inward for every door. The exit retraces this exact approach.
                m_Outside = player.GetPosition();
                m_Track.Clear();
                m_Track.Insert(m_Outside);
                m_Doors.BeginInReach("open_door", 6);
                m_Phase = 3;
                return HCDriverResult.RUNNING;
            }
            if (m_Phase == 4)
            {
                if (!player.IsSoundInsideBuilding()) { m_RouteBlocked = true; ReturnRoute(step, walker, player); return HCDriverResult.RUNNING; }
                vector bounds[2];
                if (!m_Building.GetCollisionBox(bounds)) { ReturnRoute(step, walker, player); return HCDriverResult.RUNNING; }
                m_Min = bounds[0];
                m_Max = bounds[1];
                m_Track.Insert(player.GetPosition());
                m_Phase = 5;
            }
            else if (m_Phase == 6) { m_Phase = 8; }
        }
        if (m_Phase == 3)
        {
            int opened = HCDriverResult.OK;
            if (!m_Building.IsDoorOpen(m_Door)) { opened = m_Doors.Tick(player, dt, walker); }
            if (opened == HCDriverResult.RUNNING) { return opened; }
            m_Doors.Abort(player, walker);
            if (opened != HCDriverResult.OK) { m_RouteBlocked = true; ReturnRoute(step, walker, player); return HCDriverResult.RUNNING; }
            RouteTo(step, walker, player, m_Inside);
            m_Phase = 4;
        }
        if (m_Phase == 5)
        {
            if (m_Ray < 4) { Probe(player); return HCDriverResult.RUNNING; }
            if (m_Depth <= 2) { ReturnRoute(step, walker, player); return HCDriverResult.RUNNING; }
            RouteTo(step, walker, player, m_Floor);
            m_Phase = 6;
        }
        if (m_Phase == 8)
        {
            walker.Release(player);
            int now = GetGame().GetTime();
            // A hold/availability pause must not join two disjoint below-floor holds.
            if (m_LastInsideSample == 0 || now - m_LastInsideSample > 500) { m_Held = 0; }
            m_LastInsideSample = now;
            vector pos = player.GetPosition();
            float depthNow = GetGame().SurfaceY(pos[0], pos[2]) - pos[1];
            // HCVisualActive is renderer-owned. Never substitute the heuristic for its receipt.
            if (depthNow > 2 && player.IsSoundInsideBuilding())
            {
                if (HCCellarsClient.HCVisualActive())
                {
                    m_Held += dt;
                    m_ObservedDepth = depthNow;
                    if (m_Held >= step.hold_s) { m_HeldInside = true; ReturnRoute(step, walker, player); }
                }
                else { m_Held = 0; }
            }
            else { m_Held = 0; ReturnRoute(step, walker, player); }
        }
        return HCDriverResult.RUNNING;
#endif
    }
}
