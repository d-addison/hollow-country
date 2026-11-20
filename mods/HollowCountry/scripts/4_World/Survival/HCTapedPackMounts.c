// HC-52: startup-only authored-pair admission, sharing HC-7's custody/journal.
// No tick, save loop, alternate inventory owner, light entity or offset shim.
// Installed scripts-1.30.164289 API evidence (relative to native script root):
// 3_Game/Global/Game.c:558 ConfigGetTextArray,1120 IsServer;
// 1_Core/proto/EnScript.c:380,385,394,407 Count/Clear/Find/Insert;
// 1_Core/proto/EnDebug.c:96 Print; EnConvert.c:30 int.ToString.
// N2 InventoryLocation.c:131 SetAttachment names a native slot, not a transform.
// N11 ScriptedLightBase.c:132-180 attaches a client light, not an inventory item.
// UniversalLight.c:47-91 owns its client light/memory points and cleanup.
// ActionTurnOnHelmetFlashlight.c:33-65 requires Mich2001Helmet; not a pack API.
// Do not use those APIs to simulate an unobserved backpack proxy/mount.
// Wave 16 (owner: "enable all features by default"): the mounts are admitted
// unverified, the HCV2Admission pattern. HCSettings.EnableTapedPackMounts
// defaults true and is the operator opt-out. lights/pair-receipts.json is a
// verdict log, not a gate: a pair is admitted unless its row has Disabled=true;
// Checked/CheckDate/Note record an operator's client check and change nothing
// else. An unknown pair id or a malformed file refuses the whole file (the
// module reports degraded). HCTapedPackCatalog.Qualified stays false: it is the
// native two-client verdict, so the admission line says "admitted unverified".
// Every pair still needs its native slot arrays (honest check, startup only).
// Weapon cross-slot pairs (cross_<Host>_<Light>) are admitted here at startup
// into mHCWeaponAdmitted; the attach site (HCTapedLightV1Qualification) asks
// WeaponPairAdmitted, a cached lookup. Nothing here was observed in DayZ.
// Receipt rows read with the optional Disabled opt-out; absent loads as false.
class HCTapedReceiptRow
{
    string PairId;
    bool Disabled = false;
}

class HCTapedReceiptRows
{
    ref array<ref HCTapedReceiptRow> Receipts = new array<ref HCTapedReceiptRow>();
}

class HCTapedPackMounts : HCModule
{
    protected static bool mHCCrossSlot;
    protected static bool mHCConfigured;
    protected static ref TStringArray mHCPermitted = new TStringArray;
    protected static bool mHCSettingOn;
    protected static int mHCReceiptMaxBytes;
    protected static ref TStringArray mHCChecked = new TStringArray;
    // Pair ids a receipt row opts out (Disabled=true); empty when the file was refused.
    protected static ref TStringArray mHCDisabled = new TStringArray;
    // "" when the receipt file loaded (or was not read), else the refusal reason.
    protected static string mHCReceiptReason;
    // Weapon pair ids admitted at startup, and the first weapon refusal reason.
    protected static ref TStringArray mHCWeaponAdmitted = new TStringArray;
    protected static string mHCWeaponFirstRefusal;
    protected static int mHCWeaponRefused;
    protected bool mHCStarted;
    protected ref HCOperationalStatus mHCStatus = new HCOperationalStatus;

    override string GetName() { return "TapedPackMounts"; }
    override bool IsEnabled(HCSettings settings) { return settings != null; }
    override HCOperationalStatus HCGetOperationalStatus() { return mHCStatus; }

    static void Reset()
    {
        mHCCrossSlot = false;
        mHCConfigured = false;
        mHCPermitted.Clear();
        mHCSettingOn = false;
        mHCReceiptMaxBytes = 0;
        mHCChecked.Clear();
        mHCDisabled.Clear();
        mHCReceiptReason = "";
        mHCWeaponAdmitted.Clear();
        mHCWeaponFirstRefusal = "";
        mHCWeaponRefused = 0;
    }

