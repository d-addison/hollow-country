// #316: selection happens once before materialization/command entry. No new
// scheduler, census, animation API or pose slot owner. The addon owns
// command entry, bind preflight and settled-Move checks under #315.
// Native scripts-1.30.164289: EnMath.c:38 RandomInt; Game.c:914 GetTickTime;
// DayZInfectedInputController.c:9 GetMindState; Object.c:287 GetPosition.
// Existing HCVariety native threat/hit wakes and LOD sub-budgets are unchanged.
class HCPoseVariation
{
    static bool HCEnabled()
    {
        return HCInfectedTuning.Variety().Variety.EnablePoseVariation;
    }

    // Small bounded integer generator: no overflow, no global Randomize call.
    // Separate draws from one identity keep choices stable across cursor visits.
    static int HCDraw(inout int seed)
    {
        seed = (seed * 251 + 17) % 65521;
        return seed;
    }

    static float HCUnit(inout int seed)
    {
        return HCDraw(seed) / 65521.0;
    }

    static string HCStartLine(bool preference)
    {
        bool enabled = preference && HCEnabled();
        return "[HC Variety] pose_variation enabled=" + enabled.ToString() + " switch=Variety.EnablePoseVariation selection=weighted_once admission=0.25..3s calm_deadline=30..60s wake=existing_cursor face_down=graph_unexposed command_gate=addon_owned runtime=PENDING";
    }

    // -1 standing native idle, 0 crawler, 1..4 graph pose. Cadences remain
    // operator controls: zero excludes a category, N gives it odds of 1/N.
    // Unknown context stays outside posture eligibility. Feeder stays at gas
    // stations; rooms/churches favour sitting, wrecks lying, roads sleeping.
    static int HCFresh(string context, int ordinal, HCInfectedVarietyConfig config, bool classPresent)
    {
        if (!HCEnabled())
        {
            int legacy = HCInfectedVarietyPolicy.HCPoseFresh(context, ordinal, config.PosedFreshEvery, classPresent);
            if (legacy > 0) { return legacy; }
            if (HCInfectedVarietyPolicy.HCStandingFresh(ordinal, config.StandingRiserEvery)) { return -1; }
            return 0;
        }
        int seed = Math.RandomInt(1, 65521);
        int primary = HCInfectedVarietyPolicy.HCPosePrimary(context);
        if (primary > 0 && classPresent && config.PosedFreshEvery > 0 && HCUnit(seed) < 1.0 / config.PosedFreshEvery)
        {
            // Four fixed candidates, no allocation or unbounded retry. Face-down
            // clips are packaged but command ints/graph only expose 1..4.
            int total;
            for (int pose = 1; pose <= 4; pose++) { total += HCWeight(context, pose); }
            int ticket = Math.Floor(HCUnit(seed) * total);
            for (int choice = 1; choice <= 4; choice++)
            {
                ticket -= HCWeight(context, choice);
                if (ticket < 0) { return choice; }
            }
        }
        if (config.StandingRiserEvery > 0 && HCUnit(seed) < 1.0 / config.StandingRiserEvery) { return -1; }
        return 0;
    }

    static int HCWeight(string context, int pose)
    {
        if (!HCPostureAdmission.HCCanEnter(HCPostureAdmission.HCPoseMode(pose))) { return 0; }
        if (pose == HCInfectedVarietyPolicy.HCPosePrimary(context)) { return 6; }
        if (pose == 4) { return 0; }
        if (pose == 1) { return 2; }
        return 1;
    }
}

// The native loader can zero-fill a missing bool even in a present Variety
// block. Apply presence defaults on both authored and operator-profile loads.
modded class HCInfectedVarietyConfig
{
    override void HCApplyTuningDefaults(string content)
    {
        super.HCApplyTuningDefaults(content);
        if (!Variety) { Variety = new HCC1Variety; }
        // The switch sits inside the Variety block: depth 2 keeps an explicit false.
        if (!HCJsonFields.Check(content, "EnablePoseVariation", 2, false)) { Variety.EnablePoseVariation = true; }
    }
}

