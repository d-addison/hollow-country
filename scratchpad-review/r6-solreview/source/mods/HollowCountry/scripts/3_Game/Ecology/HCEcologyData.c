// Unhooked, server-owned ecology DTOs.  Values are intentionally unset by
// default: an operator/provider must supply every world, session and budget.

// Implementation ceilings, not population targets or balance defaults.
class HCEcologyLimits
{
	static const int ACTORS = 32;
	static const int ZONES = 32;
	static const int DIRECTIVES = 8;
	static const int HINTS = 32;
	static const int SPECIES = 16;
	static const int RESOURCES = 2;
	static const int TEXT = 128;
	static const int INT_MAX = 2147483647;
}

class HCEcologyCode
{
	static const int OK = 0;
	static const int INVALID = 1;
	static const int NATIVE_REJECTED = 2;
}

class HCEcologyPopulation
{
	static const int ANIMAL = 1;
	static const int INFECTED = 2;
}

class HCEcologyResource
{
	static const int FOOD = 1;
	static const int WATER = 2;
}

// Operator-authored seasonal/migration metadata.  A hint may annotate a real
// resource observation; it is never itself evidence that a resource exists.
class HCEcologyRouteHint
{
	string Id;
	string ZoneId;
	int PopulationKind;
	int ResourceKind;
	string Species;
	int StartsAtMs;
	int EndsAtMs;
}

class HCEcologyPolicy
{
	int SchemaVersion;
	bool Enabled;
	string WorldName;
	string SessionId;
	int MaxObservationAgeMs;
	int MaxZones;
	int MaxActors;
	int MaxDirectives;
	int CooldownMs;
	int HysteresisMs;
	ref array<ref HCEcologyRouteHint> RouteHints = new array<ref HCEcologyRouteHint>();
}

// Caller-observed facts are deliberately separate from operator policy.
class HCEcologyActorObservation
{
	string Id;
	int PopulationKind;
	string Species;
	int ObservedAtMs;
	bool Alive;
	bool NativeNavigationAvailable;
	ref array<int> EligibleResources = new array<int>();
}

class HCEcologyZoneObservation
{
	string Id;
	int PopulationKind;
	int ResourceKind;
	int ObservedAtMs;
	int ExpiresAtMs;
	bool Depleted;
	bool ReachabilityKnown;
	bool NativeReachable;
	ref array<string> EligibleSpecies = new array<string>();
}

class HCEcologyObservationBatch
{
	string WorldName;
	string SessionId;
	int ObservedAtMs;
	ref array<ref HCEcologyActorObservation> Actors = new array<ref HCEcologyActorObservation>();
	ref array<ref HCEcologyZoneObservation> Zones = new array<ref HCEcologyZoneObservation>();
}

// Capability facts are provided by the eventual native adapter, not inferred
// from configuration or from the presence of an entity identifier.
class HCEcologyCapabilities
{
	bool IsServerAuthority;
	bool ProviderAvailable;
	bool SupportsAnimalNavigation;
	bool SupportsInfectedNavigation;
}

class HCEcologyDirective
{
	string WorldName;
	string SessionId;
	string ActorId;
	string ZoneId;
	int PopulationKind;
	int ResourceKind;
	string RouteHintId;
	int ObservationAtMs;
	int IssuedAtMs;
	int HoldUntilMs;
	int CooldownUntilMs;
	int NextActorIndex;
	int NextZoneIndex;
}

// Native adapter receipt: copy the exact dispatched tuple, not a mutable
// reference or a positional acceptance flag. This is correlation, not proof
// of a native command; only the trusted server provider may report acceptance.
class HCEcologyReceipt
{
	string WorldName;
	string SessionId;
	string ActorId;
	string ZoneId;
	int PopulationKind;
	int ResourceKind;
	string RouteHintId;
	int ObservationAtMs;
	int IssuedAtMs;
	int HoldUntilMs;
	int CooldownUntilMs;
	int NextActorIndex;
	int NextZoneIndex;
	bool Accepted;
}

// Explicit provider observation that this exact assignment has ended.
// Missing actors in a bounded observation batch are NOT retirement evidence.
class HCEcologyRetirementReceipt
{
	string WorldName;
	string SessionId;
	string ActorId;
	string ZoneId;
	int AssignmentIssuedAtMs;
	int ObservedAtMs;
	bool NativeDirectiveEnded;
}

class HCEcologyAssignment
{
	string ActorId;
	string ZoneId;
	int IssuedAtMs;
	int HoldUntilMs;
	int CooldownUntilMs;
}

class HCEcologyState
{
	string WorldName;
	string SessionId;
	int LastNowMs;
	int LastObservationMs;
	int NextActorIndex;
	int NextZoneIndex;
	ref array<ref HCEcologyAssignment> Assignments = new array<ref HCEcologyAssignment>();
}
