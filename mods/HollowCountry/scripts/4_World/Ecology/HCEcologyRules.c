// Native scripts-1.30.164289: 1_Core/proto/EnScript.c:902/917 map Set/Contains (hash lookup).
// Pure scheduling policy only: this source is intentionally unregistered and
// performs no entity, population, command, transform, or persistence mutation.
//
// Native API assumption, inspected against scripts 1.30.164289: DayZAnimal and
// DayZInfected expose native input controllers; AIWorld exposes FindPath with a
// PGFilter.  The public controllers expose movement overrides, but no supported
// resource-seeking command or sensory-resource query.  Therefore this policy
// accepts caller-observed facts plus explicit capability/path results and emits
// proposals only.  Remaining integration must bind stable native entity IDs,
// collect actual perception/resource evidence, validate a native path, prefer
// native population behaviour, submit a directive, and report acceptance to
// Commit.  It must not manufacture perception or movement success.
//
// Consumer contract: serialize Schedule -> native submission -> Commit using
// the same captured tick and unchanged policy/context. Freeze each dispatched
// tuple for its receipt. No overlapping or asynchronous proposal batches.
// SessionId must identify a fresh native world/session lifetime.
// One actor and zone per proposal batch is the only resource admission here:
// no cross-batch occupancy, stock quantity or native resource capacity is known.
// Assignment retention bounds bookkeeping, not resource occupancy. Do not hook
// this policy until a native provider can enforce its actual capacity contract.

class HCEcologyRules
{
	static bool TextValid(string value)
	{
		return value.Length() > 0 && value.Length() <= HCEcologyLimits.TEXT;
	}

	static bool DeadlineFits(int nowMs, int holdMs, int cooldownMs)
	{
		if (nowMs < 0 || nowMs > HCEcologyLimits.INT_MAX || holdMs < 0 || cooldownMs < 0)
		{
			return false;
		}
		if (holdMs > HCEcologyLimits.INT_MAX - nowMs)
		{
			return false;
		}
		return cooldownMs <= HCEcologyLimits.INT_MAX - nowMs - holdMs;
	}

	static bool PopulationValid(int value)
	{
		return value == HCEcologyPopulation.ANIMAL || value == HCEcologyPopulation.INFECTED;
	}

	static bool ResourceValid(int value)
	{
		return value == HCEcologyResource.FOOD || value == HCEcologyResource.WATER;
	}

	static bool HintValid(HCEcologyRouteHint hint)
	{
		if (!hint || !TextValid(hint.Id) || !TextValid(hint.ZoneId) || !TextValid(hint.Species))
		{
			return false;
		}
		if (!PopulationValid(hint.PopulationKind) || !ResourceValid(hint.ResourceKind))
		{
			return false;
		}
		return hint.StartsAtMs >= 0 && hint.EndsAtMs > hint.StartsAtMs;
	}

	static bool PolicyValid(HCEcologyPolicy policy)
	{
		if (!policy || policy.SchemaVersion != 1 || !policy.Enabled)
		{
			return false;
		}
		if (!TextValid(policy.WorldName) || !TextValid(policy.SessionId) || !policy.RouteHints)
		{
			return false;
		}
		if (policy.MaxObservationAgeMs <= 0 || policy.MaxZones <= 0 || policy.MaxActors <= 0)
		{
			return false;
		}
		if (policy.MaxActors > HCEcologyLimits.ACTORS || policy.MaxZones > HCEcologyLimits.ZONES || policy.MaxDirectives > HCEcologyLimits.DIRECTIVES)
		{
			return false;
		}
		if (policy.MaxDirectives <= 0 || policy.MaxDirectives > policy.MaxZones || policy.MaxDirectives > policy.MaxActors)
		{
			return false;
		}
		if (policy.HysteresisMs < 0 || policy.CooldownMs < 0)
		{
			return false;
		}
		if (policy.RouteHints.Count() > policy.MaxZones || policy.RouteHints.Count() > HCEcologyLimits.HINTS)
		{
			return false;
		}
		int i = 0;
		map<string, bool> hintIds = new map<string, bool>;
		while (i < policy.RouteHints.Count())
		{
			HCEcologyRouteHint hint = policy.RouteHints.Get(i);
			if (!HintValid(hint))
			{
				return false;
			}
			if (hintIds.Contains(hint.Id)) { return false; }
			hintIds.Set(hint.Id, true);
			i++;
		}
		return true;
	}

