// Police: borrow real stock first; otherwise own one HC container (Barrel_Green) per site.
// Native persistence owns the container and its cargo after creation. Container
// lifecycle (owner 2026-11-22): an emptied container is refilled in place after
// RefillCooldownSeconds, an aged (ContainerLifetimeSeconds) or ruined or missing one is
// drained, deleted and replaced, never while a player is within RefillClearRadius.
// A durable generation receipt precedes every native mutation, including failures.
// Native scripts-1.30.164289: Global/Game.c:703/705 CreateObjectEx/ObjectDelete;
// CE/CentralEconomy.c:9/17/28 ECE_SETUP/CREATEPHYSICS/KEEPHEIGHT;
// Systems/Inventory/Inventory.c:876 CreateInInventory; Entities/Object.c:287 GetPosition.
// Receipt files are written and read one native call per step, never in a loop or in a placement
// call: HCEventReceiptOp stages one write (FileExist, OpenFile WRITE, FPrint, read-back) or one
// DeleteFile; HCEventReceiptFiles holds the single-call read, the directory listing (names only) and
// the directory-ensure steps. Direct immutable files, the same format and torn-file rules as the
// reviewed WriteNew/Read primitives (no .tmp promotion): an interrupted write leaves at most one
// short or empty file, which every reader already treats as torn. Native scripts-1.30.164289
// 1_Core/proto/EnSystem.c: FileExist, OpenFile, ReadFile, CloseFile, FPrint, DeleteFile, FindFile.
class HCEventReceiptOp
{
    static const int RESULT_PENDING = 0;
    static const int RESULT_DONE = 1;
    static const int RESULT_FAILED = -1;
    // MODE_NEW: the name must not exist (checked first); MODE_FRESH: the caller already knows the
    // name is absent (the directory image was loaded); MODE_REMOVE: one DeleteFile.
    static const int MODE_NEW = 0;
    static const int MODE_FRESH = 1;
    static const int MODE_REMOVE = 2;
    // ReadFile length for a receipt: one more than the longest receipt (400), so an oversize file reads
    // as torn. A literal: the perf checker needs a constant ReadFile length.
    static const int READ_LIMIT = 401;
    static const int PHASE_EXISTS = 0;
    static const int PHASE_OPEN = 1;
    static const int PHASE_PRINT = 2;
    static const int PHASE_VERIFY = 3;
    string Name;
    string Path;
    string Text;
    // Name of the earlier queued write that must have been verified before this op runs ("" = none).
    string After;
    int Mode;
    int Phase;
    int Result;
    FileHandle Handle;

    void HCBegin(string name, string path, string text, int mode, string after)
    {
        Name = name;
        Path = path;
        Text = text;
        Mode = mode;
        After = after;
        Result = RESULT_PENDING;
        Phase = PHASE_EXISTS;
        if (mode == MODE_FRESH) { Phase = PHASE_OPEN; }
    }
    // Exactly one counted native file call per step.
    int HCStepOp()
    {
        if (Result != RESULT_PENDING) { return Result; }
        if (Mode == MODE_REMOVE)
        {
            Result = RESULT_FAILED;
            if (DeleteFile(Path)) { Result = RESULT_DONE; }
            return Result;
        }
        if (Phase == PHASE_EXISTS)
        {
            if (FileExist(Path)) { Result = RESULT_FAILED; return Result; }
            Phase = PHASE_OPEN;
            return RESULT_PENDING;
        }
        if (Phase == PHASE_OPEN)
        {
            Handle = OpenFile(Path, FileMode.WRITE);
            if (!Handle) { Result = RESULT_FAILED; return Result; }
            Phase = PHASE_PRINT;
            return RESULT_PENDING;
        }
        if (Phase == PHASE_PRINT)
        {
            FPrint(Handle, Text);
            CloseFile(Handle);
            Handle = null;
            Phase = PHASE_VERIFY;
            return RESULT_PENDING;
        }
        string actual;
        FileHandle reader = OpenFile(Path, FileMode.READ);
        Result = RESULT_FAILED;
        if (!reader) { return Result; }
        int count = ReadFile(reader, actual, READ_LIMIT);
        CloseFile(reader);
        if (count == Text.Length() && actual == Text) { Result = RESULT_DONE; }
        return Result;
    }
}
class HCEventReceiptFiles
{
    // One OpenFile + ReadFile; "" = missing, empty, longer than limit or short-read (torn).
    static string ReadText(string path, int limit)
    {
        string text;
        FileHandle handle = OpenFile(path, FileMode.READ);
        if (!handle) { return ""; }
        int count = ReadFile(handle, text, HCEventReceiptOp.READ_LIMIT);
        CloseFile(handle);
        if (count < 1 || text.Length() != count || count > limit) { return ""; }
        return text;
    }
    // Names only (FindFile is not a read or write of any file): false when the directory holds more
    // than cap entries. Sub-directories are not receipts and are skipped.
    static bool List(string root, array<string> names, int cap)
    {
        string name;
        FileAttr attributes;
        FindFileHandle handle = FindFile(root + "/*", name, attributes, FindFileFlags.ALL);
        if (!handle) { return true; }
        bool more = name != "";
        bool complete = true;
        while (more)
        {
            if (name != "." && name != ".." && attributes != FileAttr.DIRECTORY)
            {
                if (names.Count() >= cap)
                {
                    complete = false;
                    break;
                }
                names.Insert(name);
            }
            more = FindNextFile(handle, name, attributes);
        }
        CloseFindFile(handle);
        return complete;
    }
    // One FileExist per call: 0..2 = the profile, Events and receipt directories (MakeDirectory
    // when one is absent); returns the next stage, 3 = ready, -1 = a directory could not be made.
    static int EnsureStep(int stage, string root)
    {
        if (stage == 0)
        {
            if (!FileExist("$profile:HollowCountry") && !MakeDirectory("$profile:HollowCountry")) { return -1; }
            return 1;
        }
        if (stage == 1)
        {
            if (!FileExist("$profile:HollowCountry/Events") && !MakeDirectory("$profile:HollowCountry/Events")) { return -1; }
            return 2;
        }
        if (!FileExist(root) && !MakeDirectory(root)) { return -1; }
        return 3;
    }
}
class HCEventPoliceRewardIO : HCEventRewardIO
{
    void HCEventPoliceRewardIO()
    {
        m_Root = "$profile:HollowCountry/Events/police-cache-stock";
    }
}
// In-memory view of one site's generation receipts. Ok: highest completed generation;
// Gen: highest readable receipt (Gen > Ok = generation started and not completed);
// Num: highest receipt number on disk, readable or torn (numbering only); Id: persistent id of
// the barrel recorded with the completed generation ("" = unknown, never deleted); Prev: id of the
// barrel the generation replaced (a crash before the native save can restore it: it is accepted
// as ours and re-armed); Adopt: the id was taken from a barrel HC did not create (refill only,
// never drained or deleted).
class HCPoliceGeneration
{
    int Num;
    string Id;
    string Prev;
    bool Adopt;
    // Open generation only: its kind and the id/prev/adopt of the barrel it is working on.
    string GenKind;
    string GenId;
    string GenPrev;
    bool GenAdopt;
    int Ok;
    int OkUtc;
    int Gen;
    int GenUtc;
    int GenItems;

    bool Open() { return Gen > Ok; }
    string ExpectedId()
    {
        if (Gen > Ok) { return GenId; }
        return Id;
    }
    string ExpectedPrev()
    {
        if (Gen > Ok) { return GenPrev; }
        return Prev;
    }
    bool ExpectedAdopt()
    {
        if (Gen > Ok) { return GenAdopt; }
        return Adopt;
    }
}
// One parsed receipt file. Id/Prev are four space-joined integers or "".
class HCPoliceReceipt
{
    int Utc;
    int Items;
    string Kind;
    string Id;
    string Prev;
    bool Adopt;
}
// Bounded retry of a persistent id that read zero right after this process created the barrel.
class HCPoliceIdWatch
{
    Barrel_Green Barrel;
    int Tries;
}
// Unlike the legacy per-boot allowance, these immutable site grants survive restart.
// One orphan repair ever: spent .txt, no .pos/.repair and no ground barrel in the
// completed capped scan. The scan only marks the site eligible in process memory;
// Commit writes the immutable .repair when it grants, so a refused SpawnPosition or a
// restart before the grant leaves the repair available for the next boot.
// Existing HCEventJournalIO provides bounded write/readback; no other replay or refund.
// Generation receipts (immutable WriteNew files, same pattern as .repair):
//   <site>.gen-N  written BEFORE any native create/delete/item: generation N, utc, kind, items.
//                 replace/recreate carry "prev <old id>"; refill carries the id it works on.
//   <site>.ok-N   written after the items exist: N, the generation utc (cooldown/lifetime anchor)
//                 and the barrel's persistent id (only that barrel may ever be drained or deleted).
//   <site>.bar-N  replace/recreate only: the new barrel's id (+ prev), written before its items.
// Receipt text: "<tag> v1 <site> gen N utc U kind K items I" then optional groups in this order:
//   "id a b c d" (four ints), "prev a b c d" (previous barrel), "adopt 1" (needs id; the id was taken
//   from a barrel HC did not create: refill only, never drained or deleted). Exactly 11 tokens plus
//   whole groups; anything else is torn. Older receipts (11 tokens, or 16 with id) still parse.
// A barrel matching the current OR the previous id is ours: a replace that finished before the
// native save leaves the old barrel on restore; a prev match is re-armed as ok-(max+1) with that id.
// No receipt = legacy record, migrated in place by writing ok-1 (utc now, id of the barrel found).
// A missing or future-dated anchor is re-armed durably (ok-(max+1), utc now). The highest N wins;
// lower files are pruned best effort. Cooldown and lifetime read the durable utc, never memory.
class HCEventPoliceStockLedger : HCEventRewardLedger
{
    protected ref array<string> m_RepairChecked = new array<string>;
    protected ref array<string> m_RepairPending = new array<string>;
    protected ref map<string, ref HCPoliceGeneration> m_Generations = new map<string, ref HCPoliceGeneration>;
    protected bool m_PruneLogged;
    protected bool m_ListLogged;
    protected bool m_OverflowLogged;
    protected int m_PrunePasses;
    protected int m_PruneRemoved;
    static const int RECEIPT_LIMIT = 384;
    // Directory image: every receipt file name and its text ("" = present but torn), loaded one file
    // per tick by HCStepLedger (HCEventModule tick), then kept current by this ledger's own queued
    // writes and removes. All decisions read this image; nothing in a placement call touches a file.
    static const int LOAD_ENSURE = 0;
    static const int LOAD_LIST = 1;
    static const int LOAD_READ = 2;
    static const int LOAD_READY = 3;
    static const int LOAD_UNAVAILABLE = 4;
    static const int LOAD_PRUNE = 5;
    // Receipt names the image holds after a listing overflow (a listing over this keeps the highest
    // generations per site and kind and prunes the rest instead of refusing), the raw entries one
    // listing scans, the relist passes of one load.
    static const int LISTING_CAP = 48;
    static const int SCAN_CAP = 256;
    static const int PRUNE_PASSES = 16;
    static const int QUEUE_KEEP = 32;
    // A directory that cannot be made or listed is retried after this many seconds.
    static const int LOAD_RETRY_SECONDS = 60;
    protected ref map<string, string> m_Files = new map<string, string>;
    protected ref array<string> m_Listed;
    protected ref array<ref HCEventReceiptOp> m_Queue = new array<ref HCEventReceiptOp>;
    // Per-site grant progress (CommitStep): 1 = .repair queued, 2 = .txt queued, 3 = granted.
    protected ref map<string, int> m_CommitPhase = new map<string, int>;
    protected int m_Load;
    protected int m_LoadStage;
    protected int m_ReadAt;
    protected float m_RetryAt;

