// W4-08: boot-time, versioned, idempotent, self-repairing migrations for persisted
// HC profile files. Native scripts-1.30.164289: 1_Core/proto/EnSystem.c:397 FileExist,
// :528 DeleteFile, :531 CopyFile (no rename API; replacement is delete then copy and is
// NOT atomic), :106 TickCount; 1_Core/proto/EnString.c:199/240/113 Length/IndexOf/Substring;
// 3_Game/tools/tools.c ScriptCallQueue CallLater/Remove; EnDebug.c:96 Print.
//
// State lives only in the data, never in a ledger: every boot each registered step inspects
// its target, so a crash at any point leaves a state the next boot classifies and repairs.
// Per step, for target T, scratch image P = T.mig-<id>.tmp, backup slot B = T.pre-<id>.bak[n]:
//   1 verified backup copy B (never overwritten; up to HC_BACKUP_SLOTS slots)
//   2 verified full new image P (must classify CURRENT)
//   3 delete T, copy P to T, read T back == P
//   4 delete P
// Refusals never delete T, B or any operator file and never edit a file they cannot classify.
// No migration is registered by default: steps are added by HCBuiltins() only when a plan names
// the schema change.
class HCMigrationStep
{
    static const int STATE_UNKNOWN = 0;
    static const int STATE_CURRENT = 1;
    static const int STATE_OLD = 2;
    static const int STATE_NEWER = 3;

    // Stable token, [a-z0-9-], 1..48 chars; names the scratch and backup files.
    string HCId() { return ""; }
    // Gate store refused on this boot when the step refuses or is deferred:
    // "world", "escalation", "groups", or "" for a file no store gate covers.
    string HCStore() { return ""; }
    // Full profile path, starting "$profile:HollowCountry/".
    string HCTarget() { return ""; }
    int HCLimit() { return HCGroupIO.HC_RAW_READ_CAP; }
    // Pure classification of the whole file text; no IO. A file that is torn or not
    // recognisably this store's format must be UNKNOWN, a higher version NEWER.
    int HCClassify(string text) { return HCMigrationStep.STATE_UNKNOWN; }
    // Pure and deterministic OLD -> CURRENT text; no IO. Return false with a token reason to refuse.
    bool HCTransform(string text, out string migrated, out string reason)
    {
        reason = "not_implemented";
        return false;
    }
}

// Self-test probe: a synthetic two-version text format on a scratch file. Never a store.
class HCMigrationProbeStep : HCMigrationStep
{
    static const string PATH = "$profile:HollowCountry/migrate-selftest.probe";
    override string HCId() { return "selftest-probe"; }
    override string HCTarget() { return PATH; }
    override int HCLimit() { return 256; }
    override int HCClassify(string text)
    {
        int length = text.Length();
        if (length < 11 || text.Substring(length - 1, 1) != ";") { return HCMigrationStep.STATE_UNKNOWN; }
        string head = text.Substring(0, 9);
        if (head == "probe-v2:") { return HCMigrationStep.STATE_CURRENT; }
        if (head == "probe-v1:") { return HCMigrationStep.STATE_OLD; }
        if (head == "probe-v3:") { return HCMigrationStep.STATE_NEWER; }
        return HCMigrationStep.STATE_UNKNOWN;
    }
    override bool HCTransform(string text, out string migrated, out string reason)
    {
        reason = "";
        migrated = "probe-v2:" + text.Substring(9, text.Length() - 9);
        return true;
    }
}

class HCMigrationRunner
{
    static const int RESULT_APPLIED = 1;
    static const int RESULT_SKIPPED = 2;
    static const int RESULT_REFUSED = 3;
    static const int HC_BACKUP_SLOTS = 4;
    static const int HC_BOOT_STEP_CAP = 8;
    static const float HC_BOOT_BUDGET_MS = 250;
    static const float HC_TICK_BUDGET_MS = 4;
    static const int HC_TICK_INTERVAL_MS = 1000;
    static const string HC_PREFIX = "$profile:HollowCountry/";