	static bool ActorDataValid(HCEcologyActorObservation actor, int nowMs)
	{
		if (!actor || !TextValid(actor.Id) || !TextValid(actor.Species) || !actor.EligibleResources)
		{
			return false;
		}
		if (actor.EligibleResources.Count() > HCEcologyLimits.RESOURCES)
		{
			return false;
		}
		if (!PopulationValid(actor.PopulationKind) || actor.ObservedAtMs < 0 || actor.ObservedAtMs > nowMs)
		{
			return false;
		}
		int i = 0;
		while (i < actor.EligibleResources.Count())
		{
			if (!ResourceValid(actor.EligibleResources.Get(i)))
			{
				return false;
			}
			i++;
		}
		return true;
	}

	static bool ZoneDataValid(HCEcologyZoneObservation zone, int nowMs)
	{
		if (!zone || !TextValid(zone.Id) || !zone.EligibleSpecies)
		{
			return false;
		}
		if (zone.EligibleSpecies.Count() > HCEcologyLimits.SPECIES)
		{
			return false;
		}
		if (!PopulationValid(zone.PopulationKind) || !ResourceValid(zone.ResourceKind))
		{
			return false;
		}
		if (zone.ObservedAtMs < 0 || zone.ObservedAtMs > nowMs || zone.ExpiresAtMs < zone.ObservedAtMs)
		{
			return false;
		}
		int i = 0;
		while (i < zone.EligibleSpecies.Count())
		{
			if (!TextValid(zone.EligibleSpecies.Get(i)))
			{
				return false;
			}
			i++;
		}
		return true;
	}

	static bool StateDataValid(HCEcologyState state, HCEcologyPolicy policy)
	{
		if (!state || !state.Assignments || state.WorldName != policy.WorldName || state.SessionId != policy.SessionId)
		{
			return false;
		}
		if (state.LastNowMs < 0 || state.LastObservationMs < 0 || state.NextActorIndex < 0 || state.NextZoneIndex < 0)
		{
			return false;
		}
		if (state.Assignments.Count() > policy.MaxActors)
		{
			return false;
		}
		int i = 0;
		map<string, bool> assignmentIds = new map<string, bool>;
		while (i < state.Assignments.Count())
		{
			HCEcologyAssignment assignment = state.Assignments.Get(i);
			if (!assignment || !TextValid(assignment.ActorId) || !TextValid(assignment.ZoneId))
			{
				return false;
			}
			if (assignment.IssuedAtMs < 0 || assignment.HoldUntilMs < assignment.IssuedAtMs || assignment.CooldownUntilMs < assignment.HoldUntilMs)
			{
				return false;
			}
			if (assignmentIds.Contains(assignment.ActorId)) { return false; }
			assignmentIds.Set(assignment.ActorId, true);
			i++;
		}
		return true;
	}

