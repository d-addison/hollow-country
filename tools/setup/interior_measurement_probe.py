"""Generate a disposable real-house acquisition bundle; NEVER launch DayZ.

generate_probe(init_bytes, map_positions, map_prototypes, request, interfaces,
               run_id=None) -> three bounded files.
validate_receipt(receipt_bytes, files, *, outer_timed_out,
                 outer_elapsed_seconds) -> acquisition-only report.

The bundle replaces init.c only in a separately copied, pinned stock mission.
It omits the inspected ce.InitOffline pair, retains CreateHive and the stock
factory chain, and schedules SYSTEM callbacks from the end of main(). No actors,
props, native CE calls, doors, inventory, feature flags or addon hooks are used.
The coordinator must independently bind the staged mission/server/PBO and actual
outer-process outcome. Embedded source hashes are correlations, not native hashes
or engine authentication. Never overlay a live mission.

Bounds: 4 reviewed areas, radius .25..25m; 16 expected houses; 256 objects/query;
128 stock points/house, 512 total; 4 transform probes/house; 60s native watchdog;
2048 frame/128 queue callbacks; external wall deadline <=180s including startup.
A native call may block; script cannot preempt it. The post-query object cap
bounds script work, not native enumeration time. Output serialization <=256KiB
characters, host receipt <=1MiB bytes. Failure output/partial bundles are retained.
Raw collision/clipping bounds have UNQUALIFIED coordinate basis. Inverse transform
checks cannot establish clearances, rooms, valid placement or CE eligibility.
"""
import argparse
import copy
import json
import os
from pathlib import Path
import re
import secrets

from tools.validate import dayz_build
from tools.package.economy import xml
from tools.setup import diagnostic_mission as staging
from tools.setup import native_startup_probe as syntax
from tools.setup.fuel_siphon_probe import _safe
from tools.setup.infected_death_probe import _read, _sha, _encode, _decode_json, _number, _native_bool

MARKER = ".hc-interior-measurement-probe.json"
REFERENCE = "hc-interior-stock-reference.json"
RESULT = "hc-interior-measurement-result.json"
KIND = "native-real-house-measurement-acquisition"
MAX_RECEIPT_BYTES = 1024 * 1024
MAX_MANIFEST_BYTES = 128 * 1024
MAX_REFERENCE_BYTES = 512 * 1024
MAX_OUTER_SECONDS = 180
PROBES = ((0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1))
MISSING = ("room-labels", "authored-prop-placements-and-bounds",
    "door-sweep-and-stair-keepouts", "clearance-and-route-observations",
    "rendered-targeting-and-fit", "two-client-replication-and-search",
    "CE-runtime-eligibility")
STOCK_NAMES = ("init.c", "mapgrouppos.xml", "mapgroupproto.xml")
INTERFACES = {
    "3_Game/Entities/Object.c": (
        "proto native vector GetPosition();", "proto native vector GetOrientation();",
        "proto native bool GetCollisionBox(out vector minMax[2]);",
        "proto float ClippingInfo(out vector minMax[2]);",
        "proto vector ModelToWorld(vector modelPos);",
        "proto vector WorldToModel(vector worldPos);", "string GetModelName()", "string GetType()"),
    "4_World/Entities/Game/Super/Building.c": ("class House : BuildingBase",),
    "3_Game/Global/Game.c": (
        "GetObjectsAtPosition3D(vector pos, float radius, out array<Object> objects, out array<CargoBase> proxyCargos)",
        "GetVersion( out string version )", "GetWorldName( out string world_name )", "GetTickTime()", "IsServer()"),
    "3_Game/gameplay.c": ("void OnMissionFinish()",),
    "3_Game/Hive/Hive.c": ("proto native Hive CreateHive();", "proto native void InitOffline();"),
    "3_Game/DayZGame.c": ("GetCallQueue(CALL_CATEGORY_SYSTEM).Tick(timeslice)",
        "GetUpdateQueue(CALL_CATEGORY_SYSTEM).Invoke(timeslice)"),
    "2_GameLib/tools.c": ("void CallLater(func fn, int delay = 0, bool repeat = false",
        "void Remove(func fn)", "bool Insert(func fn", "int Count(func fn)"),
    "3_Game/tools/JsonFileLoader.c": (
        "static bool MakeData(T inputData, out string outputData, out string errorMessage, bool prettyPrint = true)",),
    "1_Core/proto/EnSystem.c": ("proto bool FileExist(string name);", "proto FileHandle OpenFile(string name, FileMode mode);",
        "proto void FPrint(FileHandle file, void var);", "proto void CloseFile(FileHandle file);"),
}


def _require(ok, message):
    if not ok:
        raise ValueError(message)


def _fields(value, names):
    _require(type(value) is dict and set(value) == set(names.split()), "unsupported/missing fields")


def _bytes(value, maximum):
    _require(type(value) is bytes and 0 < len(value) <= maximum, "bounded byte input required")
    return value


def _int(value, low, high):
    _require(type(value) is int and low <= value <= high, "bounded integer required")
    return value


def _vec(value, limit):
    _require(type(value) is list and len(value) == 3, "three numeric components required")
    return [_number(n, -limit, limit) for n in value]


def _id(value):
    _require(type(value) is str and re.fullmatch(r"[a-z][a-z0-9-]{0,47}", value), "bounded identifier required")
    return value


def _class(value):
    _require(type(value) is str and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,95}", value), "native class name required")
    return value


def _xml_vec(value, limit):
    _require(type(value) is str and len(value) <= 128, "bounded XML vector required")
    return _vec([float(n) for n in value.split()], limit)


def _distance(left, right):
    return sum((a-b)**2 for a, b in zip(left, right))