    string HCRoot() { return "$profile:HollowCountry/Events/police-cache-stock"; }
    bool HCLoaded() { return m_Load == LOAD_READY && !m_Fault; }
    // Final for this process (a fault), or waiting for a retry of a failed directory step: callers
    // fall back to stock only instead of waiting for the image.
    bool HCUnavailable() { return m_Fault || !m_IO || m_Load == LOAD_UNAVAILABLE; }
    // Memory only: true when HCStepLedger has a step to run (a directory load stage, a retry that is
    // due, or a queued receipt write or remove).
    bool HCWantsStep()
    {
        if (m_Fault || !m_IO) { return false; }
        if (m_Load == LOAD_UNAVAILABLE) { return GetGame().GetTickTime() >= m_RetryAt; }
        if (m_Load != LOAD_READY) { return true; }
        return HCNextOp() != null;
    }
    bool HCHas(string name) { return m_Files.Contains(name); }
    string HCText(string name)
    {
        string text;
        m_Files.Find(name, text);
        return text;
    }
    protected void HCLoadRefused(string reason)
    {
        m_Load = LOAD_UNAVAILABLE;
        m_RetryAt = GetGame().GetTickTime() + LOAD_RETRY_SECONDS;
        HCRefuse(reason);
    }
    // One staged step per call, driven every module tick: load the directory image (one file open
    // per call; the LOAD_LIST step is one name-only FindFile walk capped at SCAN_CAP entries plus its
    // in-memory prune plan, load-time only and only above LISTING_CAP), then run the queued receipt
    // writes and removes in order (one per call).
    // Returns true when a counted file call ran.
    bool HCStepLedger()
    {
        if (m_Fault || !m_IO) { return false; }
        if (m_Load == LOAD_UNAVAILABLE)
        {
            if (GetGame().GetTickTime() >= m_RetryAt)
            {
                m_Load = LOAD_ENSURE;
                m_LoadStage = 0;
            }
            return false;
        }
        if (m_Load == LOAD_ENSURE)
        {
            m_LoadStage = HCEventReceiptFiles.EnsureStep(m_LoadStage, HCRoot());
            if (m_LoadStage < 0) { HCLoadRefused("state_directory_unavailable"); }
            else if (m_LoadStage >= 3) { m_Load = LOAD_LIST; }
            return true;
        }
        if (m_Load == LOAD_LIST)
        {
            m_Listed = new array<string>;
            m_ReadAt = 0;
            m_Load = LOAD_READ;
            bool whole = HCEventReceiptFiles.List(HCRoot(), m_Listed, SCAN_CAP);
            if (!whole || m_Listed.Count() > LISTING_CAP) { HCPlanOverflow(whole); }
            else { m_PrunePasses = 0; }
            return false;
        }
        if (m_Load == LOAD_PRUNE)
        {
            // A listing that hit SCAN_CAP is only partly known: its prunes drain first, then the
            // directory is listed again until the whole of it fits.
            if (HCNextOp()) { return HCStepQueue(); }
            m_Load = LOAD_LIST;
            return false;
        }
        if (m_Load == LOAD_READ)
        {
            if (m_ReadAt >= m_Listed.Count())
            {
                m_Load = LOAD_READY;
                m_Listed = null;
                return false;
            }
            string listed = m_Listed[m_ReadAt];
            m_ReadAt++;
            m_Files.Set(listed, HCEventReceiptFiles.ReadText(m_IO.HCPath(listed), RECEIPT_LIMIT));
            return true;
        }
        return HCStepQueue();
    }
    // A listing over LISTING_CAP entries (or over SCAN_CAP raw entries) keeps, per site, the fixed
    // names (.txt/.pos/.repair) and the 4 highest numbers of each gen/ok/bar kind, queues
    // the other receipts of ours as removes (one DeleteFile per tick like every queued op) and ignores
    // names that are not receipts. The highest numbers always survive, so the anchor, the generation
    // and the barrel id the ledger reads are unchanged. A partial scan (more than SCAN_CAP entries)
    // is repeated after its prunes drain, at most PRUNE_PASSES times and only while a pass pruned
    // something; then the directory counts as unavailable (stock only) and is retried later.
    protected void HCPlanOverflow(bool whole)
    {
        ref array<string> scanned = m_Listed;
        m_Listed = new array<string>;
        array<string> siteIds = new array<string>;
        siteIds.Insert("coastal-police-source");
        siteIds.Insert("inland-police-source");
        array<string> kindPrefixes = new array<string>;
        kindPrefixes.Insert("gen-");
        kindPrefixes.Insert("ok-");
        kindPrefixes.Insert("bar-");
        // group: -2 = not a receipt of ours, -1 = fixed name, else site * 3 + kind.
        array<int> groups = new array<int>;
        array<int> numbers = new array<int>;
        for (int at = 0; at < scanned.Count(); at++)
        {
            int group = -2;
            int number = 0;
            for (int siteAt = 0; siteAt < 2; siteAt++)
            {
                string scannedName = scanned[at];
                if (scannedName == siteIds[siteAt] + ".txt" || scannedName == siteIds[siteAt] + ".pos" || scannedName == siteIds[siteAt] + ".repair") { group = -1; }
                for (int kindAt = 0; kindAt < 3; kindAt++)
                {
                    int value = HCEpochOf(siteIds[siteAt], scannedName, kindPrefixes[kindAt]);
                    if (value > 0)
                    {
                        group = siteAt * 3 + kindAt;
                        number = value;
                    }
                }
            }
            groups.Insert(group);
            numbers.Insert(number);
        }
        // Lowest number kept per group: the 4th highest, or 0 (keep all) when fewer exist.
        array<int> floors = new array<int>;
        for (int combo = 0; combo < 6; combo++)
        {
            int ceiling = 2000000000;
            int low = 0;
            for (int pass = 0; pass < 4; pass++)
            {
                int best = 0;
                for (int scan = 0; scan < scanned.Count(); scan++)
                {
                    if (groups[scan] == combo && numbers[scan] < ceiling && numbers[scan] > best) { best = numbers[scan]; }
                }
                if (best == 0)
                {
                    low = 0;
                    break;
                }
                low = best;
                ceiling = best;
            }
            floors.Insert(low);
        }
        int pruned = 0;
        for (int pick = 0; pick < scanned.Count(); pick++)
        {
            if (groups[pick] == -2) { continue; }
            bool keep = groups[pick] == -1;
            if (!keep && numbers[pick] >= floors[groups[pick]]) { keep = true; }
            if (keep)
            {
                m_Listed.Insert(scanned[pick]);
                continue;
            }
            HCEventReceiptOp removal = new HCEventReceiptOp;
            removal.HCBegin(scanned[pick], m_IO.HCPath(scanned[pick]), "", HCEventReceiptOp.MODE_REMOVE, "");
            m_Queue.Insert(removal);
            pruned = pruned + 1;
        }
        if (!m_OverflowLogged)
        {
            m_OverflowLogged = true;
            string scope = "whole";
            if (!whole) { scope = "partial"; }
            Print("[HC Police] action=receipt_listing_pruned kept=" + m_Listed.Count().ToString() + " pruned=" + pruned.ToString() + " scan=" + scope);
        }
        if (whole)
        {
            m_PrunePasses = 0;
            return;
        }
        m_PrunePasses = m_PrunePasses + 1;
        // Progress is removes that completed during the previous drain, not removes queued: a host
        // that refuses deletes refuses here instead of re-queueing the same prunes every pass.
        bool stalled = m_PrunePasses > 1 && m_PruneRemoved < 1;
        m_PruneRemoved = 0;
        if (pruned < 1 || stalled || m_PrunePasses > PRUNE_PASSES)
        {
            m_PrunePasses = 0;
            HCFailPendingRemoves();
            HCLoadRefused("listing_unavailable");
            return;
        }
        m_Load = LOAD_PRUNE;
    }
    // The latest queued op for a name (writes and removes), null when none is retained.
    protected HCEventReceiptOp HCQueued(string name, bool remove)
    {
        for (int at = m_Queue.Count() - 1; at >= 0; at--)
        {
            HCEventReceiptOp queued = m_Queue[at];
            if (queued.Name == name && (queued.Mode == HCEventReceiptOp.MODE_REMOVE) == remove) { return queued; }
        }
        return null;
    }
    // RESULT_PENDING / RESULT_DONE / RESULT_FAILED of the receipt write for a name. A name with no
    // retained write is DONE when the image holds it (a finished, since trimmed write) else FAILED.
    int HCWriteState(string name)
    {
        HCEventReceiptOp queued = HCQueued(name, false);
        if (queued) { return queued.Result; }
        if (m_Files.Contains(name)) { return HCEventReceiptOp.RESULT_DONE; }
        return HCEventReceiptOp.RESULT_FAILED;
    }
    // Queues one immutable receipt; memory only. Asking again for a name this ledger queued returns
    // that write's state. A name that is already in the image (any earlier file, torn or not) or text
    // over the limit is refused exactly as the old write-new primitive refused it.
    protected int HCPut(string name, string text, int limit, string after)
    {
        HCEventReceiptOp queued = HCQueued(name, false);
        if (queued) { return queued.Result; }
        if (!HCLoaded() || m_Files.Contains(name) || text.Length() < 1 || text.Length() > limit) { return HCEventReceiptOp.RESULT_FAILED; }
        HCEventReceiptOp op = new HCEventReceiptOp;
        op.HCBegin(name, m_IO.HCPath(name), text, HCEventReceiptOp.MODE_FRESH, after);
        m_Queue.Insert(op);
        return HCEventReceiptOp.RESULT_PENDING;
    }
    // Best-effort delete of one receipt, queued behind the write named in after; a persistent
    // failure is logged once per process.
    protected void HCPrune(string name, string after)
    {
        if (!HCHas(name) || HCQueued(name, true)) { return; }
        HCEventReceiptOp op = new HCEventReceiptOp;
        op.HCBegin(name, m_IO.HCPath(name), "", HCEventReceiptOp.MODE_REMOVE, after);
        m_Queue.Insert(op);
    }
    protected void HCFailQueue()
    {
        foreach (HCEventReceiptOp queued : m_Queue)
        {
            if (queued.Result == HCEventReceiptOp.RESULT_PENDING) { queued.Result = HCEventReceiptOp.RESULT_FAILED; }
        }
    }
    // Removes planned from a refused listing never run later against a newer image.
    protected void HCFailPendingRemoves()
    {
        foreach (HCEventReceiptOp queued : m_Queue)
        {
            if (queued.Mode == HCEventReceiptOp.MODE_REMOVE && queued.Result == HCEventReceiptOp.RESULT_PENDING) { queued.Result = HCEventReceiptOp.RESULT_FAILED; }
        }
    }
    protected HCEventReceiptOp HCNextOp()
    {
        foreach (HCEventReceiptOp queued : m_Queue)
        {
            if (queued.Result == HCEventReceiptOp.RESULT_PENDING) { return queued; }
        }
        return null;
    }
    protected bool HCStepQueue()
    {
        HCEventReceiptOp op = HCNextOp();
        if (!op)
        {
            while (m_Queue.Count() > QUEUE_KEEP && m_Queue[0].Result != HCEventReceiptOp.RESULT_PENDING) { m_Queue.RemoveOrdered(0); }
            return false;
        }
        if (op.After != "" && HCWriteState(op.After) != HCEventReceiptOp.RESULT_DONE)
        {
            // The write this one follows never became durable: it must not run (no delete before its
            // replacement exists).
            op.Result = HCEventReceiptOp.RESULT_FAILED;
            return false;
        }
        int result = op.HCStepOp();
        if (result == HCEventReceiptOp.RESULT_PENDING) { return true; }
        if (result == HCEventReceiptOp.RESULT_DONE)
        {
            if (op.Mode == HCEventReceiptOp.MODE_REMOVE)
            {
                m_Files.Remove(op.Name);
                m_PruneRemoved = m_PruneRemoved + 1;
            }
            else { m_Files.Set(op.Name, op.Text); }
            return true;
        }
        if (op.Mode == HCEventReceiptOp.MODE_REMOVE)
        {
            if (!m_PruneLogged)
            {
                m_PruneLogged = true;
                Print("[HC Police] action=receipt_prune_failed reason=delete_refused file=" + op.Name);
            }
            return true;
        }
        // A receipt that did not verify: nothing that depends on it may run, nothing new is granted.
        Fault();
        HCFailQueue();
        return true;
    }

    // A positive barrel observation may refuse early; absence requires a completed scan.
    void HCRepairOrphan(string siteId, bool barrelPresent)
    {
        if (siteId != "coastal-police-source" && siteId != "inland-police-source") { return; }
        // A barrel seen by any later scan revokes eligibility granted by an earlier empty scan.
        int pending = m_RepairPending.Find(siteId);
        if (barrelPresent && pending >= 0) { m_RepairPending.Remove(pending); }
        if (m_RepairChecked.Find(siteId) >= 0 || !HCLoaded()) { return; }
        m_RepairChecked.Insert(siteId);
        if (m_Granted.Find(siteId) >= 0 || !HCHas(siteId + ".txt") || HCHas(siteId + ".pos") || HCHas(siteId + ".repair")) { return; }
        if (barrelPresent)
        {
            Print("[HC Events] police grant orphan kept; " + siteId + "; reason=barrel_present runtime=PENDING");
            return;
        }
        m_RepairPending.Insert(siteId);
    }

    // The site's one grant, spent durably BEFORE any native creation (the marker is the spend).
    // Memory decisions plus queued writes, advanced one call at a time: RESULT_DONE = granted (plan
    // set; the caller creates now), RESULT_PENDING = a marker is still being written (call again),
    // RESULT_FAILED = refused (Refusal() says why). A faulted or unverified marker never grants and
    // the grant stays spent for the process (m_Granted), so a retry cannot create twice.
    int HCCommitStep(string siteId, out HCEventRewardPlan plan)
    {
        plan = null;
        m_Refusal = "police_cache_site_invalid";
        if (siteId != "coastal-police-source" && siteId != "inland-police-source") { return HCEventReceiptOp.RESULT_FAILED; }
        m_Refusal = "police_cache_journal_unavailable";
        if (HCUnavailable()) { return HCEventReceiptOp.RESULT_FAILED; }
        m_Refusal = "police_work_budget";
        if (!HCLoaded()) { return HCEventReceiptOp.RESULT_PENDING; }
        string name = siteId + ".txt";
        string repairName = siteId + ".repair";
        int phase = 0;
        m_CommitPhase.Find(siteId, phase);
        if (phase == 1)
        {
            int repairState = HCWriteState(repairName);
            if (repairState == HCEventReceiptOp.RESULT_PENDING) { return repairState; }
            m_CommitPhase.Set(siteId, 3);
            m_Refusal = "police_cache_journal_fault";
            if (repairState != HCEventReceiptOp.RESULT_DONE) { return HCEventReceiptOp.RESULT_FAILED; }
            Print("[HC Events] police grant orphan repaired; " + siteId + "; runtime=PENDING");
            m_Granted.Insert(siteId);
            m_Refusal = "";
            plan = HCFreshPlan(siteId);
            return HCEventReceiptOp.RESULT_DONE;
        }
        if (phase == 2)
        {
            int spendState = HCWriteState(name);
            if (spendState == HCEventReceiptOp.RESULT_PENDING) { return spendState; }
            m_CommitPhase.Set(siteId, 3);
            m_Refusal = "police_cache_journal_fault";
            if (spendState != HCEventReceiptOp.RESULT_DONE) { return HCEventReceiptOp.RESULT_FAILED; }
            m_Refusal = "";
            plan = HCFreshPlan(siteId);
            return HCEventReceiptOp.RESULT_DONE;
        }
        // These are site spends, not leases owned by a live event. Never release
        // them on event expiry: native cargo may still exist outside this scan.
        m_Refusal = "police_cache_grant_spent";
        if (phase == 3 || m_Granted.Find(siteId) >= 0) { return HCEventReceiptOp.RESULT_FAILED; }
        m_Refusal = "police_cache_position_recorded";
        if (HCHas(siteId + ".pos")) { return HCEventReceiptOp.RESULT_FAILED; }
        int repair = m_RepairPending.Find(siteId);
        if (repair < 0)
        {
            m_Refusal = "police_cache_repair_spent";
            if (HCHas(repairName)) { return HCEventReceiptOp.RESULT_FAILED; }
            m_Refusal = "police_cache_grant_spent";
            if (HCHas(name)) { return HCEventReceiptOp.RESULT_FAILED; }
        }
        m_Refusal = "police_cache_journal_fault";
        if (repair >= 0)
        {
            m_RepairPending.Remove(repair);
            // The marker is the spend: it is durable before any native creation.
            if (HCHas(repairName)) { m_Refusal = "police_cache_repair_spent"; return HCEventReceiptOp.RESULT_FAILED; }
            if (HCPut(repairName, "HC-POLICE-STOCK-REPAIR v1 " + siteId, 128, "") == HCEventReceiptOp.RESULT_FAILED) { Fault(); return HCEventReceiptOp.RESULT_FAILED; }
            m_CommitPhase.Set(siteId, 1);
            m_Refusal = "police_work_budget";
            return HCEventReceiptOp.RESULT_PENDING;
        }
        // A repair consumes its marker-backed allowance without rewriting the spent .txt.
        m_Granted.Insert(siteId);
        if (HCPut(name, "HC-POLICE-STOCK v1 " + siteId, 128, "") == HCEventReceiptOp.RESULT_FAILED) { Fault(); return HCEventReceiptOp.RESULT_FAILED; }
        m_CommitPhase.Set(siteId, 2);
        m_Refusal = "police_work_budget";
        return HCEventReceiptOp.RESULT_PENDING;
    }
    // The base grant primitive is not used for the police site spend (HCCommitStep).
    override HCEventRewardPlan Commit(string siteId)
    {
        m_Refusal = "police_cache_use_commit_step";
        return null;
    }

    // Ownership lives in this ledger, never in entity storage: extending Barrel_Green
    // OnStoreSave broke every persisted barrel ("Scripted variables corrupted", 103 boot).
    // Queued behind the other receipt writes; false when it could not be queued.
    bool RecordCache(string siteId, vector position)
    {
        if (m_Fault) { return false; }
        return HCPut(siteId + ".pos", position.ToString(false), 96, "") != HCEventReceiptOp.RESULT_FAILED;
    }

