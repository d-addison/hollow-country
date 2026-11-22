// Authored scalar algorithms: also exercised by HCInteriorSelfTests in DayZDiag.
// Journal schema 2: explicit forward migration; no wipe, downgrade or refill.
class HCInteriorRules
{
    static const float MAX_HOUSE_TILT_DEGREES = 0.5;
    protected static ref HCActivityWindow s_Activity;

    static HCActivityWindow HCActivity()
    {
        if (!s_Activity) s_Activity = new HCActivityWindow("[HC Interiors] rules", "checks admitted refused");
        return s_Activity;
    }

    static bool TiltAcceptable(vector orientation, float maxDegrees)
    {
        // Inclusive signed comparisons accept -0.0 and refuse NaN.
        return orientation[1] >= -maxDegrees && orientation[1] <= maxDegrees && orientation[2] >= -maxDegrees && orientation[2] <= maxDegrees;
    }

    static int Quantize(float value)
    {
        return Math.Floor(value * 100.0 + 0.5);
    }

    static int Yaw(float angle)
    {
        int turns = Math.Floor(angle / 360.0);
        return Quantize(angle - turns * 360.0) % 36000;
    }

    static int Layout(int x, int y, int z, int yaw, int seed)
    {
        int mixed = (Math.AbsInt(x) % 1009) * 31 + (Math.AbsInt(y) % 1009) * 17 + (Math.AbsInt(z) % 1009) * 13 + yaw + seed;
        return mixed % 3;
    }

    // 0 = empty, 1 = one Rag, 2 = one Battery9V. Fixed supplementary escrow.
    static int Allocation(int layout, int rags, int batteries)
    {
        if (rags < 0 || batteries < 0) return 0;
        if (layout == 0 && rags < 4) return 1;
        if (layout == 1 && batteries < 2) return 2;
        return 0;
    }

    // available -> reserved -> spent/quarantined. No reverse transition.
    static bool Transition(int before, int after)
    {
        return (before == 0 && after == 1) || (before == 1 && (after == 2 || after == 3));
    }

    static int Recover(bool exists, bool parses, int schema, int phase)
    {
        if (!exists) return 0;
        if (parses && schema == 1 && phase == 2) return 2;
        return 3;
    }

    // Each flag means an exact identity/actor/schema match, not merely valid JSON.
    // Even intent-before-attempt is ambiguous under unproven filesystem durability.
    static int RecoverJournal(bool claimExists, bool claimValid, bool attemptExists, bool attemptValid, bool resultExists, bool resultValid, int schema, int phase)
    {
        if (!claimExists && !attemptExists && !resultExists) return 0;
        if (!claimExists || !claimValid || !resultExists || !resultValid) return 3;
        if (schema != 1 && schema != 2) return 3;
        if (schema == 1 && attemptExists) return 3;
        if (schema == 2 && (!attemptExists || !attemptValid)) return 3;
        if (phase == 2) return 2;
        return 3;
    }

    static bool PoolWithinBounds(int entries, int rags, int batteries)
    {
        return entries >= 1 && entries <= 12 && rags >= 0 && rags <= 4 && batteries >= 0 && batteries <= 2;
    }

    static int ReconcilePhase(int before, int recovered)
    {
        if (before < 0 || before > 3 || recovered < 0 || recovered > 3) return 3;
        if (before == 3) return 3;
        if (before == recovered) return before;
        if (before != 0 && recovered == 0) return 3;
        if (before == 2) return 3;
        return recovered;
    }

    static bool MigrationAllowed(int source, int target, bool explicitApproval, bool identicalManifest)
    {
        return source == 1 && target == 2 && explicitApproval && identicalManifest;
    }

    static bool JournalVersionAccepted(int schema, int source)
    {
        return schema == 2 && source == 1;
    }

    // Reuse only a pointer already owned by this module in this process. Static
    // props have no demonstrated persistent ownership ID; transform != ownership.
    static int OrphanDecision(bool queryBounded, int matches, int ownedCount, bool exactTransform)
    {
        if (!queryBounded || matches < 0 || matches > 1 || ownedCount < 0 || ownedCount > matches) return 3;
        if (matches == 0) return 0;
        if (matches == 1 && ownedCount == 1 && exactTransform) return 1;
        return 3;
    }

    static bool MaySearch(bool server, bool interiors, bool search, bool proof, bool ready, bool livePlayer, bool available)
    {
        bool allowed = server && interiors && search && proof && ready && livePlayer && available;
        if (GetGame() && GetGame().IsServer())
        {
            HCActivity().Add("checks");
            if (allowed) HCActivity().Add("admitted");
            else HCActivity().Add("refused");
        }
        return allowed;
    }

    protected static bool s_PlacementChecked;
    protected static bool s_PlacementOptIn;
    protected static bool s_SearchChecked;
    protected static bool s_SearchOptIn;

