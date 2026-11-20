// #144 AI scavenging runs / #150 camp needs read the season phase.
// Pure decisions over the HC-34 picker survey; no scan, save or timer lives here.
// Every limit is a named field of mission/hollow-country/ai/picker-routes.json.
// Opt-out: $profile:HollowCountry/acceptance/scavenge_runs.disable (module opt-out is
// EnableEncounters). Native scripts-1.30.164289: 1_Core/proto/EnSystem.c:397 FileExist;
// 1_Core/proto/EnScript.c:380 Count, :407 Insert, :470 RemoveOrdered;
// 1_Core/proto/EnString.c IndexOf. No Expansion calls. Runtime acceptance PENDING.
// Danger comes only from the party's own experience (HCPickDanger) and from the
// world's remembered noise (HCInfectedMemory.Heat, a cell value with no player
// identity or live destination). Live player positions are never read here.
class HCPickPolicy
{
    static const string OPT_OUT = "$profile:HollowCountry/acceptance/scavenge_runs.disable";
    static const string NEED_REFUSAL = "PICKER_NO_SUPPLY_NEED";
    static const string DANGER_REFUSAL = "PICKER_ROUTE_DANGER";

    // Operator file is restart-scoped; never probe the filesystem per tick.
    protected static bool s_OptOutRead;
    protected static bool s_Enabled;

    static bool Enabled()
    {
        if (!s_OptOutRead)
        {
            s_OptOutRead = true;
            s_Enabled = !FileExist(HCPickPolicy.OPT_OUT);
        }
        return s_Enabled;
    }

    // Season phase read only: 0 spring, 1 summer, 2 autumn, 3 winter, -1 when the
    // weather owner is absent or inactive (callers then keep the neutral scale).
    static int SeasonPhase()
    {
        HCServer server = HCServer.Get();
        if (!server) { return -1; }
        HCWeatherDaysModule weather = HCWeatherDaysModule.Cast(server.HCAdminModuleNamed("WeatherDays"));
        if (!weather) { return -1; }
        return weather.HCSeasonPhaseCode();
    }

    // Percent of the base stash target for this season; 100 is the neutral scale.
    static int NeedPercent(HCPickerSurvey survey, int phase)
    {
        if (!survey) { return 100; }
        if (phase == 0) { return survey.RunNeedPercentSpring; }
        if (phase == 1) { return survey.RunNeedPercentSummer; }
        if (phase == 2) { return survey.RunNeedPercentAutumn; }
        if (phase == 3) { return survey.RunNeedPercentWinter; }
        return 100;
    }

    static int NeedTarget(HCPickerSurvey survey, int phase)
    {
        if (!survey) { return 0; }
        return (survey.RunNeedStashItems * HCPickPolicy.NeedPercent(survey, phase)) / 100;
    }

    // An unreadable stash (-1) never claims a need: no run is started on a guess.
    static bool NeedsSupplies(HCPickerSurvey survey, int stashItems, int phase)
    {
        if (!survey || stashItems < 0) { return false; }
        return stashItems < HCPickPolicy.NeedTarget(survey, phase);
    }

    static string PartyRefusal(HCPickerSurvey survey, int members)
    {
        if (!survey || members < 0) { return ""; }
        if (members < survey.RunMinMembers) { return "PICKER_PARTY_TOO_SMALL"; }
        if (members > survey.RunMaxMembers) { return "PICKER_PARTY_TOO_LARGE"; }
        return "";
    }

    // Non-terminal custody phases count as an active run.
    static bool ActiveTrip(string phase)
    {
        return phase == "leaving" || phase == "returning" || phase == "acquiring" || phase == "depositing";
    }

    // Named world and per-camp caps over trips that are not yet terminal.
    static string CapRefusal(HCPickerSurvey survey, HCPickerRoute route, int activeRuns, int activeInCamp)
    {
        if (!survey || !route) { return ""; }
        if (activeRuns >= survey.RunMaxActiveRuns) { return "PICKER_WORLD_RUN_CAP"; }
        if (activeInCamp >= survey.RunMaxPartiesPerCamp) { return "PICKER_CAMP_PARTY_CAP"; }
        return "";
    }

