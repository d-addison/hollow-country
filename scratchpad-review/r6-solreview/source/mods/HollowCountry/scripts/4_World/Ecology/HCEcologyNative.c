// API snapshot: installed scripts-1.30.164289:
// Object.GetWaterSourceObjectType, EntityAI.GetHierarchyParent,
// ItemBase.HasQuantity/GetQuantity/GetLiquidType, AIWorld.FindPath and
// SampleNavmeshPosition, PGFilter.SetFlags. Path results are geometry only.
class HCEcologyNative
{
	static bool Authority()
	{
		return GetGame() && GetGame().IsServer() && GetGame().GetWorld();
	}

	static int SampleResource(EntityAI entity)
	{
		if (!Authority() || !entity || entity.IsPendingDeletion()) { return 0; }
		if (!HCEcologyRuntimeRules.PositionValid(entity.GetPosition())) { return 0; }
		bool parent = entity.GetHierarchyParent() != null;
		bool ruined = entity.IsRuined();
		bool well = entity.GetWaterSourceObjectType() == EWaterSourceObjectType.WELL;
		ItemBase item = ItemBase.Cast(entity);
		if (!item)
		{
			return HCEcologyRuntimeRules.ResourceKind(false, false, false, 0, well, parent, ruined);
		}
		bool water = item.IsLiquidContainer() && (item.GetLiquidType() == LIQUID_WATER || item.GetLiquidType() == LIQUID_CLEANWATER);
		return HCEcologyRuntimeRules.ResourceKind(item.IsFood() || Edible_Base.Cast(item) != null, water, item.HasQuantity(), item.GetQuantity(), well, parent, ruined);
	}

	static HCEcologyActorObservation SampleActor(EntityAI entity, string id, int nowMs)
	{
		if (!Authority() || !entity || entity.IsPendingDeletion()) { return null; }
		if (!entity.IsAlive() || !HCEcologyRuntimeRules.PositionValid(entity.GetPosition())) { return null; }
		DayZCreatureAI creature = DayZCreatureAI.Cast(entity);
		if (!creature || !creature.GetAIAgent()) { return null; }
		HCEcologyActorObservation observation = new HCEcologyActorObservation;
		observation.Id = id;
		observation.Species = entity.GetType();
		observation.PopulationKind = HCEcologyPopulation.ANIMAL;
		if (ZombieBase.Cast(entity)) { observation.PopulationKind = HCEcologyPopulation.INFECTED; }
		observation.Alive = true;
		observation.ObservedAtMs = nowMs;
		// An AIAgent is not evidence of a supported resource-seeking command.
		observation.NativeNavigationAvailable = false;
		return observation;
	}

	static HCEcologyCapabilities Capabilities()
	{
		HCEcologyCapabilities capabilities = new HCEcologyCapabilities;
		capabilities.IsServerAuthority = Authority();
		capabilities.ProviderAvailable = false;
		capabilities.SupportsAnimalNavigation = false;
		capabilities.SupportsInfectedNavigation = false;
		return capabilities;
	}

	static HCEcologyRouteIntent ProbePath(EntityAI actor, EntityAI resource, string actorId, string resourceId, int kind, HCEcologyRuntimeSettings settings, string worldName, string session, int nowMs)
	{
		if (!Authority() || !actor || !resource || !HCEcologyRuntimeRules.SettingsValid(settings)) { return null; }
		if (nowMs < 0 || nowMs > 2147483647 - settings.IntentMs) { return null; }
		if (!actor.IsAlive() || actor.IsPendingDeletion() || SampleResource(resource) != kind || kind == 0) { return null; }
		DayZCreatureAI creature = DayZCreatureAI.Cast(actor);
		if (!creature || !creature.GetAIAgent()) { return null; }
		vector origin = actor.GetPosition();
		vector desired = resource.GetPosition();
		if (!HCEcologyRuntimeRules.PositionValid(origin) || !HCEcologyRuntimeRules.PositionValid(desired)) { return null; }
		if (vector.DistanceSq(origin, desired) > settings.Radius * settings.Radius) { return null; }
		AIWorld world = GetGame().GetWorld().GetAIWorld();
		if (!world) { return null; }
		PGFilter filter = new PGFilter;
		filter.SetFlags(PGPolyFlags.WALK | PGPolyFlags.DOOR | PGPolyFlags.INSIDE, PGPolyFlags.DISABLED | PGPolyFlags.UNREACHABLE | PGPolyFlags.SWIM | PGPolyFlags.SWIM_SEA | PGPolyFlags.LADDER | PGPolyFlags.JUMP | PGPolyFlags.CLIMB | PGPolyFlags.CRAWL | PGPolyFlags.CROUCH, PGPolyFlags.NONE);
		vector sampledStart;
		vector sampledEnd;
		if (!world.SampleNavmeshPosition(origin, 1.5, filter, sampledStart)) { return null; }
		if (!world.SampleNavmeshPosition(desired, 1.5, filter, sampledEnd)) { return null; }
		if (!HCEcologyRuntimeRules.PositionValid(sampledStart) || !HCEcologyRuntimeRules.PositionValid(sampledEnd)) { return null; }
		if (vector.DistanceSq(sampledStart, origin) > 2.25 || vector.DistanceSq(sampledEnd, desired) > 2.25) { return null; }
		TVectorArray path = new TVectorArray;
		if (!world.FindPath(sampledStart, sampledEnd, filter, path) || !path) { return null; }
		if (path.Count() < 2 || path.Count() > 64) { return null; }
		float length = 0;
		int i = 0;
		while (i < path.Count())
		{
			if (!HCEcologyRuntimeRules.PositionValid(path.Get(i))) { return null; }
			if (i > 0) { length += vector.Distance(path.Get(i - 1), path.Get(i)); }
			i++;
		}
		if (vector.DistanceSq(path.Get(0), sampledStart) > 4) { return null; }
		float gap = vector.DistanceSq(path.Get(path.Count() - 1), sampledEnd);
		if (!HCEcologyRuntimeRules.PathSummaryValid(path.Count(), length, gap, settings.Radius)) { return null; }
		HCEcologyRouteIntent intent = new HCEcologyRouteIntent;
		intent.WorldName = worldName;
		intent.SessionId = session;
		intent.ActorId = actorId;
		intent.ResourceId = resourceId;
		intent.ResourceKind = kind;
		intent.IssuedAtMs = nowMs;
		intent.ExpiresAtMs = nowMs + settings.IntentMs;
		intent.Origin = origin;
		intent.Destination = sampledEnd;
		intent.NativePath = true;
		intent.PathPoints = path.Count();
		intent.PathLength = length;
		return intent;
	}

	static bool Submit(HCEcologyRouteIntent intent)
	{
		// No public animal resource-goal API was found. Infected pack waypoints
		// exist, but taking another module/CE group's agents would steal control.
		// Preserve native brains and reject; never synthesize acceptance.
		return false;
	}
}