	static bool BatchValid(HCEcologyObservationBatch batch, HCEcologyPolicy policy, int nowMs)
	{
		if (!batch || !batch.Actors || !batch.Zones)
		{
			return false;
		}
		if (batch.WorldName != policy.WorldName || batch.SessionId != policy.SessionId)
		{
			return false;
		}
		if (nowMs < 0 || batch.ObservedAtMs < 0 || batch.ObservedAtMs > nowMs)
		{
			return false;
		}
		if (nowMs - batch.ObservedAtMs > policy.MaxObservationAgeMs)
		{
			return false;
		}
		if (batch.Actors.Count() > policy.MaxActors || batch.Zones.Count() > policy.MaxZones)
		{
			return false;
		}
		int i = 0;
		map<string, bool> actorIds = new map<string, bool>;
		while (i < batch.Actors.Count())
		{
			HCEcologyActorObservation actor = batch.Actors.Get(i);
			if (!ActorDataValid(actor, nowMs))
			{
				return false;
			}
			if (actorIds.Contains(actor.Id)) { return false; }
			actorIds.Set(actor.Id, true);
			i++;
		}
		i = 0;
		map<string, bool> zoneIds = new map<string, bool>;
		while (i < batch.Zones.Count())
		{
			HCEcologyZoneObservation zone = batch.Zones.Get(i);
			if (!ZoneDataValid(zone, nowMs))
			{
				return false;
			}
			if (zoneIds.Contains(zone.Id)) { return false; }
			zoneIds.Set(zone.Id, true);
			i++;
		}
		return true;
	}

	static bool Fresh(int observedAtMs, int nowMs, int maxAgeMs)
	{
		return observedAtMs <= nowMs && nowMs - observedAtMs <= maxAgeMs;
	}

	static bool ProviderSupports(HCEcologyCapabilities capabilities, int populationKind)
	{
		if (!capabilities || !capabilities.IsServerAuthority || !capabilities.ProviderAvailable)
		{
			return false;
		}
		if (populationKind == HCEcologyPopulation.ANIMAL)
		{
			return capabilities.SupportsAnimalNavigation;
		}
		return capabilities.SupportsInfectedNavigation;
	}

	static HCEcologyAssignment FindAssignment(HCEcologyState state, string actorId)
	{
		int i = 0;
		while (i < state.Assignments.Count())
		{
			if (state.Assignments.Get(i).ActorId == actorId)
			{
				return state.Assignments.Get(i);
			}
			i++;
		}
		return null;
	}

	static bool SelectedActor(array<ref HCEcologyDirective> directives, string actorId)
	{
		int i = 0;
		while (i < directives.Count())
		{
			if (directives.Get(i).ActorId == actorId)
			{
				return true;
			}
			i++;
		}
		return false;
	}

	static bool SelectedZone(array<ref HCEcologyDirective> directives, string zoneId)
	{
		int i = 0;
		while (i < directives.Count())
		{
			if (directives.Get(i).ZoneId == zoneId)
			{
				return true;
			}
			i++;
		}
		return false;
	}

	static bool ActorReady(HCEcologyActorObservation actor, HCEcologyState state, HCEcologyPolicy policy, HCEcologyCapabilities capabilities, int nowMs)
	{
		if (!actor.Alive || !actor.NativeNavigationAvailable || !Fresh(actor.ObservedAtMs, nowMs, policy.MaxObservationAgeMs))
		{
			return false;
		}
		if (!ProviderSupports(capabilities, actor.PopulationKind))
		{
			return false;
		}
		HCEcologyAssignment assignment = FindAssignment(state, actor.Id);
		return !assignment || (nowMs > assignment.IssuedAtMs && nowMs >= assignment.CooldownUntilMs);
	}

	static bool ZoneReady(HCEcologyZoneObservation zone, HCEcologyPolicy policy, int nowMs)
	{
		if (!Fresh(zone.ObservedAtMs, nowMs, policy.MaxObservationAgeMs))
		{
			return false;
		}
		if (zone.Depleted || !zone.ReachabilityKnown || !zone.NativeReachable)
		{
			return false;
		}
		return zone.ExpiresAtMs > nowMs;
	}

	static bool Compatible(HCEcologyActorObservation actor, HCEcologyZoneObservation zone)
	{
		if (actor.PopulationKind != zone.PopulationKind)
		{
			return false;
		}
		if (actor.EligibleResources.Find(zone.ResourceKind) < 0)
		{
			return false;
		}
		return zone.EligibleSpecies.Find(actor.Species) >= 0;
	}

