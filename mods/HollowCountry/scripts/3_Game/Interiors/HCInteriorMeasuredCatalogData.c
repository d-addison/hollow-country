// Import DTOs for interior_catalog.py schema 1. No measurements ship here.
// These flags express operator trust, never native fit or production acceptance.
class HCInteriorMeasuredCatalogProfile
{
    int SchemaVersion = 0;
    bool EnableTrustedExperiment = false;
    bool TrustedExternalValidation = false;
    string WorldName;
    string Build;
    string TrustedAddonSha256;
    string TrustedValidatorSha256;
    ref map<string, string> SourceSha256 = new map<string, string>;
    // Exact trusted reference texts bind bytes without inventing a native SHA API.
    string ExpectedRecordText;
    string ExpectedCandidateText;
    string ExpectedPolicyText;
    string ExpectedReportText;
}

class HCInteriorMeasuredCatalogContext
{
    // The strict reader remaps only the validated Context.World JSON key.
    string WorldName;
    string Build;
    string NativeScriptsSha256;
    string SurveyId;
    ref array<float> BuildingPosition = new array<float>;
    ref array<float> BuildingOrientation = new array<float>;
    ref map<string, string> AssetPboSha256 = new map<string, string>;
    string Operator;
    string MeasuredAt;
    string Method;
    string CoordinateBasis;
    string BuildObservation;
    string AssetObservation;
}

class HCInteriorMeasuredCatalogBox
{
    ref array<float> Min = new array<float>;
    ref array<float> Max = new array<float>;
}

class HCInteriorMeasuredCatalogProp
{
    string Type;
    ref array<float> Position = new array<float>;
    ref array<float> Orientation = new array<float>;
    bool Searchable = false;
    ref array<float> SearchPoint = new array<float>;
}

class HCInteriorMeasuredCatalogMeasuredProp
{
    int Index = -1;
    string Room;
    ref HCInteriorMeasuredCatalogBox Bounds;
    string Observation;
}

class HCInteriorMeasuredCatalogKeepout
{
    string Id;
    string Kind;
    ref HCInteriorMeasuredCatalogBox Bounds;
}

class HCInteriorMeasuredCatalogSurvey
{
    ref HCInteriorMeasuredCatalogBox Bounds;
    ref array<ref HCInteriorMeasuredCatalogMeasuredProp> Props = new array<ref HCInteriorMeasuredCatalogMeasuredProp>;
    string Stairs;
    string DoorObservation;
    string StairObservation;
    float MinimumClearanceMetres = 0;
    ref array<ref HCInteriorMeasuredCatalogKeepout> Keepouts = new array<ref HCInteriorMeasuredCatalogKeepout>;
}

class HCInteriorMeasuredCatalogLayout
{
    string Id;
    string History;
    ref array<ref HCInteriorMeasuredCatalogProp> Props = new array<ref HCInteriorMeasuredCatalogProp>;
    // Required in the full record, forbidden in the exported candidate.
    ref HCInteriorMeasuredCatalogSurvey Survey;
}

class HCInteriorMeasuredCatalogObservation
{
    string Path;
    string Sha256;
    string Kind;
}

class HCInteriorMeasuredCatalogLimits
{
    int Slots = 0;
    int Rag = 0;
    int Battery9V = 0;
}

class HCInteriorMeasuredCatalogGroup
{
    string Id;
    ref array<string> Items = new array<string>;
}

class HCInteriorMeasuredCatalogRule
{
    string LayoutId;
    string Room;
    string History;
    string Risk;
    ref array<string> ItemGroups = new array<string>;
    bool EmptyAllowed = false;
    int MaxItems = 0;
    string SelectionMode;
    string Condition;
    string Storage;
    string Observation;
    string Rationale;
}

class HCInteriorMeasuredCatalogPolicy
{
    ref array<ref HCInteriorMeasuredCatalogGroup> ItemGroups = new array<ref HCInteriorMeasuredCatalogGroup>;
    ref array<ref HCInteriorMeasuredCatalogRule> Rules = new array<ref HCInteriorMeasuredCatalogRule>;
    ref HCInteriorMeasuredCatalogLimits Limits;
}

class HCInteriorMeasuredCatalogRecord
{
    int SchemaVersion = 0;
    bool Synthetic = true;
    ref HCInteriorMeasuredCatalogContext Context;
    ref map<string, string> SourceSha256 = new map<string, string>;
    string BuildingClass;
    int CatalogVersion = 0;
    ref array<ref HCInteriorMeasuredCatalogLayout> Layouts = new array<ref HCInteriorMeasuredCatalogLayout>;
    ref array<ref HCInteriorMeasuredCatalogObservation> Observations = new array<ref HCInteriorMeasuredCatalogObservation>;
    ref HCInteriorMeasuredCatalogPolicy Policy;
}

class HCInteriorMeasuredCatalogCandidate
{
    int SchemaVersion = 0;
    int CatalogVersion = 0;
    string BuildingClass;
    bool Synthetic = true;
    string RecordSha256;
    ref array<ref HCInteriorMeasuredCatalogLayout> Layouts = new array<ref HCInteriorMeasuredCatalogLayout>;
}

class HCInteriorMeasuredCatalogReport
{
    int schema = 0;
    string status;
    bool synthetic = true;
    bool runtime_loader_wired = true;
    bool production_accepted = true;
    string record_sha256;
    ref map<string, string> source_sha256 = new map<string, string>;
    ref array<ref HCInteriorMeasuredCatalogObservation> observations = new array<ref HCInteriorMeasuredCatalogObservation>;
    // Strictly remapped from the report's lowercase world key before parsing.
    string WorldName;
    string build;
    ref map<string, string> candidate_sha256 = new map<string, string>;
    ref array<string> pending = new array<string>;
}

// Private parser cursor. No gameplay state or external object references.
class HCInteriorMeasuredCatalogCursor
{
    string Content;
    int Index = 0;
    int Nodes = 0;
    int WorldKey = -1;
    string NativeText;
    int CopyFrom = 0;
    int Rewrites = 0;
    bool Failed = false;
    // Character reads go through a 1 KB window, as in HCInteriorTemplateCursor.
    protected ref HCTextWindow m_Window;

    void HCSetContent(string content)
    {
        Content = content;
        m_Window = new HCTextWindow(content);
    }

    string HCAt(int index)
    {
        if (!m_Window) { m_Window = new HCTextWindow(Content); }
        return m_Window.At(index);
    }

    string HCRange(int start, int count)
    {
        if (!m_Window) { m_Window = new HCTextWindow(Content); }
        return m_Window.Range(start, count);
    }
}
