// Core integration seam only: main calls Start(settings, world, freshSession),
// Tick(GetGame().GetTime()) and Stop(). No module registration/core edits here.
// Bounded registrations are a partial observed cohort, never a world census.
// No entities are spawned, consumed, fed, moved, deleted or re-grouped.
class HCEcologyLiveBinding
{
	EntityAI Live;
	int Serial;
	string LocalId;
}

class HCEcologyRuntime
{
	protected static ref HCEcologyRuntime s_Instance;
	protected ref array<ref HCEcologyLiveBinding> m_Actors = new array<ref HCEcologyLiveBinding>;
	protected ref array<ref HCEcologyLiveBinding> m_Resources = new array<ref HCEcologyLiveBinding>;
	protected ref array<ref HCEcologyRouteIntent> m_Intents = new array<ref HCEcologyRouteIntent>;
	protected ref HCEcologyRuntimeSettings m_Settings;
	protected ref HCEcologyRuntimeStore m_Store;
	protected ref HCEcologyCheckpoint m_Checkpoint;
	protected ref HCEcologyPolicy m_Policy;
	protected ref HCEcologyState m_State;
	protected bool m_Running;
	// Collect initial EEInit callbacks before Start; Stop/admission failure closes
	// this window until another successful Start. Late teardown hooks cannot refill it.
	protected bool m_Collecting = true;
	// Per registry, so a full resource cohort never hides an actor overflow.
	protected bool m_ActorOverflow;
	protected bool m_ResourceOverflow;
	protected bool m_Dirty;
	protected int m_NextSerial = 1;
	protected int m_LastTick;
	protected int m_LastNow;
	protected int m_LastSave;
	protected int m_ActorCursor;
	protected int m_ResourceCursor;
	// Rotating sample windows over the registries; independent of the pairing cursors.
	protected int m_ActorSample;
	protected int m_ResourceSample;
	protected string m_Session;

	static HCEcologyRuntime Instance()
	{
		if (!HCEcologyNative.Authority()) { return null; }
		if (!s_Instance) { s_Instance = new HCEcologyRuntime; }
		return s_Instance;
	}

	static void Register(EntityAI entity, bool actor)
	{
		HCEcologyRuntime runtime = Instance();
		if (!runtime || !entity) { return; }
		runtime.Add(entity, actor);
	}

	// Called when the service will not start (disabled or rejected): releases
	// the pre-start cohort and stops collecting. A running service is untouched.
	static void CloseCollection()
	{
		if (s_Instance) { s_Instance.CloseCohort(); }
	}

	void CloseCohort()
	{
		if (m_Running) { return; }
		m_Collecting = false;
		m_Actors.Clear();
		m_Resources.Clear();
	}

	static void Unregister(EntityAI entity)
	{
		if (!s_Instance || !entity) { return; }
		s_Instance.Remove(entity);
	}

	void Add(EntityAI entity, bool actor)
	{
		if (!m_Collecting || !entity || !HCEcologyNative.Authority() || entity.IsPendingDeletion()) { return; }
		array<ref HCEcologyLiveBinding> entries = m_Resources;
		int limit = 32;
		if (actor) { entries = m_Actors; }
		if (m_Settings)
		{
			limit = m_Settings.MaxResources;
			if (actor) { limit = m_Settings.MaxActors; }
		}
		// EEInit hot path: full cohorts never inspect resources or scan duplicates.
		if (entries.Count() >= limit || m_NextSerial >= 2147483647)
		{
			// One line per registry and session: name, cap and the count this entry would make.
			string registry = "resources";
			bool reported = m_ResourceOverflow;
			if (actor)
			{
				registry = "actors";
				reported = m_ActorOverflow;
			}
			if (!reported)
			{
				int attempted = entries.Count() + 1;
				Print("[HC Ecology] registration overflow; registry=" + registry + "; cap=" + limit.ToString() + "; attempted=" + attempted.ToString() + "; coverage partial, no population census");
				if (actor) { m_ActorOverflow = true; }
				else { m_ResourceOverflow = true; }
			}
			return;
		}
		if (!actor)
		{
			ItemBase item = ItemBase.Cast(entity);
			bool eligible = entity.GetWaterSourceObjectType() == EWaterSourceObjectType.WELL;
			if (item) { eligible = eligible || item.IsFood() || Edible_Base.Cast(item) != null || item.IsLiquidContainer(); }
			if (!eligible) { return; }
		}
		int i = 0;
		while (i < entries.Count())
		{
			if (entries.Get(i).Live == entity) { return; }
			i++;
		}
		HCEcologyLiveBinding binding = new HCEcologyLiveBinding;
		binding.Live = entity;
		binding.Serial = m_NextSerial;
		binding.LocalId = HCEcologyRuntimeRules.LocalId(m_Session, binding.Serial);
		m_NextSerial++;
		entries.Insert(binding);
	}