    // Called only by the server settings owner before module startup. Copy a
    // bounded, unique exact-ID list so later DTO mutation cannot grant access.
    static bool Configure(HCTapedLightMountSettings settings)
    {
        if (!GetGame() || !GetGame().IsServer()) { return false; }
        Reset();
        if (!settings || !settings.permittedPairIds) { return false; }
        if (settings.permittedPairIds.Count() > 2) { return false; }
        foreach (string pairId : settings.permittedPairIds)
        {
            if (!HCTapedPackCatalog.KnownPair(pairId) || mHCPermitted.Find(pairId) >= 0)
            {
                Reset();
                return false;
            }
            mHCPermitted.Insert(pairId);
        }
        mHCCrossSlot = settings.crossSlotLights;
        mHCConfigured = true;
        return true;
    }

    static bool CrossSlotEnabled()
    {
        return mHCConfigured && mHCCrossSlot;
    }

    static bool NativeSlotAvailable(string pairId)
    {
        if (!GetGame() || !GetGame().IsServer()) { return false; }
        if (!HCTapedPackCatalog.KnownPair(pairId)) { return false; }
        if (!HCBuildIdentity.Matches(HCBuildIdentity.SeenBuild())) { return false; }
        string slotName = HCTapedPackCatalog.SlotName(pairId);
        TStringArray hostSlots = new TStringArray;
        TStringArray lightSlots = new TStringArray;
        GetGame().ConfigGetTextArray("CfgVehicles TortillaBag attachments", hostSlots);
        GetGame().ConfigGetTextArray("CfgVehicles UniversalLight inventorySlot", lightSlots);
        return hostSlots.Find(slotName) >= 0 && lightSlots.Find(slotName) >= 0;
    }

    static bool BindingAllowed(HCTapedLightBinding binding)
    {
        if (!GetGame() || !GetGame().IsServer() || !binding) { return false; }
        if (binding.HostConfigRoot == "CfgWeapons") { return WeaponBindingAllowed(binding); }
        if (!mHCConfigured || binding.HostConfigRoot != "CfgVehicles") { return false; }
        if (!HCTapedPackCatalog.Matches(binding.PairId, binding.HostClass, binding.LightClass, binding.SlotName, binding.CrossSlot)) { return false; }
        if (binding.CrossSlot)
        {
            if (!CrossSlotEnabled() || mHCPermitted.Find(binding.PairId) < 0) { return false; }
        }
        // Deliberately cheap closed path: no repeated native config scans for
        // an unqualified pair, no fabricated measurement digest or binding.
        return PairQualified(binding.PairId);
    }

    static bool ReceiptChecked(string pairId)
    {
        return mHCChecked.Find(pairId) >= 0;
    }

    static bool ReceiptDisabled(string pairId)
    {
        return mHCDisabled.Find(pairId) >= 0;
    }

    // Checked receipt ids split by kind, for the separate boot counts.
    static int ReceiptPackChecked()
    {
        int packChecked = 0;
        foreach (string checkedId : mHCChecked)
        {
            if (HCTapedPackCatalog.KnownPair(checkedId)) { packChecked = packChecked + 1; }
        }
        return packChecked;
    }

    static int ReceiptWeaponChecked()
    {
        return mHCChecked.Count() - ReceiptPackChecked();
    }

    // "" when the pair is admitted, else the first refusal reason. Order keeps
    // the closed path cheap: no native config scan until every earlier gate holds.
    // Pack pairs are decided here; any other id goes to the weapon path.
    static string PairAdmission(string pairId)
    {
        if (!HCTapedPackCatalog.KnownPair(pairId)) { return WeaponPairAdmission(pairId); }
        if (!mHCConfigured) { return "pack_mounts_unconfigured"; }
        if (!mHCSettingOn) { return "setting_off"; }
        if (mHCReceiptReason != "") { return mHCReceiptReason; }
        if (ReceiptDisabled(pairId)) { return "receipt_disabled"; }
        if (pairId == "tortilla_universal_cross")
        {
            if (!CrossSlotEnabled()) { return "cross_slot_disabled"; }
            if (mHCPermitted.Find(pairId) < 0) { return "cross_slot_pair_not_permitted"; }
        }
        if (!NativeSlotAvailable(pairId)) { return "pack_native_slot_unavailable"; }
        return "";
    }

