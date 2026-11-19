// HC-16 / #143 supersedes LC-T413's imaginary visitors/refugees. Native camp
// signal classification may be observed; it is not proof that a party arrived.
// Physical arrivals/deaths belong to HC-10 custody + HCHoldouts body callbacks.
// Native scripts-1.30.164289: 3_Game/Global/Game.c:931 GetWorld;
// 3_Game/Global/World.c:28 GetDate; EnDebug.c:96 Print.
class HCCampVisitors
{
    static bool Dusk()
    {
        int year;
        int month;
        int day;
        int hour;
        int minute;
        GetGame().GetWorld().GetDate(year, month, day, hour, minute);
        return hour >= 17 && hour < 21;
    }

    static void Step(HCCampModule module, HCCampRecord camp, HCCampScan scan, bool burning, int now)
    {
        string signal = scan.Signal(burning);
        camp.Signal = signal;
        // Signal changes are not visitor-state transitions. Preserve the
        // refusal through restart; only acknowledge a successful durable write.
        if (camp.VisitorRefusal == "VISITOR_BODY_NOT_OBSERVED") { return; }
        string previousRefusal = camp.VisitorRefusal;
        camp.VisitorRefusal = "VISITOR_BODY_NOT_OBSERVED";
        camp.LastSignal = now;
        if (!module.Commit(now))
        {
            camp.VisitorRefusal = previousRefusal;
            return;
        }
        Print("[HC Plan] HC-16 camp=" + camp.Id + " level=" + camp.Tier.ToString() + " supply=0 roles=0 state=refused refusal=VISITOR_BODY_NOT_OBSERVED runtime=PENDING");
        // Legacy Neighbours fields are preserved for migration only. No visit,
        // settlement, combat, loss, notification or world fact is manufactured.
    }
}
