// Dev-only test addon (never shipped). Radius entry for the scripted client driver: the R3
// ai=site_radius_entered and event=mission_radius_entered walks, on foot, never a teleport.
// The server counts an entry only when HCReleaseRadius saw this character outside and, on the next
// sample of the same radius, inside (mods/HollowCountry/scripts/4_World/Operations/HCReleaseRadius.c);
// spawning inside counts for nothing. The client learns the result through the server's own
// RPC_ENTRY, which HCUseLifecycle.c stores in MissionGameplay m_HCRelease*Observed; this step only
// reads those flags (HCTestRadiusObserved below) and never sends or counts anything.
//  mission  candidates are the published rows the client already has: HCMissionBeaconStore
//           (3_Game/Events/HCMissionBeaconData.c Get, Count, At; HCBeaconRow X, Z, Radius, Id), the
//           same centre and radius HCMissionBeacon.HCSampleReleaseRadius samples.
//  site     candidates come from repo data (driver_script.py: patrol sites of ai/sites.json, first
//           waypoint = HCSiteAnchor for a patrol, radius = the repo-default activation radius).
// Rounds: walk in, hold, walk out, hold, walk in again; every round doubles the hold (capped at
// HOLD_CAP, below the 600 s patrol despawn) so one hold covers the server's sampling cycle; every
// second round widens the in/out margins (an operator radius scale) and every fourth moves to the
// next candidate. Bounded by timeout_s. Per frame: one walker update and a few float compares; the
// mission rows are re-read at most once per second.
class HCDriverEnter
{
    static const int E_PICK = 0;
    static const int E_IN = 1;
    static const int E_HOLD_IN = 2;
    static const int E_OUT = 3;
    static const int E_HOLD_OUT = 4;
    static const float IN_MARGIN = 60.0;
    static const float OUT_MARGIN = 40.0;
    static const float HOLD_CAP = 540.0;
    static const int MAX_TRIED = 64;

    protected string m_Zone;
    protected int m_Observation;
    protected ref array<float> m_Sites;
    protected string m_Gait;
    protected float m_Hold;
    protected float m_Timeout;
    protected float m_Elapsed;
    protected float m_StageAge;
    protected float m_RowCheck;
    protected int m_Stage;
    protected int m_Rounds;
    protected float m_Margin;
    protected float m_X;
    protected float m_Z;
    protected float m_R;
    protected int m_Candidate;
    protected string m_RowId;
    protected ref map<int, bool> m_Tried = new map<int, bool>;
    protected string m_Detail;

    string Detail()
    {
        return m_Detail;
    }

    void Begin(HCDriverStep step)
    {
        m_Zone = step.zone;
        m_Observation = HCReleaseRadiusWire.MISSION;
        if (m_Zone == "site") { m_Observation = HCReleaseRadiusWire.AI_SITE; }
        m_Sites = step.sites;
        m_Gait = step.gait;
        if (m_Gait == "") { m_Gait = "jog"; }
        m_Hold = Math.Clamp(step.hold_s, 10.0, HCDriverEnter.HOLD_CAP);
        m_Timeout = Math.Max(step.timeout_s, 30.0);
        m_Elapsed = 0;
        m_StageAge = 0;
        m_RowCheck = 0;
        m_Stage = HCDriverEnter.E_PICK;
        m_Rounds = 0;
        m_Margin = 1.0;
        m_Candidate = -1;
        m_RowId = "";
        m_Tried.Clear();
        m_Detail = "";
    }

    protected int Count()
    {
        if (m_Zone == "mission") { return HCMissionBeaconStore.Get().Count(); }
        if (!m_Sites) { return 0; }
        return m_Sites.Count() / 3;
    }

    // Centre and radius of candidate index; false when it is not usable.
    protected bool Candidate(int index, out float x, out float z, out float radius, out string rowId)
    {
        rowId = "";
        if (m_Zone == "mission")
        {
            HCBeaconRow row = HCMissionBeaconStore.Get().At(index);
            if (!row || row.Radius <= 0) { return false; }
            x = row.X;
            z = row.Z;
            radius = row.Radius;
            rowId = row.Id;
            return true;
        }
        int base = index * 3;
        if (!m_Sites || base + 2 >= m_Sites.Count()) { return false; }
        x = m_Sites[base];
        z = m_Sites[base + 1];
        radius = m_Sites[base + 2];
        return radius > 0;
    }