    // The one stock table: first creation, refill and replacement all use it.
    HCEventRewardPlan HCFreshPlan(string siteId)
    {
        HCEventRewardPlan plan = new HCEventRewardPlan;
        plan.SiteId = siteId;
        plan.Items.Insert("BandageDressing");
        plan.Items.Insert("SodaCan_Cola");
        plan.Items.Insert("MetalWire");
        return plan;
    }
    static bool HCSiteValid(string siteId)
    {
        return siteId == "coastal-police-source" || siteId == "inland-police-source";
    }
    // Persisted record complete (spent .txt plus recorded .pos) and the position valid.
    bool HCBarrelRecordPosition(string siteId, out vector position)
    {
        position = vector.Zero;
        if (!HCSiteValid(siteId)) { return false; }
        if (!HCLoaded() || !HCHas(siteId + ".txt")) { return false; }
        return CachePosition(siteId, position);
    }
    protected int HCEpochOf(string siteId, string name, string kind)
    {
        string prefix = siteId + "." + kind;
        if (name.IndexOf(prefix) != 0) { return 0; }
        int tail = name.Length() - prefix.Length();
        string digits = name.Substring(prefix.Length(), tail);
        int value = digits.ToInt();
        if (value < 1 || value.ToString() != digits) { return 0; }
        return value;
    }
    static bool HCIntToken(string token)
    {
        if (token == "") { return false; }
        return token.ToInt().ToString() == token;
    }
    // Four tokens starting at index -> "a b c d" or "" when any is not an integer.
    protected string HCJoinId(array<string> tokens, int index)
    {
        if (index + 4 > tokens.Count()) { return ""; }
        for (int part = 0; part < 4; part++)
        {
            if (!HCIntToken(tokens[index + part])) { return ""; }
        }
        return tokens[index] + " " + tokens[index + 1] + " " + tokens[index + 2] + " " + tokens[index + 3];
    }
    // null = unreadable or torn: exactly 11 base tokens plus whole id / prev / adopt groups.
    protected HCPoliceReceipt HCReadReceipt(string name, string tag, int generation)
    {
        if (!HCHas(name)) { return null; }
        string text = HCText(name);
        if (text == "") { return null; }
        array<string> tokens = new array<string>;
        text.Split(" ", tokens);
        int count = tokens.Count();
        if (count < 11) { return null; }
        if (tokens[0] != tag || tokens[1] != "v1" || tokens[3] != "gen" || tokens[4].ToInt() != generation || tokens[5] != "utc" || tokens[7] != "kind" || tokens[9] != "items") { return null; }
        HCPoliceReceipt receipt = new HCPoliceReceipt;
        receipt.Utc = tokens[6].ToInt();
        receipt.Items = tokens[10].ToInt();
        receipt.Kind = tokens[8];
        receipt.Id = "";
        receipt.Prev = "";
        int at = 11;
        while (at < count)
        {
            string key = tokens[at];
            if (key == "adopt")
            {
                if (receipt.Adopt || at + 2 > count || tokens[at + 1] != "1") { return null; }
                receipt.Adopt = true;
                at = at + 2;
            }
            else if (key == "id" || key == "prev")
            {
                string joined = HCJoinId(tokens, at + 1);
                if (joined == "") { return null; }
                if (key == "id")
                {
                    if (receipt.Id != "") { return null; }
                    receipt.Id = joined;
                }
                else
                {
                    if (receipt.Prev != "") { return null; }
                    receipt.Prev = joined;
                }
                at = at + 5;
            }
            else
            {
                return null;
            }
        }
        if (receipt.Adopt && receipt.Id == "") { return null; }
        if (receipt.Utc < 1) { return null; }
        return receipt;
    }
    // Identity an open generation works on. refill: its own id group; an id-less refill keeps no id
    // (never the completed state's: that id may belong to an older generation's barrel) and only the
    // prev carried by gen-N, so a barrel found later takes the safe adopt path (refill only);
    // replace/recreate: the bar-N id (when written) and the prev carried by gen-N/bar-N.
    protected void HCGenIdentity(string siteId, int number, HCPoliceReceipt gen, HCPoliceGeneration state, out string id, out string prev, out bool adopt)
    {
        id = "";
        prev = gen.Prev;
        adopt = false;
        if (gen.Kind == "refill")
        {
            id = gen.Id;
            adopt = gen.Adopt && gen.Id != "";
            return;
        }
        HCPoliceReceipt bar = HCReadReceipt(siteId + ".bar-" + number.ToString(), "HC-POLICE-BAR", number);
        if (bar)
        {
            id = bar.Id;
            if (bar.Prev != "") { prev = bar.Prev; }
        }
    }
    // Highest readable ok-k below bound (k < bound) from the listing; null = none. Bounded by the
    // 27-file listing.
    protected HCPoliceReceipt HCReadLowerOk(string siteId, array<string> names, int bound, out int found)
    {
        found = 0;
        int limit = bound;
        for (int round = 0; round < 27; round++)
        {
            int pick = 0;
            foreach (string scanned : names)
            {
                int scanNumber = HCEpochOf(siteId, scanned, "ok-");
                if (scanNumber > pick && scanNumber < limit) { pick = scanNumber; }
            }
            if (pick < 1) { return null; }
            limit = pick;
            HCPoliceReceipt lower = HCReadReceipt(siteId + ".ok-" + pick.ToString(), "HC-POLICE-OK", pick);
            if (lower)
            {
                found = pick;
                return lower;
            }
        }
        return null;
    }
    // Loads the receipts once per process; null = unavailable this process (never refuses boot).
    // Num is the highest number of any receipt file (readable or torn) so a new WriteNew never collides.
    // A torn gen-N is ignored (native work starts only after a successful readback). A torn ok-N
    // falls back to the readable gen-N utc and the identity gen-N/bar-N recorded; with gen-N also
    // unreadable the highest readable lower ok-k is the anchor. No readable anchor: Ok = 0 and the
    // caller re-arms durably.
    HCPoliceGeneration HCGeneration(string siteId)
    {
        if (!HCSiteValid(siteId) || m_Fault) { return null; }
        HCPoliceGeneration state;
        if (m_Generations.Find(siteId, state)) { return state; }
        // The loaded directory image (bounded at LISTING_CAP files, no sub-directories); null =
        // unavailable (stock only) or not loaded yet.
        if (!HCLoaded())
        {
            if (HCUnavailable() && !m_ListLogged)
            {
                m_ListLogged = true;
                Print("[HC Police] site=" + siteId + " action=receipt_unreadable reason=listing_unavailable_stock_only");
            }
            return null;
        }
        array<string> names = m_Files.GetKeyArray();
        state = new HCPoliceGeneration;
        int genMax = 0;
        int okMax = 0;
        foreach (string listed : names)
        {
            int genNumber = HCEpochOf(siteId, listed, "gen-");
            if (genNumber > genMax) { genMax = genNumber; }
            int okNumber = HCEpochOf(siteId, listed, "ok-");
            if (okNumber > okMax) { okMax = okNumber; }
        }
        state.Num = genMax;
        if (okMax > state.Num) { state.Num = okMax; }
        HCPoliceReceipt receipt;
        string identityId;
        string identityPrev;
        bool identityAdopt;
        bool okReadable = false;
        if (okMax > 0)
        {
            receipt = HCReadReceipt(siteId + ".ok-" + okMax.ToString(), "HC-POLICE-OK", okMax);
            if (receipt)
            {
                okReadable = true;
                state.Ok = okMax;
                state.OkUtc = receipt.Utc;
                state.Id = receipt.Id;
                state.Prev = receipt.Prev;
                state.Adopt = receipt.Adopt;
            }
            else
            {
                receipt = HCReadReceipt(siteId + ".gen-" + okMax.ToString(), "HC-POLICE-GEN", okMax);
                if (receipt)
                {
                    // Torn ok-N: the generation utc is the anchor; gen-N/bar-N supply the identity.
                    Print("[HC Police] site=" + siteId + " action=receipt_unreadable reason=ok_receipt_torn");
                    state.Ok = okMax;
                    state.OkUtc = receipt.Utc;
                    HCGenIdentity(siteId, okMax, receipt, state, identityId, identityPrev, identityAdopt);
                    state.Id = identityId;
                    state.Prev = identityPrev;
                    state.Adopt = identityAdopt;
                }
                else
                {
                    // Neither ok-N nor gen-N is readable: fall back to the highest readable lower ok-k.
                    int lowerOk = 0;
                    receipt = HCReadLowerOk(siteId, names, okMax, lowerOk);
                    if (receipt)
                    {
                        Print("[HC Police] site=" + siteId + " action=receipt_unreadable reason=ok_receipt_torn_lower_used");
                        okReadable = true;
                        state.Ok = lowerOk;
                        state.OkUtc = receipt.Utc;
                        // Keep the lower ok's time as the anchor but demote its identity: the older
                        // generation's barrel may already be gone, so its id must come back through
                        // the rollback path rather than count the live barrel as foreign.
                        state.Id = "";
                        if (receipt.Adopt)
                        {
                            state.Prev = "";
                        }
                        else
                        {
                            state.Prev = receipt.Id;
                        }
                        state.Adopt = false;
                    }
                    else
                    {
                        Print("[HC Police] site=" + siteId + " action=receipt_unreadable reason=ok_receipt_no_anchor");
                    }
                }
            }
        }
        state.Gen = state.Ok;
        if (genMax > state.Ok)
        {
            receipt = HCReadReceipt(siteId + ".gen-" + genMax.ToString(), "HC-POLICE-GEN", genMax);
            if (receipt)
            {
                state.Gen = genMax;
                state.GenUtc = receipt.Utc;
                state.GenItems = receipt.Items;
                state.GenKind = receipt.Kind;
                HCGenIdentity(siteId, genMax, receipt, state, identityId, identityPrev, identityAdopt);
                state.GenId = identityId;
                state.GenPrev = identityPrev;
                state.GenAdopt = identityAdopt;
            }
            else
            {
                Print("[HC Police] site=" + siteId + " action=receipt_unreadable reason=gen_receipt_torn_ignored");
            }
        }
        // Best-effort prune of superseded receipts; torn higher files are pruned by a later generation.
        // bar-N is kept while ok-N is torn: it is the only record of that generation's barrel id.
        foreach (string stale : names)
        {
            int staleGen = HCEpochOf(siteId, stale, "gen-");
            if (staleGen > 0 && state.Ok > 0 && (staleGen < state.Ok || (staleGen == state.Ok && okReadable))) { HCPrune(stale, ""); }
            int staleOk = HCEpochOf(siteId, stale, "ok-");
            if (staleOk > 0 && staleOk < state.Ok) { HCPrune(stale, ""); }
            int staleBar = HCEpochOf(siteId, stale, "bar-");
            if (staleBar > 0 && (staleBar < state.Ok || (staleBar == state.Ok && okReadable))) { HCPrune(stale, ""); }
        }
        m_Generations.Insert(siteId, state);
        return state;
    }
    // Cooldown and lifetime anchor: the last create/refill time from the durable receipt (0 = none).
    int HCEpochAnchor(HCPoliceGeneration state)
    {
        if (state.Gen > state.Ok) { return state.GenUtc; }
        return state.OkUtc;
    }
    // Identity groups appended to a receipt: id [prev] [adopt]. adopt needs an id.
    protected string HCIdentityText(string barrelId, string prevId, bool adopt)
    {
        string text = "";
        if (barrelId != "") { text = text + " id " + barrelId; }
        if (prevId != "") { text = text + " prev " + prevId; }
        if (barrelId != "" && adopt) { text = text + " adopt 1"; }
        return text;
    }
    // Writes a completed-generation marker that is not tied to an open gen: legacy migration,
    // first creation ("initial"), re-arm after a missing/future-dated anchor or a restored previous
    // barrel ("rearm") and a late-learned id ("idfix"). barrelId is the exact identity to record
    // ("" = unknown); utc is the anchor to record.
    bool HCEpochMark(string siteId, HCPoliceGeneration state, int utc, string kind, string barrelId, string prevId, bool adopt)
    {
        if (!HCLoaded() || utc < 1 || state.Num >= 1000000000) { return false; }
        int next = state.Num + 1;
        string text = "HC-POLICE-OK v1 " + siteId + " gen " + next.ToString() + " utc " + utc.ToString() + " kind " + kind + " items 0" + HCIdentityText(barrelId, prevId, adopt);
        if (HCPut(siteId + ".ok-" + next.ToString(), text, RECEIPT_LIMIT, "") == HCEventReceiptOp.RESULT_FAILED) { Fault(); return false; }
        state.Num = next;
        state.Ok = next;
        state.Gen = next;
        state.OkUtc = utc;
        state.GenUtc = 0;
        state.GenItems = 0;
        state.Id = barrelId;
        state.Prev = prevId;
        state.Adopt = adopt && barrelId != "";
        return true;
    }
    // Durable intent, written BEFORE any native create/delete/item of this generation.
    // carryId/carryPrev/carryAdopt: the identity of the barrel being worked on right now.
    // refill keeps that id (written explicitly, so a crashed earlier generation cannot lose it);
    // replace/recreate record it as prev when it is a deletable (not adopted) barrel.
    bool HCEpochBegin(string siteId, HCPoliceGeneration state, int now, string kind, int items, string carryId, string carryPrev, bool carryAdopt)
    {
        if (!HCLoaded() || now < 1 || items < 1 || state.Num >= 1000000000) { return false; }
        int next = state.Num + 1;
        string newId = "";
        string newPrev = "";
        bool newAdopt = false;
        if (kind == "refill")
        {
            newId = carryId;
            newPrev = carryPrev;
            newAdopt = carryAdopt;
        }
        else
        {
            if (carryId == "") { newPrev = carryPrev; }
            else if (!carryAdopt) { newPrev = carryId; }
        }
        string text = "HC-POLICE-GEN v1 " + siteId + " gen " + next.ToString() + " utc " + now.ToString() + " kind " + kind + " items " + items.ToString() + HCIdentityText(newId, newPrev, newAdopt);
        string genName = siteId + ".gen-" + next.ToString();
        if (HCPut(genName, text, RECEIPT_LIMIT, "") == HCEventReceiptOp.RESULT_FAILED) { Fault(); return false; }
        int prior = state.Gen;
        bool priorIncomplete = state.Gen > state.Ok;
        state.Num = next;
        state.Gen = next;
        state.GenUtc = now;
        state.GenItems = items;
        state.GenKind = kind;
        state.GenId = newId;
        state.GenPrev = newPrev;
        state.GenAdopt = newAdopt;
        if (priorIncomplete)
        {
            HCPrune(siteId + ".gen-" + prior.ToString(), genName);
            HCPrune(siteId + ".bar-" + prior.ToString(), genName);
        }
        return true;
    }
    // Identity of the barrel a replace/recreate generation just created, written BEFORE its items
    // so a crash mid-fill leaves a barrel the next boot can recognise as its own. Carries prev.
    bool HCEpochBarrel(string siteId, HCPoliceGeneration state, int now, string barrelId)
    {
        if (!HCLoaded() || state.Gen <= state.Ok || barrelId == "") { return false; }
        string text = "HC-POLICE-BAR v1 " + siteId + " gen " + state.Gen.ToString() + " utc " + now.ToString() + " kind " + state.GenKind + " items 0" + HCIdentityText(barrelId, state.GenPrev, false);
        if (HCPut(siteId + ".bar-" + state.Gen.ToString(), text, RECEIPT_LIMIT, "") == HCEventReceiptOp.RESULT_FAILED) { Fault(); return false; }
        state.GenId = barrelId;
        state.GenAdopt = false;
        return true;
    }
    // Completion marker for the open generation; carries the generation utc as the anchor, the
    // exact barrel identity of the generation ("" = unknown), its prev and the adopt flag.
    bool HCEpochComplete(string siteId, HCPoliceGeneration state, string kind, int now, string barrelId, bool adopt)
    {
        if (!HCLoaded() || state.Gen <= state.Ok) { return false; }
        int generation = state.Gen;
        int utc = state.GenUtc;
        if (utc < 1) { utc = now; }
        int items = state.GenItems;
        string prevId = state.GenPrev;
        string text = "HC-POLICE-OK v1 " + siteId + " gen " + generation.ToString() + " utc " + utc.ToString() + " kind " + kind + " items " + items.ToString() + HCIdentityText(barrelId, prevId, adopt);
        string okName = siteId + ".ok-" + generation.ToString();
        if (HCPut(okName, text, RECEIPT_LIMIT, "") == HCEventReceiptOp.RESULT_FAILED) { Fault(); return false; }
        int priorOk = state.Ok;
        state.Ok = generation;
        state.OkUtc = utc;
        state.Id = barrelId;
        state.Prev = prevId;
        state.Adopt = adopt && barrelId != "";
        HCPrune(siteId + ".gen-" + generation.ToString(), okName);
        HCPrune(siteId + ".bar-" + generation.ToString(), okName);
        if (priorOk > 0) { HCPrune(siteId + ".ok-" + priorOk.ToString(), okName); }
        return true;
    }
    // True when the recorded position file exists but is unreadable or zero (torn).
    bool HCPositionTorn(string siteId)
    {
        if (!HCLoaded() || !HCHas(siteId + ".pos")) { return false; }
        vector ignored;
        return !CachePosition(siteId, ignored);
    }

    bool CachePosition(string siteId, out vector position)
    {
        position = vector.Zero;
        if (!HCLoaded() || !HCHas(siteId + ".pos")) { return false; }
        string text = HCText(siteId + ".pos");
        if (text == "" || text.Length() > 96) { return false; }
        text.Trim();
        position = text.ToVector();
        return position != vector.Zero;
    }
}
// Native: 3_Game/AI/AIWorld.c:122 SampleNavmeshPosition, :65 PGFilter.SetFlags;
// Game.c GetWorld().GetAIWorld(). Outdoor walkable polygons only (INSIDE excluded).
class HCEventPoliceNav
{
    static vector Sample(vector wanted, float radius)
    {
        if (!GetGame() || !GetGame().GetWorld()) { return vector.Zero; }
        AIWorld world = GetGame().GetWorld().GetAIWorld();
        if (!world) { return vector.Zero; }
        PGFilter filter = new PGFilter;
        filter.SetFlags(PGPolyFlags.WALK, PGPolyFlags.DISABLED | PGPolyFlags.UNREACHABLE | PGPolyFlags.INSIDE | PGPolyFlags.SWIM | PGPolyFlags.SWIM_SEA | PGPolyFlags.LADDER | PGPolyFlags.JUMP | PGPolyFlags.CLIMB | PGPolyFlags.CRAWL | PGPolyFlags.CROUCH, PGPolyFlags.NONE);
        vector found;
        if (!world.SampleNavmeshPosition(wanted, radius, filter, found)) { return vector.Zero; }
        return found;
    }
}
// Retain native query order with a capped cargo handle snapshot per container.
// No inventory is cloned; fallbacks start only after the full capped scan.
class HCEventPoliceStockSlice
{
    ref array<Object> Nearby;
    int Next;
    int Stage;
    vector OwnedPosition;
    bool HasOwnedPosition;
    bool GroundBarrelPresent;
    // Up to 4 live barrels within 2 m of the recorded position (ruined or not); the one whose
    // persistent id matches the receipt is the site container (PoliceContainer decides).
    ref array<Barrel_Green> NearBarrels;
    bool NearCapped;
    ItemBase GroundItem;
    ItemBase DeliveryContainer;
    ItemBase CargoOwner;
    int CargoNext;
    ref array<ItemBase> CargoItems;
}
// Scene cache fill (owner 2026-11-22: a container item refills or drains and is replaced by a new
// one with new loot). CE alone creates, ages and replaces the SmallProtectorCase (events/cache-events.xml,
// lootmax=0, lifetime 3600): its hourly replacement IS the drain-and-replace. HC never creates, moves
// or deletes the case; it creates the fill items (plan.Items, vanilla stock) inside a case, at most
// once per case identity (the persistent id) within the receipt rule below.
// Which case: only a case that CE created in this process (ItemBase.HCEventEconomyCandidate: set in
// EEOnCECreate, in memory, never on a database load, cleared when the case goes into hands or under a
// player hierarchy) and that stands within CASE_RADIUS metres (horizontal) of the eventspawn position
// (mission.Source = events/cache-eventspawns.xml). A case a player placed or moved, or one that
// survived a restart, is refused (not_ce_created / not_at_eventspawn), never filled.
// Durable order, same intent-then-ok pattern as the police generations (immutable WriteNew files):
//   <site>.<id key>.int  written BEFORE any item exists (id, utc, planned count);
//   <site>.<id key>.ok   written after the items exist (id, the fill utc = min-spacing anchor, real count).
// An open intent is retried (empty case) only while it was written by this process; on any later boot
// an open intent is adopted as done whatever the case holds (fail closed: no duplicate fill). A case
// holding anything without an intent is skipped (logged once). An unreadable or zero id waits.
// An ok means the identity is not filled again while the receipt exists. Receipts are only needed
// within one process (the candidate flag does not survive a restart), so they are pruned after
// RECEIPT_RETENTION_SECONDS (2x the CE case lifetime), independent of any police container lifetime.
// The site RefillCooldownSeconds does NOT gate this fill: one fill per id is the duplicate guard and the
// CE lifetime is the replace cadence. Only a small MIN_SPACING_SECONDS floor from the site's last fill
// receipt guards against CE recreating a case at once (reason=min_spacing).
// The receipt directory is walked in steps: each step lists names only up to SCAN_STEP entries past a
// cursor and opens just those (memory and file opens per step stay bounded whatever the directory
// holds), pruning at most PRUNE_LIMIT per step. The fill waits (scan_pending) until the first pass over
// the whole directory has finished; a new pass starts after RECEIPT_RETENTION_SECONDS of uptime.
// Native: EntityAI.c:3374 GetPersistentID; Inventory.c CreateInInventory/GetCargo; EnSystem.c FindFile.
class HCEventCacheFillIO : HCEventJournalIO
{
    void HCEventCacheFillIO()
    {
        m_Root = "$profile:HollowCountry/Events/cache-fill";
        m_Label = "cache fill directory";
    }
}
class HCEventCacheFillSite
{
    // Receipt walk: Cursor = surviving receipt names already read in the pass in progress; Loaded = the
    // first pass over the whole directory finished; PassUtc = when the last pass finished.
    bool Scanning;
    bool Loaded;
    int Cursor;
    int PassUtc;
    // Newest completed fill (items > 0) of this site: the min-spacing anchor.
    int LastUtc;
    // The batch being read: names listed past Cursor, how many were read, how many were pruned, the
    // receipt chosen for pruning (removed on the next step) and whether the listing ended.
    ref array<string> Batch;
    int BatchAt;
    int Removed;
    string PruneName;
    bool Listed;
    bool Ended;
}
// One scene cache case being filled. The job advances one native file call per HCEventCacheFill.HCStepFill
// (driven every module tick); the observer probe (Step) only creates it, re-arms it and harvests the result.
class HCEventCacheFillJob
{
    string SiteId;
    string Id;
    string Key;
    string DoneKey;
    string OkName;
    string IntName;
    ItemBase Item;
    int Phase;
    int Held;
    int Created;
    int Granted;
    int AfterWrite;
    int Utc;
    bool IntentOpen;
    bool Resolved;
    ref HCEventReceiptOp Write;
}
class HCEventCacheFill
{
    static const int RECEIPT_LIMIT = 192;
    // Directory entries walked (names only) per step; a pass that reaches it ends there.
    static const int ENUM_LIMIT = 512;
    static const int SCAN_STEP = 6;
    static const int PRUNE_LIMIT = 4;
    static const int ATTEMPT_LIMIT = 3;
    static const int MIN_SPACING_SECONDS = 600;
    // Twice the CE case lifetime (3600 s in cache-events.xml).
    static const int RECEIPT_RETENTION_SECONDS = 7200;
    static const float CASE_RADIUS = 2;
    static const int SAY_PAIR_LIMIT = 8;
    static const int TRACK_LIMIT = 16;
    static const int ENSURE_RETRY_SECONDS = 60;
    // Job phases. Each HCStepFill call runs the current phase: a phase either makes one file call or
    // is memory/world work only (then the next phase runs on the next call).
    static const int PHASE_OK = 0;
    static const int PHASE_SCAN = 1;
    static const int PHASE_INTENT = 2;
    static const int PHASE_DECIDE = 3;
    static const int PHASE_ADOPT_READ = 4;
    static const int PHASE_WRITE = 5;
    static const int PHASE_CREATE = 6;
    static const int PHASE_PARKED = 7;
    static const int PHASE_DONE = 8;
    static const int WRITE_INTENT = 1;
    static const int WRITE_OK = 2;
    static const int WRITE_ADOPT = 3;
    protected static ref HCEventCacheFillIO s_IO;
    protected static ref map<string, ref HCEventCacheFillSite> s_Sites = new map<string, ref HCEventCacheFillSite>;
    protected static ref array<string> s_Done = new array<string>;
    // Case keys whose intent receipt this process wrote (only these may retry an open intent).
    protected static ref array<string> s_Intents = new array<string>;
    // Failed create attempts per case key (site|id key).
    protected static ref map<string, int> s_Attempts = new map<string, int>;
    protected static ref array<string> s_Logged = new array<string>;
    protected static ref map<string, int> s_PairShown = new map<string, int>;
    protected static ref array<string> s_BindLogged = new array<string>;
    protected static ref array<ref HCEventCacheFillJob> s_Jobs = new array<ref HCEventCacheFillJob>;
    protected static int s_Dropped;
    protected static bool s_Fault;
    // Receipt directory ensure: 0..2 stages, 3 = ready, -1 = refused (retried after ENSURE_RETRY_SECONDS).
    protected static int s_EnsureStage;
    protected static float s_EnsureRetryAt;
    protected static int s_JobCursor;

