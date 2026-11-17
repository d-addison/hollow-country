"""Read-only POSIX native item-audit consumer; no eligibility/geometry inference."""
import argparse
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat

MAX_CHUNKS, MAX_CHILDREN = 64, 16384
MAX_CHUNK_BYTES, MAX_MANIFEST_BYTES = 16 << 20, 8 << 20
MAX_TOTAL_BYTES, MAX_DEPTH = 256 << 20, 32
MAX_NODES, MAX_TOTAL_NODES = 2_000_000, 16_000_000
ROOT_ROLES = dict(
    CfgWeapons="weapon_config_not_inventory_eligibility",
    CfgVehicles="vehicle_and_equipment_config_not_inventory_eligibility",
    CfgMagazines="magazine_and_ammunition_inventory_config",
    CfgAmmo="projectile_config_not_inventory_eligibility")
TYPES = ("CT_INT", "CT_FLOAT", "CT_STRING", "CT_ARRAY", "CT_CLASS", "CT_OTHER")
MANIFEST = """SchemaVersion ArtifactKind IntegrityPolicy Header FullCoverage
IndexPlanComplete EnumerationComplete AdvertisedChildren ExpectedClassRows
NonClassChildren CommittedChunkByteBound UncommittedFile UncommittedByteBound
MaxChildren MaxChunks MaxChunkBytes MaxTotalBytes TargetChildrenPerChunk
MaxManifestBytes IndexPlan Chunks""".split()
HEADER = """SchemaVersion Acquisition ActualWorld ActualBuild ConfigProvenance RunId
ProvenancePolicy FieldPolicy ArrayPolicy BytePolicy FilePolicy EnumerationOrder
FullCoverage Partial StopReason StopClassPath UnresolvedFields KindVariantFields
RowsWritten VisitedChildren MaxRows MaxBytes MaxFields MaxArrayValues MaxValueUnits
MaxAncestors MaxVisitedChildren RowByteBound SchemaFields Unknowns Roots""".split()
DYNAMIC = set("""Partial StopReason StopClassPath UnresolvedFields KindVariantFields
RowsWritten VisitedChildren MaxRows MaxBytes MaxVisitedChildren RowByteBound Roots""".split())
FIELD = """ConfigPath ReadAs ExpectedReadAs ConfigType ConfigTypeName Status
ValueCaptured UnresolvedReasons ValueText ValueInt ValueFloat TextValues IntValues
FloatValues""".split()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def shape(value, keys):
    require(type(value) is dict and set(value) == set(keys), "object schema mismatch")
    return value


def integer(value, maximum=MAX_TOTAL_BYTES, minimum=0):
    require(type(value) is int and minimum <= value <= maximum, "integer bound/type")
    return value


def flag(value):
    require(type(value) is bool or type(value) is int and value in (0, 1),
            "boolean must be bool or integer 0/1")
    return bool(value)


def text(value, maximum=512, empty=False):
    require(type(value) is str and (empty or bool(value)) and len(value) <= maximum,
            "string bound/type")
    value.encode("utf-8", errors="strict")
    return value


def strings(value, maximum, empty=False):
    require(type(value) is list and len(value) <= maximum, "array bound/type")
    for item in value:
        text(item, empty=empty)
    require(len(set(value)) == len(value), "duplicate string identity")
    return value


def native_type(value):
    code = integer(value["ConfigType"], 5)
    require(value["ConfigTypeName"] == TYPES[code], "native type identity")
    return code


def strict_json(raw, state):
    source = raw.decode("utf-8", errors="strict")
    depth = nodes = 0
    quoted = escaped = atom = False
    for char in source:
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted, atom = True, False
            nodes += 1
        elif char in "[{":
            depth += 1
            nodes += 1
            atom = False
            require(depth <= MAX_DEPTH, "JSON depth budget")
        elif char in "]}":
            depth -= 1
            atom = False
        elif char.isspace() or char in ",:":
            atom = False
        elif not atom:
            atom = True
            nodes += 1
        require(nodes <= MAX_NODES, "JSON node budget")
    state["nodes"] += nodes
    require(state["nodes"] <= MAX_TOTAL_NODES, "JSON aggregate node budget")

    def pairs(entries):
        result = {}
        for key, value in entries:
            require(key not in result, "duplicate JSON key")
            result[key] = value
        return result

    def number(value):
        result = float(value)
        require(math.isfinite(result), "nonfinite JSON number")
        return result

    def whole(value):
        require(len(value) <= 20, "JSON integer digit budget")
        return int(value)

    def invalid(value):
        raise ValueError("nonfinite JSON constant")

    result = json.loads(source, object_pairs_hook=pairs, parse_float=number,
                        parse_int=whole, parse_constant=invalid)
    pending = [result]
    while pending:
        value = pending.pop()
        if type(value) is dict:
            pending.extend(value)
            pending.extend(value.values())
        elif type(value) is list:
            pending.extend(value)
        elif type(value) is str:
            text(value, 4096, empty=True)
    return result