	static string ActiveHint(HCEcologyPolicy policy, HCEcologyActorObservation actor, HCEcologyZoneObservation zone, int nowMs)
	{
		int i = 0;
		while (i < policy.RouteHints.Count())
		{
			HCEcologyRouteHint hint = policy.RouteHints.Get(i);
			if (hint.ZoneId == zone.Id && hint.PopulationKind == actor.PopulationKind && hint.ResourceKind == zone.ResourceKind)
			{
				if (hint.Species == actor.Species && nowMs >= hint.StartsAtMs && nowMs < hint.EndsAtMs)
				{
					return hint.Id;
				}
			}
			i++;
		}
		return "";
	}

	static int Schedule(HCEcologyState state, HCEcologyPolicy policy, HCEcologyObservationBatch batch, HCEcologyCapabilities capabilities, int nowMs, out array<ref HCEcologyDirective> directives)
	{
		if (!directives)
		{
			return HCEcologyCode.INVALID;
		}
		directives.Clear();
		if (!PolicyValid(policy) || !StateDataValid(state, policy) || !BatchValid(batch, policy, nowMs))
		{
			return HCEcologyCode.INVALID;
		}
		if (nowMs < state.LastNowMs)
		{
			return HCEcologyCode.INVALID;
		}
		if (batch.ObservedAtMs < state.LastObservationMs)
		{
			return HCEcologyCode.INVALID;
		}
		if (!capabilities || !capabilities.IsServerAuthority || !capabilities.ProviderAvailable)
		{
			return HCEcologyCode.OK;
		}
		int actorCount = batch.Actors.Count();
		int zoneCount = batch.Zones.Count();
		if (actorCount == 0 || zoneCount == 0)
		{
			return HCEcologyCode.OK;
		}
		if (!DeadlineFits(nowMs, policy.HysteresisMs, policy.CooldownMs))
		{
			return HCEcologyCode.INVALID;
		}
		int holdUntilMs = nowMs + policy.HysteresisMs;
		int cooldownUntilMs = holdUntilMs + policy.CooldownMs;
		if (holdUntilMs < nowMs || cooldownUntilMs < holdUntilMs)
		{
			return HCEcologyCode.INVALID;
		}
		int zoneCursor = state.NextZoneIndex % zoneCount;
		int actorCursor = state.NextActorIndex % actorCount;
		int actorStep = 0;
		int newAssignments = 0;
		while (actorStep < actorCount && directives.Count() < policy.MaxDirectives)
		{
			int actorIndex = (actorCursor + actorStep) % actorCount;
			HCEcologyActorObservation actor = batch.Actors.Get(actorIndex);
			HCEcologyAssignment prior = FindAssignment(state, actor.Id);
			bool capacity = prior != null || state.Assignments.Count() + newAssignments < policy.MaxActors;
			if (capacity && ActorReady(actor, state, policy, capabilities, nowMs) && !SelectedActor(directives, actor.Id))
			{
				int zoneStep = 0;
				bool found = false;
				while (zoneStep < zoneCount && !found)
				{
					int zoneIndex = (zoneCursor + zoneStep) % zoneCount;
					HCEcologyZoneObservation zone = batch.Zones.Get(zoneIndex);
					if (ZoneReady(zone, policy, nowMs) && Compatible(actor, zone) && !SelectedZone(directives, zone.Id))
					{
						HCEcologyDirective directive = new HCEcologyDirective();
						directive.WorldName = policy.WorldName;
						directive.SessionId = policy.SessionId;
						directive.ActorId = actor.Id;
						directive.ZoneId = zone.Id;
						directive.PopulationKind = actor.PopulationKind;
						directive.ResourceKind = zone.ResourceKind;
						directive.RouteHintId = ActiveHint(policy, actor, zone, nowMs);
						directive.ObservationAtMs = batch.ObservedAtMs;
						directive.IssuedAtMs = nowMs;
						directive.HoldUntilMs = holdUntilMs;
						directive.CooldownUntilMs = cooldownUntilMs;
						directive.NextActorIndex = (actorIndex + 1) % actorCount;
						directive.NextZoneIndex = (zoneIndex + 1) % zoneCount;
						directives.Insert(directive);
						if (!prior)
						{
							newAssignments++;
						}
						zoneCursor = directive.NextZoneIndex;
						found = true;
					}
					zoneStep++;
				}
			}
			actorStep++;
		}
		return HCEcologyCode.OK;
	}