    // "" = zero id (not yet assigned or unreadable): never fill.
    static string CacheId(ItemBase item)
    {
        int b1;
        int b2;
        int b3;
        int b4;
        if (!item) { return ""; }
        item.GetPersistentID(b1, b2, b3, b4);
        if (b1 == 0 && b2 == 0 && b3 == 0 && b4 == 0) { return ""; }
        return b1.ToString() + " " + b2.ToString() + " " + b3.ToString() + " " + b4.ToString();
    }
    // File-name safe form of an id: spaces become '_', a minus sign becomes 'n'.
    static string KeyOf(string id)
    {
        string key = id;
        key.Replace(" ", "_");
        key.Replace("-", "n");
        return key;
    }
    protected static bool HasSuffix(string name, string suffix)
    {
        int at = name.Length() - suffix.Length();
        if (at < 1) { return false; }
        return name.Substring(at, suffix.Length()) == suffix;
    }
    // One line per site and reason. Each (action, reason) pair shows at most SAY_PAIR_LIMIT sites;
    // the first line dropped for a pair prints once with the running count of dropped lines.
    protected static void Say(string siteId, string action, string reason)
    {
        string key = siteId + ":" + action + ":" + reason;
        if (s_Logged.Find(key) >= 0) { return; }
        s_Logged.Insert(key);
        string pair = action + ":" + reason;
        int shown = 0;
        s_PairShown.Find(pair, shown);
        if (shown >= SAY_PAIR_LIMIT)
        {
            s_Dropped++;
            if (shown == SAY_PAIR_LIMIT)
            {
                s_PairShown.Set(pair, shown + 1);
                Print("[HC Events] scene cache fill; log cap reached; action=" + action + "; reason=" + reason + "; dropped_lines=" + s_Dropped.ToString() + " runtime=PENDING");
            }
            return;
        }
        s_PairShown.Set(pair, shown + 1);
        Print("[HC Events] scene cache fill; " + siteId + "; action=" + action + "; reason=" + reason + " runtime=PENDING");
    }
    // Not resolved: retried on the next bounded probe.
    protected static bool HCWaitSite(string siteId, string reason)
    {
        Say(siteId, "waiting", reason);
        return false;
    }
    // Resolved without a fill for this case.
    protected static bool Refuse(string siteId, string reason)
    {
        Say(siteId, "refused", reason);
        return true;
    }
    // Bind diagnostic, once per site and (ce_created, id_zero) state per boot: lets the lead confirm
    // that EEOnCECreate fires for CE event children and whether the persistent id is assigned.
    protected static void BindLine(string siteId, bool ceCreated, string id, float dist)
    {
        int ce = 0;
        if (ceCreated) { ce = 1; }
        int zero = 1;
        string idKey = "";
        if (id != "")
        {
            zero = 0;
            idKey = KeyOf(id);
        }
        string key = siteId + ":" + ce.ToString() + ":" + zero.ToString();
        if (s_BindLogged.Count() >= TRACK_LIMIT || s_BindLogged.Find(key) >= 0) { return; }
        s_BindLogged.Insert(key);
        Print("[HC Events] cache bind ce_created=" + ce.ToString() + " id_zero=" + zero.ToString() + " site=" + siteId + " id=" + idKey + " dist=" + Meters(dist) + " runtime=PENDING");
    }
    // Horizontal distance only: the eventspawn position has no authored height.
    protected static float SpawnDistance(ItemBase item, HCEventMission mission)
    {
        vector at = item.GetPosition();
        float dx = at[0] - mission.Source[0];
        float dz = at[2] - mission.Source[2];
        return Math.Sqrt(dx * dx + dz * dz);
    }
    // Metres with two decimals (the script float has no fixed-decimals formatter).
    protected static string Meters(float metres)
    {
        int hundredths = Math.Round(metres * 100);
        string fraction = (hundredths % 100).ToString();
        if (fraction.Length() < 2) { fraction = "0" + fraction; }
        return (hundredths / 100).ToString() + "." + fraction;
    }
    protected static void MarkDone(string doneKey)
    {
        if (s_Done.Count() >= TRACK_LIMIT) { s_Done.RemoveOrdered(0); }
        s_Done.Insert(doneKey);
    }
    protected static void MarkIntent(string doneKey)
    {
        if (s_Intents.Find(doneKey) >= 0) { return; }
        if (s_Intents.Count() >= TRACK_LIMIT) { s_Intents.RemoveOrdered(0); }
        s_Intents.Insert(doneKey);
    }
    protected static void ForgetIntent(string doneKey)
    {
        int at = s_Intents.Find(doneKey);
        if (at >= 0) { s_Intents.RemoveOrdered(at); }
    }
    // 12 tokens: tag v1 site id a b c d utc U items N. Anything else is torn.
    protected static bool ParseReceipt(string text, string tag, string siteId, out int utc, out int items)
    {
        utc = 0;
        items = 0;
        if (text == "") { return false; }
        array<string> tokens = new array<string>;
        text.Split(" ", tokens);
        if (tokens.Count() != 12) { return false; }
        if (tokens[0] != tag || tokens[1] != "v1" || tokens[2] != siteId || tokens[3] != "id" || tokens[8] != "utc" || tokens[10] != "items") { return false; }
        utc = tokens[9].ToInt();
        items = tokens[11].ToInt();
        return utc > 0 && items >= 0;
    }
    protected static string ReceiptText(string tag, string siteId, string id, int utc, int items)
    {
        return tag + " v1 " + siteId + " id " + id + " utc " + utc.ToString() + " items " + items.ToString();
    }
    protected static HCEventReceiptOp BeginReceipt(string name, string text)
    {
        HCEventReceiptOp op = new HCEventReceiptOp;
        op.HCBegin(name, s_IO.HCPath(name), text, HCEventReceiptOp.MODE_NEW, "");
        return op;
    }
    // Names only, no file is opened: the receipt names (.ok / .int) after the first `skip`
    // of them, at most SCAN_STEP. True when the directory ended (or ENUM_LIMIT entries were walked).
    protected static bool ListStep(string siteId, int skip, array<string> batch)
    {
        string fileName;
        FileAttr attributes;
        FindFileHandle handle = FindFile(s_IO.HCPath(siteId + ".*"), fileName, attributes, FindFileFlags.ALL);
        if (!handle) { return true; }
        bool more = fileName != "";
        int walked = 0;
        int matched = 0;
        bool ended = true;
        while (more)
        {
            if (batch.Count() >= SCAN_STEP || walked >= ENUM_LIMIT)
            {
                ended = walked >= ENUM_LIMIT;
                break;
            }
            walked++;
            if (attributes != FileAttr.DIRECTORY && (HasSuffix(fileName, ".ok") || HasSuffix(fileName, ".int")))
            {
                if (matched >= skip) { batch.Insert(fileName); }
                matched++;
            }
            more = FindNextFile(handle, fileName, attributes);
        }
        CloseFindFile(handle);
        return ended;
    }
    protected static HCEventCacheFillSite SiteOf(string siteId)
    {
        HCEventCacheFillSite site;
        if (!s_Sites.Find(siteId, site))
        {
            site = new HCEventCacheFillSite;
            s_Sites.Set(siteId, site);
        }
        return site;
    }
    protected static HCEventCacheFillJob JobOf(string doneKey)
    {
        foreach (HCEventCacheFillJob job : s_Jobs)
        {
            if (job.DoneKey == doneKey) { return job; }
        }
        return null;
    }
    // A finished job nobody harvested (its mission ended first) is forgotten, oldest first.
    protected static void DropResolved()
    {
        foreach (HCEventCacheFillJob finished : s_Jobs)
        {
            if (finished.Resolved)
            {
                s_Jobs.RemoveItem(finished);
                return;
            }
        }
    }
    protected static void Resolve(HCEventCacheFillJob job)
    {
        job.Resolved = true;
        job.Phase = PHASE_DONE;
        job.Write = null;
    }
    // Final without a fill (refused for good).
    protected static void Close(HCEventCacheFillJob job, string reason)
    {
        Refuse(job.SiteId, reason);
        Resolve(job);
    }
    // One bounded probe for the case bound to a scene cache mission (called by the observer every 30 s
    // while the fill is unresolved). Memory only: it creates the fill job, re-arms a waiting one and
    // returns its result. True when this case is resolved (filled, adopted, already done, skipped or
    // refused for good) and need not be probed again; false while the job or a later probe may still fill it.
    // granted = items created by the job, reported once when it is harvested.
    static bool Step(HCEventMission mission, ItemBase item, out int granted)
    {
        granted = 0;
        if (!mission || !item || !GetGame() || !GetGame().IsServer()) { return true; }
        if (!HCEventCacheSpawner.HCPhysicalGround(item)) { return true; }
        string siteId = mission.SiteId;
        HCEventRewardPlan plan = HCEventReviewedSites.StockPlan(siteId);
        if (!plan) { return Refuse(siteId, "no_stock_plan"); }
        string id = CacheId(item);
        bool ceCreated = item.HCEventEconomyCandidate();
        float dist = SpawnDistance(item, mission);
        BindLine(siteId, ceCreated, id, dist);
        if (!ceCreated) { return Refuse(siteId, "not_ce_created"); }
        if (dist > CASE_RADIUS) { return Refuse(siteId, "not_at_eventspawn"); }
        HCW38SituationPolicy policy = HCW38SituationPolicy.HCGet();
        int now = HCInfectedClock.UtcSeconds();
        if (!policy || now < 1) { return HCWaitSite(siteId, "clock_or_policy_unavailable"); }
        if (s_Fault) { return Refuse(siteId, "journal_unavailable"); }
        if (id == "") { return HCWaitSite(siteId, "id_unreadable"); }
        string key = KeyOf(id);
        string doneKey = siteId + "|" + key;
        HCEventCacheFillJob job = JobOf(doneKey);
        if (job)
        {
            if (job.Resolved)
            {
                granted = job.Granted;
                s_Jobs.RemoveItem(job);
                return true;
            }
            // A waiting job decides again (spacing, players, budget) on its next step.
            job.Item = item;
            if (job.Phase == PHASE_PARKED) { job.Phase = PHASE_DECIDE; }
            return false;
        }
        if (s_Done.Find(doneKey) >= 0) { return true; }
        CargoBase cargo = null;
        if (item.GetInventory()) { cargo = item.GetInventory().GetCargo(); }
        if (!cargo) { return Refuse(siteId, "no_cargo"); }
        if (s_Jobs.Count() >= TRACK_LIMIT) { DropResolved(); }
        if (s_Jobs.Count() >= TRACK_LIMIT) { return HCWaitSite(siteId, "fill_queue_full"); }
        job = new HCEventCacheFillJob;
        job.SiteId = siteId;
        job.Id = id;
        job.Key = key;
        job.DoneKey = doneKey;
        job.OkName = siteId + "." + key + ".ok";
        job.IntName = siteId + "." + key + ".int";
        job.Item = item;
        job.Phase = PHASE_OK;
        s_Jobs.Insert(job);
        return HCWaitSite(siteId, "receipt_check_pending");
    }
    // One staged step per call (HCEventModule tick): advances ONE fill job by ONE phase. A phase makes
    // at most one native file call (the receipt checks, one directory read or prune, one write stage)
    // or does only memory/world work. Returns true when a counted file call ran.
    static bool HCStepFill()
    {
        if (s_Jobs.Count() < 1 || s_Fault) { return false; }
        if (!s_IO) { s_IO = new HCEventCacheFillIO; }
        if (s_EnsureStage < 0)
        {
            if (GetGame().GetTickTime() >= s_EnsureRetryAt) { s_EnsureStage = 0; }
            return false;
        }
        if (s_EnsureStage < 3)
        {
            s_EnsureStage = HCEventReceiptFiles.EnsureStep(s_EnsureStage, "$profile:HollowCountry/Events/cache-fill");
            if (s_EnsureStage < 0)
            {
                s_EnsureRetryAt = GetGame().GetTickTime() + ENSURE_RETRY_SECONDS;
                s_IO.HCRefuse("state_directory_unavailable");
            }
            return true;
        }
        HCEventCacheFillJob job = NextJob();
        if (!job) { return false; }
        return HCStepJob(job);
    }
    // Round robin over the jobs that have a step to run; finished jobs nobody harvested are dropped.
    protected static HCEventCacheFillJob NextJob()
    {
        int total = s_Jobs.Count();
        for (int offset = 0; offset < total; offset++)
        {
            int index = (s_JobCursor + offset) % total;
            HCEventCacheFillJob candidate = s_Jobs[index];
            if (candidate.Resolved || candidate.Phase == PHASE_PARKED) { continue; }
            s_JobCursor = index + 1;
            return candidate;
        }
        return null;
    }
    protected static bool HCStepJob(HCEventCacheFillJob job)
    {
        ItemBase item = job.Item;
        if (job.Phase != PHASE_WRITE && (!item || !HCEventCacheSpawner.HCPhysicalGround(item)))
        {
            // The case left the world mid-fill: nothing more is written for it. An intent already
            // written stays; a later boot adopts it as done (never a second fill).
            Close(job, "case_gone");
            return false;
        }
        if (job.Phase == PHASE_OK)
        {
            if (s_IO.Exists(job.OkName))
            {
                MarkDone(job.DoneKey);
                Resolve(job);
            }
            else { job.Phase = PHASE_SCAN; }
            return true;
        }
        if (job.Phase == PHASE_SCAN) { return HCStepScan(job); }
        if (job.Phase == PHASE_INTENT)
        {
            job.IntentOpen = s_IO.Exists(job.IntName);
            job.Phase = PHASE_DECIDE;
            return true;
        }
        if (job.Phase == PHASE_ADOPT_READ)
        {
            int intentUtc;
            int intentItems;
            string intentText = HCEventReceiptFiles.ReadText(s_IO.HCPath(job.IntName), RECEIPT_LIMIT);
            if (!ParseReceipt(intentText, "HC-CACHEFILL-INT", job.SiteId, intentUtc, intentItems)) { intentUtc = HCInfectedClock.UtcSeconds(); }
            job.Utc = intentUtc;
            // Intent without ok: with items present the fill happened and only the ok was lost; from an
            // earlier process nothing proves the case is still ours to fill, so it counts as done.
            job.Write = BeginReceipt(job.OkName, ReceiptText("HC-CACHEFILL-OK", job.SiteId, job.Id, intentUtc, job.Held));
            job.AfterWrite = WRITE_ADOPT;
            job.Phase = PHASE_WRITE;
            return true;
        }
        if (job.Phase == PHASE_WRITE) { return HCStepWrite(job); }
        if (job.Phase == PHASE_CREATE) { return HCStepCreate(job); }
        if (job.Phase == PHASE_DECIDE) { return HCStepDecide(job); }
        return false;
    }
    // One receipt write stage (FileExist / OpenFile / FPrint / read-back).
    protected static bool HCStepWrite(HCEventCacheFillJob job)
    {
        int result = job.Write.HCStepOp();
        if (result == HCEventReceiptOp.RESULT_PENDING) { return true; }
        job.Write = null;
        if (result == HCEventReceiptOp.RESULT_FAILED)
        {
            s_Fault = true;
            if (job.AfterWrite == WRITE_OK) { Close(job, "ok_write_failed"); }
            else { Close(job, "receipt_write_failed"); }
            return true;
        }
        if (job.AfterWrite == WRITE_INTENT)
        {
            MarkIntent(job.DoneKey);
            job.IntentOpen = true;
            job.Phase = PHASE_CREATE;
            return true;
        }
        int now = HCInfectedClock.UtcSeconds();
        HCEventCacheFillSite site = SiteOf(job.SiteId);
        MarkDone(job.DoneKey);
        ForgetIntent(job.DoneKey);
        if (job.AfterWrite == WRITE_ADOPT)
        {
            if (job.Held > 0 && job.Utc > site.LastUtc) { site.LastUtc = job.Utc; }
            Print("[HC Events] scene cache fill; " + job.SiteId + "; action=adopted; items=" + job.Held.ToString() + "; id=" + job.Key + " runtime=PENDING");
            Resolve(job);
            return true;
        }
        s_Attempts.Remove(job.DoneKey);
        site.LastUtc = now;
        job.Granted = job.Created;
        HCEventRewardPlan plan = HCEventReviewedSites.StockPlan(job.SiteId);
        if (plan && job.Created < plan.Items.Count()) { Say(job.SiteId, "partial", "created_" + job.Created.ToString() + "_of_" + plan.Items.Count().ToString()); }
        Print("[HC Events] scene cache fill; " + job.SiteId + "; action=filled; items=" + job.Created.ToString() + "; id=" + job.Key + " runtime=PENDING");
        HCModuleReadiness.HCUse("Events", "cache_filled");
        Resolve(job);
        return true;
    }
    // Memory/world only: the item creation after the durable intent. Returns false (no file call).
    protected static bool HCStepCreate(HCEventCacheFillJob job)
    {
        ItemBase item = job.Item;
        HCEventRewardPlan plan = HCEventReviewedSites.StockPlan(job.SiteId);
        if (!plan)
        {
            Close(job, "no_stock_plan");
            return false;
        }
        int created = 0;
        foreach (string itemClass : plan.Items)
        {
            if (!HCEventCacheSpawner.HCPhysicalGround(item) || !item.GetInventory() || !item.GetInventory().CreateInInventory(itemClass)) { break; }
            created++;
        }
        if (created < 1)
        {
            int attempts = 0;
            s_Attempts.Find(job.DoneKey, attempts);
            if (s_Attempts.Count() >= TRACK_LIMIT) { s_Attempts.Clear(); }
            s_Attempts.Set(job.DoneKey, attempts + 1);
            HCWaitSite(job.SiteId, "create_failed");
            job.Phase = PHASE_PARKED;
            return false;
        }
        job.Created = created;
        job.Write = BeginReceipt(job.OkName, ReceiptText("HC-CACHEFILL-OK", job.SiteId, job.Id, HCInfectedClock.UtcSeconds(), created));
        job.AfterWrite = WRITE_OK;
        job.Phase = PHASE_WRITE;
        return false;
    }
    // Memory/world only: what to do with the case now. Returns false (no file call).
    protected static bool HCStepDecide(HCEventCacheFillJob job)
    {
        ItemBase item = job.Item;
        HCW38SituationPolicy policy = HCW38SituationPolicy.HCGet();
        int now = HCInfectedClock.UtcSeconds();
        if (!policy || now < 1)
        {
            HCWaitSite(job.SiteId, "clock_or_policy_unavailable");
            job.Phase = PHASE_PARKED;
            return false;
        }
        CargoBase cargo = null;
        if (item.GetInventory()) { cargo = item.GetInventory().GetCargo(); }
        if (!cargo)
        {
            Close(job, "no_cargo");
            return false;
        }
        int held = cargo.GetItemCount();
        job.Held = held;
        bool ownIntent = s_Intents.Find(job.DoneKey) >= 0;
        if (job.IntentOpen && (held > 0 || !ownIntent))
        {
            job.Phase = PHASE_ADOPT_READ;
            return false;
        }
        if (!job.IntentOpen && held > 0)
        {
            // Never touch a case that already holds anything (a player's items).
            Say(job.SiteId, "skip_nonempty", "case_not_empty");
            job.Phase = PHASE_PARKED;
            return false;
        }
        int attempts = 0;
        s_Attempts.Find(job.DoneKey, attempts);
        if (attempts >= ATTEMPT_LIMIT)
        {
            Close(job, "fill_failed");
            return false;
        }
        HCEventCacheFillSite site = SiteOf(job.SiteId);
        if (!job.IntentOpen && site.LastUtc > 0)
        {
            int last = site.LastUtc;
            if (last > now) { last = now; }
            if (now - last < MIN_SPACING_SECONDS)
            {
                HCWaitSite(job.SiteId, "min_spacing");
                job.Phase = PHASE_PARKED;
                return false;
            }
        }
        if (HCEventCacheSpawner.PolicePlayersWithin(item.GetPosition(), policy.RefillClearRadius))
        {
            HCWaitSite(job.SiteId, "players_near");
            job.Phase = PHASE_PARKED;
            return false;
        }
        if (job.IntentOpen)
        {
            job.Phase = PHASE_CREATE;
            return false;
        }
        HCEventRewardPlan plan = HCEventReviewedSites.StockPlan(job.SiteId);
        if (!plan)
        {
            Close(job, "no_stock_plan");
            return false;
        }
        job.Write = BeginReceipt(job.IntName, ReceiptText("HC-CACHEFILL-INT", job.SiteId, job.Id, now, plan.Items.Count()));
        job.AfterWrite = WRITE_INTENT;
        job.Phase = PHASE_WRITE;
        return false;
    }
    // At most SCAN_STEP receipts are read per pass step, one file call per call. The newest completed fill
    // becomes the min-spacing anchor, and receipts older than RECEIPT_RETENTION_SECONDS (never the
    // current identity) are pruned, at most PRUNE_LIMIT per batch. The fill waits until the first pass over
    // the whole directory has finished; a later pass runs in the background of the fill, never blocking it.
    protected static bool HCStepScan(HCEventCacheFillJob job)
    {
        HCEventCacheFillSite site = SiteOf(job.SiteId);
        int now = HCInfectedClock.UtcSeconds();
        if (!site.Scanning)
        {
            if (site.Loaded && now - site.PassUtc < RECEIPT_RETENTION_SECONDS)
            {
                job.Phase = PHASE_INTENT;
                return false;
            }
            site.Scanning = true;
            site.Cursor = 0;
            site.Listed = false;
            return false;
        }
        if (site.PruneName != "")
        {
            string pruning = site.PruneName;
            site.PruneName = "";
            if (s_IO.Remove(pruning)) { site.Removed++; }
            return true;
        }
        if (!site.Listed)
        {
            site.Batch = new array<string>;
            site.Ended = ListStep(job.SiteId, site.Cursor, site.Batch);
            site.BatchAt = 0;
            site.Removed = 0;
            site.Listed = true;
            return false;
        }
        if (site.BatchAt < site.Batch.Count())
        {
            string name = site.Batch[site.BatchAt];
            site.BatchAt++;
            bool isOk = HasSuffix(name, ".ok");
            string tag = "HC-CACHEFILL-INT";
            if (isOk) { tag = "HC-CACHEFILL-OK"; }
            int utc;
            int items;
            string text = HCEventReceiptFiles.ReadText(s_IO.HCPath(name), RECEIPT_LIMIT);
            if (!ParseReceipt(text, tag, job.SiteId, utc, items)) { return true; }
            if (isOk && items > 0 && utc > site.LastUtc) { site.LastUtc = utc; }
            if (site.Removed < PRUNE_LIMIT && name != job.OkName && name != job.IntName && utc < now - RECEIPT_RETENTION_SECONDS) { site.PruneName = name; }
            return true;
        }
        // A removed name no longer counts as already read.
        site.Cursor = site.Cursor + site.Batch.Count() - site.Removed;
        site.Listed = false;
        if (site.Ended)
        {
            site.Scanning = false;
            site.Loaded = true;
            site.PassUtc = now;
            job.Phase = PHASE_INTENT;
        }
        return false;
    }
}
// One police generation in flight (refill / replace / recreate): gen-N is queued first and every
// native mutation waits for it to be durable; a new barrel waits for bar-N before its items.
class HCPoliceGenJob
{
    string SiteId;
    string Kind;
    string Reason;
    string GenName;
    string BarName;
    int Stage;
    int Now;
    vector Position;
    Barrel_Green Old;
    Barrel_Green Barrel;
    string BarrelId;
    bool Adopt;
}
class HCEventCacheSpawner
{
    static const int GEN_WAIT_GEN = 0;
    static const int GEN_WAIT_BAR = 1;
    static const int PENDING_KEEP = 8;
    // Upper bound for the native physical-stock sphere around a mission source (metres).
    static const float SCAN_RADIUS_MAX = 25;
    protected static ref map<string, ref HCEventPoliceStockSlice> s_StockSlices = new map<string, ref HCEventPoliceStockSlice>;
    protected static ref HCEventPoliceStockLedger s_PoliceLedger;
    protected static ref map<string, ref HCPoliceGenJob> s_GenJobs = new map<string, ref HCPoliceGenJob>;
    // Missions whose first police grant is waiting for its durable marker (CreatePoliceStock).
    protected static ref array<string> s_CreatePending = new array<string>;
    protected static int s_ReceiptSteps;
    protected static ref array<string> s_PoliceLogged = new array<string>;
    // Per process only: a restart forgets every live event target (and so every bound container).
    protected static ref array<ref HCEventTarget> s_PoliceTargets;
    // Containers held by DELIVERY-family targets (weak handles): only those bind a barrel; a stock
    // target in s_PoliceTargets also records its barrel but holds nothing.
    protected static ref array<ItemBase> s_PoliceDeliveryHolds = new array<ItemBase>;
    // Sticky per process: set when a delivery hold could not be recorded after pruning.
    protected static bool s_PoliceHoldOverflow = false;
    protected static ref map<string, ref HCPoliceIdWatch> s_PoliceIdWatch;
    protected static ref array<string> s_PoliceCreatedSites = new array<string>;
    protected static int s_PoliceProbeLines;
    static const int POLICE_OWN_FOREIGN = -1;
    static const int POLICE_OWN_NONE = 0;
    static const int POLICE_OWN_OURS = 1;
    static const int POLICE_OWN_ADOPTED = 2;
    static const int POLICE_OWN_ROLLBACK = 3;
    static const int POLICE_OWN_UNREADABLE = 4;