	void Remove(EntityAI entity)
	{
		RemoveFrom(m_Actors, entity);
		RemoveFrom(m_Resources, entity);
	}

	void RemoveFrom(array<ref HCEcologyLiveBinding> entries, EntityAI entity)
	{
		int i = entries.Count() - 1;
		while (i >= 0)
		{
			HCEcologyLiveBinding binding = entries.Get(i);
			if (!binding || !binding.Live || binding.Live == entity)
			{
				if (binding) { ForgetIntents(binding.LocalId); }
				entries.Remove(i);
			}
			i--;
		}
	}

	void ForgetIntents(string id)
	{
		int i = m_Intents.Count() - 1;
		while (i >= 0)
		{
			HCEcologyRouteIntent intent = m_Intents.Get(i);
			if (!intent || intent.ActorId == id || intent.ResourceId == id) { m_Intents.Remove(i); }
			i--;
		}
	}

	static bool Start(HCEcologyRuntimeSettings settings, string worldName, string session)
	{
		HCEcologyRuntime runtime = Instance();
		if (!runtime) { return false; }
		bool started = runtime.Begin(settings, worldName, session);
		if (!started && !runtime.m_Running) { runtime.Finish(); }
		return started;
	}

	bool Begin(HCEcologyRuntimeSettings settings, string worldName, string session)
	{
		if (m_Running || session == m_Session) { return false; }
		worldName = HCBuildIdentity.CanonicalWorld(worldName);
		if (!HCEcologyNative.Authority() || !HCBuildIdentity.SameWorld(worldName, GetGame().GetWorldName())) { return false; }
		if (!HCEcologyRuntimeRules.Token(worldName) || !HCEcologyRuntimeRules.Token(session)) { return false; }
		int nowMs = GetGame().GetTime();
		if (!HCEcologyRuntimeRules.ClockValid(nowMs)) { return false; }
		if (!settings) { settings = HCEcologyRuntimeIO.Settings(); }
		if (!HCEcologyRuntimeRules.SettingsValid(settings))
		{
			Print("[HC Ecology] invalid or unreadable settings; admission rejected");
			return false;
		}
		// Freeze caller-owned scalar preferences through the bounded native codec.
		string text;
		string error;
		if (!JsonFileLoader<HCEcologyRuntimeSettings>.MakeData(settings, text, error)) { return false; }
		if (text.Length() > 2048) { return false; }
		if (!JsonFileLoader<HCEcologyRuntimeSettings>.LoadData(text, m_Settings, error)) { return false; }
		if (!m_Settings.Enabled)
		{
			Print("[HC Ecology] explicitly disabled by operator");
			return false;
		}
		if (m_Actors.Count() > m_Settings.MaxActors || m_Resources.Count() > m_Settings.MaxResources)
		{
			Print("[HC Ecology] retained cohort exceeds configured bounds; admission rejected");
			return false;
		}
		m_Store = new HCEcologyRuntimeStore;
		m_Checkpoint = m_Store.Open(worldName, session);
		if (!m_Checkpoint)
		{
			Print("[HC Ecology] checkpoint unavailable; observation service rejected");
			return false;
		}
		m_Session = session;
		// EEInit may have registered handles before the session was admitted.
		BindLocalIds();
		m_Policy = new HCEcologyPolicy;
		m_Policy.SchemaVersion = 1;
		m_Policy.Enabled = true;
		m_Policy.WorldName = worldName;
		m_Policy.SessionId = session;
		m_Policy.MaxObservationAgeMs = m_Settings.FreshMs;
		m_Policy.MaxActors = m_Settings.MaxActors;
		m_Policy.MaxZones = m_Settings.MaxResources;
		m_Policy.MaxDirectives = Math.Min(m_Settings.MaxPathQueries, Math.Min(m_Settings.MaxActors, m_Settings.MaxResources));
		m_Policy.HysteresisMs = m_Settings.IntentMs;
		m_State = new HCEcologyState;
		m_State.WorldName = worldName;
		m_State.SessionId = session;
		m_LastTick = nowMs;
		m_LastNow = nowMs;
		m_LastSave = m_LastTick;
		m_ActorCursor = 0;
		m_ResourceCursor = 0;
		m_ActorSample = 0;
		m_ResourceSample = 0;
		m_Dirty = false;
		m_Intents.Clear();
		m_Collecting = true;
		m_Running = true;
		Print("[HC Ecology] observation/path adapter started; native brains preserved");
		return true;
	}

