"""Bounded CE-disabled death-selection diagnostic; NEVER launch or install.

generate_probe(init_bytes, request, interfaces, run_id=None) returns a five-file
byte bundle. Overlay init.c only into a fresh, separately pinned stock mission;
pack addon/ separately with prefix HCDeathSelectionProbe and load explicitly.
inspect_interfaces(root) reads installed declarations. validate_receipt accepts
one byte snapshot and requires the actual external outcome/duration. These are
correlations, not authentication. No ragdoll/render/gameplay acceptance follows.
Native cap 60s; external total cap 180s including startup and cleanup; two cases,
one victim plus one owned Stone source, 2s deletion windows, 16 samples/case.
No process launch, assets or balance/config installation. stage() is the only
filesystem write: it creates a fresh directory of the bundle plus the packed
probe PBO and never launches anything.

Optional request fields (absent = the original probe text, byte for byte):
spawn_profile names the victim creation flags (initai-only reproduces the
unexplained run-065 access violation; surface-initai matches vanilla debug and
the run-047 spawn; surface-only has no AI agent and bisects the crash).
selection "policy" adds the production HCInfectedDeathPolicy file and replaces
the forced case-1 IMPULSE with that policy's decision for a heavy frontal
torso kill. None of this establishes DayZ behavior until a real run is observed.
"""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import re
import os
import secrets
import stat
import struct

from tools.setup import diagnostic_mission as staging
from tools.setup import native_startup_probe as syntax
from tools.setup.infected_death_probe import _read, _sha, _encode, _decode_json, _number, _native_bool

MARKER = ".hc-death-selection-probe.json"
PROVIDER = "addon/scripts/4_World/HCDeathSelection.c"
CONFIG = "addon/config.cpp"
PREFIX = "addon/$PBOPREFIX$"
RESULT = "hc-death-selection-result.json"
KIND = "native-death-selection-observations"
CASES = ("vanilla", "impulse-selection")
CASES_POLICY = ("vanilla", "policy-selection")
POLICY = "addon/scripts/4_World/HCInfectedDeathPolicy.c"
STAGED_PBO = "@HCDeathSelectionProbe/addons/hc-death-selection.pbo"
POLICY_SIGNATURE = ("static int SelectDeathType(int nativeType, bool finisher, int ammoHitAnimation, "
                    "bool heavyOverride, string zone, float hitDirection)")
POLICY_FORBIDDEN = ("StartCommand_Death", "dBodyApply", "SetPosition", "PhysicsSet", "SetHealth", "HCDS")
MAX_POLICY_BYTES = 64*1024
SPAWN_PROFILES = {"initai-only": "ECE_INITAI",
                  "surface-initai": "ECE_PLACE_ON_SURFACE|ECE_INITAI",
                  "surface-only": "ECE_PLACE_ON_SURFACE"}
BASE_REQUEST = "world_name engine_version stock_init_sha256 victim_position source_position".split()
OPTIONAL_REQUEST = ("spawn_profile", "selection")
CASE_FIELDS = ("index name spawn_frame spawn_queue damage_frame damage_queue command_frame delete_frame "
               "delete_queue cleanup_frame cleanup_queue spawn_elapsed damage_elapsed command_elapsed "
               "delete_elapsed cleanup_elapsed damage_calls eval_calls before_type after_type command_type "
               "hit_direction command_direction ammo zone ammo_physics_flag ammo_damage cleanup_confirmed samples")
POLICY_FRONT_HALF_ANGLE = 60
MAX_BYTES = 256*1024
MAX_OUTER_SECONDS = 180
ENGINE_VERSION = "1.30.164289.70"
INTERFACES = {
    "3_Game/Entities/DayZInfected.c": ("ANIM_DEATH_DEFAULT = 0", "ANIM_DEATH_IMPULSE = 1",
        "COMMANDID_DEATH", "class DayZInfected extends DayZCreatureAI"),
    "3_Game/Entities/DayZAnimal.c": ("GetBoneIndexByName(string pBoneName)", "IsDeathProcessed()"),
    "3_Game/Entities/DayZInfectedType.c": ('m_DefaultHitComponent = "Torso"',),
    "4_World/Entities/Creatures/Infected/ZombieBase.c": (
        "bool EvaluateDeathAnimationEx(EntityAI pSource, ZombieHitData data, out int pAnimType, out float pAnimHitDir)",
        "void CommandHandler(float pDt, int pCurrentCommandID, bool pCurrentCommandFinished)",
        "StartCommand_Death(m_DeathType, m_DamageHitDirection)", "ComputeHitDirectionAngle",
        "override bool IsBeingBackstabbed()"),
    "3_Game/Entities/Object.c": (
        "ProcessDirectDamage(int damageType, EntityAI source, string componentName, string ammoName",
        "GetDamageZones(out TStringArray dmgZones)", "GetDamageZonePos(string zoneName)",
        "GetBonePositionWS(int pivot)", "GetHealth(string zoneName, string healthType)"),
    "4_World/Plugins/PluginBase/PluginDiagMenu/PluginDiagMenu.c": (
        'ProcessDirectDamage(DamageType.CUSTOM, player, "", "MeleeFist", "0 0 0")',),
    "3_Game/Global/Game.c": ("GetTickTime()", "CreateObjectEx(", "ObjectDelete(",
        "GetWorldName( out string world_name )", "GetVersion( out string version )",
        "GetPlayerIndentities( out array<PlayerIdentity> identities )", "ConfigGetFloat(string path)",
        "SurfaceY(float x, float z)"),
    "3_Game/DayZGame.c": ("GetCallQueue(CALL_CATEGORY_SYSTEM).Tick(timeslice)",
        "GetUpdateQueue(CALL_CATEGORY_SYSTEM).Invoke(timeslice)"),
    "3_Game/Hive/Hive.c": ("proto native Hive CreateHive();", "proto native void InitOffline();"),
    "3_Game/tools/JsonFileLoader.c": ("static bool SaveFile(string filename, T data, out string errorMessage)",),
}