    protected static int s_PoliceQueryPeak;
    protected static int s_CacheQueryPeak;
    // The native query allocates the entire sphere before returning. Isolate
    // its peak from inspection/cargo/ledger work without changing stock order,
    // overflow refusal, radius, retry semantics or the durability barrier.
    static void HCStockQueryCost(int began, bool police)
    {
        int cost = TickCount(began);
        string consumer = "SITUATIONS";
        if (police)
        {
            if (cost <= s_PoliceQueryPeak) { return; }
            s_PoliceQueryPeak = cost;
            consumer = "POLICE_BIND";
        }
        else
        {
            if (cost <= s_CacheQueryPeak) { return; }
            s_CacheQueryPeak = cost;
        }
        if (cost >= 40000)
        {
            Print("[HC Events] stock_query consumer=" + consumer + " ticks_max=" + cost.ToString() + " atomic=1 runtime=PENDING");
        }
    }

    protected static string s_PoliceReason;
    protected static string s_PoliceDetails;

    static string PoliceReason() { return s_PoliceReason; }
    static string PoliceDetails() { return s_PoliceDetails; }
    static void PoliceRefused(string reason, string details = "")
    {
        s_PoliceReason = reason;
        s_PoliceDetails = details;
    }

    static HCEventPoliceStockLedger PoliceLedger()
    {
        if (!s_PoliceLedger)
        {
            HCEventRewardPool pool = new HCEventRewardPool;
            pool.MaxCaches = 2;
            pool.ItemsPerCache = 3;
            pool.Entries.Insert(HCEventRewardPools.Entry("BandageDressing", 2));
            pool.Entries.Insert(HCEventRewardPools.Entry("SodaCan_Cola", 2));
            pool.Entries.Insert(HCEventRewardPools.Entry("MetalWire", 2));
            HCEventPoliceStockLedger created = new HCEventPoliceStockLedger;
            s_PoliceLedger = created;
            HCEventPoliceRewardIO policeIO = new HCEventPoliceRewardIO;
            s_PoliceLedger.Configure(policeIO, pool);
        }
        return s_PoliceLedger;
    }
    static HCEventTarget PoliceTarget(string missionId)
    {
        if (!s_PoliceTargets) { return null; }
        foreach (HCEventTarget target : s_PoliceTargets)
        {
            if (target.MissionId == missionId) { return target; }
        }
        return null;
    }
    static HCEventTarget CreatePolice(HCEventMission mission)
    {
        PoliceRefused("");
        if (!HCEventSites.PoliceSupplies(mission)) { PoliceRefused("police_mission_mismatch"); return null; }
        if (!HCEventSitesGate.Admitted()) { PoliceRefused("police_gate_closed"); return null; }
        if (!GetGame() || !GetGame().IsServer()) { PoliceRefused("police_server_unavailable"); return null; }
        if (!HCEventRuntimePolicy.MissionValid(mission, mission.WorldName)) { PoliceRefused("police_mission_invalid"); return null; }
        HCEventTarget existing = PoliceTarget(mission.Id);
        if (existing) { return existing; }
        // Keep the CE lookup at the exact origin; only the HC fallback uses navmesh.
        SpawnPoliceSlice(mission);
        return PoliceTarget(mission.Id);
    }
    static HCEventTarget Create(HCEventMission mission)
    {
        if (!mission || !mission.RewardCache || mission.Family != HCEventFamily.RECOVERY) { return null; }
        if (!HCEventSitesGate.Admitted() || !GetGame() || !GetGame().IsServer()) { return null; }
        if (!HCEventRuntimePolicy.MissionValid(mission, mission.WorldName)) { return null; }
        return Spawn(mission, mission.Source, mission.ItemClass, false);
    }
    // Used only for newly reserved HC stock; never moves existing world stock.
    static vector SpawnPosition(HCEventMission mission, vector anchor, bool police)
    {
        if (police) { PoliceRefused(""); }
        if (!mission) { if (police) { PoliceRefused("police_mission_invalid"); } return vector.Zero; }
        if (!GetGame() || !GetGame().IsServer()) { if (police) { PoliceRefused("police_server_unavailable"); } return vector.Zero; }
        float height = GetGame().SurfaceY(anchor[0], anchor[2]);
        if (height != height)
        {
            if (police) { PoliceRefused("police_terrain_unavailable"); }
            if (!police) { Print("[HC Events] reward cache refused for site " + mission.SiteId + "; terrain height differs from the reviewed height"); }
            return vector.Zero;
        }
        vector position;
        if (police)
        {
            // Police Source is the station's stock mapgrouppos model origin, which stands
            // above its ground (stock neighbours sit ~5 m lower). Accept ground up to 12 m
            // below it, then take an outdoor walkable navmesh point so the barrel is not
            // inside a wall. Retries report through BindFailed's bounded (mission, reason) set.
            if (height > mission.Source[1] + 3 || height < mission.Source[1] - 12)
            {
                PoliceRefused("police_terrain_height", "; h=" + height.ToString() + "; src=" + mission.Source[1].ToString());
                return vector.Zero;
            }
            position = HCEventPoliceNav.Sample(Vector(anchor[0], height, anchor[2]), 6);
            if (position == vector.Zero) { PoliceRefused("police_navmesh_none"); return vector.Zero; }
        }
        else
        {
            if (Math.AbsFloat(height - mission.Source[1]) > 6)
            {
                Print("[HC Events] reward cache refused for site " + mission.SiteId + "; terrain height differs from the reviewed height");
                return vector.Zero;
            }
            position = Vector(anchor[0], height, anchor[2]);
        }
        if (vector.DistanceSq(position, mission.Source) > mission.Radius * mission.Radius)
        {
            if (police) { PoliceRefused("police_position_outside_radius"); }
            return vector.Zero;
        }
        return position;
    }
    // One shared admission owner for stock and infected bind continuations.
    // Their roster slot is serialized by HCEventModule, so they cannot consume
    // each other's sole starvation grant in the same refresh.
    static bool PoliceWork()
    {
        return HCServer.HCTickWork().HCTakeFor(HCUnitBudget.HC_WORK_POLICE_BIND, 8);
    }

