// Sole CF call boundary. Installed scripts.pbo public API inspected in
// 3_Game/CommunityFramework/Utils/CF_Date.c: Timestamp and IsLeapYear.
// Original HC validation only; no provider implementation copied.
class HCXCFBridge
{
    // Restrict the signed 32-bit epoch to complete supported years. Conversion
    // performs at most 67 year steps, 11 month steps and 30 day steps in CF.
    // Returns -1 on refusal (including dates outside 1970-2037). Callers must
    // reject negative results before updating lockouts or persisting an epoch.
    static int HCTimestamp(int year, int month, int day, int hour, int minute, int second)
    {
        if (year < 1970 || year > 2037 || month < 1 || month > 12)
        {
            HCXExpansionBridge.HCRefuse("Timestamp", "UTC_DATE_RANGE");
            return -1;
        }
        int maxDay = 31;
        if (month == 4 || month == 6 || month == 9 || month == 11) { maxDay = 30; }
        if (month == 2)
        {
            maxDay = 28;
            if (CF_Date.IsLeapYear(year)) { maxDay = 29; }
        }
        if (day < 1 || day > maxDay || hour < 0 || hour > 23 || minute < 0 || minute > 59 || second < 0 || second > 59)
        {
            HCXExpansionBridge.HCRefuse("Timestamp", "UTC_TIME_RANGE");
            return -1;
        }
        return CF_Date.Timestamp(year, month, day, hour, minute, second);
    }
}
