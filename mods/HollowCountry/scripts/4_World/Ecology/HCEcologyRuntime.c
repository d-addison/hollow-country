// Core integration seam only: main calls Start(settings, world, freshSession),
// Tick(GetGame().GetTime()) and Stop(). No module registration/core edits here.
// Bounded registrations are a partial observed cohort, never a world census.
// No entities are spawned, consumed, fed, moved, deleted or re-grouped.
// Installed scripts-1.30.164289 native references for checkpoint work:
// 1_Core/proto/EnScript.c:380 Count; EnDebug.c:96 Print;
// 3_Game/Global/Game.c:1535 GetTime, :1197 SurfaceIsPond;
// 3_Game/Entities/Object.c:287 GetPosition. Dirty state tracks only the
// persisted Samples/PathQueries counters; native acceptance remains pending.
// Registry ceilings: HCEcologyRuntimeRules.REGISTRY_ACTORS (256) and
// REGISTRY_RESOURCES (2048), fixed, sized for the shipped vanilla CE cohort;
// settings MaxActors/MaxResources bound only the per-tick batch/policy (<=32).
// HC-29: one stage per tick; pruning retains a reverse cursor and shared
// unit/time caps. Probe cursors and the existing small sample windows remain.
// Routine checkpoints use HCSaveScheduler; only startup/shutdown are barriers.
// N1: Game.c:914 GetTickTime, :1535 GetTime; EnSystem.c:106 TickCount.
// EnMath.c:553/566 Min/Max; EnScript.c:380/399/463 Count/Get/Remove.
// Raw callback, startup, admission and save maxima are cached independently.
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
	protected bool m_SampleActorTurn = true;
	protected string m_Session;
	// Cycle stage machine (HCEcologyRuntimeRules.STAGE_*) and the totals one cycle carries between stages.
	protected int m_Stage;
	protected int m_CycleSamples;
	protected int m_CycleExamined;
	protected int m_CycleQueries;
	protected bool m_ProbeDone;
	protected ref HCUnitBudget m_Units = new HCUnitBudget;
	protected ref HCWorkBudget m_Work = new HCWorkBudget;
	protected ref HCEcologySaveJob m_SaveJob;
	protected int m_PruneKind;
	protected int m_PruneCursor = -1;
	protected int m_Visited;
	protected int m_Deferred;
	protected int m_CallbackMaxTicks = -1;
	protected int m_StartupMaxTicks = -1;
	protected int m_AdmissionMaxTicks = -1;
	protected int m_SaveMaxTicks = -1;
	protected int m_LastElapsedTicks;
	protected int m_ReportAfter;
	protected float m_TicksPerMs;

	// Passive sampler/debug lookup: never allocates or observes native state.
	static HCEcologyRuntime HCPeek() { return s_Instance; }

	static HCEcologyRuntime Instance()
	{
		if (!HCEcologyNative.Authority()) { return null; }
		if (!s_Instance) { s_Instance = new HCEcologyRuntime; }
		return s_Instance;
	}

	// True when the entity was bound; the hook keeps that flag so a repeated
	// EEInit never rebinds and only bound entities pay for Unregister.
	static bool Register(EntityAI entity, bool actor)
	{
		HCEcologyRuntime runtime = Instance();
		if (!runtime || !entity || !runtime.m_Collecting) { return false; }
		int callbackStart = TickCount(0);
		bool added = runtime.Add(entity, actor);
		runtime.m_CallbackMaxTicks = Math.Max(runtime.m_CallbackMaxTicks, TickCount(callbackStart));
		return added;
	}

	// Called when the service will not start (disabled or rejected): releases
	// the pre-start cohort and stops collecting. A running service is untouched.
	static void CloseCollection()
	{
		if (s_Instance) { s_Instance.CloseCohort(); }
		else { Print("[HC Plan] HC-29 state=off visited=0 deferred=0 save_phase=0 elapsed_us=-1; runtime=PENDING"); }
	}

	void CloseCohort()
	{
		if (m_Running) { return; }
		if (m_Collecting) { Print("[HC Plan] HC-29 state=off visited=0 deferred=0 save_phase=0 elapsed_us=-1; runtime=PENDING"); }
		m_Collecting = false;
		m_Actors.Clear();
		m_Resources.Clear();
	}

	static void Unregister(EntityAI entity)
	{
		if (!s_Instance || !entity || !s_Instance.m_Collecting) { return; }
		int callbackStart = TickCount(0);
		s_Instance.Remove(entity);
		s_Instance.m_CallbackMaxTicks = Math.Max(s_Instance.m_CallbackMaxTicks, TickCount(callbackStart));
	}

	bool Add(EntityAI entity, bool actor)
	{
		if (!m_Collecting || !entity || !HCEcologyNative.Authority() || entity.IsPendingDeletion()) { return false; }
		array<ref HCEcologyLiveBinding> entries = m_Resources;
		int limit = HCEcologyRuntimeRules.REGISTRY_RESOURCES;
		if (actor)
		{
			entries = m_Actors;
			limit = HCEcologyRuntimeRules.REGISTRY_ACTORS;
		}
		// EEInit hot path: full cohorts never inspect resources. Duplicates are
		// excluded by the hook's bound flag, so no per-registration scan runs.
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
			return false;
		}
		if (!actor)
		{
			ItemBase item = ItemBase.Cast(entity);
			bool eligible = entity.GetWaterSourceObjectType() == EWaterSourceObjectType.WELL;
			if (item) { eligible = eligible || item.IsFood() || Edible_Base.Cast(item) != null || item.IsLiquidContainer(); }
			if (!eligible) { return false; }
		}
		HCEcologyLiveBinding binding = new HCEcologyLiveBinding;
		binding.Live = entity;
		binding.Serial = m_NextSerial;
		binding.LocalId = HCEcologyRuntimeRules.LocalId(m_Session, binding.Serial);
		m_NextSerial++;
		entries.Insert(binding);
		return true;
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
		int startupStart = TickCount(0);
		bool started = runtime.Begin(settings, worldName, session);
		runtime.m_StartupMaxTicks = Math.Max(runtime.m_StartupMaxTicks, TickCount(startupStart));
		if (!started && !runtime.m_Running)
		{
			Print("[HC Plan] HC-29 state=refused reason=start_admission visited=0 deferred=0 save_phase=0 elapsed_us=-1; runtime=PENDING");
			runtime.Finish();
		}
		return started;
	}

	bool Begin(HCEcologyRuntimeSettings settings, string worldName, string session)
	{
		int admissionStart = TickCount(0);
		if (m_Running || session == m_Session) { return false; }
		// A new session starts a new save-cost window (#180); Open records startup saves after this.
		m_SaveMaxTicks = -1;
		worldName = HCBuildIdentity.CanonicalWorld(worldName);
		if (!HCEcologyNative.Authority() || !HCBuildIdentity.SameWorld(worldName, GetGame().GetWorldName())) { return false; }
		if (!HCEcologyRuntimeRules.Token(worldName) || !HCEcologyRuntimeRules.Token(session)) { return false; }
		int nowMs = GetGame().GetTime();
		if (!HCEcologyRuntimeRules.ClockValid(nowMs)) { return false; }
		if (!settings) { settings = HCEcologyRuntimeIO.Settings(); }
		if (!HCEcologyRuntimeRules.SettingsValid(settings))
		{
			Print("[HC Ecology] invalid or unreadable settings; admission rejected");
			Print("[HC Plan] HC-29 state=refused reason=invalid_settings visited=0 deferred=0 save_phase=0 elapsed_us=-1; runtime=PENDING");
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
		if (m_Actors.Count() > HCEcologyRuntimeRules.REGISTRY_ACTORS || m_Resources.Count() > HCEcologyRuntimeRules.REGISTRY_RESOURCES)
		{
			Print("[HC Ecology] retained cohort exceeds configured bounds; admission rejected");
			return false;
		}
		m_AdmissionMaxTicks = Math.Max(m_AdmissionMaxTicks, TickCount(admissionStart));
		m_Store = new HCEcologyRuntimeStore;
		int openStart = TickCount(0);
		m_Checkpoint = m_Store.Open(worldName, session);
		// Open includes recovery/readback and the synchronous startup barrier.
		// Save attribution overlaps total startup; neither is an additive cost.
		HCRecordSaveTicks(TickCount(openStart));
		if (!m_Checkpoint)
		{
			Print("[HC Ecology] checkpoint unavailable; observation service rejected");
			return false;
		}
		m_SaveJob = new HCEcologySaveJob;
		m_SaveJob.HCBind(this, m_Store);
		// HC-29 lead wiring: staged routine saves run on the shared scheduler; Finish unregisters on every stop path.
		HCSaveScheduler.HCRegister(m_SaveJob);
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
		m_PruneKind = 0;
		m_PruneCursor = -1;
		m_ReportAfter = 0;
		m_ActorSample = 0;
		m_ResourceSample = 0;
		m_SampleActorTurn = true;
		m_Visited = 0;
		m_Deferred = 0;
		m_TicksPerMs = 0;
		m_Dirty = false;
		m_Stage = HCEcologyRuntimeRules.STAGE_IDLE;
		m_CycleSamples = 0;
		m_CycleExamined = 0;
		m_CycleQueries = 0;
		m_ProbeDone = false;
		m_Intents.Clear();
		m_Collecting = true;
		m_Running = true;
		Print("[HC Ecology] observation/path adapter started; native brains preserved");
		Print("[HC Plan] HC-29 state=on visited=0 deferred=0 save_phase=0 elapsed_us=-1 reason=invalid_calibration migration=unsupported; runtime=PENDING");
		return true;
	}

	static void Tick(int nowMs)
	{
		if (!s_Instance || !s_Instance.m_Running) { return; }
		int tickStart = TickCount(0);
		s_Instance.m_Visited = 0;
		s_Instance.Pump(nowMs);
		s_Instance.m_LastElapsedTicks = TickCount(tickStart);
		s_Instance.HCReport(nowMs);
	}

	void Pump(int nowMs)
	{
		if (!m_Running) { return; }
		if (m_SaveJob && m_SaveJob.HCFailed())
		{
			m_Running = false;
			Finish();
			return;
		}
		// Scheduler completion clears HCDirty; a newer counter mutation may have
		// occurred during its frozen snapshot. Rearm it on the next cheap tick.
		if (m_SaveJob && m_Dirty) { m_SaveJob.HCDirty = true; }
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
		if (m_Stage == HCEcologyRuntimeRules.STAGE_IDLE)
		{
			if (!HCEcologyRuntimeRules.TickDue(nowMs, m_LastTick, m_Settings.TickMs)) { return; }
			m_LastTick = nowMs;
			m_Stage = HCEcologyRuntimeRules.STAGE_PRUNE;
			m_PruneKind = 0;
			m_PruneCursor = m_Resources.Count() - 1;
			m_CycleSamples = 0;
			m_CycleExamined = 0;
			m_CycleQueries = 0;
			m_ProbeDone = false;
		}
		// Exactly one stage per module tick; each stage is bounded on its own.
		if (m_Stage == HCEcologyRuntimeRules.STAGE_PRUNE) { StagePrune(nowMs); return; }
		if (m_Stage == HCEcologyRuntimeRules.STAGE_SAMPLE) { StageSample(nowMs); return; }
		if (m_Stage == HCEcologyRuntimeRules.STAGE_PROBE) { StageProbe(nowMs); return; }
		if (m_Stage == HCEcologyRuntimeRules.STAGE_SAVE) { StageSave(nowMs); }
	}

	void StagePrune(int nowMs)
	{
		m_Units.HCReset(HCEcologyRuntimeRules.PRUNE_ROWS_PER_TICK);
		m_Work.HCReset(HCEcologyRuntimeRules.PRUNE_ROWS_PER_TICK, HCEcologyRuntimeRules.SLICE_MS);
		int visited = 0;
		// Capture a reverse window at cycle start. New registrations cannot
		// extend this pass indefinitely; deletions normalize the next cursor.
		while (m_PruneKind < 3)
		{
			array<ref HCEcologyLiveBinding> entries = m_Resources;
			if (m_PruneKind == 1) { entries = m_Actors; }
			int count = entries.Count();
			if (m_PruneKind == 2) { count = m_Intents.Count(); }
			m_PruneCursor = Math.Min(m_PruneCursor, count - 1);
			if (m_PruneCursor < 0)
			{
				m_PruneKind++;
				if (m_PruneKind == 1) { m_PruneCursor = m_Actors.Count() - 1; }
				if (m_PruneKind == 2) { m_PruneCursor = m_Intents.Count() - 1; }
				continue;
			}
			// Always allow the first bounded row; then consult both shared caps.
			if (visited > 0 && !m_Work.HCContinue()) { break; }
			if (!m_Units.HCTake(1)) { break; }
			int index = m_PruneCursor;
			m_PruneCursor--;
			visited++;
			if (m_PruneKind == 2)
			{
				if (!HCEcologyRuntimeRules.IntentValid(m_Intents.Get(index), m_Policy.WorldName, m_Session, nowMs, m_Settings.Radius)) { m_Intents.Remove(index); }
				continue;
			}
			HCEcologyLiveBinding binding = entries.Get(index);
			if (!binding || !binding.Live)
			{
				if (binding) { ForgetIntents(binding.LocalId); }
				entries.Remove(index);
			}
		}
		m_Visited = visited;
		m_Deferred = Math.Max(0, m_PruneCursor + 1);
		if (m_PruneKind == 0) { m_Deferred += m_Actors.Count() + m_Intents.Count(); }
		if (m_PruneKind == 1) { m_Deferred += m_Intents.Count(); }
		if (m_PruneKind < 3) { return; }
		m_Stage = HCEcologyRuntimeRules.STAGE_SAMPLE;
	}

	void StageSample(int nowMs)
	{
		HCEcologyObservationBatch batch = new HCEcologyObservationBatch;
		batch.WorldName = m_Policy.WorldName;
		batch.SessionId = m_Session;
		batch.ObservedAtMs = nowMs;
		int actorTotal = m_Actors.Count();
		int resourceTotal = m_Resources.Count();
		int actorTake = Math.Min(actorTotal, Math.Min(m_Settings.SampleSlice, m_Settings.MaxActors));
		int resourceTake = Math.Min(resourceTotal, Math.Min(m_Settings.SampleSlice, m_Settings.MaxResources));
		int actors = 0;
		int resources = 0;
		int visited = 0;
		m_Units.HCReset(HCEcologyRuntimeRules.SAMPLE_ROWS_PER_TICK);
		m_Work.HCReset(HCEcologyRuntimeRules.SAMPLE_ROWS_PER_TICK, HCEcologyRuntimeRules.SLICE_MS);
		// Alternate the two registries, retaining the NEXT row and turn before
		// native observation. Even a one-row time slice reaches both over time.
		while (actors < actorTake || resources < resourceTake)
		{
			if (visited > 0 && !m_Work.HCContinue()) { break; }
			if (!m_Units.HCTake(1)) { break; }
			bool actorTurn = m_SampleActorTurn;
			if (actors >= actorTake) { actorTurn = false; }
			if (resources >= resourceTake) { actorTurn = true; }
			m_SampleActorTurn = !actorTurn;
			visited++;
			if (actorTurn)
			{
				m_ActorSample = m_ActorSample % actorTotal;
				HCEcologyLiveBinding actorBinding = m_Actors.Get(m_ActorSample);
				m_ActorSample = (m_ActorSample + 1) % actorTotal;
				actors++;
				if (!actorBinding || !actorBinding.Live) { continue; }
				HCEcologyActorObservation observed = HCEcologyNative.SampleActor(actorBinding.Live, actorBinding.LocalId, nowMs);
				if (!observed) { continue; }
				batch.Actors.Insert(observed);
				vector point = actorBinding.Live.GetPosition();
				bool pondHere = GetGame().SurfaceIsPond(point[0], point[2]);
				if (pondHere && batch.Zones.Count() < m_Settings.MaxResources)
				{
					HCEcologyZoneObservation pond = Zone("pond:" + observed.Id, HCEcologyResource.WATER, nowMs);
					batch.Zones.Insert(pond);
				}
				continue;
			}
			m_ResourceSample = m_ResourceSample % resourceTotal;
			HCEcologyLiveBinding resourceBinding = m_Resources.Get(m_ResourceSample);
			m_ResourceSample = (m_ResourceSample + 1) % resourceTotal;
			resources++;
			if (!resourceBinding || !resourceBinding.Live) { continue; }
			int kind = HCEcologyNative.SampleResource(resourceBinding.Live);
			if (kind != 0 && batch.Zones.Count() < m_Settings.MaxResources)
			{
				HCEcologyZoneObservation zone = Zone(resourceBinding.LocalId, kind, nowMs);
				batch.Zones.Insert(zone);
			}
		}
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
		m_CycleSamples = batch.Actors.Count();
		m_Visited = visited;
		m_Deferred = Math.Max(0, actorTotal + resourceTotal - m_Visited);
		m_Stage = HCEcologyRuntimeRules.STAGE_PROBE;
	}

	void StageProbe(int nowMs)
	{
		ProbeCohort(nowMs);
		if (!m_ProbeDone) { return; }
		if (!HCEcologyRuntimeRules.CountersFit(m_Checkpoint, m_CycleSamples, m_CycleQueries))
		{
			Print("[HC Ecology] bounded diagnostic counters exhausted");
			Finish();
			return;
		}
		m_Checkpoint.Samples += m_CycleSamples;
		m_Checkpoint.PathQueries += m_CycleQueries;
		// Only persisted counters changed here. An empty sample/path pass is
		// not a new checkpoint and must not rewrite the journal every minute.
		if (m_CycleSamples > 0 || m_CycleQueries > 0) { m_Dirty = true; }
		m_Stage = HCEcologyRuntimeRules.STAGE_IDLE;
		if (nowMs - m_LastSave >= 60000) { m_Stage = HCEcologyRuntimeRules.STAGE_SAVE; }
	}

	// The checkpoint request gets a module tick; IO runs in the shared scheduler.
	void StageSave(int nowMs)
	{
		m_Stage = HCEcologyRuntimeRules.STAGE_IDLE;
		if (!Checkpoint())
		{
			// The failed store is poisoned; release handles without retrying it.
			m_Running = false;
			Finish();
		}
		m_LastSave = nowMs;
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

	// One bounded SLICE of the cycle's pair/probe pass (the PROBE stage calls it once per module tick
	// until m_ProbeDone). Returns the probes issued by this slice; m_CycleExamined / m_CycleQueries
	// carry the cycle totals, so a cycle still examines <=PAIRS_PER_TICK pairs and issues <=queryLimit
	// probes. Work units come from the shared core HCUnitBudget (no clock): a pair costs
	// PROBE_PAIR_UNITS, a native path probe PROBE_PATH_UNITS, a slice has PROBE_UNITS_PER_TICK.
	int ProbeCohort(int nowMs)
	{
		m_ProbeDone = true;
		int actorCount = m_Actors.Count();
		int resourceCount = m_Resources.Count();
		if (actorCount == 0 || resourceCount == 0) { return 0; }
		int queries = 0;
		// <=256*2048 pairs, so the product cannot overflow int.
		int totalPairs = actorCount * resourceCount;
		int pairLimit = Math.Min(totalPairs, HCEcologyRuntimeRules.PAIRS_PER_TICK);
		int queryLimit = Math.Min(m_Settings.MaxPathQueries, HCEcologyRuntimeRules.PROBES_PER_TICK);
		m_ActorCursor = m_ActorCursor % actorCount;
		m_ResourceCursor = m_ResourceCursor % resourceCount;
		// The unit budget is consulted BEFORE each pair, so the cursors always name the NEXT
		// unexamined pair when this slice yields, and the next module tick resumes there.
		m_Units.HCReset(HCEcologyRuntimeRules.PROBE_UNITS_PER_TICK);
		m_Work.HCReset(HCEcologyRuntimeRules.PROBE_UNITS_PER_TICK, HCEcologyRuntimeRules.SLICE_MS);
		int visited = 0;
		while (m_CycleExamined < pairLimit && m_CycleQueries + queries < queryLimit)
		{
			if (visited > 0 && !m_Work.HCContinue())
			{
				m_ProbeDone = false;
				break;
			}
			if (!m_Units.HCTake(HCEcologyRuntimeRules.PROBE_PAIR_UNITS))
			{
				m_ProbeDone = false;
				break;
			}
			HCEcologyLiveBinding actor = m_Actors.Get(m_ActorCursor);
			HCEcologyLiveBinding resource = m_Resources.Get(m_ResourceCursor);
			m_CycleExamined++;
			visited++;
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
			m_Units.HCCharge(HCEcologyRuntimeRules.PROBE_PATH_UNITS);
			HCEcologyRouteIntent intent = HCEcologyNative.ProbePath(actor.Live, resource.Live, actorId, resourceId, kind, m_Settings, m_Policy.WorldName, m_Session, nowMs);
			if (intent) { m_Intents.Insert(intent); }
		}
		m_Visited = visited;
		m_Deferred = Math.Max(0, pairLimit - m_CycleExamined);
		m_CycleQueries = m_CycleQueries + queries;
		if (m_CycleExamined >= pairLimit || m_CycleQueries >= queryLimit) { m_ProbeDone = true; }
		return queries;
	}

	// Routine save request is constant work. Registration is lead-owned.
	bool Checkpoint()
	{
		if (!m_Dirty) { return true; }
		if (!m_SaveJob || m_SaveJob.HCFailed()) { return false; }
		m_SaveJob.HCDirty = true;
		return true;
	}

	HCEcologySaveJob HCGetSaveJob() { return m_SaveJob; }
	bool HCIsRunning() { return m_Running; }
	int HCCallbackTicks() { return m_CallbackMaxTicks; }
	int HCStartupTicks() { return m_StartupMaxTicks; }
	int HCAdmissionTicks() { return m_AdmissionMaxTicks; }
	int HCSaveTicks() { return m_SaveMaxTicks; }
	int HCVisited() { return m_Visited; }
	int HCDeferred() { return m_Deferred; }
	int HCSavePhase()
	{
		if (!m_Store) { return 0; }
		return m_Store.HCPhase();
	}
	// Consume once after forwarding these raw maxima to SampleCost; HC-25 can
	// cache the forwarded values without running another observation/IO pass.
	void HCResetCostTicks()
	{
		m_CallbackMaxTicks = -1;
		m_StartupMaxTicks = -1;
		m_AdmissionMaxTicks = -1;
		m_SaveMaxTicks = -1;
	}
	void HCSetCalibration(float ticksPerMs) { m_TicksPerMs = ticksPerMs; }
	void HCRecordSaveTicks(int ticks) { m_SaveMaxTicks = Math.Max(m_SaveMaxTicks, ticks); }

	void HCReport(int nowMs)
	{
		if (nowMs < m_ReportAfter) { return; }
		if (!HCEcologyRuntimeRules.ClockValid(nowMs)) { return; }
		m_ReportAfter = nowMs + 60000;
		int elapsedUs = HCEcologyRuntimeRules.ElapsedUs(m_LastElapsedTicks, m_TicksPerMs);
		int phase = HCSavePhase();
		string reason = "observed_clock";
		if (elapsedUs < 0) { reason = "invalid_calibration"; }
		string state = "on";
		if (!m_Running) { state = "refused"; }
		// Split: native Enforce refuses more than 9 '+' in one statement.
		string counts = "visited=" + m_Visited.ToString() + " deferred=" + m_Deferred.ToString() + " save_phase=" + phase.ToString();
		string timing = " elapsed_us=" + elapsedUs.ToString() + " state=" + state + " reason=" + reason;
		Print("[HC Plan] HC-29 " + counts + timing + "; runtime=PENDING");
	}

	HCEcologyCheckpoint HCSnapshot()
	{
		if (!m_Dirty || !m_Checkpoint) { return null; }
		HCEcologyCheckpoint snapshot = new HCEcologyCheckpoint;
		snapshot.Version = m_Checkpoint.Version;
		snapshot.WorldName = m_Checkpoint.WorldName;
		snapshot.SessionId = m_Checkpoint.SessionId;
		snapshot.Revision = m_Checkpoint.Revision + 1;
		snapshot.Samples = m_Checkpoint.Samples;
		snapshot.PathQueries = m_Checkpoint.PathQueries;
		return snapshot;
	}

	void HCSaved(HCEcologyCheckpoint snapshot)
	{
		m_Checkpoint.Revision = snapshot.Revision;
		m_Dirty = m_Checkpoint.Samples != snapshot.Samples || m_Checkpoint.PathQueries != snapshot.PathQueries;
	}

	bool HCWriteCheckpoint()
	{
		if (!m_Dirty) { return true; }
		HCEcologyCheckpoint next = new HCEcologyCheckpoint;
		next.Version = m_Checkpoint.Version;
		next.WorldName = m_Checkpoint.WorldName;
		next.SessionId = m_Checkpoint.SessionId;
		next.Revision = m_Checkpoint.Revision + 1;
		next.Samples = m_Checkpoint.Samples;
		next.PathQueries = m_Checkpoint.PathQueries;
		int saveStart = TickCount(0);
		bool saved = m_Store.Save(next);
		HCRecordSaveTicks(TickCount(saveStart));
		if (!saved)
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
		m_Stage = HCEcologyRuntimeRules.STAGE_IDLE;
		if (wasRunning)
		{
			bool flushed = HCSaveScheduler.HCFlush(m_SaveJob);
			// Counters may advance during an in-flight snapshot. Finish the
			// continuation first, then synchronously persist only that delta.
			if (flushed) { HCWriteCheckpoint(); }
		}
		if (m_SaveJob)
		{
			HCSaveScheduler.HCUnregister(m_SaveJob);
			m_SaveJob.HCDetach();
		}
		m_SaveJob = null;
		m_TicksPerMs = 0;
		m_Deferred = 0;
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
