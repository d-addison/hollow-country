// W6 #123. Native scripts-1.30.164289: 1_Core/proto/EnScript.c:380,407
// Count/Insert, :887,897 map GetElement/GetKey; EnMath3D.c:18 Vector;
// EnString.c:113,199 Substring/Length; EnConvert.c:30 int.ToString; EnDebug.c:96 Print. HCDebugSnapshot owns capture.
// One completed request: <=1024 points +128 routes*64 vertices examined;
// <=512 total vertices/MAX_WIRE_LAYERS (24) layers exported, text already bounded by shared API.
// w28-debugmap #193: the 512-mark budget is shared fairly (water-fill: every sent
// layer gets budget/layers first, leftovers go to layers that still have rows),
// so a late layer (camps, scenes, lead-ledger) is not starved by ai-units. Per-layer
// sent/total ride in the bounded Notice as `layers=name:sent/total,...` (the client
// replaces a snapshot reply's Lines, so Notice is the carried channel). Caps unchanged.
// w29-debugmap #194: allowance a layer cannot use (a route that does not fit whole
// inside its share) is redistributed by a second water-fill to layers that still
// have unsent points; the 512 mark cap and every layer's own row count still bound
// the result. The named layer cap grows 16 -> 24 for the w29 layers. A layer's
// `unplaced` count (rows with no drawable position, kept out of total) rides in
// the Notice as `unplaced=layer:n,...` only when nonzero.
// w31-p3admin3 #196: the Notice is built head and tail first (the fixed text is never
// clipped); `layers=` and `unplaced=` entries are added only while they fit inside
// NOTICE_BYTES, cut on entry boundaries, and a cut list ends with an explicit `+N more`.
// `unplaced=` keeps a reserved share (1/NOTICE_UNPLACED_SHARE of the room) so a crowded
// layers= list cannot hide it. Same caps: 1024 Notice bytes, 512 marks, 24 layers.
class HCAdminSnapshotWire
{
    static const int MAX_WIRE_LAYERS = 24;
    static const int NOTICE_BYTES = 1024;
    static const int NOTICE_UNPLACED_SHARE = 4;

    // Comma-joined entries that fit in `room` characters. A cut list ends in `+N more`.
    // Check the complete list first: reserving a marker must not clip a list that
    // fits without one. Otherwise reserve the exact omitted-count suffix per entry.
    // Tiny rooms retain the existing identifiable first-entry preview.
    protected static string HCFitEntries(array<string> entries, int room)
    {
        if (room < 1 || !entries || entries.Count() < 1) { return ""; }
        string complete = "";
        for (int completeIndex = 0; completeIndex < entries.Count(); completeIndex++)
        {
            if (completeIndex > 0) { complete += ","; }
            complete += entries[completeIndex];
        }
        if (complete.Length() <= room) { return complete; }
        string joined = "";
        int kept = 0;
        for (int entryIndex = 0; entryIndex < entries.Count(); entryIndex++)
        {
            string entry = entries[entryIndex];
            int added = joined.Length() + entry.Length();
            if (kept > 0) { added = added + 1; }
            if (entryIndex < entries.Count() - 1) { added = added + 7 + (entries.Count() - entryIndex - 1).ToString().Length(); }
            if (added > room) { break; }
            if (kept > 0) { joined += ","; }
            joined += entry;
            kept++;
        }
        // Tiny-room fallback: identify the first layer even when no whole entry
        // fits. A tilde marks clipping; the suffix counts other omitted entries.
        // If even that suffix would consume the preview, retain only the preview.
        if (kept == 0)
        {
            string suffix = "";
            if (entries.Count() > 1) { suffix = ",+" + (entries.Count() - 1).ToString() + " more"; }
            int previewRoom = room - suffix.Length();
            if (previewRoom < 2) { suffix = ""; previewRoom = room; }
            string preview = entries[0];
            if (preview.Length() > previewRoom)
            {
                if (previewRoom == 1) { preview = preview.Substring(0, 1); }
                else { preview = preview.Substring(0, previewRoom - 1) + "~"; }
            }
            return preview + suffix;
        }
        if (kept < entries.Count())
        {
            if (kept > 0) { joined += ","; }
            joined += "+" + (entries.Count() - kept).ToString() + " more";
        }
        return joined;
    }