    static bool PairQualified(string pairId)
    {
        return PairAdmission(pairId) == "";
    }

    static int AdmittedCount()
    {
        int admitted = 0;
        TStringArray ids = HCTapedPackCatalog.PairIds();
        foreach (string pairId : ids)
        {
            if (PairQualified(pairId)) { admitted = admitted + 1; }
        }
        return admitted;
    }

    // Pairs with a recorded native/two-client verdict. Shipped code has none, so
    // every admission is "admitted unverified".
    static int VerifiedCount()
    {
        int verified = 0;
        TStringArray ids = HCTapedPackCatalog.PairIds();
        foreach (string pairId : ids)
        {
            if (HCTapedPackCatalog.Qualified(pairId)) { verified = verified + 1; }
        }
        return verified;
    }

    // First refusal across the known pack pairs, for the one-line boot summary.
    // An operator opt-out (receipt_disabled) is a choice, not a refusal.
    static string FirstAdmissionReason()
    {
        TStringArray ids = HCTapedPackCatalog.PairIds();
        string reason = "";
        foreach (string pairId : ids)
        {
            string refusal = PairAdmission(pairId);
            if (reason == "" && refusal != "receipt_disabled") { reason = refusal; }
        }
        return reason;
    }

    static int PackRefusedCount()
    {
        int refused = 0;
        TStringArray ids = HCTapedPackCatalog.PairIds();
        foreach (string pairId : ids)
        {
            string refusal = PairAdmission(pairId);
            if (refusal != "" && refusal != "receipt_disabled") { refused = refused + 1; }
        }
        return refused;
    }

    // Weapon cross-slot pair: the host must carry the slot natively and the cross
    // light must list that slot in its own inventorySlot, or the engine itself
    // refuses the attachment. Same startup-only config scan as the pack check.
    static bool WeaponNativeSlotAvailable(HCTapedLightHostRow row)
    {
        if (!GetGame() || !GetGame().IsServer() || !row) { return false; }
        if (!HCBuildIdentity.Matches(HCBuildIdentity.SeenBuild())) { return false; }
        TStringArray hostSlots = new TStringArray;
        TStringArray lightSlots = new TStringArray;
        GetGame().ConfigGetTextArray("CfgWeapons " + row.HostClass + " attachments", hostSlots);
        GetGame().ConfigGetTextArray("CfgVehicles " + row.LightClass + " inventorySlot", lightSlots);
        return hostSlots.Find(row.SlotName) >= 0 && lightSlots.Find(row.SlotName) >= 0;
    }

    static string WeaponPairAdmission(string pairId)
    {
        HCTapedLightHostRow row = HCTapedLightCatalog.CrossRow(pairId);
        if (!row) { return "unsupported_pack_pair"; }
        if (!mHCConfigured) { return "pack_mounts_unconfigured"; }
        if (!mHCSettingOn) { return "setting_off"; }
        if (mHCReceiptReason != "") { return mHCReceiptReason; }
        if (ReceiptDisabled(pairId)) { return "receipt_disabled"; }
        if (!WeaponNativeSlotAvailable(row)) { return "weapon_light_slot_unavailable"; }
        return "";
    }

    // Startup only: decide every weapon pair once and cache the admitted ids, so
    // the attach site never repeats a config scan. Clears first, so a stop/start
    // or a refused receipt file leaves nothing admitted.
    static void HCRefreshWeaponAdmission()
    {
        mHCWeaponAdmitted.Clear();
        mHCWeaponFirstRefusal = "";
        mHCWeaponRefused = 0;
        TStringArray ids = HCTapedLightCatalog.CrossPairIds();
        foreach (string pairId : ids)
        {
            string refusal = WeaponPairAdmission(pairId);
            if (refusal == "") { mHCWeaponAdmitted.Insert(pairId); }
            // An operator opt-out (receipt_disabled) is counted in disabled=, not here.
            if (refusal != "" && refusal != "receipt_disabled")
            {
                mHCWeaponRefused = mHCWeaponRefused + 1;
                if (mHCWeaponFirstRefusal == "") { mHCWeaponFirstRefusal = refusal; }
            }
        }
    }

