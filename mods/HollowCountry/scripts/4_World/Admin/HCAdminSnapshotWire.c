// W6 #123. Native scripts-1.30.164289: 1_Core/proto/EnScript.c:380,407
// Count/Insert, :887,897 map GetElement/GetKey; EnMath3D.c:18 Vector;
// EnConvert.c:30 int.ToString; EnDebug.c:96 Print. HCDebugSnapshot owns capture.
// One completed request: <=1024 points +128 routes*64 vertices examined;
// <=512 total vertices/16 layers exported, text already bounded by shared API.
class HCAdminSnapshotWire
{
    protected static void HCMark(HCAdminReply reply, array<string> layers, string layer, vector pos, string label, string detail, int route)
    {
        if (reply.Marks.Count() >= 512) { return; }
        if (layers.Find(layer) < 0)
        {
            if (layers.Count() >= 16) { return; }
            layers.Insert(layer);
        }
        HCAdminMark mark = new HCAdminMark;
        mark.Layer = layer;
        mark.Position = pos;
        mark.Label = label;
        mark.Detail = detail;
        mark.Route = route;
        reply.Marks.Insert(mark);
    }

    static HCAdminReply HCBuild(HCDebugSnapshot capture, int ticket)
    {
        HCAdminReply reply = new HCAdminReply;
        reply.Ticket = ticket;
        reply.Snapshot = true;
        array<string> layers = new array<string>;
        HCDebugDocument document = capture.HCDocument();
        int total = 0;
        for (int layerIndex = 0; layerIndex < document.layers.Count(); layerIndex++)
        {
            string layer = document.layers.GetKey(layerIndex);
            array<ref HCDebugPoint> points = document.layers.GetElement(layerIndex);
            for (int pointIndex = 0; pointIndex < points.Count(); pointIndex++)
            {
                HCDebugPoint point = points[pointIndex];
                total++;
                HCMark(reply, layers, layer, Vector(point.x, 0, point.z), point.label, point.detail, 0);
            }
        }
        for (int routeIndex = 0; routeIndex < document.routes.Count(); routeIndex++)
        {
            HCDebugRoute route = document.routes[routeIndex];
            total += route.points.Count();
            // Keep a route whole: never export a misleading partial polyline.
            if (reply.Marks.Count() + route.points.Count() > 512) { continue; }
            for (int vertexIndex = 0; vertexIndex < route.points.Count(); vertexIndex++)
            {
                array<float> pair = route.points[vertexIndex];
                HCMark(reply, layers, route.layer, Vector(pair[0], 0, pair[1]), route.label, "Contributor route; not a surveyed path", routeIndex + 1);
            }
        }
        int operationalLoss = document.operationalTruncated + document.truncated;
        HCOperationalContributors.HCAppend(reply, document.operational, operationalLoss);
        int dropped = total - reply.Marks.Count();
        int rowLoss = Math.Max(0, document.operational.Count() - 63);
        int refused = document.truncated + document.operationalTruncated + rowLoss;
        reply.Notice = "Snapshot row/contributor losses=" + refused.ToString() + "; runtime=PENDING; vertices=" + reply.Marks.Count().ToString() + " dropped=" + dropped.ToString() + "; captured over several ticks; expires in 60s";
        Print("[HC Admin] cmd=snapshot result=ok reason=delivered vertices=" + reply.Marks.Count().ToString() + " truncated=" + dropped.ToString());
        return reply;
    }
}