	static bool DirectiveValid(HCEcologyDirective directive, HCEcologyPolicy policy, int nowMs)
	{
		if (!DeadlineFits(nowMs, policy.HysteresisMs, policy.CooldownMs))
		{
			return false;
		}
		if (!directive || !TextValid(directive.ActorId) || !TextValid(directive.ZoneId))
		{
			return false;
		}
		if (directive.WorldName != policy.WorldName || directive.SessionId != policy.SessionId)
		{
			return false;
		}
		if (directive.RouteHintId.Length() > HCEcologyLimits.TEXT)
		{
			return false;
		}
		if (!PopulationValid(directive.PopulationKind) || !ResourceValid(directive.ResourceKind))
		{
			return false;
		}
		if (directive.ObservationAtMs < 0 || directive.ObservationAtMs > nowMs)
		{
			return false;
		}
		if (nowMs - directive.ObservationAtMs > policy.MaxObservationAgeMs)
		{
			return false;
		}
		if (directive.IssuedAtMs != nowMs || directive.HoldUntilMs != nowMs + policy.HysteresisMs)
		{
			return false;
		}
		if (directive.NextActorIndex < 0 || directive.NextActorIndex >= policy.MaxActors || directive.NextZoneIndex < 0 || directive.NextZoneIndex >= policy.MaxZones)
		{
			return false;
		}
		return directive.CooldownUntilMs == nowMs + policy.HysteresisMs + policy.CooldownMs;
	}

	static HCEcologyReceipt MakeReceipt(HCEcologyDirective directive, bool accepted)
	{
		if (!directive)
		{
			return null;
		}
		HCEcologyReceipt receipt = new HCEcologyReceipt();
		receipt.WorldName = directive.WorldName;
		receipt.SessionId = directive.SessionId;
		receipt.ActorId = directive.ActorId;
		receipt.ZoneId = directive.ZoneId;
		receipt.PopulationKind = directive.PopulationKind;
		receipt.ResourceKind = directive.ResourceKind;
		receipt.RouteHintId = directive.RouteHintId;
		receipt.ObservationAtMs = directive.ObservationAtMs;
		receipt.IssuedAtMs = directive.IssuedAtMs;
		receipt.HoldUntilMs = directive.HoldUntilMs;
		receipt.CooldownUntilMs = directive.CooldownUntilMs;
		receipt.NextActorIndex = directive.NextActorIndex;
		receipt.NextZoneIndex = directive.NextZoneIndex;
		receipt.Accepted = accepted;
		return receipt;
	}

	static bool ReceiptMatches(HCEcologyReceipt receipt, HCEcologyDirective directive)
	{
		if (!receipt || !directive)
		{
			return false;
		}
		if (receipt.WorldName != directive.WorldName)
		{
			return false;
		}
		if (receipt.SessionId != directive.SessionId)
		{
			return false;
		}
		if (receipt.ActorId != directive.ActorId)
		{
			return false;
		}
		if (receipt.ZoneId != directive.ZoneId)
		{
			return false;
		}
		if (receipt.PopulationKind != directive.PopulationKind)
		{
			return false;
		}
		if (receipt.ResourceKind != directive.ResourceKind)
		{
			return false;
		}
		if (receipt.RouteHintId != directive.RouteHintId)
		{
			return false;
		}
		if (receipt.ObservationAtMs != directive.ObservationAtMs)
		{
			return false;
		}
		if (receipt.IssuedAtMs != directive.IssuedAtMs)
		{
			return false;
		}
		if (receipt.HoldUntilMs != directive.HoldUntilMs)
		{
			return false;
		}
		if (receipt.CooldownUntilMs != directive.CooldownUntilMs)
		{
			return false;
		}
		if (receipt.NextActorIndex != directive.NextActorIndex)
		{
			return false;
		}
		if (receipt.NextZoneIndex != directive.NextZoneIndex)
		{
			return false;
		}
		return true;
	}