    // Cached runtime lookup for the attach site; cheap and false off the server.
    static bool WeaponPairAdmitted(string pairId)
    {
        if (!GetGame() || !GetGame().IsServer()) { return false; }
        if (!mHCConfigured || !mHCSettingOn) { return false; }
        return mHCWeaponAdmitted.Find(pairId) >= 0;
    }

    // A weapon binding must name an admitted pair and match its derived row exactly.
    static bool WeaponBindingAllowed(HCTapedLightBinding binding)
    {
        if (!binding || !binding.CrossSlot || binding.PairId == "") { return false; }
        HCTapedLightHostRow row = HCTapedLightCatalog.CrossRow(binding.PairId);
        if (!row) { return false; }
        if (row.HostClass != binding.HostClass || row.LightClass != binding.LightClass || row.SlotName != binding.SlotName) { return false; }
        return WeaponPairAdmitted(binding.PairId);
    }

    // Receipt file read: bounded by the manifest's MaxReceiptBytes, "" when unreadable.
    protected static string ReadReceipts()
    {
        string text;
        if (!HCGroupIO.Read("$mission:hollow-country/lights/pair-receipts.json", mHCReceiptMaxBytes, text)) { return ""; }
        return text;
    }

    // Native JsonFileLoader zero-fills missing fields, so callers guard presence.
    protected static HCTapedPairReceipts ParseReceipts(string text)
    {
        HCTapedPairReceipts parsed;
        string error;
        if (!JsonFileLoader<HCTapedPairReceipts>.LoadData(text, parsed, error)) { return null; }
        return parsed;
    }

    // Second parse of the same text for the optional per-row Disabled opt-out.
    // An absent Disabled loads as false (admitted); a non-bool is refused earlier.
    protected static HCTapedReceiptRows ParseOptOuts(string text)
    {
        HCTapedReceiptRows parsed;
        string error;
        if (!JsonFileLoader<HCTapedReceiptRows>.LoadData(text, parsed, error)) { return null; }
        return parsed;
    }

    // True when every quoted key (the quoted word followed by a colon) in the
    // text is followed by a true or false literal. JsonFileLoader may coerce or
    // zero-fill a wrongly typed bool, so the raw text is checked first. A key that
    // is absent passes (optional bools). Escaped quotes inside a Note never match.
    // First index at or after startAt where needle starts, -1 when absent. Compares
    // through 1 KB windows: IndexOf/IndexOfFrom are only trusted on 1 KB text.
    static int ReceiptFind(HCTextWindow text, HCTextWindow needle, int startAt)
    {
        int last = text.Length() - needle.Length();
        int index = startAt;
        while (index <= last)
        {
            int offset = 0;
            while (offset < needle.Length() && text.At(index + offset) == needle.At(offset)) { offset = offset + 1; }
            if (offset == needle.Length()) { return index; }
            index = index + 1;
        }
        return -1;
    }

    static bool ReceiptBoolTyped(string text, string key)
    {
        HCTextWindow window = new HCTextWindow(text);
        HCTextWindow needle = new HCTextWindow("\"" + key + "\"");
        int total = window.Length();
        int at = ReceiptFind(window, needle, 0);
        while (at >= 0)
        {
            int cursor = at + needle.Length();
            while (cursor < total && (window.At(cursor) == " " || window.At(cursor) == "\n" || window.At(cursor) == "\r" || window.At(cursor) == "\t")) { cursor = cursor + 1; }
            // A string value equal to the key (e.g. "Note": "Checked") is not a key: no colon follows, skip it.
            if (cursor < total && window.At(cursor) == ":")
            {
                cursor = cursor + 1;
                while (cursor < total && (window.At(cursor) == " " || window.At(cursor) == "\n" || window.At(cursor) == "\r" || window.At(cursor) == "\t")) { cursor = cursor + 1; }
                string trueText = "";
                if (cursor + 4 <= total) { trueText = window.Range(cursor, 4); }
                string falseText = "";
                if (cursor + 5 <= total) { falseText = window.Range(cursor, 5); }
                if (trueText != "true" && falseText != "false") { return false; }
            }
            at = ReceiptFind(window, needle, cursor);
        }
        return true;
    }