def _pose(position, orientation, expected):
    _vec(position, 30000); _vec(orientation, 360)
    _require(_distance(position, expected["position"]) <= .1**2, "live position mismatch")
    _require(all(abs((a-b+180) % 360-180) <= .1
                 for a, b in zip(orientation, expected["orientation"])), "live orientation mismatch")


def _interface_records(interfaces):
    _require(type(interfaces) is dict and set(interfaces) == set(INTERFACES), "exact installed interface snapshots required")
    result = {}
    for name, tokens in INTERFACES.items():
        data = _bytes(interfaces[name], 2*1024*1024)
        text = " ".join(data.decode("utf-8-sig").split())
        _require(all(" ".join(token.split()) in text for token in tokens), "installed interface mismatch: "+name)
        result[name] = dict(bytes=len(data), sha256=_sha(data))
    return result


def _request(value, blobs=None):
    _fields(value, "schema world_name engine_version stock_sha256 areas")
    _require(type(value["schema"]) is int and value["schema"] == 1, "request schema")
    _require(value["world_name"] == "chernarusplus" and value["engine_version"] == dayz_build.pinned() + ".70", "explicit pinned world/full engine version required")
    pins = value["stock_sha256"]
    _require(type(pins) is dict and set(pins) == set(STOCK_NAMES), "exact stock pins required")
    for digest in pins.values():
        _require(type(digest) is str and re.fullmatch(r"[0-9a-f]{64}", digest), "stock digest required")
    if blobs is not None:
        _require(pins == {name:_sha(blobs[name]) for name in STOCK_NAMES}, "pinned stock bytes mismatch")
    areas = value["areas"]
    _require(type(areas) is list and 1 <= len(areas) <= 4, "1..4 reviewed areas required")
    area_ids, house_ids, stock_rows, count = set(), set(), set(), 0
    for area in areas:
        _fields(area, "id reviewed center radius expected")
        _id(area["id"]); _require(area["id"] not in area_ids, "duplicate area")
        area_ids.add(area["id"])
        _require(area["reviewed"] is True, "explicit operator-reviewed area required")
        _vec(area["center"], 30000); _number(area["radius"], .25, 25)
        expected = area["expected"]
        _require(type(expected) is list and 1 <= len(expected) <= 16, "bounded expected houses required")
        count += len(expected); _require(count <= 16, "global house cap")
        for house in expected:
            _fields(house, "id stock_row building_class orientation")
            _id(house["id"]); _class(house["building_class"])
            _require(house["id"] not in house_ids, "duplicate house ID")
            house_ids.add(house["id"]); _int(house["stock_row"], 0, 99999)
            _require(house["stock_row"] not in stock_rows, "duplicate selected stock row")
            stock_rows.add(house["stock_row"])
            _vec(house["orientation"], 360)
    return copy.deepcopy(value)


def _references(request, positions, prototypes):
    placed = list(xml(positions, "map"))
    proto = list(xml(prototypes, "prototype"))
    _require(len(placed) <= 100000 and len(proto) <= 10000, "stock row budget")
    groups = {}
    defaults_seen = False
    for group in proto:
        if group.tag == "defaults":
            # Stock contains global CE defaults. Preserve their source hash;
            # do not evaluate them as point eligibility or furnishing policy.
            _require(not defaults_seen and not group.attrib and len(group) <= 64,
                     "duplicate/unbounded prototype defaults")
            defaults_seen = True
            for item in group:
                _require(item.tag == "default" and not list(item) and len(item.attrib) <= 16
                         and all(len(key) <= 96 and len(value) <= 512
                                 for key, value in item.attrib.items()),
                         "unsupported prototype defaults")
            continue
        _require(group.tag == "group" and group.get("name") not in groups, "duplicate/unsupported prototype group")
        groups[group.get("name")] = group
    references, selected_rows, selected_poses, total = [], set(), set(), 0
    for area in request["areas"]:
        for expected in area["expected"]:
            index = expected["stock_row"]
            _require(index < len(placed) and index not in selected_rows, "missing/duplicate stock row")
            row = placed[index]; selected_rows.add(index)
            _require(row.tag == "group" and row.get("name") == expected["building_class"], "stock row/class mismatch")
            position = _xml_vec(row.get("pos"), 30000)
            identity = (expected["building_class"], *position)
            _require(identity not in selected_poses, "duplicate physical house")
            selected_poses.add(identity)
            _require(_distance(position, area["center"]) <= (area["radius"]-.1)**2, "expected origin outside reviewed area margin")
            _require(expected["building_class"] in groups, "prototype missing for selected class")
            group = groups[expected["building_class"]]
            containers = group.findall("container")
            _require(len(containers) <= 32, "container cap")
            points, container_ids = [], set()
            for container in containers:
                name = container.get("name")
                _require(type(name) is str and 1 <= len(name) <= 96 and name not in container_ids, "container identity")
                container_ids.add(name); locations = set()
                categories = _labels([v.get("name") for v in container.findall("category")])
                tags = _labels([v.get("name") for v in container.findall("tag")])
                for index_in_container, point in enumerate(container.findall("point")):
                    _require(set(point.attrib) <= {"pos","range","height","flags"} and "pos" in point.attrib and not list(point), "unsupported point fields")
                    local = _xml_vec(point.get("pos"), 1000)
                    _require(tuple(local) not in locations, "duplicate stock point")
                    locations.add(tuple(local))
                    for field in ("range","height"):
                        _number(float(point.get(field,"0")), 0, 100)
                    _require(re.fullmatch(r"[0-9]{1,5}", point.get("flags","0")), "point flags")
                    points.append(dict(container=name, point_index=index_in_container,
                        local_position=local, attributes=dict(point.attrib),
                        categories=categories, tags=tags))
                    _require(len(points) <= 128, "per-house point cap")
            total += len(points); _require(total <= 512, "global point cap")
            references.append(dict(id=expected["id"], area_id=area["id"],
                stock_row=expected["stock_row"], building_class=expected["building_class"],
                position=position, orientation=expected["orientation"], ce_points=points))
    return dict(schema=1, provenance="stock-xml-reference-only", houses=references)