    protected static void HCMark(HCAdminReply reply, array<string> layers, string layer, vector pos, string label, string detail, int route)
    {
        if (reply.Marks.Count() >= 512) { return; }
        if (layers.Find(layer) < 0)
        {
            if (layers.Count() >= HCAdminSnapshotWire.MAX_WIRE_LAYERS) { return; }
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

    // Index of the layer in the sent list; registers it (<=MAX_WIRE_LAYERS) when new, -1 when full.
    protected static int HCSlot(array<string> layers, array<int> demand, string layer)
    {
        int found = layers.Find(layer);
        if (found >= 0) { return found; }
        if (layers.Count() >= HCAdminSnapshotWire.MAX_WIRE_LAYERS) { return -1; }
        layers.Insert(layer);
        demand.Insert(0);
        return layers.Count() - 1;
    }

    // Water-fill the budget across layers: each unmet layer takes an equal share per
    // round, capped by its own demand; <=MAX_WIRE_LAYERS layers so the rounds terminate early.
    static void HCAllocate(array<int> demand, int budget, array<int> allowance)
    {
        int count = demand.Count();
        allowance.Clear();
        for (int init = 0; init < count; init++) { allowance.Insert(0); }
        int remaining = budget;
        for (int fillRound = 0; fillRound < 40; fillRound++)
        {
            if (remaining < 1) { break; }
            int unmet = 0;
            for (int scan = 0; scan < count; scan++)
            {
                if (allowance[scan] < demand[scan]) { unmet++; }
            }
            if (unmet < 1) { break; }
            int share = remaining / unmet;
            if (share < 1) { share = 1; }
            for (int fill = 0; fill < count; fill++)
            {
                int gap = demand[fill] - allowance[fill];
                if (gap < 1 || remaining < 1) { continue; }
                int take = gap;
                if (take > share) { take = share; }
                if (take > remaining) { take = remaining; }
                allowance[fill] = allowance[fill] + take;
                remaining = remaining - take;
            }
        }
    }

    // Marks a layer would send inside `room`: points first, then whole routes only.
    protected static int HCFitted(HCDebugDocument document, string layer, int pointCount, int room)
    {
        int fitted = pointCount;
        if (fitted > room) { fitted = room; }
        for (int fitRoute = 0; fitRoute < document.routes.Count(); fitRoute++)
        {
            HCDebugRoute candidate = document.routes[fitRoute];
            if (candidate.layer != layer) { continue; }
            if (fitted + candidate.points.Count() > room) { continue; }
            fitted += candidate.points.Count();
        }
        return fitted;
    }

    static HCAdminReply HCBuild(HCDebugSnapshot capture, int ticket)
    {
        HCAdminReply reply = new HCAdminReply;
        reply.Ticket = ticket;
        reply.Snapshot = true;
        array<string> layers = new array<string>;
        array<string> unsent = new array<string>;
        array<int> demand = new array<int>;
        array<int> pointDemand = new array<int>;
        array<int> allowance = new array<int>;
        HCDebugDocument document = capture.HCDocument();
        int total = 0;
        // Pass 1: register <=MAX_WIRE_LAYERS layers in document order and count each one's demand.
        for (int layerIndex = 0; layerIndex < document.layers.Count(); layerIndex++)
        {
            string layer = document.layers.GetKey(layerIndex);
            int pointCount = document.layers.GetElement(layerIndex).Count();
            total += pointCount;
            int layerSlot = HCSlot(layers, demand, layer);
            while (pointDemand.Count() < demand.Count()) { pointDemand.Insert(0); }
            if (layerSlot < 0)
            {
                if (unsent.Find(layer) < 0) { unsent.Insert(layer); }
                continue;
            }
            demand[layerSlot] = demand[layerSlot] + pointCount;
            pointDemand[layerSlot] = pointDemand[layerSlot] + pointCount;
        }
        for (int demandRoute = 0; demandRoute < document.routes.Count(); demandRoute++)
        {
            HCDebugRoute counted = document.routes[demandRoute];
            int vertexCount = counted.points.Count();
            total += vertexCount;
            int routeSlot = HCSlot(layers, demand, counted.layer);
            while (pointDemand.Count() < demand.Count()) { pointDemand.Insert(0); }
            if (routeSlot < 0)
            {
                if (unsent.Find(counted.layer) < 0) { unsent.Insert(counted.layer); }
                continue;
            }
            demand[routeSlot] = demand[routeSlot] + vertexCount;
        }
        HCAllocate(demand, 512, allowance);
        // Redistribute what a layer cannot use (an unfittable route) to layers whose
        // points were still unsent; they never receive more than their own rows.
        int leftover = 512;
        array<int> wanted = new array<int>;
        for (int planSlot = 0; planSlot < layers.Count(); planSlot++)
        {
            leftover = leftover - HCFitted(document, layers[planSlot], pointDemand[planSlot], allowance[planSlot]);
            int unsentPoints = pointDemand[planSlot] - allowance[planSlot];
            if (unsentPoints < 0) { unsentPoints = 0; }
            wanted.Insert(unsentPoints);
        }
        if (leftover > 0)
        {
            array<int> extra = new array<int>;
            HCAllocate(wanted, leftover, extra);
            for (int extraSlot = 0; extraSlot < layers.Count(); extraSlot++) { allowance[extraSlot] = allowance[extraSlot] + extra[extraSlot]; }
        }
        // Pass 2: fill each layer inside its allowance (points first, then whole routes).
        array<int> sentCount = new array<int>;
        for (int emitSlot = 0; emitSlot < layers.Count(); emitSlot++)
        {
            string emitLayer = layers[emitSlot];
            int room = allowance[emitSlot];
            int sent = 0;
            array<ref HCDebugPoint> points = document.layers.Get(emitLayer);
            if (points)
            {
                int pointLimit = Math.Min(points.Count(), room);
                for (int pointIndex = 0; pointIndex < pointLimit; pointIndex++)
                {
                    HCDebugPoint point = points[pointIndex];
                    HCMark(reply, layers, emitLayer, Vector(point.x, 0, point.z), point.label, point.detail, 0);
                    sent++;
                }
            }
            for (int routeIndex = 0; routeIndex < document.routes.Count(); routeIndex++)
            {
                HCDebugRoute route = document.routes[routeIndex];
                if (route.layer != emitLayer) { continue; }
                // Keep a route whole: never export a misleading partial polyline.
                if (sent + route.points.Count() > room) { continue; }
                for (int vertexIndex = 0; vertexIndex < route.points.Count(); vertexIndex++)
                {
                    array<float> pair = route.points[vertexIndex];
                    HCMark(reply, layers, emitLayer, Vector(pair[0], 0, pair[1]), route.label, "Contributor route; not a surveyed path", routeIndex + 1);
                    sent++;
                }
            }
            sentCount.Insert(sent);
        }
        int operationalLoss = document.operationalTruncated + document.truncated;
        HCOperationalContributors.HCAppend(reply, document.operational, operationalLoss);
        int dropped = total - reply.Marks.Count();
        int rowLoss = Math.Max(0, document.operational.Count() - 63);
        int refused = document.truncated + document.operationalTruncated + rowLoss;
        // Per-layer sent/total: total adds the contributor-side loss from layerStats.
        array<string> statEntries = new array<string>;
        for (int statSlot = 0; statSlot < layers.Count(); statSlot++)
        {
            int layerTotal = demand[statSlot];
            for (int statIndex = 0; statIndex < document.layerStats.Count(); statIndex++)
            {
                HCDebugLayerStat stat = document.layerStats[statIndex];
                if (stat.layer == layers[statSlot] && stat.total > stat.shown) { layerTotal += stat.total - stat.shown; }
            }
            statEntries.Insert(HCDebugSnapshot.HCText(layers[statSlot], 24) + ":" + sentCount[statSlot].ToString() + "/" + layerTotal.ToString());
        }
        array<string> unplacedEntries = new array<string>;
        for (int unplacedIndex = 0; unplacedIndex < document.layerStats.Count(); unplacedIndex++)
        {
            HCDebugLayerStat unplacedStat = document.layerStats[unplacedIndex];
            if (unplacedStat.unplaced < 1) { continue; }
            unplacedEntries.Insert(HCDebugSnapshot.HCText(unplacedStat.layer, 24) + ":" + unplacedStat.unplaced.ToString());
        }
        // Fixed head and tail first; the list entries share what is left.
        string head = "Snapshot row/contributor losses=" + refused.ToString() + "; runtime=PENDING; vertices=" + reply.Marks.Count().ToString() + " dropped=" + dropped.ToString();
        string middle = "; layers_unsent=" + unsent.Count().ToString();
        string tail = "; captured over several ticks; expires in 60s";
        string layersLabel = "; layers=";
        string unplacedLabel = "; unplaced=";
        int noticeRoom = HCAdminSnapshotWire.NOTICE_BYTES - head.Length() - middle.Length() - tail.Length() - layersLabel.Length();
        int unplacedRoom = 0;
        if (unplacedEntries.Count() > 0)
        {
            noticeRoom = noticeRoom - unplacedLabel.Length();
            unplacedRoom = noticeRoom / HCAdminSnapshotWire.NOTICE_UNPLACED_SHARE;
        }
        string layerText = HCFitEntries(statEntries, noticeRoom - unplacedRoom);
        string notice = head + layersLabel + layerText + middle;
        if (unplacedEntries.Count() > 0)
        {
            notice += unplacedLabel + HCFitEntries(unplacedEntries, noticeRoom - layerText.Length());
        }
        notice += tail;
        reply.Notice = HCDebugSnapshot.HCText(notice, HCAdminSnapshotWire.NOTICE_BYTES);
        Print("[HC Admin] cmd=snapshot result=ok reason=delivered vertices=" + reply.Marks.Count().ToString() + " truncated=" + dropped.ToString() + " runtime=PENDING");
        return reply;
    }
}