	static int Commit(HCEcologyState state, HCEcologyPolicy policy, array<ref HCEcologyDirective> directives, array<ref HCEcologyReceipt> receipts, int nowMs, HCEcologyCapabilities capabilities)
	{
		if (!PolicyValid(policy) || !StateDataValid(state, policy) || !directives || !receipts)
		{
			return HCEcologyCode.INVALID;
		}
		if (!capabilities || !capabilities.IsServerAuthority || !capabilities.ProviderAvailable)
		{
			return HCEcologyCode.INVALID;
		}
		if (!DeadlineFits(nowMs, 0, 0) || nowMs < state.LastNowMs || directives.Count() > policy.MaxDirectives || receipts.Count() != directives.Count())
		{
			return HCEcologyCode.INVALID;
		}
		int i = 0;
		int newAssignments = 0;
		int confirmed = 0;
		bool rejected = false;
		int observationAtMs = state.LastObservationMs;
		map<string, bool> directiveActors = new map<string, bool>;
		map<string, bool> directiveZones = new map<string, bool>;
		while (i < directives.Count())
		{
			HCEcologyDirective directive = directives.Get(i);
			if (!DirectiveValid(directive, policy, nowMs) || !ProviderSupports(capabilities, directive.PopulationKind))
			{
				return HCEcologyCode.INVALID;
			}
			HCEcologyReceipt receipt = receipts.Get(i);
			if (!ReceiptMatches(receipt, directive))
			{
				return HCEcologyCode.INVALID;
			}
			if (receipt.Accepted)
			{
				confirmed++;
			}
			else
			{
				rejected = true;
			}
			if (directive.ObservationAtMs < state.LastObservationMs)
			{
				return HCEcologyCode.INVALID;
			}
			if (i == 0)
			{
				observationAtMs = directive.ObservationAtMs;
			}
			if (directive.ObservationAtMs != observationAtMs)
			{
				return HCEcologyCode.INVALID;
			}
			HCEcologyAssignment prior = FindAssignment(state, directive.ActorId);
			// Reject repeated receipts and proposals that bypass an existing
			// hold/cooldown. Validate the entire batch before changing state.
			if (prior && (nowMs <= prior.IssuedAtMs || nowMs < prior.CooldownUntilMs))
			{
				return HCEcologyCode.INVALID;
			}
			if (!prior && receipt.Accepted)
			{
				newAssignments++;
			}
			if (directiveActors.Contains(directive.ActorId) || directiveZones.Contains(directive.ZoneId)) { return HCEcologyCode.INVALID; }
			directiveActors.Set(directive.ActorId, true);
			directiveZones.Set(directive.ZoneId, true);
			i++;
		}
		if (state.Assignments.Count() + newAssignments > policy.MaxActors)
		{
			return HCEcologyCode.INVALID;
		}
		if (confirmed == 0 && rejected)
		{
			return HCEcologyCode.NATIVE_REJECTED;
		}
		i = 0;
		while (i < directives.Count())
		{
			if (!receipts.Get(i).Accepted)
			{
				i++;
				continue;
			}
			HCEcologyDirective accepted = directives.Get(i);
			HCEcologyAssignment assignment = FindAssignment(state, accepted.ActorId);
			if (!assignment)
			{
				assignment = new HCEcologyAssignment();
				state.Assignments.Insert(assignment);
			}
			assignment.ActorId = accepted.ActorId;
			assignment.ZoneId = accepted.ZoneId;
			assignment.IssuedAtMs = accepted.IssuedAtMs;
			assignment.HoldUntilMs = accepted.HoldUntilMs;
			assignment.CooldownUntilMs = accepted.CooldownUntilMs;
			state.NextActorIndex = accepted.NextActorIndex;
			state.NextZoneIndex = accepted.NextZoneIndex;
			i++;
		}
		state.LastNowMs = nowMs;
		state.LastObservationMs = observationAtMs;
		if (rejected)
		{
			return HCEcologyCode.NATIVE_REJECTED;
		}
		return HCEcologyCode.OK;
	}

