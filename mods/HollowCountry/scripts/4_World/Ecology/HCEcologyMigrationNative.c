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
		return GetGame().GetWorldName();
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
			if (actor && visualAdmitted && HCInfectedQualification.InvestigationQualified() && HCInfectedObservation.VisualSamplingAvailable())
			{
				if (actor.Visual && actor.Visual.Provenance == 2 && actor.Visual.IsLive(nativeNow)) { candidate = actor.Visual; }
			}
			if (actor && !candidate && heardAdmitted && HCInfectedQualification.SupplementaryChainsQualified() && actor.HeardExternally)
			{
				if (actor.Heard && actor.Heard.Provenance == 1 && actor.Heard.IsLive(nativeNow)) { candidate = actor.Heard; }
			}
			if (HCHordeStimulus.PreferClue(candidate, chosen, nativeNow)) { chosen = candidate; }
			i++;
		}
		if (!chosen) { return null; }
		return HCHordeStimulus.FreezeClue(chosen);
	}

	static int Move(HCNativeInfectedPack pack, HCInfectedClue clue, float nativeNow)
	{
		if (!HCEcologyNative.Authority() || !HCEcologyMigrationQualification.Admitted()) { return 0; }
		if (!HCInfectedQualification.NativePackRoutesQualified() || !HCInfectedQualification.HordeStimulusRoutesQualified()) { return 0; }
		if (!pack || !clue) { return 0; }
		// Retarget rechecks ownership, combat/injury, expiry, path geometry,
		// cooldown and bounded attempts; no Start/AddAgent/waypoint duplication.
		return pack.Retarget(clue, nativeNow);
	}
}