	static void Tick(int nowMs)
	{
		if (s_Instance) { s_Instance.Pump(nowMs); }
	}

	void Pump(int nowMs)
	{
		if (!m_Running) { return; }
		if (!HCEcologyNative.Authority() || !HCBuildIdentity.SameWorld(m_Policy.WorldName, GetGame().GetWorldName()))
		{
			Finish();
			return;
		}
		if (!HCEcologyRuntimeRules.ClockValid(nowMs) || nowMs < m_LastNow)
		{
			Print("[HC Ecology] native session clock invalid; stopped");
			Finish();
			return;
		}
		m_LastNow = nowMs;
		if (!HCEcologyRuntimeRules.TickDue(nowMs, m_LastTick, m_Settings.TickMs)) { return; }
		m_LastTick = nowMs;
		RemoveFrom(m_Actors, null);
		RemoveFrom(m_Resources, null);
		int i = m_Intents.Count() - 1;
		while (i >= 0)
		{
			if (!HCEcologyRuntimeRules.IntentValid(m_Intents.Get(i), m_Policy.WorldName, m_Session, nowMs, m_Settings.Radius)) { m_Intents.Remove(i); }
			i--;
		}
		HCEcologyObservationBatch batch = new HCEcologyObservationBatch;
		batch.WorldName = m_Policy.WorldName;
		batch.SessionId = m_Session;
		batch.ObservedAtMs = nowMs;
		// Each tick samples at most SampleSlice actors and SampleSlice resources, starting
		// at a cursor that advances by the window, so every entry is reached in turn and
		// the batch (and its quadratic validation) stays small however full the cohorts are.
		int actorTotal = m_Actors.Count();
		int actorTake = Math.Min(actorTotal, m_Settings.SampleSlice);
		if (actorTotal > 0) { m_ActorSample = m_ActorSample % actorTotal; }
		i = 0;
		while (i < actorTake)
		{
			HCEcologyLiveBinding actorBinding = m_Actors.Get((m_ActorSample + i) % actorTotal);
			HCEcologyActorObservation observed = HCEcologyNative.SampleActor(actorBinding.Live, actorBinding.LocalId, nowMs);
			if (observed) { batch.Actors.Insert(observed); }
			// Native pond presence is observed at this live position only; no
			// invented shore point, drinking access or reachability is inferred.
			if (observed)
			{
				vector point = actorBinding.Live.GetPosition();
				bool pondHere = GetGame().SurfaceIsPond(point[0], point[2]);
				if (pondHere && batch.Zones.Count() < m_Settings.MaxResources)
				{
					HCEcologyZoneObservation pond = Zone("pond:" + observed.Id, HCEcologyResource.WATER, nowMs);
					batch.Zones.Insert(pond);
				}
			}
			i++;
		}
		if (actorTotal > 0) { m_ActorSample = (m_ActorSample + actorTake) % actorTotal; }
		int resourceTotal = m_Resources.Count();
		int resourceTake = Math.Min(resourceTotal, m_Settings.SampleSlice);
		if (resourceTotal > 0) { m_ResourceSample = m_ResourceSample % resourceTotal; }
		i = 0;
		while (i < resourceTake && batch.Zones.Count() < m_Settings.MaxResources)
		{
			HCEcologyLiveBinding resourceBinding = m_Resources.Get((m_ResourceSample + i) % resourceTotal);
			int kind = HCEcologyNative.SampleResource(resourceBinding.Live);
			if (kind != 0)
			{
				HCEcologyZoneObservation zone = Zone(resourceBinding.LocalId, kind, nowMs);
				batch.Zones.Insert(zone);
			}
			i++;
		}
		if (resourceTotal > 0) { m_ResourceSample = (m_ResourceSample + resourceTake) % resourceTotal; }
		// Consume the existing policy with genuine observations and explicit
		// absent movement capability. No eligibility lists are fabricated:
		// resource presence is not sensory eligibility.
		array<ref HCEcologyDirective> directives = new array<ref HCEcologyDirective>;
		array<ref HCEcologyReceipt> receipts = new array<ref HCEcologyReceipt>;
		HCEcologyCapabilities capabilities = HCEcologyNative.Capabilities();
		int code = HCEcologyRules.Schedule(m_State, m_Policy, batch, capabilities, nowMs, directives);
		if (code != HCEcologyCode.OK || directives.Count() != 0)
		{
			Print("[HC Ecology] scheduling contract rejected");
			Finish();
			return;
		}
		// Commit requires a qualified native provider even for an empty set.
		// Never call it to manufacture acceptance. This guarded seam remains
		// explicit for a later provider-qualified integration.
		if (capabilities.ProviderAvailable)
		{
			code = HCEcologyRules.Commit(m_State, m_Policy, directives, receipts, nowMs, capabilities);
		}
		int queries = ProbeCohort(nowMs);
		if (!HCEcologyRuntimeRules.CountersFit(m_Checkpoint, batch.Actors.Count(), queries))
		{
			Print("[HC Ecology] bounded diagnostic counters exhausted");
			Finish();
			return;
		}
		m_Checkpoint.Samples += batch.Actors.Count();
		m_Checkpoint.PathQueries += queries;
		m_Dirty = true;
		if (nowMs - m_LastSave >= 60000)
		{
			if (!Checkpoint())
			{
				// The failed store is poisoned; release handles without retrying it.
				m_Running = false;
				Finish();
			}
			m_LastSave = nowMs;
		}
	}

