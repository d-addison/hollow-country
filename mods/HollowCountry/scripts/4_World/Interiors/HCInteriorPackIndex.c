// HC-24 storage adapter; no placement loop, world scan, save job or gameplay cap changes.
// Integration into the reserved reader/strict parser is pending its owner. Schema-2
// DTOs below are the existing reader interface; schema 3 changes ONLY index storage.
// Installed native scripts-1.30.164289 evidence:
// 1_Core/proto/EnSystem.c:413 OpenFile, :425 ReadFile, :446 CloseFile;
// 3_Game/tools/JsonFileLoader.c:69 LoadData (bounded text, never LoadFile);
// 1_Core/proto/EnScript.c:380 Count, :394 Find, :407 Insert; EnDebug.c:96 Print.
// EnScript.c:902 map.Set, :917 Contains; EnConvert.c:30 int.ToString.
// Hash trust remains docs/INTERIOR_TEMPLATES_CONTRACT.md section 2: offline
// installer SHA-256 + receipt. No inspected native SHA-256 API; NEVER claim runtime
// digest verification. Runtime checks pins/bindings/schema/read sizes only.
class HCInteriorPackRoot
{
    int SchemaVersion;
    string Kind;
    string WorldName;
    string Build;
    string PackId;
    string SourcePin;
    string Frame;
    bool Provisional;
    ref array<ref HCInteriorTemplateFile> IndexFiles = new array<ref HCInteriorTemplateFile>;
}

class HCInteriorPackSource
{
    string Name;
    string Sha256;
}

class HCInteriorPackPage
{
    int SchemaVersion;
    int Chunk;
    ref array<ref HCInteriorPackSource> SourcePins = new array<ref HCInteriorPackSource>;
    ref array<ref HCInteriorTemplateFile> ClassFiles = new array<ref HCInteriorTemplateFile>;
    ref array<ref HCInteriorTemplateFileBinding> TemplateFiles = new array<ref HCInteriorTemplateFileBinding>;
    ref array<ref HCInteriorTemplateFile> FurnishFiles = new array<ref HCInteriorTemplateFile>;
    ref array<ref HCInteriorTemplateFile> GroupFiles = new array<ref HCInteriorTemplateFile>;
}

// Owned by the existing reader. Discard/reset on stop; no static stale admission.
class HCInteriorPackJob
{
    string Root;
    string Reason;
    int NextPage;
    int Files;
    int Bytes;
    bool Started;
    bool Ready;
    ref HCInteriorPackRoot Header;
    ref HCInteriorTemplateIndex Index;
    ref map<string, string> Pins = new map<string, string>;
    ref map<string, string> Schemas = new map<string, string>;
}

class HCInteriorPackIndex
{
    // Storage bounds only: <=16 metadata pages plus the existing <=610 pack files.
    // Native calls/strict parsing of ONE <=32767-byte page cannot be preempted.
    static bool HCFail(HCInteriorPackJob job, string reason)
    {
        if (job.Reason != "")
        {
            return false;
        }
        job.Reason = reason;
        job.Ready = false;
        job.Index = null;
        job.Header = null;
        job.Pins.Clear();
        job.Schemas.Clear();
        Print("[HC Plan] HC-24 pack_chunks=" + job.NextPage.ToString() + " classes=0 state=refused refused=" + reason + " runtime=PENDING");
        return false;
    }

    static void HCReset(HCInteriorPackJob job)
    {
        job.Root = "";
        job.Reason = "";
        job.NextPage = 0;
        job.Files = 0;
        job.Bytes = 0;
        job.Started = false;
        job.Ready = false;
        job.Header = null;
        job.Index = null;
        job.Pins.Clear();
        job.Schemas.Clear();
    }

    // Fixed caller-selected root (profile OR PBO), never per-file fallback or a tree scan.
    static string HCRead(HCInteriorPackJob job, string fileName)
    {
        if (job.Reason != "" || job.Files >= 626)
        {
            HCFail(job, "file_cap");
            return "";
        }
        FileHandle handle = OpenFile(job.Root + fileName, FileMode.READ);
        if (!handle)
        {
            HCFail(job, "file_size_or_read:" + fileName);
            return "";
        }
        string content;
        int count = ReadFile(handle, content, 32768);
        CloseFile(handle);
        if (count < 1 || count > 32767 || count != content.Length())
        {
            HCFail(job, "file_size_or_read:" + fileName);
            return "";
        }
        job.Files = job.Files + 1;
        job.Bytes = job.Bytes + count;
        if (job.Bytes > 20971520)
        {
            HCFail(job, "pack_size");
            return "";
        }
        Print("[HC Plan] HC-24 read=" + fileName + " bytes=" + count.ToString() + " length=" + content.Length().ToString() + " runtime=PENDING");
        return content;
    }

