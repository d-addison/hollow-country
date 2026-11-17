// No hooks or automatic enablement. Operator supplies qualified measurements,
// native LOS and exclusive custody. Catalog metadata alone grants nothing.
// Native reference: scripts-1.30.164289. Journal readback is NOT fsync/atomicity.
class HCTapedLightService
{
    static bool TextValid(string value, int limit)
    {
        if (value.Length() < 1 || value.Length() > limit) { return false; }
        if (value.Trim().Length() == 0) { return false; }
        if (value.Contains("\n") || value.Contains("\r") || value.Contains("\t")) { return false; }
        return true;
    }
    static bool TokenValid(string value)
    {
        if (value.Length() < 1 || value.Length() > 64) { return false; }
        string alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-";
        int index = 0;
        while (index < value.Length())
        {
            if (!alphabet.Contains(value.Substring(index, 1))) { return false; }
            index = index + 1;
        }
        return true;
    }
    static bool DigestValid(string value)
    {
        if (value.Length() != 64) { return false; }
        string alphabet = "0123456789abcdef";
        int index = 0;
        while (index < 64)
        {
            if (!alphabet.Contains(value.Substring(index, 1))) { return false; }
            index = index + 1;
        }
        return true;
    }
    static bool BindingValid(HCTapedLightBinding b, string build)
    {
        if (!b || b.Version != 1) { return false; }
        if (!DigestValid(b.ManifestDigest) || !DigestValid(b.MeasurementDigest)) { return false; }
        if (!TextValid(build, 96) || !HCBuildIdentity.SameBuild(b.GameBuild, build)) { return false; }
        if (b.HostConfigRoot != "CfgVehicles" && b.HostConfigRoot != "CfgWeapons") { return false; }
        if (!TextValid(b.HostClass, 128) || !TextValid(b.LightClass, 128)) { return false; }
        if (!TextValid(b.SlotName, 96)) { return false; }
        if (!(b.TapeUnits >= 1 && b.TapeUnits <= 1000000)) { return false; }
        return b.MaxDistance > 0 && b.MaxDistance <= 5;
    }
    // Exact qualified operation identity; digests alone are not eligibility.
    static bool SameBinding(HCTapedLightBinding a, HCTapedLightBinding b)
    {
        if (!a || !b || a.Version != b.Version) { return false; }
        if (a.ManifestDigest != b.ManifestDigest || a.MeasurementDigest != b.MeasurementDigest) { return false; }
        if (HCBuildIdentity.Normalize(a.GameBuild) != HCBuildIdentity.Normalize(b.GameBuild) || a.HostConfigRoot != b.HostConfigRoot) { return false; }
        if (a.HostClass != b.HostClass || a.LightClass != b.LightClass) { return false; }
        if (a.SlotName != b.SlotName || a.BatterySlotName != b.BatterySlotName) { return false; }
        return a.TapeUnits == b.TapeUnits && a.MaxDistance == b.MaxDistance;
    }
    static HCTapedLightBinding CopyBinding(HCTapedLightBinding b)
    {
        HCTapedLightBinding n = new HCTapedLightBinding;
        n.Version = b.Version;
        n.ManifestDigest = b.ManifestDigest;
        n.MeasurementDigest = b.MeasurementDigest;
        n.GameBuild = b.GameBuild;
        n.HostConfigRoot = b.HostConfigRoot;
        n.HostClass = b.HostClass;
        n.LightClass = b.LightClass;
        n.SlotName = b.SlotName;
        n.BatterySlotName = b.BatterySlotName;
        n.TapeUnits = b.TapeUnits;
        n.MaxDistance = b.MaxDistance;
        return n;
    }
    static bool SnapshotValid(HCTapedLightSnapshot s, bool mounting)
    {
        if (!s) { return false; }
        if (!TextValid(s.ActorId, 128) || !TextValid(s.HostId, 128)) { return false; }
        if (!TextValid(s.LightId, 128) || s.HostId == s.LightId) { return false; }
        if (!(s.HostHealth > 0 && s.HostHealth <= 1)) { return false; }
        if (!(s.LightHealth > 0 && s.LightHealth <= 1)) { return false; }
        if (!(s.LightEnergy >= 0 && s.LightEnergy <= 1000000)) { return false; }
        if (s.LightOn || s.Place < 0 || s.Place > 2) { return false; }
        if (s.BatteryId != "")
        {
            if (!TextValid(s.BatteryId, 128)) { return false; }
            if (s.BatteryId == s.LightId || s.BatteryId == s.HostId) { return false; }
            if (!(s.BatteryHealth > 0 && s.BatteryHealth <= 1)) { return false; }
            if (!(s.BatteryEnergy >= 0 && s.BatteryEnergy <= 1000000)) { return false; }
        }
        else
        {
            if (s.BatteryHealth != 0 || s.BatteryEnergy != 0) { return false; }
        }
        if (mounting)
        {
            if (!TextValid(s.TapeId, 128)) { return false; }
            if (s.TapeId == s.LightId || s.TapeId == s.HostId) { return false; }
            if (s.TapeId == s.BatteryId) { return false; }
            if (!(s.TapeHealth > 0 && s.TapeHealth <= 1)) { return false; }
            if (!(s.TapeQuantity > 0 && s.TapeQuantity <= 1000000)) { return false; }
        }
        return true;
    }
    static bool Preserved(HCTapedLightSnapshot a, HCTapedLightSnapshot b)
    {
        if (!a || !b) { return false; }
        if (a.ActorId != b.ActorId || a.HostId != b.HostId) { return false; }
        if (a.LightId != b.LightId || a.BatteryId != b.BatteryId) { return false; }
        if (a.HostHealth != b.HostHealth || a.LightHealth != b.LightHealth) { return false; }
        if (a.BatteryHealth != b.BatteryHealth || a.BatteryEnergy != b.BatteryEnergy) { return false; }
        return a.LightEnergy == b.LightEnergy && a.LightOn == b.LightOn;
    }
    static bool StateValid(HCTapedLightState s)
    {
        if (!s || s.Version != 1 || !s.Records) { return false; }
        if (s.Records.Count() > 128) { return false; }
        int index = 0;
        foreach (HCTapedLightRecord r : s.Records)
        {
            if (!r || r.Version != 1 || !TokenValid(r.RecordKey)) { return false; }
            if (!r.BindingData || !BindingValid(r.BindingData, r.BindingData.GameBuild)) { return false; }
            if (!SnapshotValid(r.BeforeData, r.Mounting)) { return false; }
            if (r.ActorId != r.BeforeData.ActorId || r.HostId != r.BeforeData.HostId) { return false; }
            if (r.LightId != r.BeforeData.LightId) { return false; }
            if (r.Phase < 1 || r.Phase > HCTapedLightPhase.QUARANTINE) { return false; }
            if (r.Phase == HCTapedLightPhase.MOUNTED && !r.Mounting) { return false; }
            if (r.Phase == HCTapedLightPhase.REMOVED && r.Mounting) { return false; }
            if (r.Mounting)
            {
                if (r.BeforeData.Place == 1) { return false; }
                if (r.BeforeData.TapeQuantity < r.BindingData.TapeUnits) { return false; }
            }
            else
            {
                if (r.BeforeData.Place != 1) { return false; }
                if (r.Phase == HCTapedLightPhase.TAPE_SPENT) { return false; }
            }
            HCTapedLightRecord priorLight = null;
            int previous = 0;
            while (previous < index)
            {
                HCTapedLightRecord earlier = s.Records[previous];
                if (earlier.RecordKey == r.RecordKey) { return false; }
                // Serialized transactions cannot proceed past an uncertain result.
                if (earlier.Phase != HCTapedLightPhase.MOUNTED && earlier.Phase != HCTapedLightPhase.REMOVED) { return false; }
                if (earlier.LightId == r.LightId) { priorLight = earlier; }
                previous = previous + 1;
            }
            if (r.Mounting)
            {
                if (priorLight && priorLight.Phase == HCTapedLightPhase.MOUNTED) { return false; }
            }
            else
            {
                if (!priorLight || priorLight.Phase != HCTapedLightPhase.MOUNTED) { return false; }
                if (priorLight.HostId != r.HostId) { return false; }
                if (!SameBinding(priorLight.BindingData, r.BindingData)) { return false; }
            }
            index = index + 1;
        }
        return true;
    }
    static int Open(HCTapedLightState s, HCTapedLightPort p)
    {
        if (!s || !p) { return HCTapedLightCode.INVALID; }
        if (s.Ready || s.Busy) { return HCTapedLightCode.CONFLICT; }
        if (!s.Records || s.Records.Count() != 0) { return HCTapedLightCode.INVALID; }
        if (!p.Load(s)) { return HCTapedLightCode.BLOCKED; }
        if (!StateValid(s))
        {
            s.Quarantined = true;
            return HCTapedLightCode.QUARANTINED;
        }
        foreach (HCTapedLightRecord r : s.Records)
        {
            if (r.Phase != HCTapedLightPhase.MOUNTED && r.Phase != HCTapedLightPhase.REMOVED)
            {
                s.Quarantined = true;
                return HCTapedLightCode.QUARANTINED;
            }
        }
        if (s.Quarantined) { return HCTapedLightCode.QUARANTINED; }
        s.Ready = true;
        return HCTapedLightCode.OK;
    }
    static int Quarantine(HCTapedLightState s, HCTapedLightPort p, HCTapedLightRecord r)
    {
        s.Quarantined = true;
        if (r)
        {
            r.Phase = HCTapedLightPhase.QUARANTINE;
            p.Write(r, r.Phase);
        }
        // Keep uncertain custody. No rollback, automatic retry or tape refund.
        s.Busy = false;
        return HCTapedLightCode.QUARANTINED;
    }
    static bool Stamp(HCTapedLightPort p, HCTapedLightRecord r, int phase)
    {
        r.Phase = phase;
        return p.Write(r, phase);
    }
    static int Run(HCTapedLightState s, HCTapedLightPort p, string key, bool mounting)
    {
        if (!s || !p) { return HCTapedLightCode.INVALID; }
        if (s.Quarantined) { return HCTapedLightCode.QUARANTINED; }
        if (!s.Ready || s.Busy) { return HCTapedLightCode.BLOCKED; }
        if (!StateValid(s)) { return Quarantine(s, p, null); }
        foreach (HCTapedLightRecord pending : s.Records)
        {
            if (pending.Phase != HCTapedLightPhase.MOUNTED && pending.Phase != HCTapedLightPhase.REMOVED)
            {
                return Quarantine(s, p, null);
            }
        }
        if (!TokenValid(key)) { return HCTapedLightCode.INVALID; }
        if (!p.ActorAllowed()) { return HCTapedLightCode.DENIED; }
        if (!p.CustodyAvailable()) { return HCTapedLightCode.BLOCKED; }
        HCTapedLightBinding b = p.Resolve();
        if (!BindingValid(b, p.CurrentBuild())) { return HCTapedLightCode.BLOCKED; }
        b = CopyBinding(b);
        if (!p.InRange(b) || !p.HasLOS(b)) { return HCTapedLightCode.DENIED; }
        HCTapedLightSnapshot before = p.Observe(b);
        if (!SnapshotValid(before, mounting)) { return HCTapedLightCode.DENIED; }
        if (before.ActorId != p.ActorKey()) { return HCTapedLightCode.DENIED; }
        HCTapedLightRecord latest = null;
        foreach (HCTapedLightRecord old : s.Records)
        {
            if (old.RecordKey == key)
            {
                if (old.ActorId != before.ActorId || old.HostId != before.HostId) { return HCTapedLightCode.CONFLICT; }
                if (old.LightId != before.LightId || old.Mounting != mounting) { return HCTapedLightCode.CONFLICT; }
                if (!SameBinding(old.BindingData, b)) { return HCTapedLightCode.CONFLICT; }
                if (old.Phase != HCTapedLightPhase.MOUNTED && old.Phase != HCTapedLightPhase.REMOVED) { return Quarantine(s, p, null); }
                // Historical acknowledgement, not a new physical-state claim.
                return HCTapedLightCode.OK;
            }
            if (old.LightId == before.LightId) { latest = old; }
        }
        if (mounting)
        {
            if (latest && latest.Phase == HCTapedLightPhase.MOUNTED) { return HCTapedLightCode.CONFLICT; }
            if (before.Place == 1 || before.TapeQuantity < b.TapeUnits) { return HCTapedLightCode.DENIED; }
        }
        else
        {
            if (!latest || latest.Phase != HCTapedLightPhase.MOUNTED) { return HCTapedLightCode.DENIED; }
            if (latest.HostId != before.HostId) { return HCTapedLightCode.DENIED; }
            if (!SameBinding(latest.BindingData, b)) { return HCTapedLightCode.BLOCKED; }
        }
        if (!p.CanTransfer(b, mounting)) { return HCTapedLightCode.BLOCKED; }
        if (s.Records.Count() >= 128) { return HCTapedLightCode.LIMIT; }
        s.Busy = true;
        // Read back the intent before custody can become uncertain. Later
        // failure remains quarantined even if a fault-image write also fails.
        // This supplies recovery evidence, not fsync or native atomicity.
        HCTapedLightRecord r = new HCTapedLightRecord;
        r.RecordKey = key;
        r.ActorId = before.ActorId;
        r.HostId = before.HostId;
        r.LightId = before.LightId;
        r.Mounting = mounting;
        r.BindingData = CopyBinding(b);
        // Observe must return new snapshots, never mutable cached DTOs.
        r.BeforeData = before;
        s.Records.Insert(r);
        if (!Stamp(p, r, HCTapedLightPhase.INTENT)) { return Quarantine(s, p, r); }
        if (!p.Acquire(mounting)) { return Quarantine(s, p, r); }
        HCTapedLightSnapshot fresh = p.Observe(b);
        bool same = SnapshotValid(fresh, mounting) && Preserved(before, fresh);
        if (fresh)
        {
            same = same && fresh.Place == before.Place;
            if (mounting)
            {
                same = same && fresh.TapeId == before.TapeId;
                same = same && fresh.TapeQuantity == before.TapeQuantity;
                same = same && fresh.TapeHealth == before.TapeHealth;
            }
        }
        if (!p.ActorAllowed() || !p.InRange(b) || !p.HasLOS(b)) { same = false; }
        if (!p.CanTransfer(b, mounting)) { same = false; }
        if (!same)
        {
            // Best-effort release cannot acknowledge or clear the intent.
            // Either release result leaves this failed operation quarantined.
            p.Release();
            return Quarantine(s, p, r);
        }
        if (mounting)
        {
            p.ConsumeTape(r.BindingData.TapeUnits);
            HCTapedLightSnapshot spent = p.Observe(b);
            if (!SnapshotValid(spent, false) || !Preserved(fresh, spent)) { return Quarantine(s, p, r); }
            if (spent.Place != fresh.Place || spent.TapeId != fresh.TapeId) { return Quarantine(s, p, r); }
            if (spent.TapeHealth != fresh.TapeHealth) { return Quarantine(s, p, r); }
            if (spent.TapeQuantity != fresh.TapeQuantity - b.TapeUnits) { return Quarantine(s, p, r); }
            if (!Stamp(p, r, HCTapedLightPhase.TAPE_SPENT)) { return Quarantine(s, p, r); }
        }
        if (!p.ActorAllowed() || !p.InRange(b) || !p.HasLOS(b)) { return Quarantine(s, p, r); }
        if (!p.CanTransfer(b, mounting)) { return Quarantine(s, p, r); }
        if (!Stamp(p, r, HCTapedLightPhase.MOVE_INTENT)) { return Quarantine(s, p, r); }
        bool moved = p.Transfer(b, mounting);
        HCTapedLightSnapshot after = p.Observe(b);
        if (!moved || !SnapshotValid(after, false) || !Preserved(fresh, after)) { return Quarantine(s, p, r); }
        int expectedPlace = 2;
        if (mounting) { expectedPlace = 1; }
        if (after.Place != expectedPlace) { return Quarantine(s, p, r); }
        if (mounting)
        {
            if (after.TapeId != fresh.TapeId || after.TapeHealth != fresh.TapeHealth) { return Quarantine(s, p, r); }
            if (after.TapeQuantity != fresh.TapeQuantity - b.TapeUnits) { return Quarantine(s, p, r); }
        }
        if (!p.ActorAllowed() || after.ActorId != p.ActorKey()) { return Quarantine(s, p, r); }
        int finalPhase = HCTapedLightPhase.REMOVED;
        if (mounting) { finalPhase = HCTapedLightPhase.MOUNTED; }
        // Keep recovery nonterminal until custody release succeeds.
        if (!p.Release()) { return Quarantine(s, p, r); }
        if (!Stamp(p, r, finalPhase)) { return Quarantine(s, p, r); }
        s.Busy = false;
        return HCTapedLightCode.OK;
    }
}