def _need(condition, message):
    if not condition:
        raise ValueError(message)

def _bytes(blob, limit=MAX_BYTES):
    _need(type(blob) is bytes and 0 < len(blob) <= limit, "bounded nonempty byte snapshot required")
    return blob

def _json(blob):
    value = _decode_json(_bytes(blob))
    nodes = 0
    def visit(v, depth):
        nonlocal nodes
        nodes += 1
        _need(depth <= 12 and nodes <= 4096, "JSON depth/node bound")
        if type(v) is dict:
            _need(len(v) <= 64 and all(type(k) is str and len(k) <= 128 for k in v), "JSON keys")
            for item in v.values(): visit(item, depth+1)
        elif type(v) is list:
            _need(len(v) <= 128, "JSON array bound")
            for item in v: visit(item, depth+1)
        elif type(v) is str:
            _need(len(v) <= 1024, "JSON text bound")
        elif type(v) is float:
            _need(math.isfinite(v), "nonfinite JSON")
    visit(value, 0)
    return value

def _fields(value, names):
    _need(type(value) is dict and set(value) == set(names.split()), "exact fields required")

def _flag(value, wanted):
    _need(_native_bool(value) == wanted, "native boolean mismatch")

def _int(value, low, high):
    _need(type(value) is int and low <= value <= high, "bounded exact integer required")
    return value

def _vector(value):
    _need(type(value) is list and len(value) == 3, "vector required")
    for n in value: _number(n, -100000, 100000)
    return value

def _request(req, stock=None):
    _need(type(req) is dict and set(BASE_REQUEST) <= set(req) and set(req) <= set(BASE_REQUEST) | set(OPTIONAL_REQUEST),
          "exact fields required")
    if "spawn_profile" in req:
        _need(type(req["spawn_profile"]) is str and req["spawn_profile"] in SPAWN_PROFILES, "known spawn profile")
    if "selection" in req:
        _need(type(req["selection"]) is str and req["selection"] == "policy", "known selection mode")
    _need(req["world_name"] == "chernarusplus" and req["engine_version"] == ENGINE_VERSION,
          "fixed inspected world/build required")
    _need(type(req["stock_init_sha256"]) is str and re.fullmatch("[0-9a-f]{64}",req["stock_init_sha256"]),
          "stock hash required")
    if stock is not None:
        _need(_sha(stock) == req["stock_init_sha256"], "stock provenance mismatch")
    a, b = _vector(req["victim_position"]), _vector(req["source_position"])
    _need(all(1 <= v[i] <= 100000 for v in (a,b) for i in (0,2)), "world coordinates")
    _need(1 <= sum((a[i]-b[i])**2 for i in range(3)) <= 25, "source distance 1..5m")
    return req

def _policy_mode(req):
    return req.get("selection") == "policy"

def _cases(req):
    return CASES_POLICY if _policy_mode(req) else CASES

def _read_policy_file(value):
    """Bounded no-follow read of the policy source; unlike staging._safe_path this may live in the checkout."""
    path = Path(value).absolute()
    _need(".." not in path.parts, "policy path traversal forbidden")
    _need(not any(p.is_symlink() for p in (path, *path.parents)), "policy symlink paths forbidden")
    info = staging.lstat_at(path)
    _need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size <= MAX_POLICY_BYTES,
          "bounded regular policy file required")
    fd = staging.open_file_at(path, os.O_RDONLY | getattr(os, "O_BINARY", 0))
    with os.fdopen(fd, "rb") as stream:
        _need(staging._identity(os.fstat(stream.fileno())) == staging._identity(info), "policy changed")
        data = stream.read(MAX_POLICY_BYTES + 1)
    _need(len(data) == info.st_size and staging._identity(staging.lstat_at(path)) == staging._identity(info),
          "policy changed or size exceeded")
    return data

def _policy_source(blob):
    _need(type(blob) is bytes and 0 < len(blob) <= MAX_POLICY_BYTES, "bounded policy source required")
    try: text = blob.decode("utf-8")
    except UnicodeError as exc: raise ValueError("policy UTF-8 required") from exc
    flat = " ".join(text.split())
    _need("class HCInfectedDeathPolicy" in flat and POLICY_SIGNATURE in flat, "policy class and selector required")
    _need(not any(token in text for token in POLICY_FORBIDDEN), "policy contains forbidden calls")
    return blob

def inspect_interfaces(root):
    return {name: _read(Path(root)/name, 2*1024*1024) for name in INTERFACES}

