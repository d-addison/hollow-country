// Finite, server-owned reward pool for reviewed event caches. Vanilla class names only.
class HCEventRewardEntry
{
    string Type;
    int Count = 0;
}
class HCEventRewardPool
{
    int Version = 1;
    int MaxCaches = 3;
    int ItemsPerCache = 4;
    ref array<ref HCEventRewardEntry> Entries = new array<ref HCEventRewardEntry>();
}
// One journaled grant decision. It is spent when it is returned, never replayed.
class HCEventRewardPlan
{
    string SiteId;
    int Boot = 0;
    ref array<string> Items = new array<string>();
}