def _labels(values):
    _require(type(values) is list and len(values) <= 32, "label cap")
    for value in values:
        _require(type(value) is str and re.fullmatch(r"[A-Za-z0-9_-]{1,96}", value),
                 "bounded reference label required")
    _require(len(set(values)) == len(values), "duplicate reference label")
    return values


def _bundle(manifest, refs, init, reference):
    _fields(manifest, "schema kind run_id request request_sha256 interfaces init_sha256 reference_sha256 gameplay_acceptance survey_complete native_watchdog_seconds max_outer_seconds acquisition_only ce_initialization bundle_scope")
    _require(type(manifest["schema"]) is int and manifest["schema"] == 1, "bundle schema")
    _require(manifest["kind"] == KIND, "bundle kind")
    _require(type(manifest["run_id"]) is str and re.fullmatch(r"[0-9a-f]{32}", manifest["run_id"]), "bundle nonce")
    _require(manifest["init_sha256"] == _sha(init) and
             manifest["reference_sha256"] == _sha(reference), "bundle source drift")
    req = _request(manifest["request"])
    _require(manifest["request_sha256"] == _sha(_encode(req)), "bundle request drift")
    _require(manifest["gameplay_acceptance"] is False and manifest["survey_complete"] is False
             and manifest["acquisition_only"] is True, "bundle scope contradiction")
    for key, number in (("native_watchdog_seconds", 60), ("max_outer_seconds", MAX_OUTER_SECONDS)):
        _require(type(manifest[key]) is int and manifest[key] == number, "bundle bound contradiction")
    _require(manifest["ce_initialization"] == "omitted" and
             manifest["bundle_scope"] == "overlay-three-files-into-separately-pinned-fresh-stock-mission",
             "bundle staging scope")
    interfaces = manifest["interfaces"]
    _require(type(interfaces) is dict and set(interfaces) == set(INTERFACES), "interface denominator")
    for item in interfaces.values():
        _fields(item, "sha256 bytes")
        _int(item["bytes"], 1, 2*1024*1024)
        _require(type(item["sha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", item["sha256"]),
                 "interface digest")
    _fields(refs, "schema provenance houses")
    _require(type(refs["schema"]) is int and refs["schema"] == 1 and
             refs["provenance"] == "stock-xml-reference-only", "reference scope")
    expected = [(area, item) for area in req["areas"] for item in area["expected"]]
    rows = refs["houses"]
    _require(type(rows) is list and len(rows) == len(expected), "reference house denominator")
    poses, total = set(), 0
    for ref, (area, item) in zip(rows, expected):
        _fields(ref, "id area_id stock_row building_class position orientation ce_points")
        for key in ("id", "stock_row", "building_class", "orientation"):
            _require(ref[key] == item[key], "reference/request identity mismatch")
        _int(ref["stock_row"], 0, 99999)
        _require(ref["area_id"] == area["id"], "reference area identity")
        _vec(ref["position"], 30000); _vec(ref["orientation"], 360)
        _require(_distance(ref["position"], area["center"]) <= (area["radius"]-.1)**2,
                 "reference outside reviewed area")
        pose = (ref["building_class"], *ref["position"])
        _require(pose not in poses, "duplicate physical house"); poses.add(pose)
        points = ref["ce_points"]
        _require(type(points) is list and len(points) <= 128, "reference point cap")
        total += len(points); _require(total <= 512, "global reference point cap")
        containers, locations = {}, set()
        for point in points:
            _fields(point, "container point_index local_position attributes categories tags")
            name = point["container"]
            _require(type(name) is str and 1 <= len(name) <= 96, "reference container name")
            ordinal = _int(point["point_index"], 0, 127)
            _require(ordinal == containers.get(name, 0), "container point denominator")
            containers[name] = ordinal+1
            _require(len(containers) <= 32, "reference container cap")
            local = _vec(point["local_position"], 1000)
            identity = (name, *local)
            _require(identity not in locations, "duplicate reference point"); locations.add(identity)
            attributes = point["attributes"]
            _require(type(attributes) is dict and "pos" in attributes and
                     set(attributes) <= {"pos", "range", "height", "flags"}, "reference attributes")
            _require(all(type(v) is str and len(v) <= 128 for v in attributes.values()),
                     "bounded raw attributes")
            _require(_xml_vec(attributes["pos"], 1000) == local, "raw/local point mismatch")
            for field in ("range", "height"):
                _number(float(attributes.get(field, "0")), 0, 100)
            _require(re.fullmatch(r"[0-9]{1,5}", attributes.get("flags", "0")), "reference flags")
            _labels(point["categories"]); _labels(point["tags"])
    return req


def _vector_literal(value):
    return '"' + " ".join(format(n, ".9g") for n in value) + '"'


def _build_code(request, references):
    lines = ["        HCIMArea area;", "        HCIMExpected expected;"]
    for area in request["areas"]:
        lines += ["        area = new HCIMArea;",
            '        area.Id = "'+area["id"]+'";',
            "        area.Center = "+_vector_literal(area["center"])+";",
            "        area.QueryRadius = "+format(area["radius"],".9g")+";"]
        for expected in (r for r in references["houses"] if r["area_id"] == area["id"]):
            lines += ["        expected = new HCIMExpected;",
                '        expected.Id = "'+expected["id"]+'";',
                '        expected.BuildingClass = "'+expected["building_class"]+'";',
                "        expected.Position = "+_vector_literal(expected["position"])+";",
                "        expected.Orientation = "+_vector_literal(expected["orientation"])+";"]
            for point in expected["ce_points"]:
                lines.append("        expected.Points.Insert("+_vector_literal(point["local_position"])+");")
            lines.append("        area.Expected.Insert(expected);")
        lines.append("        Areas.Insert(area);")
    return "\n".join(lines)


def _instrument(blob, hook):
    text = blob.decode("utf-8-sig"); masked = syntax._mask(text)
    _require("HCIM" not in text and "#" not in masked, "previous/incompatible mission instrumentation")
    mains = list(re.finditer(r"\bvoid\s+main\s*\(\s*\)\s*\{", masked))
    _require(len(mains) == 1, "one stock main required")
    opening = mains[0].end()-1; closing = syntax._block(masked, opening)
    pair = re.compile(r"\bHive\s+ce\s*=\s*CreateHive\s*\(\s*\)\s*;\s*"
        r"if\s*\(\s*ce\s*\)\s*(?:\{\s*)?ce\s*\.\s*InitOffline\s*\(\s*\)\s*;\s*(?:\})?")
    matches = list(pair.finditer(masked, opening+1, closing))
    _require(len(matches) == 1 and len(re.findall(r"\bInitOffline\s*\(",masked)) == 1
        and len(re.findall(r"\bCreateHive\s*\(",masked)) == 1, "exact inspected stock Hive pair required")
    classes = list(re.finditer(r"\bclass\s+CustomMission\s*:\s*MissionServer\s*\{",masked))
    _require(len(classes) == 1 and len(re.findall(r"\bCreateCustomMission\s*\(",masked)) == 1, "stock mission/factory required")
    class_open = classes[0].end()-1; class_close = syntax._block(masked,class_open)
    _require(not re.search(r"\bOnMissionFinish\s*\(",masked[class_open:class_close]), "existing finish hook needs review")
    match=matches[0]; end=text.index(";",match.start())+1
    edits=[(match.start(),match.end(),text[match.start():end]),
           (closing,closing,"\n    HCIMeasure.Begin();\n")]
    for start,end,replacement in sorted(edits,reverse=True):
        text=text[:start]+replacement+text[end:]
    emitted,count=staging._FACTORY.subn(rb"\g<1>HCIMMission\g<2>",text.encode())
    _require(count == 1, "exact stock factory return required")
    return emitted+b"\n"+hook.encode()


def generate_probe(init_bytes, map_positions, map_prototypes, request, interfaces, run_id=None):
    blobs = dict(zip(STOCK_NAMES, (
        _bytes(init_bytes,staging.MAX_INIT_BYTES), _bytes(map_positions,16*1024*1024),
        _bytes(map_prototypes,16*1024*1024))))
    run_id=secrets.token_hex(16) if run_id is None else run_id
    _require(type(run_id) is str and re.fullmatch(r"[0-9a-f]{32}",run_id), "hex nonce required")
    records=_interface_records(interfaces)
    req=_request(request,blobs); refs=_references(req,map_positions,map_prototypes)
    reference=_encode(refs); _bytes(reference,MAX_REFERENCE_BYTES)
    request_sha=_sha(_encode(req))
    substitutions={"@RUN@":run_id, "@REQUEST@":request_sha, "@REFERENCE@":_sha(reference),
        "@INIT@":_sha(init_bytes), "@POSITIONS@":_sha(map_positions), "@PROTOTYPES@":_sha(map_prototypes),
        "@BUILD@":_build_code(req,refs), "@WORLD@":req["world_name"], "@VERSION@":req["engine_version"],
        "@MISSING@":"\n".join('        State.missing_survey_data.Insert("'+v+'");' for v in MISSING)}
    hook=HOOK
    for key,value in substitutions.items():hook=hook.replace(key,value)
    emitted=_instrument(init_bytes,hook); _bytes(emitted,128*1024)
    manifest=dict(schema=1,kind=KIND,run_id=run_id,request=req,
        request_sha256=request_sha,interfaces=records,
        init_sha256=_sha(emitted),reference_sha256=_sha(reference),
        gameplay_acceptance=False,survey_complete=False,
        native_watchdog_seconds=60,max_outer_seconds=MAX_OUTER_SECONDS,
        acquisition_only=True,ce_initialization="omitted",
        bundle_scope="overlay-three-files-into-separately-pinned-fresh-stock-mission")
    marker=_encode(manifest); _bytes(marker,MAX_MANIFEST_BYTES)
    return {"init.c":emitted,REFERENCE:reference,MARKER:marker}


def _flag(value, expected):
    _require(_native_bool(value) == expected, "native flag mismatch")


def _samples(values, inputs):
    _require(type(values) is list and len(values) == len(inputs), "sample denominator mismatch")
    for index,(value,point) in enumerate(zip(values,inputs)):
        _fields(value,"id world_position local_return error_squared")
        _require(type(value["id"]) is int and value["id"] == index, "sample identity/order")
        _vec(value["world_position"],100000); _vec(value["local_return"],1000)
        measured=_number(value["error_squared"],0,.001**2)
        calculated=_distance(value["local_return"],point)
        _require(calculated <= .001**2 and abs(measured-calculated) <= 1e-6, "inverse transform mismatch")


def validate_receipt(receipt_bytes, files, *, outer_timed_out, outer_elapsed_seconds):
    _require(outer_timed_out is False, "actual non-timeout outer outcome required")
    _number(outer_elapsed_seconds,0,MAX_OUTER_SECONDS)
    _require(type(files) is dict and set(files) == {"init.c",MARKER,REFERENCE}, "exact three-file bundle required")
    init=_bytes(files["init.c"],128*1024); marker=_bytes(files[MARKER],MAX_MANIFEST_BYTES)
    reference=_bytes(files[REFERENCE],MAX_REFERENCE_BYTES)
    manifest=_decode_json(marker); refs=_decode_json(reference)
    req = _bundle(manifest, refs, init, reference)
    row=_decode_json(_bytes(receipt_bytes,MAX_RECEIPT_BYTES))
    _fields(row,"schema kind run_id world_name engine_version request_sha256 reference_sha256 stock_init_sha256 stock_positions_sha256 stock_prototypes_sha256 ce_point_provenance bbox_basis missing_survey_data server_context complete failed reason phase callbacks_detached entities_created gameplay_acceptance survey_complete engine_eligibility_verified frame_entries frame_exits queue_entries queue_exits elapsed_seconds areas")
    _require(type(row["schema"]) is int and row["schema"] == 1 and row["kind"] == KIND, "receipt schema")
    for field,value in (("run_id",manifest["run_id"]),("world_name",req["world_name"]),
        ("engine_version",req["engine_version"]),("request_sha256",manifest["request_sha256"]),
        ("reference_sha256",_sha(reference)),("stock_init_sha256",req["stock_sha256"]["init.c"]),
        ("stock_positions_sha256",req["stock_sha256"]["mapgrouppos.xml"]),
        ("stock_prototypes_sha256",req["stock_sha256"]["mapgroupproto.xml"]),
        ("ce_point_provenance","stock-xml-reference-only"),("bbox_basis","unqualified-native-return")):
        _require(row[field] == value, "receipt provenance mismatch: "+field)
    for field,wanted in (("server_context",True),("complete",True),("failed",False),
        ("callbacks_detached",True),("gameplay_acceptance",False),("survey_complete",False),
        ("engine_eligibility_verified",False)):
        _flag(row[field],wanted)
    _require(type(row["entities_created"]) is int and row["entities_created"] == 0, "no entities permitted")
    _require(row["reason"] == "" and row["phase"] == "complete" and row["missing_survey_data"] == list(MISSING), "incomplete/contradictory scope")
    _number(row["elapsed_seconds"],0,60)
    areas=req["areas"]; observed=row["areas"]
    _require(type(observed) is list and len(observed) == len(areas), "area denominator")
    frames=_int(row["frame_entries"],len(areas),2048)
    _require(type(row["frame_exits"]) is int and row["frame_exits"] == frames,"frame imbalance")
    queues=_int(row["queue_entries"],len(areas),128)
    _require(type(row["queue_exits"]) is int and row["queue_exits"] == queues,"queue imbalance")
    house_count=point_count=last_frame=0
    for area,actual in zip(areas,observed):
        _fields(actual,"id query_object_count house_count overflow frame_ordinal houses")
        _require(actual["id"] == area["id"],"area identity/order")
        objects=_int(actual["query_object_count"],0,256)
        houses_in_query=_int(actual["house_count"],0,objects); _flag(actual["overflow"],False)
        ordinal=_int(actual["frame_ordinal"],1,frames)
        _require(ordinal > last_frame,"distinct callback update intervals required"); last_frame=ordinal
        expected=[r for r in refs["houses"] if r["area_id"] == area["id"]]
        _require(len(expected) == len(area["expected"]),"reference denominator")
        houses=actual["houses"]
        _require(type(houses) is list and len(houses) == len(expected) and houses_in_query >= len(houses),"house denominator")
        for house,ref in zip(houses,expected):
            _fields(house,"id status matches building_class position orientation model_name collision_success collision_min collision_max clipping_min clipping_max clipping_radius transforms ce_points")
            _require(house["id"] == ref["id"] and house["building_class"] == ref["building_class"]
                and house["status"] == "measured" and type(house["matches"]) is int and house["matches"] == 1,"house identity/ambiguity")
            _pose(house["position"],house["orientation"],ref)
            name=house["model_name"]
            _require(type(name) is str and 1<=len(name)<=256 and all(ord(ch)>=32 for ch in name),"native model metadata")
            _flag(house["collision_success"],True)
            for prefix in ("collision","clipping"):
                low=_vec(house[prefix+"_min"],100000); high=_vec(house[prefix+"_max"],100000)
                _require(all(a < b for a,b in zip(low,high)),"native bounds unavailable/inverted")
            _require(_number(house["clipping_radius"],0,100000)>0,"native clipping radius unavailable")
            _samples(house["transforms"],PROBES)
            _samples(house["ce_points"],[p["local_position"] for p in ref["ce_points"]])
            house_count+=1; point_count+=len(ref["ce_points"])
    return dict(schema=1,status="measurement-acquisition-complete",run_id=row["run_id"],
        gameplay_acceptance=False,survey_complete=False,engine_eligibility_verified=False,
        bbox_basis="unqualified-native-return",ce_point_provenance="stock-xml-reference-only",
        area_count=len(areas),house_count=house_count,ce_reference_point_count=point_count,
        missing_survey_data=list(MISSING),receipt_sha256=_sha(receipt_bytes),
        bundle_manifest_sha256=_sha(marker),receipt=row)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest="command",required=True)
    prepare=sub.add_parser("prepare")
    prepare.add_argument("--stock-dir",type=Path,required=True)
    prepare.add_argument("--scripts-root",type=Path,required=True)
    prepare.add_argument("--request",type=Path,required=True)
    prepare.add_argument("--out",type=Path,required=True)
    validate=sub.add_parser("validate")
    validate.add_argument("--bundle-dir",type=Path,required=True)
    validate.add_argument("--receipt",type=Path,required=True)
    validate.add_argument("--outer-outcome",choices=("completed","timeout"),required=True)
    validate.add_argument("--outer-elapsed-seconds",type=float,required=True)
    args=parser.parse_args(argv)
    try:
        if args.command == "prepare":
            stock=_safe(args.stock_dir); root=_safe(args.scripts_root); out=_safe(args.out)
            for source in (stock,root,_safe(args.request)):
                _require(out != source and out not in source.parents and source not in out.parents,"output/input overlap")
            _require(not out.exists(),"fresh output bundle required")
            request=_decode_json(_read(args.request,32768))
            inputs=[_read(stock/name,staging.MAX_INIT_BYTES if name=="init.c" else 16*1024*1024) for name in STOCK_NAMES]
            interfaces={name:_read(root/name,2*1024*1024) for name in INTERFACES}
            files=generate_probe(*inputs,request,interfaces)
            out.mkdir(parents=True,exist_ok=False)
            for name,data in files.items():
                with (_safe(out/name)).open("xb") as stream:stream.write(data)
                _require(_read(out/name,len(data)) == data,"bundle readback mismatch")
            print(json.dumps(dict(status="bundle-prepared-not-executed",files=sorted(files),gameplay_acceptance=False)))
        else:
            root=_safe(args.bundle_dir)
            expected={"init.c",MARKER,REFERENCE}
            with os.scandir(root) as entries:
                seen=set()
                for entry in entries:
                    _require(entry.name in expected and entry.name not in seen, "unexpected bundle entry")
                    _require(entry.is_file(follow_symlinks=False), "regular bundle files required")
                    seen.add(entry.name)
                _require(seen == expected, "missing bundle entry")
            files={name:_read(root/name,128*1024 if name=="init.c" else
                MAX_MANIFEST_BYTES if name==MARKER else MAX_REFERENCE_BYTES)
                for name in ("init.c",MARKER,REFERENCE)}
            report=validate_receipt(_read(args.receipt,MAX_RECEIPT_BYTES),files,
                outer_timed_out=args.outer_outcome=="timeout",
                outer_elapsed_seconds=args.outer_elapsed_seconds)
            print(json.dumps({k:v for k,v in report.items() if k!="receipt"},sort_keys=True))
    except (ValueError,OSError,KeyError,TypeError,UnicodeError,RecursionError) as exc:
        parser.exit(1,str(exc)+"\n")