def _interfaces(blobs):
    _need(type(blobs) is dict and set(blobs) == set(INTERFACES), "exact interface set")
    records = {}
    total = 0
    for name, tokens in INTERFACES.items():
        data = _bytes(blobs[name], 2*1024*1024); total += len(data)
        _need(total <= 8*1024*1024, "interface total bound")
        try: text = " ".join(data.decode("utf-8-sig").split())
        except UnicodeError as exc: raise ValueError("invalid interface UTF-8") from exc
        _need(all(" ".join(t.split()) in text for t in tokens), "installed interface mismatch: "+name)
        records[name] = dict(bytes=len(data), sha256=_sha(data))
    return records

def _instrument(blob):
    try: text = blob.decode("utf-8-sig")
    except UnicodeError as exc: raise ValueError("stock UTF-8 required") from exc
    masked = syntax._mask(text)
    _need("HCDS" not in text and "#" not in masked, "previous/preprocessed instrumentation")
    mains = list(re.finditer(r"\bvoid\s+main\s*\(\s*\)\s*\{",masked))
    classes = list(re.finditer(r"\bclass\s+CustomMission\s*:\s*MissionServer\s*\{",masked))
    _need(len(mains) == len(classes) == 1, "one stock main/class")
    opening = mains[0].end()-1; closing = syntax._block(masked,opening)
    co = classes[0].end()-1; cc = syntax._block(masked,co)
    _need(not re.search(r"\bOnMissionFinish\s*\(",masked[co:cc]), "existing finish override")
    pair = re.compile(r"\bHive\s+ce\s*=\s*CreateHive\s*\(\s*\)\s*;\s*"
        r"if\s*\(\s*ce\s*\)\s*(?:\{\s*)?ce\s*\.\s*InitOffline\s*\(\s*\)\s*;\s*(?:\})?")
    matches = list(pair.finditer(masked,opening+1,closing))
    _need(len(matches) == 1 and len(re.findall(r"\bInitOffline\s*\(",masked)) == 1
          and len(re.findall(r"\bCreateHive\s*\(",masked)) == 1, "exact stock Hive pair")
    _need(len(re.findall(r"\bCreateCustomMission\s*\(",masked)) == 1, "one factory")
    match = matches[0]; end = text.index(";",match.start())+1
    for start, stop, replacement in sorted([
        (match.start(),match.end(),text[match.start():end]+"\n    if (!ce) return;\n"),
        (closing,closing,"\n    HCDS.Begin();\n")], reverse=True):
        text = text[:start]+replacement+text[stop:]
    emitted, count = staging._FACTORY.subn(rb"\g<1>HCDSMission\g<2>",text.encode())
    _need(count == 1, "stock factory")
    return emitted + b"""
class HCDSMission : CustomMission
{
    override void OnMissionFinish()
    {
        HCDS.Interrupt();
        super.OnMissionFinish();
    }
}
"""

def generate_probe(init_bytes, request, interfaces, run_id=None, policy_source=None):
    init_bytes = _bytes(init_bytes,staging.MAX_INIT_BYTES)
    req = copy.deepcopy(_request(request,init_bytes))
    policy = _policy_mode(req)
    _need(policy == (policy_source is not None), "policy source exactly when selection is policy")
    if policy: _policy_source(policy_source)
    run_id = secrets.token_hex(16) if run_id is None else run_id
    _need(type(run_id) is str and re.fullmatch("[0-9a-f]{32}",run_id), "hex run nonce")
    records = _interfaces(interfaces)
    replacements = {"@RUN@":run_id, "@REQUEST@":_sha(_encode(req))}
    for key, field in (("@VICTIM@","victim_position"),("@SOURCE@","source_position")):
        replacements[key] = " ".join(format(n,".9g") for n in req[field])
    # The inspected normal server rejects a guard continuation beginning with
    # ||/&& (native compile 062). Keep each logical expression on one line.
    native = re.sub(r'\n\s*(\|\||&&)\s*', r' \1 ', NATIVE)
    replacements.update(_variant(req))
    for key, value in replacements.items(): native = native.replace(key,value)
    files = {"init.c":_instrument(init_bytes), PROVIDER:native.encode(),
             CONFIG:ADDON.encode(), PREFIX:b"HCDeathSelectionProbe"}
    if policy: files[POLICY] = policy_source
    manifest = dict(schema=1,kind=KIND,run_id=run_id,request=req,
        request_sha256=_sha(_encode(req)),interfaces=records,
        ce_initialization="omitted",max_outer_seconds=180,native_watchdog_seconds=60,
        max_owned_entities=2,cases=list(_cases(req)),
        files={n:dict(bytes=len(v),sha256=_sha(v)) for n,v in files.items()})
    files[MARKER] = _encode(manifest)
    for v in files.values(): _bytes(v)
    _need(sum(map(len,files.values())) <= MAX_BYTES, "bundle total bound")
    return files

