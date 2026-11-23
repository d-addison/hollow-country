// HC site survey: implementation behind the director's virtual seams.
class HCXAISiteSurvey : HCXAISiteStorage
{
    override protected vector HCSiteAnchor(HCXAISite site)
    {
        if (site.Kind == "holdout") { return site.HousePosition; }
        return site.Waypoints[0];
    }
    override protected float HCPlayerGap(HCXAISite site)
    {
        this.HCRefreshPlayers();
        vector anchor = this.HCSiteAnchor(site);
        float nearestSq = 1000000000;
        for (int playerIndex = 0; playerIndex < m_Players.Count() && playerIndex < 64; playerIndex++)
        {
            Man observer = m_Players[playerIndex];
            if (!observer || !observer.GetIdentity() || !observer.IsAlive()) { continue; }
            vector position = observer.GetPosition();
            position[1] = anchor[1];
            float gapSq = vector.DistanceSq(position, anchor);
            if (gapSq < nearestSq) { nearestSq = gapSq; }
        }
        return nearestSq;
    }
    override protected bool HCWithinActivation(HCXAISite site)
    {
        float radius = this.HCActivationRadius(site, false);
        return this.HCPlayerGap(site) <= radius * radius;
    }
    override protected void HCScanNearby(int now)
    {
        for (int scan = 0; scan < HC_PROXIMITY_ROWS && m_ProximityCursor < m_Policy.Sites.Count(); scan++)
        {
            int candidateIndex = m_ProximityCursor++;
            HCXAISite candidate = m_Policy.Sites[candidateIndex];
            if (!m_SiteLocalities.Contains(candidate.Id) || this.HCHasSite(candidate.Id)) { continue; }
            if (candidate.Checkpoint && !HCXAIQualification.EncountersEnabled()) { continue; }
            int localityIndex = m_SiteLocalities.Get(candidate.Id);
            HCXAILocalityCoverage coverage = m_CoverageRows.Get(m_Localities.Localities[localityIndex].Id);
            if (!coverage || now < coverage.RetryAt) { continue; }
            float radius = this.HCActivationRadius(candidate, false);
            float gap = this.HCPlayerGap(candidate);
            if (gap > radius * radius || gap >= m_ScanNearGap) { continue; }
            m_ScanNearGap = gap;
            m_ScanNearSite = candidateIndex;
        }
        if (m_ProximityCursor < m_Policy.Sites.Count()) { return; }
        m_NearSite = m_ScanNearSite;
        m_ProximityCursor = 0;
        m_ScanNearSite = -1;
        m_ScanNearGap = 1000000000;
    }
    override protected HCXAISiteState HCSurveyState(HCXAISite site)
    {
        HCXAISiteState state = m_Survey.Get(site.Id);
        if (state) { return state; }
        state = new HCXAISiteState();
        state.Site = site;
        if (m_Localities && m_SiteLocalities.Contains(site.Id))
        {
            state.LocalityId = m_Localities.Localities[m_SiteLocalities.Get(site.Id)].Id;
        }
        m_Survey.Set(site.Id, state);
        return state;
    }
    override protected HCXAISiteState HCNearbySurveyState()
    {
        HCXAISiteState nearest;
        float nearestGap = 1000000000;
        if (m_NearSite >= 0 && m_NearSite < m_Policy.Sites.Count())
        {
            HCXAISiteState candidate = this.HCSurveyState(m_Policy.Sites[m_NearSite]);
            if (!candidate.Failed && !candidate.Qualified && this.HCWithinActivation(candidate.Site))
            {
                nearest = candidate;
                nearestGap = this.HCPlayerGap(candidate.Site);
            }
        }
        for (int index = 0; index < m_States.Count() && index < 64; index++)
        {
            HCXAISiteState waiting = m_States[index];
            if (waiting.LocalityId == "" || waiting.Failed || waiting.Qualified || waiting.Patrol || !m_PolicySiteIds.Contains(waiting.Site.Id)) { continue; }
            float gap = this.HCPlayerGap(waiting.Site);
            float radius = this.HCActivationRadius(waiting.Site, false);
            if (gap > radius * radius || gap >= nearestGap) { continue; }
            nearest = waiting;
            nearestGap = gap;
        }
        return nearest;
    }
    override protected void HCStepSurvey()
    {
        if (m_SurveyCursor >= m_Policy.Sites.Count()) { return; }
        if (!this.HCTakeSiteUnits(64)) { return; }
        int nowMs = GetGame().GetTime();
        if (m_SurveyStartedMs < 0) { m_SurveyStartedMs = nowMs; }
        if (!m_SurveyBackgroundLogged && (nowMs < m_SurveyStartedMs || nowMs - m_SurveyStartedMs >= 1500000))
        {
            m_SurveyBackgroundLogged = true;
            Print("[HC Expansion AI] survey continuing in background; pending geometry retains qualification gate runtime=PENDING");
        }
        if (!this.HCSurveyReady()) { return; }
        string refusedSites;
        m_SurveyWork.HCReset(64, Math.Min(HCPerfConfig.HCGet().SliceMs, 2));
        HCXAISiteState nearby = this.HCNearbySurveyState();
        while (m_SurveyCursor < m_Policy.Sites.Count() && m_SurveyWork.HCContinue())
        {
            HCXAISiteState state = nearby;
            if (!state) { state = this.HCSurveyState(m_Policy.Sites[m_SurveyCursor]); }
            if (state.Failed || state.Qualified)
            {
                this.HCRecordRouteState(state);
                if (nearby) { nearby = null; }
                else { m_SurveyCursor++; }
                continue;
            }
            if (state.Site.Checkpoint && !HCXAIQualification.EncountersEnabled())
            {
                state.Failed = true;
                state.Reason = "checkpoint encounters disabled";
                refusedSites += " " + state.Site.Id;
                continue;
            }
            if (!state.Bound) { this.Bind(state); continue; }
            int calls = state.PathCalls;
            this.QualifyStep(state);
            if (state.PathCalls > calls) { break; }
        }
        if (refusedSites != "")
        {
            Print("[HC Expansion AI] survey refused sites=" + refusedSites + " reason=checkpoint encounters disabled runtime=PENDING");
        }
        if (m_SurveyCursor >= m_Policy.Sites.Count())
        {
            this.HCRoutesWarm();
            Print("[HC Expansion AI] survey complete qualified=" + m_QualifiedCount.ToString() + " refused=" + m_RefusedCount.ToString() + " elapsed_ms=" + (nowMs - m_SurveyStartedMs).ToString() + " runtime=PENDING");
        }
    }
    override protected void HCRecordRouteState(HCXAISiteState state)
    {
        if (state.Transient || (!state.Failed && !state.Qualified)) { return; }
        state.HCPath.Clear();
        state.AttemptPoints.Clear();
        if (!m_PolicySiteIds.Contains(state.Site.Id)) { return; }
        int result = 1;
        if (state.Failed) { result = 2; }
        int previous = m_RouteResults.Get(state.Site.Id);
        if (previous == result) { return; }
        if (previous == 1) { m_QualifiedCount--; }
        if (previous == 2) { m_RefusedCount--; }
        if (result == 1) { m_QualifiedCount++; }
        else { m_RefusedCount++; }
        m_RouteResults.Set(state.Site.Id, result);
    }
    override protected void HCRoutesWarm()
    {
        if (m_RoutesWarm || m_CachePending.Count() > 0) { return; }
        m_RoutesWarm = true;
        m_CacheStates.Clear();
        m_CachePolicy.Clear();
        m_CacheReviewIds.Clear();
        int elapsed;
        if (m_SurveyStartedMs >= 0) { elapsed = Math.Max(0, GetGame().GetTime() - m_SurveyStartedMs) / 1000; }
        Print("[HC Expansion AI] routes warm elapsed_s=" + elapsed.ToString() + " cached=" + m_CacheHits.ToString() + " requalified=" + m_Requalified.ToString() + " discarded=" + m_CacheDiscarded.ToString() + " retained=" + m_CacheRetained.ToString());
    }
    override protected void HCCacheVerdict(string siteId, bool reused)
    {
        if (!m_CachePending.Contains(siteId)) { return; }
        m_CachePending.Remove(siteId);
        if (reused) { m_CacheHits++; }
        else { m_CacheDiscarded++; }
    }
    override protected void HCCacheDiscard(HCXAIRouteRow row, string reason, string field = "")
    {
        string diagnostic = reason;
        if (field != "") { diagnostic += " field=" + field; }
        if (!m_CacheReasons.Contains(diagnostic))
        {
            m_CacheReasons.Set(diagnostic, true);
            string detail;
            if (reason == "validity_mismatch" && row.ValidityKey == "") { detail = " detail=missing_validity"; }
            // Pre-manifest (chain-v6) rows: stale by design, replaced one by one.
            if (reason == "validity_mismatch" && (field == "algorithm" || field == "manifest")) { detail = " detail=manifest_term"; }
            Print("[HC Expansion AI] route cache discarded reason=" + diagnostic + detail);
        }
        this.HCCacheVerdict(row.SiteId, false);
        this.HCRemoveRoute(row);
        this.SaveRoutes();
    }
    override protected void HCDiscardLegacyRoutes()
    {
        array<ref HCXAIRouteRow> retained = new array<ref HCXAIRouteRow>;
        int discarded = 0;
        foreach (HCXAIRouteRow row : m_Routes.Rows)
        {
            if (row.ValidityKey != "") { retained.Insert(row); continue; }
            discarded++;
            if (!m_CachePolicy.Contains(row.SiteId)) { m_CacheRetained--; }
            this.HCCacheVerdict(row.SiteId, false);
        }
        if (discarded == 0) { return; }
        m_Routes.Rows = retained;
        m_LegacyRoutesDirty = true;
        Print("[HC Expansion AI] route cache discarded reason=validity_mismatch field=policy detail=missing_validity count=" + discarded.ToString());
    }
    override protected void HCReviewCachedRoute()
    {
        if (!this.HCTakeSiteUnits(2)) { return; }
        HCWorkBudget slice = new HCWorkBudget;
        slice.HCReset(16, Math.Min(HCPerfConfig.HCGet().SliceMs, 2));
        while (m_CacheReviewCursor < m_CacheReviewIds.Count() && !m_CachePending.Contains(m_CacheReviewIds[m_CacheReviewCursor]) && slice.HCContinue()) { m_CacheReviewCursor++; }
        if (m_CacheReviewCursor >= m_CacheReviewIds.Count()) { this.HCRoutesWarm(); return; }
        string siteId = m_CacheReviewIds[m_CacheReviewCursor];
        if (!m_CachePending.Contains(siteId)) { return; }
        HCXAISiteState state = m_CacheStates.Get(siteId);
        if (!state && m_CachePolicy.Contains(siteId)) { state = this.HCSurveyState(m_CachePolicy.Get(siteId)); }
        if (state && state.Site.Checkpoint && !HCXAIQualification.EncountersEnabled())
        {
            m_CachePending.Remove(siteId);
            m_CacheRetained++;
            return;
        }
        if (state && (state.Qualified || (state.HCRouteCacheChecked && !state.HCCachedRoute)))
        {
            this.HCCacheVerdict(siteId, state.Cached);
            return;
        }
        HCXAIRouteRow row;
        if (state && state.HCRouteCacheChecked) { row = state.HCCachedRoute; }
        else
        {
            row = this.RouteRow(siteId);
            if (state) { state.HCCachedRoute = row; state.HCRouteCacheChecked = true; }
        }
        if (!row) { this.HCCacheVerdict(siteId, false); return; }
        if (!state) { this.HCCacheDiscard(row, "site_absent"); return; }
        if (state.Failed) { this.HCCacheDiscard(row, "site_failed"); return; }
        string scalarField = HCXAISiteRules.HCRouteMismatch(row, row.Key, m_RouteValidity);
        if (scalarField != "")
        {
            this.HCCacheDiscard(row, "validity_mismatch", scalarField);
            state.HCCachedRoute = null;
            return;
        }
        if (!state.Bound) { this.Bind(state); return; }
        this.QualifyStep(state, true);
    }
    override protected void StepBind()
    {
        if (!this.HCTakeSiteUnits(2)) { return; }
        HCWorkBudget slice = new HCWorkBudget;
        slice.HCReset(HCXAISiteDirector.WORK_PER_TICK, Math.Min(HCPerfConfig.HCGet().SliceMs, 2));
        int work = 0;
        while (work < HCXAISiteDirector.WORK_PER_TICK && m_Cursor < m_States.Count() && slice.HCContinue())
        {
            if (!m_States[m_Cursor].Bound && !m_States[m_Cursor].Failed) { this.Bind(m_States[m_Cursor]); }
            if (m_States[m_Cursor].Bound || m_States[m_Cursor].Failed) { m_Cursor++; }
            work++;
        }
        if (m_Cursor < m_States.Count()) { return; }
        int bound = 0;
        foreach (HCXAISiteState counted : m_States)
        {
            if (counted.Bound) { bound++; }
        }
        Print("[HC Expansion AI] sites bound: " + bound.ToString() + "/" + m_States.Count().ToString() + "; qualifying routes on the navmesh");
        m_Phase = "qualify";
        m_Cursor = 0;
    }
    override protected void Bind(HCXAISiteState state)
    {
        if (state.Bound || state.Failed) { return; }
        if (!state.Transient && !m_RoutesWarm) { m_CacheStates.Set(state.Site.Id, state); }
        if (m_Localities && !state.Transient && HCXAISiteRules.HCRoadFallback(state.Site, state.LocalityId) && !this.HCSurveyReady()) { return; }
        if (state.HCBindHash)
        {
            int partBytes = Math.Min(128, state.HCBindText.Length() - state.HCBindCursor);
            bool lastPart = state.HCBindCursor + partBytes == state.HCBindText.Length();
            string digest = HCGapcodeRouteHash.HCRoutePart(state.HCBindHash, state.HCBindText.Substring(state.HCBindCursor, partBytes), lastPart);
            state.HCBindCursor += partBytes;
            if (!lastPart) { return; }
            state.Key = digest;
            state.HCBindHash = null;
            state.HCBindText = "";
            state.Bound = true;
            return;
        }
        HCXAISite site = state.Site;
        if (site.Kind != "holdout")
        {
            foreach (vector waypoint : site.Waypoints)
            {
                state.Points.Insert(Vector(waypoint[0], GetGame().SurfaceY(waypoint[0], waypoint[2]), waypoint[2]));
            }
        }
        else
        {
            array<Object> objects = new array<Object>();
            array<CargoBase> cargos = new array<CargoBase>();
            GetGame().GetObjectsAtPosition(site.HousePosition, 10, objects, cargos);
            float best = 11;
            foreach (Object candidate : objects)
            {
                if (!candidate || candidate.GetType() != site.HouseClass) { continue; }
                float gap = vector.Distance(candidate.GetPosition(), site.HousePosition);
                if (gap < best)
                {
                    best = gap;
                    state.HouseObject = candidate;
                }
            }
            if (!state.HouseObject)
            {
                state.Failed = true;
                state.Reason = "house " + site.HouseClass + " not found at its position";
                Print("[HC Expansion AI] site " + site.Id + " not bound: " + state.Reason);
                return;
            }
            foreach (vector inner : site.LocalPoints)
            {
                state.Points.Insert(state.HouseObject.ModelToWorld(inner));
            }
            state.CacheWorld = HCXExpansionBridge.HCPlacementPosition(state.HouseObject.ModelToWorld(site.CacheLocal));
            state.CacheOrientation = state.HouseObject.GetOrientation();
        }
        if (state.Transient)
        {
            state.Key = "transient:" + state.ProposalId;
            state.Bound = true;
            return;
        }
        state.HCBindText = HCXAISiteRules.RouteText(site, m_Build);
        state.HCBindCursor = 0;
        state.HCBindHash = new HCGapcodeRouteHashState;
    }
    override protected void StepQualify()
    {
        if (!this.HCTakeSiteUnits(64)) { return; }
        HCWorkBudget slice = new HCWorkBudget;
        slice.HCReset(HCXAISiteDirector.WORK_PER_TICK, Math.Min(HCPerfConfig.HCGet().SliceMs, 2));
        int work = 0;
        while (work < HCXAISiteDirector.WORK_PER_TICK && m_Cursor < m_States.Count() && slice.HCContinue())
        {
            HCXAISiteState state = m_States[m_Cursor];
            if (!state.Bound || state.Failed || state.Qualified)
            {
                m_Cursor++;
                continue;
            }
            int callsBefore = state.PathCalls;
            this.QualifyStep(state);
            work++;
            if (state.PathCalls > callsBefore) { return; }
        }
        if (m_Cursor < m_States.Count()) { return; }
        int qualified = 0;
        foreach (HCXAISiteState counted : m_States)
        {
            if (counted.Qualified) { qualified++; }
        }
        this.HCRoutesWarm();
        Print("[HC Expansion AI] sites routes qualified: " + qualified.ToString() + "/" + m_States.Count().ToString() + " (chain-v7; cached geometry or navmesh sample + bounded FindPath chains, outdoor-first ground sampling; cache " + HCXAISiteDirector.ROUTES + " keyed by algorithm, route and build)");
        m_Phase = "create";
        m_Cursor = 0;
    }
    override protected void QualifyStep(HCXAISiteState state, bool cacheOnly = false)
    {
        if (cacheOnly && (state.Qualified || !state.HCCachedRoute || state.HCPathReady)) { this.HCCacheVerdict(state.Site.Id, state.Cached); return; }
        if (state.HCPathReady) { this.HCFinishPath(state); return; }
        AIWorld world = GetGame().GetWorld().GetAIWorld();
        if (!world)
        {
            // Transient: never a refusal and never a discard of a cached row.
            // The qualify phase retries each tick; only the non-cache path
            // gives up (uncached) after 600 postponed visits.
            state.HCAiWorldWaits++;
            if (m_AiWorldPostponed == 0) { Print("[HC Expansion AI] route postponed reason=aiworld"); }
            m_AiWorldPostponed++;
            if (!cacheOnly && state.HCAiWorldWaits > 600)
            {
                state.Failed = true;
                state.Reason = "navmesh unavailable";
                Print("[HC Expansion AI] site " + state.Site.Id + " route refused (not cached): navmesh unavailable after 600 visits; postponed=" + m_AiWorldPostponed.ToString());
            }
            return;
        }
        if (!state.HCRouteCacheChecked)
        {
            state.HCCachedRoute = this.RouteRow(state.Site.Id);
            state.HCRouteCacheChecked = true;
        }
        HCXAIRouteRow cached = state.HCCachedRoute;
        if (cached)
        {
            string cacheProblem;
            string cacheField = HCXAISiteRules.HCRouteMismatch(cached, state.Key, m_RouteValidity);
            if (cacheField != "") { cacheProblem = "validity_mismatch"; }
            else if (cached.Qualified && (!cached.Waypoints || cached.Waypoints.Count() < 2 || cached.Waypoints.Count() > HCXAISiteRules.HCMaxRouteWaypoints())) { cacheProblem = "no_geometry"; }
            if (cacheProblem == "")
            {
                if (!cached.Qualified)
                {
                    if (!this.HCTakeRouteCacheUnit()) { return; }
                    this.HCCacheVerdict(state.Site.Id, true);
                    state.Failed = true;
                    state.Reason = cached.Reason;
                    Print("[HC Expansion AI] site " + state.Site.Id + " route refused (cached for this route and build): " + cached.Reason);
                    return;
                }
                int tick = GetGame().GetTime();
                if (m_CacheSampleTick != tick) { m_CacheSampleTick = tick; m_CacheSamples = 0; }
                if (m_CacheSamples >= 4 || !this.HCTakeRouteCacheUnit()) { return; }
                m_CacheSamples++;
                vector point = cached.Waypoints[state.HCCacheCursor];
                float maxCachedLeg = m_Policy.MaxLegLength * 2 + 32;
                if (!HCXAIRules.PositionValid(point, 16000)) { cacheProblem = "waypoint_bounds"; }
                else if (state.HCCacheCursor > 0 && vector.DistanceSq(cached.Waypoints[state.HCCacheCursor - 1], point) > maxCachedLeg * maxCachedLeg) { cacheProblem = "waypoint_leg"; }
                else if (state.HCCacheCursor == cached.Waypoints.Count() - 1 && !cached.OpenRoute && state.Site.Behaviour == "LOOP" && vector.DistanceSq(point, cached.Waypoints[0]) > maxCachedLeg * maxCachedLeg) { cacheProblem = "closing_leg"; }
                else
                {
                    vector sampled = this.NavSample(point, 0.5, m_Filter);
                    if (sampled == vector.Zero || vector.Distance(sampled, point) > 0.5) { cacheProblem = "waypoint_sample"; }
                }
                if (cacheProblem == "")
                {
                    state.HCCacheCursor++;
                    if (state.HCCacheCursor < cached.Waypoints.Count()) { return; }
                    state.PatrolPoints.Copy(cached.Waypoints);
                    state.OpenRoute = cached.OpenRoute;
                    state.Qualified = true;
                    this.HCReusedRoute(state);
                    return;
                }
            }
            this.HCCacheDiscard(cached, cacheProblem, cacheField);
            state.HCCachedRoute = null;
            return;
        }
        if (cacheOnly) { this.HCCacheVerdict(state.Site.Id, false); return; }
        if (state.Sampled.Count() < state.Points.Count())
        {
            if (state.Points.Count() < 2 || state.Points.Count() > 8)
            {
                this.Refuse(state, "2..8 authored waypoints are required");
                return;
            }
            // Outdoor ground first for every kind but holdouts (their points are
            // indoors on purpose): one native sample per step, no second pass.
            if (state.Site.Kind != "holdout") { this.HCOutdoorStep(state); return; }
            vector wanted = state.Points[state.Sampled.Count()];
            {
                vector found = this.NavSample(wanted, 2, m_Filter);
                if (found == vector.Zero)
                {
                    this.Refuse(state, HCXAISiteRules.LegProblem(false, false, 0, 0, 0, 0));
                    return;
                }
                state.Sampled.Insert(found);
            }
            if (state.Sampled.Count() < state.Points.Count()) { return; }
            state.PatrolPoints.Insert(state.Sampled[0]);
            return;
        }
        int authoredCount = state.Sampled.Count();
        if (authoredCount < 2 || authoredCount > 8)
        {
            this.Refuse(state, "2..8 authored waypoints are required");
            return;
        }
        int minimum = HCXAISiteRules.RouteMinimum(state.Site.Kind);
        bool closing = state.Leg >= authoredCount - 1;
        if (closing && state.Kept < minimum && authoredCount - state.StartIndex - 1 >= minimum)
        {
            state.StartIndex++;
            state.Kept = 1;
            state.Leg = state.StartIndex;
            state.Skipped = state.StartIndex;
            state.Snapped = 0;
            state.SkippedPoints = "";
            int droppedIndex = 0;
            while (droppedIndex < state.StartIndex)
            {
                state.SkippedPoints = state.SkippedPoints + " " + droppedIndex.ToString() + HCXAISiteRules.PointText(state.Sampled[droppedIndex]);
                droppedIndex++;
            }
            state.PatrolPoints.Clear();
            state.PatrolPoints.Insert(state.Sampled[state.StartIndex]);
            state.AttemptPoints.Clear();
            state.ChainSteps = 0;
            return;
        }
        if (closing && state.Kept < minimum)
        {
            this.Refuse(state, "route minimum: kept=" + state.Kept.ToString() + " required=" + minimum.ToString() + "; " + state.Reason);
            return;
        }
        if (closing && state.Kept == 2 && state.Site.Kind != "holdout") { state.OpenRoute = true; }
        if (closing && (state.Site.Behaviour != "LOOP" || state.Closed || state.OpenRoute))
        {
            state.Qualified = true;
            state.Reason = "";
            HCXAIRouteRow passed = new HCXAIRouteRow();
            passed.Key = state.Key;
            passed.SiteId = state.Site.Id;
            passed.Qualified = true;
            passed.ValidityKey = m_RouteValidity;
            passed.OpenRoute = state.OpenRoute;
            if (state.PatrolPoints.Count() > HCXAISiteRules.HCMaxRouteWaypoints())
            {
                state.Qualified = false;
                this.Refuse(state, "route geometry exceeds cache cap");
                return;
            }
            passed.Waypoints.Copy(state.PatrolPoints);
            if (m_PolicySiteIds.Contains(state.Site.Id) && !m_RouteResults.Contains(state.Site.Id)) { m_Requalified++; }
            if (m_RouteValidity != "") { this.Remember(passed); }
            int legs = state.Kept - 1;
            if (state.Closed) { legs++; }
            string sampling = "navmesh";
            if (state.Site.Kind != "holdout") { sampling = "outdoor"; }
            string qualifiedLine = "[HC Expansion AI] site " + state.Site.Id + " route qualified: chain-v7 legs=" + legs.ToString() + " FindPath=" + state.PathCalls.ToString() + " continuations=" + state.Continuations.ToString();
            qualifiedLine = qualifiedLine + " patrol waypoints=" + state.PatrolPoints.Count().ToString() + " skipped=" + state.Skipped.ToString() + " snapped=" + state.Snapped.ToString() + " behaviour=" + HCXAISiteRules.PatrolBehaviour(state.Site.Behaviour, state.OpenRoute);
            qualifiedLine = qualifiedLine + " sampling=" + sampling + " outdoor=" + state.Outdoor.ToString() + "/" + authoredCount.ToString() + " indoor_fallback=" + state.IndoorFallback.ToString() + " skipped-points=" + state.SkippedPoints;
            Print("" + qualifiedLine);
            return;
        }
        if (state.PathCalls >= 96)
        {
            this.Refuse(state, "route search budget");
            return;
        }
        vector legFrom = state.PatrolPoints[state.PatrolPoints.Count() - 1];
        vector legTo = state.Sampled[(state.Leg + 1) % authoredCount];
        if (closing) { legTo = state.PatrolPoints[0]; }
        if (state.ChainSteps == 0)
        {
            state.ChainFrom = legFrom;
            state.ChainLength = 0;
            state.ClosestEnd = legFrom;
            state.ClosestGap = vector.Distance(legFrom, legTo);
            state.AttemptPoints.Clear();
        }
        state.HCPath.Clear();
        int nativeBegan = TickCount(0);
        bool pathFound = world.FindPath(state.ChainFrom, legTo, m_Filter, state.HCPath);
        this.HCSiteStageCost("native_path", nativeBegan);
        if (!pathFound) { state.HCPath.Clear(); }
        state.PathCalls++;
        state.ChainSteps++;
        state.HCPathReady = true;
        state.HCPathCursor = 1;
        state.HCPathLength = 0;
    }
    override protected void HCFinishPath(HCXAISiteState state)
    {
        int postBegan = TickCount(0);
        TVectorArray path = state.HCPath;
        int pathPoints = path.Count();
        int processed = 0;
        while (state.HCPathCursor < pathPoints && processed < 8)
        {
            int index = state.HCPathCursor;
            state.HCPathLength += vector.Distance(path[index - 1], path[index]);
            state.HCPathCursor++;
            processed++;
        }
        this.HCSiteStageCost("path_post", postBegan);
        if (state.HCPathCursor < pathPoints) { return; }
        state.HCPathReady = false;
        float length = state.HCPathLength;
        float endGap = 1000;
        int authoredCount = state.Sampled.Count();
        int minimum = HCXAISiteRules.RouteMinimum(state.Site.Kind);
        bool closing = state.Leg >= authoredCount - 1;
        vector legFrom = state.PatrolPoints[state.PatrolPoints.Count() - 1];
        vector legTo = state.Sampled[(state.Leg + 1) % authoredCount];
        if (closing) { legTo = state.PatrolPoints[0]; }
        vector pathEnd = state.ChainFrom;
        float advance = 0;
        if (pathPoints > 0)
        {
            pathEnd = path[pathPoints - 1];
            endGap = vector.Distance(pathEnd, legTo);
            advance = vector.Distance(state.ChainFrom, pathEnd);
            if (state.ChainSteps == 1 || endGap < state.ClosestGap)
            {
                state.ClosestGap = endGap;
                state.ClosestEnd = pathEnd;
            }
        }
        state.ChainLength = state.ChainLength + length;
        string problem = HCXAISiteRules.ChainAction(state.Site.Kind, state.ChainSteps, pathPoints, endGap, advance, state.ChainLength, vector.Distance(legFrom, legTo));
        if (closing && problem == "snap" && state.Site.Kind != "holdout" && advance >= 0.5 && state.ChainSteps < 16) { problem = "continue"; }
        if (problem == "continue")
        {
            state.AttemptPoints.Insert(pathEnd);
            state.ChainFrom = pathEnd;
            state.Continuations++;
            return;
        }
        if (closing && problem == "snap") { problem = "closing path ends short of the waypoint"; }
        if (problem != "" && problem != "snap")
        {
            state.Reason = "leg " + state.Leg.ToString() + ": " + problem + "; from=" + HCXAISiteRules.PointText(legFrom) + "; to=" + HCXAISiteRules.PointText(legTo);
            state.Reason = state.Reason + "; closest=" + HCXAISiteRules.PointText(state.ClosestEnd) + "; gap=" + state.ClosestGap.ToString() + "; steps=" + state.ChainSteps.ToString();
            state.AttemptPoints.Clear();
            state.ChainSteps = 0;
            if (closing)
            {
                state.OpenRoute = true;
                return;
            }
            int skippedIndex = state.Leg + 1;
            state.Skipped++;
            state.SkippedPoints = state.SkippedPoints + " " + skippedIndex.ToString() + HCXAISiteRules.PointText(state.Sampled[skippedIndex]);
            state.Leg++;
            if (state.Leg >= authoredCount - 1 && state.Kept < minimum && authoredCount - state.StartIndex - 1 < minimum)
            {
                this.Refuse(state, "route minimum: kept=" + state.Kept.ToString() + " required=" + minimum.ToString() + "; " + state.Reason);
            }
            return;
        }
        foreach (vector acceptedEnd : state.AttemptPoints)
        {
            state.PatrolPoints.Insert(acceptedEnd);
        }
        state.AttemptPoints.Clear();
        state.ChainSteps = 0;
        if (closing)
        {
            state.Closed = true;
            return;
        }
        if (problem == "snap") { legTo = pathEnd; }
        vector lastKept = state.PatrolPoints[state.PatrolPoints.Count() - 1];
        if (!HCXAISiteRules.SnapKeeps(lastKept, legTo))
        {
            int mergedIndex = state.Leg + 1;
            state.Skipped++;
            state.SkippedPoints = state.SkippedPoints + " " + mergedIndex.ToString() + HCXAISiteRules.PointText(state.Sampled[mergedIndex]);
            state.Leg++;
            return;
        }
        if (problem == "snap") { state.Snapped++; }
        state.PatrolPoints.Insert(legTo);
        state.Kept++;
        state.Leg++;
    }
    override protected vector NavSample(vector wanted, float radius, PGFilter filter)
    {
        AIWorld world = GetGame().GetWorld().GetAIWorld();
        if (!world) { return vector.Zero; }
        vector found = wanted;
        int sampleBegan = TickCount(0);
        bool sampled = world.SampleNavmeshPosition(wanted, radius, filter, found);
        this.HCSiteStageCost("native_sample", sampleBegan);
        if (!sampled) { return vector.Zero; }
        return found;
    }
    override protected vector GroundSample(vector probe, float radius)
    {
        vector found = this.NavSample(probe, radius, m_OutdoorFilter);
        if (found == vector.Zero) { return vector.Zero; }
        if (Math.AbsFloat(found[1] - GetGame().SurfaceY(found[0], found[2])) > 2) { return vector.Zero; }
        return found;
    }
    // Samples the next authored point of a non-holdout site, one native sample
    // per step: centre probe radius 16, then four 12 m probes radius 8 (best
    // horizontal gap), all on the outdoor filter within 2 m of the surface;
    // when none lands outdoors, one primary-filter sample (radius 12) is the
    // fallback and is counted as indoor_fallback.
    override protected void HCOutdoorStep(HCXAISiteState state)
    {
        int outdoorBegan = TickCount(0);
        int index = state.Sampled.Count();
        vector wanted = state.Points[index];
        vector found = vector.Zero;
        bool pointDone = false;
        if (state.HCOutdoorProbe == 0)
        {
            found = this.GroundSample(wanted, 16);
            if (found == vector.Zero) { state.HCOutdoorProbe = 1; }
            else { pointDone = true; state.Outdoor++; }
        }
        else if (state.HCOutdoorProbe <= 4)
        {
            float dx = 0;
            float dz = 0;
            if (state.HCOutdoorProbe == 1) { dx = 12; }
            if (state.HCOutdoorProbe == 2) { dx = -12; }
            if (state.HCOutdoorProbe == 3) { dz = 12; }
            if (state.HCOutdoorProbe == 4) { dz = -12; }
            float px = wanted[0] + dx;
            float pz = wanted[2] + dz;
            vector candidate = this.GroundSample(Vector(px, GetGame().SurfaceY(px, pz), pz), 8);
            if (candidate != vector.Zero)
            {
                float gap = vector.Distance(Vector(candidate[0], 0, candidate[2]), Vector(wanted[0], 0, wanted[2]));
                if (gap < state.HCOutdoorBestGap) { state.HCOutdoorBestGap = gap; state.HCOutdoorBest = candidate; }
            }
            state.HCOutdoorProbe++;
            if (state.HCOutdoorProbe > 4 && state.HCOutdoorBest != vector.Zero)
            {
                found = state.HCOutdoorBest;
                pointDone = true;
                state.Outdoor++;
            }
        }
        else
        {
            found = this.NavSample(wanted, 12, m_Filter);
            if (found == vector.Zero)
            {
                this.HCSiteStageCost("outdoor_sample", outdoorBegan);
                this.Refuse(state, HCXAISiteRules.LegProblem(false, false, 0, 0, 0, 0));
                return;
            }
            pointDone = true;
            state.IndoorFallback++;
        }
        this.HCSiteStageCost("outdoor_sample", outdoorBegan);
        if (!pointDone) { return; }
        state.HCOutdoorProbe = 0;
        state.HCOutdoorBest = vector.Zero;
        state.HCOutdoorBestGap = 1000;
        state.Sampled.Insert(found);
        if (state.Sampled.Count() >= state.Points.Count()) { state.PatrolPoints.Insert(state.Sampled[0]); }
    }
    override protected void Refuse(HCXAISiteState state, string reason)
    {
        string text = reason;
        state.Failed = true;
        state.Reason = text;
        HCXAIRouteRow failed = new HCXAIRouteRow();
        failed.Key = state.Key;
        failed.SiteId = state.Site.Id;
        failed.Qualified = false;
        failed.ValidityKey = m_RouteValidity;
        failed.Reason = text;
        if (m_RouteValidity != "") { this.Remember(failed); }
        Print("[HC Expansion AI] site " + state.Site.Id + " route refused: " + text);
    }
    override protected void HCReusedRoute(HCXAISiteState state)
    {
        state.Cached = true;
        this.HCCacheVerdict(state.Site.Id, true);
        HCModuleReadiness.HCUse("optional-expansion-human-ai", "route_cache");
    }
    override string HCPrepareRingSpawn(HCXAISitePatrol patrol)
    {
        if (!m_Policy || m_Phase != "run") { return "sites not running"; }
        if (patrol.HCHasGroup() || patrol.m_HCTransient || patrol.m_HCKind == "holdout") { return ""; }
        vector original = patrol.m_Position;
        float minimum = HCPerceptionRing.HCSpawnMin();
        if (this.NearestPlayer(original) >= minimum && !GetGame().SurfaceIsSea(original[0], original[2]) && !GetGame().SurfaceIsPond(original[0], original[2])) { return ""; }
        this.HCRefreshPlayers();
        array<vector> ringObservers = new array<vector>();
        array<Man> ringPlayers = m_Players;
        vector centre = vector.Zero;
        float nearestGap = -1;
        foreach (Man ringPlayer : ringPlayers)
        {
            if (!ringPlayer || !ringPlayer.GetIdentity() || !ringPlayer.IsAlive()) { continue; }
            vector observerPoint = ringPlayer.GetPosition();
            ringObservers.Insert(observerPoint);
            float observerGap = vector.Distance(observerPoint, original);
            if (nearestGap < 0 || observerGap < nearestGap) { centre = observerPoint; nearestGap = observerGap; }
        }
        if (ringObservers.Count() == 0) { return "spawn_ring_search_unavailable"; }
        int ringNowMs = GetGame().GetTime();
        if (ringNowMs < patrol.m_HCRingRetryMs || ringNowMs < m_RingNextProbeMs) { return "spawn_ring_work_pending"; }
        if (!HCServer.HCTickWork().HCTakeAISlice(HCUnitBudget.HC_AI_RING, HCUnitBudget.HC_WORK_AI_SITES, 64)) { return "spawn_ring_work_pending"; }
        m_RingNextProbeMs = ringNowMs + 1000;
        patrol.m_HCRingRetryMs = ringNowMs + Math.Max(5000, m_States.Count() * 2000);
        HCPerceptionRingPick pick = HCPerceptionRing.HCFindLand(centre, m_RingDegrees, ringObservers, m_RingCandidates);
        if (pick.Reason != "")
        {
            m_RingDegrees += 180.0 / m_RingCandidates;
            if (m_RingDegrees >= 360.0) { m_RingDegrees -= 360.0; }
            return pick.Reason;
        }
        HCServer.HCTickWork().HCCharge(1);
        string ringProblem = this.HCRingPickProblem(pick, centre, ringObservers, original);
        if (ringProblem != "")
        {
            m_RingDegrees = m_RingDegrees + 360.0 * (pick.Attempts + 0.5) / m_RingCandidates;
            while (m_RingDegrees >= 360.0) { m_RingDegrees = m_RingDegrees - 360.0; }
            return ringProblem;
        }
        patrol.m_HCRingRetryMs = 0;
        patrol.m_Position = m_RingGround;
        m_RelocatedTotal++;
        if (!patrol.m_HCRingLogged)
        {
            patrol.m_HCRingLogged = true;
            Print("[HC Expansion AI] site " + patrol.m_HCSiteId + " spawn ring relocated; runtime=PENDING");
        }
        return "";
    }
    override protected string HCRingPickProblem(HCPerceptionRingPick pick, vector centre, array<vector> ringObservers, vector original)
    {
        vector ground = this.GroundSample(pick.Position, HCPerceptionRing.HCGet().SpawnMarginMeters);
        if (ground == vector.Zero || !HCPerceptionRing.HCClearOfObservers(ground, ringObservers)) { return "spawn_ring_ground_unavailable"; }
        if (vector.Distance(ground, centre) > HCPerceptionRing.HCSpawnMax()) { return "spawn_ring_ground_outside_band"; }
        string routeProblem = this.HCRingRouteProblem(ground, original);
        if (routeProblem != "") { return routeProblem; }
        string observerProblem = this.MemberProblemFor(ground);
        if (observerProblem != "") { return observerProblem; }
        m_RingGround = ground;
        return "";
    }
    override protected string HCRingRouteProblem(vector start, vector target)
    {
        AIWorld ringWorld = GetGame().GetWorld().GetAIWorld();
        if (!ringWorld) { return "spawn_ring_navmesh_unavailable"; }
        TVectorArray ringPath = new TVectorArray();
        HCServer.HCTickWork().HCCharge(1);
        int ringBegan = TickCount(0);
        bool ringFound = ringWorld.FindPath(start, target, m_Filter, ringPath);
        this.HCSiteStageCost("ring_native_path", ringBegan);
        if (!ringFound || ringPath.Count() < 2) { return "spawn_ring_route_unreachable"; }
        if (vector.DistanceSq(ringPath[ringPath.Count() - 1], target) > 6.25) { return "spawn_ring_route_incomplete"; }
        return "";
    }
}