	// Retirement is explicit, atomic and bounded. Neither elapsed time alone
	// nor absence from a partial batch releases an assignment slot. Cooldown
	// must finish even when the provider observes an earlier native ending.
	static int Reconcile(HCEcologyState state, HCEcologyPolicy policy, array<ref HCEcologyRetirementReceipt> receipts, int nowMs, HCEcologyCapabilities capabilities)
	{
		if (!PolicyValid(policy) || !StateDataValid(state, policy) || !receipts)
		{
			return HCEcologyCode.INVALID;
		}
		if (!capabilities || !capabilities.IsServerAuthority || !capabilities.ProviderAvailable)
		{
			return HCEcologyCode.INVALID;
		}
		if (!DeadlineFits(nowMs, 0, 0) || nowMs < state.LastNowMs || receipts.Count() > policy.MaxActors)
		{
			return HCEcologyCode.INVALID;
		}
		int i = 0;
		int observationAtMs = state.LastObservationMs;
		map<string, bool> retiredActors = new map<string, bool>;
		while (i < receipts.Count())
		{
			HCEcologyRetirementReceipt receipt = receipts.Get(i);
			if (!receipt || receipt.WorldName != policy.WorldName || receipt.SessionId != policy.SessionId)
			{
				return HCEcologyCode.INVALID;
			}
			if (!TextValid(receipt.ActorId) || !TextValid(receipt.ZoneId) || !receipt.NativeDirectiveEnded)
			{
				return HCEcologyCode.INVALID;
			}
			HCEcologyAssignment assignment = FindAssignment(state, receipt.ActorId);
			if (!assignment || receipt.ZoneId != assignment.ZoneId || receipt.AssignmentIssuedAtMs != assignment.IssuedAtMs)
			{
				return HCEcologyCode.INVALID;
			}
			if (nowMs <= assignment.IssuedAtMs || nowMs < assignment.CooldownUntilMs)
			{
				return HCEcologyCode.INVALID;
			}
			if (receipt.ObservedAtMs < assignment.IssuedAtMs || !Fresh(receipt.ObservedAtMs, nowMs, policy.MaxObservationAgeMs))
			{
				return HCEcologyCode.INVALID;
			}
			if (retiredActors.Contains(receipt.ActorId)) { return HCEcologyCode.INVALID; }
			retiredActors.Set(receipt.ActorId, true);
			if (receipt.ObservedAtMs > observationAtMs)
			{
				observationAtMs = receipt.ObservedAtMs;
			}
			i++;
		}
		if (receipts.Count() == 0)
		{
			return HCEcologyCode.OK;
		}
		array<ref HCEcologyAssignment> retained = new array<ref HCEcologyAssignment>();
		i = 0;
		while (i < state.Assignments.Count())
		{
			HCEcologyAssignment candidate = state.Assignments.Get(i);
			if (!retiredActors.Contains(candidate.ActorId))
			{
				retained.Insert(candidate);
			}
			i++;
		}
		state.Assignments = retained;
		state.LastNowMs = nowMs;
		state.LastObservationMs = observationAtMs;
		return HCEcologyCode.OK;
	}
}