def _variant(req):
    """Template substitutions; the absent-optional values reproduce the original text exactly."""
    flags = SPAWN_PROFILES[req.get("spawn_profile", "initai-only")]
    values = {"@VFLAGS@":flags, "@CASE1NAME@":_cases(req)[1], "@CASEFIELDS@":"", "@PREDAMAGE@":"",
        "@SELECT@":"if (HCDS.Row.index == 1) pAnimType = DayZInfectedDeathAnims.ANIM_DEATH_IMPULSE;"}
    if _policy_mode(req):
        values["@CASEFIELDS@"] = "\n    int policy_type = -1;\n    int heavy_override;"
        values["@PREDAMAGE@"] = ("\n        if (Row.index == 1)\n        {\n"
            "            Victim.m_HeavyHitOverride = true;\n            Row.heavy_override = 1;\n        }")
        values["@SELECT@"] = ("if (HCDS.Row.index == 1)\n        {\n"
            "            int ammoHitAnimation = GetGame().ConfigGetInt(\"cfgAmmo \" + data.m_AmmoType + \" hitAnimation\");\n"
            "            HCDS.Row.policy_type = HCInfectedDeathPolicy.SelectDeathType(pAnimType, IsBeingBackstabbed(), "
            "ammoHitAnimation, m_HeavyHitOverride, data.m_DamageZone, pAnimHitDir);\n"
            "            pAnimType = HCDS.Row.policy_type;\n        }")
    return values

def _bundle(files):
    _need(type(files) is dict and MARKER in files, "exact bundle")
    manifest = _json(_bytes(files[MARKER]))
    _need(type(manifest.get("request")) is dict, "manifest request")
    names = {"init.c",PROVIDER,CONFIG,PREFIX,MARKER}
    if _policy_mode(manifest["request"]): names.add(POLICY)
    _need(set(files) == names, "exact bundle")
    _need(sum(len(_bytes(v)) for v in files.values()) <= MAX_BYTES, "bundle bound")
    _fields(manifest,"schema kind run_id request request_sha256 interfaces ce_initialization max_outer_seconds native_watchdog_seconds max_owned_entities cases files")
    _need(type(manifest["schema"]) is int and manifest["schema"] == 1 and manifest["kind"] == KIND, "manifest schema")
    _need(type(manifest["run_id"]) is str and re.fullmatch("[0-9a-f]{32}",manifest["run_id"]), "manifest nonce")
    _request(manifest["request"])
    _need(manifest["request_sha256"] == _sha(_encode(manifest["request"])), "request pin")
    for k, wanted in (("ce_initialization","omitted"),("max_outer_seconds",180),
        ("native_watchdog_seconds",60),("max_owned_entities",2),("cases",list(_cases(manifest["request"])))):
        _need(manifest[k] == wanted and type(manifest[k]) is type(wanted), "manifest policy")
    _need(type(manifest["interfaces"]) is dict and set(manifest["interfaces"]) == set(INTERFACES), "interface pins")
    for pin in manifest["interfaces"].values():
        _fields(pin,"bytes sha256"); _int(pin["bytes"],1,2*1024*1024)
        _need(type(pin["sha256"]) is str and re.fullmatch("[0-9a-f]{64}",pin["sha256"]), "interface digest")
    _need(type(manifest["files"]) is dict and set(manifest["files"]) == set(files)-{MARKER}, "file pins")
    for name, pin in manifest["files"].items():
        _fields(pin,"bytes sha256")
        _need(type(pin["bytes"]) is int and pin["bytes"] == len(files[name]) and pin["sha256"] == _sha(files[name]), "bundle drift")
    digest = _sha(_encode({n:_sha(v) for n,v in sorted(files.items())}))
    return manifest, digest

