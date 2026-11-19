// HC-17: compatibility seam only; no mailbox conversation, text scan or reply.
class HCCampMailbox
{
    static bool Keyword(string text) { return false; }
    static void Step(HCCampModule module, HCCampRecord camp, HCCampScan scan, int now) {}
}