HOOK = "\n// DISPOSABLE acquisition only. No placement, room/door clearance or CE eligibility.\nclass HCIMExpected\n{\n    string Id;\n    string BuildingClass;\n    vector Position;\n    vector Orientation;\n    ref array<vector> Points = new array<vector>;\n}\nclass HCIMArea\n{\n    string Id;\n    vector Center;\n    float QueryRadius;\n    ref array<ref HCIMExpected> Expected = new array<ref HCIMExpected>;\n}\nclass HCIMSample\n{\n    int id;\n    ref array<float> world_position = new array<float>;\n    ref array<float> local_return = new array<float>;\n    float error_squared;\n}\nclass HCIMHouse\n{\n    string id;\n    string status = \"pending\";\n    int matches;\n    string building_class;\n    ref array<float> position = new array<float>;\n    ref array<float> orientation = new array<float>;\n    string model_name;\n    bool collision_success;\n    ref array<float> collision_min = new array<float>;\n    ref array<float> collision_max = new array<float>;\n    ref array<float> clipping_min = new array<float>;\n    ref array<float> clipping_max = new array<float>;\n    float clipping_radius;\n    ref array<ref HCIMSample> transforms = new array<ref HCIMSample>;\n    ref array<ref HCIMSample> ce_points = new array<ref HCIMSample>;\n}\nclass HCIMAreaResult\n{\n    string id;\n    int query_object_count;\n    int house_count;\n    bool overflow;\n    int frame_ordinal;\n    ref array<ref HCIMHouse> houses = new array<ref HCIMHouse>;\n}\nclass HCIMReceipt\n{\n    int schema = 1;\n    string kind = \"native-real-house-measurement-acquisition\";\n    string run_id = \"@RUN@\";\n    string world_name;\n    string engine_version;\n    string request_sha256 = \"@REQUEST@\";\n    string reference_sha256 = \"@REFERENCE@\";\n    string stock_init_sha256 = \"@INIT@\";\n    string stock_positions_sha256 = \"@POSITIONS@\";\n    string stock_prototypes_sha256 = \"@PROTOTYPES@\";\n    string ce_point_provenance = \"stock-xml-reference-only\";\n    string bbox_basis = \"unqualified-native-return\";\n    ref array<string> missing_survey_data = new array<string>;\n    bool server_context;\n    bool complete;\n    bool failed;\n    string reason;\n    string phase = \"begin\";\n    bool callbacks_detached;\n    int entities_created = 0;\n    bool gameplay_acceptance = false;\n    bool survey_complete = false;\n    bool engine_eligibility_verified = false;\n    int frame_entries;\n    int frame_exits;\n    int queue_entries;\n    int queue_exits;\n    float elapsed_seconds;\n    ref array<ref HCIMAreaResult> areas = new array<ref HCIMAreaResult>;\n}\nclass HCIMeasure\n{\n    static ref HCIMReceipt State;\n    static ref array<ref HCIMArea> Areas;\n    static bool Done;\n    static bool Armed;\n    static float Started;\n    static float LastTime;\n    static int NextArea;\n    static int LastAreaFrame;\n\n    static void Build()\n    {\n        Areas = new array<ref HCIMArea>;\n@BUILD@\n    }\n\n    static void Begin()\n    {\n        if (State || Done) return;\n        if (!GetGame()) return;\n        if (!GetGame().IsServer()) return;\n        if (FileExist(\"$profile:hc-interior-measurement-result.json\"))\n        {\n            Done = true;\n            Print(\"[HC Interior Measure] REJECT stale receipt run=@RUN@\");\n            return;\n        }\n        State = new HCIMReceipt;\n        State.server_context = GetGame().IsServer();\n        GetGame().GetWorldName(State.world_name);\n        GetGame().GetVersion(State.engine_version);\n        Started = GetGame().GetTickTime();\n        LastTime = Started;\n@MISSING@\n        Build();\n        Save();\n        if (Done) return;\n        if (State.world_name != \"@WORLD@\")\n        {\n            Fail(\"world-mismatch\");\n            return;\n        }\n        if (State.engine_version != \"@VERSION@\")\n        {\n            Fail(\"engine-version-mismatch\");\n            return;\n        }\n        Armed = true;\n        GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(Tick, 100, true);\n        if (!GetGame().GetUpdateQueue(CALL_CATEGORY_SYSTEM).Insert(Frame))\n        {\n            Fail(\"frame-registration-failed\");\n            return;\n        }\n        Print(\"[HC Interior Measure] BEGIN run=@RUN@\");\n    }\n\n    static void Detach()\n    {\n        if (Armed)\n        {\n            Armed = false;\n            GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).Remove(Tick);\n            GetGame().GetUpdateQueue(CALL_CATEGORY_SYSTEM).Remove(Frame);\n        }\n        State.callbacks_detached = GetGame().GetUpdateQueue(CALL_CATEGORY_SYSTEM).Count(Frame) == 0;\n        if (!State.callbacks_detached)\n        {\n            State.complete = false;\n            State.failed = true;\n            State.phase = \"failed\";\n            State.reason = \"frame-removal-not-observed\";\n        }\n    }\n\n    static void Save()\n    {\n        if (!State) return;\n        string encoded;\n        string error;\n        bool made = JsonFileLoader<HCIMReceipt>.MakeData(State, encoded, error, false);\n        if (made && encoded.Length() <= 262144)\n        {\n            FileHandle handle = OpenFile(\"$profile:hc-interior-measurement-result.json\", FileMode.WRITE);\n            if (handle != 0)\n            {\n                FPrint(handle, encoded);\n                CloseFile(handle);\n                return;\n            }\n        }\n        Done = true;\n        State.failed = true;\n        State.complete = false;\n        State.phase = \"failed\";\n        State.reason = \"receipt-serialization-or-write-failed\";\n        Detach();\n        Print(\"[HC Interior Measure] FAIL receipt-serialization-or-write-failed run=@RUN@\");\n    }\n\n    static void Fail(string reason)\n    {\n        if (!State || Done) return;\n        Done = true;\n        State.failed = true;\n        State.complete = false;\n        State.phase = \"failed\";\n        State.reason = reason;\n        Detach();\n        Save();\n        Print(\"[HC Interior Measure] FAIL \" + reason + \" run=@RUN@\");\n    }\n\n    static bool Finite(float value, float bound)\n    {\n        if (value != value) return false;\n        if (value < -bound) return false;\n        if (value > bound) return false;\n        return true;\n    }\n\n    static bool VecFinite(vector value, float bound)\n    {\n        for (int i = 0; i < 3; i++)\n        {\n            if (!Finite(value[i], bound)) return false;\n        }\n        return true;\n    }\n\n    static float Squared(vector left, vector right)\n    {\n        float result = 0;\n        for (int i = 0; i < 3; i++)\n        {\n            float delta = left[i] - right[i];\n            result = result + delta * delta;\n        }\n        return result;\n    }\n\n    static void Components(vector value, array<float> target)\n    {\n        for (int i = 0; i < 3; i++) target.Insert(value[i]);\n    }\n\n    static bool Pose(vector position, vector orientation, HCIMExpected expected)\n    {\n        if (!VecFinite(position, 30000)) return false;\n        if (!VecFinite(orientation, 360)) return false;\n        if (Squared(position, expected.Position) > 0.01) return false;\n        for (int i = 0; i < 3; i++)\n        {\n            float delta = orientation[i] - expected.Orientation[i];\n            if (delta > 180) delta = delta - 360;\n            if (delta > 180) delta = delta - 360;\n            if (delta < -180) delta = delta + 360;\n            if (delta < -180) delta = delta + 360;\n            if (delta < -0.1) return false;\n            if (delta > 0.1) return false;\n        }\n        return true;\n    }\n\n    static bool Check()\n    {\n        if (!State || Done) return false;\n        float now = GetGame().GetTickTime();\n        State.elapsed_seconds = now - Started;\n        if (!Finite(now, 1000000000))\n        {\n            Fail(\"invalid-clock\");\n            return false;\n        }\n        if (now < LastTime || State.elapsed_seconds > 60)\n        {\n            Fail(\"watchdog-or-clock\");\n            return false;\n        }\n        if (State.frame_entries > 2048 || State.queue_entries > 128)\n        {\n            Fail(\"callback-overflow\");\n            return false;\n        }\n        LastTime = now;\n        return true;\n    }\n\n    static void Frame(float timeslice)\n    {\n        if (Done) return;\n        State.frame_entries++;\n        State.frame_exits++;\n        Check();\n    }\n\n    static bool Bounds(vector low, vector high)\n    {\n        if (!VecFinite(low, 100000)) return false;\n        if (!VecFinite(high, 100000)) return false;\n        for (int i = 0; i < 3; i++)\n        {\n            if (low[i] >= high[i]) return false;\n        }\n        return true;\n    }\n\n    static bool Sample(House house, vector localPoint, int ordinal, array<ref HCIMSample> output)\n    {\n        HCIMSample sample = new HCIMSample;\n        sample.id = ordinal;\n        vector worldPosition = house.ModelToWorld(localPoint);\n        vector localReturn = house.WorldToModel(worldPosition);\n        Components(worldPosition, sample.world_position);\n        Components(localReturn, sample.local_return);\n        sample.error_squared = Squared(localReturn, localPoint);\n        output.Insert(sample);\n        if (!VecFinite(worldPosition, 100000)) return false;\n        if (!VecFinite(localReturn, 1000)) return false;\n        if (!Finite(sample.error_squared, 0.000001)) return false;\n        return sample.error_squared >= 0;\n    }\n\n    static bool Capture(House house, HCIMExpected expected, HCIMHouse row)\n    {\n        row.building_class = house.GetType();\n        vector position = house.GetPosition();\n        vector orientation = house.GetOrientation();\n        Components(position, row.position);\n        Components(orientation, row.orientation);\n        row.model_name = house.GetModelName();\n        if (!Pose(position, orientation, expected)) return false;\n        if (row.model_name.Length() < 1 || row.model_name.Length() > 256) return false;\n        vector collision[2];\n        row.collision_success = house.GetCollisionBox(collision);\n        Components(collision[0], row.collision_min);\n        Components(collision[1], row.collision_max);\n        if (!row.collision_success) return false;\n        if (!Bounds(collision[0], collision[1])) return false;\n        vector clipping[2];\n        row.clipping_radius = house.ClippingInfo(clipping);\n        Components(clipping[0], row.clipping_min);\n        Components(clipping[1], row.clipping_max);\n        if (!Bounds(clipping[0], clipping[1])) return false;\n        if (!Finite(row.clipping_radius, 100000)) return false;\n        if (row.clipping_radius <= 0) return false;\n        if (!Sample(house, \"0 0 0\", 0, row.transforms)) return false;\n        if (!Sample(house, \"1 0 0\", 1, row.transforms)) return false;\n        if (!Sample(house, \"0 1 0\", 2, row.transforms)) return false;\n        if (!Sample(house, \"0 0 1\", 3, row.transforms)) return false;\n        for (int i = 0; i < expected.Points.Count(); i++)\n        {\n            if (!Sample(house, expected.Points[i], i, row.ce_points)) return false;\n        }\n        // A pose change during capture invalidates the measurements.\n        if (Squared(house.GetPosition(), position) > 0.000001) return false;\n        vector finalOrientation = house.GetOrientation();\n        for (int component = 0; component < 3; component++)\n        {\n            if (finalOrientation[component] != orientation[component]) return false;\n        }\n        return true;\n    }\n\n    static void Acquire(HCIMArea area, HCIMAreaResult result)\n    {\n        array<Object> objects = new array<Object>;\n        array<CargoBase> cargos = new array<CargoBase>;\n        // The partial receipt exists BEFORE this potentially blocking native read.\n        GetGame().GetObjectsAtPosition3D(area.Center, area.QueryRadius, objects, cargos);\n        result.query_object_count = objects.Count();\n        if (objects.Count() > 256)\n        {\n            result.overflow = true;\n            Fail(\"query-object-overflow\");\n            return;\n        }\n        House house;\n        for (int i = 0; i < objects.Count(); i++)\n        {\n            house = House.Cast(objects[i]);\n            if (house) result.house_count++;\n        }\n        foreach (HCIMExpected expected : area.Expected)\n        {\n            HCIMHouse row = new HCIMHouse;\n            row.id = expected.Id;\n            result.houses.Insert(row);\n            House matched;\n            for (int j = 0; j < objects.Count(); j++)\n            {\n                house = House.Cast(objects[j]);\n                if (!house) continue;\n                if (house.GetType() != expected.BuildingClass) continue;\n                if (!Pose(house.GetPosition(), house.GetOrientation(), expected)) continue;\n                row.matches++;\n                matched = house;\n            }\n            if (row.matches != 1)\n            {\n                row.status = \"missing-or-ambiguous\";\n                Fail(\"house-match-not-unique\");\n                return;\n            }\n            row.status = \"capturing\";\n            if (!Capture(matched, expected, row))\n            {\n                row.status = \"native-measurement-invalid\";\n                Fail(\"native-measurement-invalid\");\n                return;\n            }\n            row.status = \"measured\";\n            if (!Check()) return;\n        }\n    }\n\n    static void Finish()\n    {\n        if (!Check()) return;\n        if (State.frame_entries != State.frame_exits)\n        {\n            Fail(\"frame-imbalance\");\n            return;\n        }\n        if (State.queue_entries != State.queue_exits)\n        {\n            Fail(\"queue-imbalance\");\n            return;\n        }\n        Done = true;\n        State.complete = true;\n        State.phase = \"complete\";\n        Detach();\n        Save();\n        if (!State.failed) Print(\"[HC Interior Measure] ACQUIRED run=@RUN@; no survey/gameplay acceptance\");\n    }\n\n    static void Tick()\n    {\n        if (Done) return;\n        State.queue_entries++;\n        if (!Check()) return;\n        if (State.frame_entries <= LastAreaFrame)\n        {\n            State.queue_exits++;\n            return;\n        }\n        HCIMArea area = Areas[NextArea];\n        HCIMAreaResult result = new HCIMAreaResult;\n        result.id = area.Id;\n        result.frame_ordinal = State.frame_entries;\n        State.areas.Insert(result);\n        State.phase = \"query-area:\" + area.Id;\n        Save();\n        if (Done) return;\n        Acquire(area, result);\n        State.queue_exits++;\n        if (Done) return;\n        LastAreaFrame = State.frame_entries;\n        NextArea++;\n        if (!Check()) return;\n        if (NextArea == Areas.Count())\n        {\n            Finish();\n            return;\n        }\n        State.phase = \"waiting-next-frame\";\n        Save();\n    }\n\n    static void Interrupt()\n    {\n        if (!State || Done) return;\n        Fail(\"mission-interrupted\");\n    }\n}\nclass HCIMMission : CustomMission\n{\n    override void OnMissionFinish()\n    {\n        HCIMeasure.Interrupt();\n        super.OnMissionFinish();\n    }\n}\n"

if __name__ == '__main__':
    main()