// These two capabilities must be implemented/qualified by a trusted server
// integration. No imported config row, client flag or hash string is sufficient.
// Resolve covers exact audited class pairs without a hardcoded pilot whitelist.
class HCTapedLightQualification
{
    bool Ready() { return false; }
    HCTapedLightBinding Resolve(EntityAI host, ItemBase light) { return null; }
    bool HasLOS(PlayerBase actor, EntityAI host, HCTapedLightBinding binding) { return false; }
}
class HCTapedLightCustody
{
    bool Ready() { return false; }
    bool Acquire(PlayerBase actor, EntityAI host, ItemBase light, ItemBase tape, bool mounting) { return false; }
    bool Release() { return false; }
}

// Immutable intent + full-image pairs, bounded at 768 images / 128 operations.
// A partial highest pair blocks recovery. No older-state fallback or compaction.
// Exclusive server/profile ownership is required. File APIs supply no fsync.
class HCTapedLightJournal
{
    protected string mHCRoot;
    protected int mHCSequence;
    protected bool mHCFault;
    protected ref HCTapedLightState mHCState;

    string Build()
    {
        string version;
        GetGame().GetVersion(version);
        // The engine reports 1.30.164289.70; journals and bindings carry the canonical pin.
        return HCBuildIdentity.Normalize(version);
    }
    bool Read(string path, int limit, out string text)
    {
        FileHandle handle = OpenFile(path, FileMode.READ);
        if (!handle) { return false; }
        int count = ReadFile(handle, text, limit + 1);
        CloseFile(handle);
        return count > 0 && count <= limit && text.Length() <= limit;
    }
    bool WriteNew(string path, string text)
    {
        if (FileExist(path) || text.Length() < 1 || text.Length() > 262144) { return false; }
        FileHandle handle = OpenFile(path, FileMode.WRITE);
        if (!handle) { return false; }
        FPrint(handle, text);
        CloseFile(handle);
        string actual;
        return Read(path, 262144, actual) && actual == text;
    }
    bool Configure(string name)
    {
        if (!GetGame().IsServer() || !HCTapedLightService.TokenValid(name)) { return false; }
        if (mHCRoot != "") { return false; }
        string parent = "$profile:HollowCountry";
        if (!FileExist(parent) && !MakeDirectory(parent)) { return false; }
        parent = parent + "/TapedLights";
        if (!FileExist(parent) && !MakeDirectory(parent)) { return false; }
        mHCRoot = parent + "/" + name;
        if (!FileExist(mHCRoot))
        {
            if (!MakeDirectory(mHCRoot)) { return false; }
            if (!WriteNew(mHCRoot + "/build.txt", Build())) { return false; }
        }
        string actual;
        return Read(mHCRoot + "/build.txt", 96, actual) && HCBuildIdentity.SameBuild(actual, Build());
    }
    int Number(string name, string prefix, string suffix)
    {
        if (name.IndexOf(prefix) != 0) { return 0; }
        int length = name.Length() - prefix.Length() - suffix.Length();
        if (length < 1) { return 0; }
        int number = name.Substring(prefix.Length(), length).ToInt();
        if (number < 1 || number > 768) { return 0; }
        if (prefix + number.ToString() + suffix != name) { return 0; }
        return number;
    }
    bool Load(HCTapedLightState state)
    {
        if (mHCFault || mHCRoot == "" || mHCState) { return false; }
        string filename;
        FileAttr attr;
        FindFileHandle handle = FindFile(mHCRoot + "/*", filename, attr, FindFileFlags.DIRECTORIES);
        if (!handle) { return false; }
        int highestIntent = 0;
        int highestState = 0;
        int count = 0;
        bool valid = true;
        bool found = filename != "";
        while (found)
        {
            if (filename != "." && filename != "..")
            {
                count = count + 1;
                if (attr == FileAttr.DIRECTORY || count > 1537) { valid = false; break; }
                if (filename != "build.txt")
                {
                    int intent = Number(filename, "intent_", ".txt");
                    int image = Number(filename, "state_", ".json");
                    if (intent == 0 && image == 0) { valid = false; break; }
                    highestIntent = Math.Max(highestIntent, intent);
                    highestState = Math.Max(highestState, image);
                }
            }
            found = FindNextFile(handle, filename, attr);
        }
        CloseFindFile(handle);
        if (!valid || highestIntent != highestState) { mHCFault = true; return false; }
        if (count != highestIntent * 2 + 1) { mHCFault = true; return false; }
        // Recheck the configured provenance at recovery, then require the
        // highest intent's exact contents. Never fall back to an older image.
        string buildText;
        string buildPath = mHCRoot + "/build.txt";
        if (!Read(buildPath, 96, buildText)) { mHCFault = true; return false; }
        if (!HCBuildIdentity.SameBuild(buildText, Build())) { mHCFault = true; return false; }
        if (highestState > 0)
        {
            string marker;
            string markerPath = mHCRoot + "/intent_" + highestIntent.ToString() + ".txt";
            if (!Read(markerPath, 32, marker)) { mHCFault = true; return false; }
            if (marker != highestIntent.ToString()) { mHCFault = true; return false; }
            string text;
            string error;
            HCTapedLightState loaded;
            string path = mHCRoot + "/state_" + highestState.ToString() + ".json";
            if (!Read(path, 262144, text)) { mHCFault = true; return false; }
            if (!JsonFileLoader<HCTapedLightState>.LoadData(text, loaded, error)) { mHCFault = true; return false; }
            if (!HCTapedLightService.StateValid(loaded)) { mHCFault = true; return false; }
            state.Version = loaded.Version;
            state.Records = loaded.Records;
            state.Quarantined = loaded.Quarantined;
        }
        mHCSequence = highestState;
        mHCState = state;
        return true;
    }
    bool Save(HCTapedLightRecord record, int phase)
    {
        if (!GetGame().IsServer() || mHCFault || !mHCState) { return false; }
        if (mHCSequence >= 768 || !record || record.Phase != phase) { return false; }
        if (mHCState.Records.Find(record) < 0) { return false; }
        string text;
        string error;
        if (!JsonFileLoader<HCTapedLightState>.MakeData(mHCState, text, error)) { mHCFault = true; return false; }
        int next = mHCSequence + 1;
        string number = next.ToString();
        if (!WriteNew(mHCRoot + "/intent_" + number + ".txt", number)) { mHCFault = true; return false; }
        if (!WriteNew(mHCRoot + "/state_" + number + ".json", text)) { mHCFault = true; return false; }
        mHCSequence = next;
        return true;
    }
}