    protected static ref array<ref HCMigrationStep> s_Steps = new array<ref HCMigrationStep>;
    protected static ref HCWorkBudget s_Budget = new HCWorkBudget;
    protected static bool s_BuiltinsRegistered;
    protected static bool s_SelfTested;
    protected static bool s_Scheduled;
    protected static bool s_WorldEnabled = true;
    protected static int s_Next;
    protected static int s_Applied;
    protected static int s_Skipped;
    protected static int s_Refused;
    protected static string s_BlockWorld;
    protected static string s_BlockEscalation;
    protected static string s_BlockGroups;

    // Steps for stores or files introduced by a plan-named schema change register here.
    // Intentionally empty: nothing that changes behaviour is registered by default.
    protected static void HCBuiltins()
    {
    }

    static bool HCRegisterStep(HCMigrationStep step)
    {
        if (!step) { return false; }
        string id = step.HCId();
        string why = HCStepInvalid(step);
        if (why == "")
        {
            foreach (HCMigrationStep known : s_Steps)
            {
                if (known.HCId() == id) { why = "duplicate_id"; }
            }
        }
        if (why != "")
        {
            HCReceipt(id, HCMigrationRunner.RESULT_REFUSED, why);
            return false;
        }
        s_Steps.Insert(step);
        return true;
    }

    // Called once per boot by HCPersistenceDisposition.HCLoad after the recovery gate is
    // admitted and before any store module opens its file. Bounded by a step cap and a time
    // budget; steps left over are deferred to later ticks and their stores refuse this boot.
    static void HCBoot(bool enableWorld)
    {
        HCHalt();
        s_WorldEnabled = enableWorld;
        if (!s_BuiltinsRegistered)
        {
            s_BuiltinsRegistered = true;
            HCBuiltins();
        }
        if (!s_SelfTested)
        {
            s_SelfTested = true;
            HCSelfTest();
        }
        if (s_Steps.Count() < 1)
        {
            Print("[HC Migrate] id=runner action=skipped reason=no_registered_migrations");
            return;
        }
        s_Budget.HCReset(HCMigrationRunner.HC_BOOT_STEP_CAP, HCMigrationRunner.HC_BOOT_BUDGET_MS);
        while (s_Next < s_Steps.Count() && s_Budget.HCContinue())
        {
            HCRunOne(s_Steps.Get(s_Next));
            s_Next++;
        }
        if (s_Next < s_Steps.Count())
        {
            int index = s_Next;
            while (index < s_Steps.Count())
            {
                HCMigrationStep deferred = s_Steps.Get(index);
                HCBlock(deferred.HCStore(), "deferred_budget");
                HCReceipt(deferred.HCId(), HCMigrationRunner.RESULT_SKIPPED, "deferred_budget");
                index++;
            }
            HCSchedule();
            return;
        }
        HCSummary();
    }

    // Refuse, for this boot only, every store whose migration refused or is deferred.
    // Files stay exactly as they are; the gate reports through the shared quarantine line.
    static void HCGate()
    {
        if (s_BlockWorld != "") { HCRecoveryGate.HCRefuse("world", "migration_" + s_BlockWorld); }
        if (s_BlockEscalation != "") { HCRecoveryGate.HCRefuse("escalation", "migration_" + s_BlockEscalation); }
        if (s_BlockGroups != "") { HCRecoveryGate.HCRefuse("groups", "migration_" + s_BlockGroups); }
    }

