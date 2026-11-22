// The single shared engine-build matcher. Every Hollow Country script that
// binds, stamps or checks a build string goes through here and nowhere else.
//
// Native evidence: GetGame().GetVersion(out string) on the real engine returned
// "1.30.164289.70" (interior-sampler-001 census.json "version"), while the
// pinned, reviewed script snapshot is "1.30.164289". Exactly these two strings
// are admitted. No other suffix digits (".7x", ".700") or longer numbers
// ("1.30.1642890") have been observed, so they refuse until qualified; surrounding
// whitespace and the empty string refuse too. Compare is exact and case-sensitive.
// Wave 8 #165: alias-aware gates and a fixed per-gate refusal set.
// Source/synthetic qualification only; runtime acceptance remains pending.
class HCBuildIdentity
{
    static const string CANONICAL_BUILD = "1.30.164289";
    static const string NATIVE_FULL_BUILD = "1.30.164289.70";
    // Fixed bit set: legacy/shared (bit 1) + two XAI gates (bits 4, 16). Unknown caller tags
    // share bit 1, so arbitrary input can never grow a map or log without bound.
    // Shared across mission restarts; successes do not consume a bit.
    static int s_MismatchLogged = 0;

    static int GateMask(string gate)
    {
        if (gate == "xai_prerequisites") return 4;
        if (gate == "xai_site") return 16;
        return 1;
    }

    static string GateSuffix(string gate)
    {
        if (gate == "xai_prerequisites") return " gate=xai_prerequisites";
        if (gate == "xai_site") return " gate=xai_site";
        return "";
    }

    // Installed 3_Game/Global/Game.c:934,942 and 1_Core/proto/EnDebug.c:96.
    // These reads supply diagnostics only; missing game state cannot admit a gate.
    static string SeenWorld()
    {
        if (!GetGame()) return "";
        return GetGame().GetWorldName();
    }

    static string SeenBuild()
    {
        string build;
        if (!GetGame()) return "";
        GetGame().GetVersion(build);
        return build;
    }

    static bool Refuse(string build, string world, string reason, string gate = "shared")
    {
        int gateMask = GateMask(gate);
        if ((s_MismatchLogged & gateMask) != 0) return false;
        s_MismatchLogged = s_MismatchLogged | gateMask;
        Print("[HC Identity] build=" + build + " world=" + world + " accepted=0 reason=" + reason + GateSuffix(gate));
        return false;
    }

    // The only build string Hollow Country writes into journals and manifests.
    static string Canonical()
    {
        return CANONICAL_BUILD;
    }

    // True for exactly the pinned build or its one observed native full version.
    static bool Matches(string engineBuild, string gate = "shared")
    {
        if (engineBuild == CANONICAL_BUILD) return true;
        if (engineBuild == NATIVE_FULL_BUILD) return true;
        return Refuse(engineBuild, SeenWorld(), "build_mismatch", gate);
    }

    // Canonical text for an admitted build; any other text is returned untouched
    // so it still differs from every admitted build.
    static string Normalize(string build, string gate = "shared")
    {
        if (Matches(build, gate)) return CANONICAL_BUILD;
        return build;
    }

    // Equal once normalised. Empty text is never the same build.
    static bool SameBuild(string left, string right, string gate = "shared")
    {
        if (left == "") return Refuse(left, SeenWorld(), "build_mismatch", gate);
        // Equality of nonempty foreign stamps is retained; it is not build admission.
        if (left == right) return true;
        return Normalize(left, gate) == Normalize(right, gate);
    }

    // Map names are case-insensitive identities: "ChernarusPlus" == "chernarusplus".
    static string CanonicalWorld(string worldName)
    {
        string lowered = worldName;
        lowered.ToLower();
        return lowered;
    }

    // Case-normalised world equality; an empty world is never a match.
    static bool SameWorld(string left, string right)
    {
        if (left != "" && CanonicalWorld(left) == CanonicalWorld(right)) return true;
        return Refuse(SeenBuild(), right, "world_mismatch");
    }
}