    static HCEventTarget SpawnPoliceSlice(HCEventMission mission)
    {
        PoliceRefused("police_work_budget");
        if (!HCPhysicalEnabled()) { PoliceRefused("police_physical_disabled"); return null; }
        HCW38SituationPolicy policy = HCW38SituationPolicy.HCGet();
        if (!policy) { PoliceRefused("police_policy_invalid"); return null; }
        if (!PoliceWork()) { return null; }
        HCEventPoliceStockLedger ledger = PoliceLedger();
        // A generation or first creation waiting for its durable receipt resumes before any new scan.
        HCPoliceGenJob genJob;
        if (s_GenJobs.Find(mission.SiteId, genJob)) { return PoliceGenerateStep(mission, genJob); }
        if (s_CreatePending.Find(mission.Id) >= 0)
        {
            Barrel_Green pendingCache = CreatePoliceStock(mission);
            if (pendingCache) { return PoliceStockTarget(mission, pendingCache); }
            return null;
        }
        ref HCEventPoliceStockSlice job = s_StockSlices.Get(mission.Id);
        if (!job)
        {
            job = new HCEventPoliceStockSlice;
            job.Nearby = new array<Object>;
            job.NearBarrels = new array<Barrel_Green>;
            array<CargoBase> proxies = new array<CargoBase>;
            int began = TickCount(0);
            GetGame().GetObjectsAtPosition3D(mission.Source, Math.Min(mission.Radius, SCAN_RADIUS_MAX), job.Nearby, proxies);
            HCStockQueryCost(began, true);
            s_StockSlices.Set(mission.Id, job);
            return null;
        }
        if (job.Stage == 0)
        {
            // The receipt directory image loads one file per module tick; the record is read from it.
            if (!ledger.HCLoaded() && !ledger.HCUnavailable()) { return null; }
            job.HasOwnedPosition = ledger.CachePosition(mission.SiteId, job.OwnedPosition);
            if (!job.HasOwnedPosition && ledger.HCPositionTorn(mission.SiteId)) { PoliceLogOnceAs(mission.SiteId, "record_unreadable", "pos_torn_stock_only"); }
            job.Stage = 1;
            return null;
        }
        if (job.Stage == 1)
        {
            array<string> classes = HCW38SituationPolicy.PoliceClasses(mission.Family);
            HCWorkBudget slice = new HCWorkBudget;
            slice.HCReset(32, Math.Min(HCPerfConfig.HCGet().SliceMs, 2));
            while (slice.HCContinue())
            {
                if (job.CargoOwner)
                {
                    ItemBase cargoOwner = job.CargoOwner;
                    // Validate the retained owner before any native inventory access.
                    if (!HCPhysicalGround(cargoOwner) || vector.DistanceSq(cargoOwner.GetPosition(), mission.Source) > mission.Radius * mission.Radius)
                    {
                        job.CargoOwner = null;
                        job.CargoItems = null;
                        continue;
                    }
                    CargoBase cargo;
                    if (cargoOwner.GetInventory()) { cargo = cargoOwner.GetInventory().GetCargo(); }
                    if (!cargo)
                    {
                        job.CargoOwner = null;
                        job.CargoItems = null;
                        continue;
                    }
                    if (!job.CargoItems)
                    {
                        // One grant snapshots at most 64 weak item handles in
                        // native order. No yield can shift indices mid-copy.
                        job.CargoItems = new array<ItemBase>;
                        int cargoCount = Math.Min(cargo.GetItemCount(), policy.PhysicalScanCargo);
                        for (int cargoIndex = 0; cargoIndex < cargoCount; cargoIndex++)
                        {
                            job.CargoItems.Insert(ItemBase.Cast(cargo.GetItem(cargoIndex)));
                        }
                        return null;
                    }
                    if (job.CargoNext >= job.CargoItems.Count())
                    {
                        job.CargoOwner = null;
                        job.CargoItems = null;
                        continue;
                    }
                    ItemBase item = job.CargoItems[job.CargoNext];
                    job.CargoNext++;
                    if (!item || item.IsSetForDeletion() || item.IsRuined() || item.GetHierarchyRootPlayer()) { continue; }
                    if (item.GetHierarchyParent() != cargoOwner || !PoliceItemMatches(item, mission, classes) || PoliceItemUsed(item)) { continue; }
                    if (mission.Family == HCEventFamily.DELIVERY && !PoliceDeliveryValid(mission, job.DeliveryContainer)) { continue; }
                    s_StockSlices.Remove(mission.Id);
                    if (mission.Family == HCEventFamily.DELIVERY) { return RememberPolice(mission, item, job.DeliveryContainer); }
                    return RememberPolice(mission, item, cargoOwner);
                }
                if (job.Next >= job.Nearby.Count() || job.Next >= policy.PhysicalScanObjects)
                {
                    job.Stage = 2;
                    return null;
                }
                ItemBase cache = ItemBase.Cast(job.Nearby[job.Next]);
                job.Next++;
                // Even a ruined ground barrel blocks repair; it may be the old HC cache.
                Barrel_Green nearbyBarrel = Barrel_Green.Cast(cache);
                if (!job.GroundBarrelPresent && nearbyBarrel && !nearbyBarrel.IsSetForDeletion() && !nearbyBarrel.GetHierarchyParent() && !nearbyBarrel.GetHierarchyRootPlayer() && vector.DistanceSq(nearbyBarrel.GetPosition(), mission.Source) <= mission.Radius * mission.Radius)
                {
                    job.GroundBarrelPresent = true;
                    ledger.HCRepairOrphan(mission.SiteId, true);
                }
                // Barrels (even ruined) at the recorded position are candidates for the site container.
                if (nearbyBarrel && job.HasOwnedPosition && !nearbyBarrel.IsSetForDeletion() && !nearbyBarrel.GetHierarchyParent() && vector.DistanceSq(nearbyBarrel.GetPosition(), job.OwnedPosition) <= 4)
                {
                    if (job.NearBarrels.Count() < 4) { job.NearBarrels.Insert(nearbyBarrel); }
                    else { job.NearCapped = true; }
                }
                if (!HCPhysicalGround(cache)) { continue; }
                if (vector.DistanceSq(cache.GetPosition(), mission.Source) > mission.Radius * mission.Radius) { continue; }
                if (!job.GroundItem && PoliceItemMatches(cache, mission, classes) && !PoliceItemUsed(cache)) { job.GroundItem = cache; }
                if (cache.GetType() != mission.ContainerClass || !cache.GetInventory() || !cache.GetInventory().GetCargo()) { continue; }
                if (vector.DistanceSq(cache.GetPosition(), mission.Destination) <= mission.Radius * mission.Radius) { job.DeliveryContainer = cache; }
                job.CargoOwner = cache;
                job.CargoNext = 0;
                job.CargoItems = null;
                // Isolate the bounded snapshot from object inspection work.
                return null;
            }
            return null;
        }
        if (job.Stage == 2)
        {
            // A retained ground item may have been picked up between grants.
            // Refuse that attempt rather than borrowing a different target.
            if (job.GroundItem && (!HCPhysicalGround(job.GroundItem) || PoliceItemUsed(job.GroundItem) || vector.DistanceSq(job.GroundItem.GetPosition(), mission.Source) > mission.Radius * mission.Radius))
            {
                s_StockSlices.Remove(mission.Id);
                PoliceRefused("police_target_changed");
                return null;
            }
            if (job.DeliveryContainer && !PoliceDeliveryValid(mission, job.DeliveryContainer))
            {
                if (mission.Family == HCEventFamily.DELIVERY)
                {
                    s_StockSlices.Remove(mission.Id);
                    PoliceRefused("police_target_changed");
                    return null;
                }
                job.DeliveryContainer = null;
            }
            if (job.GroundItem && (mission.Family != HCEventFamily.DELIVERY || PoliceDeliveryValid(mission, job.DeliveryContainer)))
            {
                s_StockSlices.Remove(mission.Id);
                return RememberPolice(mission, job.GroundItem, job.DeliveryContainer);
            }
            if (job.Nearby.Count() > policy.PhysicalScanObjects)
            {
                s_StockSlices.Remove(mission.Id);
                PoliceRefused("police_scan_limit", "; queried=" + job.Nearby.Count().ToString() + "; scan_cap=" + policy.PhysicalScanObjects.ToString());
                return null;
            }
            if (job.HasOwnedPosition)
            {
                // Recorded site: container lifecycle (refill, replace, recreate) or its stock.
                s_StockSlices.Remove(mission.Id);
                return PoliceContainer(mission, job);
            }
            ledger.HCRepairOrphan(mission.SiteId, job.GroundBarrelPresent);
            // No native creation handle or partially initialized cache crosses a grant.
            s_StockSlices.Remove(mission.Id);
            Barrel_Green created = CreatePoliceStock(mission);
            if (created) { return PoliceStockTarget(mission, created); }
            return null;
        }
        return null;
    }