    // Only change alongside recorded runtime artifacts and normal signed-PBO tests.
    static bool PlacementAccepted()
    {
        return false;
    }

    static bool SearchAccepted()
    {
        return false;
    }

    // Placement and search ship default-on through the template house path.
    // Native placement/transfer acceptance remains pending.
    static bool PlacementOptIn()
    {
        return !FileExist("$profile:HollowCountry/acceptance/interior_placement.disable");
    }

    protected static bool s_SearchMarkerLoaded;
    protected static bool s_SearchMarkerOptIn;

    static bool SearchOptIn()
    {
        if (s_SearchMarkerLoaded) { return s_SearchMarkerOptIn; }
        s_SearchMarkerLoaded = true;
        s_SearchMarkerOptIn = !FileExist("$profile:HollowCountry/acceptance/interior_search.disable");
        return s_SearchMarkerOptIn;
    }

    static bool PlacementAdmitted()
    {
        if (PlacementAccepted())
            return true;
        if (!GetGame() || !GetGame().IsServer())
            return false;
        if (!s_PlacementChecked)
        {
            s_PlacementChecked = true;
            s_PlacementOptIn = PlacementOptIn();
            Print(HCV1Admission.Line("InteriorPlacement", s_PlacementOptIn, "interior_placement", PlacementAccepted()));
        }
        return s_PlacementOptIn;
    }

    static bool SearchAdmitted()
    {
        if (SearchAccepted())
            return true;
        if (!GetGame() || !GetGame().IsServer())
            return false;
        if (!s_SearchChecked)
        {
            s_SearchChecked = true;
            s_SearchOptIn = SearchOptIn();
            Print(HCV1Admission.Line("InteriorSearch", s_SearchOptIn, "interior_search", SearchAccepted()));
        }
        return s_SearchOptIn;
    }

    static string TransformKey(vector position, vector orientation)
    {
        return Quantize(position[0]).ToString() + "_" + Quantize(position[1]).ToString() + "_" + Quantize(position[2]).ToString() + "_" + Yaw(orientation[0]).ToString() + "_" + Quantize(orientation[1]).ToString() + "_" + Quantize(orientation[2]).ToString();
    }

    static bool SaneVector(vector value, float limit)
    {
        // Explicit comparisons also reject NaN and infinities.
        return value[0] >= -limit && value[0] <= limit && value[1] >= -limit && value[1] <= limit && value[2] >= -limit && value[2] <= limit;
    }
}

// Fixed metric schemas only: no entity/player keys, queues, scans or timers.
// Native snapshot: EnString.c Split; EnScript.c array Count/Insert; Game.c GetTickTime.
// Every total is process-local and saturates; window counts reset only after print.
class HCActivityWindow
{
    protected string m_Tag;
    protected ref array<string> m_Keys = new array<string>;
    protected ref array<int> m_Window = new array<int>;
    protected ref array<int> m_Total = new array<int>;
    protected float m_Since;

    void HCActivityWindow(string tag, string keys)
    {
        m_Tag = tag;
        keys.Split(" ", m_Keys);
        for (int i = 0; i < m_Keys.Count() && i < 32; i++)
        {
            m_Window.Insert(0);
            m_Total.Insert(0);
        }
        m_Since = GetGame().GetTickTime();
    }

    void Add(string key)
    {
        int index = m_Keys.Find(key);
        if (index < 0 || index >= m_Total.Count()) return;
        if (m_Window[index] < 2147483647) m_Window[index] = m_Window[index] + 1;
        if (m_Total[index] < 2147483647) m_Total[index] = m_Total[index] + 1;
    }

    void Report(string state = "", bool force = false)
    {
        if (!GetGame() || !GetGame().IsServer()) return;
        float now = GetGame().GetTickTime();
        if (!force && now - m_Since < 600) return;
        string line = m_Tag + " summary window_s=" + (now - m_Since).ToString();
        for (int i = 0; i < m_Total.Count(); i++)
        {
            line = line + " " + m_Keys[i] + "=" + m_Window[i].ToString() + " " + m_Keys[i] + "_total=" + m_Total[i].ToString();
            m_Window[i] = 0;
        }
        if (state != "") line = line + " " + state;
        Print(line + " runtime=PENDING");
        m_Since = now;
    }
}

modded class HCInteriorsModule
{
    override void OnStart(HCSettings settings)
    {
        HCInteriorRules.HCActivity();
        HCSearchHouses.HCActivity();
        super.OnStart(settings);
    }

    override void OnTick(float deltaTime)
    {
        super.OnTick(deltaTime);
        HCInteriorRules.HCActivity().Report();
        HCSearchHouses.HCActivity().Report();
    }

    override void OnStop()
    {
        HCInteriorRules.HCActivity().Report("", true);
        HCSearchHouses.HCActivity().Report("", true);
        super.OnStop();
    }
}
