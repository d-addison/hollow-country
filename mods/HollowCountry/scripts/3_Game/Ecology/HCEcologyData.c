// Unhooked, server-owned ecology DTOs.  Values are intentionally unset by
// default: an operator/provider must supply every world, session and budget.

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