    // Container lifecycle, owner 2026-11-22. Runs on police bind attempts inside the
    // PoliceWork grant of SpawnPoliceSlice (no separate timer); one create per grant.
    // Every generation (refill, replace, recreate) is gated on RefillCooldownSeconds read
    // from the durable receipt, so a carried-off or looted container cannot be farmed by
    // restarting, and on no player within RefillClearRadius of the recorded position.
    // Only the barrel whose persistent id is in the ok receipt, holding only untouched plan
    // items, is ever drained or deleted; any other barrel at the record is left alone and the
    // site waits (police_container_not_ours). Native: EntityAI.c:3374 GetPersistentID,
    // Inventory.c:205 AttachmentCount, :138 GetCargo; Cargo.c GetItemCount/GetItem.
    // The empty-container pickup (Barrel_ColorBase.c CanPutIntoHands) is not blocked: an HC
    // Barrel_Green subclass needs a config class and CE types entry, unverified here.
    static int PoliceCargoCount(Barrel_Green barrel)
    {
        if (!barrel || !barrel.GetInventory()) { return -1; }
        CargoBase cargo = barrel.GetInventory().GetCargo();
        if (!cargo) { return -1; }
        return cargo.GetItemCount();
    }
    // "" = unknown (zero id or no barrel). The id is recorded in the ok receipt.
    static string PoliceBarrelId(Barrel_Green barrel)
    {
        int b1;
        int b2;
        int b3;
        int b4;
        if (!barrel) { return ""; }
        barrel.GetPersistentID(b1, b2, b3, b4);
        if (b1 == 0 && b2 == 0 && b3 == 0 && b4 == 0) { return ""; }
        return b1.ToString() + " " + b2.ToString() + " " + b3.ToString() + " " + b4.ToString();
    }
    // Bounded observation line for the lead: does GetPersistentID work on a barrel created this
    // session (created=1) and on one first resolved on a later boot (created=0)?
    // created=0 also reports match=current|prev|none: the barrel's id against the receipt's id / prev
    // (an unstable id would read none every boot and duplicate the barrel).
    static void PoliceProbe(string siteId, Barrel_Green barrel, int created, HCPoliceGeneration state = null)
    {
        if (s_PoliceProbeLines >= 24) { return; }
        if (created == 0)
        {
            if (s_PoliceCreatedSites.Find(siteId) >= 0) { return; }
            string probeKey = siteId + ":probe";
            if (s_PoliceLogged.Find(probeKey) >= 0) { return; }
            if (s_PoliceLogged.Count() < 32) { s_PoliceLogged.Insert(probeKey); }
        }
        else if (s_PoliceCreatedSites.Find(siteId) < 0)
        {
            s_PoliceCreatedSites.Insert(siteId);
        }
        s_PoliceProbeLines++;
        int b1;
        int b2;
        int b3;
        int b4;
        string shown = "zero";
        if (barrel)
        {
            barrel.GetPersistentID(b1, b2, b3, b4);
            if (b1 != 0 || b2 != 0 || b3 != 0 || b4 != 0) { shown = b1.ToString() + "-" + b2.ToString() + "-" + b3.ToString() + "-" + b4.ToString(); }
        }
        string matchText = "";
        if (created == 0)
        {
            // Only match=none means "id unstable": unknown = no receipt state, unrecorded = no id
            // recorded to compare against.
            string matchState = "none";
            string probeId = PoliceBarrelId(barrel);
            if (!state)
            {
                matchState = "unknown";
            }
            else if (state.ExpectedId() == "" && state.ExpectedPrev() == "")
            {
                matchState = "unrecorded";
            }
            else if (probeId != "")
            {
                if (probeId == state.ExpectedId()) { matchState = "current"; }
                else if (probeId == state.ExpectedPrev()) { matchState = "prev"; }
            }
            matchText = " match=" + matchState;
        }
        Print("[HC Police] site=" + siteId + " action=id_probe created=" + created.ToString() + " id=" + shown + matchText);
    }
    static void PoliceIdWatchSet(string siteId, Barrel_Green barrel)
    {
        if (!s_PoliceIdWatch) { s_PoliceIdWatch = new map<string, ref HCPoliceIdWatch>; }
        HCPoliceIdWatch watch = new HCPoliceIdWatch;
        watch.Barrel = barrel;
        s_PoliceIdWatch.Set(siteId, watch);
    }
    // A barrel this process created read a zero id: retry on later grants (at most 4) and record
    // the id as soon as it reads. Only the barrel object this process created qualifies, so the
    // learned id is a deletable identity; every other id learned later is adopted (refill only).
    static void PoliceIdWatchStep(HCEventPoliceStockLedger ledger, HCPoliceGeneration state, string siteId, Barrel_Green barrel, int now)
    {
        if (!s_PoliceIdWatch) { return; }
        HCPoliceIdWatch watch;
        if (!s_PoliceIdWatch.Find(siteId, watch)) { return; }
        if (!barrel || watch.Barrel != barrel) { s_PoliceIdWatch.Remove(siteId); return; }
        string learned = PoliceBarrelId(barrel);
        if (learned == "")
        {
            watch.Tries++;
            if (watch.Tries >= 4)
            {
                s_PoliceIdWatch.Remove(siteId);
                PoliceLogOnceAs(siteId, "id_probe", "id_unknown_after_retries");
            }
            return;
        }
        s_PoliceIdWatch.Remove(siteId);
        if (state.Open())
        {
            if (state.GenKind != "refill" && state.GenId == "") { ledger.HCEpochBarrel(siteId, state, now, learned); }
        }
        else if (state.Id == "")
        {
            int anchorUtc = state.OkUtc;
            if (anchorUtc < 1) { anchorUtc = now; }
            ledger.HCEpochMark(siteId, state, anchorUtc, "idfix", learned, state.Prev, false);
        }
        PoliceProbe(siteId, barrel, 1);
    }
    // The barrel's standing against the receipt (POLICE_OWN_*). FOREIGN: a different barrel;
    // NONE: no id recorded (nothing proves it ours); UNREADABLE: an id is recorded but this
    // barrel's reads zero; ROLLBACK: the previous barrel came back (re-armed by the caller);
    // ADOPTED: recorded id taken from a barrel HC did not create (refill only).
    static int PoliceOwnership(Barrel_Green barrel, HCPoliceGeneration state)
    {
        string expected = state.ExpectedId();
        string prev = state.ExpectedPrev();
        if (expected == "" && prev == "") { return POLICE_OWN_NONE; }
        string id = PoliceBarrelId(barrel);
        if (id == "")
        {
            // Only a recorded current id makes a zero read suspicious; with just prev set the
            // barrel degrades to refill-only.
            if (expected != "") { return POLICE_OWN_UNREADABLE; }
            return POLICE_OWN_NONE;
        }
        if (id == expected)
        {
            if (state.ExpectedAdopt()) { return POLICE_OWN_ADOPTED; }
            return POLICE_OWN_OURS;
        }
        if (prev != "" && id == prev) { return POLICE_OWN_ROLLBACK; }
        if (expected == "") { return POLICE_OWN_NONE; }
        return POLICE_OWN_FOREIGN;
    }
    // Log reason for a barrel that may not be replaced.
    static string PoliceOwnershipReason(int ownership)
    {
        if (ownership == POLICE_OWN_NONE) { return "id_unknown"; }
        if (ownership == POLICE_OWN_ADOPTED) { return "adopted_refill_only"; }
        if (ownership == POLICE_OWN_UNREADABLE) { return "id_unreadable"; }
        return "not_ours";
    }
    // Which barrel within 2 m of the record is the site container. Identity first (current id,
    // then the previous id); with no identity recorded an intact barrel is preferred. When an id
    // is recorded and none matches, the barrels standing there are foreign: they are neither
    // "present" nor touched (logged once) and the recreate path stays reachable. A barrel whose
    // id reads zero while an id is recorded is kept as the container (UNREADABLE: refuse, never
    // recreate beside what may be our own).
    // With an id recorded and no candidate matching, a candidate holding 1..plan-size untouched plan
    // items is kept as the (foreign_plan_like) container, never recreated beside: an unstable
    // persistent id would otherwise duplicate the barrel every restart. The caller serves its stock only.
    static Barrel_Green PolicePickBarrel(string siteId, HCEventPoliceStockSlice job, HCPoliceGeneration state, HCEventRewardPlan plan = null)
    {
        if (!job.NearBarrels) { return null; }
        if (job.NearCapped) { PoliceLogOnceAs(siteId, "scan_note", "candidates_capped_at_4"); }
        string expected = "";
        string prev = "";
        if (state)
        {
            expected = state.ExpectedId();
            prev = state.ExpectedPrev();
        }
        Barrel_Green best = null;
        Barrel_Green prevMatch = null;
        Barrel_Green unreadable = null;
        int total = job.NearBarrels.Count();
        for (int index = 0; index < total; index++)
        {
            Barrel_Green candidate = job.NearBarrels[index];
            if (!candidate || candidate.IsSetForDeletion() || candidate.GetHierarchyParent()) { continue; }
            string id = PoliceBarrelId(candidate);
            if (id != "" && id == expected) { return candidate; }
            if (id != "" && id == prev) { prevMatch = candidate; }
            if (id == "" && !unreadable) { unreadable = candidate; }
            if (!best || (!HCPhysicalGround(best) && HCPhysicalGround(candidate))) { best = candidate; }
        }
        if (prevMatch) { return prevMatch; }
        if (expected == "") { return best; }
        if (unreadable) { return unreadable; }
        if (plan)
        {
            for (int likeIndex = 0; likeIndex < total; likeIndex++)
            {
                Barrel_Green like = job.NearBarrels[likeIndex];
                if (!like || like.IsSetForDeletion() || like.GetHierarchyParent()) { continue; }
                if (PoliceCargoCount(like) <= 0) { continue; }
                // item_reserved: a stage-1 cargo scan reserved this HC barrel's plan item through
                // RememberPolice; the barrel is never changed on this path, so it is still plan-like.
                string likeRefusal = PoliceCargoRefusal(like, plan);
                if (likeRefusal == "" || likeRefusal == "item_reserved")
                {
                    PoliceLogOnce(siteId, "foreign_plan_like");
                    return like;
                }
            }
        }
        if (best) { PoliceLogOnceAs(siteId, "replace_refused", "foreign_barrel_ignored"); }
        return null;
    }
    static void PoliceLogOnceAs(string siteId, string action, string reason)
    {
        string key = siteId + ":" + action + ":" + reason;
        if (s_PoliceLogged.Count() >= 32 || s_PoliceLogged.Find(key) >= 0) { return; }
        s_PoliceLogged.Insert(key);
        Print("[HC Police] site=" + siteId + " action=" + action + " reason=" + reason);
    }
    static void PoliceLogOnce(string siteId, string reason)
    {
        PoliceLogOnceAs(siteId, "replace_refused", reason);
    }
    // A live police delivery event holds this barrel as its container: never delete it.
    // s_PoliceTargets is per process and never pruned, so this guards the current process only;
    // only DELIVERY-family targets count (a stock target also records its barrel, which is no hold).
    static bool PoliceContainerBound(Barrel_Green barrel)
    {
        if (!barrel) { return false; }
        // Sticky overflow: a hold that could not be recorded fails closed (refuse replaces).
        if (s_PoliceHoldOverflow) { return true; }
        return s_PoliceDeliveryHolds.Find(barrel) >= 0;
    }
    static bool PoliceInPlan(HCEventRewardPlan plan, string className)
    {
        return plan.Items.Find(className) >= 0;
    }
    // "" = every cargo item is an untouched plan item of this barrel (no cargo or attachments of
    // its own, count within the plan size, none reserved by a police event); otherwise the reason.
    static string PoliceCargoRefusal(Barrel_Green barrel, HCEventRewardPlan plan)
    {
        if (!barrel || !barrel.GetInventory()) { return "player_items"; }
        CargoBase cargo = barrel.GetInventory().GetCargo();
        if (!cargo) { return "player_items"; }
        int count = cargo.GetItemCount();
        if (count > plan.Items.Count()) { return "player_items"; }
        for (int index = 0; index < count; index++)
        {
            ItemBase item = ItemBase.Cast(cargo.GetItem(index));
            if (!item || item.GetHierarchyParent() != barrel || !PoliceInPlan(plan, item.GetType())) { return "player_items"; }
            GameInventory inner = item.GetInventory();
            if (inner && inner.AttachmentCount() > 0) { return "player_items"; }
            CargoBase innerCargo = null;
            if (inner) { innerCargo = inner.GetCargo(); }
            if (innerCargo && innerCargo.GetItemCount() > 0) { return "player_items"; }
            if (PoliceItemUsed(item)) { return "item_reserved"; }
        }
        return "";
    }
    static bool PolicePlayersWithin(vector position, float radius)
    {
        array<Man> players = HCPerfPlayers.HCGet();
        int count = players.Count();
        // More than the scan cap: cannot prove the area clear, so treat players as near.
        if (count > 64) { return true; }
        for (int index = 0; index < count; index++)
        {
            Man player = players[index];
            if (!player || !player.IsAlive()) { continue; }
            if (vector.DistanceSq(player.GetPosition(), position) <= radius * radius) { return true; }
        }
        return false;
    }
    // Deletes the cargo of a barrel PoliceCargoRefusal already verified (at most the plan size).
    static void PoliceDrain(Barrel_Green barrel)
    {
        if (!barrel || !barrel.GetInventory()) { return; }
        CargoBase cargo = barrel.GetInventory().GetCargo();
        if (!cargo) { return; }
        int count = cargo.GetItemCount();
        for (int index = count - 1; index >= 0; index--)
        {
            ItemBase item = ItemBase.Cast(cargo.GetItem(index));
            if (!item || item.IsSetForDeletion() || item.GetHierarchyParent() != barrel) { continue; }
            GetGame().ObjectDelete(item);
        }
    }
    static bool PoliceFillCargo(Barrel_Green cache, HCEventRewardPlan plan)
    {
        // Native: ItemBase/Barrel_ColorBase.c:87 Open, :512 cargo requires IsOpen.
        cache.Open();
        foreach (string itemClass : plan.Items)
        {
            // Preserve 60a261e3: never delete the cache or its cargo on failure here;
            // the open receipt makes the next generation discard a partial one.
            if (!HCPhysicalGround(cache) || !cache.IsOpen() || !cache.GetInventory() || !cache.GetInventory().CreateInInventory(itemClass)) { return false; }
        }
        return true;
    }
    // Lifecycle unavailable: serve the stock of the container that is there, never mutate it.
    static HCEventTarget PoliceStockOnly(HCEventMission mission, Barrel_Green cache)
    {
        if (cache) { return PoliceStockTarget(mission, cache); }
        PoliceRefused("police_cache_position_recorded");
        return null;
    }
    static HCEventTarget PoliceContainer(HCEventMission mission, HCEventPoliceStockSlice job)
    {
        HCEventPoliceStockLedger ledger = PoliceLedger();
        HCW38SituationPolicy policy = HCW38SituationPolicy.HCGet();
        vector recorded;
        HCPoliceGeneration state;
        HCEventRewardPlan plan;
        int now = HCInfectedClock.UtcSeconds();
        bool ready = policy && now > 0 && GetGame() && GetGame().IsServer();
        if (ready) { ready = ledger.HCBarrelRecordPosition(mission.SiteId, recorded); }
        if (ready)
        {
            state = ledger.HCGeneration(mission.SiteId);
            ready = state != null;
        }
        if (ready) { plan = ledger.HCFreshPlan(mission.SiteId); }
        // The container among the barrels at the record, chosen by persistent id.
        Barrel_Green barrel = PolicePickBarrel(mission.SiteId, job, state, plan);
        Barrel_Green cache = null;
        if (barrel && HCPhysicalGround(barrel)) { cache = barrel; }
        if (barrel) { PoliceProbe(mission.SiteId, barrel, 0, state); }
        if (ready && state.Num < 1)
        {
            // Old record without receipts: migrate in place; the cooldown starts now. The identity
            // of the barrel found is recorded only when it holds nothing but untouched plan items
            // (the legacy migration is the one place a found barrel becomes deletable).
            string legacyId = "";
            if (barrel && PoliceCargoRefusal(barrel, plan) == "") { legacyId = PoliceBarrelId(barrel); }
            if (ledger.HCEpochMark(mission.SiteId, state, now, "migrate", legacyId, "", false)) { Print("[HC Police] site=" + mission.SiteId + " action=ledger_migrated reason=legacy_record"); }
            ready = state.Ok > 0;
        }
        if (ready) { PoliceIdWatchStep(ledger, state, mission.SiteId, barrel, now); }
        int anchor = 0;
        if (ready) { anchor = ledger.HCEpochAnchor(state); }
        if (ready && (anchor < 1 || anchor > now + 86400))
        {
            // No readable or a future-dated anchor: re-arm durably (ok-(max+1), utc now) so recovery
            // takes exactly one cooldown across restarts. The identity in force (the open generation's
            // when one is open) is carried over; a barrel present with no recorded id is adopted
            // (refill only) unless it is the recorded previous barrel.
            string rearmId = state.ExpectedId();
            string rearmPrev = state.ExpectedPrev();
            bool rearmAdopt = state.ExpectedAdopt();
            if (rearmId == "" && barrel)
            {
                string presentId = PoliceBarrelId(barrel);
                if (presentId != "" && presentId != rearmPrev)
                {
                    rearmId = presentId;
                    rearmAdopt = true;
                }
            }
            Print("[HC Police] site=" + mission.SiteId + " action=receipt_rearmed reason=anchor_unusable");
            ready = ledger.HCEpochMark(mission.SiteId, state, now, "rearm", rearmId, rearmPrev, rearmAdopt);
            anchor = now;
        }
        if (!ready) { return PoliceStockOnly(mission, cache); }
        int ownership = POLICE_OWN_NONE;
        if (barrel) { ownership = PoliceOwnership(barrel, state); }
        if (ownership == POLICE_OWN_ROLLBACK)
        {
            // The previous barrel came back (the replace finished but the native save did not): it is
            // ours. Re-arm durably with its id; this closes the rolled-back generation. One cooldown.
            Print("[HC Police] site=" + mission.SiteId + " action=receipt_rearmed reason=previous_barrel_restored");
            if (!ledger.HCEpochMark(mission.SiteId, state, now, "rearm", PoliceBarrelId(barrel), "", false)) { return PoliceStockOnly(mission, cache); }
            anchor = now;
            ownership = PoliceOwnership(barrel, state);
        }
        int remaining = policy.RefillCooldownSeconds - (now - anchor);
        bool cooled = remaining <= 0;
        if (!barrel && job.NearCapped && job.NearBarrels && job.NearBarrels.Count() > 0)
        {
            // More barrels than the candidate list holds and none matched: the container may be one
            // that was not listed, so never recreate beside it.
            PoliceLogOnce(mission.SiteId, "candidates_capped_refused");
            PoliceRefused("police_container_not_ours");
            return null;
        }
        if (!barrel)
        {
            if (!cooled) { PoliceRefused("police_container_cooldown", "; wait_s=" + remaining.ToString()); return null; }
            if (PolicePlayersWithin(recorded, policy.RefillClearRadius)) { PoliceRefused("police_container_players_near"); return null; }
            return PoliceGenerate(mission, state, recorded, null, "recreate", "missing_entity", now);
        }
        if (ownership == POLICE_OWN_UNREADABLE)
        {
            // An id is recorded but this barrel reports none: cannot prove it is not ours, so neither
            // replace nor recreate beside it; its stock is served, nothing is mutated. The id_probe
            // line shows whether this can occur.
            PoliceLogOnce(mission.SiteId, "id_unreadable");
            return PoliceStockOnly(mission, cache);
        }
        if (ownership == POLICE_OWN_FOREIGN)
        {
            // Only reachable through PolicePickBarrel's plan-like fallback (foreign_plan_like): serve
            // its stock, never mutate it and never recreate beside it.
            return PoliceStockOnly(mission, cache);
        }
        string cargoRefusal = PoliceCargoRefusal(barrel, plan);
        int count = PoliceCargoCount(barrel);
        string keepId = state.ExpectedId();
        bool keepAdopt = state.ExpectedAdopt();
        if (keepId == "")
        {
            // No identity recorded: a barrel taken up now is adopted, never deletable.
            keepId = PoliceBarrelId(barrel);
            keepAdopt = keepId != "";
        }
        bool incomplete = state.Open();
        if (cache && incomplete && count >= 0 && cargoRefusal == "")
        {
            // A generation that crashed after its items but before its marker is completed,
            // never regenerated: its items are present.
            int planned = state.GenItems;
            if (planned < 1) { planned = plan.Items.Count(); }
            if (count >= planned && ledger.HCEpochComplete(mission.SiteId, state, "resume", now, keepId, keepAdopt))
            {
                Print("[HC Police] site=" + mission.SiteId + " action=generation_completed reason=items_present");
                incomplete = false;
            }
        }
        if (!cache)
        {
            // Ruined barrel at the record: replace only our own, untouched one.
            if (!cooled) { PoliceRefused("police_container_cooldown", "; wait_s=" + remaining.ToString()); return null; }
            if (PolicePlayersWithin(recorded, policy.RefillClearRadius)) { PoliceRefused("police_container_players_near"); return null; }
            if (ownership != POLICE_OWN_OURS) { PoliceLogOnce(mission.SiteId, PoliceOwnershipReason(ownership)); PoliceRefused("police_container_not_ours"); return null; }
            if (cargoRefusal != "") { PoliceLogOnce(mission.SiteId, cargoRefusal); PoliceRefused("police_container_not_ours"); return null; }
            if (PoliceContainerBound(barrel)) { PoliceLogOnce(mission.SiteId, "container_bound"); PoliceRefused("police_container_bound"); return null; }
            return PoliceGenerate(mission, state, recorded, barrel, "replace", "ruined", now);
        }
        bool expired = !incomplete && (now - anchor) >= policy.ContainerLifetimeSeconds;
        bool empty = count == 0;
        if ((empty || incomplete || expired) && cooled && !PolicePlayersWithin(recorded, policy.RefillClearRadius))
        {
            // Never add to a container that still holds items: only an empty one refills in place.
            if (empty) { return PoliceGenerate(mission, state, recorded, barrel, "refill", "depleted", now); }
            string why = "lifetime";
            if (incomplete) { why = "incomplete_generation"; }
            if (ownership != POLICE_OWN_OURS) { PoliceLogOnce(mission.SiteId, PoliceOwnershipReason(ownership)); }
            else if (cargoRefusal != "") { PoliceLogOnce(mission.SiteId, cargoRefusal); }
            else if (PoliceContainerBound(barrel)) { PoliceLogOnce(mission.SiteId, "container_bound"); }
            else { return PoliceGenerate(mission, state, recorded, barrel, "replace", why, now); }
        }
        return PoliceStockTarget(mission, cache);
    }
    // kind: refill (in place), replace (drain + delete + create), recreate (missing: create).
    // Callers verified identity and cargo before any replace; the checks that can change between
    // grants (hierarchy, distance, a bound delivery container) are repeated here, before any write
    // and again once gen-N is durable (PoliceGenerateStep).
    // gen-N is queued here and nothing native happens until it is verified on disk (the roster retries
    // every tick while the receipt is written, one file call per module tick); a new barrel waits the
    // same way for bar-N before its items are created. Crash points: see docs/MODULE_STATUS.md
    // (Police stock container lifecycle).
    static HCEventTarget PoliceGenerate(HCEventMission mission, HCPoliceGeneration state, vector position, Barrel_Green old, string kind, string reason, int now)
    {
        if (vector.DistanceSq(position, mission.Source) > mission.Radius * mission.Radius) { PoliceRefused("police_position_outside_radius"); return null; }
        if (kind == "replace")
        {
            if (!old) { PoliceRefused("police_container_changed"); return null; }
            if (PoliceContainerBound(old)) { PoliceLogOnce(mission.SiteId, "container_bound"); PoliceRefused("police_container_bound"); return null; }
            if (old.IsSetForDeletion() || old.GetHierarchyParent() || old.GetHierarchyRootPlayer() || vector.DistanceSq(old.GetPosition(), position) > 4) { PoliceRefused("police_container_changed"); return null; }
        }
        HCEventPoliceStockLedger ledger = PoliceLedger();
        HCEventRewardPlan plan = ledger.HCFreshPlan(mission.SiteId);
        // Durable receipt first: a crash after it loses one generation, never doubles one. The
        // identity of the barrel being replaced is carried as prev (see the receipt format).
        string barrelId = state.ExpectedId();
        bool adopt = state.ExpectedAdopt();
        if (kind == "refill" && barrelId == "")
        {
            // No identity recorded for this barrel: adopted (refill only). The id goes into gen-N
            // itself, so a crash before ok-N never lets a reload fall back to an older generation's id.
            barrelId = PoliceBarrelId(old);
            adopt = barrelId != "";
        }
        if (!ledger.HCEpochBegin(mission.SiteId, state, now, kind, plan.Items.Count(), barrelId, state.ExpectedPrev(), adopt)) { PoliceRefused("police_receipt_write_failed"); return null; }
        HCPoliceGenJob job = new HCPoliceGenJob;
        job.SiteId = mission.SiteId;
        job.Kind = kind;
        job.Reason = reason;
        job.GenName = mission.SiteId + ".gen-" + state.Gen.ToString();
        job.Stage = GEN_WAIT_GEN;
        job.Now = now;
        job.Position = position;
        job.Old = old;
        job.BarrelId = barrelId;
        job.Adopt = adopt;
        s_GenJobs.Set(mission.SiteId, job);
        PoliceRefused("police_work_budget");
        return null;
    }
    static void PoliceGenerateDrop(HCPoliceGenJob job, string reason)
    {
        s_GenJobs.Remove(job.SiteId);
        PoliceRefused(reason);
    }
    // Runs on the grants after PoliceGenerate: waits (police_work_budget) while the receipt of the
    // current stage is being written, then performs the native work of that stage.
    static HCEventTarget PoliceGenerateStep(HCEventMission mission, HCPoliceGenJob job)
    {
        HCEventPoliceStockLedger ledger = PoliceLedger();
        HCPoliceGeneration state = ledger.HCGeneration(job.SiteId);
        if (!state || !state.Open())
        {
            PoliceGenerateDrop(job, "police_receipt_write_failed");
            return null;
        }
        HCEventRewardPlan plan = ledger.HCFreshPlan(job.SiteId);
        Barrel_Green barrel = job.Barrel;
        if (job.Stage == GEN_WAIT_GEN)
        {
            int genState = ledger.HCWriteState(job.GenName);
            if (genState == HCEventReceiptOp.RESULT_PENDING)
            {
                PoliceRefused("police_work_budget");
                return null;
            }
            if (genState != HCEventReceiptOp.RESULT_DONE)
            {
                PoliceGenerateDrop(job, "police_receipt_write_failed");
                return null;
            }
            // The receipt is durable; what may have changed while it was written is re-checked before
            // anything native. A refusal leaves an open generation: the next attempt resumes or redoes it.
            if (PolicePlayersWithin(job.Position, HCW38SituationPolicy.HCGet().RefillClearRadius))
            {
                PoliceGenerateDrop(job, "police_container_players_near");
                return null;
            }
            if (job.Kind != "recreate")
            {
                Barrel_Green old = job.Old;
                if (!old || old.IsSetForDeletion() || old.GetHierarchyParent() || old.GetHierarchyRootPlayer() || vector.DistanceSq(old.GetPosition(), job.Position) > 4)
                {
                    PoliceGenerateDrop(job, "police_container_changed");
                    return null;
                }
                if (job.Kind == "replace" && PoliceContainerBound(old))
                {
                    PoliceGenerateDrop(job, "police_container_bound");
                    return null;
                }
            }
            barrel = job.Old;
            if (job.Kind != "refill")
            {
                if (job.Old)
                {
                    PoliceDrain(job.Old);
                    GetGame().ObjectDelete(job.Old);
                }
                barrel = Barrel_Green.Cast(GetGame().CreateObjectEx("Barrel_Green", job.Position, ECE_SETUP | ECE_KEEPHEIGHT | ECE_CREATEPHYSICS));
                if (!barrel)
                {
                    PoliceGenerateDrop(job, "police_cache_create_failed");
                    return null;
                }
                HCGroundSnap.Snap(barrel);
                PoliceProbe(job.SiteId, barrel, 1);
                if (vector.DistanceSq(barrel.GetPosition(), job.Position) > 4)
                {
                    // The new barrel is still empty: delete it; the open receipt retries after a cooldown.
                    GetGame().ObjectDelete(barrel);
                    PoliceGenerateDrop(job, "police_cache_position_drift");
                    return null;
                }
                // HC created this barrel: its id is a deletable identity.
                job.BarrelId = PoliceBarrelId(barrel);
                job.Adopt = false;
                if (job.BarrelId == "")
                {
                    PoliceIdWatchSet(job.SiteId, barrel);
                }
                else
                {
                    if (!ledger.HCEpochBarrel(job.SiteId, state, job.Now, job.BarrelId))
                    {
                        GetGame().ObjectDelete(barrel);
                        PoliceGenerateDrop(job, "police_receipt_write_failed");
                        return null;
                    }
                    // bar-N must be durable before the items exist.
                    job.Barrel = barrel;
                    job.BarName = job.SiteId + ".bar-" + state.Gen.ToString();
                    job.Stage = GEN_WAIT_BAR;
                    PoliceRefused("police_work_budget");
                    return null;
                }
            }
        }
        else
        {
            if (!barrel || !HCPhysicalGround(barrel))
            {
                PoliceGenerateDrop(job, "police_cache_create_failed");
                return null;
            }
            int barState = ledger.HCWriteState(job.BarName);
            if (barState == HCEventReceiptOp.RESULT_PENDING)
            {
                PoliceRefused("police_work_budget");
                return null;
            }
            if (barState != HCEventReceiptOp.RESULT_DONE)
            {
                GetGame().ObjectDelete(barrel);
                PoliceGenerateDrop(job, "police_receipt_write_failed");
                return null;
            }
        }
        s_GenJobs.Remove(job.SiteId);
        if (!PoliceFillCargo(barrel, plan)) { PoliceRefused("police_cache_cargo_failed"); return null; }
        ledger.HCEpochComplete(job.SiteId, state, job.Kind, job.Now, job.BarrelId, job.Adopt);
        if (job.Kind == "refill")
        {
            Print("[HC Police] site=" + job.SiteId + " action=refilled reason=" + job.Reason);
            HCModuleReadiness.HCUse("Events", "container_refilled");
        }
        else if (job.Kind == "recreate")
        {
            Print("[HC Police] site=" + job.SiteId + " action=barrel_recreated reason=" + job.Reason);
            HCModuleReadiness.HCUse("Events", "police_barrel_recreated");
        }
        else
        {
            Print("[HC Police] site=" + job.SiteId + " action=replaced reason=" + job.Reason);
            HCModuleReadiness.HCUse("Events", "container_replaced");
        }
        return PoliceStockTarget(mission, barrel);
    }

