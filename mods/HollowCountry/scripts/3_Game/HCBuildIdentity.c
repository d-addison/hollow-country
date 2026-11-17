// The single shared engine-build matcher. Every Hollow Country script that
// binds, stamps or checks a build string goes through here and nowhere else.
//
// Native evidence: GetGame().GetVersion(out string) on the real engine returned
// "1.30.164289.70" (interior-sampler-001 census.json "version"), while the
// pinned, reviewed script snapshot is "1.30.164289". Exactly these two strings
// are admitted. No other suffix digits (".7x", ".700") or longer numbers
// ("1.30.1642890") have been observed, so they refuse until qualified; surrounding
// whitespace and the empty string refuse too. Compare is exact and case-sensitive.
class HCBuildIdentity
{
    static const string CANONICAL_BUILD = "1.30.164289";
    static const string NATIVE_FULL_BUILD = "1.30.164289.70";

    // The only build string Hollow Country writes into journals and manifests.
    static string Canonical()
    {
        return CANONICAL_BUILD;
    }

    // True for exactly the pinned build or its one observed native full version.
    static bool Matches(string engineBuild)
    {
        if (engineBuild == CANONICAL_BUILD) return true;
        if (engineBuild == NATIVE_FULL_BUILD) return true;
        return false;
    }

    // Canonical text for an admitted build; any other text is returned untouched
    // so it still differs from every admitted build.
    static string Normalize(string build)
    {
        if (Matches(build)) return CANONICAL_BUILD;
        return build;
    }

    // Equal once normalised. Empty text is never the same build.
    static bool SameBuild(string left, string right)
    {
        if (left == "") return false;
        return Normalize(left) == Normalize(right);
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
        if (left == "") return false;
        return CanonicalWorld(left) == CanonicalWorld(right);
    }
}
