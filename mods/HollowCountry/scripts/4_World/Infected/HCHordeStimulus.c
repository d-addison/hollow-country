// Shared stimulus contract for individual investigations and cohort selection.
// Source adapters supply a frozen Origin, Observed, Expires, Strength (0.2..1),
// Provenance, Hops (0..2), and EventId. Strength is normalized evidence strength,
// never measured sound pressure. No category grants a new perception capability.
//
// Priority: qualified live visual observation (2) > admitted live heard cue (1)
// > retained memory > idle. IsLive validates time, TTL, provenance, strength and
// hops. Expired/unknown/invalid evidence is memory, never a routing destination.
// Precedence is deliberate: "live" means inside its TTL, so a stale-but-live
// visual clue beats a fresher sound; recency only orders clues of one category.
// The two-client perception check of this precedence is pending, not accepted.
// A retained visual clue is not a currently visible threat: provenance alone
// cannot keep it eligible after expiry or establish continued native sight.
// Provenance 2 must come from a qualified observation adapter; a retained native
// target, ray geometry, or this selector cannot assert that qualification. Its
// bounded observation ticket must expire or be invalidated when unsupported;
// selection never refreshes it. Native perception qualification remains pending.
//
// Supported heard category is actual local native infected voice only. The seed
// is not external hearing; every relay preserves root expiry and decays strength.
// Other native noises keep native handling until a measured gap justifies an
// adapter. No gunshot/rummage adapter or duplicate noise emission is added here.
// Only authored DTO/policy calls below; no native perception/coordinate API.
enum HCStimulusCategory
{
    HC_STIMULUS_NONE = 0,
    HC_STIMULUS_MEMORY = 1,
    HC_STIMULUS_HEARD = 2,
    HC_STIMULUS_VISUAL = 3
}

enum HCStimulusReason
{
    HC_STIMULUS_NO_ADMISSIBLE_CLUE = 0,
    HC_STIMULUS_SELECTED_VISUAL = 1,
    HC_STIMULUS_SELECTED_HEARD = 2,
    HC_STIMULUS_RETAINED_ONLY = 3
}

class HCHordeStimulus
{
    static int Category(HCInfectedClue candidate, float now)
    {
        if (!candidate) return HCStimulusCategory.HC_STIMULUS_NONE;
        if (!candidate.IsLive(now)) return HCStimulusCategory.HC_STIMULUS_MEMORY;
        if (candidate.Provenance == 2) return HCStimulusCategory.HC_STIMULUS_VISUAL;
        if (candidate.Provenance == 1) return HCStimulusCategory.HC_STIMULUS_HEARD;
        return HCStimulusCategory.HC_STIMULUS_MEMORY;
    }

    static bool PreferClue(HCInfectedClue candidate, HCInfectedClue previousClue, float now)
    {
        int candidateCategory = Category(candidate, now);
        if (candidateCategory <= HCStimulusCategory.HC_STIMULUS_MEMORY) return false;
        int previousCategory = Category(previousClue, now);
        if (previousCategory <= HCStimulusCategory.HC_STIMULUS_MEMORY) return true;
        if (candidateCategory != previousCategory) return candidateCategory > previousCategory;
        if (candidate.Observed != previousClue.Observed) return candidate.Observed > previousClue.Observed;
        return candidate.Strength > previousClue.Strength;
    }

    // Borrowed chosen clue or null, plus a reason on every exit. The Module
    // passes admission AND HeardExternally; no self-voice may become a threat.
    // Slots are typed by provenance, not by which field happens to hold a clue.
    static HCInfectedClue SelectClue(HCInfectedClue visual, HCInfectedClue heard, bool admitExternalHeard, float now, out int reason)
    {
        reason = HCStimulusReason.HC_STIMULUS_NO_ADMISSIBLE_CLUE;
        int visualCategory = Category(visual, now);
        if (visualCategory == HCStimulusCategory.HC_STIMULUS_VISUAL)
        {
            reason = HCStimulusReason.HC_STIMULUS_SELECTED_VISUAL;
            return visual;
        }
        int heardCategory = HCStimulusCategory.HC_STIMULUS_NONE;
        if (admitExternalHeard)
            heardCategory = Category(heard, now);
        if (heardCategory == HCStimulusCategory.HC_STIMULUS_HEARD)
        {
            reason = HCStimulusReason.HC_STIMULUS_SELECTED_HEARD;
            return heard;
        }
        if (visualCategory == HCStimulusCategory.HC_STIMULUS_MEMORY || heardCategory == HCStimulusCategory.HC_STIMULUS_MEMORY)
            reason = HCStimulusReason.HC_STIMULUS_RETAINED_ONLY;
        return null;
    }

    static HCInfectedClue FreezeClue(HCInfectedClue candidate)
    {
        HCInfectedClue frozenClue = new HCInfectedClue;
        frozenClue.Origin = candidate.Origin;
        frozenClue.Observed = candidate.Observed;
        frozenClue.Expires = candidate.Expires;
        frozenClue.Strength = candidate.Strength;
        frozenClue.Provenance = candidate.Provenance;
        frozenClue.Hops = candidate.Hops;
        frozenClue.EventId = candidate.EventId;
        return frozenClue;
    }

    static HCInfectedClue ChooseClue(HCInfectedActor actor, float now, bool hearing)
    {
        if (!actor) return null;
        int reason;
        HCInfectedClue chosen = SelectClue(actor.Visual, actor.Heard, hearing && actor.HeardExternally, now, reason);
        if (!chosen) return null;
        return FreezeClue(chosen);
    }
}
