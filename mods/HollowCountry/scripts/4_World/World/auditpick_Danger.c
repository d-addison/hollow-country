// #144 remembered danger for scavenging routes, perceived clues only.
// A clue is written ONLY by the party's own experience (a combat abort or a lost
// member of this party); it expires and the table is capped. It never stores a
// player identity or a live player position, and nothing here reads players.
// Native scripts-1.30.164289: 1_Core/proto/EnScript.c:380 Count, :407 Insert,
// :470 RemoveOrdered. Runtime acceptance PENDING.
class HCPickDanger
{
    ref array<string> Routes = new array<string>;
    ref array<string> Kinds = new array<string>;
    ref array<int> Times = new array<int>;

    void HCPrune(int now, int ttl)
    {
        int index = Routes.Count() - 1;
        while (index >= 0)
        {
            if (now - Times[index] >= ttl)
            {
                Routes.RemoveOrdered(index);
                Kinds.RemoveOrdered(index);
                Times.RemoveOrdered(index);
            }
            index = index - 1;
        }
    }

    // Oldest clue is dropped at the cap; a repeated clue refreshes in place.
    void HCNote(string routeId, string kind, int now, int ttl, int cap)
    {
        if (routeId == "" || kind == "" || now < 1 || cap < 1) { return; }
        HCPrune(now, ttl);
        for (int known = 0; known < Routes.Count(); known++)
        {
            if (Routes[known] == routeId && Kinds[known] == kind)
            {
                Times[known] = now;
                return;
            }
        }
        while (Routes.Count() >= cap)
        {
            Routes.RemoveOrdered(0);
            Kinds.RemoveOrdered(0);
            Times.RemoveOrdered(0);
        }
        Routes.Insert(routeId);
        Kinds.Insert(kind);
        Times.Insert(now);
    }

    // Kind of the first unexpired clue for this route, else "".
    string HCFresh(string routeId, int now, int ttl)
    {
        for (int index = 0; index < Routes.Count(); index++)
        {
            if (Routes[index] == routeId && now - Times[index] < ttl) { return Kinds[index]; }
        }
        return "";
    }

    int HCCount() { return Routes.Count(); }
}