	HCEcologyZoneObservation Zone(string id, int kind, int nowMs)
	{
		HCEcologyZoneObservation zone = new HCEcologyZoneObservation;
		zone.Id = id;
		// No species/population eligibility is asserted by resource presence.
		zone.PopulationKind = HCEcologyPopulation.ANIMAL;
		zone.ResourceKind = kind;
		zone.ObservedAtMs = nowMs;
		zone.ExpiresAtMs = nowMs + m_Settings.FreshMs;
		return zone;
	}

	// Cache once per binding/session, including the bounded pre-start cohort.
	void BindLocalIds()
	{
		foreach (HCEcologyLiveBinding actorBinding : m_Actors)
		{
			actorBinding.LocalId = HCEcologyRuntimeRules.LocalId(m_Session, actorBinding.Serial);
		}
		foreach (HCEcologyLiveBinding resourceBinding : m_Resources)
		{
			resourceBinding.LocalId = HCEcologyRuntimeRules.LocalId(m_Session, resourceBinding.Serial);
		}
	}

	int ProbeCohort(int nowMs)
	{
		int actorCount = m_Actors.Count();
		int resourceCount = m_Resources.Count();
		if (actorCount == 0 || resourceCount == 0) { return 0; }
		int queries = 0;
		int examined = 0;
		int totalPairs = actorCount * resourceCount;
		m_ActorCursor = m_ActorCursor % actorCount;
		m_ResourceCursor = m_ResourceCursor % resourceCount;
		// Pair examinations and native path queries have independent budgets.
		// These cursors identify the NEXT pair, even when a query exhausts its budget.
		while (examined < 64 && examined < totalPairs && queries < m_Settings.MaxPathQueries)
		{
			HCEcologyLiveBinding actor = m_Actors.Get(m_ActorCursor);
			HCEcologyLiveBinding resource = m_Resources.Get(m_ResourceCursor);
			examined++;
			m_ResourceCursor++;
			if (m_ResourceCursor >= resourceCount)
			{
				m_ResourceCursor = 0;
				m_ActorCursor = (m_ActorCursor + 1) % actorCount;
			}
			if (!actor || !resource || !actor.Live || !resource.Live) { continue; }
			vector actorPoint = actor.Live.GetPosition();
			vector to = resource.Live.GetPosition();
			// Pairs are rejected by one comparison. A non-finite coordinate gives a NaN
			// distance, which is never within the radius, so no per-axis validation runs
			// for the many distant pairs.
			float gapSq = vector.DistanceSq(actorPoint, to);
			bool within = gapSq <= m_Settings.Radius * m_Settings.Radius;
			if (!within) { continue; }
			string actorId = actor.LocalId;
			string resourceId = resource.LocalId;
			int kind = HCEcologyNative.SampleResource(resource.Live);
			bool room = HCEcologyRuntimeRules.Capacity(m_Intents, actorId, resourceId, nowMs, 8);
			if (kind == 0 || !actor.Live.IsAlive() || !room) { continue; }
			queries++;
			HCEcologyRouteIntent intent = HCEcologyNative.ProbePath(actor.Live, resource.Live, actorId, resourceId, kind, m_Settings, m_Policy.WorldName, m_Session, nowMs);
			if (intent) { m_Intents.Insert(intent); }
		}
		return queries;
	}

