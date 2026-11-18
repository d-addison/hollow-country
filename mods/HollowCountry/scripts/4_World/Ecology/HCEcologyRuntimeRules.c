// Registry ceilings are runtime constants, separate from the settings fields:
// MaxActors/MaxResources remain the per-tick observation batch/policy bounds
// (<= 3_Game HCEcologyLimits.ACTORS/ZONES = 32). Sized for vanilla Chernarus CE
// (types.xml food nominal 839 + liquid containers 271, plus wells, inventories
// and herd/ambient animals) with headroom; a binding is one handle, int and
// short id, so the fixed ceilings bound memory to a few hundred KB.
class HCEcologyRuntimeRules
{
	static const int REGISTRY_ACTORS = 256;
	static const int REGISTRY_RESOURCES = 2048;
	// Per observation tick: distance-only pair checks and native path probes,
	// both also stopped by the shared HCWorkBudget 4 ms cooperative guard.
	static const int PAIRS_PER_TICK = 512;
	static const int PROBES_PER_TICK = 2;

	static bool Finite(float value)
	{
		return value >= -FLT_MAX && value <= FLT_MAX;
	}

	static bool PositionValid(vector point)
	{
		if (!Finite(point[0])) { return false; }
		if (!Finite(point[1])) { return false; }
		return Finite(point[2]);
	}

	static bool Token(string value)
	{
		if (value.Length() < 1 || value.Length() > 96) { return false; }
		string alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-.";
		int i = 0;
		while (i < value.Length())
		{
			string c = value.Substring(i, 1);
			if (alphabet.IndexOf(c) < 0) { return false; }
			i++;
		}
		return value != "." && value != "..";
	}

	static bool SettingsValid(HCEcologyRuntimeSettings settings)
	{
		if (!settings || settings.Version != 1) { return false; }
		if (settings.MaxActors < 1 || settings.MaxActors > HCEcologyLimits.ACTORS) { return false; }
		if (settings.MaxResources < 1 || settings.MaxResources > HCEcologyLimits.ACTORS) { return false; }
		if (settings.MaxPathQueries < 1 || settings.MaxPathQueries > 8) { return false; }
		if (settings.SampleSlice < 1 || settings.SampleSlice > HCEcologyLimits.ACTORS) { return false; }
		if (settings.TickMs < 1000 || settings.TickMs > 60000) { return false; }
		if (settings.FreshMs < settings.TickMs || settings.FreshMs > 60000) { return false; }
		if (settings.IntentMs < settings.TickMs || settings.IntentMs > 60000) { return false; }
		if (!Finite(settings.Radius)) { return false; }
		return settings.Radius >= 1 && settings.Radius <= 120;
	}

	static bool ClockValid(int nowMs)
	{
		// Reserve headroom for all configured observation/intent deadlines.
		return nowMs >= 0 && nowMs <= 2147483647 - 60000;
	}

	static bool TickDue(int nowMs, int lastMs, int interval)
	{
		if (!ClockValid(nowMs) || lastMs < 0 || nowMs <= lastMs) { return false; }
		if (interval < 1000 || interval > 60000) { return false; }
		return nowMs - lastMs >= interval;
	}

	static bool Fresh(int observed, int nowMs, int age)
	{
		if (observed < 0 || nowMs < observed || age < 0) { return false; }
		return nowMs - observed <= age;
	}

	static int ResourceKind(bool food, bool water, bool quantityKnown, float quantity, bool well, bool parent, bool ruined)
	{
		if (parent || ruined) { return 0; }
		if (well) { return 2; }
		if (quantityKnown)
		{
			if (!Finite(quantity) || quantity <= 0) { return 0; }
		}
		if (water && quantityKnown) { return 2; }
		if (food) { return 1; }
		return 0;
	}

	static string LocalId(string session, int serial)
	{
		if (!Token(session) || serial < 1 || serial >= 2147483647) { return ""; }
		return session + ":" + serial.ToString();
	}

	static bool CounterValid(int value)
	{
		return value >= 0 && value <= 1000000000;
	}

	static bool CheckpointValid(HCEcologyCheckpoint state, string world)
	{
		if (!state || state.Version != 1 || state.WorldName != world) { return false; }
		if (!Token(world) || !Token(state.SessionId)) { return false; }
		if (state.Revision < 1 || state.Revision > 1000000000) { return false; }
		return CounterValid(state.Samples) && CounterValid(state.PathQueries);
	}

	static bool CountersFit(HCEcologyCheckpoint state, int samples, int queries)
	{
		if (!state || samples < 0 || samples > HCEcologyLimits.ACTORS || queries < 0 || queries > 8) { return false; }
		if (!CounterValid(state.Samples) || !CounterValid(state.PathQueries)) { return false; }
		if (state.Revision >= 1000000000) { return false; }
		if (samples > 1000000000 - state.Samples) { return false; }
		return queries <= 1000000000 - state.PathQueries;
	}

	static bool CheckpointAdmission(bool pending, bool image, bool valid)
	{
		if (pending) { return false; }
		if (image) { return valid; }
		return !valid;
	}

	static bool Capacity(array<ref HCEcologyRouteIntent> intents, string actorId, string resourceId, int nowMs, int limit)
	{
		if (!intents || intents.Count() > 8 || limit < 1 || limit > 8) { return false; }
		int active = 0;
		int i = 0;
		while (i < intents.Count())
		{
			HCEcologyRouteIntent intent = intents.Get(i);
			if (!intent) { return false; }
			if (intent.ExpiresAtMs > nowMs)
			{
				active++;
				if (intent.ActorId == actorId || intent.ResourceId == resourceId) { return false; }
			}
			i++;
		}
		return active < limit;
	}

	static bool PathSummaryValid(int count, float length, float gapSq, float radius)
	{
		if (count < 2 || count > 64) { return false; }
		if (!Finite(length) || !Finite(gapSq) || !Finite(radius)) { return false; }
		if (length < 0 || gapSq < 0 || radius < 1 || radius > 120) { return false; }
		return length <= radius * 2 && gapSq <= 4;
	}

	static bool IntentValid(HCEcologyRouteIntent intent, string world, string session, int nowMs, float radius)
	{
		if (!intent || !intent.NativePath || intent.MovementAccepted) { return false; }
		if (intent.WorldName != world || intent.SessionId != session) { return false; }
		if (intent.ActorId.Length() < 1 || intent.ResourceId.Length() < 1) { return false; }
		if (intent.IssuedAtMs < 0 || nowMs < intent.IssuedAtMs || nowMs >= intent.ExpiresAtMs) { return false; }
		if (intent.ExpiresAtMs - intent.IssuedAtMs > 60000) { return false; }
		if (!PositionValid(intent.Origin) || !PositionValid(intent.Destination)) { return false; }
		return PathSummaryValid(intent.PathPoints, intent.PathLength, 0, radius);
	}
}