    static bool HCStart(HCInteriorPackJob job, string root)
    {
        // One attempt per lifecycle. Failure never retries on every tick.
        if (job.Started)
        {
            return false;
        }
        job.Started = true;
        job.Root = root;
        if (root == "")
        {
            return HCFail(job, "pack_missing");
        }
        Print("[HC Plan] HC-24 pack_chunks=0 classes=0 state=pending refused=none hash_refused=runtime_sha256_unavailable runtime=PENDING");
        string raw = HCRead(job, "index.json");
        if (raw == "")
        {
            return false;
        }
        string error;
        string legacy = HCInteriorTemplatesStrict.NativeText(raw, "index");
        HCInteriorTemplateIndex index = new HCInteriorTemplateIndex;
        if (legacy != "")
        {
            if (!JsonFileLoader<HCInteriorTemplateIndex>.LoadData(legacy, index, error) || !HCInteriorTemplates.IndexValid(index))
            {
                return HCFail(job, "legacy_index_or_pin");
            }
            job.Index = index;
            HCRegisterChunks(job);
            job.Ready = true;
            return true;
        }
        string content = HCInteriorTemplatesStrict.NativeText(raw, "pack-index");
        HCInteriorPackRoot header = new HCInteriorPackRoot;
        if (content == "" || !JsonFileLoader<HCInteriorPackRoot>.LoadData(content, header, error))
        {
            return HCFail(job, "index_schema_or_strict");
        }
        if (header.SchemaVersion != 3 || !header.IndexFiles || header.IndexFiles.Count() < 1 || header.IndexFiles.Count() > 16)
        {
            return HCFail(job, "index_version_or_page_cap");
        }
        int number = 0;
        foreach (HCInteriorTemplateFile binding : header.IndexFiles)
        {
            if (!binding || binding.FileName != HCInteriorTemplates.Numbered("index-", number, 3) || !HCSearchRules.PinValid(binding.Sha256))
            {
                return HCFail(job, "index_page_binding");
            }
            number = number + 1;
        }
        index.SchemaVersion = 2;
        index.Kind = header.Kind;
        index.WorldName = header.WorldName;
        index.Build = header.Build;
        index.PackId = header.PackId;
        index.SourcePin = header.SourcePin;
        index.Frame = header.Frame;
        index.Provisional = header.Provisional;
        job.Header = header;
        job.Index = index;
        return true;
    }

    static bool HCMerge(HCInteriorPackJob job, HCInteriorPackPage page)
    {
        if (page.SchemaVersion != 3 || page.Chunk != job.NextPage || !page.SourcePins || !page.ClassFiles || !page.TemplateFiles || !page.FurnishFiles || !page.GroupFiles)
        {
            return HCFail(job, "index_page_version_or_order");
        }
        if (page.SourcePins.Count() + page.ClassFiles.Count() + page.TemplateFiles.Count() + page.FurnishFiles.Count() + page.GroupFiles.Count() == 0)
        {
            return HCFail(job, "index_page_empty");
        }
        HCInteriorTemplateIndex index = job.Index;
        if (index.Sources.Count() + page.SourcePins.Count() > 520 || index.ClassFiles.Count() + page.ClassFiles.Count() > 16 || index.TemplateFiles.Count() + page.TemplateFiles.Count() > 512 || index.FurnishFiles.Count() + page.FurnishFiles.Count() > 16 || index.GroupFiles.Count() + page.GroupFiles.Count() > 64)
        {
            return HCFail(job, "index_list_cap");
        }
        foreach (HCInteriorPackSource source : page.SourcePins)
        {
            if (!source || !HCInteriorTemplatesStrict.SourceName(source.Name) || !HCSearchRules.PinValid(source.Sha256) || index.Sources.Contains(source.Name))
            {
                return HCFail(job, "index_source_duplicate_or_pin");
            }
            index.Sources.Set(source.Name, source.Sha256);
        }
        foreach (HCInteriorTemplateFile classFile : page.ClassFiles)
        {
            index.ClassFiles.Insert(classFile);
        }
        foreach (HCInteriorTemplateFileBinding templateFile : page.TemplateFiles)
        {
            index.TemplateFiles.Insert(templateFile);
        }
        foreach (HCInteriorTemplateFile furnishFile : page.FurnishFiles)
        {
            index.FurnishFiles.Insert(furnishFile);
        }
        foreach (HCInteriorTemplateFile groupFile : page.GroupFiles)
        {
            index.GroupFiles.Insert(groupFile);
        }
        return true;
    }

