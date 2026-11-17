// Native observation preferences are enabled; unsupported movement stays explicit.
// These ceilings are work budgets, not biological targets or measured balance.
class HCEcologyRuntimeSettings
{
	int Version = 1;
	bool Enabled = true;
	int MaxActors = 32;
	int MaxResources = 32;
	int MaxPathQueries = 4;
	int TickMs = 5000;
	int FreshMs = 10000;
	int IntentMs = 10000;
	float Radius = 24.0;
}

// Diagnostic counters only. No live handles, IDs, assignment, position or
// process-relative clock is restored into another world/session.
class HCEcologyCheckpoint
{
	// Missing required JSON fields must remain invalid after deserialization.
	int Version;
	string WorldName;
	string SessionId;
	int Revision;
	int Samples = -1;
	int PathQueries = -1;
}

// Real native geometry evidence. Neither sensory eligibility nor movement proof.
class HCEcologyRouteIntent
{
	string WorldName;
	string SessionId;
	string ActorId;
	string ResourceId;
	int IssuedAtMs;
	int ExpiresAtMs;
	int ResourceKind;
	vector Origin;
	vector Destination;
	int PathPoints;
	float PathLength;
	bool NativePath = false;
	bool MovementAccepted = false;
}

// Durable cadence only: no entity identities, live positions or session clocks.
// Outcomes: 0=idle, 1=write-ahead pending, 2=command accepted (NOT arrival),
// 3=command rejected. Pending is preserved across restart and blocks replay.
class HCEcologyMigrationSchedule
{
	string Id;
	int PopulationKind;
	int IntervalSeconds;
	int NextDueUtc = -1;
	int Sequence = -1;
	// Conservative route reservations, never a live population census.
	// Retained on rejected retarget/restart because an old route may still run.
	int ReservedMembers = -1;
	bool Pending;
	int LastOutcome = -1;
}

class HCEcologyMigrationJournal
{
	int Version;
	string WorldName;
	int Revision;
	int LastUtc = -1;
	ref array<ref HCEcologyMigrationSchedule> Schedules = new array<ref HCEcologyMigrationSchedule>;
}

// Frozen resource presence for diagnostic route surveys. Coordinates never
// become a sensory ticket or an inventory/consumption transaction.
class HCEcologyResourceSample
{
	string WorldName;
	string Id;
	string SourceKind;
	int ResourceKind;
	int ObservedAtMs;
	vector Position;
	bool SensoryEligibility = false;
}
