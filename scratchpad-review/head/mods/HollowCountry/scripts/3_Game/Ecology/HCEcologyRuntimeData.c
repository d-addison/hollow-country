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