    static bool ReceiptCheckedTyped(string text)
    {
        return ReceiptBoolTyped(text, "Checked");
    }

    // Reject Unicode escapes in keys rather than accepting a spelling the raw
    // bool/presence guards cannot match. Escapes in prose values remain valid.
    static bool ReceiptKeysUnescaped(string text)
    {
        HCTextWindow window = new HCTextWindow(text);
        int total = window.Length();
        int cursor = 0;
        while (cursor < total)
        {
            if (window.At(cursor) != "\"") { cursor = cursor + 1; continue; }
            cursor = cursor + 1;
            bool unicodeKey = false;
            while (cursor < total && window.At(cursor) != "\"")
            {
                if (window.At(cursor) == "\\")
                {
                    cursor = cursor + 1;
                    if (cursor < total && window.At(cursor) == "u") { unicodeKey = true; }
                }
                cursor = cursor + 1;
            }
            cursor = cursor + 1;
            while (cursor < total && (window.At(cursor) == " " || window.At(cursor) == "\n" || window.At(cursor) == "\r" || window.At(cursor) == "\t")) { cursor = cursor + 1; }
            if (unicodeKey && cursor < total && window.At(cursor) == ":") { return false; }
        }
        return true;
    }

    // Same cohort as the admission summary: admitted ids plus explicit opt-outs.
    // Receipts for slot-refused/unpermitted pairs stay in receipts_checked only.
    static int ReceiptCoveredChecked()
    {
        int checked = 0;
        TStringArray ids = mHCChecked;
        foreach (string pairId : ids)
        {
            if (ReceiptDisabled(pairId) || PairAdmission(pairId) == "") { checked = checked + 1; }
        }
        return checked;
    }

    // Decimal value of width digit characters of an already digit-checked date.
    static int DateNumber(string date, int first, int width)
    {
        string digits = "0123456789";
        int value = 0;
        HCTextWindow window = new HCTextWindow(date);
        int index = first;
        while (index < first + width)
        {
            string letter = window.At(index);
            value = value * 10 + digits.IndexOf(letter);
            index = index + 1;
        }
        return value;
    }

    // ISO date YYYY-MM-DD: digits and dashes, month 01-12, day 1 to the real
    // Gregorian month length (leap years included). The date is operator prose,
    // never evidence, but an impossible day is still a typo worth refusing.
    static bool ValidCheckDate(string date)
    {
        if (date.Length() != 10) { return false; }
        string digits = "0123456789";
        int index = 0;
        while (index < 10)
        {
            string letter = date.Get(index);
            if (index == 4 || index == 7)
            {
                if (letter != "-") { return false; }
            }
            else
            {
                if (digits.IndexOf(letter) < 0) { return false; }
            }
            index = index + 1;
        }
        int year = DateNumber(date, 0, 4);
        int month = DateNumber(date, 5, 2);
        int day = DateNumber(date, 8, 2);
        if (month < 1 || month > 12) { return false; }
        int limit = 31;
        if (month == 4 || month == 6 || month == 9 || month == 11) { limit = 30; }
        if (month == 2)
        {
            limit = 28;
            bool leap = false;
            if (year % 4 == 0) { leap = true; }
            if (year % 100 == 0) { leap = false; }
            if (year % 400 == 0) { leap = true; }
            if (leap) { limit = 29; }
        }
        return day >= 1 && day <= limit;
    }

