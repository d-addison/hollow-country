// API snapshot: installed scripts-1.30.164289:
// Object.GetWaterSourceObjectType, EntityAI.GetHierarchyParent,
// ItemBase.HasQuantity/GetQuantity/GetLiquidType, AIWorld.FindPath and
// SampleNavmeshPosition, PGFilter.SetFlags. Path results are geometry only.
// HC-48 / #149: spec FR-008/011 -> Wave 3 habitat/target dispositions in
// mission/hollow-country/ecology/habitat-overrides.json. The manifest is an
// install-time delta contract, NOT an engine-readable territory overlay.
// CE still owns native herds, territories, grazing, travel and fleeing.
// Reuse HCWildlifeObservation.HCSnapshot for bounded, deduplicated facts;
// never take a second animal cohort or infer prey from HUNTING/proximity.
// N9 evidence in scripts-1.30.164289: 3_Game/Entities/DayZAnimal.c:193/664
// GetAIAgent/GetInputController; 3_Game/AI/AIAgent.c:7 GetGroup (identity);
// 3_Game/Entities/DayZCreatureAIInputController.c:27 GetBehaviourSlot;
// 3_Game/Entities/DayZAnimalInputController.c:55 GetBehaviourAction.
// Neither these nor 4_World/Entities/DayZAnimalImplement.c:1-8 exposes an
// animal destination or target accessor. N17 is a human lifecycle, not an AI
// SDK. The supplied optional provider source path was unavailable at authoring;
// no faction/target hook is admitted from that absence or a dependency name.
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

	// HC-48 / #149 boot receipt. HCEcologyRuntimeModule calls this once per state
	// change (ready after admission, off for operator-off, refused otherwise); the
	// static guard keeps a restart or repeated owner observation from re-printing.
	// It emits counts and refusal reasons only: it neither claims CE loaded the
	// JSON/XML nor adds a tick, status controller or any admission. The counts are
	// the manifest's validated effective native content (Counts, Species and
	// Habitats Disposition tallies), pinned by tests/unit/test_hc48_habitat_boot.py.
	// Native scripts-1.30.164289: 1_Core/proto/EnDebug.c:96 Print.
	protected static string s_HabitatState;

	static void HCHabitatRefusals(string state)
	{
		if (state != "ready" && state != "off") { state = "refused"; }
		if (s_HabitatState == state) { return; }
		s_HabitatState = state;
		int species = 0;
		int habitats = 0;
		if (state == "ready")
		{
			species = 27;
			habitats = 11;
		}
		string counts = "species=" + species.ToString() + " habitats=" + habitats.ToString();
		counts = counts + " target_pairs_supported=0 state=" + state;
		counts = counts + " authored_species=42 authored_habitats=12 admitted_overlay_species=0 observed_reactions=unobserved";
		string kinds = "species_dispositions=retain_native:27,pending_suitability:14,selected_pending_addon_and_native:1";
		kinds = kinds + " habitat_dispositions=retain_native:11,legacy_unreferenced_pending_survey:1";
		string refusals = "refusals=animal_destination:no_inspected_animal_destination_api";
		refusals = refusals + ",animal_migration:native_brains_retained_no_destination_provider";
		refusals = refusals + ",animal_target_pairs:no_inspected_animal_target_accessor";
		refusals = refusals + ",provider_target_pairs:provider_source_unavailable_at_supplied_path";
		Print("[HC Plan] HC-48 " + counts + " " + kinds + " " + refusals + " runtime=PENDING");
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
