#!/usr/bin/env python3
"""Build the search group pack (contract section 6) from stock mapgroupproto.xml and types.xml.

Writes templates/search-groups-NNN.json chunks plus a separate report that carries the pins the
index needs (including the `search-generator` pin, the SHA-256 of this file). Standard library
only. Parsing, bounded reads and output-path rules come from tools/audit/interior_points.py.

Offline output is a filter list only: search never creates items (contract section 6)."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.audit import interior_points  # noqa: E402

SCHEMA_VERSION = 2
MAX_CHUNKS = 64
MAX_CHUNK_BYTES = 32767
MAX_ITEMS_PER_GROUP = 1024           # owner decision: search in every class; matches the runtime cap
MAX_ITEMS_LIMIT = 1024               # runtime volume class cap; larger is never accepted
MAX_GROUPS = 9999
REPORT_NAME = "search-context-report.json"
ALPHABET = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-:+/=")
MAX_NAME = 128


class SearchContextError(ValueError):
    """Input or output refused with a clear reason."""


def generator_sha256():
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def _name(value, what):
    if not value or len(value) > MAX_NAME or any(c not in ALPHABET for c in value):
        raise SearchContextError(f"unsafe {what} name: {value!r}")
    return value


def _parse(data, what, root_tag):
    try:
        root = interior_points._parse_xml(data)
    except ValueError as error:
        text = str(error)
        if "DTD" in text:
            raise SearchContextError(f"{what}: refused, declares a DTD or entity ({text})") from error
        if "too large" in text:
            raise SearchContextError(f"{what}: too large ({text})") from error
        raise SearchContextError(f"{what}: {text}") from error
    if root.tag != root_tag:
        raise SearchContextError(f"{what}: unexpected root <{root.tag}>, expected <{root_tag}>")
    return root


def _names(element, tag, what):
    return sorted({_name(child.get("name", ""), what) for child in element.findall(tag)})


def _read_types(data):
    root = _parse(data, "types.xml", "types")
    items = {}
    for element in root.findall("type"):
        name = _name(element.get("name", ""), "type")
        if name in items:
            raise SearchContextError(f"duplicate type {name}")
        nominal = element.find("nominal")
        text = (nominal.text or "").strip() if nominal is not None else "0"
        try:
            value = int(text)
        except ValueError as error:
            raise SearchContextError(f"type {name}: unreadable nominal {text!r}") from error
        items[name] = {
            "nominal": value,
            "categories": frozenset(_names(element, "category", "category")),
            "usages": frozenset(_names(element, "usage", "usage")),
            "tags": frozenset(_names(element, "tag", "tag")),
        }
    return items


def _read_groups(data):
    """[(class, [(container, key, points)])] in document order."""
    root = _parse(data, "mapgroupproto", "prototype")
    classes, seen = [], set()
    for group in root.iter("group"):
        cls = _name(group.get("name", ""), "group")
        if cls in seen:
            raise SearchContextError(f"duplicate group {cls}")
        seen.add(cls)
        usages = tuple(_names(group, "usage", "usage"))
        containers = []
        for container in group.findall("container"):
            cname = _name(container.get("name", ""), "container")
            key = (usages, cname, tuple(_names(container, "category", "category")),
                   tuple(_names(container, "tag", "tag")))
            containers.append((cname, key, len(container.findall("point"))))
        classes.append((cls, containers))
    return classes


def _items_for(key, types):
    usages, _container, categories, tags = key
    usage_set, category_set, tag_set = set(usages), set(categories), set(tags)
    out = []
    for name, row in types.items():
        if row["nominal"] <= 0:
            continue
        if row["usages"] and not (row["usages"] & usage_set):
            continue
        if not (row["categories"] & category_set):
            continue
        if row["tags"] and not (row["tags"] & tag_set):
            continue
        out.append(name)
    return sorted(out)


def _dump(document):
    return json.dumps(document, separators=(",", ":"), ensure_ascii=True, sort_keys=False).encode("ascii")


def _chunk(groups):
    """Pack groups, in order, into chunks whose serialised size stays under MAX_CHUNK_BYTES."""
    chunks, current = [], []
    for group in groups:
        trial = current + [group]
        if len(_dump({"SchemaVersion": SCHEMA_VERSION, "Chunk": len(chunks), "Groups": trial})) <= MAX_CHUNK_BYTES:
            current = trial
            continue
        if not current:
            raise SearchContextError(f"group {group['Id']} alone exceeds one chunk ({MAX_CHUNK_BYTES} bytes)")
        chunks.append(current)
        current = [group]
        if len(_dump({"SchemaVersion": SCHEMA_VERSION, "Chunk": len(chunks), "Groups": current})) > MAX_CHUNK_BYTES:
            raise SearchContextError(f"group {group['Id']} alone exceeds one chunk ({MAX_CHUNK_BYTES} bytes)")
    if current:
        chunks.append(current)
    if len(chunks) > MAX_CHUNKS:
        raise SearchContextError(f"{len(chunks)} chunks exceed the {MAX_CHUNKS} chunk cap")
    return [_dump({"SchemaVersion": SCHEMA_VERSION, "Chunk": index, "Groups": rows})
            for index, rows in enumerate(chunks)]


def build_search_groups(proto_bytes, types_bytes, max_items=None):
    """(chunks, report). chunks are compact ASCII JSON bytes; the report holds the pins.

    max_items defaults to 1024 items per group (owner decision, the runtime cap); an operator may
    lower it, never raise it above MAX_ITEMS_LIMIT, and the report records the value used."""
    if max_items is None:
        max_items = MAX_ITEMS_PER_GROUP
    if not isinstance(max_items, int) or isinstance(max_items, bool) or not 1 <= max_items <= MAX_ITEMS_LIMIT:
        raise SearchContextError(f"max items must be 1..{MAX_ITEMS_LIMIT}")
    types = _read_types(types_bytes)
    classes = _read_groups(proto_bytes)
    keys = sorted({key for _cls, containers in classes for _name_, key, _n in containers})
    emitted, group_ids, empty, over = [], {}, [], []
    for key in keys:
        items = _items_for(key, types)
        row = {"Usages": list(key[0]), "Container": key[1], "Categories": list(key[2]), "Tags": list(key[3])}
        if not items:
            empty.append(dict(row, Reason="no_items"))
        elif len(items) > max_items:
            over.append(dict(row, Items=len(items), Reason="over_budget"))
        else:
            if len(emitted) >= MAX_GROUPS:
                raise SearchContextError(f"more than {MAX_GROUPS} groups")
            gid = "g-%04d" % len(emitted)
            group_ids[key] = gid
            emitted.append(dict([("Id", gid)] + list(row.items()) + [("Items", items)]))
    chunks = _chunk(emitted)
    class_groups, empty_classes, over_classes = {}, [], []
    empty_keys = {(tuple(r["Usages"]), r["Container"], tuple(r["Categories"]), tuple(r["Tags"])) for r in empty}
    for cls, containers in sorted(classes):
        rows = []
        for cname, key, points in containers:
            row = {"Container": cname, "Group": group_ids.get(key), "Points": points}
            if key not in group_ids:
                row["Refused"] = "empty" if key in empty_keys else "over_budget"
            rows.append(row)
        class_groups[cls] = rows
        if any(r.get("Refused") == "empty" for r in rows):
            empty_classes.append(cls)
        if any(r.get("Refused") == "over_budget" for r in rows):
            over_classes.append(cls)
    report = {
        "SchemaVersion": SCHEMA_VERSION,
        "Kind": "hc-search-context-report",
        "Sources": {"mapgroupproto": hashlib.sha256(proto_bytes).hexdigest(),
                    "types": hashlib.sha256(types_bytes).hexdigest(),
                    "search-generator": generator_sha256()},
        "Chunks": [{"File": "search-groups-%03d.json" % index, "Bytes": len(chunk),
                    "Sha256": hashlib.sha256(chunk).hexdigest()} for index, chunk in enumerate(chunks)],
        "MaxItemsPerGroup": max_items,
        "GroupCount": len(emitted),
        "EmptyGroups": empty,
        "OverBudget": over,
        "EmptyClasses": sorted(empty_classes),
        "OverBudgetClasses": sorted(over_classes),
        "ClassGroups": class_groups,
    }
    return chunks, report


def write_pack(output_dir, chunks, report):
    out = interior_points._output_path(output_dir)
    out.mkdir(parents=True)
    for index, chunk in enumerate(chunks):
        (out / ("search-groups-%03d.json" % index)).write_bytes(chunk)
    text = json.dumps(report, indent=1, sort_keys=True, ensure_ascii=True) + "\n"
    (out / REPORT_NAME).write_bytes(text.encode("ascii"))
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--mapgroupproto", required=True)
    parser.add_argument("--types", required=True)
    parser.add_argument("--max-items", type=int, default=MAX_ITEMS_PER_GROUP,
                        help=f"items per group cap, 1..{MAX_ITEMS_LIMIT} (contract default {MAX_ITEMS_PER_GROUP})")
    parser.add_argument("--output-dir", required=True, help="new directory outside the checkout")
    args = parser.parse_args(argv)
    try:
        proto = interior_points._read_bounded(args.mapgroupproto, interior_points.MAX_STOCK_BYTES)
        types = interior_points._read_bounded(args.types, interior_points.MAX_STOCK_BYTES)
        interior_points._output_path(args.output_dir)  # refuse before parsing anything large
        chunks, report = build_search_groups(proto, types, args.max_items)
        out = write_pack(args.output_dir, chunks, report)
    except (OSError, ValueError) as error:
        print(f"search_context: refused: {error}", file=sys.stderr)
        return 2
    print(f"search_context: {report['GroupCount']} groups in {len(chunks)} chunks -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
