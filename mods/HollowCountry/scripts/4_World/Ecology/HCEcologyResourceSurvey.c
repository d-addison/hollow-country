// Experimental diagnostic resource survey, bounded by caller's supplied points.
// Installed 3_Game/Global/Game.c:1196-1197 only classify terrain, not a usable shore.
// :934-938 GetWorldName; HCBuildIdentity uses 1_Core/proto/EnString.c:171 ToLower.
class HCEcologyResourceSurvey
{
	// HC-49: consume HC-15's server snapshot, never discover/spawn another cohort.
	// Native scripts-1.30.164289: Object.c:215/517 pending deletion/alive;
	// 3_Game/Entities/DayZAnimal.c:60 CanBeSkinned; EntityAI.c:483 IsSkinned.
	// ActionSkinning.c:64-80 marks spent BEFORE native organ creation/deletion.
	// Neither a skinnable body nor proximity proves predator feeding or CE ownership.
	static AnimalBase Carcass(HCWildlifeFact fact)
	{
		if (!HCEcologyNative.Authority() || !fact || !fact.Carcass) { return null; }
		AnimalBase animal = AnimalBase.Cast(fact.Subject);
		if (CarcassSupply(animal) != "native_skinnable") { return null; }
		return animal;
	}

	static string CarcassSupply(EntityAI resource)
	{
		if (!HCEcologyNative.Authority() || !resource) { return "unavailable"; }
		// Skinning and scheduled deletion may be visible in the same tick.
		if (resource.IsSkinned()) { return "depleted"; }
		if (resource.IsPendingDeletion()) { return "unavailable"; }
		if (resource.IsAlive()) { return "unknown"; }
		if (!resource.CanBeSkinned()) { return "unavailable"; }
		return "native_skinnable";
	}

	static HCEcologyResourceSample Pond(vector point, string id, int nowMs)
	{
		if (!HCEcologyNative.Authority() || !HCEcologyMigrationQualification.Admitted()) { return null; }
		if (!HCEcologyRuntimeRules.PositionValid(point) || !HCEcologyRuntimeRules.Token(id)) { return null; }
		if (!HCEcologyRuntimeRules.ClockValid(nowMs)) { return null; }
		if (GetGame().SurfaceIsSea(point[0], point[2]) || !GetGame().SurfaceIsPond(point[0], point[2])) { return null; }
		HCEcologyResourceSample sample = new HCEcologyResourceSample;
		sample.WorldName = HCBuildIdentity.CanonicalWorld(GetGame().GetWorldName());
		sample.Id = id;
		sample.SourceKind = "pond";
		sample.ResourceKind = 2;
		sample.ObservedAtMs = nowMs;
		sample.Position = point;
		return sample;
	}

	static HCEcologyResourceSample ObjectSample(EntityAI resource, string id, int nowMs)
	{
		if (!HCEcologyNative.Authority() || !HCEcologyMigrationQualification.Admitted() || !resource) { return null; }
		if (!HCEcologyRuntimeRules.Token(id) || !HCEcologyRuntimeRules.ClockValid(nowMs)) { return null; }
		int kind = HCEcologyNative.SampleResource(resource);
		if (kind == 0) { return null; }
		HCEcologyResourceSample sample = new HCEcologyResourceSample;
		sample.WorldName = HCBuildIdentity.CanonicalWorld(GetGame().GetWorldName());
		sample.Id = id;
		sample.SourceKind = "object";
		sample.ResourceKind = kind;
		sample.ObservedAtMs = nowMs;
		sample.Position = resource.GetPosition();
		return sample;
	}
}