    // 0 metadata complete, 1 yield/more, 2 refused. Retain this job and the existing
    // reader's placement/load cursors. Caller resets HCWorkBudget for each slice.
    // Never publish any class/template until the reserved reader validates ALL leaves.
    static int HCStep(HCInteriorPackJob job, HCWorkBudget budget)
    {
        if (!job.Started || job.Reason != "")
        {
            return 2;
        }
        if (job.Ready)
        {
            return 0;
        }
        if (!budget || !budget.HCContinue())
        {
            return 1;
        }
        HCInteriorTemplateFile binding = job.Header.IndexFiles.Get(job.NextPage);
        string raw = HCRead(job, binding.FileName);
        if (raw == "")
        {
            return 2;
        }
        string content = HCInteriorTemplatesStrict.NativeText(raw, "pack-page");
        string error;
        HCInteriorPackPage page = new HCInteriorPackPage;
        if (content == "" || !JsonFileLoader<HCInteriorPackPage>.LoadData(content, page, error))
        {
            HCFail(job, "index_page_strict");
            return 2;
        }
        if (!HCMerge(job, page))
        {
            return 2;
        }
        job.NextPage = job.NextPage + 1;
        if (job.NextPage < job.Header.IndexFiles.Count())
        {
            return 1;
        }
        if (!HCInteriorTemplates.IndexValid(job.Index))
        {
            HCFail(job, "index_or_pin");
            return 2;
        }
        job.Ready = true;
        HCRegisterChunks(job);
        return 0;
    }

    static void HCRegisterFiles(HCInteriorPackJob job, array<ref HCInteriorTemplateFile> files, string schema)
    {
        foreach (HCInteriorTemplateFile binding : files)
        {
            job.Pins.Set(binding.FileName, binding.Sha256);
            job.Schemas.Set(binding.FileName, schema);
        }
    }

    static void HCRegisterChunks(HCInteriorPackJob job)
    {
        HCRegisterFiles(job, job.Index.ClassFiles, "classes");
        HCRegisterFiles(job, job.Index.FurnishFiles, "furnish");
        HCRegisterFiles(job, job.Index.GroupFiles, "groups");
        foreach (HCInteriorTemplateFileBinding binding : job.Index.TemplateFiles)
        {
            job.Pins.Set(binding.FileName, binding.Sha256);
            job.Schemas.Set(binding.FileName, "template");
        }
    }

    // Called by the reserved reader with a binding from the completed Index, keeping
    // the existing schema-2 per-chunk validation and placement interfaces unchanged.
    static string HCReadChunk(HCInteriorPackJob job, string fileName, string schema, string expectedPin)
    {
        if (!job.Ready || !HCSearchRules.PinValid(expectedPin) || job.Pins.Get(fileName) != expectedPin || job.Schemas.Get(fileName) != schema)
        {
            HCFail(job, "chunk_before_index_or_pin");
            return "";
        }
        string raw = HCRead(job, fileName);
        if (raw == "")
        {
            return "";
        }
        string content = HCInteriorTemplatesStrict.NativeText(raw, schema);
        if (content == "")
        {
            HCFail(job, "chunk_strict:" + fileName);
        }
        return content;
    }

    // Only the reserved owner calls this after its unchanged full-pack checks.
    // Counts prove admission only, never physical fit. 'off' is the caller's off path.
    static void HCReceipt(HCInteriorPackJob job, int classes, bool enabled)
    {
        string state = "off";
        string refused = "none";
        if (enabled)
        {
            state = "pending";
            if (job.Ready && classes >= 1 && classes <= 2048)
            {
                state = "ready";
            }
            if (job.Reason != "")
            {
                state = "refused";
                refused = job.Reason;
            }
        }
        Print("[HC Plan] HC-24 pack_chunks=" + job.NextPage.ToString() + " classes=" + classes.ToString() + " state=" + state + " refused=" + refused + " hash=offline-receipt runtime=PENDING");
    }
}
