// W6 #123. Native scripts-1.30.164289: 1_Core/proto/EnScript.c:380,407
// Count/Insert, :887,897 map GetElement/GetKey; EnMath3D.c:18 Vector;
// EnConvert.c:30 int.ToString; EnDebug.c:96 Print. HCDebugSnapshot owns capture.
// One completed request: <=1024 points +128 routes*64 vertices examined;
// <=512 total vertices/16 layers exported, text already bounded by shared API.
// w28-debugmap #193: the 512-mark budget is shared fairly (water-fill: every sent
// layer gets budget/layers first, leftovers go to layers that still have rows),
// so a late layer (camps, scenes, lead-ledger) is not starved by ai-units. Per-layer
// sent/total ride in the bounded Notice as `layers=name:sent/total,...` (the client
// replaces a snapshot reply's Lines, so Notice is the carried channel). Caps unchanged.
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

    // Index of the layer in the sent list; registers it (<=16) when new, -1 when full.
    protected static int HCSlot(array<string> layers, array<int> demand, string layer)
    {
        int found = layers.Find(layer);
        if (found >= 0) { return found; }
        if (layers.Count() >= 16) { return -1; }
        layers.Insert(layer);
        demand.Insert(0);
        return layers.Count() - 1;
    }

    // Water-fill the budget across layers: each unmet layer takes an equal share per
    // round, capped by its own demand; <=16 layers so the rounds terminate early.
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

    static HCAdminReply HCBuild(HCDebugSnapshot capture, int ticket)
    {
        HCAdminReply reply = new HCAdminReply;
        reply.Ticket = ticket;
        reply.Snapshot = true;
        array<string> layers = new array<string>;
        array<string> unsent = new array<string>;
        array<int> demand = new array<int>;
        array<int> allowance = new array<int>;
        HCDebugDocument document = capture.HCDocument();
        int total = 0;
        // Pass 1: register <=16 layers in document order and count each one's demand.
        for (int layerIndex = 0; layerIndex < document.layers.Count(); layerIndex++)
        {
            string layer = document.layers.GetKey(layerIndex);
            int pointCount = document.layers.GetElement(layerIndex).Count();
            total += pointCount;
            int layerSlot = HCSlot(layers, demand, layer);
            if (layerSlot < 0)
            {
                if (unsent.Find(layer) < 0) { unsent.Insert(layer); }
                continue;
            }
            demand[layerSlot] = demand[layerSlot] + pointCount;
        }
        for (int demandRoute = 0; demandRoute < document.routes.Count(); demandRoute++)
        {
            HCDebugRoute counted = document.routes[demandRoute];
            int vertexCount = counted.points.Count();
            total += vertexCount;
            int routeSlot = HCSlot(layers, demand, counted.layer);
            if (routeSlot < 0)
            {
                if (unsent.Find(counted.layer) < 0) { unsent.Insert(counted.layer); }
                continue;
            }
            demand[routeSlot] = demand[routeSlot] + vertexCount;
        }
        HCAllocate(demand, 512, allowance);
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
        string statText = "";
        for (int statSlot = 0; statSlot < layers.Count(); statSlot++)
        {
            int layerTotal = demand[statSlot];
            for (int statIndex = 0; statIndex < document.layerStats.Count(); statIndex++)
            {
                HCDebugLayerStat stat = document.layerStats[statIndex];
                if (stat.layer == layers[statSlot] && stat.total > stat.shown) { layerTotal += stat.total - stat.shown; }
            }
            if (statSlot > 0) { statText += ","; }
            statText += HCDebugSnapshot.HCText(layers[statSlot], 24) + ":" + sentCount[statSlot].ToString() + "/" + layerTotal.ToString();
        }
        string notice = "Snapshot row/contributor losses=" + refused.ToString() + "; runtime=PENDING; vertices=" + reply.Marks.Count().ToString() + " dropped=" + dropped.ToString();
        notice += "; layers=" + statText + "; layers_unsent=" + unsent.Count().ToString();
        notice += "; captured over several ticks; expires in 60s";
        reply.Notice = HCDebugSnapshot.HCText(notice, 1024);
        Print("[HC Admin] cmd=snapshot result=ok reason=delivered vertices=" + reply.Marks.Count().ToString() + " truncated=" + dropped.ToString());
        return reply;
    }
}