def validate_receipt(receipt_bytes, files, *, outer_timed_out, outer_elapsed_seconds,
                     expected_bundle_sha256=None):
    _need(outer_timed_out is False, "actual non-timeout outcome required")
    _number(outer_elapsed_seconds,0,MAX_OUTER_SECONDS)
    manifest, digest = _bundle(files)
    if expected_bundle_sha256 is not None:
        _need(expected_bundle_sha256 == digest, "external bundle pin mismatch")
    row = _json(receipt_bytes)
    _fields(row,"schema kind run_id request_sha256 world_name engine_version ce_initialization server_context complete failed reason callbacks_detached frames queues elapsed_seconds peak_owned_entities owned_entities_remaining render_observed ragdoll_observed gameplay_acceptance cases")
    _need(type(row["schema"]) is int and row["schema"] == 1 and row["kind"] == KIND, "receipt schema")
    for key in ("run_id","request_sha256","ce_initialization"):
        _need(row[key] == manifest[key], "receipt correlation")
    for key in ("world_name","engine_version"):
        _need(row[key] == manifest["request"][key], "world/build mismatch")
    for key, wanted in (("server_context",True),("complete",True),("failed",False),
        ("callbacks_detached",True),("render_observed",False),("ragdoll_observed",False),("gameplay_acceptance",False)):
        _flag(row[key],wanted)
    _need(row["reason"] == "", "failure reason")
    frames = _int(row["frames"],2,20000); queues = _int(row["queues"],2,512)
    elapsed = _number(row["elapsed_seconds"],0,60)
    _need(elapsed <= outer_elapsed_seconds, "native duration beyond outer duration")
    _int(row["peak_owned_entities"],2,2); _int(row["owned_entities_remaining"],0,0)
    _need(type(row["cases"]) is list and len(row["cases"]) == 2, "two cases required")
    policy = _policy_mode(manifest["request"]); names = _cases(manifest["request"])
    last_frame = last_queue = -1; last_time = -1
    for index, case in enumerate(row["cases"]):
        _fields(case,CASE_FIELDS+(" policy_type heavy_override" if policy else ""))
        _need(type(case["index"]) is int and case["index"] == index and case["name"] == names[index], "case identity")
        for field in ("spawn_frame","damage_frame","command_frame","delete_frame","cleanup_frame"):
            _int(case[field],2,frames)
        for field in ("spawn_queue","damage_queue","delete_queue","cleanup_queue"):
            _int(case[field],2,queues)
        sf,df,cf,xf,ef = (case[k+"_frame"] for k in ("spawn","damage","command","delete","cleanup"))
        sq,dq,xq,eq = (case[k+"_queue"] for k in ("spawn","damage","delete","cleanup"))
        _need(last_frame < sf < df <= cf < xf < ef and last_queue < sq < dq <= xq < eq, "callback/lifecycle order")
        times = [case[k+"_elapsed"] for k in ("spawn","damage","command","delete","cleanup")]
        for t in times: _number(t,0,elapsed)
        st,dt,ct,xt,et = times
        _need(last_time < st < dt <= ct < xt < et and et-xt <= 2, "lifecycle clock/deletion bound")
        last_frame,last_queue,last_time = ef,eq,et
        for key, expected in (("damage_calls",1),("eval_calls",1),("before_type",0),
            ("after_type",index),("command_type",index),("ammo_physics_flag",0)):
            _int(case[key],expected,expected)
        _need(case["ammo"] == "MeleeFist" and case["zone"] == "Torso", "native damage inputs")
        _number(case["ammo_damage"],.000001,1000000)
        direction = _number(case["hit_direction"],-180,180)
        if policy:
            wanted = 1 if index == 1 else -1
            _int(case["policy_type"],wanted,wanted); _flag(case["heavy_override"],index == 1)
            _need(index == 0 or abs(direction) <= POLICY_FRONT_HALF_ANGLE, "policy case needs a frontal observation")
        _need(type(case["command_direction"]) in (int,float) and case["command_direction"] == direction, "native direction changed")
        _flag(case["cleanup_confirmed"],True)
        samples = case["samples"]
        _need(type(samples) is list and 3 <= len(samples) <= 16, "bounded samples")
        previous = -1; previous_frame = -1
        for sample in samples:
            _fields(sample,"elapsed frame health death_processed position spine")
            t = _number(sample["elapsed"],st,xt); f = _int(sample["frame"],sf,xf)
            _need(t >= previous and f >= previous_frame, "sample order")
            previous,previous_frame = t,f
            _number(sample["health"],0,1000000); _native_bool(sample["death_processed"])
            _vector(sample["position"]); _vector(sample["spine"])
        _need(samples[0]["health"] > 0 and samples[0]["elapsed"] < dt, "live pre-damage observation")
        last = samples[-1]
        _need(last["health"] == 0 and last["elapsed"]-dt >= 2 and xt-dt >= 2
              and last["frame"] > cf and last["elapsed"] >= ct, "real post-command observation window")
    return dict(status="death-selection-observations-complete",receipt_sha256=_sha(receipt_bytes),
        bundle_sha256=digest,run_id=row["run_id"],gameplay_acceptance=False,
        visual_acceptance=False,ragdoll_acceptance=False,receipt=row)

def pack_addon(files):
    """Deterministic stored PBO (prefix HCDeathSelectionProbe) of the bundle's addon/ files.

    Same layout as tools.package.pbo.pack, which hard-codes the HollowCountry prefix.
    """
    _bundle(files)
    entries = {name[len("addon/"):]: data for name, data in files.items()
               if name.startswith("addon/") and name != PREFIX}
    _need(entries and len(entries) <= 16, "bounded addon entries")
    words = struct.Struct("<5I")
    header = bytearray(b"\0" + words.pack(0x56657273, 0, 0, 0, 0))
    header += b"prefix\0" + files[PREFIX] + b"\0\0"
    payload = bytearray()
    for name in sorted(entries, key=lambda n: (n.casefold(), n)):
        _need(re.fullmatch(r"[A-Za-z0-9_./]+", name) and ".." not in name, "safe PBO entry name")
        header += name.replace("/", "\\").encode("ascii") + b"\0"
        header += words.pack(0, 0, 0, 0, len(entries[name]))
        payload += entries[name]
    body = bytes(header + bytes(21) + payload)
    return body + b"\0" + hashlib.sha1(body).digest()

def stage(destination, files):
    """Write the validated bundle plus the packed PBO into a FRESH directory. Never launches.

    The destination must be absolute, free of '..' and not exist; files are created
    exclusively. Returns the sorted staged relative names.
    """
    _bundle(files)
    dest = Path(destination)
    _need(dest.is_absolute() and ".." not in dest.parts, "absolute destination without '..' required")
    _need(not dest.exists() and not dest.is_symlink(), "fresh destination required")
    _need(dest.parent.is_dir() and not dest.parent.is_symlink(), "existing real parent directory required")
    staged = dict(files)
    staged[STAGED_PBO] = pack_addon(files)
    dest.mkdir()
    for name, data in sorted(staged.items()):
        target = dest / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(data)
    return sorted(staged)