def parent_handle(path):
    path = Path(path)
    require(path.name not in ("", ".", "..") and ".." not in path.parts,
            "unsafe manifest path")
    require(hasattr(os, "O_NOFOLLOW") and hasattr(os, "O_DIRECTORY") and
            hasattr(os, "O_NONBLOCK") and os.open in os.supports_dir_fd,
            "secure directory-relative reads unavailable")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    handle = os.open(path.anchor or ".", flags)
    try:
        parts = path.parts[1:] if path.anchor else path.parts
        for part in parts[:-1]:
            next_handle = os.open(part, flags, dir_fd=handle)
            os.close(handle)
            handle = next_handle
        return handle, path.name
    except BaseException:
        os.close(handle)
        raise


def read_file(directory, name, maximum, state):
    handle = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                     dir_fd=directory)
    try:
        before = os.fstat(handle)
        require(stat.S_ISREG(before.st_mode), "input must be a regular file")
        require(before.st_size <= maximum, "file byte budget")
        blocks, size = [], 0
        while True:
            block = os.read(handle, min(65536, maximum + 1 - size))
            if not block:
                break
            size += len(block)
            state["bytes"] += len(block)
            require(size <= maximum and state["bytes"] <= MAX_TOTAL_BYTES,
                    "file/aggregate byte budget")
            blocks.append(block)
        after = os.fstat(handle)
        require((before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
                (after.st_size, after.st_mtime_ns, after.st_ctime_ns),
                "input changed during read")
        raw = b"".join(blocks)
        state["pins"].append(dict(file=name, bytes=len(raw),
                                  sha256=hashlib.sha256(raw).hexdigest()))
        return raw
    finally:
        os.close(handle)


def header(value, chunk=False):
    shape(value, HEADER)
    require(value["SchemaVersion"] == 1 and type(value["SchemaVersion"]) is int,
            "header version")
    require(not flag(value["FullCoverage"]), "FullCoverage claims prohibited")
    for key, limit in (("RunId", 96), ("ActualWorld", 128), ("ActualBuild", 128),
                       ("ConfigProvenance", 1024)):
        text(value[key], limit)
    require(re.fullmatch(r"[A-Za-z0-9_-]+", value["RunId"]), "unsafe run identity")
    policies = dict(Acquisition="effective_native_config_all_classes_in_selected_roots",
        ProvenancePolicy="caller_supplied_not_independently_verified",
        FieldPolicy="whitelist_present_only_missing_paths_omitted_no_eligibility_inference",
        ArrayPolicy="schema_typed_native_array_reads_element_kind_unverified_per_field",
        BytePolicy="conservative_four_UTF8_bytes_per_string_unit",
        FilePolicy="isolated_profile_single_writer_no_atomic_exclusive_create_API")
    text(value["EnumerationOrder"])
    require(all(value[key] == expected for key, expected in policies.items()),
            "unsupported header policy")
    for key, expected in (("MaxRows", 512 if chunk else MAX_CHILDREN),
                          ("MaxBytes", MAX_CHUNK_BYTES if chunk else MAX_TOTAL_BYTES),
                          ("MaxVisitedChildren", 512 if chunk else MAX_CHILDREN),
                          ("MaxFields", 96), ("MaxArrayValues", 128),
                          ("MaxValueUnits", 512), ("MaxAncestors", 64)):
        require(integer(value[key]) == expected, "header limit mismatch")
    strings(value["SchemaFields"], 96)
    strings(value["Unknowns"], 64)
    flag(value["Partial"])
    text(value["StopReason"], 4096, True)
    text(value["StopClassPath"], 1024, True)
    return value


def row_counts(row, root, name, schema, reasons):
    shape(row, """ConfigRoot ItemClass ParentClass UnresolvedFields KindVariantFields
ConfigAncestors Fields""".split())
    require(row["ConfigRoot"] == root and row["ItemClass"] == name, "row identity")
    ancestors = strings(row["ConfigAncestors"], 64)
    require(name.casefold() not in {s.casefold() for s in ancestors} and
            len({s.casefold() for s in ancestors}) == len(ancestors), "ancestry cycle")
    require(row["ParentClass"] == (ancestors[0] if ancestors else ""), "parent identity")
    require(type(row["Fields"]) is list and len(row["Fields"]) <= 96, "field budget")
    seen, unresolved, variants = set(), 0, 0
    for field in row["Fields"]:
        shape(field, FIELD)
        path = field["ConfigPath"]
        require(type(path) is str and path in schema and path not in seen, "field identity")
        seen.add(path)
        code, expected = native_type(field), field["ExpectedReadAs"]
        require(expected in ("text", "number", "text_array", "int_array", "float_array"),
                "expected field mode")
        matches = code == 2 if expected == "text" else code in (0, 1) if expected == "number" else code == 3
        mode = "text" if code == 2 else "number" if code in (0, 1) else expected if code == 3 and expected.endswith("_array") else "text_array" if code == 3 else "unresolved"
        why = set()
        if not matches:
            why.add("schema_kind_variant")
        if code == 3:
            why.add("array_element_kind_unverified")
        if mode == "unresolved":
            why.add("unsupported_native_kind")
        require(set(strings(field["UnresolvedReasons"], 3)) == why, "field uncertainty")
        status = "unresolved" if mode == "unresolved" else "kind_variant" if not matches else "captured_unresolved" if code == 3 else "captured"
        require(field["ReadAs"] == mode and field["Status"] == status and
                flag(field["ValueCaptured"]) == (mode != "unresolved"), "field capture semantics")
        text(field["ValueText"], empty=True)
        integer(field["ValueInt"], 2147483647, -2147483648)
        require(type(field["ValueFloat"]) in (int, float) and
                abs(field["ValueFloat"]) <= 3.4028235e38, "float field bound")
        for key in ("TextValues", "IntValues", "FloatValues"):
            values = field[key]
            require(type(values) is list and len(values) <= 128, "field array bound")
            for value in values:
                if key == "TextValues":
                    text(value, empty=True)
                elif key == "IntValues":
                    integer(value, 2147483647, -2147483648)
                else:
                    require(type(value) in (int, float) and abs(value) <= 3.4028235e38,
                            "float array bound")
        unresolved += bool(why)
        variants += not matches
        reasons.update(why)
    require(integer(row["UnresolvedFields"], 96) == unresolved and
            integer(row["KindVariantFields"], 96) == variants, "row uncertainty totals")
    return unresolved, variants


def scan_manifest(path, expected_sha256=None):
    """Validate one native export; invalid input raises ValueError/OSError."""
    if expected_sha256 is not None:
        require(type(expected_sha256) is str and
                re.fullmatch(r"[0-9a-fA-F]{64}", expected_sha256), "invalid SHA256 pin")
    directory, filename = parent_handle(path)
    state = dict(bytes=0, nodes=0, pins=[])
    try:
        raw = read_file(directory, filename, MAX_MANIFEST_BYTES, state)
        if expected_sha256 is not None:
            require(state["pins"][0]["sha256"] == expected_sha256.lower(), "manifest SHA256 mismatch")
        manifest = shape(strict_json(raw, state), MANIFEST)
        require(type(manifest["SchemaVersion"]) is int and manifest["SchemaVersion"] == 1 and
                manifest["ArtifactKind"] == "item_compatibility_manifest", "manifest identity")
        require(manifest["IntegrityPolicy"] == "readback_equality_only_external_SHA256_required",
                "manifest integrity policy")
        require(not flag(manifest["FullCoverage"]), "FullCoverage claims prohibited")
        for key, expected in (("MaxChildren", MAX_CHILDREN), ("MaxChunks", MAX_CHUNKS),
                              ("MaxChunkBytes", MAX_CHUNK_BYTES), ("MaxTotalBytes", MAX_TOTAL_BYTES),
                              ("TargetChildrenPerChunk", 512), ("MaxManifestBytes", MAX_MANIFEST_BYTES)):
            require(integer(manifest[key]) == expected, "manifest limit mismatch")
        h = header(manifest["Header"])
        roots = h["Roots"]
        require(type(roots) is list and 1 <= len(roots) <= len(ROOT_ROLES),
                "selected root denominator")
        require(all(type(root) is dict for root in roots), "root object")
        advertised, root_names = [], []
        with_roles = "ConfigRole" in roots[0]
        for root in roots:
            keys = "ConfigRoot AdvertisedChildren VisitedChildren RowsWritten EnumerationComplete".split()
            shape(root, keys + (["ConfigRole"] if with_roles else []))
            name = text(root["ConfigRoot"])
            require(name in ROOT_ROLES and name not in root_names, "root identity")
            if with_roles:
                require(root["ConfigRole"] == ROOT_ROLES[name], "root role mismatch")
            root_names.append(name)
            advertised.append(integer(root["AdvertisedChildren"], MAX_CHILDREN))
        require(h["EnumerationOrder"] == "native_child_index_" + "_then_".join(root_names),
                "root enumeration order")
        total = integer(manifest["AdvertisedChildren"], MAX_CHILDREN)
        require(sum(advertised) == total, "advertised denominator")
        plan = manifest["IndexPlan"]
        require(type(plan) is list and len(plan) <= total, "index plan bound")
        indexed, identities, classes = [0] * len(roots), set(), 0
        previous_root = 0
        for entry in plan:
            shape(entry, "RootIndex ChildIndex ChildName ConfigType ConfigTypeName".split())
            ri = integer(entry["RootIndex"], len(roots) - 1)
            require(ri >= previous_root and integer(entry["ChildIndex"], MAX_CHILDREN) == indexed[ri]
                    and indexed[ri] < advertised[ri] and
                    all(indexed[j] == advertised[j] for j in range(ri)),
                    "noncontiguous root index")
            previous_root = ri
            indexed[ri] += 1
            name = text(entry["ChildName"])
            if native_type(entry) == 4:
                identity = (ri, name.casefold())
                require(identity not in identities, "duplicate class identity")
                identities.add(identity)
                classes += 1
        planned = flag(manifest["IndexPlanComplete"])
        require(planned == (len(plan) == total), "index completeness claim")
        require(integer(manifest["ExpectedClassRows"], MAX_CHILDREN) == classes, "class denominator")
        chunks = manifest["Chunks"]
        require(type(chunks) is list and len(chunks) <= MAX_CHUNKS, "chunk count bound")
        visited = rows = unresolved = variants = bound = row_bound = 0
        per_root, per_rows, reasons = [0] * len(roots), [0] * len(roots), Counter()
        for sequence, ref in enumerate(chunks):
            shape(ref, """FileName Sequence StartPlanIndex NextPlanIndex RowsWritten
NonClassChildren ByteBound ReadbackVerified""".split())
            name = "chunk-" + str(sequence) + ".json"
            require(ref["FileName"] == name and flag(ref["ReadbackVerified"]), "chunk file identity/readback")
            require(integer(ref["Sequence"], MAX_CHUNKS) == sequence and
                    integer(ref["StartPlanIndex"], MAX_CHILDREN) == visited, "chunk sequence/gap")
            end = integer(ref["NextPlanIndex"], len(plan))
            require(visited < end <= visited + 512, "chunk window")
            raw = read_file(directory, name, MAX_CHUNK_BYTES, state)
            cb = integer(ref["ByteBound"], MAX_CHUNK_BYTES)
            require(cb == len(raw) * 4, "chunk byte bound mismatch")
            bound += cb
            require(bound <= MAX_TOTAL_BYTES - 2 * MAX_MANIFEST_BYTES, "aggregate declared byte bound")
            data = shape(strict_json(raw, state), ("Chunk", "Rows"))
            chunk = shape(data["Chunk"], """ArtifactKind Header Sequence StartPlanIndex
NextPlanIndex BoundaryReason RowPlanIndices NonClassPlanIndices""".split())
            require(chunk["ArtifactKind"] == "item_compatibility_chunk", "chunk kind")
            for key in ("Sequence", "StartPlanIndex", "NextPlanIndex"):
                require(type(chunk[key]) is int and chunk[key] == ref[key], "chunk metadata mismatch")
            ch = header(chunk["Header"], True)
            require(all(ch[key] == h[key] for key in HEADER if key not in DYNAMIC),
                    "run/world/build/header mismatch")
            require(not flag(ch["Partial"]) and ch["StopReason"] == "" and
                    ch["StopClassPath"] == "" and ch["Roots"] == [], "chunk header state")
            class_indices = [i for i in range(visited, end) if plan[i]["ConfigType"] == 4]
            nonclass_indices = [i for i in range(visited, end) if plan[i]["ConfigType"] != 4]
            for key, expected in (("RowPlanIndices", class_indices),
                                  ("NonClassPlanIndices", nonclass_indices)):
                require(type(chunk[key]) is list and all(type(i) is int for i in chunk[key])
                        and chunk[key] == expected, "chunk index partition")
            require(type(data["Rows"]) is list and len(data["Rows"]) == len(class_indices),
                    "chunk row cardinality")
            cu = cv = 0
            for row, index in zip(data["Rows"], class_indices):
                entry = plan[index]
                u, v = row_counts(row, root_names[entry["RootIndex"]], entry["ChildName"],
                                  h["SchemaFields"], reasons)
                cu, cv = cu + u, cv + v
            for key, expected in (("RowsWritten", len(class_indices)),
                                  ("NonClassChildren", len(nonclass_indices))):
                require(integer(ref[key], 512) == expected, "reference totals")
            for key, expected in (("RowsWritten", len(class_indices)), ("VisitedChildren", end - visited),
                                  ("UnresolvedFields", cu), ("KindVariantFields", cv)):
                require(integer(ch[key]) == expected, "chunk header totals")
            rb = integer(ch["RowByteBound"], MAX_CHUNK_BYTES - 65536)
            require(rb <= len(class_indices) * 65536 and (rb == 0) == (not class_indices),
                    "row byte bound")
            boundary = chunk["BoundaryReason"]
            require(boundary in ("child_target", "byte_target", "source_failure", "single_row_budget", "end_plan")
                    and (boundary != "child_target" or end - visited == 512)
                    and (boundary not in ("source_failure", "single_row_budget", "end_plan")
                         or sequence == len(chunks) - 1)
                    and (boundary != "end_plan" or end == len(plan)), "chunk boundary reason")
            for entry in plan[visited:end]:
                ri = entry["RootIndex"]
                per_root[ri] += 1
                per_rows[ri] += entry["ConfigType"] == 4
            visited, rows = end, rows + len(class_indices)
            unresolved, variants = unresolved + cu, variants + cv
            row_bound += rb
        for key, expected in (("VisitedChildren", visited), ("RowsWritten", rows),
                              ("UnresolvedFields", unresolved), ("KindVariantFields", variants),
                              ("RowByteBound", row_bound)):
            require(integer(h[key]) == expected, "manifest header totals")
        require(integer(manifest["NonClassChildren"], MAX_CHILDREN) == visited - rows and
                integer(manifest["CommittedChunkByteBound"]) == bound, "manifest chunk totals")
        for i, root in enumerate(roots):
            require(integer(root["VisitedChildren"], MAX_CHILDREN) == per_root[i] and
                    integer(root["RowsWritten"], MAX_CHILDREN) == per_rows[i] and
                    flag(root["EnumerationComplete"]) == (planned and per_root[i] == advertised[i]),
                    "per-root coverage")
        complete = flag(manifest["EnumerationComplete"])
        require(flag(h["Partial"]) == (not complete), "partial/completion contradiction")
        require(not complete or planned and visited == total and rows == classes,
                "truncated enumeration claim")
        require((not complete and bool(h["StopReason"])) or
                (complete and h["StopReason"] == "" and h["StopClassPath"] == ""),
                "terminal completion reason")
        pending = text(manifest["UncommittedFile"], 64, True)
        pending_bound = integer(manifest["UncommittedByteBound"], MAX_CHUNK_BYTES)
        require((pending == "" and pending_bound == 0) or
                (not complete and len(chunks) < MAX_CHUNKS and
                 pending == "chunk-" + str(len(chunks)) + ".json"
                 and pending_bound > 0), "uncommitted artifact claim")
        require(bound + pending_bound <= MAX_TOTAL_BYTES - 2 * MAX_MANIFEST_BYTES,
                "uncommitted byte budget")
        if pending:
            try:
                read_file(directory, pending, MAX_CHUNK_BYTES, state)
            except FileNotFoundError:
                pass  # A failed open can legitimately leave no uncommitted file.
        return dict(status="complete" if complete else "partial", FullCoverage=False,
                    EnumerationComplete=complete, RunId=h["RunId"], ActualWorld=h["ActualWorld"],
                    ActualBuild=h["ActualBuild"], ConfigProvenance=h["ConfigProvenance"],
                    ProvenancePolicy=h["ProvenancePolicy"], RowsWritten=rows,
                    AdvertisedChildren=total, VisitedChildren=visited, NonClassChildren=visited - rows,
                    UnresolvedFields=unresolved, KindVariantFields=variants,
                    UnresolvedReasons=dict(sorted(reasons.items())), Roots=roots,
                    StopReason=h["StopReason"], UncommittedFile=pending, files=state["pins"],
                    manifest_pin_checked=expected_sha256 is not None,
                    limitations=["Metadata enumeration only; no eligibility or geometry conclusions.",
                                 "SHA256 values pin consumed bytes; no prior chunk digests were supplied."])
    finally:
        os.close(directory)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--expect-manifest-sha256")
    args = parser.parse_args(argv)
    try:
        report = scan_manifest(args.manifest, args.expect_manifest_sha256)
        code = 0 if report["EnumerationComplete"] else 1
    except (OSError, ValueError, RecursionError) as exc:
        report, code = dict(status="invalid", FullCoverage=False, error=str(exc)), 1
    print(json.dumps(report, allow_nan=False, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
