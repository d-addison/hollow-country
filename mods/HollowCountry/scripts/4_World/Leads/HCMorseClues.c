// Issue #62, LC-STY-02/03 and LC-T307 channel, EXP-S2. Owner 2026-11-17:
// EnableLeads admits runtime; the experiment verdict is diagnostic, not proof.
// Native evidence in scripts-1.30.164289:
// 4_World/Entities/ItemBase/TransmitterBase/PersonalRadio.c:1,5,6;
// 4_World/Entities/ItemBase/TransmitterBase.c:96-116 OnWorkStart/Stop;
// 4_World/Entities/Core/Inherited/InventoryItem.c:18 GetTunedFrequency, :22 IsReceiving;
// 4_World/Classes/UserActionsComponent/Actions/Interact/ActionTuneFrequencyOnGround.c:17 (MHz).
// 4_World/Entities/ManBase/PlayerBase.c:2394,2399,2638,6733 quickbar/disconnect/hands;
// 3_Game/Entities/EntityAI.c:882,3409 hierarchy/GetCompEM;
// 3_Game/tools/Component/ComponentEnergyManager.c:884,925 switched-on/working;
// 3_Game/Entities/Man.c:21 GetIdentity; Entities/Object.c:215,517 deletion/alive;
// 3_Game/Global/Game.c:945,1120 GetPlayers/IsServer;
// 3_Game/gameplay.c:104,117,368 ScriptRPC/targeted Send/identity GetId;
// 1_Core/proto/EnEntity.c:518 GetID; EnString.c:199,223 Length/Hash;
// 1_Core/proto/EnMath.c:427 Floor; EnScript.c:94,380,399,407,470 Cast/arrays;
// 1_Core/proto/Serializer.c:57 Write; 3_Game/Entities/Object.c:1219 IsRuined;
// 1_Core/proto/EnSystem.c:397,525,528,531 file/directory/copy/delete;
// 3_Game/tools/JsonFileLoader.c:69,85 LoadData/MakeData; EnDebug.c:96 Print.
// Reuse HCWorldClock.UTC and HCGroupIO bounded reads/write-readback.
// Native has no RenameFile: use HCWorldStore's temp/backup/copy/readback intent
// protocol, rejecting any interrupted temp on load, never restoring older caps.
// Inspecting 3_Game/MorseCodeConverter.c:6-7 found BroadcastTextAsMorse sends to
// ALL players. It and Land_Underground/BunkerBroadcastProxy are not used here.
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
        m_Fault = true;
        Print("[HollowCountry] V2 morse unavailable: rate store fault; preserve profile files");
        return false;
    }

    bool Open()
    {
        int now = HCWorldClock.UTC();
        if (now < 1 || FileExist(m_Temp)) { return Fail(); }
        if (!FileExist("$profile:HollowCountry") && !MakeDirectory("$profile:HollowCountry")) { return Fail(); }
        if (!FileExist(m_Path))
        {
            if (FileExist(m_Backup)) { return Fail(); }
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
        // Every saved image reserves a receipt before the RPC, including the
        // newest timestamp. Malformed images cannot reset a budget silently.
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
        if (m_Fault || !m_Data || now < m_Data.LastUTC) { return false; }
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
            receiptIndex--;
        }
        return RateAllowed(now, playerAt, m_Data.Receipts.Count());
    }

    bool Same(string path, string expected)
    {
        string actual;
        return HCGroupIO.Read(path, 4096, actual) && actual == expected;
    }

    bool Reserve(int fingerprint, int now)
    {
        if (!Allowed(fingerprint, now)) { return false; }
        HCMorseReceipt receipt = new HCMorseReceipt;
        receipt.Fingerprint = fingerprint;
        receipt.At = now;
        m_Data.Receipts.Insert(receipt);
        m_Data.LastUTC = now;
        string image;
        string error;
        if (!JsonFileLoader<HCMorseRateData>.MakeData(m_Data, image, error) || !HCGroupIO.WriteNew(m_Temp, image, 4096)) { return Fail(); }
        if (FileExist(m_Path))
        {
            string prior;
            if (!HCGroupIO.Read(m_Path, 4096, prior)) { return Fail(); }
            if (FileExist(m_Backup) && !DeleteFile(m_Backup)) { return Fail(); }
            if (!CopyFile(m_Path, m_Backup) || !Same(m_Backup, prior)) { return Fail(); }
            if (!DeleteFile(m_Path)) { return Fail(); }
        }
        if (!CopyFile(m_Temp, m_Path) || !Same(m_Path, image) || !DeleteFile(m_Temp)) { return Fail(); }
        return true;
    }
}

class HCMorseClues : HCModule
{
    protected ref HCMorseRateStore m_Rates;
    protected float m_Elapsed;
    protected int m_PlayerCursor;
    protected int m_TargetCursor;
    protected bool m_Running;
    protected bool m_AdmissionPrinted;

    override string GetName() { return "Morse"; }
    override bool IsEnabled(HCSettings settings) { return settings && settings.EnableLeads; }

    override void OnStart(HCSettings settings)
    {
        if (m_Running || !IsEnabled(settings) || !GetGame().IsServer()) { return; }
        if (!m_AdmissionPrinted)
        {
            Print(HCV2Admission.Line("Morse", true, "EXP-S2", HCV2Gates.Qualified("EXP-S2")));
            m_AdmissionPrinted = true;
        }
        m_Rates = new HCMorseRateStore;
        m_Running = m_Rates.Open();
        m_Elapsed = 0;
        m_PlayerCursor = 0;
        m_TargetCursor = 0;
        if (m_Running) { Print("[HollowCountry] V2 morse ready frequency=" + HCRadioChatter.Frequency("travellers").ToString() + " MHz; tuned holders only"); }
    }

