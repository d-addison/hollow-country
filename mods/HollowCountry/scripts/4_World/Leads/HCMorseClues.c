// HC-20 / #148. Read-only migration of the old Morse anti-replay ledger.
// Never delete/reset/rewrite it: honour valid global/per-recipient cooldowns.
// Native scripts-1.30.164289: 1_Core/proto/EnSystem.c:397 FileExist,
// :525 MakeDirectory; 3_Game/tools/JsonFileLoader.c:69 LoadData;
// 1_Core/proto/EnScript.c:380 Count, :470 RemoveOrdered; EnDebug.c:96 Print.
// Bounded 4096-byte IO uses HCGroupIO. Legacy faults impose no cooldown.
class HCMorseReceipt
{
    int Fingerprint;
    int At;
}

class HCMorseRateData
{
    int Version = 1;
    int LastUTC;
    // Only rate receipts, no positions, inventory, standing or readable IDs.
    // Hash collisions conservatively share a cooldown; at most six rows.
    ref array<ref HCMorseReceipt> Receipts = new array<ref HCMorseReceipt>;
}

class HCMorseRateStore
{
    protected string m_Path = "$profile:HollowCountry/morse-rates.json";
    protected string m_Temp = "$profile:HollowCountry/morse-rates.json.tmp";
    protected string m_Backup = "$profile:HollowCountry/morse-rates.json.bak";
    protected ref HCMorseRateData m_Data;
    protected bool m_Fault;

    bool Fail()
    {
        if (!m_Fault)
        {
            Print("[HC Plan] HC-20 radio=environmental morse=folded legacy_cooldown=ignored reason=legacy_rate_store_fault runtime=PENDING; preserve profile files");
        }
        m_Fault = true;
        return false;
    }

    bool Open()
    {
        int now = HCWorldClock.UTC();
        if (now < 1 || FileExist(m_Temp) || FileExist(m_Backup)) { return Fail(); }
        if (!FileExist("$profile:HollowCountry") && !MakeDirectory("$profile:HollowCountry")) { return Fail(); }
        if (!FileExist(m_Path))
        {
            m_Data = new HCMorseRateData;
            return true;
        }
        string text;
        string error;
        if (!HCGroupIO.Read(m_Path, 4096, text) || !JsonFileLoader<HCMorseRateData>.LoadData(text, m_Data, error)) { return Fail(); }
        if (!m_Data || m_Data.Version != 1 || !m_Data.Receipts || m_Data.Receipts.Count() > 6 || m_Data.LastUTC < 1 || m_Data.LastUTC > now) { return Fail(); }
        int previousAt;
        foreach (HCMorseReceipt receipt : m_Data.Receipts)
        {
            if (!receipt || receipt.At < 1 || receipt.At < previousAt || receipt.At > m_Data.LastUTC) { return Fail(); }
            previousAt = receipt.At;
        }
        // Every valid legacy image reserved a receipt before delivery, including
        // its newest timestamp. Malformed images log once and impose no cooldown.
        if (m_Data.Receipts.Count() < 1 || previousAt != m_Data.LastUTC) { return Fail(); }
        return true;
    }

    static bool RateAllowed(int now, int playerAt, int recentCount)
    {
        if (now < 1 || playerAt > now || recentCount < 0 || recentCount >= 6) { return false; }
        if (playerAt > 0 && now - playerAt < 1800) { return false; }
        return true;
    }

    bool Allowed(int fingerprint, int now)
    {
        if (m_Fault) { return true; }
        if (!m_Data || now < m_Data.LastUTC) { return false; }
        // Space rare clues out; stalls/restarts never catch up with a burst.
        if (m_Data.LastUTC > 0 && now - m_Data.LastUTC < 600) { return false; }
        int playerAt;
        int receiptIndex = m_Data.Receipts.Count() - 1;
        while (receiptIndex >= 0)
        {
            HCMorseReceipt recent = m_Data.Receipts[receiptIndex];
            if (now - recent.At >= 3600) { m_Data.Receipts.RemoveOrdered(receiptIndex); }
            else
            {
                if (recent.Fingerprint == fingerprint && recent.At > playerAt) { playerAt = recent.At; }
            }
            receiptIndex = receiptIndex - 1;
        }
        return RateAllowed(now, playerAt, m_Data.Receipts.Count());
    }

}

// HC-20: unregistered compatibility shell. There is no second producer,
// target scan, timer, RPC or save loop.
// HCRadioChatter consumes delayed shared facts, including existing morse_lead.
class HCMorseClues : HCModule
{
    protected ref HCOperationalStatus m_Status = new HCOperationalStatus;

    override string GetName() { return "Morse"; }
    override bool IsEnabled(HCSettings settings)
    {
        m_Status.HCPublish("off", "folded_into_radio");
        return false;
    }
    override HCOperationalStatus HCGetOperationalStatus() { return m_Status; }
}