	bool Checkpoint()
	{
		if (!m_Dirty) { return true; }
		HCEcologyCheckpoint next = new HCEcologyCheckpoint;
		next.Version = m_Checkpoint.Version;
		next.WorldName = m_Checkpoint.WorldName;
		next.SessionId = m_Checkpoint.SessionId;
		next.Revision = m_Checkpoint.Revision + 1;
		next.Samples = m_Checkpoint.Samples;
		next.PathQueries = m_Checkpoint.PathQueries;
		if (!m_Store.Save(next))
		{
			Print("[HC Ecology] checkpoint write/readback failed; stopped, preserve journal");
			return false;
		}
		m_Checkpoint = next;
		m_Dirty = false;
		return true;
	}

	static void Stop()
	{
		if (s_Instance) { s_Instance.Finish(); }
	}

	void Finish()
	{
		bool wasRunning = m_Running;
		m_Running = false;
		m_Collecting = false;
		if (wasRunning) { Checkpoint(); }
		m_Dirty = false;
		m_Intents.Clear();
		m_Actors.Clear();
		m_Resources.Clear();
	}

	static array<ref HCEcologyRouteIntent> IntentSnapshot(int nowMs)
	{
		array<ref HCEcologyRouteIntent> copy = new array<ref HCEcologyRouteIntent>;
		if (!s_Instance || !s_Instance.m_Running) { return copy; }
		foreach (HCEcologyRouteIntent intent : s_Instance.m_Intents)
		{
			if (!HCEcologyRuntimeRules.IntentValid(intent, s_Instance.m_Policy.WorldName, s_Instance.m_Session, nowMs, s_Instance.m_Settings.Radius)) { continue; }
			string text;
			string error;
			HCEcologyRouteIntent cloned;
			if (!JsonFileLoader<HCEcologyRouteIntent>.MakeData(intent, text, error) || text.Length() > 2048) { return new array<ref HCEcologyRouteIntent>; }
			if (!JsonFileLoader<HCEcologyRouteIntent>.LoadData(text, cloned, error)) { return new array<ref HCEcologyRouteIntent>; }
			copy.Insert(cloned);
		}
		return copy;
	}
}