    // Returns "" and records the checked and disabled pair ids, else a refusal
    // reason with nothing recorded. Unknown or duplicate ids, half-filled rows and
    // a non-bool Checked/Disabled refuse the whole file: a receipt file is
    // all-or-nothing, never partially trusted. The file never admits a pair; it
    // records client checks and opts pairs out (Disabled=true).
    static string ApplyReceipts(string text)
    {
        mHCChecked.Clear();
        mHCDisabled.Clear();
        if (text == "") { return "receipts_unreadable"; }
        if (!ReceiptKeysUnescaped(text)) { return "receipt_key_unicode_escape"; }
        if (!HCJsonFields.Has(text, "SchemaVersion") || !HCJsonFields.Has(text, "Receipts")) { return "receipts_fields_missing"; }
        if (!HCJsonFields.Every(text, "PairId", 3) || !HCJsonFields.Every(text, "Checked", 3)) { return "receipts_fields_missing"; }
        if (!HCJsonFields.Every(text, "CheckDate", 3) || !HCJsonFields.Every(text, "Note", 3)) { return "receipts_fields_missing"; }
        if (!ReceiptCheckedTyped(text)) { return "receipt_checked_type"; }
        if (!ReceiptBoolTyped(text, "Disabled")) { return "receipt_disabled_type"; }
        HCTapedPairReceipts parsed = ParseReceipts(text);
        if (!parsed || !parsed.Receipts) { return "receipts_invalid"; }
        if (parsed.SchemaVersion != 1) { return "receipts_schema"; }
        HCTapedReceiptRows optOuts = ParseOptOuts(text);
        if (!optOuts || !optOuts.Receipts) { return "receipts_invalid"; }
        TStringArray seen = new TStringArray;
        TStringArray known = HCTapedPackCatalog.ReceiptPairIds();
        array<ref HCTapedPairReceipt> rows = parsed.Receipts;
        string refusal = "";
        foreach (HCTapedPairReceipt row : rows)
        {
            if (refusal == "" && (!row || known.Find(row.PairId) < 0)) { refusal = "receipt_unknown_pair"; }
            if (refusal == "" && seen.Find(row.PairId) >= 0) { refusal = "receipt_duplicate_pair"; }
            if (refusal == "" && row.Checked && (row.CheckDate == "" || row.Note == "")) { refusal = "receipt_check_incomplete"; }
            if (refusal == "" && row.CheckDate != "" && !ValidCheckDate(row.CheckDate)) { refusal = "receipt_check_incomplete"; }
            if (refusal == "")
            {
                seen.Insert(row.PairId);
                if (row.Checked) { mHCChecked.Insert(row.PairId); }
            }
        }
        array<ref HCTapedReceiptRow> optRows = optOuts.Receipts;
        foreach (HCTapedReceiptRow optRow : optRows)
        {
            if (refusal == "" && optRow && optRow.Disabled) { mHCDisabled.Insert(optRow.PairId); }
        }
        if (refusal != "")
        {
            mHCChecked.Clear();
            mHCDisabled.Clear();
        }
        return refusal;
    }

    // Startup-only. Skipped while the setting is off (no file read), and while
    // the manifest is not configured (no read limit exists yet). Remembers the
    // refusal so PairAdmission can name it for every pair.
    static string LoadReceipts()
    {
        mHCChecked.Clear();
        mHCDisabled.Clear();
        mHCReceiptReason = "";
        if (!mHCConfigured) { return "pack_mounts_unconfigured"; }
        if (!mHCSettingOn) { return ""; }
        mHCReceiptReason = ApplyReceipts(ReadReceipts());
        return mHCReceiptReason;
    }

    // Mission manifest read: bounded (file is under 16 KiB), "" when unreadable.
    protected static string ReadManifest()
    {
        string text;
        if (!HCGroupIO.Read("$mission:hollow-country/lights/backpack-mounts.json", 16384, text)) { return ""; }
        return text;
    }

    // Native JsonFileLoader zero-fills missing ints, so callers guard presence.
    protected static HCTapedPackManifest ParseManifest(string text)
    {
        HCTapedPackManifest manifest;
        string error;
        if (!JsonFileLoader<HCTapedPackManifest>.LoadData(text, manifest, error)) { return null; }
        return manifest;
    }