modded class ZombieBase
{
    protected int m_HCPoseVariationSeed;
    protected bool m_HCPoseAdmissionSeeded;

    protected void HCPoseSeed()
    {
        if (m_HCPoseVariationSeed == 0) { m_HCPoseVariationSeed = Math.RandomInt(1, 65521); }
    }

    // Reuse the existing admission deadline and existing owner cursor. Waiting
    // never holds an actor idle, and cannot delay a native threat response.
    override bool HCVarietyCanTry(float now)
    {
        if (HCPoseVariation.HCEnabled() && !m_HCPoseAdmissionSeeded)
        {
            HCPoseSeed();
            m_HCPoseAdmissionSeeded = true;
            m_HCVarietyNextTry = Math.Max(m_HCVarietyNextTry, now + 0.25 + 2.75 * HCPoseVariation.HCUnit(m_HCPoseVariationSeed));
        }
        return super.HCVarietyCanTry(now);
    }

    protected void HCPoseSetDeadline()
    {
        if (!HCPoseVariation.HCEnabled()) { return; }
        HCPoseSeed();
        // Existing unused sleep deadline now expires on the native tick clock;
        // no Timer/CallLater, and no animation-rate or get-up duration changes.
        m_HCVarietySleepUntil = GetGame().GetTickTime() + 600 + 1200 * HCPoseVariation.HCUnit(m_HCPoseVariationSeed);
    }

    override bool HCVarietySleep(float now, bool permitted)
    {
        bool entered = super.HCVarietySleep(now, permitted);
        if (entered) { HCPoseSetDeadline(); }
        return entered;
    }

    override bool HCVarietyFreshPosed(float now, string place, int role, int pose)
    {
        bool entered = super.HCVarietyFreshPosed(now, place, role, pose);
        if (entered) { HCPoseSetDeadline(); }
        return entered;
    }

    override bool HCVarietyFreshStanding(float now, string place, int role)
    {
        bool entered = super.HCVarietyFreshStanding(now, place, role);
        if (entered) { HCPoseSetDeadline(); }
        return entered;
    }

    override bool HCVarietyFreshCrawler(float now, string place, int role)
    {
        bool entered = super.HCVarietyFreshCrawler(now, place, role);
        if (entered) { HCPoseSetDeadline(); }
        return entered;
    }
}

modded class HCInfectedModule
{
    // Native geometry chain: HCAlertChain.c:153-165, Global/DayZPhysics.c:199
    // RaycastRV. Each clear test uses <=2 rays; this override plus the base
    // can use <=4 rays in total, with no object or room query.
    // Rotates the first observer tested so one blocked player cannot starve
    // a clear crouched player in reach; one extra two-ray test per visit.
    protected int m_HCPoseObserverCursor;

    override protected bool HCVarietyNearStanding(array<Man> players, HCInfectedActor actor, ZombieBase candidate, bool checkGeometry, bool preserveObserver = false)
    {
        // Expiry only shortens a calm hold; never postpones the existing wake
        // test. This runs in the same bounded spatial work slice as before.
        if (checkGeometry && HCPoseVariation.HCEnabled() && candidate.HCVarietySleepUntil() > 0 && GetGame().GetTickTime() >= candidate.HCVarietySleepUntil()) { return true; }
        if (HCPoseVariation.HCEnabled())
        {
            // Any stance in reach qualifies, including a crouched client. Use
            // the existing shared player sample and clear-geometry service;
            // at most 32 distances and one extra two-ray test in the owner's spatial
            // candidate slice. Overlarge observer sets release conservatively.
            if (players.Count() > 32) { return true; }
            int observers = players.Count();
            for (int step = 0; step < observers; step++)
            {
                int index = (m_HCPoseObserverCursor + step) % observers;
                Man observer = players[index];
                if (!observer || !observer.IsAlive()) { continue; }
                if (vector.DistanceSq(observer.GetPosition(), candidate.GetPosition()) > 9) { continue; }
                if (!checkGeometry) { return true; }
                // One two-ray test: a blocked observer falls through to the
                // existing standing test; the next visit starts after it.
                m_HCPoseObserverCursor = (index + 1) % observers;
                if (m_AlertChain.HCVarietyClear(observer.GetPosition(), candidate)) { return true; }
                break;
            }
        }
        return super.HCVarietyNearStanding(players, actor, candidate, checkGeometry, preserveObserver);
    }
}
