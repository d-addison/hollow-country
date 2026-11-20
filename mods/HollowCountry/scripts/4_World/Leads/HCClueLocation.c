// Optional fields extend only this module's persisted lead DTO. Old JSON rows
// have an empty LocationHint and retain their exact original text/identity.
class HCClueLead : HCWorldLead
{
    string LocationHint;
}

class HCClueLocalities
{
    int SchemaVersion;
    ref array<ref HCWorldPlace> Localities;
}

// Compact, pre-indexed named locality anchors, loaded once at module start.
// No world/object/player scan. At most 128 comparisons per new clue, never
// during rendering, read-paper actions or persistence validation.
// Native scripts-1.30.164289/1_Core/proto/EnMath.c:16,305,399,413
// (RAD2DEG/Sqrt/Atan2/Round); JSON/IO use the existing bounded shared helpers.
class HCClueLocation
{
    protected static ref array<ref HCWorldPlace> s_Localities;

    static void HCLoad()
    {
        s_Localities = new array<ref HCWorldPlace>;
        string text;
        string error;
        HCClueLocalities decoded;
        if (!HCGroupIO.Read("$mission:hollow-country/leads/localities.json", 32768, text) || !JsonFileLoader<HCClueLocalities>.LoadData(text, decoded, error) || !decoded) { return; }
        if (decoded.SchemaVersion != 1 || !decoded.Localities || decoded.Localities.Count() > 128) { return; }
        foreach (HCWorldPlace locality : decoded.Localities)
        {
            if (!locality || !HCWorldLimits.Token(locality.Id) || locality.Name == "" || locality.Name.Length() > 64 || !HCWorldLimits.Position(locality.Position)) { continue; }
            s_Localities.Insert(locality);
        }
    }

    static HCWorldPlace HCNearest(vector position)
    {
        if (!s_Localities) { return null; }
        HCWorldPlace nearest;
        float best = 1000000000;
        foreach (HCWorldPlace locality : s_Localities)
        {
            vector anchor = locality.Position;
            float dx = position[0] - anchor[0];
            float dz = position[2] - anchor[2];
            float squared = dx * dx + dz * dz;
            if (squared < best) { best = squared; nearest = locality; }
        }
        return nearest;
    }

    static string HCDirection(float dx, float dz)
    {
        float bearing = Math.Atan2(dx, dz) * Math.RAD2DEG;
        if (bearing < 0) { bearing += 360; }
        if (bearing < 22.5 || bearing >= 337.5) { return "north"; }
        if (bearing < 67.5) { return "northeast"; }
        if (bearing < 112.5) { return "east"; }
        if (bearing < 157.5) { return "southeast"; }
        if (bearing < 202.5) { return "south"; }
        if (bearing < 247.5) { return "southwest"; }
        if (bearing < 292.5) { return "west"; }
        return "northwest";
    }

    static string HCRange(float dx, float dz)
    {
        float metres = Math.Sqrt(dx * dx + dz * dz);
        int rounded = Math.Round(metres / 100) * 100;
        if (rounded < 100) { rounded = 100; }
        return "about " + rounded.ToString() + " m " + HCDirection(dx, dz);
    }

    static void HCResolve(HCClueLead lead, vector origin, bool fromNote)
    {
        if (!lead || lead.LocationHint != "") { return; }
        HCWorldPlace target = HCLeadPolicy.Place(lead.TargetPlaceId);
        if (!target) { return; }
        vector targetPosition = target.Position;
        HCWorldPlace nearest = HCNearest(targetPosition);
        // The fallback still names the authored place; missing optional text
        // data never rejects an otherwise valid existing lead store.
        string hint = "Look around " + target.Name + ".";
        if (nearest)
        {
            vector anchor = nearest.Position;
            float dx = targetPosition[0] - anchor[0];
            float dz = targetPosition[2] - anchor[2];
            hint = "Look around " + nearest.Name + ".";
            if (dx * dx + dz * dz >= 90000) { hint = "The reported area is " + HCRange(dx, dz) + " of " + nearest.Name + "."; }
        }
        if (fromNote)
        {
            float noteDx = targetPosition[0] - origin[0];
            float noteDz = targetPosition[2] - origin[2];
            if (noteDx * noteDx + noteDz * noteDz < 90000) { hint += " Close to where this note was left."; }
            else { hint += " From where this note was left: " + HCRange(noteDx, noteDz) + "."; }
        }
        lead.LocationHint = hint;
    }
}