    // Restore the pre-slicing creation order (4b12d4f0) within one PoliceWork grant, except that the
    // site's spent marker is written first over the module ticks that follow (HCCommitStep: RESULT_PENDING
    // yields with police_work_budget and the grant resumes here, never through a new scan). The plan is
    // fixed at three items; only the capped world/cargo scan yields.
    static Barrel_Green CreatePoliceStock(HCEventMission mission)
    {
        vector position = SpawnPosition(mission, mission.Source, true);
        if (position == vector.Zero) { return null; }
        HCEventPoliceStockLedger owner = PoliceLedger();
        HCEventRewardPlan plan;
        int commit = owner.HCCommitStep(mission.SiteId, plan);
        int pendingAt = s_CreatePending.Find(mission.Id);
        if (commit == HCEventReceiptOp.RESULT_PENDING)
        {
            if (pendingAt < 0)
            {
                if (s_CreatePending.Count() >= PENDING_KEEP) { s_CreatePending.RemoveOrdered(0); }
                s_CreatePending.Insert(mission.Id);
            }
            PoliceRefused("police_work_budget");
            return null;
        }
        if (pendingAt >= 0) { s_CreatePending.RemoveOrdered(pendingAt); }
        if (commit != HCEventReceiptOp.RESULT_DONE || !plan) { PoliceRefused(owner.Refusal()); return null; }
        Barrel_Green cache = Barrel_Green.Cast(GetGame().CreateObjectEx("Barrel_Green", position, ECE_SETUP | ECE_KEEPHEIGHT | ECE_CREATEPHYSICS));
        if (!cache) { PoliceRefused("police_cache_create_failed"); return null; }
        HCGroundSnap.Snap(cache);
        PoliceProbe(mission.SiteId, cache, 1);
        if (PoliceBarrelId(cache) == "") { PoliceIdWatchSet(mission.SiteId, cache); }
        if (!owner.RecordCache(mission.SiteId, cache.GetPosition()))
        {
            // Reservation already spent; an unrecorded cache is still finite native loot.
            Print("[HC Events] police cache position not recorded; " + mission.SiteId + " runtime=PENDING");
        }
        if (!PoliceFillCargo(cache, plan))
        {
            PoliceRefused("police_cache_cargo_failed");
            return null;
        }
        // Start the lifecycle clock; a crash before this write migrates at the next boot.
        int createdUtc = HCInfectedClock.UtcSeconds();
        HCPoliceGeneration createdState = owner.HCGeneration(mission.SiteId);
        if (createdState && createdState.Num < 1 && createdUtc > 0) { owner.HCEpochMark(mission.SiteId, createdState, createdUtc, "initial", PoliceBarrelId(cache), "", false); }
        Print("[HC Events] police cache created; " + mission.SiteId + "; stock=finite_until_depleted; refill=after_cooldown runtime=PENDING");
        return cache;
    }
    // One staged step per module tick (HCEventModule): the police ledger's directory load and queued
    // receipt writes first, then the scene cache fill jobs. At most one native file call per call.
    static bool HCStepReceipts()
    {
        s_ReceiptSteps++;
        if (s_PoliceLedger && s_PoliceLedger.HCWantsStep()) { return s_PoliceLedger.HCStepLedger(); }
        return HCEventCacheFill.HCStepFill();
    }

    static bool PoliceDeliveryValid(HCEventMission mission, ItemBase container)
    {
        if (!HCPhysicalGround(container) || container.GetType() != mission.ContainerClass || !container.GetInventory() || !container.GetInventory().GetCargo()) { return false; }
        return vector.DistanceSq(container.GetPosition(), mission.Source) <= mission.Radius * mission.Radius && vector.DistanceSq(container.GetPosition(), mission.Destination) <= mission.Radius * mission.Radius;
    }

    static HCEventTarget Spawn(HCEventMission mission, vector anchor, string containerClass, bool police)
    {
        // Police owns a retained job; ordinary recovery keeps its bounded lookup.
        if (police) { return SpawnPoliceSlice(mission); }
        if (!mission || !GetGame() || !GetGame().IsServer() || !HCEventSitesGate.Admitted() || !HCPhysicalEnabled()) { return null; }
        HCW38SituationPolicy policy = HCW38SituationPolicy.HCGet();
        int consumer = HCUnitBudget.HC_WORK_SITUATIONS;
        if (!policy || !HCServer.HCTickWork().HCTakeFor(consumer, 8)) { return null; }
        array<Object> nearby = new array<Object>;
        array<CargoBase> proxies = new array<CargoBase>;
        int began = TickCount(0);
        GetGame().GetObjectsAtPosition3D(anchor, Math.Min(mission.Radius, SCAN_RADIUS_MAX), nearby, proxies);
        HCStockQueryCost(began, false);
        int remaining = policy.PhysicalScanObjects;
        foreach (Object candidate : nearby)
        {
            if (remaining <= 0) { break; }
            remaining--;
            ItemBase cache = ItemBase.Cast(candidate);
            if (!HCPhysicalGround(cache) || vector.DistanceSq(cache.GetPosition(), mission.Source) > mission.Radius * mission.Radius) { continue; }
            if (!HCPhysicalStock(cache) || cache.GetType() != containerClass) { continue; }
            HCEventTarget result = new HCEventTarget;
            result.MissionId = mission.Id;
            result.Item = cache;
            result.Presence = cache;
            return result;
        }
        HCPhysicalPending();
        return null;
    }

    static HCEventTarget PoliceStockTarget(HCEventMission mission, Barrel_Green cache)
    {
        // The cache can come from an earlier scan grant: validate before dereference.
        if (!HCPhysicalGround(cache) || !cache.GetInventory() || vector.DistanceSq(cache.GetPosition(), mission.Source) > mission.Radius * mission.Radius)
        {
            PoliceRefused("police_target_changed");
            return null;
        }
        CargoBase cargo = cache.GetInventory().GetCargo();
        if (!cargo) { PoliceRefused("police_cache_depleted"); return null; }
        int count = cargo.GetItemCount();
        if (count > 16) { count = 16; }
        for (int index = 0; index < count; index++)
        {
            ItemBase item = ItemBase.Cast(cargo.GetItem(index));
            if (!item || item.IsSetForDeletion() || item.IsRuined() || item.GetHierarchyRootPlayer()) { continue; }
            if (item.GetHierarchyParent() != cache || item.GetType() != mission.ItemClass || PoliceItemUsed(item)) { continue; }
            return RememberPolice(mission, item, cache);
        }
        PoliceRefused("police_cache_depleted");
        return null;
    }

    // Exact configured classes only; retain the original wanted barrel item.
    static bool PoliceItemMatches(ItemBase item, HCEventMission mission, array<string> classes)
    {
        if (item.GetType() == mission.ItemClass) { return true; }
        return classes && classes.Find(item.GetType()) >= 0;
    }
    static bool PoliceItemUsed(ItemBase item)
    {
        if (!s_PoliceTargets) { return false; }
        foreach (HCEventTarget target : s_PoliceTargets)
        {
            if (target.Item == item) { return true; }
        }
        return false;
    }
    static void PrunePoliceHolds()
    {
        for (int hold = s_PoliceDeliveryHolds.Count() - 1; hold >= 0; hold--)
        {
            if (!s_PoliceDeliveryHolds[hold] || s_PoliceDeliveryHolds[hold].IsSetForDeletion()) { s_PoliceDeliveryHolds.Remove(hold); }
        }
    }
    static HCEventTarget RememberPolice(HCEventMission mission, ItemBase item, ItemBase container)
    {
        HCEventTarget supply = new HCEventTarget;
        supply.MissionId = mission.Id;
        supply.Item = item;
        supply.DeliveryContainer = container;
        if (mission.Family == HCEventFamily.DELIVERY && container)
        {
            // Bounded: drop deleted handles before the list can grow past 64.
            if (s_PoliceDeliveryHolds.Count() >= 64) { PrunePoliceHolds(); }
            if (s_PoliceDeliveryHolds.Count() < 64)
            {
                if (s_PoliceDeliveryHolds.Find(container) < 0) { s_PoliceDeliveryHolds.Insert(container); }
            }
            else if (!s_PoliceHoldOverflow)
            {
                s_PoliceHoldOverflow = true;
                Print("[HC Police] site=" + mission.SiteId + " action=hold_overflow reason=delivery_holds_full_replaces_refused");
            }
        }
        if (!s_PoliceTargets) { s_PoliceTargets = new array<ref HCEventTarget>; }
        s_PoliceTargets.Insert(supply);
        return supply;
    }
    // Rosters are rebuilt on retry. Pin the objective to the actual native class
    // before Announce so Ready and later inventory evidence retain exact matching.
    static void PoliceObjectiveClass(HCEventMission mission)
    {
        if (!HCEventSites.PoliceSupplies(mission)) { return; }
        HCEventTarget supply = PoliceTarget(mission.Id);
        if (supply && supply.Item && !supply.Item.IsSetForDeletion()) { mission.ItemClass = supply.Item.GetType(); }
    }
    static bool HCPhysicalGround(ItemBase item)
    {
        return item && !item.IsSetForDeletion() && !item.IsRuined() && !item.GetHierarchyRootPlayer() && !item.GetHierarchyParent();
    }

    protected static bool s_PhysicalPendingPrinted;
    protected static bool s_PhysicalAdmissionPrinted;
    protected static bool s_PhysicalEnabled;
    static bool HCPhysicalEnabled()
    {
        // Operator marker is probed once per process, like the other acceptance markers.
        if (s_PhysicalAdmissionPrinted) { return s_PhysicalEnabled; }
        s_PhysicalAdmissionPrinted = true;
        s_PhysicalEnabled = !FileExist("$profile:HollowCountry/acceptance/w38_rewards.disable");
        Print(HCV2Admission.Line("PhysicalSpoils", s_PhysicalEnabled, "w38_rewards", false) + " runtime=PENDING");
        return s_PhysicalEnabled;
    }

    static void HCPhysicalPending()
    {
        if (s_PhysicalPendingPrinted) { return; }
        s_PhysicalPendingPrinted = true;
        Print("[HC Events] physical_stock=waiting EXISTING_CE_CAMP_STOCK_PENDING runtime=PENDING");
    }

    static bool HCPhysicalStock(ItemBase cache)
    {
        if (!cache || cache.IsSetForDeletion() || cache.IsRuined()) { return false; }
        if (cache.GetHierarchyRootPlayer() || cache.GetHierarchyParent() || !cache.GetInventory()) { return false; }
        CargoBase cargo = cache.GetInventory().GetCargo();
        return cargo && cargo.GetItemCount() > 0;
    }
    // Borrowed physical stock always stays with its native owner.
    static void Discard(ItemBase cache) {}
}