    static string RouteDanger(HCPickerSurvey survey, HCPickDanger danger, HCPickerRoute route, int now)
    {
        if (!survey || !route || !route.Waypoints) { return ""; }
        if (danger)
        {
            string clue = danger.HCFresh(route.RouteId, now, survey.RunDangerClueSeconds);
            if (clue != "") { return HCPickPolicy.DANGER_REFUSAL + "_" + clue; }
        }
        int count = route.Waypoints.Count();
        for (int pointIndex = 0; pointIndex < count; pointIndex++)
        {
            if (HCInfectedMemory.Heat(route.Waypoints[pointIndex].HCPosition()) >= survey.RunDangerHeatAvoid) { return HCPickPolicy.DANGER_REFUSAL + "_NOISE"; }
        }
        return "";
    }

    // A deferred refusal re-arms the party after RunNeedRecheckSeconds, not every visit.
    static bool Deferred(string refusal)
    {
        if (refusal == HCPickPolicy.NEED_REFUSAL) { return true; }
        return refusal.IndexOf(HCPickPolicy.DANGER_REFUSAL) == 0;
    }

    // First defect of the run fields by name; "" when usable.
    static string RunRefusal(HCPickerSurvey survey)
    {
        if (!survey) { return "PICKER_SURVEY_RUN_LIMITS"; }
        if (survey.RunMinMembers < 1 || survey.RunMaxMembers < survey.RunMinMembers) { return "PICKER_SURVEY_RUN_MEMBERS"; }
        if (survey.RunMaxCarriedHouseGoods < 1 || survey.RunMaxCarriedHouseGoods > survey.MaxCargoScan) { return "PICKER_SURVEY_RUN_CARRY"; }
        if (survey.RunMaxHousesPerRun < 0 || survey.RunMaxHouseAttempts < survey.RunMaxHousesPerRun) { return "PICKER_SURVEY_RUN_HOUSES"; }
        if (survey.RunMaxHouseCandidates < 1 || survey.RunMaxHouseCandidates > survey.MaxScannedObjects) { return "PICKER_SURVEY_RUN_HOUSES"; }
        if (survey.RunHouseSearchRadiusMeters <= 0 || survey.RunHouseSearchRadiusMeters > survey.MaxLegMeters) { return "PICKER_SURVEY_RUN_HOUSES"; }
        if (survey.RunHouseSearchSeconds <= 0 || survey.RunHouseWalkSeconds <= survey.RunHouseSearchSeconds) { return "PICKER_SURVEY_RUN_HOUSES"; }
        if (survey.RunNeedStashItems < 1 || survey.RunNeedRecheckSeconds < 1) { return "PICKER_SURVEY_RUN_NEED"; }
        if (survey.RunNeedPercentSpring < 1 || survey.RunNeedPercentSummer < 1) { return "PICKER_SURVEY_RUN_NEED"; }
        if (survey.RunNeedPercentAutumn < 1 || survey.RunNeedPercentWinter < 1) { return "PICKER_SURVEY_RUN_NEED"; }
        int widest = Math.Max(Math.Max(survey.RunNeedPercentSpring, survey.RunNeedPercentSummer), Math.Max(survey.RunNeedPercentAutumn, survey.RunNeedPercentWinter));
        // The stash count is read inside MaxCargoScan; a larger target could never be decided.
        if ((survey.RunNeedStashItems * widest) / 100 > survey.MaxCargoScan) { return "PICKER_SURVEY_RUN_NEED_BEYOND_SCAN"; }
        if (!(survey.RunDangerHeatAvoid > 0) || survey.RunDangerHeatAvoid > 1) { return "PICKER_SURVEY_RUN_DANGER"; }
        if (survey.RunDangerClueSeconds < 1 || survey.RunDangerMaxClues < 1 || survey.RunCombatAbortSeconds < 1) { return "PICKER_SURVEY_RUN_DANGER"; }
        if (survey.RunMaxActiveRuns < 1 || survey.RunMaxPartiesPerCamp < 1) { return "PICKER_SURVEY_RUN_CAPS"; }
        map<string, int> partiesByCamp = new map<string, int>;
        for (int routeIndex = 0; routeIndex < survey.Routes.Count(); routeIndex++)
        {
            int inCamp = 0;
            if (!partiesByCamp.Find(survey.Routes[routeIndex].LocalityId, inCamp)) { inCamp = 0; }
            inCamp++;
            partiesByCamp.Set(survey.Routes[routeIndex].LocalityId, inCamp);
            if (inCamp > survey.RunMaxPartiesPerCamp) { return "PICKER_SURVEY_CAMP_PARTY_CAP"; }
        }
        return "";
    }
}