    // The candidate whose edge is closest to the player, skipping the ones already tried.
    protected bool Pick(PlayerBase player)
    {
        int count = Count();
        if (count <= 0) { return false; }
        if (m_Tried.Count() >= count || m_Tried.Count() >= HCDriverEnter.MAX_TRIED) { m_Tried.Clear(); }
        vector pos = player.GetPosition();
        float bestGap = 1000000;
        int best = -1;
        for (int index = 0; index < count && index < 256; index++)
        {
            if (m_Tried.Contains(index)) { continue; }
            float cx;
            float cz;
            float cr;
            string cid;
            if (!Candidate(index, cx, cz, cr, cid)) { continue; }
            float dx = pos[0] - cx;
            float dz = pos[2] - cz;
            float gap = Math.AbsFloat(Math.Sqrt(dx * dx + dz * dz) - cr);
            if (gap < bestGap)
            {
                bestGap = gap;
                best = index;
            }
        }
        if (best < 0) { return false; }
        float px;
        float pz;
        float pr;
        string pickedId;
        if (!Candidate(best, px, pz, pr, pickedId)) { return false; }
        m_X = px;
        m_Z = pz;
        m_R = pr;
        m_Candidate = best;
        m_RowId = pickedId;
        m_Tried.Set(best, true);
        return true;
    }

    // A published mission row can end; true while the picked row is still in the store.
    protected bool RowPresent()
    {
        if (m_Zone != "mission") { return true; }
        HCMissionBeaconStore store = HCMissionBeaconStore.Get();
        for (int index = 0; index < store.Count(); index++)
        {
            HCBeaconRow row = store.At(index);
            if (row && row.Id == m_RowId) { return true; }
        }
        return false;
    }

    protected float Distance(PlayerBase player)
    {
        vector pos = player.GetPosition();
        float dx = pos[0] - m_X;
        float dz = pos[2] - m_Z;
        return Math.Sqrt(dx * dx + dz * dz);
    }

    protected float InsideDistance()
    {
        float inside = m_R - HCDriverEnter.IN_MARGIN * m_Margin;
        if (m_Zone == "mission" || inside < m_R * 0.5) { inside = m_R * 0.5; }
        return Math.Max(inside, 3.0);
    }

    protected void BeginIn(HCDriverWalker walker)
    {
        walker.Begin(m_X, m_Z, m_Gait, InsideDistance(), Math.Max(m_Timeout - m_Elapsed, 1.0));
        m_Stage = HCDriverEnter.E_IN;
        m_StageAge = 0;
    }

    protected void BeginOut(PlayerBase player, HCDriverWalker walker)
    {
        vector pos = player.GetPosition();
        float dx = pos[0] - m_X;
        float dz = pos[2] - m_Z;
        float length = Math.Sqrt(dx * dx + dz * dz);
        if (length < 1.0)
        {
            dx = 1.0;
            dz = 0;
            length = 1.0;
        }
        float reach = m_R + HCDriverEnter.OUT_MARGIN * m_Margin;
        float tx = Math.Clamp(m_X + dx / length * reach, 5.0, 15355.0);
        float tz = Math.Clamp(m_Z + dz / length * reach, 5.0, 15355.0);
        walker.Begin(tx, tz, m_Gait, 5.0, Math.Max(m_Timeout - m_Elapsed, 1.0));
        m_Stage = HCDriverEnter.E_OUT;
        m_StageAge = 0;
    }

    protected string Tail()
    {
        return " zone=" + m_Zone + " rounds=" + m_Rounds.ToString() + " candidate=" + m_Candidate.ToString() + " radius_m=" + Math.Round(m_R).ToString();
    }

