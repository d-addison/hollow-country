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

class HCEcologyRules
{
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
		if (!hint || hint.Id == "" || hint.ZoneId == "" || hint.Species == "")
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
		if (policy.WorldName == "" || policy.SessionId == "" || !policy.RouteHints)
		{
			return false;
		}
		if (policy.MaxObservationAgeMs <= 0 || policy.MaxZones <= 0 || policy.MaxActors <= 0)
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
		if (policy.RouteHints.Count() > policy.MaxZones)
		{
			return false;
		}
		int i = 0;
		while (i < policy.RouteHints.Count())
		{
			HCEcologyRouteHint hint = policy.RouteHints.Get(i);
			if (!HintValid(hint))
			{
				return false;
			}
			int j = i + 1;
			while (j < policy.RouteHints.Count())
			{
				if (policy.RouteHints.Get(j).Id == hint.Id)
				{
					return false;
				}
				j++;
			}
			i++;
		}
		return true;
	}

	static bool ActorDataValid(HCEcologyActorObservation actor, int nowMs)
	{
		if (!actor || actor.Id == "" || actor.Species == "" || !actor.EligibleResources)
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
		if (!zone || zone.Id == "" || !zone.EligibleSpecies)
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
			if (zone.EligibleSpecies.Get(i) == "")
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
		while (i < state.Assignments.Count())
		{
			HCEcologyAssignment assignment = state.Assignments.Get(i);
			if (!assignment || assignment.ActorId == "" || assignment.ZoneId == "")
			{
				return false;
			}
			if (assignment.IssuedAtMs < 0 || assignment.HoldUntilMs < assignment.IssuedAtMs || assignment.CooldownUntilMs < assignment.HoldUntilMs)
			{
				return false;
			}
			int j = i + 1;
			while (j < state.Assignments.Count())
			{
				if (state.Assignments.Get(j).ActorId == assignment.ActorId)
				{
					return false;
				}
				j++;
			}
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
		while (i < batch.Actors.Count())
		{
			HCEcologyActorObservation actor = batch.Actors.Get(i);
			if (!ActorDataValid(actor, nowMs))
			{
				return false;
			}
			int j = i + 1;
			while (j < batch.Actors.Count())
			{
				if (batch.Actors.Get(j).Id == actor.Id)
				{
					return false;
				}
				j++;
			}
			i++;
		}
		i = 0;
		while (i < batch.Zones.Count())
		{
			HCEcologyZoneObservation zone = batch.Zones.Get(i);
			if (!ZoneDataValid(zone, nowMs))
			{
				return false;
			}
			int k = i + 1;
			while (k < batch.Zones.Count())
			{
				if (batch.Zones.Get(k).Id == zone.Id)
				{
					return false;
				}
				k++;
			}
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
		return !assignment || nowMs >= assignment.CooldownUntilMs;
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
		int holdUntilMs = nowMs + policy.HysteresisMs;
		int cooldownUntilMs = holdUntilMs + policy.CooldownMs;
		if (holdUntilMs < nowMs || cooldownUntilMs < holdUntilMs)
		{
			return HCEcologyCode.INVALID;
		}
		int zoneCursor = state.NextZoneIndex % zoneCount;
		int actorStep = 0;
		while (actorStep < actorCount && directives.Count() < policy.MaxDirectives)
		{
			int actorIndex = (state.NextActorIndex + actorStep) % actorCount;
			HCEcologyActorObservation actor = batch.Actors.Get(actorIndex);
			if (ActorReady(actor, state, policy, capabilities, nowMs) && !SelectedActor(directives, actor.Id))
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
		if (!directive || directive.ActorId == "" || directive.ZoneId == "")
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
		if (directive.NextActorIndex < 0 || directive.NextZoneIndex < 0)
		{
			return false;
		}
		return directive.CooldownUntilMs == nowMs + policy.HysteresisMs + policy.CooldownMs;
	}

	static int Commit(HCEcologyState state, HCEcologyPolicy policy, array<ref HCEcologyDirective> directives, array<bool> nativeAccepted, int nowMs)
	{
		if (!PolicyValid(policy) || !StateDataValid(state, policy) || !directives || !nativeAccepted)
		{
			return HCEcologyCode.INVALID;
		}
		if (nowMs < state.LastNowMs || directives.Count() > policy.MaxDirectives || nativeAccepted.Count() != directives.Count())
		{
			return HCEcologyCode.INVALID;
		}
		int i = 0;
		int newAssignments = 0;
		int observationAtMs = state.LastObservationMs;
		while (i < directives.Count())
		{
			HCEcologyDirective directive = directives.Get(i);
			if (!DirectiveValid(directive, policy, nowMs))
			{
				return HCEcologyCode.INVALID;
			}
			if (!nativeAccepted.Get(i))
			{
				return HCEcologyCode.NATIVE_REJECTED;
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
			if (!FindAssignment(state, directive.ActorId))
			{
				newAssignments++;
			}
			int j = i + 1;
			while (j < directives.Count())
			{
				if (directives.Get(j).ActorId == directive.ActorId || directives.Get(j).ZoneId == directive.ZoneId)
				{
					return HCEcologyCode.INVALID;
				}
				j++;
			}
			i++;
		}
		if (state.Assignments.Count() + newAssignments > policy.MaxActors)
		{
			return HCEcologyCode.INVALID;
		}
		i = 0;
		while (i < directives.Count())
		{
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
		return HCEcologyCode.OK;
	}
}