    // Returns "" once Configure() accepted the closed manifest defaults, else a
    // refusal reason with nothing configured. The file cannot qualify a pair.
    static string ApplyManifest(string text)
    {
        if (text == "") { return "mount_manifest_unreadable"; }
        if (!HCJsonFields.Has(text, "SchemaVersion") || !HCJsonFields.Has(text, "Qualified") || !HCJsonFields.Has(text, "SettingsContract")) { return "mount_manifest_fields_missing"; }
        if (!HCJsonFields.Check(text, "DefaultCrossSlotLights", 2, false) || !HCJsonFields.Check(text, "DefaultPermittedPairIds", 2, false) || !HCJsonFields.Check(text, "MaxPermittedPairIds", 2, false)) { return "mount_manifest_fields_missing"; }
        if (!HCJsonFields.Check(text, "MaxReceiptBytes", 2, false) || !HCJsonFields.Check(text, "MaxReceiptBytesCeiling", 2, false)) { return "mount_manifest_fields_missing"; }
        HCTapedPackManifest manifest = ParseManifest(text);
        if (!manifest || !manifest.SettingsContract || !manifest.SettingsContract.DefaultPermittedPairIds) { return "mount_manifest_invalid"; }
        if (manifest.SchemaVersion != 1) { return "mount_manifest_schema"; }
        if (manifest.Qualified) { return "mount_manifest_qualified_claim"; }
        HCTapedPackSettingsContract contract = manifest.SettingsContract;
        TStringArray ids = contract.DefaultPermittedPairIds;
        if (contract.MaxPermittedPairIds != 2 || ids.Count() > contract.MaxPermittedPairIds) { return "pack_mount_settings_refused"; }
        if (contract.MaxReceiptBytes <= 0) { return "pack_mount_settings_refused"; }
        // The ceiling is a named manifest field, never a bare number here.
        if (contract.MaxReceiptBytesCeiling <= 0 || contract.MaxReceiptBytes > contract.MaxReceiptBytesCeiling) { return "mount_manifest_receipt_limit"; }
        HCTapedLightMountSettings preferences = new HCTapedLightMountSettings;
        preferences.crossSlotLights = contract.DefaultCrossSlotLights;
        foreach (string pairId : ids) { preferences.permittedPairIds.Insert(pairId); }
        if (!Configure(preferences)) { return "pack_mount_settings_refused"; }
        mHCReceiptMaxBytes = contract.MaxReceiptBytes;
        return "";
    }

    // Loads the manifest once per start; Reset() on stop makes the next start reload.
    static string LoadSettings()
    {
        if (mHCConfigured) { return ""; }
        return ApplyManifest(ReadManifest());
    }

