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

    // Retained build cursors. Each step is one layer/route/mark; the final
    // notice is bounded by 24 wire layers and 16 layer stats, as before.
    protected ref HCAdminReply reply;
    protected ref HCDebugDocument document;
    protected ref array<string> layers = new array<string>;
    protected ref array<string> unsent = new array<string>;
    protected ref map<string, bool> unsentSeen = new map<string, bool>;
    protected ref array<int> demand = new array<int>;
    protected ref array<int> pointDemand = new array<int>;
    protected ref array<int> allowance = new array<int>;
    protected ref array<int> wanted = new array<int>;
    protected ref array<int> sentCount = new array<int>;
    protected ref HCWorkBudget m_Budget = new HCWorkBudget;
    protected int total;
    protected int leftover = 512;
    protected int m_Phase;
    protected int m_Index;
    protected int m_Slot;
    protected int m_Point;
    protected int m_Route;
    protected int m_Vertex;
    protected int m_Sent;

    void HCAdminSnapshotWire(HCDebugSnapshot capture, int ticket)
    {
        reply = new HCAdminReply;
        reply.Ticket = ticket;
        reply.Snapshot = true;
        document = capture.HCDocument();
    }

    HCAdminReply HCReply() { return reply; }

    bool HCBuildNext()
    {
        // 16 marks per tick limits allocations/string copies; route vertices
        // also yield individually. Leave headroom for dispatch and lootmap.
        m_Budget.HCReset(16, HCPerfConfig.HCGet().SliceMs);
        while (m_Phase < 5 && m_Budget.HCContinue()) { HCBuildStep(); }
        return m_Phase == 5;
    }

    protected void HCBuildStep()
    {
        if (m_Phase == 0)
        {
            if (m_Index >= document.layers.Count()) { m_Phase = 1; m_Index = 0; return; }
            string layer = document.layers.GetKey(m_Index);
            int pointCount = document.layers.GetElement(m_Index).Count();
            m_Index++;
            total += pointCount;
            int layerSlot = HCSlot(layers, demand, layer);
            while (pointDemand.Count() < demand.Count()) { pointDemand.Insert(0); }
            if (layerSlot < 0)
            {
                if (!unsentSeen.Contains(layer)) { unsentSeen.Insert(layer, true); unsent.Insert(layer); }
                return;
            }
            demand[layerSlot] = demand[layerSlot] + pointCount;
            pointDemand[layerSlot] = pointDemand[layerSlot] + pointCount;
            return;
        }
        if (m_Phase == 1)
        {
            if (m_Index >= document.routes.Count())
            {
                HCAllocate(demand, 512, allowance);
                m_Phase = 2; m_Index = 0; return;
            }
            HCDebugRoute counted = document.routes[m_Index];
            m_Index++;
            int vertexCount = counted.points.Count();
            total += vertexCount;
            int routeSlot = HCSlot(layers, demand, counted.layer);
            while (pointDemand.Count() < demand.Count()) { pointDemand.Insert(0); }
            if (routeSlot < 0)
            {
                if (!unsentSeen.Contains(counted.layer)) { unsentSeen.Insert(counted.layer, true); unsent.Insert(counted.layer); }
                return;
            }
            demand[routeSlot] = demand[routeSlot] + vertexCount;
            return;
        }
        if (m_Phase == 2)
        {
            if (m_Index < layers.Count())
            {
                leftover = leftover - HCFitted(document, layers[m_Index], pointDemand[m_Index], allowance[m_Index]);
                wanted.Insert(Math.Max(0, pointDemand[m_Index] - allowance[m_Index]));
                m_Index++;
                return;
            }
            if (leftover > 0)
            {
                array<int> extra = new array<int>;
                HCAllocate(wanted, leftover, extra);
                for (int extraSlot = 0; extraSlot < layers.Count(); extraSlot++) { allowance[extraSlot] = allowance[extraSlot] + extra[extraSlot]; }
            }
            m_Phase = 3;
            return;
        }
        if (m_Phase == 3)
        {
            if (m_Slot >= layers.Count()) { m_Phase = 4; return; }
            string emitLayer = layers[m_Slot];
            int room = allowance[m_Slot];
            array<ref HCDebugPoint> points = document.layers.Get(emitLayer);
            if (points && m_Point < Math.Min(points.Count(), room))
            {
                HCDebugPoint point = points[m_Point];
                HCMark(reply, layers, emitLayer, Vector(point.x, 0, point.z), point.label, point.detail, 0);
                m_Point++; m_Sent++;
                return;
            }
            if (m_Route < document.routes.Count())
            {
                HCDebugRoute route = document.routes[m_Route];
                // Test room once, before emitting the first vertex of a route.
                if (route.layer != emitLayer || (m_Vertex == 0 && m_Sent + route.points.Count() > room)) { m_Route++; return; }
                if (m_Vertex < route.points.Count())
                {
                    array<float> pair = route.points[m_Vertex];
                    HCMark(reply, layers, emitLayer, Vector(pair[0], 0, pair[1]), route.label, "Contributor route; not a surveyed path", m_Route + 1);
                    m_Vertex++; m_Sent++;
                    return;
                }
                m_Route++; m_Vertex = 0;
                return;
            }
            sentCount.Insert(m_Sent);
            m_Slot++; m_Point = 0; m_Route = 0; m_Vertex = 0; m_Sent = 0;
            return;
        }
        HCFinishNotice();
    }

    protected void HCFinishNotice()
    {
        int operationalLoss = document.operationalTruncated + document.truncated;
        HCOperationalContributors.HCAppend(reply, document.operational, operationalLoss);
        int dropped = total - reply.Marks.Count();
        int rowLoss = Math.Max(0, document.operational.Count() - 63);
        int refused = document.truncated + document.operationalTruncated + rowLoss;
        // Per-layer sent/total: total adds the contributor-side loss from layerStats.
        array<string> statEntries = new array<string>;
        // One pass over layerStats builds each layer's unshown total; the slot loop reads it.
        map<string, int> statExtra = new map<string, int>;
        for (int statIndex = 0; statIndex < document.layerStats.Count(); statIndex++)
        {
            HCDebugLayerStat stat = document.layerStats[statIndex];
            if (stat.total <= stat.shown) { continue; }
            int priorExtra = 0;
            if (statExtra.Contains(stat.layer)) { priorExtra = statExtra.Get(stat.layer); }
            statExtra.Set(stat.layer, priorExtra + stat.total - stat.shown);
        }
        for (int statSlot = 0; statSlot < layers.Count(); statSlot++)
        {
            int layerTotal = demand[statSlot];
            if (statExtra.Contains(layers[statSlot])) { layerTotal += statExtra.Get(layers[statSlot]); }
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
        m_Phase = 5;
    }
}