    int Tick(PlayerBase player, float dt, HCDriverWalker walker, bool confirmed)
    {
        if (confirmed)
        {
            walker.Release(player);
            m_Detail = "server-confirmed" + Tail();
            if (m_Stage == HCDriverEnter.E_PICK && m_Elapsed <= 0) { m_Detail = "already-server-confirmed zone=" + m_Zone; }
            return HCDriverResult.OK;
        }
        if (!player || !player.IsAlive() || player.IsUnconscious())
        {
            walker.Release(player);
            m_Detail = "player-unavailable";
            return HCDriverResult.REFUSED;
        }
        if (player.IsRestrained())
        {
            walker.Release(player);
            m_Detail = "restrained";
            return HCDriverResult.REFUSED;
        }
        m_Elapsed = m_Elapsed + dt;
        m_StageAge = m_StageAge + dt;
        if (m_Elapsed > m_Timeout)
        {
            walker.Release(player);
            if (m_Candidate < 0)
            {
                m_Detail = "no-candidates zone=" + m_Zone;
                if (m_Zone == "mission") { m_Detail = "no-published-mission"; }
                return HCDriverResult.REFUSED;
            }
            m_Detail = "not-confirmed" + Tail();
            return HCDriverResult.TIMEOUT;
        }
        if (m_Stage == HCDriverEnter.E_PICK)
        {
            // Mission rows arrive over RPC after join; re-check once a second until the timeout.
            if (m_StageAge < 1.0 && m_Elapsed > dt) { return HCDriverResult.RUNNING; }
            m_StageAge = 0;
            if (!Pick(player))
            {
                if (m_Elapsed >= 15.0)
                {
                    m_Detail = "no-usable-candidates zone=" + m_Zone + " published=" + Count().ToString();
                    return HCDriverResult.REFUSED;
                }
                return HCDriverResult.RUNNING;
            }
            float leg = Math.AbsFloat(Distance(player) - InsideDistance());
            if (Distance(player) < m_R)
            {
                float outside = m_R + HCDriverEnter.OUT_MARGIN * m_Margin;
                leg = outside - Distance(player) + outside - InsideDistance();
            }
            if (leg > Math.Max(m_Timeout - m_Elapsed - m_Hold, 0) * 2.8)
            {
                m_Detail = "candidate-out-of-walk-budget distance_m=" + Math.Round(leg).ToString() + Tail();
                return HCDriverResult.REFUSED;
            }
            if (Distance(player) < m_R) { BeginOut(player, walker); }
            else { BeginIn(walker); }
            return HCDriverResult.RUNNING;
        }
        m_RowCheck = m_RowCheck + dt;
        if (m_RowCheck >= 1.0)
        {
            m_RowCheck = 0;
            if (!RowPresent())
            {
                walker.Release(player);
                m_Stage = HCDriverEnter.E_PICK;
                m_StageAge = 1.0;
                return HCDriverResult.RUNNING;
            }
        }
        if (m_Stage == HCDriverEnter.E_IN || m_Stage == HCDriverEnter.E_OUT)
        {
            int walked = walker.Update(player, dt);
            if (walked == HCDriverResult.RUNNING) { return walked; }
            if (walked != HCDriverResult.OK)
            {
                m_Detail = "walk-" + walker.Detail() + Tail();
                return walked;
            }
            if (m_Stage == HCDriverEnter.E_IN) { m_Stage = HCDriverEnter.E_HOLD_IN; }
            else { m_Stage = HCDriverEnter.E_HOLD_OUT; }
            m_StageAge = 0;
            return HCDriverResult.RUNNING;
        }
        if (m_StageAge < m_Hold) { return HCDriverResult.RUNNING; }
        if (m_Stage == HCDriverEnter.E_HOLD_IN)
        {
            BeginOut(player, walker);
            return HCDriverResult.RUNNING;
        }
        // One full in/out round without a server answer.
        m_Rounds = m_Rounds + 1;
        m_Hold = Math.Min(m_Hold * 2.0, HCDriverEnter.HOLD_CAP);
        if (m_Rounds % 2 == 0) { m_Margin = m_Margin * 2.0; }
        if (m_Rounds % 4 == 0)
        {
            m_Margin = 1.0;
            m_Stage = HCDriverEnter.E_PICK;
            m_StageAge = 1.0;
            return HCDriverResult.RUNNING;
        }
        BeginIn(walker);
        return HCDriverResult.RUNNING;
    }
}

// Multi-waypoint walk with a stuck ladder (kind route). points = flat x,z pairs from driver_script.py.
// Each leg is an HCDriverWalker leg in hand-over mode: after HANDOVER_SECONDS without 1 m of progress
// the walker reports stuck and the route climbs one rung:
//   1 side-right  2 s strafe to the right of the target heading (calibrated angle sign)
//   2 side-left   2 s strafe to the left (calibrated angle sign)
//   3 back-up     2 s walking backwards                    (180, speed 1 per human.c:467)
//   4 door        ActionOpenDoors on a door in reach of where the player stands, through the
//                 client action manager (HCDriverActions.BeginInReach; ActionOpenDoors.c:1); a
//                 locked or open door fails Can() and is skipped, never forced
//   5 skip        once per route: give up the current waypoint and head for the next one
// then the step ends refused stuck:<last rung>. Progress of 10 m since the last stuck spell starts
// the ladder again at rung 1; reaching a waypoint resets it. Collisions stay engine-owned: no
// SetPosition, no teleport, no physics change. Per frame: one walker update or one input override
// (plus one ray during the door rung); nothing is allocated after Begin.
class HCDriverRoute
{
    static const int R_WALK = 0;
    static const int R_SIDE_RIGHT = 1;
    static const int R_SIDE_LEFT = 2;
    static const int R_BACK = 3;
    static const int R_DOOR = 4;
    static const int R_SKIP = 5;
    static const float MOVE_SECONDS = 2.0;
    static const float DOOR_SECONDS = 6.0;
    static const float FRESH_PROGRESS = 10.0;