def main(argv=None):
    parser = argparse.ArgumentParser(description="Stage (never launch) the CE-disabled death-selection probe.")
    parser.add_argument("--stock-init", required=True, help="pinned stock mission init.c")
    parser.add_argument("--interfaces", required=True, help="installed native script root")
    parser.add_argument("--destination", required=True, help="fresh absolute directory to create")
    parser.add_argument("--victim", required=True, nargs=2, type=float, metavar=("X", "Z"))
    parser.add_argument("--source", required=True, nargs=2, type=float, metavar=("X", "Z"))
    parser.add_argument("--spawn-profile", choices=sorted(SPAWN_PROFILES))
    parser.add_argument("--selection", choices=("policy",))
    parser.add_argument("--policy-source", help="HCInfectedDeathPolicy.c; required with --selection policy")
    parser.add_argument("--run-id", help="32 lowercase hex characters; random when omitted")
    args = parser.parse_args(argv)
    if args.policy_source and args.selection != "policy":
        parser.error("--policy-source requires --selection policy")
    if args.selection == "policy" and not args.policy_source:
        parser.error("--selection policy requires --policy-source")
    stock = _read(Path(args.stock_init), staging.MAX_INIT_BYTES)
    req = dict(world_name="chernarusplus", engine_version=ENGINE_VERSION, stock_init_sha256=_sha(stock),
               victim_position=[args.victim[0], 0, args.victim[1]], source_position=[args.source[0], 0, args.source[1]])
    if args.spawn_profile: req["spawn_profile"] = args.spawn_profile
    policy = None
    if args.selection:
        req["selection"] = args.selection
        policy = _read_policy_file(args.policy_source)
    files = generate_probe(stock, req, inspect_interfaces(args.interfaces), run_id=args.run_id, policy_source=policy)
    names = stage(args.destination, files)
    manifest, digest = _bundle(files)
    print("staged %d files run_id=%s bundle_sha256=%s" % (len(names), manifest["run_id"], digest))
    for name in names: print("  " + name)
    print("Nothing was launched. Run in a fresh experiment with fresh profiles/storage; see docs/INFECTED_DEATHS.md.")
    return 0

ADDON = r'''
class CfgPatches
{
    class HCDeathSelectionProbe
    {
        units[] = {};
        weapons[] = {};
        requiredVersion = 0.1;
        requiredAddons[] = {"DZ_Data", "DZ_Scripts"};
    };
};
class CfgMods
{
    class HCDeathSelectionProbe
    {
        dir = "HCDeathSelectionProbe";
        type = "mod";
        dependencies[] = {"World"};
        class defs
        {
            class worldScriptModule
            {
                value = "";
                files[] = {"HCDeathSelectionProbe/scripts/4_World"};
            };
        };
    };
};
'''

