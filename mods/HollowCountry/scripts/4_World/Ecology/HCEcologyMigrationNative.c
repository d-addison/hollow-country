// Inspected installed API root (local only):
// ~/.cache/hollow-country/native-scripts/scripts-1.30.164289/
// 2_GameLib/gameLib.c:4 GetGame; 3_Game/Global/Game.c:931 GetWorld,
// :934-938 GetWorldName(), :942 GetVersion(out string), :945 GetPlayers,
// :1120 IsServer. 3_Game/Entities/Object.c:238 GetBonePositionWS,
// :287 GetPosition, :517-520 IsAlive; 3_Game/human.c:1417 GetBoneIndexByName
// (missing bone returns -1). Native head use: 4_World/Static/
// MiscGameplayFunctions.c:746-754. 3_Game/Global/DayZPhysics.c:199 RaycastRV
// (declared out locals, nearest contact default); 1_Core/proto/EnConvert.c:210
// DistanceSq; EnMath3D.c:18 Vector; EnScript.c:380 Count, :399 Get,
// :743-750 set Count/Clear/Find; EnDebug.c:96 Print; EnSystem.c:397 FileExist.
// 3_Game/CE/CentralEconomy.c:585 GetCEGlobalInt, :746 GetCEApi. Utc delegates to
// authored HCGroupClock; native UTC readers are in
// 1_Core/proto/EnSystem.c:76,100. CanonicalWorld uses EnString.c:171 ToLower.
// These declarations support source authoring, never visibility acceptance.

class HCEcologyMigrationQualification
{
	protected static bool s_Checked;
	protected static bool s_OptIn;

	static bool Qualified()
	{
		return false;
	}

	static bool LocalAcceptanceOptIn()
	{
		return FileExist("$profile:HollowCountry/acceptance/ecology_migration.enable");
	}

	static bool Admitted()
	{
		if (Qualified()) { return true; }
		if (!s_Checked)
		{
			s_Checked = true;
			s_OptIn = LocalAcceptanceOptIn();
			if (s_OptIn) { Print("[HC Ecology] migration EXPERIMENTAL local acceptance opt-in; runtime acceptance PENDING"); }
			else { Print("[HC Ecology] migration not admitted; runtime acceptance PENDING"); }
		}
		return s_OptIn;
	}
}

// No ownership acquisition here. The Infected module supplies its already-owned
// pack and exact observed members. Public API only; native citations in REPORT.
class HCEcologyMigrationNative
{
	static bool AnimalDestinationSupported()
	{
		// AIAgent.c:6-7; AIGroupBehaviour.c:1-5,19-32; DayZAnimal.c:655-675.
		// No animal destination command. Input overrides are not path navigation.
		return false;
	}

	static string CurrentWorld()
	{
		if (!HCEcologyNative.Authority()) { return ""; }
		return HCBuildIdentity.CanonicalWorld(GetGame().GetWorldName());
	}

	static bool BuildSupported()
	{
		if (!HCEcologyNative.Authority()) { return false; }
		string build;
		GetGame().GetVersion(build);
		return HCBuildIdentity.Matches(build);
	}

	// Veto only: server player positions never become clues or destinations.
	// No facing/visibility-distance exemption. Oversize/unknown rosters refuse.
	// At most 32 observers * (6 members + destination) * 3 heights * 2 rays.
	// 100m proximity is a conservative provisional veto, not measured eyesight.
	static bool Unobserved(array<HCInfectedActor> members, HCInfectedClue clue)
	{
		if (!HCEcologyNative.Authority() || !members || !clue) { return false; }
		if (members.Count() < 1 || members.Count() > 6 || !HCEcologyRuntimeRules.PositionValid(clue.Origin)) { return false; }
		int validation = 0;
		while (validation < members.Count())
		{
			HCInfectedActor checked = members.Get(validation);
			if (!checked || !checked.InfectedEntity || !checked.InfectedEntity.IsAlive()) { return false; }
			if (!HCEcologyRuntimeRules.PositionValid(checked.InfectedEntity.GetPosition())) { return false; }
			validation++;
		}
		array<Man> observers = new array<Man>;
		GetGame().GetPlayers(observers);
		if (observers.Count() > 32) { return false; }
		int i = 0;
		while (i < observers.Count())
		{
			PlayerBase observer = PlayerBase.Cast(observers.Get(i));
			if (!observer) { return false; }
			if (!PointHidden(observer, null, clue.Origin)) { return false; }
			int j = 0;
			while (j < members.Count())
			{
				HCInfectedActor actor = members.Get(j);
				if (!PointHidden(observer, actor.InfectedEntity, actor.InfectedEntity.GetPosition())) { return false; }
				j++;
			}
			i++;
		}
		return true;
	}