    protected ref array<float> m_Points;
    protected string m_Gait;
    protected float m_Arrive;
    protected float m_Timeout;
    protected float m_Elapsed;
    protected int m_Waypoint;
    protected int m_Rung;
    protected int m_Mode;
    protected float m_ModeAge;
    protected float m_StuckAt;
    protected bool m_Skipped;
    protected int m_Climbs;
    protected int m_Doors;
    protected bool m_DoorStarted;
    protected string m_Detail;

    string Detail()
    {
        return m_Detail;
    }

    static string RungName(int rung)
    {
        if (rung == HCDriverRoute.R_SIDE_RIGHT) { return "side-right"; }
        if (rung == HCDriverRoute.R_SIDE_LEFT) { return "side-left"; }
        if (rung == HCDriverRoute.R_BACK) { return "back-up"; }
        if (rung == HCDriverRoute.R_DOOR) { return "door"; }
        if (rung == HCDriverRoute.R_SKIP) { return "skip"; }
        return "none";
    }

    // False when the points list is unusable (the step is then refused route-needs-points).
    bool Begin(HCDriverStep step)
    {
        m_Points = step.points;
        m_Gait = step.gait;
        if (m_Gait == "") { m_Gait = "jog"; }
        m_Arrive = Math.Max(step.arrive_m, 2.0);
        m_Timeout = Math.Max(step.timeout_s, 10.0);
        m_Elapsed = 0;
        m_Waypoint = 0;
        m_Rung = 0;
        m_Mode = HCDriverRoute.R_WALK;
        m_ModeAge = 0;
        m_StuckAt = 1000000;
        m_Skipped = false;
        m_Climbs = 0;
        m_Doors = 0;
        m_DoorStarted = false;
        m_Detail = "";
        return m_Points && m_Points.Count() >= 4 && m_Points.Count() % 2 == 0;
    }

    protected int Legs()
    {
        return m_Points.Count() / 2;
    }

    protected float Remaining(PlayerBase player)
    {
        vector pos = player.GetPosition();
        float dx = m_Points[m_Waypoint * 2] - pos[0];
        float dz = m_Points[m_Waypoint * 2 + 1] - pos[2];
        return Math.Sqrt(dx * dx + dz * dz);
    }

    protected void Leg(HCDriverWalker walker)
    {
        walker.Begin(m_Points[m_Waypoint * 2], m_Points[m_Waypoint * 2 + 1], m_Gait, m_Arrive, Math.Max(m_Timeout - m_Elapsed, 1.0));
        walker.HandOverStuck();
        m_Mode = HCDriverRoute.R_WALK;
        m_ModeAge = 0;
    }

    protected string Tail(PlayerBase player)
    {
        return " waypoint=" + m_Waypoint.ToString() + "/" + Legs().ToString() + " climbs=" + m_Climbs.ToString() + " doors=" + m_Doors.ToString() + " remaining_m=" + Math.Round(Remaining(player)).ToString();
    }

    // Strafe or back up relative to the heading toward the current waypoint, for MOVE_SECONDS.
    protected void Maneuver(PlayerBase player, float offset, float speed)
    {
        HumanInputController input = player.GetInputController();
        if (!input) { return; }
        vector pos = player.GetPosition();
        float want = Math.Atan2(m_Points[m_Waypoint * 2] - pos[0], m_Points[m_Waypoint * 2 + 1] - pos[2]) * Math.RAD2DEG;
        float frame = HCDriverWalker.MovementFrame(player) + HCDriverMovement.HeadingOffset;
        float diff = HCDriverWalker.Wrap180(want - frame + offset);
        // The fit, not a native doc, gives +/-90 requests for a full circle when |scale|=2.
        // Native 1_Core/proto/EnMath.c:540 Math.Clamp.
        HCDriverMovement.Request(speed, Math.Clamp(diff / HCDriverMovement.AngleScale, -180.0, 180.0));
    }

