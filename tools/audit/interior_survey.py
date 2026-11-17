"""Whole stock metadata inventory, reviewed batching, and acquisition-only merge.

Pure APIs: build_inventory(stock_bytes, native_rows, native_admission),
plan_survey(inventory, review), merge_receipts(inventory, plan, evidence_iterable).
No engine/process launches, asset writes, runtime hooks or settings changes.
Every map row, prototype and native row remains in its denominator. Config
ancestry/model fields are hints, not script identity or playable interior proof.
The stock mapgroup subset is NOT a census of every object in the world.

Review schema 1 explicitly approves the stock-origin-radius-v1 area policy,
radius, an evidence SHA256 and either exact per-row native orientations or a
reviewed rpy component/sign mapping scoped to named classes. Generated area
centers are stock origins; live matching remains mandatory. Review hashes bind
operator assertions, not their truth. Do not approve an entire class/map from
one pilot without an explicit review of that extrapolation.

Native admission is produced by item_compatibility.scan_manifest; raw rows must
be the exact admitted chunk rows. The pure API validates denominators/canonical
row pins but does not authenticate caller evidence. load_native re-reads and
rehashes every admitted file before returning its rows. Native metadata, stock
XML, reports and receipts belong OUTSIDE Git; the CLI only reads/prints.

Missing/malformed/ambiguous sources stay unresolved. Unsupported generator
limits remain backlog. Repeated or timed-out receipts cannot increase coverage.
A short native model name does not verify a full config model path. No room,
door/stair, clearance, placement, search or CE-eligibility inference is made.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from tools.package.economy import xml
from tools.setup import interior_measurement_probe as probe
from tools.setup.infected_death_probe import _read, _decode_json, _native_bool
from tools.setup.fuel_siphon_probe import _safe

MAX_PLACEMENTS = 100000
MAX_PROTOTYPES = 10000
MAX_NATIVE_ROWS = 16384
MAX_BATCHES = 25000
MAX_ATTEMPTS = 50000
MAX_WORK = 8_000_000
MAX_NODES = 8_000_000
MAX_JSON_BYTES = 192 << 20
MAX_MERGE_BYTES = 8 << 30
ROOTS = ("CfgWeapons", "CfgVehicles", "CfgMagazines", "CfgAmmo")
NATIVE_CLASS = re.compile(r"[A-Za-z_][A-Za-z_0-9]{0,511}\Z")
SHA = re.compile(r"[0-9a-f]{64}\Z")
GLOBAL_PROTO_ERRORS = ("duplicate/unsupported prototype group",
    "duplicate/unbounded prototype defaults", "unsupported prototype defaults")
MISSING = tuple(probe.MISSING) + ("world-object-census-outside-stock-mapgroups",
    "qualified-model-path-and-bbox-basis", "expanded-effective-CE-dispatch-graph")

def require(ok, code):
    if not ok:
        raise ValueError(code)

def integer(value, low, high):
    require(type(value) is int and low <= value <= high, "bounded-integer")
    return value

def digest(data):
    return hashlib.sha256(data).hexdigest()

def pin(value):
    require(type(value) is str and SHA.fullmatch(value), "SHA256-required")
    return value

class Budget:
    def __init__(self):
        self.work = self.nodes = self.bytes = 0
    def take(self, n=1):
        self.work += n
        require(self.work <= MAX_WORK, "work-budget")
    def copy(self, value, depth=0):
        self.take()
        self.nodes += 1
        require(depth <= 24 and self.nodes <= MAX_NODES, "structure-budget")
        if type(value) is dict:
            require(len(value) <= 128, "mapping-budget")
            result = {}
            self.bytes += 2 + len(value)*2
            for key, child in value.items():
                require(type(key) is str, "JSON-key")
                result[self.copy(key,depth+1)] = self.copy(child,depth+1)
        elif type(value) is list:
            require(len(value) <= MAX_PLACEMENTS, "array-budget")
            self.bytes += len(value)+2
            result = [self.copy(v,depth+1) for v in value]
        else:
            require(type(value) in (str,int,float,bool,type(None)), "JSON-value")
            if type(value) is str:
                require(len(value) <= 8192 and not any(0xD800<=ord(c)<=0xDFFF for c in value), "string-budget")
            if type(value) is int:
                require(value.bit_length() <= 63, "integer-budget")
            if type(value) is float:
                require(math.isfinite(value), "nonfinite-number")
            self.bytes += len(json.dumps(value,ensure_ascii=True,allow_nan=False))
            result = value
        require(self.bytes <= MAX_JSON_BYTES, "JSON-byte-budget")
        return result

def encoded(value):
    encoder = json.JSONEncoder(sort_keys=True,separators=(",",":"),ensure_ascii=True,allow_nan=False)
    parts = []
    size = 0
    for part in encoder.iterencode(value):
        size += len(part)
        require(size <= MAX_JSON_BYTES, "output-byte-budget")
        parts.append(part)
    return "".join(parts).encode("ascii")

def seal(value, key):
    value[key] = digest(encoded(value))
    return value

def admitted(value, key, kind):
    value = Budget().copy(value)
    require(type(value) is dict and value.get("schema") == 1 and type(value["schema"]) is int
            and value.get("kind") == kind, "artifact-schema")
    expected = pin(value.pop(key,None))
    require(digest(encoded(value)) == expected, "artifact-hash")
    value[key] = expected
    require(value.get("gameplay_acceptance") is False, "scope-contradiction")
    return value

def optional_vec(text, limit):
    try:
        return probe._xml_vec(text,limit)
    except (ValueError,TypeError,OverflowError):
        return None

def native_metadata(rows, admission, budget):
    require(type(rows) is list and len(rows) <= MAX_NATIVE_ROWS, "native-row-budget")
    rows = budget.copy(rows)
    admission = budget.copy(admission)
    require(type(admission) is dict and admission.get("status") in ("complete","partial"), "native-admission")
    complete = _native_bool(admission.get("EnumerationComplete"))
    require(complete == (admission["status"] == "complete"), "native-status")
    require(admission.get("manifest_pin_checked") is True and
            admission.get("FullCoverage") is False, "native-pin-and-scope")
    require(admission.get("ActualWorld") == "chernarusplus" and
            admission.get("ActualBuild") == "1.30.164289.70", "native-build-world")
    total = integer(admission.get("AdvertisedChildren"),0,MAX_NATIVE_ROWS)
    visited = integer(admission.get("VisitedChildren"),0,total)
    written = integer(admission.get("RowsWritten"),0,visited)
    require(written == len(rows) and integer(admission.get("NonClassChildren"),0,visited) == visited-written, "native-denominator")
    roots = admission.get("Roots")
    require(type(roots) is list and len(roots) == 4, "native-root-denominator")
    counts = Counter()
    for row in rows:
        budget.take()
        require(type(row) is dict and row.get("ConfigRoot") in ROOTS, "native-root")
        for key in ("ItemClass","ParentClass"):
            v = row.get(key)
            require(type(v) is str and (key == "ParentClass" and v == "" or NATIVE_CLASS.fullmatch(v)), "native-class")
        ancestors = row.get("ConfigAncestors")
        require(type(ancestors) is list and len(ancestors) <= 64 and
                all(type(v) is str and NATIVE_CLASS.fullmatch(v) for v in ancestors), "native-ancestors")
        fields = row.get("Fields")
        require(type(fields) is list and len(fields) <= 96 and
                all(type(f) is dict and type(f.get("ConfigPath")) is str for f in fields), "native-fields")
        counts[row["ConfigRoot"]] += 1
    sums = [0,0,0]
    for root, name in zip(roots,ROOTS):
        require(type(root) is dict and root.get("ConfigRoot") == name, "native-root-order")
        a = integer(root.get("AdvertisedChildren"),0,MAX_NATIVE_ROWS)
        v = integer(root.get("VisitedChildren"),0,a)
        r = integer(root.get("RowsWritten"),0,v)
        require(r == counts[name] and _native_bool(root.get("EnumerationComplete")) == (v == a), "native-root-count")
        sums = [sums[0]+a,sums[1]+v,sums[2]+r]
    require(sums == [total,visited,written] and (not complete or total == visited), "native-total")
    files = admission.get("files")
    require(type(files) is list and 1 <= len(files) <= 65, "native-file-denominator")
    names = set()
    for item in files:
        require(type(item) is dict and set(item) == {"file","bytes","sha256"}, "native-file")
        name = item["file"]
        require(type(name) is str and re.fullmatch(r"(?:manifest|chunk-[0-9]{1,2})\.json",name)
                and name not in names, "native-file-name")
        names.add(name); pin(item["sha256"]); integer(item["bytes"],1,16<<20)
    require(files[0]["file"] == "manifest.json", "native-manifest-pin")
    return rows, admission

def model_field(row):
    fields = [f for f in row["Fields"] if f["ConfigPath"].casefold() == "model"]
    if len(fields) != 1:
        return None, "missing-or-ambiguous-model-field"
    field = fields[0]
    if (type(field.get("ValueCaptured")) in (bool,int) and field["ValueCaptured"] == 1
            and field.get("ReadAs") == "text" and field.get("ConfigTypeName") == "CT_STRING"):
        value = field.get("ValueText")
        if type(value) is str and 0 < len(value) <= 512:
            return value, None
    return None, "uncaptured-or-empty-model"

def prototype_record(group, index):
    containers = group.findall("container")
    return dict(stock_prototype_row=index,tag=group.tag,name=group.get("name"),
        attributes=dict(group.attrib),source_fragment_sha256=digest(ET.tostring(group)),
        child_tags=dict(sorted(Counter(c.tag for c in group).items())),
        container_count=len(containers),raw_point_count=sum(len(c.findall("point")) for c in containers),
        containers=[dict(attributes=dict(c.attrib),points=[dict(p.attrib) for p in c.findall("point")],
            categories=[dict(x.attrib) for x in c.findall("category")],
            tags=[dict(x.attrib) for x in c.findall("tag")]) for c in containers],
        unresolved_scope=["effective-CE-dispatch-not-expanded"] if group.findall("dispatch") else [])

def build_inventory(stock_bytes, native_rows, native_admission):
    budget = Budget()
    require(type(stock_bytes) is dict and set(stock_bytes) == set(probe.STOCK_NAMES), "stock-input-denominator")
    for name, raw in stock_bytes.items():
        budget.take()
        maximum = 65536 if name == "init.c" else 16<<20
        require(type(raw) is bytes and 0 < len(raw) <= maximum, "stock-byte-budget")
    pos = list(xml(stock_bytes["mapgrouppos.xml"],"map"))
    proto = list(xml(stock_bytes["mapgroupproto.xml"],"prototype"))
    require(len(pos) <= MAX_PLACEMENTS and len(proto) <= MAX_PROTOTYPES, "stock-row-budget")
    native_rows, native_admission = native_metadata(native_rows,native_admission,budget)
    config = defaultdict(list)
    for i, row in enumerate(native_rows):
        budget.take()
        if row["ConfigRoot"] == "CfgVehicles":
            config[row["ItemClass"].casefold()].append(i)
    prototypes = []
    proto_indices = defaultdict(list)
    for i, group in enumerate(proto):
        budget.take()
        if group.tag == "group":
            record = prototype_record(group,i)
            prototypes.append(record)
            proto_indices[group.get("name")].append(len(prototypes)-1)
    global_issues = []
    # Probe global parsing once. Per-class subsets below are only for explaining
    # unsupported limits; emitted requests still pin the ENTIRE original XML.
    if prototypes:
        first = next((p["name"] for p in prototypes if type(p["name"]) is str), None)
        if type(first) is str:
            request = dict(areas=[dict(id="preflight",center=[0,0,0],radius=1,
                expected=[dict(id="preflight",stock_row=0,building_class=first,orientation=[0,0,0])])])
            simple = ET.Element("map"); ET.SubElement(simple,"group",name=first,pos="0 0 0")
            try:
                probe._references(request,ET.tostring(simple),stock_bytes["mapgroupproto.xml"])
            except (ValueError,TypeError) as exc:
                if str(exc) in GLOBAL_PROTO_ERRORS:
                    global_issues.append(str(exc))
    else:
        global_issues.append("no-prototypes")
    for group in proto:
        if group.tag not in ("group","defaults"):
            global_issues.append("unsupported-prototype-node")
    support = {}
    for name, indices in proto_indices.items():
        budget.take()
        if len(indices) != 1 or type(name) is not str:
            support[name] = (False,None,"duplicate-or-unnamed-prototype")
            continue
        original = proto[prototypes[indices[0]]["stock_prototype_row"]]
        wrapper = ET.Element("prototype"); wrapper.append(original)
        placed = ET.Element("map"); ET.SubElement(placed,"group",name=name,pos="0 0 0")
        request = dict(areas=[dict(id="preflight",center=[0,0,0],radius=1,
            expected=[dict(id="preflight",stock_row=0,building_class=name,orientation=[0,0,0])])])
        try:
            refs = probe._references(request,ET.tostring(placed),ET.tostring(wrapper))
            support[name] = (True,len(refs["houses"][0]["ce_points"]),"")
        except (ValueError,TypeError,OverflowError) as exc:
            support[name] = (False,None,str(exc)[:256])
    placements = []
    origins = defaultdict(list)
    placed_names = Counter()
    for i, node in enumerate(pos):
        budget.take()
        name = node.get("name")
        position = optional_vec(node.get("pos"),30000)
        rpy = optional_vec(node.get("rpy"),360)
        reasons = []
        if node.tag != "group":reasons.append("unsupported-placement-node")
        try:probe._class(name)
        except ValueError:reasons.append("unsupported-placement-class")
        if position is None:reasons.append("stock-position-unavailable")
        matches = config.get(name.casefold(),[]) if type(name) is str else []
        if not matches:reasons.append("native-class-missing")
        elif len(matches) != 1:reasons.append("ambiguous-native-class")
        elif native_rows[matches[0]]["ItemClass"] != name:reasons.append("native-class-case-mismatch")
        models = [model_field(native_rows[n])[0] for n in matches]
        if len(matches) == 1 and models[0] is None:reasons.append("native-model-unresolved")
        indices = proto_indices.get(name,[])
        if not indices:reasons.append("prototype-missing")
        elif len(indices) > 1:reasons.append("duplicate-prototype")
        supported, count, detail = support.get(name,(False,None,"prototype-missing"))
        if not supported:reasons.append("measurement-generator-unsupported")
        if global_issues:reasons.append("global-prototype-unsupported")
        placements.append(dict(stock_row=i,tag=node.tag,building_class=name,
            attributes=dict(node.attrib),position=position,rpy=rpy,native_rows=matches,
            prototype_rows=[prototypes[n]["stock_prototype_row"] for n in indices],
            config_models=models,ce_reference_points=count,generator_error=detail,
            reasons=sorted(set(reasons))))
        if type(name) is str:placed_names[name] += 1
        if position is not None and type(name) is str:origins[(name,*position)].append(i)
    for ids in origins.values():
        if len(ids) > 1:
            for i in ids:
                placements[i]["reasons"].append("duplicate-placement-origin")
                placements[i]["reasons"].sort()
    classes = []
    all_names = sorted(set(placed_names) | {r["ItemClass"] for r in native_rows if r["ConfigRoot"]=="CfgVehicles"})
    for name in all_names:
        budget.take()
        ids = config.get(name.casefold(),[])
        models = sorted(set(m for i in ids if (m:=model_field(native_rows[i])[0]) is not None))
        ancestry = sorted(set(v for i in ids for v in native_rows[i]["ConfigAncestors"]))
        classes.append(dict(building_class=name,placement_rows=placed_names[name],
            native_rows=ids,config_models=models,prototype_rows=[
                prototypes[n]["stock_prototype_row"] for n in proto_indices.get(name,[])],
            house_config_hint=any(a.casefold() in ("house","housenodestruct","building") for a in ancestry),
            config_ancestors=ancestry,script_identity="UNKNOWN",model_identity_verified=False))
    models = defaultdict(list)
    for c in classes:
        for m in c["config_models"]:models[m].append(c["building_class"])
    report = dict(schema=1,kind="stock-interior-inventory",gameplay_acceptance=False,
        feature_complete=False,survey_complete=False,world_object_census_complete=False,
        world_name=native_admission["ActualWorld"],engine_version=native_admission["ActualBuild"],
        source_pins=dict(stock={n:digest(b) for n,b in stock_bytes.items()},
            native_files=native_admission["files"],native_rows_sha256=digest(encoded(native_rows))),
        coverage=dict(placement_rows=len(pos),prototype_rows=len(prototypes),
            prototype_root_nodes=len(proto),native_rows=len(native_rows),
            native_enumeration_complete=_native_bool(native_admission["EnumerationComplete"]),
            native_unvisited_children=native_admission["AdvertisedChildren"]-native_admission["VisitedChildren"],
            classes=len(classes),config_model_paths=len(models)),
        placements=placements,prototypes=prototypes,
        prototype_non_groups=[dict(stock_prototype_row=i,tag=n.tag,attributes=dict(n.attrib),
            source_fragment_sha256=digest(ET.tostring(n))) for i,n in enumerate(proto) if n.tag!="group"],
        global_generator_issues=sorted(set(global_issues)),native_rows=native_rows,
        native_admission=native_admission,classes=classes,
        models=[dict(config_model_path=m,classes=names) for m,names in sorted(models.items())],
        missing_survey_data=list(MISSING))
    encoded(report)
    return seal(report,"inventory_sha256")

def reviewed_orientations(inv, review, budget):
    probe._fields(review,"schema inventory_sha256 reviewed evidence_sha256 area_policy radius mapping")
    require(type(review["schema"]) is int and review["schema"] == 1 and review["reviewed"] is True, "explicit-review-required")
    require(review["inventory_sha256"] == inv["inventory_sha256"],"review-source-drift")
    pin(review["evidence_sha256"])
    require(review["area_policy"] == "stock-origin-radius-v1", "unsupported-area-policy")
    probe._number(review["radius"],.25,25)
    mapping = review["mapping"]
    require(type(mapping) is dict, "coordinate-mapping")
    orientations = {}
    if mapping.get("kind") == "explicit-native":
        probe._fields(mapping,"kind orientations")
        require(type(mapping["orientations"]) is list and len(mapping["orientations"]) <= MAX_PLACEMENTS, "orientation-budget")
        for row in mapping["orientations"]:
            budget.take()
            probe._fields(row,"stock_row orientation")
            index = integer(row["stock_row"],0,len(inv["placements"])-1)
            require(index not in orientations,"duplicate-explicit-orientation")
            orientations[index] = probe._vec(row["orientation"],360)
    elif mapping.get("kind") == "reviewed-rpy":
        probe._fields(mapping,"kind components signs classes")
        components = mapping["components"]; signs = mapping["signs"]; classes = mapping["classes"]
        require(type(components) is list and len(components)==3 and all(type(i) is int for i in components)
                and sorted(components)==[0,1,2], "reviewed-coordinate-components")
        require(type(signs) is list and len(signs)==3 and all(type(i) is int and i in (-1,1) for i in signs), "reviewed-coordinate-signs")
        require(type(classes) is list and len(classes)<=MAX_NATIVE_ROWS and
                all(type(c) is str and NATIVE_CLASS.fullmatch(c) for c in classes), "reviewed-class-scope")
        require(len(set(classes))==len(classes),"duplicate-reviewed-class")
        allowed = set(classes)
        known = {c["building_class"] for c in inv["classes"]}
        require(allowed <= known,"unknown-reviewed-class")
        for row in inv["placements"]:
            budget.take()
            if row["building_class"] in allowed and row["rpy"] is not None:
                orientations[row["stock_row"]] = [row["rpy"][i]*sign for i,sign in zip(components,signs)]
    else:
        raise ValueError("unsupported-coordinate-mapping")
    return orientations

def cell(position, radius):
    return tuple(math.floor(v/radius) for v in position)

def plan_survey(inventory, review):
    inv = admitted(inventory,"inventory_sha256","stock-interior-inventory")
    budget = Budget()
    review = budget.copy(review)
    orientations = reviewed_orientations(inv,review,budget)
    rows = []
    eligible = {}
    for row in inv["placements"]:
        budget.take()
        reasons = list(row["reasons"])
        if row["stock_row"] not in orientations:
            reasons.append("coordinate-mapping-unreviewed")
            if row["rpy"] is None:reasons.append("stock-rpy-unavailable")
        state = dict(stock_row=row["stock_row"],building_class=row["building_class"],
            reasons=sorted(set(reasons)),status="unplanned",batch_id=None,area_id=None)
        rows.append(state)
        if not reasons:eligible[row["stock_row"]] = row
    radius = review["radius"]
    buckets = defaultdict(set)
    for i, row in eligible.items():buckets[cell(row["position"],radius)].add(i)
    remaining = set(eligible)
    areas = []
    for index in eligible:
        budget.take()
        if index not in remaining:continue
        anchor = eligible[index]
        center = anchor["position"]; key = cell(center,radius)
        candidates = []
        for dx in (-1,0,1):
            for dy in (-1,0,1):
                for dz in (-1,0,1):
                    for n in buckets.get((key[0]+dx,key[1]+dy,key[2]+dz),()):
                        budget.take()
                        if probe._distance(center,eligible[n]["position"]) <= (radius-.1)**2:
                            candidates.append(n)
        selected=[]; points=0
        for n in sorted(candidates):
            budget.take()
            count=eligible[n]["ce_reference_points"]
            if len(selected)==16 or points+count>512:continue
            selected.append(n);points+=count
        require(index in selected, "anchor-not-selected")
        for n in selected:
            remaining.remove(n);buckets[cell(eligible[n]["position"],radius)].remove(n)
        area = dict(id="stock-house-"+str(index),reviewed=True,center=list(center),radius=radius,
            expected=[dict(id="house-"+str(n),stock_row=n,building_class=eligible[n]["building_class"],
                orientation=orientations[n]) for n in selected])
        areas.append((area,points))
    batches=[]; current=[]; current_points=current_houses=0
    def flush():
        nonlocal current,current_points,current_houses
        if not current:return
        request = dict(schema=1,world_name=inv["world_name"],engine_version=inv["engine_version"],
            stock_sha256=inv["source_pins"]["stock"],areas=current)
        probe._request(request)
        identity = "batch-"+str(len(batches))
        for a in current:
            for h in a["expected"]:
                state = rows[h["stock_row"]];state.update(status="planned",batch_id=identity,area_id=a["id"])
        batches.append(dict(id=identity,request=request,request_sha256=digest(probe._encode(request)),
            ce_reference_points=current_points,native_watchdog_seconds=60,max_outer_seconds=probe.MAX_OUTER_SECONDS))
        current=[];current_points=current_houses=0
    for area,points in areas:
        count = len(area["expected"])
        if len(current)==4 or current_houses+count>16 or current_points+points>512:flush()
        current.append(area);current_houses+=count;current_points+=points
    flush()
    require(len(batches)<=MAX_BATCHES, "batch-count-budget")
    result=dict(schema=1,kind="reviewed-interior-measurement-plan",gameplay_acceptance=False,
        feature_complete=False,survey_complete=False,inventory_sha256=inv["inventory_sha256"],
        review=review,review_sha256=digest(encoded(review)),rows=rows,batches=batches,
        coverage=dict(inv["coverage"],planned_placements=len(eligible),
            unplanned_placements=len(rows)-len(eligible),batches=len(batches)),
        missing_survey_data=list(MISSING))
    return seal(result,"plan_sha256")

def merge_receipts(inventory, plan, evidence_iterable):
    inv=admitted(inventory,"inventory_sha256","stock-interior-inventory")
    plan=admitted(plan,"plan_sha256","reviewed-interior-measurement-plan")
    require(plan["inventory_sha256"]==inv["inventory_sha256"],"plan-source-drift")
    # Regeneration binds request ids, every denominator and review to inventory.
    expected=plan_survey(inv,plan["review"])
    require(plan==expected,"plan-policy-mismatch")
    batches={b["id"]:b for b in plan["batches"]}
    attempts=[];accepted=set();nonces=set();measured={};total=0
    require(not isinstance(evidence_iterable,(dict,str,bytes)), "evidence-iterable")
    for index,evidence in enumerate(evidence_iterable):
        require(index<MAX_ATTEMPTS,"attempt-budget")
        probe._fields(evidence,"batch_id files receipt outer_timed_out outer_elapsed_seconds external_run_sha256")
        identity=evidence["batch_id"]
        require(type(identity) is str and identity in batches,"unplanned-batch")
        pin(evidence["external_run_sha256"])
        files=evidence["files"];raw=evidence["receipt"]
        require(type(raw) is bytes and len(raw)<=probe.MAX_RECEIPT_BYTES,"receipt-byte-budget")
        require(type(files) is dict and set(files)=={"init.c",probe.MARKER,probe.REFERENCE},"bundle-files")
        for name,limit in (("init.c",128<<10),(probe.MARKER,probe.MAX_MANIFEST_BYTES),
                           (probe.REFERENCE,probe.MAX_REFERENCE_BYTES)):
            require(type(files[name]) is bytes and len(files[name])<=limit,"bundle-byte-budget")
        files=dict(files)  # immutable byte snapshots before independent validation
        total+=len(raw)+sum(len(v) for v in files.values())
        require(total<=MAX_MERGE_BYTES,"aggregate-evidence-byte-budget")
        attempt=dict(batch_id=identity,receipt_sha256=digest(raw),
            external_run_sha256=evidence["external_run_sha256"],status="rejected",reason="")
        try:
            require(identity not in accepted,"duplicate-successful-batch")
            report=probe.validate_receipt(raw,files,
                outer_timed_out=evidence["outer_timed_out"],outer_elapsed_seconds=evidence["outer_elapsed_seconds"])
            manifest=_decode_json(files[probe.MARKER])
            require(manifest["request"]==batches[identity]["request"],"receipt-request-not-planned")
            require(manifest["run_id"] not in nonces,"replayed-native-run")
            native_areas=report["receipt"]["areas"]
            for area,native_area in zip(batches[identity]["request"]["areas"],native_areas):
                for target,house in zip(area["expected"],native_area["houses"]):
                    row_id=target["stock_row"]
                    require(row_id not in measured,"repeated-placement-acquisition")
                    measured[row_id]=dict(stock_row=row_id,batch_id=identity,run_id=manifest["run_id"],
                        receipt_sha256=digest(raw),native_model_name=house["model_name"],
                        model_identity_verified=False)
            nonces.add(manifest["run_id"]);accepted.add(identity)
            attempt.update(status="accepted-acquisition",run_id=manifest["run_id"])
        except (ValueError,TypeError,KeyError,UnicodeError,RecursionError) as exc:
            attempt["reason"]=str(exc)[:512]
        attempts.append(attempt)
    per_class=Counter(inv["placements"][i]["building_class"] for i in measured)
    classes=[dict(c,measured_placements=per_class[c["building_class"]]) for c in inv["classes"]]
    unmeasured=[dict(row,reasons=list(row["reasons"])+
        ([] if row["status"]=="unplanned" else ["no-accepted-measurement"]))
        for row in plan["rows"] if row["stock_row"] not in measured]
    result=dict(schema=1,kind="interior-acquisition-coverage",gameplay_acceptance=False,
        feature_complete=False,survey_complete=False,model_identity_verified=False,
        world_object_census_complete=False,inventory_sha256=inv["inventory_sha256"],
        plan_sha256=plan["plan_sha256"],coverage=dict(plan["coverage"],
            measured_placements=len(measured),unmeasured_placements=len(unmeasured),
            accepted_batches=len(accepted),attempts=len(attempts)),
        measured_rows=[measured[i] for i in sorted(measured)],unmeasured_rows=unmeasured,
        classes=classes,models=inv["models"],attempts=attempts,missing_survey_data=list(MISSING))
    return seal(result,"coverage_sha256")

def load_native(manifest_path, expected_sha256):
    """POSIX secure native manifest admission; refuses unsupported platforms."""
    from tools.audit.item_compatibility import scan_manifest
    pin(expected_sha256)
    manifest_path=_safe(Path(manifest_path))
    admission=scan_manifest(manifest_path,expected_sha256)
    rows=[];size=0
    for ref in admission["files"]:
        raw=_read(manifest_path.parent/ref["file"],16<<20)
        size+=len(raw);require(size<=256<<20,"native-source-byte-budget")
        require(len(raw)==ref["bytes"] and digest(raw)==ref["sha256"],"native-source-drift")
        if ref["file"]!="manifest.json":
            data=_decode_json(raw)
            require(type(data.get("Rows")) is list,"native-chunk-rows")
            rows.extend(data["Rows"]);require(len(rows)<=MAX_NATIVE_ROWS,"native-row-budget")
    return rows,admission

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest="command",required=True)
    scan=sub.add_parser("inventory")
    scan.add_argument("--stock-dir",type=Path,required=True)
    scan.add_argument("--native-manifest",type=Path,required=True)
    scan.add_argument("--expect-native-sha256",required=True)
    plan=sub.add_parser("plan")
    plan.add_argument("--inventory",type=Path,required=True)
    plan.add_argument("--review",type=Path,required=True)
    merge=sub.add_parser("merge")
    merge.add_argument("--inventory",type=Path,required=True)
    merge.add_argument("--plan",type=Path,required=True)
    merge.add_argument("--evidence-index",type=Path,required=True)
    args=parser.parse_args(argv)
    def record(path):
        return _decode_json(_read(_safe(path),MAX_JSON_BYTES))
    try:
        if args.command=="inventory":
            stock_dir=_safe(args.stock_dir)
            sources={n:_read(stock_dir/n,65536 if n=="init.c" else 16<<20) for n in probe.STOCK_NAMES}
            rows,admission=load_native(args.native_manifest,args.expect_native_sha256)
            result=build_inventory(sources,rows,admission)
        elif args.command=="plan":
            result=plan_survey(record(args.inventory),record(args.review))
        else:
            index=record(args.evidence_index)
            probe._fields(index,"schema entries")
            require(type(index["schema"]) is int and index["schema"]==1,"evidence-index-schema")
            require(type(index["entries"]) is list and len(index["entries"])<=MAX_ATTEMPTS,"evidence-index-budget")
            def evidence():
                for entry in index["entries"]:
                    probe._fields(entry,"batch_id bundle_dir receipt_path outer_timed_out outer_elapsed_seconds external_run_sha256")
                    root=_safe(Path(entry["bundle_dir"]))
                    # Exact inventory; stops at the first unexpected node.
                    expected={"init.c",probe.MARKER,probe.REFERENCE}
                    import os
                    with os.scandir(root) as scan:
                        seen=set()
                        for item in scan:
                            require(item.name in expected and item.is_file(follow_symlinks=False),"unexpected-bundle-node")
                            seen.add(item.name)
                        require(seen==expected,"bundle-file-denominator")
                    files={n:_read(root/n,128<<10 if n=="init.c" else
                        probe.MAX_MANIFEST_BYTES if n==probe.MARKER else probe.MAX_REFERENCE_BYTES) for n in expected}
                    yield dict(batch_id=entry["batch_id"],files=files,
                        receipt=_read(_safe(Path(entry["receipt_path"])),probe.MAX_RECEIPT_BYTES),
                        outer_timed_out=entry["outer_timed_out"],outer_elapsed_seconds=entry["outer_elapsed_seconds"],
                        external_run_sha256=entry["external_run_sha256"])
            result=merge_receipts(record(args.inventory),record(args.plan),evidence())
        print(encoded(result).decode("ascii"))
    except (ValueError,OSError,TypeError,KeyError,UnicodeError,RecursionError) as exc:
        parser.exit(1,str(exc)+"\n")

if __name__=="__main__":main()
