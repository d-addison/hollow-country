// LC-T411 / #104 abstract only. scripts-1.30.164289 native references:
// 1_Core/proto/EnMath.c:427 Floor, :553 Min; EnConvert.c:30 int.ToString;
// EnScript.c:380,385,394,407,463 arrays; EnDebug.c:96 Print.
// HCWorldModule.HCWorldStep passes its owned ledger before updating Meta.LastTick;
// the existing world store persists strength/territory and the daily watermark
// in ONE image. No second-store replay window, body, item, sound or RPC.
class HCFactionConflict : HCModule
{
    protected static bool s_Active;
    override string GetName() { return "FactionConflict"; }
    override bool IsEnabled(HCSettings settings) { return settings && settings.EnableEncounters; }
    override void OnStart(HCSettings settings)
    {
        Print(HCV2Admission.Line("FactionConflict", true, "EXP-S4", HCV2Gates.Qualified("EXP-S4")));
        s_Active = true;
    }
    override void OnStop() { s_Active = false; }

    static string Cell(vector position)
    {
        int x = Math.Floor(position[0] / 1000);
        int z = Math.Floor(position[2] / 1000);
        return x.ToString() + ":" + z.ToString();
    }

    // Authored off-screen starting claims, not sightings of NPCs. No claim
    // is recreated once a faction has lost it or reached zero strength.
    static void Seed(HCWorldData data, HCWorldFaction faction, int now)
    {
        if (faction.LastRegrowth != 0) { return; }
        faction.LastRegrowth = now;
        if (faction.Territory.Count() > 0) { return; }
        for (int placeIndex = 0; placeIndex < data.Places.Count(); placeIndex++)
        {
            bool claim = false;
            if (faction.Id == "locals" && placeIndex % 4 == 0) { claim = true; }
            if (faction.Id == "volunteers" && placeIndex % 4 == 1) { claim = true; }
            if (faction.Id == "scavengers" && placeIndex % 4 == 2) { claim = true; }
            if (faction.Id == "travellers" && placeIndex % 4 == 3) { claim = true; }
            if (faction.Id == "raiders" && placeIndex % 3 == 1) { claim = true; }
            string cell = Cell(data.Places[placeIndex].Position);
            if (claim && faction.Territory.Find(cell) < 0 && faction.Territory.Count() < HCWorldLimits.TERRITORY) { faction.Territory.Insert(cell); }
        }
    }

    // A recently fought-over place rests for seven real days. Bounded ring
    // contents, expiry and future timestamps are checked without player data.
    static bool HCRecentlyContested(HCWorldData data, string placeId, int now)
    {
        foreach (HCWorldSiteMemory memory : data.SiteMemory)
        {
            bool sameSite = memory.PlaceId == placeId && memory.Event == "RAIDED";
            bool current = memory.At <= now && memory.Expires > now;
            if (sameSite && current) { return true; }
        }
        return false;
    }

    static void Tick(HCWorldModule world, HCWorldData data, int now)
    {
        if (!s_Active || !world || !data || now < data.Meta.Epoch) { return; }
        // Five fixed factions, each with <=64 claims. Seeding runs once;
        // regrowth is <=1 per TWO real days and cannot resurrect extinction.
        foreach (HCWorldFaction growing : data.Factions)
        {
            Seed(data, growing, now);
            if (now - growing.LastRegrowth >= 2 * HCWorldLimits.DAY)
            {
                if (growing.Strength > 0 && growing.Strength < HCWorldLimits.STRENGTH) { world.AdjustStrength(growing.Id, 1); }
                growing.LastRegrowth = now;
            }
        }
        int today = HCWorldClock.Day(data, now);
        int previousDay = HCWorldClock.Day(data, data.Meta.LastTick);
        if (today <= previousDay) { return; }
        // One shared cell/day, no downtime catch-up, no per-minute attrition.
        // Epoch/day/place index give a stable seeded roll without consuming the
        // engine's random stream. A restart reloads the same committed outcome.
        int start = today % data.Places.Count();
        for (int offset = 0; offset < data.Places.Count(); offset++)
        {
            int placeIndex = (start + offset) % data.Places.Count();
            HCWorldPlace place = data.Places[placeIndex];
            if (HCRecentlyContested(data, place.Id, now)) { continue; }
            string cell = Cell(place.Position);
            for (int first = 0; first < data.Factions.Count(); first++)
            {
                HCWorldFaction left = data.Factions[first];
                if (left.Strength < 1 || left.Territory.Find(cell) < 0) { continue; }
                for (int second = first + 1; second < data.Factions.Count(); second++)
                {
                    HCWorldFaction right = data.Factions[second];
                    if (right.Strength < 1 || right.Territory.Find(cell) < 0 || world.Relation(left.Id, right.Id) != -1) { continue; }
                    int roll = (data.Meta.Epoch % 97 + today % 97 * 17 + placeIndex * 7) % 13;
                    HCWorldFaction winner = left;
                    HCWorldFaction loser = right;
                    if (right.Strength + roll > left.Strength + 6) { winner = right; loser = left; }
                    // Losses consume finite strength; combat never creates it.
                    world.AdjustStrength(loser.Id, -1);
                    if (roll % 3 == 0 && winner.Strength > 1) { world.AdjustStrength(winner.Id, -1); }
                    int claimIndex = loser.Territory.Find(cell);
                    if (claimIndex >= 0) { loser.Territory.Remove(claimIndex); }
                    // Finite strength zero removes all remaining abstract claims.
                    if (loser.Strength == 0) { loser.Territory.Clear(); }
                    world.AddFact("faction_clash", place.Id, 2);
                    world.AddFact(winner.Id + "_pushed_" + loser.Id, place.Id, 2);
                    HCWorldSiteMemory memory = new HCWorldSiteMemory;
                    memory.PlaceId = place.Id;
                    memory.Event = "RAIDED";
                    memory.At = now;
                    memory.Expires = now + HCWorldLimits.FACT_LIFETIME;
                    data.AppendMemory(memory);
                    Print("[HollowCountry] V2 faction conflict " + winner.Id + " pushed " + loser.Id + " out of " + place.Name);
                    return;
                }
            }
        }
    }
}

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        Register(new HCFactionConflict);
    }
}