    // Next rung after a stuck report; false when the ladder is exhausted.
    protected bool Climb(PlayerBase player, HCDriverWalker walker)
    {
        float remaining = Remaining(player);
        if (remaining < m_StuckAt - HCDriverRoute.FRESH_PROGRESS) { m_Rung = 0; }
        m_StuckAt = remaining;
        m_Rung = m_Rung + 1;
        if (m_Rung == HCDriverRoute.R_SKIP && (m_Skipped || m_Waypoint + 1 >= Legs())) { return false; }
        if (m_Rung > HCDriverRoute.R_SKIP) { return false; }
        m_Climbs = m_Climbs + 1;
        walker.Release(player);
        m_Mode = m_Rung;
        m_ModeAge = 0;
        m_DoorStarted = false;
        return true;
    }

    int Tick(PlayerBase player, float dt, HCDriverWalker walker, HCDriverActions actions)
    {
        if (!player || !player.IsAlive() || player.IsUnconscious())
        {
            walker.Release(player);
            m_Detail = "player-unavailable";
            return HCDriverResult.REFUSED;
        }
        if (player.IsRestrained())
        {
            walker.Release(player);
            m_Detail = "restrained";
            return HCDriverResult.REFUSED;
        }
        if (m_Elapsed <= 0 && !walker.IsActive()) { Leg(walker); }
        m_Elapsed = m_Elapsed + dt;
        m_ModeAge = m_ModeAge + dt;
        if (m_Elapsed > m_Timeout)
        {
            actions.Abort(player, walker);
            m_Detail = "route-timeout" + Tail(player);
            return HCDriverResult.TIMEOUT;
        }
        if (m_Mode == HCDriverRoute.R_WALK)
        {
            int walked = walker.Update(player, dt);
            if (walked == HCDriverResult.OK)
            {
                m_Rung = 0;
                m_StuckAt = 1000000;
                if (m_Waypoint + 1 >= Legs())
                {
                    m_Detail = "arrived" + Tail(player);
                    return HCDriverResult.OK;
                }
                m_Waypoint = m_Waypoint + 1;
                Leg(walker);
                return HCDriverResult.RUNNING;
            }
            if (walked != HCDriverResult.RUNNING)
            {
                m_Detail = walker.Detail() + Tail(player);
                return walked;
            }
            if (!walker.TakeStuck()) { return HCDriverResult.RUNNING; }
            if (!Climb(player, walker))
            {
                walker.Release(player);
                m_Detail = "stuck:" + HCDriverRoute.RungName(m_Rung - 1) + Tail(player);
                return HCDriverResult.REFUSED;
            }
            return HCDriverResult.RUNNING;
        }
        if (m_Mode == HCDriverRoute.R_SIDE_RIGHT || m_Mode == HCDriverRoute.R_SIDE_LEFT || m_Mode == HCDriverRoute.R_BACK)
        {
            if (m_ModeAge >= HCDriverRoute.MOVE_SECONDS)
            {
                walker.Release(player);
                Leg(walker);
                return HCDriverResult.RUNNING;
            }
            if (m_Mode == HCDriverRoute.R_SIDE_RIGHT) { Maneuver(player, 90.0, 2.0); }
            if (m_Mode == HCDriverRoute.R_SIDE_LEFT) { Maneuver(player, -90.0, 2.0); }
            if (m_Mode == HCDriverRoute.R_BACK) { Maneuver(player, 180.0, 1.0); }
            return HCDriverResult.RUNNING;
        }
        if (m_Mode == HCDriverRoute.R_DOOR)
        {
            if (!m_DoorStarted)
            {
                m_DoorStarted = true;
                actions.BeginInReach("open_door", HCDriverRoute.DOOR_SECONDS);
            }
            int opened = actions.Tick(player, dt, walker);
            if (opened == HCDriverResult.RUNNING) { return opened; }
            actions.Abort(player, walker);
            if (opened == HCDriverResult.OK) { m_Doors = m_Doors + 1; }
            Leg(walker);
            return HCDriverResult.RUNNING;
        }
        // R_SKIP: the current waypoint is given up once; the next leg is the re-route.
        m_Skipped = true;
        m_Waypoint = m_Waypoint + 1;
        m_Rung = 0;
        m_StuckAt = 1000000;
        Leg(walker);
        return HCDriverResult.RUNNING;
    }
}
