// Flat schema-v2 DTOs. Coordinates are model-frame arrays, never world guesses.
// Slot JSON keys are span-remapped to SlotId and File keys to FileName: Slot is a native type name and
// a loaded dependency declares a type File.
class HCInteriorTemplateCursor
{
    string Content;
    int Index;
    int Nodes;
    bool Failed;
    int CopyFrom;
    string NativeText;
}

class HCInteriorTemplateFile
{
    string FileName;
    string Sha256;
}

class HCInteriorTemplateFileBinding
{
    string FileName;
    string BuildingClass;
    string Sha256;
}

class HCInteriorTemplateIndex
{
    int SchemaVersion;
    string Kind;
    string WorldName;
    string Build;
    string PackId;
    string SourcePin;
    string Frame;
    bool Provisional;
    ref map<string, string> Sources = new map<string, string>;
    ref array<ref HCInteriorTemplateFile> ClassFiles = new array<ref HCInteriorTemplateFile>;
    ref array<ref HCInteriorTemplateFileBinding> TemplateFiles = new array<ref HCInteriorTemplateFileBinding>;
    ref array<ref HCInteriorTemplateFile> FurnishFiles = new array<ref HCInteriorTemplateFile>;
    ref array<ref HCInteriorTemplateFile> GroupFiles = new array<ref HCInteriorTemplateFile>;
}

class HCInteriorTemplateClassRow
{
    string BuildingClass;
    string Rooms;
    string Furniture;
    string Search;
}

class HCInteriorTemplateClasses
{
    int SchemaVersion;
    int Chunk;
    ref array<ref HCInteriorTemplateClassRow> Rows = new array<ref HCInteriorTemplateClassRow>;
}

class HCInteriorTemplateBox
{
    ref array<float> Min = new array<float>;
    ref array<float> Max = new array<float>;
}

class HCInteriorTemplateEvidence
{
    string Kind;
    string RunId;
    string Sha256;
}

class HCInteriorTemplateRoom
{
    int Id;
    string Label;
    ref array<float> Min = new array<float>;
    ref array<float> Max = new array<float>;
    ref array<float> Anchor = new array<float>;
    float FloorY;
    int Cells;
}

class HCInteriorTemplateKeepOut
{
    string Kind;
    int Index;
    ref array<float> Min = new array<float>;
    ref array<float> Max = new array<float>;
}

class HCInteriorTemplatePropSlot
{
    int Id;
    int Room;
    string Type;
    ref array<float> Position = new array<float>;
    ref array<float> Orientation = new array<float>;
    ref HCInteriorTemplateBox Bounds;
    ref array<string> History = new array<string>;
}

class HCInteriorTemplateSearchSite
{
    int Id;
    int Room;
    ref array<float> Center = new array<float>;
    float Radius;
    string Source;
    ref array<int> Points = new array<int>;
    ref array<string> Groups = new array<string>;
}

class HCInteriorTemplate
{
    int SchemaVersion;
    string BuildingClass;
    string TemplateId;
    ref HCInteriorTemplateBox Box;
    ref array<ref HCInteriorTemplateEvidence> Evidence = new array<ref HCInteriorTemplateEvidence>;
    ref array<ref HCInteriorTemplateRoom> Rooms = new array<ref HCInteriorTemplateRoom>;
    ref array<ref HCInteriorTemplateKeepOut> KeepOuts = new array<ref HCInteriorTemplateKeepOut>;
    ref array<ref HCInteriorTemplatePropSlot> PropSlots = new array<ref HCInteriorTemplatePropSlot>;
    ref array<ref HCInteriorTemplateSearchSite> SearchSites = new array<ref HCInteriorTemplateSearchSite>;
}

class HCInteriorSearchGroup
{
    string Id;
    ref array<string> Usages = new array<string>;
    string Container;
    ref array<string> Categories = new array<string>;
    ref array<string> Tags = new array<string>;
    ref array<string> Items = new array<string>;
}

class HCInteriorTemplateGroups
{
    int SchemaVersion;
    int Chunk;
    ref array<ref HCInteriorSearchGroup> Groups = new array<ref HCInteriorSearchGroup>;
}

class HCInteriorFurnishRow
{
    int SlotId;
    string BuildingClass;
    ref array<float> Position = new array<float>;
    float Yaw;
    ref array<int> Props = new array<int>;
    string History;
}

class HCInteriorTemplateFurnish
{
    int SchemaVersion;
    int Chunk;
    ref array<ref HCInteriorFurnishRow> Rows = new array<ref HCInteriorFurnishRow>;
}

// Transient native query snapshot, never serialized or published as template data.
class HCInteriorResolveEntry
{
    vector Position;
    int QuerySize;
    ref array<Object> Objects = new array<Object>;
}