// Concrete native observations/moves. Configure is explicit server integration,
// not a production hook. Qualification and custody must be supplied separately.
class HCTapedLightPort
{
    protected PlayerBase mHCActor;
    protected EntityAI mHCHost;
    protected ItemBase mHCLight;
    protected ItemBase mHCTape;
    protected string mHCIdentity;
    protected bool mHCHeld;
    protected ref HCTapedLightRecord mHCMoveRecord;
    protected bool mHCReleaseConfirmed;
    protected ref HCTapedLightQualification mHCQualification;
    protected ref HCTapedLightCustody mHCCustody;
    protected ref HCTapedLightJournal mHCJournal;

    bool Configure(PlayerBase actor, EntityAI host, ItemBase light, ItemBase tape, HCTapedLightQualification qualification, HCTapedLightCustody custody, string journalName)
    {
        if (!GetGame().IsServer() || mHCActor || !actor) { return false; }
        if (!actor.GetIdentity() || !host || !light) { return false; }
        if (!qualification || !custody) { return false; }
        if (!qualification.Ready() || !custody.Ready()) { return false; }
        mHCJournal = new HCTapedLightJournal;
        if (!mHCJournal.Configure(journalName)) { return false; }
        mHCActor = actor;
        mHCHost = host;
        mHCLight = light;
        mHCTape = tape;
        mHCIdentity = actor.GetIdentity().GetId();
        mHCQualification = qualification;
        mHCCustody = custody;
        return ActorAllowed();
    }
    bool ActorAllowed()
    {
        if (!GetGame().IsServer() || !mHCActor || !mHCActor.GetIdentity()) { return false; }
        if (!mHCActor.IsAlive() || mHCActor.IsUnconscious()) { return false; }
        return ActorKey() == mHCIdentity;
    }
    string ActorKey()
    {
        if (!mHCActor || !mHCActor.GetIdentity()) { return ""; }
        return mHCActor.GetIdentity().GetId();
    }
    string PersistentKey(EntityAI item)
    {
        if (!item) { return ""; }
        int a, b, c, d;
        item.GetPersistentID(a, b, c, d);
        if (a == 0 && b == 0 && c == 0 && d == 0) { return ""; }
        return string.Format("%1:%2:%3:%4", a, b, c, d);
    }
    string CurrentBuild()
    {
        string version;
        GetGame().GetVersion(version);
        // The engine reports 1.30.164289.70; journals and bindings carry the canonical pin.
        return HCBuildIdentity.Normalize(version);
    }
    bool CustodyAvailable()
    {
        if (!mHCCustody || !mHCQualification || !mHCJournal) { return false; }
        return mHCCustody.Ready() && mHCQualification.Ready();
    }
    HCTapedLightBinding Resolve()
    {
        if (!ActorAllowed() || !mHCQualification) { return null; }
        return mHCQualification.Resolve(mHCHost, mHCLight);
    }
    bool InRange(HCTapedLightBinding b)
    {
        if (!ActorAllowed() || !mHCHost) { return false; }
        float distance = vector.DistanceSq(mHCActor.GetPosition(), mHCHost.GetPosition());
        return distance >= 0 && distance <= b.MaxDistance * b.MaxDistance;
    }
    bool HasLOS(HCTapedLightBinding b)
    {
        if (!ActorAllowed() || !mHCQualification) { return false; }
        return mHCQualification.HasLOS(mHCActor, mHCHost, b);
    }
    bool Acquire(bool mounting)
    {
        mHCMoveRecord = null;
        mHCReleaseConfirmed = false;
        if (mHCHeld || !ActorAllowed() || !CustodyAvailable()) { return false; }
        mHCHeld = mHCCustody.Acquire(mHCActor, mHCHost, mHCLight, mHCTape, mounting);
        return mHCHeld;
    }
    bool Release()
    {
        mHCReleaseConfirmed = false;
        if (!mHCHeld || !mHCCustody) { return false; }
        if (!mHCCustody.Release()) { return false; }
        mHCHeld = false;
        mHCReleaseConfirmed = mHCMoveRecord != null;
        return true;
    }
    HCTapedLightSnapshot Observe(HCTapedLightBinding b)
    {
        if (!ActorAllowed() || !mHCHost || !mHCLight) { return null; }
        if (!mHCLight.GetCompEM()) { return null; }
        HCTapedLightSnapshot s = new HCTapedLightSnapshot;
        s.ActorId = ActorKey();
        s.HostId = PersistentKey(mHCHost);
        s.LightId = PersistentKey(mHCLight);
        s.HostHealth = mHCHost.GetHealth01("", "Health");
        s.LightHealth = mHCLight.GetHealth01("", "Health");
        s.LightOn = mHCLight.GetCompEM().IsSwitchedOn();
        s.LightEnergy = mHCLight.GetCompEM().GetEnergy();
        EntityAI battery;
        if (b.BatterySlotName != "")
        {
            battery = mHCLight.FindAttachmentBySlotName(b.BatterySlotName);
        }
        EntityAI supply = mHCLight.GetCompEM().GetEnergySource();
        if (supply && supply != battery && supply != mHCLight) { return null; }
        if (battery)
        {
            if (!battery.GetCompEM()) { return null; }
            s.BatteryId = PersistentKey(battery);
            if (s.BatteryId == "") { return null; }
            s.BatteryHealth = battery.GetHealth01("", "Health");
            s.BatteryEnergy = battery.GetCompEM().GetEnergy();
        }
        if (mHCTape)
        {
            s.TapeId = PersistentKey(mHCTape);
            s.TapeHealth = mHCTape.GetHealth01("", "Health");
            s.TapeQuantity = mHCTape.GetQuantity();
        }
        InventoryLocation location = new InventoryLocation;
        if (!mHCLight.GetInventory().GetCurrentInventoryLocation(location)) { return null; }
        s.Place = -1;
        int slotId = InventorySlots.GetSlotIdFromString(b.SlotName);
        if (location.GetType() == InventoryLocationType.ATTACHMENT)
        {
            if (location.GetParent() == mHCHost && location.GetSlot() == slotId) { s.Place = 1; }
        }
        else
        {
            if (mHCLight.GetHierarchyRootPlayer() == mHCActor)
            {
                if (location.GetType() == InventoryLocationType.HANDS) { s.Place = 2; }
                if (location.GetType() == InventoryLocationType.CARGO) { s.Place = 0; }
            }
        }
        return s;
    }
    bool CanTransfer(HCTapedLightBinding b, bool mounting)
    {
        if (!ActorAllowed() || !mHCHost || !mHCLight) { return false; }
        if (mHCHost.GetType() != b.HostClass || mHCLight.GetType() != b.LightClass) { return false; }
        if (mHCHost.GetHierarchyRootPlayer() != mHCActor) { return false; }
        if (mHCLight.GetHierarchyRootPlayer() != mHCActor) { return false; }
        int slotId = InventorySlots.GetSlotIdFromString(b.SlotName);
        if (slotId < 0) { return false; }
        InventoryLocation sourceLocation = new InventoryLocation;
        InventoryLocation destination = new InventoryLocation;
        if (!mHCLight.GetInventory().GetCurrentInventoryLocation(sourceLocation)) { return false; }
        if (mounting)
        {
            if (!mHCTape || !mHCTape.IsKindOf("DuctTape")) { return false; }
            if (mHCTape.GetHierarchyRootPlayer() != mHCActor) { return false; }
            if (!mHCHost.GetInventory().CanAddAttachmentEx(mHCLight, slotId)) { return false; }
            destination.SetAttachment(mHCHost, mHCLight, slotId);
        }
        else
        {
            if (mHCActor.GetItemInHands()) { return false; }
            if (mHCHost.GetInventory().FindAttachment(slotId) != mHCLight) { return false; }
            destination.SetHands(mHCActor, mHCLight);
        }
        return GameInventory.LocationCanMoveEntity(sourceLocation, destination);
    }
    void ConsumeTape(float units)
    {
        if (!mHCHeld || !ActorAllowed() || !mHCTape) { return; }
        // Return value means DELETED, not SUCCESS. Observe the actual delta.
        // Keep the zero-quantity roll to avoid an additional unjournaled deletion.
        mHCTape.AddQuantity(-units, false, false);
    }
    bool Transfer(HCTapedLightBinding b, bool mounting)
    {
        if (!mHCHeld || !CanTransfer(b, mounting)) { return false; }
        InventoryLocation sourceLocation = new InventoryLocation;
        InventoryLocation destination = new InventoryLocation;
        if (!mHCLight.GetInventory().GetCurrentInventoryLocation(sourceLocation)) { return false; }
        int slotId = InventorySlots.GetSlotIdFromString(b.SlotName);
        if (mounting) { destination.SetAttachment(mHCHost, mHCLight, slotId); }
        else { destination.SetHands(mHCActor, mHCLight); }
        return GameInventory.LocationSyncMoveEntity(sourceLocation, destination);
    }
    bool Load(HCTapedLightState state)
    {
        if (!ActorAllowed() || !CustodyAvailable()) { return false; }
        return mHCJournal.Load(state);
    }
    bool Write(HCTapedLightRecord record, int phase)
    {
        if (!mHCJournal || !GetGame().IsServer()) { return false; }
        bool terminal = phase == HCTapedLightPhase.MOUNTED || phase == HCTapedLightPhase.REMOVED;
        if (terminal)
        {
            if (mHCHeld || !mHCReleaseConfirmed || !record || mHCMoveRecord != record) { return false; }
            // One attempt for this released record, including failed writes.
            mHCReleaseConfirmed = false;
            mHCMoveRecord = null;
        }
        else
        {
            if (!mHCHeld && phase != HCTapedLightPhase.INTENT) { return false; }
            if (phase == HCTapedLightPhase.INTENT)
            {
                mHCMoveRecord = null;
                mHCReleaseConfirmed = false;
            }
        }
        bool written = mHCJournal.Save(record, phase);
        if (written && phase == HCTapedLightPhase.MOVE_INTENT)
        {
            mHCMoveRecord = record;
            mHCReleaseConfirmed = false;
        }
        return written;
    }
}