    static bool Receiving(EntityAI item, PlayerBase player)
    {
        PersonalRadio radio = PersonalRadio.Cast(item);
        if (!radio || radio.IsRuined() || radio.GetHierarchyRootPlayer() != player || !radio.GetCompEM()) { return false; }
        if (!radio.GetCompEM().IsSwitchedOn() || !radio.GetCompEM().IsWorking() || !radio.IsReceiving()) { return false; }
        float frequency = HCRadioChatter.Frequency("travellers");
        float tuned = radio.GetTunedFrequency();
        return tuned > frequency - 0.01 && tuned < frequency + 0.01;
    }

    static bool Holder(PlayerBase player)
    {
        if (!player || !player.IsAlive() || player.IsPendingDeletion() || player.IsPlayerDisconnected()) { return false; }
        if (Receiving(player.GetItemInHands(), player)) { return true; }
        int quickSlots = player.GetQuickBarSize();
        if (quickSlots > 10) { quickSlots = 10; }
        for (int slotIndex = 0; slotIndex < quickSlots; slotIndex++)
        {
            if (Receiving(player.GetQuickBarEntity(slotIndex), player)) { return true; }
        }
        return false;
    }

    protected HCEventMission Target()
    {
        HCEventModule events = HCEventModule.Get();
        if (!events || !events.Runtime()) { return null; }
        HCEventContext context = events.Context();
        if (!context || context.WorldName != "chernarusplus" || !events.Runtime().Allowed(context)) { return null; }
        HCEventRuntimeState snapshot = events.Runtime().Snapshot();
        if (!snapshot || !snapshot.Director || !snapshot.Runs || snapshot.Runs.Count() < 1 || snapshot.Runs.Count() > 32) { return null; }
        // At most 32 existing event records, only when a ready holder is due.
        for (int runOffset = 0; runOffset < snapshot.Runs.Count(); runOffset++)
        {
            int runIndex = (m_TargetCursor + runOffset) % snapshot.Runs.Count();
            HCEventRun run = snapshot.Runs[runIndex];
            if (!run || !run.Objective || run.Phase >= HCEventRunPhase.CLEANUP) { continue; }
            HCEventRecord record = HCEventDirector.FindRecord(snapshot.Director, run.EventId);
            HCEventMission mission = run.Objective;
            if (!record || record.Session != context.Session || HCEventDirector.Terminal(record.Status) || record.Expires <= context.Now) { continue; }
            if (!mission.Reviewed || mission.WorldName != context.WorldName || HCMorseRpc.Word(mission.Family) == "") { continue; }
            // Source is a reviewed, configured site, never a tracked entity.
            if (!HCWorldLimits.Position(mission.Source) || mission.Source[0] < 0 || mission.Source[2] < 0 || mission.Source[0] >= 15360 || mission.Source[2] >= 15360) { continue; }
            m_TargetCursor = (runIndex + 1) % snapshot.Runs.Count();
            return mission;
        }
        return null;
    }

    override void OnTick(float deltaTime)
    {
        if (!m_Running || !(deltaTime > 0)) { return; }
        m_Elapsed += deltaTime;
        if (m_Elapsed < 60) { return; }
        m_Elapsed = 0;
        array<Man> players = new array<Man>;
        GetGame().GetPlayers(players);
        if (players.Count() < 1) { return; }
        if (m_PlayerCursor >= players.Count()) { m_PlayerCursor = 0; }
        PlayerBase player = PlayerBase.Cast(players[m_PlayerCursor]);
        m_PlayerCursor++;
        if (!Holder(player)) { return; }
        PlayerIdentity identity = player.GetIdentity();
        if (!identity || identity.GetId().Length() < 1 || identity.GetId().Length() > 96) { return; }
        int now = HCWorldClock.UTC();
        int fingerprint = identity.GetId().Hash();
        if (!m_Rates.Allowed(fingerprint, now)) { return; }
        HCEventMission mission = Target();
        if (!mission) { return; }
        // Durable reservation precedes delivery: interruption may lose a clue,
        // but cannot replay one after restart or reconnect to bypass the limits.
        if (!m_Rates.Reserve(fingerprint, now)) { return; }
        int east = Math.Floor(mission.Source[0] / 1000);
        int north = Math.Floor(mission.Source[2] / 1000);
        ScriptRPC rpc = new ScriptRPC;
        rpc.Write(east);
        rpc.Write(north);
        rpc.Write(mission.Family);
        rpc.Send(player, HCMorseRpc.CLUE, true, identity);
        HCWorldModule ledger = HCWorldModule.Get();
        if (ledger)
        {
            string place = ledger.NearestPlace(mission.Source);
            if (place != "") { ledger.AddFact("morse_lead", place, 0); }
        }
        Print("[HollowCountry] V2 morse clue player=" + player.GetID().ToString() + " grid=" + HCMorseRpc.Grid(east, north) + " target=" + HCMorseRpc.Word(mission.Family));
    }

    override void OnStop()
    {
        m_Running = false;
        m_Rates = null;
        m_Elapsed = 0;
    }
}

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        Register(new HCMorseClues);
    }
}