    // Cancel continuation and clear per-boot state; the registry itself is kept.
    static void HCHalt()
    {
        if (s_Scheduled && GetGame())
        {
            GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).Remove(HCTick);
        }
        s_Scheduled = false;
        s_Next = 0;
        s_Applied = 0;
        s_Skipped = 0;
        s_Refused = 0;
        s_BlockWorld = "";
        s_BlockEscalation = "";
        s_BlockGroups = "";
    }

    protected static void HCSchedule()
    {
        if (s_Scheduled || !GetGame()) { return; }
        s_Scheduled = true;
        GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(HCTick, HCMigrationRunner.HC_TICK_INTERVAL_MS, false);
    }

    // One step per tick; each step is itself bounded by the 8 MiB raw cap.
    protected static void HCTick()
    {
        s_Scheduled = false;
        if (s_Next >= s_Steps.Count()) { return; }
        s_Budget.HCReset(1, HCMigrationRunner.HC_TICK_BUDGET_MS);
        while (s_Next < s_Steps.Count() && s_Budget.HCContinue())
        {
            HCRunOne(s_Steps.Get(s_Next));
            s_Next++;
        }
        if (s_Next < s_Steps.Count())
        {
            HCSchedule();
            return;
        }
        HCSummary();
    }

    protected static void HCSummary()
    {
        Print("[HC Migrate] id=runner action=skipped reason=summary applied=" + s_Applied.ToString() + " skipped=" + s_Skipped.ToString() + " refused=" + s_Refused.ToString());
    }

    protected static void HCBlock(string store, string reason)
    {
        if (store == "world" && s_BlockWorld == "") { s_BlockWorld = reason; }
        if (store == "escalation" && s_BlockEscalation == "") { s_BlockEscalation = reason; }
        if (store == "groups" && s_BlockGroups == "") { s_BlockGroups = reason; }
    }

    protected static void HCReceipt(string id, int result, string reason)
    {
        string action = "refused";
        if (result == HCMigrationRunner.RESULT_APPLIED) { action = "applied"; }
        if (result == HCMigrationRunner.RESULT_SKIPPED) { action = "skipped"; }
        Print("[HC Migrate] id=" + id + " action=" + action + " reason=" + reason);
    }

    protected static void HCRunOne(HCMigrationStep step)
    {
        string reason;
        int result;
        string store = step.HCStore();
        if (!s_WorldEnabled && (store == "world" || store == "escalation"))
        {
            result = HCMigrationRunner.RESULT_SKIPPED;
            reason = "world_disabled";
        }
        else
        {
            result = HCRunStep(step, reason);
        }
        if (result == HCMigrationRunner.RESULT_APPLIED) { s_Applied++; }
        if (result == HCMigrationRunner.RESULT_SKIPPED) { s_Skipped++; }
        if (result == HCMigrationRunner.RESULT_REFUSED)
        {
            s_Refused++;
            HCBlock(store, reason);
        }
        HCReceipt(step.HCId(), result, reason);
    }

    // Returns "" when the step is well formed, otherwise a refusal token.
    protected static string HCStepInvalid(HCMigrationStep step)
    {
        string id = step.HCId();
        string target = step.HCTarget();
        string store = step.HCStore();
        if (id.Length() < 1 || id.Length() > 48) { return "step_invalid_id"; }
        string allowed = "abcdefghijklmnopqrstuvwxyz0123456789-";
        for (int i = 0; i < id.Length(); i++)
        {
            if (allowed.IndexOf(id.Substring(i, 1)) < 0) { return "step_invalid_id"; }
        }
        if (target.Length() <= HCMigrationRunner.HC_PREFIX.Length() || target.Length() > 160 || target.IndexOf(HCMigrationRunner.HC_PREFIX) != 0) { return "step_invalid_target"; }
        if (target.IndexOf("..") >= 0 || target.IndexOf("\\") >= 0 || target.IndexOf("//") >= 0) { return "step_invalid_target"; }
        if (store != "" && store != "world" && store != "escalation" && store != "groups") { return "step_invalid_store"; }
        if (step.HCLimit() < 1 || step.HCLimit() > HCGroupIO.HC_RAW_READ_CAP) { return "step_invalid_limit"; }
        return "";
    }

    protected static string HCPendingPath(string target, string id) { return target + ".mig-" + id + ".tmp"; }

    protected static string HCBackupSuffix(string id, int slot)
    {
        string suffix = ".pre-" + id + ".bak";
        if (slot > 1) { suffix = suffix + slot.ToString(); }
        return suffix;
    }

    protected static string HCBackupPath(string target, string id, int slot) { return target + HCBackupSuffix(id, slot); }

    // Classify and, if needed, repair one step. Pure of receipts; the caller prints them.
    static int HCRunStep(HCMigrationStep step, out string reason)
    {
        reason = HCStepInvalid(step);
        if (reason != "") { return HCMigrationRunner.RESULT_REFUSED; }
        string id = step.HCId();
        string target = step.HCTarget();
        int limit = step.HCLimit();
        string pending = HCPendingPath(target, id);
        bool hasPending = FileExist(pending);
        if (!FileExist(target))
        {
            if (!hasPending)
            {
                reason = "target_absent";
                return HCMigrationRunner.RESULT_SKIPPED;
            }
            // Crash between deleting the target and copying the verified image over it.
            return HCRecover(step, target, pending, limit, false, "", "recovered_missing_target", reason);
        }
        string text;
        // Empty is readable (a torn or truncated target); oversize or unopenable is not.
        bool readable = HCPersistenceDisposition.HCReadArchive(target, limit, text, true);
        int state = HCMigrationStep.STATE_UNKNOWN;
        if (readable) { state = step.HCClassify(text); }
        if (state == HCMigrationStep.STATE_CURRENT)
        {
            reason = "current";
            if (hasPending)
            {
                // Scratch left after a finished commit; the target is already verified current.
                if (!DeleteFile(pending) || FileExist(pending)) { reason = "current_pending_cleanup_failed"; }
                else { reason = "current_pending_removed"; }
            }
            return HCMigrationRunner.RESULT_SKIPPED;
        }
        if (state == HCMigrationStep.STATE_NEWER)
        {
            reason = "newer_schema";
            return HCMigrationRunner.RESULT_REFUSED;
        }
        if (state == HCMigrationStep.STATE_UNKNOWN)
        {
            if (hasPending)
            {
                // Crash while copying the image over the target: a torn prefix of it, or empty.
                return HCRecover(step, target, pending, limit, readable, text, "recovered_torn_commit", reason);
            }
            reason = "target_unreadable";
            if (readable) { reason = "target_schema_unknown"; }
            return HCMigrationRunner.RESULT_REFUSED;
        }
        if (state != HCMigrationStep.STATE_OLD)
        {
            reason = "classify_invalid";
            return HCMigrationRunner.RESULT_REFUSED;
        }
        return HCMigrate(step, target, pending, text, limit, reason);
    }

    protected static int HCMigrate(HCMigrationStep step, string target, string pending, string text, int limit, out string reason)
    {
        string id = step.HCId();
        // A scratch image beside an OLD target was never committed; it is recomputed below.
        if (FileExist(pending) && (!DeleteFile(pending) || FileExist(pending)))
        {
            reason = "pending_cleanup_failed";
            return HCMigrationRunner.RESULT_REFUSED;
        }
        string migrated;
        string why;
        if (!step.HCTransform(text, migrated, why))
        {
            reason = why;
            if (reason == "") { reason = "transform_refused"; }
            return HCMigrationRunner.RESULT_REFUSED;
        }
        if (migrated.Length() < 1 || migrated.Length() > limit || step.HCClassify(migrated) != HCMigrationStep.STATE_CURRENT)
        {
            reason = "transform_not_current";
            return HCMigrationRunner.RESULT_REFUSED;
        }
        if (!HCBackup(target, id, text, limit, reason)) { return HCMigrationRunner.RESULT_REFUSED; }
        if (!HCPersistenceDisposition.HCWriteRawNew(pending, migrated, limit))
        {
            reason = "pending_write_failed";
            return HCMigrationRunner.RESULT_REFUSED;
        }
        if (!HCCommit(target, pending, migrated, limit, reason)) { return HCMigrationRunner.RESULT_REFUSED; }
        reason = "migrated";
        return HCMigrationRunner.RESULT_APPLIED;
    }

    // Reuse a slot already holding exactly this image; otherwise fill the first free slot.
    // An occupied slot with other bytes is evidence and is never touched.
    protected static bool HCBackup(string target, string id, string text, int limit, out string reason)
    {
        reason = "backup_slots_full";
        string existing;
        string path;
        for (int slot = 1; slot <= HCMigrationRunner.HC_BACKUP_SLOTS; slot++)
        {
            path = HCBackupPath(target, id, slot);
            if (!FileExist(path))
            {
                if (!HCPersistenceDisposition.HCArchive(target, HCBackupSuffix(id, slot), limit))
                {
                    reason = "backup_failed";
                    return false;
                }
                reason = "";
                return true;
            }
            if (HCGroupIO.HCReadRaw(path, limit, existing) && existing == text)
            {
                reason = "";
                return true;
            }
        }
        return false;
    }

    // A pending image may replace the target only when some backup slot proves it descends from
    // that backup: the slot classifies OLD and the deterministic transform reproduces the image.
    protected static bool HCProvenance(HCMigrationStep step, string target, int limit, string imageText)
    {
        string old;
        string migrated;
        string why;
        string path;
        for (int slot = 1; slot <= HCMigrationRunner.HC_BACKUP_SLOTS; slot++)
        {
            path = HCBackupPath(target, step.HCId(), slot);
            if (FileExist(path) && HCGroupIO.HCReadRaw(path, limit, old) && step.HCClassify(old) == HCMigrationStep.STATE_OLD)
            {
                if (step.HCTransform(old, migrated, why) && migrated == imageText) { return true; }
            }
        }
        return false;
    }

    protected static int HCRecover(HCMigrationStep step, string target, string pending, int limit, bool targetReadable, string targetText, string okReason, out string reason)
    {
        string imageText;
        if (!HCGroupIO.HCReadRaw(pending, limit, imageText) || step.HCClassify(imageText) != HCMigrationStep.STATE_CURRENT)
        {
            reason = "pending_image_invalid";
            return HCMigrationRunner.RESULT_REFUSED;
        }
        // Only a torn prefix (or an empty file) of our own image may be replaced.
        if (targetReadable && targetText.Length() > 0 && imageText.IndexOf(targetText) != 0)
        {
            reason = "target_schema_unknown";
            return HCMigrationRunner.RESULT_REFUSED;
        }
        if (!HCProvenance(step, target, limit, imageText))
        {
            reason = "pending_provenance_missing";
            return HCMigrationRunner.RESULT_REFUSED;
        }
        if (!HCCommit(target, pending, imageText, limit, reason)) { return HCMigrationRunner.RESULT_REFUSED; }
        reason = okReason;
        return HCMigrationRunner.RESULT_APPLIED;
    }

    // Replace target with the verified pending image. Not atomic: the pending image and the
    // backup stay on disk until readback succeeds, which is what the recovery paths rely on.
    protected static bool HCCommit(string target, string pending, string imageText, int limit, out string reason)
    {
        reason = "";
        if (FileExist(target) && (!DeleteFile(target) || FileExist(target)))
        {
            reason = "target_delete_failed";
            return false;
        }
        bool copied = CopyFile(pending, target);
        if (!copied) { copied = CopyFile(pending, target); }
        string readback;
        if (!copied || !HCGroupIO.HCReadRaw(target, limit, readback) || readback != imageText)
        {
            reason = "commit_failed_pending_kept";
            return false;
        }
        // A failed scratch delete is harmless: the next boot sees a CURRENT target and removes it.
        if (!DeleteFile(pending)) { Print("[HC Migrate] id=runner action=skipped reason=pending_delete_failed"); }
        return true;
    }

    // Exercises the real IO path on scratch files once per script lifetime: apply, idempotent
    // rerun, stale scratch, torn commit, missing target, newer-schema refusal and an
    // unclassifiable file. Touches no store file. Prints one [HC SelfTest] line.
    protected static void HCSelfTest()
    {
        string detail = "ok";
        bool passed = false;
        if (GetGame() && GetGame().IsServer()) { passed = HCSelfTestCases(detail); }
        else { detail = "server_required"; }
        HCProbeClear();
        Print("[HC SelfTest] name=migration_runner pass=" + passed.ToString() + " detail=" + detail);
    }

    protected static void HCProbeClear()
    {
        HCMigrationProbeStep probe = new HCMigrationProbeStep;
        string target = HCMigrationProbeStep.PATH;
        HCProbeDelete(target);
        HCProbeDelete(HCPendingPath(target, probe.HCId()));
        HCProbeDelete(HCBackupPath(target, probe.HCId(), 1));
        HCProbeDelete(HCBackupPath(target, probe.HCId(), 2));
    }

    protected static void HCProbeDelete(string path)
    {
        if (FileExist(path)) { DeleteFile(path); }
    }

    protected static bool HCProbeIs(string path, string expected)
    {
        string text;
        return HCGroupIO.HCReadRaw(path, 256, text) && text == expected;
    }

    protected static bool HCProbePut(string path, string text)
    {
        return HCPersistenceDisposition.HCWriteRawNew(path, text, 256);
    }

    protected static bool HCSelfTestCases(out string detail)
    {
        HCMigrationProbeStep probe = new HCMigrationProbeStep;
        string target = HCMigrationProbeStep.PATH;
        string pending = HCPendingPath(target, probe.HCId());
        string backup = HCBackupPath(target, probe.HCId(), 1);
        string reason;
        int result;
        if (!FileExist("$profile:HollowCountry") && !MakeDirectory("$profile:HollowCountry")) { detail = "profile_unavailable"; return false; }
        HCProbeClear();
        if (HCStepInvalid(probe) != "") { detail = "probe_step_invalid"; return false; }

        // Apply, then an idempotent rerun.
        if (!HCProbePut(target, "probe-v1:alpha;")) { detail = "setup_apply"; return false; }
        result = HCRunStep(probe, reason);
        if (result != HCMigrationRunner.RESULT_APPLIED || reason != "migrated" || !HCProbeIs(target, "probe-v2:alpha;")) { detail = "apply_" + reason; return false; }
        if (!HCProbeIs(backup, "probe-v1:alpha;") || FileExist(pending)) { detail = "apply_backup_or_scratch"; return false; }
        result = HCRunStep(probe, reason);
        if (result != HCMigrationRunner.RESULT_SKIPPED || reason != "current" || !HCProbeIs(target, "probe-v2:alpha;")) { detail = "rerun_" + reason; return false; }

        // Crash after backup and scratch, before the commit: recomputed, backup reused.
        HCProbeClear();
        if (!HCProbePut(target, "probe-v1:alpha;") || !HCProbePut(backup, "probe-v1:alpha;") || !HCProbePut(pending, "probe-v2:alpha;")) { detail = "setup_stale"; return false; }
        result = HCRunStep(probe, reason);
        if (result != HCMigrationRunner.RESULT_APPLIED || !HCProbeIs(target, "probe-v2:alpha;") || FileExist(pending) || FileExist(HCBackupPath(target, probe.HCId(), 2))) { detail = "stale_" + reason; return false; }

        // Crash while copying the image over the target: a torn prefix.
        HCProbeClear();
        if (!HCProbePut(target, "probe-v2:al") || !HCProbePut(backup, "probe-v1:alpha;") || !HCProbePut(pending, "probe-v2:alpha;")) { detail = "setup_torn"; return false; }
        result = HCRunStep(probe, reason);
        if (result != HCMigrationRunner.RESULT_APPLIED || reason != "recovered_torn_commit" || !HCProbeIs(target, "probe-v2:alpha;") || !HCProbeIs(backup, "probe-v1:alpha;")) { detail = "torn_" + reason; return false; }

        // Crash between deleting the target and copying the image.
        HCProbeClear();
        if (!HCProbePut(backup, "probe-v1:alpha;") || !HCProbePut(pending, "probe-v2:alpha;")) { detail = "setup_missing"; return false; }
        result = HCRunStep(probe, reason);
        if (result != HCMigrationRunner.RESULT_APPLIED || reason != "recovered_missing_target" || !HCProbeIs(target, "probe-v2:alpha;")) { detail = "missing_" + reason; return false; }

        // A pending image without provenance never replaces anything.
        HCProbeClear();
        if (!HCProbePut(target, "probe-v2:al") || !HCProbePut(pending, "probe-v2:alpha;")) { detail = "setup_noprov"; return false; }
        result = HCRunStep(probe, reason);
        if (result != HCMigrationRunner.RESULT_REFUSED || reason != "pending_provenance_missing" || !HCProbeIs(target, "probe-v2:al")) { detail = "noprov_" + reason; return false; }

        // A newer schema and an unclassifiable file are refused and left untouched.
        HCProbeClear();
        if (!HCProbePut(target, "probe-v3:alpha;")) { detail = "setup_newer"; return false; }
        result = HCRunStep(probe, reason);
        if (result != HCMigrationRunner.RESULT_REFUSED || reason != "newer_schema" || !HCProbeIs(target, "probe-v3:alpha;") || FileExist(backup)) { detail = "newer_" + reason; return false; }
        HCProbeClear();
        if (!HCProbePut(target, "garbage")) { detail = "setup_unknown"; return false; }
        result = HCRunStep(probe, reason);
        if (result != HCMigrationRunner.RESULT_REFUSED || reason != "target_schema_unknown" || !HCProbeIs(target, "garbage")) { detail = "unknown_" + reason; return false; }
        detail = "cases=7";
        return true;
    }
}