    override void OnStart(HCSettings settings)
    {
        if (mHCStarted) { return; }
        mHCStarted = true;
        string loadReason = LoadSettings();
        string config = "loaded";
        if (loadReason != "") { config = loadReason; }
        // Set after LoadSettings(): Configure() resets this class's state first.
        mHCSettingOn = settings.EnableTapedPackMounts;
        string receiptReason = LoadReceipts();
        HCRefreshWeaponAdmission();
        string receipts = "not_read";
        if (mHCSettingOn && receiptReason == "") { receipts = "ok"; }
        if (receiptReason != "") { receipts = receiptReason; }
        string crossSlot = HCV2Admission.OnOff(CrossSlotEnabled());
        string setting = HCV2Admission.OnOff(mHCSettingOn);
        int pairs = HCTapedPackCatalog.PairIds().Count();
        int weaponPairs = HCTapedLightCatalog.CrossPairIds().Count();
        int receiptPairs = HCTapedPackCatalog.ReceiptPairIds().Count();
        int permitted = mHCPermitted.Count();
        int packChecked = ReceiptPackChecked();
        int weaponChecked = ReceiptWeaponChecked();
        int receiptsChecked = packChecked + weaponChecked;
        int packAdmitted = AdmittedCount();
        int weaponAdmitted = mHCWeaponAdmitted.Count();
        int admitted = packAdmitted + weaponAdmitted;
        int verified = VerifiedCount();
        int disabled = mHCDisabled.Count();
        // off: operator setting off. degraded: the manifest or the receipt file
        // failed (named reason). ready: loaded and admitted unverified; a pair
        // whose native slot is missing is a named one-time refusal below, never
        // a silent skip, and never claimed as admitted.
        string state = "ready";
        string stateReason = "admitted_unverified";
        if (admitted == 0)
        {
            state = "degraded";
            stateReason = FirstAdmissionReason();
            if (stateReason == "") { stateReason = mHCWeaponFirstRefusal; }
            if (stateReason == "") { stateReason = "all_pairs_disabled"; state = "off"; }
        }
        if (!HCTapedLightAdmission.Admitted())
        {
            state = "off";
            stateReason = "taped_light_unavailable";
        }
        if (!mHCSettingOn)
        {
            state = "off";
            stateReason = "setting_off";
        }
        if (receiptReason != "")
        {
            state = "degraded";
            stateReason = receiptReason;
        }
        if (loadReason != "")
        {
            state = "degraded";
            stateReason = loadReason;
        }
        mHCStatus.HCPublish(state, stateReason);
        HCReached.Mark("taped_pack.admission_logged");
        Print(HCV2Admission.Line("TapedPackMounts", mHCSettingOn, "light_mount_two_client_check", verified > 0));
        string line = "[HC TapedPackMounts] pairs=" + pairs.ToString() + " weapon_pairs=" + weaponPairs.ToString() + " receipt_pairs=" + receiptPairs.ToString();
        line = line + " receipts_checked=" + receiptsChecked.ToString() + " pack_checked=" + packChecked.ToString() + " weapon_checked=" + weaponChecked.ToString();
        line = line + " pack_admitted=" + packAdmitted.ToString() + " weapon_admitted=" + weaponAdmitted.ToString() + " admitted=" + admitted.ToString();
        line = line + " setting=" + setting + " reason=" + stateReason;
        Print(line + " receipts=" + receipts + " runtime=PENDING");
        if (state == "ready")
        {
            // One summary line, never one line per pair. Admitted unverified:
            // no native or two-client verdict is recorded for any pair.
            int covered = admitted + disabled;
            int coveredChecked = ReceiptCoveredChecked();
            int unchecked = covered - coveredChecked;
            line = "[HC TapedPackMounts] admission result=admitted unverified pairs=" + covered.ToString() + " unchecked=" + unchecked.ToString();
            Print(line + " checked=" + coveredChecked.ToString() + " disabled=" + disabled.ToString() + " runtime=PENDING");
        }
        // Missing native slots remain visible even when no pair is usable.
        // No repeated tick/config logging; this owner runs once per start.
        if (mHCSettingOn && loadReason == "" && receiptReason == "")
        {
            int packRefused = PackRefusedCount();
            if (packRefused > 0) { Print("[HC TapedPackMounts] pack_pairs_refused count=" + packRefused.ToString() + " reason=" + FirstAdmissionReason() + " runtime=PENDING"); }
            if (mHCWeaponRefused > 0) { Print("[HC TapedPackMounts] weapon_pairs_refused count=" + mHCWeaponRefused.ToString() + " reason=" + mHCWeaponFirstRefusal + " runtime=PENDING"); }
        }
        string mountReason = PairAdmission("tortilla_universal_mount");
        string mountState = "refused";
        if (mountReason == "") { mountState = "admitted_unverified"; }
        string crossReason = PairAdmission("tortilla_universal_cross");
        string crossState = "refused";
        if (crossReason == "") { crossState = "admitted_unverified"; }
        line = "[HC Plan] HC-52 pack_pairs=1 cross_slot=" + crossSlot + " qualified=" + verified.ToString();
        line = line + " permitted=" + permitted.ToString() + " state=" + state + " reason=" + stateReason;
        Print(line + " authored=1 admitted=" + packAdmitted.ToString() + " observed=0 geometry=native_proxy_unverified config=" + config + " runtime=PENDING");
        Print("[HC Plan] HC-52 pair=tortilla_universal_mount state=" + mountState + " reason=" + mountReason + " runtime=PENDING");
        Print("[HC Plan] HC-52 pair=tortilla_universal_cross state=" + crossState + " reason=" + crossReason + " runtime=PENDING");
    }

    override void OnStop()
    {
        Reset();
        mHCStarted = false;
        mHCStatus.HCStop();
    }
}

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        Register(new HCTapedPackMounts());
    }
}