	static bool PointHidden(PlayerBase observer, Object target, vector point)
	{
		// An observer attached to a parent (vehicle seat) hits its own vehicle first; never treat that as cover.
		if (observer.GetParent()) { return false; }
		vector origin = observer.GetPosition();
		if (!HCEcologyRuntimeRules.PositionValid(origin) || !HCEcologyRuntimeRules.PositionValid(point)) { return false; }
		if (vector.DistanceSq(origin, point) <= 10000) { return false; }
		int head = observer.GetBoneIndexByName("Head");
		if (head < 0) { return false; }
		vector eye = observer.GetBonePositionWS(head);
		if (!HCEcologyRuntimeRules.PositionValid(eye)) { return false; }
		if (vector.DistanceSq(origin, eye) > 16) { return false; }
		// Sample lower body, torso and head; a path/partial obstacle is not
		// proof the whole actor is hidden. Two intersection modes fail closed.
		if (!RayBlocked(observer, target, eye, point + Vector(0, 0.3, 0))) { return false; }
		if (!RayBlocked(observer, target, eye, point + Vector(0, 1.0, 0))) { return false; }
		return RayBlocked(observer, target, eye, point + Vector(0, 1.7, 0));
	}

	static bool RayBlocked(PlayerBase observer, Object target, vector eye, vector point)
	{
		vector contact;
		vector normal;
		int component;
		set<Object> hits = new set<Object>;
		bool hit = DayZPhysics.RaycastRV(eye, point, contact, normal, component, hits, null, observer, true, false, ObjIntersectView);
		if (!hit || !HCEcologyRuntimeRules.PositionValid(contact)) { return false; }
		if (target && hits.Find(target) >= 0) { return false; }
		if (vector.DistanceSq(eye, contact) >= vector.DistanceSq(eye, point)) { return false; }
		hits.Clear();
		hit = DayZPhysics.RaycastRV(eye, point, contact, normal, component, hits, null, observer, true, false, ObjIntersectFire);
		if (!hit || !HCEcologyRuntimeRules.PositionValid(contact)) { return false; }
		if (target && hits.Find(target) >= 0) { return false; }
		return vector.DistanceSq(eye, contact) < vector.DistanceSq(eye, point);
	}

	static int Utc()
	{
		// Shared reader brackets the UTC date and rejects rollback/midnight mixes.
		return HCGroupClock.Utc();
	}

	static int Ceiling(int populationKind)
	{
		if (!HCEcologyNative.Authority()) { return 0; }
		CEApi economy = GetCEApi();
		if (!economy) { return 0; }
		// CentralEconomy.c:574-585,746. Missing/wrong type returns int.MIN.
		if (populationKind == HCEcologyPopulation.ANIMAL) { return economy.GetCEGlobalInt("AnimalMaxCount"); }
		if (populationKind == HCEcologyPopulation.INFECTED) { return economy.GetCEGlobalInt("ZombieMaxCount"); }
		return 0;
	}

	static bool Owns(HCNativeInfectedPack pack, array<HCInfectedActor> members)
	{
		if (!pack || !members || members.Count() < 1 || members.Count() > 6) { return false; }
		if (pack.IsReleasing() || pack.IsReleaseQuarantined()) { return false; }
		int i = 0;
		while (i < members.Count())
		{
			HCInfectedActor actor = members.Get(i);
			if (!actor || !actor.InfectedEntity || !pack.OwnsMember(actor.InfectedEntity)) { return false; }
			int j = 0;
			while (j < i)
			{
				if (members.Get(j).InfectedEntity == actor.InfectedEntity) { return false; }
				j++;
			}
			i++;
		}
		return true;
	}

	static HCInfectedClue Choose(array<HCInfectedActor> members, float nativeNow, bool visualAdmitted, bool heardAdmitted)
	{
		if (!members || members.Count() < 1 || members.Count() > 6) { return null; }
		if (!HCEcologyRuntimeRules.Finite(nativeNow) || nativeNow < 0) { return null; }
		HCInfectedClue chosen;
		int i = 0;
		while (i < members.Count())
		{
			HCInfectedActor actor = members.Get(i);
			// Ecology cannot widen the Infected module's perception admission.
			// These source qualifications remain false until their owner accepts.
			HCInfectedClue candidate;
			if (actor && visualAdmitted && HCInfectedQualification.InvestigationAdmitted() && HCInfectedObservation.VisualSamplingAvailable())
			{
				if (actor.Visual && actor.Visual.Provenance == 2 && actor.Visual.IsLive(nativeNow)) { candidate = actor.Visual; }
			}
			if (actor && !candidate && heardAdmitted && HCInfectedQualification.SupplementaryChainsAdmitted() && actor.HeardExternally)
			{
				if (actor.Heard && actor.Heard.Provenance == 1 && actor.Heard.IsLive(nativeNow)) { candidate = actor.Heard; }
			}
			if (HCHordeStimulus.PreferClue(candidate, chosen, nativeNow)) { chosen = candidate; }
			i++;
		}
		if (!chosen) { return null; }
		return HCHordeStimulus.FreezeClue(chosen);
	}

	static int Move(HCNativeInfectedPack pack, HCInfectedClue clue, array<HCInfectedActor> members, float nativeNow)
	{
		if (!HCEcologyNative.Authority() || !BuildSupported() || !HCEcologyMigrationQualification.Admitted()) { return 0; }
		if (!HCInfectedQualification.NativePackRoutesAdmitted() || !HCInfectedQualification.HordeStimulusRoutesAdmitted()) { return 0; }
		if (!pack || !clue || !Owns(pack, members) || !Unobserved(members, clue)) { return 0; }
		// Retarget rechecks ownership, combat/injury, expiry, path geometry,
		// cooldown and bounded attempts; no Start/AddAgent/waypoint duplication.
		return pack.Retarget(clue, nativeNow);
	}
}