NATIVE = r'''
// Disposable 4_World observer/provider. Unarmed unless the generated mission begins.
class HCDSSample
{
    float elapsed;
    int frame;
    float health;
    bool death_processed;
    ref array<float> position = new array<float>;
    ref array<float> spine = new array<float>;
}
class HCDSCase
{
    int index;
    string name;
    int spawn_frame;
    int spawn_queue;
    int damage_frame;
    int damage_queue;
    int command_frame;
    int delete_frame;
    int delete_queue;
    int cleanup_frame;
    int cleanup_queue;
    float spawn_elapsed;
    float damage_elapsed;
    float command_elapsed;
    float delete_elapsed;
    float cleanup_elapsed;
    int damage_calls;
    int eval_calls;
    int before_type = -1;
    int after_type = -1;
    int command_type = -1;
    float hit_direction;
    float command_direction;
    string ammo;
    string zone;
    int ammo_physics_flag = -1;
    float ammo_damage;@CASEFIELDS@
    bool cleanup_confirmed;
    ref array<ref HCDSSample> samples = new array<ref HCDSSample>;
}
class HCDSReceipt
{
    int schema = 1;
    string kind = "native-death-selection-observations";
    string run_id = "@RUN@";
    string request_sha256 = "@REQUEST@";
    string world_name;
    string engine_version;
    string ce_initialization = "omitted";
    bool server_context;
    bool complete;
    bool failed;
    string reason;
    bool callbacks_detached;
    int frames;
    int queues;
    float elapsed_seconds;
    int peak_owned_entities;
    int owned_entities_remaining;
    bool render_observed;
    bool ragdoll_observed;
    bool gameplay_acceptance;
    ref array<ref HCDSCase> cases = new array<ref HCDSCase>;
}
class HCDS
{
    static ref HCDSReceipt State;
    static ref HCDSCase Row;
    static ZombieBase Victim;
    static EntityAI Source;
    static Object OwnedVictim;
    static Object OwnedSource;
    static bool Done;
    static int Phase;
    static float Started;
    static float LastTime;
    static float LastSample;

    static int Owned()
    {
        int count;
        if (OwnedVictim) count++;
        if (OwnedSource) count++;
        return count;
    }
    static float Elapsed()
    {
        return GetGame().GetTickTime() - Started;
    }
    static bool Save()
    {
        string error;
        if (!JsonFileLoader<HCDSReceipt>.SaveFile("$profile:hc-death-selection-result.json", State, error))
        {
            State.failed = true;
            State.complete = false;
            State.reason = "receipt-write-failed";
            Print("[HC Death Selection] FAIL receipt write run=@RUN@");
            return false;
        }
        return true;
    }
    static void Begin()
    {
        if (State || Done || !GetGame() || !GetGame().IsServer()) return;
        if (FileExist("$profile:hc-death-selection-result.json"))
        {
            Done = true;
            Print("[HC Death Selection] REJECT stale receipt run=@RUN@");
            return;
        }
        State = new HCDSReceipt;
        State.server_context = GetGame().IsServer();
        GetGame().GetWorldName(State.world_name);
        GetGame().GetVersion(State.engine_version);
        Started = GetGame().GetTickTime();
        LastTime = Started;
        if (State.world_name != "chernarusplus" || State.engine_version != "1.30.164289.70")
        {
            Fault("world-or-build");
            Stop();
            return;
        }
        if (!Save())
        {
            Stop();
            return;
        }
        GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(Tick, 100, true);
        if (!GetGame().GetUpdateQueue(CALL_CATEGORY_SYSTEM).Insert(Frame))
        {
            Fault("callback-registration");
            Stop();
        }
    }
    static void Fault(string reason)
    {
        if (!State || Done) return;
        State.failed = true;
        if (State.reason == "") State.reason = reason;
        // Native damage/command callbacks only latch failure; Tick owns cleanup.
    }
    static void Cleanup()
    {
        if (Phase == 3) return;
        Phase = 3;
        if (Row)
        {
            Row.delete_frame = State.frames;
            Row.delete_queue = State.queues;
            Row.delete_elapsed = Elapsed();
        }
        if (OwnedVictim) GetGame().ObjectDelete(OwnedVictim);
        if (OwnedSource) GetGame().ObjectDelete(OwnedSource);
        // Keep references: issuing deletion is not observing deletion.
    }
    static void Stop()
    {
        if (Done || !State) return;
        Done = true;
        GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).Remove(Tick);
        GetGame().GetUpdateQueue(CALL_CATEGORY_SYSTEM).Remove(Frame);
        State.callbacks_detached = true;
        State.elapsed_seconds = Elapsed();
        State.owned_entities_remaining = Owned();
        State.complete = !State.failed && State.cases.Count() == 2 && Owned() == 0;
        Save();
        Print("[HC Death Selection] terminal run=@RUN@ complete=" + State.complete);
    }
    static void Interrupt()
    {
        if (!State || Done) return;
        Fault("mission-finished");
        // No synchronous deletion confirmation is claimed during shutdown.
        Stop();
    }
    static void Frame(float dt)
    {
        if (Done || !State) return;
        State.frames++;
        if (State.frames > 20000) Fault("frame-budget");
    }
    static void Sample()
    {
        if (!Victim || !Row || Row.samples.Count() >= 16)
        {
            Fault("sample-budget-or-missing-victim");
            return;
        }
        int bone = Victim.GetBoneIndexByName("spine3");
        if (bone < 0)
        {
            Fault("missing-spine");
            return;
        }
        HCDSSample sample = new HCDSSample;
        sample.elapsed = Elapsed();
        sample.frame = State.frames;
        sample.health = Victim.GetHealth("", "Health");
        sample.death_processed = Victim.IsDeathProcessed();
        vector position = Victim.GetPosition();
        vector spine = Victim.GetBonePositionWS(bone);
        for (int i = 0; i < 3; i++)
        {
            sample.position.Insert(position[i]);
            sample.spine.Insert(spine[i]);
        }
        Row.samples.Insert(sample);
        LastSample = sample.elapsed;
    }
    static void Spawn()
    {
        if (Owned() != 0 || State.cases.Count() >= 2)
        {
            Fault("ownership-or-case-bound");
            return;
        }
        vector vp = "@VICTIM@";
        vector sp = "@SOURCE@";
        float size = GetGame().GetWorld().GetWorldSize();
        if (vp[0] >= size || vp[2] >= size || sp[0] >= size || sp[2] >= size)
        {
            Fault("outside-world");
            return;
        }
        // Resolve terrain height before object creation, never reposition a live actor.
        vp[1] = GetGame().SurfaceY(vp[0], vp[2]);
        sp[1] = GetGame().SurfaceY(sp[0], sp[2]);
        if (!GetGame().ConfigIsExisting("CfgVehicles ZmbF_JournalistNormal_Blue")
            || !GetGame().ConfigIsExisting("CfgVehicles Stone")
            || !GetGame().ConfigIsExisting("CfgAmmo MeleeFist DamageApplied Health damage"))
        {
            Fault("stock-config-missing");
            return;
        }
        Row = new HCDSCase;
        Row.index = State.cases.Count();
        Row.name = "vanilla";
        if (Row.index == 1) Row.name = "@CASE1NAME@";
        Row.spawn_frame = State.frames;
        Row.spawn_queue = State.queues;
        Row.spawn_elapsed = Elapsed();
        State.cases.Insert(Row);
        OwnedSource = GetGame().CreateObjectEx("Stone", sp, 0);
        Source = EntityAI.Cast(OwnedSource);
        OwnedVictim = GetGame().CreateObjectEx("ZmbF_JournalistNormal_Blue", vp, @VFLAGS@);
        Victim = ZombieBase.Cast(OwnedVictim);
        State.peak_owned_entities = Math.Max(State.peak_owned_entities, Owned());
        if (!Source || !Victim || !Victim.IsAlive())
        {
            Fault("owned-spawn-failed");
            return;
        }
        Phase = 1;
        Sample();
        if (!Save()) Fault("receipt-write-failed");
    }
    static void Damage()
    {
        if (!Victim || !Source || !Victim.IsAlive() || Victim.IsBeingBackstabbed())
        {
            Fault("pre-damage-state");
            return;
        }
        array<string> zones = new array<string>;
        Victim.GetDamageZones(zones);
        if (zones.Count() > 64 || zones.Find("Torso") < 0)
        {
            Fault("stock-torso-zone-missing");
            return;
        }
        Row.ammo = "MeleeFist";
        Row.zone = "Torso";
        Row.ammo_physics_flag = GetGame().ConfigGetInt("CfgAmmo MeleeFist doPhxImpulse");
        Row.ammo_damage = GetGame().ConfigGetFloat("CfgAmmo MeleeFist DamageApplied Health damage");
        if (Row.ammo_physics_flag != 0 || !(Row.ammo_damage > 0) || !(Row.ammo_damage <= 1000000))
        {
            Fault("native-ammo-policy");
            return;
        }
        Row.damage_frame = State.frames;
        Row.damage_queue = State.queues;
        Row.damage_elapsed = Elapsed();
        Row.damage_calls++;
        Phase = 2;@PREDAMAGE@
        // GetDamageZonePos returns world space; ProcessDirectDamage takes model space.
        vector modelPos = Victim.WorldToModel(Victim.GetDamageZonePos("Torso"));
        Victim.ProcessDirectDamage(DamageType.CUSTOM, Source, "Torso", "MeleeFist",
            modelPos, 100.0, ProcessDirectDamageFlags.ALL_TRANSFER);
        if (!Victim || Victim.IsAlive() || Row.eval_calls != 1)
        {
            Fault("native-fatal-damage-not-observed");
            return;
        }
        Sample();
        if (!Save()) Fault("receipt-write-failed");
    }
    static void Tick()
    {
        if (Done || !State) return;
        State.queues++;
        float now = GetGame().GetTickTime();
        if (!(now >= LastTime) || !(now - Started <= 60) || State.queues > 512)
            Fault("clock-or-fixture-budget");
        LastTime = now;
        State.elapsed_seconds = now - Started;
        array<PlayerIdentity> clients = new array<PlayerIdentity>;
        GetGame().GetPlayerIndentities(clients);
        if (clients.Count() != 0) Fault("unexpected-clients");
        if (State.failed) Cleanup();
        if (State.frames < 2 || State.queues < 2) return;
        if (Phase == 0 && !State.failed)
        {
            Spawn();
            return;
        }
        if (Phase == 1 && !State.failed)
        {
            if (State.frames > Row.spawn_frame && State.queues > Row.spawn_queue) Damage();
            return;
        }
        if (Phase == 2 && !State.failed)
        {
            if (!Victim || !Source)
            {
                Fault("actor-disappeared");
                return;
            }
            if (Elapsed() - LastSample >= 0.25) Sample();
            if (!State.failed && Elapsed() - Row.damage_elapsed >= 2.0 && Row.command_frame > 0
                && State.frames > Row.command_frame)
            {
                Sample();
                Cleanup();
            }
        }
        if (Phase == 3)
        {
            if (!Row || Elapsed() - Row.delete_elapsed > 2)
            {
                State.failed = true;
                if (State.reason == "") State.reason = "deletion-deadline";
                Stop();
                return;
            }
            if (Owned() == 0 && Row && State.frames > Row.delete_frame && State.queues > Row.delete_queue)
            {
                Row.cleanup_frame = State.frames;
                Row.cleanup_queue = State.queues;
                Row.cleanup_elapsed = Elapsed();
                Row.cleanup_confirmed = true;
                if (!Save()) Fault("receipt-write-failed");
                if (State.failed || State.cases.Count() == 2)
                {
                    Stop();
                    return;
                }
                Row = null;
                Phase = 0;
                return;
            }
        }
    }
}
modded class ZombieBase
{
    override bool EvaluateDeathAnimationEx(EntityAI pSource, ZombieHitData data,
        out int pAnimType, out float pAnimHitDir)
    {
        bool result = super.EvaluateDeathAnimationEx(pSource, data, pAnimType, pAnimHitDir);
        if (HCDS.Victim != this || !HCDS.Row || HCDS.Done) return result;
        if (!result || !data || pSource != HCDS.Source || data.m_AmmoType != "MeleeFist"
            || data.m_DamageZone != "Torso" || IsBeingBackstabbed() || IsAlive()
            || HCDS.Phase != 2 || HCDS.Row.eval_calls != 0)
        {
            HCDS.Fault("unexpected-native-death-evaluation");
            return result;
        }
        HCDS.Row.eval_calls++;
        HCDS.Row.before_type = pAnimType;
        if (pAnimType != DayZInfectedDeathAnims.ANIM_DEATH_DEFAULT)
        {
            HCDS.Fault("unexpected-native-animation");
            return result;
        }
        @SELECT@
        HCDS.Row.after_type = pAnimType;
        HCDS.Row.hit_direction = pAnimHitDir;
        return result;
    }
    override void CommandHandler(float pDt, int pCurrentCommandID, bool pCurrentCommandFinished)
    {
        if (HCDS.Victim == this && HCDS.Row && !HCDS.Done
            && pCurrentCommandID == DayZInfectedConstants.COMMANDID_DEATH && HCDS.Row.command_frame == 0)
        {
            HCDS.Row.command_frame = HCDS.State.frames;
            HCDS.Row.command_elapsed = HCDS.Elapsed();
            HCDS.Row.command_type = m_DeathType;
            HCDS.Row.command_direction = m_DamageHitDirection;
        }
        super.CommandHandler(pDt, pCurrentCommandID, pCurrentCommandFinished);
    }
}
'''

if __name__ == "__main__":
    raise SystemExit(main())
