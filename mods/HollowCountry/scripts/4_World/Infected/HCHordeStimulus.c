// Sensed, frozen clues only. Never use an actor's own vocalization as evidence
// about a threat. Native target entities do not enter this selector.
class HCHordeStimulus
{
    static bool PreferClue(HCInfectedClue candidate, HCInfectedClue previousClue, float now)
    {
        if (!candidate || !candidate.IsLive(now)) return false;
        if (!previousClue || !previousClue.IsLive(now)) return true;
        return HCInfectedPolicy.PreferStimulus(candidate.Observed, candidate.Provenance, candidate.Strength, previousClue.Observed, previousClue.Provenance, previousClue.Strength);
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
        HCInfectedClue chosen;
        if (actor.Visual && actor.Visual.Provenance == 2 && actor.Visual.IsLive(now))
            chosen = actor.Visual;
        if (hearing && actor.HeardExternally && actor.Heard)
        {
            if (actor.Heard.Provenance == 1 && PreferClue(actor.Heard, chosen, now))
                chosen = actor.Heard;
        }
        if (!chosen) return null;
        return FreezeClue(chosen);
    }
}
