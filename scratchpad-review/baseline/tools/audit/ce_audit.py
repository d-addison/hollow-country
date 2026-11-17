"""Bounded T0 CE XML audit. This module makes no engine eligibility claims.

Only explicitly declared CE files of type 'types' are added to the base types
inventory. Entries are never merged or interpreted as engine override results.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import codecs
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import tempfile
import xml.etree.ElementTree as ET


MAX_FILE_BYTES = 32 * 1024 * 1024
MAX_TOTAL_BYTES = 128 * 1024 * 1024
MAX_SOURCE_FILES = 128
MAX_XML_NODES = 500_000
MAX_XML_DEPTH = 64
COUNT_FIELDS = frozenset(("nominal", "min", "lifetime", "restock", "cost"))
COUNT_ATTRIBUTES = frozenset(("lootmax", "lootmin", "count", "nominal", "min", "max"))
CORE_NUMERIC_DEFAULTS = frozenset(("dyn_radius", "dyn_smin", "dyn_smax", "dyn_dmin", "dyn_dmax"))
FLAG_ATTRIBUTES = frozenset(("count_in_cargo", "count_in_hoarder", "count_in_map", "count_in_player", "crafted", "deloot"))
LIMITATIONS = [
    "T0 offline structural audit only; no installed game or engine behavior verified.",
    "Raw XML points, including points under lootmax=0, are not engine eligible loot opportunities.",
    "Group/model names are not verified building classnames; accessibility, geometry and aliases require engine proof.",
    "Only base types and explicit CE type=types declarations are inventoried; cross-file overrides are reported, not merged or evaluated.",
    "Other declared CE files are checked for safe readable presence and hashed, but their XML schemas are not audited.",
    "Only selected core numeric defaults and prototype numeric attributes are checked; this is not a full DayZ schema validator.",
    "Omitted numeric fields are not defaulted; quantity -1 is retained as an unspecified sentinel.",
    "Catalog authority belongs to the supplied snapshot; without it, type and dispatch proxy classnames are unverified.",
    "Category, usage, tag, value and dynamic-event references are not resolved against CE vocabulary files.",
]


class InputProblem(Exception):
    def __init__(self, code, message):
        self.code = code
        self.message = message
        super().__init__(message)


class BoundedTreeBuilder(ET.TreeBuilder):
    def __init__(self, audit):
        super().__init__()
        self.audit = audit
        self.depth = 0

    def start(self, tag, attrs):
        self.depth += 1
        self.audit.xml_nodes += 1
        if self.depth > MAX_XML_DEPTH or self.audit.xml_nodes > MAX_XML_NODES:
            raise InputProblem("resource_limit", "XML depth or total node budget exceeded.")
        return super().start(tag, attrs)

    def end(self, tag):
        result = super().end(tag)
        self.depth -= 1
        return result

    def doctype(self, name, pubid, system):
        raise InputProblem("unsafe_xml", "DTD and entity declarations are not accepted.")


def _relative(value):
    """CE declarations use either slash convention, but must stay in mission."""
    value = value.replace("\\", "/")
    path = PurePosixPath(value)
    if not value.strip() or path.is_absolute() or ".." in path.parts or ":" in value or "\x00" in value:
        raise InputProblem("unsafe_source_path", "CE source paths must be relative and remain inside the mission.")
    return path.as_posix()


def _alias_key(name):
    # Hints only: no path, case, suffix or Land_ normalization grants a match.
    key = name.replace("\\", "/").rsplit("/", 1)[-1].casefold()
    if key.endswith(".p3d"):
        key = key[:-4]
    return key.removeprefix("land_")


class _Audit:
    def __init__(self, mission):
        self.mission_usable = True
        try:
            self.mission = Path(mission).resolve()
        except (OSError, RuntimeError, ValueError):
            self.mission = Path(mission).absolute()
            self.mission_usable = False
        self.diagnostics = []
        self.sources = []
        self.source_paths = set()
        self.read_paths = set()
        self.total_bytes = 0
        self.xml_nodes = 0
        self.types = defaultdict(list)
        self.prototypes = defaultdict(list)
        self.proxy_types = defaultdict(list)
        self.unknown_proxies = []
        self.placements = Counter()
        self.declarations = []
        self.catalog_status = "not_supplied"
        self.unknown = []
        self.inputs_complete = self.mission_usable
        self.prototypes_available = False
        self.positions_available = False
        if not self.mission_usable:
            self.issue("invalid_mission", "@mission", "mission", "Mission path cannot be resolved safely.")
        # Even missing required inputs must be protected from --output.
        for relative in ("db/types.xml", "types.xml", "mapgroupproto.xml", "mapgrouppos.xml", "cfgeconomycore.xml"):
            self.source_paths.add(self.mission / relative)

    def issue(self, code, source, context, message, severity="error"):
        self.diagnostics.append(dict(severity=severity, code=code, source=source, context=context, message=message))

    def read(self, path, role, source, *, external=False):
        self.source_paths.add(path)
        try:
            resolved = path.resolve()
            if not external and not resolved.is_relative_to(self.mission):
                raise InputProblem("unsafe_source_path", "Resolved source leaves the mission (possibly a symlink).")
            self.source_paths.add(resolved)
            if resolved in self.read_paths and not external:
                raise InputProblem("duplicate_source", "The same source was declared more than once; it was read only once.")
            if len(self.read_paths) >= MAX_SOURCE_FILES:
                raise InputProblem("resource_limit", "Source file count budget exceeded.")
            self.read_paths.add(resolved)
            info = resolved.stat()
            if not stat.S_ISREG(info.st_mode):
                raise InputProblem("unreadable_input", "Input must be a regular file.")
            if info.st_size > MAX_FILE_BYTES or self.total_bytes + info.st_size > MAX_TOTAL_BYTES:
                raise InputProblem("resource_limit", "Source byte budget exceeded.")
            remaining = min(MAX_FILE_BYTES, MAX_TOTAL_BYTES - self.total_bytes)
            with resolved.open("rb") as handle:
                data = handle.read(remaining + 1)
            if len(data) > remaining:
                raise InputProblem("resource_limit", "Source grew beyond its byte budget.")
            self.total_bytes += len(data)
            self.sources.append(dict(path=source, role=role, size_bytes=len(data), sha256=hashlib.sha256(data).hexdigest()))
            return data
        except FileNotFoundError:
            self.issue("missing_required_input", source, role, "Required input is missing.")
        except InputProblem as exc:
            self.issue(exc.code, source, role, exc.message)
        except (OSError, RuntimeError, ValueError):
            self.issue("unreadable_input", source, role, "Input cannot be read safely.")
        self.inputs_complete = False
        return None

    def parse(self, data, source, expected):
        if data is None:
            return None
        try:
            root = ET.fromstring(data, parser=ET.XMLParser(target=BoundedTreeBuilder(self)))
            if root.tag != expected:
                self.issue("unexpected_root", source, "root", f"Expected <{expected}> root.")
                self.inputs_complete = False
                return None
            return root
        except InputProblem as exc:
            self.issue(exc.code, source, "xml", exc.message)
        except (ET.ParseError, ValueError, LookupError):
            # Parser messages may contain private input text; use a fixed message.
            self.issue("malformed_xml", source, "xml", "XML is malformed or uses an unsupported encoding.")
        self.inputs_complete = False
        return None

    def xml(self, relative, role, expected):
        return self.parse(self.read(self.mission / relative, role, relative), relative, expected)

    def name(self, element, source, context):
        value = element.get("name", "")
        if not value.strip():
            self.issue("missing_name", source, context, "A nonempty name attribute is required.")
            return None
        return value

    def integer(self, value, source, context, *, quantity=False):
        code = "invalid_quantity" if quantity else "invalid_count"
        if value is None or re.fullmatch(r"[+-]?[0-9]+", value.strip()) is None:
            self.issue(code, source, context, "Expected an integer count.")
            return None
        try:
            number = int(value)
        except ValueError:
            self.issue(code, source, context, "Integer count is too large to parse.")
            return None
        if number < (-1 if quantity else 0):
            self.issue(code, source, context, "Negative counts are invalid; only quantities allow sentinel -1.")
            return None
        return number

    def vector(self, value, source, context, size=3, nonnegative=False, code=None):
        try:
            values = [float(part) for part in (value or "").split()]
            valid = len(values) == size and all(math.isfinite(part) for part in values)
            valid = valid and (not nonnegative or all(part >= 0 for part in values))
        except (ValueError, OverflowError):
            valid = False
        if not valid:
            code = code or ("invalid_dimension" if nonnegative else "invalid_coordinate")
            self.issue(code, source, context, f"Expected {size} finite numeric component(s)" + (" >= 0." if nonnegative else "."))

    def parse_types(self, relative):
        root = self.xml(relative, "types", "types")
        if root is None:
            return False
        for index, element in enumerate(root.findall("type"), 1):
            context = f"type[{index}]"
            name = self.name(element, relative, context)
            if name is not None:
                previous = self.types[name]
                if relative in previous:
                    self.issue("duplicate_type", relative, name, "Duplicate type entry within one source.")
                elif previous:
                    self.issue("type_override", relative, name, "Type repeats across declared sources; supported override declaration, effective values are not simulated.", "warning")
                previous.append(relative)
            values = {}
            for field in sorted(COUNT_FIELDS | {"quantmin", "quantmax"}):
                fields = element.findall(field)
                if len(fields) > 1:
                    self.issue("duplicate_field", relative, f"{context}/{field}", "Numeric field occurs more than once.")
                for item in fields:
                    values[field] = self.integer(item.text, relative, f"{context}/{field}", quantity=field.startswith("quant"))
            nominal, minimum = values.get("nominal"), values.get("min")
            # Official and installed 1.30 data contain nominal=0/min=1 for
            # event-managed entities. This is not a structural count error.
            if nominal is not None and nominal > 0 and minimum is not None and minimum > nominal:
                self.issue("min_exceeds_nominal", relative, context, "min exceeds nominal.")
            qmin, qmax = values.get("quantmin"), values.get("quantmax")
            if qmin is not None and qmax is not None and qmin >= 0 and qmax >= 0 and qmin > qmax:
                self.issue("invalid_quantity", relative, context, "quantmin exceeds quantmax.")
            for flags in element.findall("flags"):
                for key in sorted(FLAG_ATTRIBUTES & flags.attrib.keys()):
                    if flags.get(key) not in ("0", "1"):
                        self.issue("invalid_flag", relative, f"{context}/flags/{key}", "Flag must be 0 or 1.")

        return True

    def discover_types(self):
        db, root = self.mission / "db/types.xml", self.mission / "types.xml"
        if os.path.lexists(db) and os.path.lexists(root):
            self.issue("ambiguous_types_input", "db/types.xml|types.xml", "types", "Both base types candidates exist; no implicit merge or precedence is assumed.")
            self.inputs_complete = False
            self.parse_types("db/types.xml")
            self.parse_types("types.xml")
        elif os.path.lexists(root):
            self.parse_types("types.xml")
        else:
            self.parse_types("db/types.xml")
        core_source = "cfgeconomycore.xml"
        if not os.path.lexists(self.mission / core_source):
            self.issue("modular_types_not_checked", core_source, "discovery", "Optional core file is absent; only base types were discovered.", "warning")
            return
        core = self.xml(core_source, "economycore", "economycore")
        if core is None:
            return
        for index, default in enumerate(core.findall("defaults/default"), 1):
            if default.get("name") in CORE_NUMERIC_DEFAULTS:
                self.vector(default.get("value"), core_source, f"defaults/default[{index}]/@value",
                            size=1, nonnegative=True, code="invalid_number")
        count = 0
        for ce in core.findall("ce"):
            for element in ce.findall("file"):
                count += 1
                if count > MAX_SOURCE_FILES:
                    self.issue("resource_limit", core_source, "declarations", "CE declaration count budget exceeded.")
                    self.inputs_complete = False
                    return
                context = f"ce/file[{count}]"
                kind = element.get("type", "")
                try:
                    folder = _relative(ce.get("folder", "."))
                    name = _relative(element.get("name", ""))
                    relative = _relative(f"{folder}/{name}")
                except InputProblem as exc:
                    self.issue(exc.code, core_source, context, exc.message)
                    self.inputs_complete = False
                    continue
                self.source_paths.add(self.mission / relative)
                declaration = dict(path=relative, type=kind, status="not_audited")
                self.declarations.append(declaration)
                if kind == "types":
                    declaration["status"] = "audited" if self.parse_types(relative) else "unavailable"
                else:
                    data = self.read(self.mission / relative, "ce_reference", relative)
                    if data is None:
                        declaration["status"] = "unavailable"
                    self.issue("unsupported_ce_file_type", core_source, context, "Declared CE file kind is outside this schema audit; readable presence and hash only, no generic XML merge assumed.", "warning")

    @staticmethod
    def has_alias(element, descendants=True):
        nodes = element.iter() if descendants else (element,)
        return any("alias" in node.tag.casefold() or
                   any("alias" in key.casefold() for key in node.attrib) for node in nodes)

    def parse_prototypes(self):
        source = "mapgroupproto.xml"
        root = self.xml(source, "prototypes", "prototype")
        if root is None:
            return
        self.prototypes_available = True
        for index, element in enumerate(root.iter(), 1):
            context = f"{element.tag}[{index}]"
            for key in sorted(COUNT_ATTRIBUTES & element.attrib.keys()):
                self.integer(element.get(key), source, f"{context}/@{key}")
            for key in ("pos", "rpy"):
                if key in element.attrib or (element.tag in ("point", "proxy") and key == "pos"):
                    self.vector(element.get(key), source, f"{context}/@{key}")
            if "a" in element.attrib:
                self.vector(element.get("a"), source, f"{context}/@a", size=1)
            if element.tag == "point":
                for key in ("range", "height"):
                    if key in element.attrib:
                        self.vector(element.get(key), source, f"{context}/@{key}", size=1, nonnegative=True)
            if element.tag == "point" and "flags" in element.attrib:
                self.integer(element.get("flags"), source, f"{context}/@flags")
            if element.tag == "default" and element.get("name") == "clusterMatrix":
                for key in ("width", "height"):
                    if key in element.attrib:
                        self.vector(element.get(key), source, f"{context}/@{key}", size=1, nonnegative=True)
            if element.tag in ("dispatch", "proxy") and "dechance" in element.attrib:
                self.vector(element.get("dechance"), source, f"{context}/@dechance", size=1,
                            nonnegative=True, code="invalid_probability")
            if element.tag == "proxy":
                name = element.get("type", "")
                if not name.strip():
                    self.issue("missing_proxy_type", source, context, "Proxy requires a nonempty type reference.")
                else:
                    self.proxy_types[name].append(context)
            if self.has_alias(element, descendants=False):
                self.issue("unresolved_alias", source, context, "Alias construct is not interpreted; confirm mapping in the installed engine.", "warning")
        global_aliases = self.has_alias(root, descendants=False) or any(
            self.has_alias(child) for child in root if child.tag != "group")
        for index, group in enumerate(root.findall("group"), 1):
            name = self.name(group, source, f"group[{index}]")
            if name is None:
                continue
            self.prototypes[name].append(dict(container_count=len(group.findall("container")),
                                             raw_point_count=len(group.findall("container/point")),
                                             unresolved_alias=global_aliases or self.has_alias(group)))
            if len(self.prototypes[name]) > 1:
                self.issue("duplicate_group", source, name, "Prototype name is duplicated; placement coverage is ambiguous.")

    def parse_positions(self):
        source = "mapgrouppos.xml"
        root = self.xml(source, "placements", "map")
        if root is None:
            return
        self.positions_available = True
        for index, group in enumerate(root.findall("group"), 1):
            context = f"group[{index}]"
            name = self.name(group, source, context)
            if name is not None:
                self.placements[name] += 1
            self.vector(group.get("pos"), source, f"{context}/@pos")
            for key, size in (("rpy", 3), ("a", 1)):
                if key in group.attrib:
                    self.vector(group.get(key), source, f"{context}/@{key}", size=size)

    def known_types(self, path):
        if path is None:
            return
        self.catalog_status = "invalid"
        source = "@known-types"
        path = Path(path)
        data = self.read(path, "known_types", source, external=True)
        if data is None:
            return
        prefix = data.removeprefix(codecs.BOM_UTF8).lstrip()
        is_xml = prefix.startswith((b"<", codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE,
                                    codecs.BOM_UTF32_LE, codecs.BOM_UTF32_BE))
        if is_xml or path.suffix.casefold() == ".xml":
            # Expat accepts UTF-8/16 byte XML; decode UTF-32 BOMs explicitly.
            if data.startswith((codecs.BOM_UTF32_LE, codecs.BOM_UTF32_BE)):
                try:
                    data = data.decode("utf-32")
                except UnicodeError:
                    self.issue("invalid_catalog", source, "catalog", "Catalog XML has invalid UTF-32 encoding.")
                    return
            root = self.parse(data, source, "types")
            if root is None:
                return
            names = [self.name(item, source, f"type[{index}]") for index, item in enumerate(root.findall("type"), 1)]
        else:
            try:
                names = [line.strip() for line in data.decode("utf-8-sig").splitlines() if line.strip() and not line.lstrip().startswith("#")]
            except UnicodeError:
                self.issue("invalid_catalog", source, "catalog", "Catalog must be UTF-8 text or a <types> XML snapshot.")
                return
        if not names or any(name is None or not name or any(char.isspace() or not char.isprintable() for char in name) for name in names):
            self.issue("invalid_catalog", source, "catalog", "Catalog must contain nonempty classnames without whitespace.")
            return
        self.catalog_status = "supplied"
        known = set(names)
        self.unknown = sorted(self.types.keys() - known)
        self.unknown_proxies = sorted(self.proxy_types.keys() - known)
        for name in self.unknown_proxies:
            for context in self.proxy_types[name]:
                self.issue("unknown_reference", "mapgroupproto.xml", context,
                           "Proxy type is absent from the supplied authoritative catalog.")
        for name in self.unknown:
            self.issue("unknown_type", source, name, "Type is absent from the supplied authoritative catalog.")

    def report(self):
        aliases = defaultdict(list)
        for name in sorted(self.prototypes):
            aliases[_alias_key(name)].append(name)
        rows = []
        for name in sorted(self.prototypes.keys() | self.placements.keys()):
            prototypes = self.prototypes.get(name, [])
            placements = self.placements[name] if self.positions_available else None
            candidates = []
            if not self.prototypes_available or not self.positions_available:
                resolution = "input_unavailable"
            elif not prototypes:
                candidates = aliases.get(_alias_key(name), [])
                code = "possible_alias" if candidates else "missing_group"
                self.issue(code, "mapgrouppos.xml", name, "Placement has no exact prototype match; any alias candidates remain unverified.")
                resolution = "unresolved"
            elif len(prototypes) > 1:
                resolution = "ambiguous"
            elif prototypes[0]["unresolved_alias"]:
                self.issue("unresolved_alias", "mapgroupproto.xml", name,
                           "Prototype has unsupported alias constructs; placed coverage cannot be resolved.",
                           "error" if placements else "warning")
                resolution = "unresolved"
            else:
                resolution = "exact"
            counts = ({key: prototypes[0][key] for key in ("container_count", "raw_point_count")}
                      if len(prototypes) == 1 else dict(container_count=None, raw_point_count=None))
            raw = counts["raw_point_count"]
            placed_raw = raw * placements if raw is not None and placements is not None and resolution == "exact" else None
            if raw == 0 and placements:
                self.issue("zero_raw_points", "mapgroupproto.xml", name, "Placed prototype has zero raw XML points; this is not an engine eligibility conclusion.", "warning")
            rows.append(dict(name=name, resolution=resolution, alias_candidates=candidates, placement_count=placements, **counts, placed_raw_point_count=placed_raw))
        unresolved = sum(row["placement_count"] or 0 for row in rows if row["resolution"] != "exact")
        resolved_points = sum(row["placed_raw_point_count"] or 0 for row in rows if row["resolution"] == "exact")
        coverage_available = self.prototypes_available and self.positions_available
        diagnostics = sorted(self.diagnostics, key=lambda row: (row["source"], row["context"], row["code"], row["message"], row["severity"]))
        return dict(
            schema_version=1,
            valid=not any(row["severity"] == "error" for row in diagnostics),
            inputs_complete=self.inputs_complete,
            sources=sorted(self.sources, key=lambda row: (row["path"], row["role"])),
            diagnostics=diagnostics,
            ce_declarations=sorted(self.declarations, key=lambda row: (row["path"], row["type"])),
            types=dict(entries=sum(map(len, self.types.values())), unique_names=len(self.types), names=sorted(self.types), catalog_status=self.catalog_status, unknown_names=self.unknown),
            references=dict(proxy_type_names=sorted(self.proxy_types),
                            unknown_proxy_type_names=self.unknown_proxies,
                            catalog_status=self.catalog_status),
            coverage=dict(
                inputs_complete=coverage_available,
                placement_count=sum(self.placements.values()) if self.positions_available else None,
                prototype_count=sum(map(len, self.prototypes.values())) if self.prototypes_available else None,
                raw_point_count=sum(item["raw_point_count"] for entries in self.prototypes.values() for item in entries) if self.prototypes_available else None,
                placed_raw_point_count=resolved_points if coverage_available and not unresolved else None,
                resolved_placed_raw_point_count=resolved_points if coverage_available else None,
                unresolved_placement_count=unresolved if self.positions_available else None,
                engine_eligible_loot_points=None,
                building_classes_verified=False,
                groups=rows,
            ),
            limits=dict(max_file_bytes=MAX_FILE_BYTES, max_total_bytes=MAX_TOTAL_BYTES, max_source_files=MAX_SOURCE_FILES, max_xml_nodes=MAX_XML_NODES, max_xml_depth=MAX_XML_DEPTH),
            limitations=LIMITATIONS.copy(),
        )


def _run(mission, known_types=None):
    audit = _Audit(mission)
    if audit.mission_usable:
        audit.discover_types()
        audit.parse_prototypes()
        audit.parse_positions()
        audit.known_types(known_types)
    return audit, audit.report()


def audit_mission(mission, known_types=None):
    """Return a deterministic JSON-compatible report without writing any files."""
    return _run(mission, known_types)[1]


def _json(report):
    return json.dumps(report, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mission", required=True, type=Path, help="Mission directory containing CE XML inputs.")
    parser.add_argument("--output", type=Path, help="Also atomically write JSON here; parent directory must exist.")
    parser.add_argument("--known-types", type=Path, help="Authoritative UTF-8 classname list or <types> XML snapshot.")
    args = parser.parse_args(argv)
    audit, report = _run(args.mission, args.known_types)
    output_problem = None
    if args.output is not None:
        temporary = None
        try:
            resolved = args.output.resolve()
            conflict = resolved in audit.source_paths
            if not conflict and resolved.exists():
                conflict = any(path.exists() and resolved.samefile(path) for path in audit.source_paths)
            if conflict:
                raise InputProblem("output_conflicts_with_source", "Output would overwrite an audit input.")
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n", dir=resolved.parent, prefix=".ce-audit-", delete=False) as handle:
                temporary = Path(handle.name)
                handle.write(_json(report))
            os.replace(temporary, resolved)
        except InputProblem as exc:
            output_problem = (exc.code, exc.message)
        except (OSError, ValueError, RuntimeError):
            output_problem = ("output_error", "JSON output could not be written; check its parent directory and permissions.")
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass
    if output_problem:
        code, message = output_problem
        report["valid"] = False
        report["diagnostics"].append(dict(severity="error", code=code, source="@output", context="output", message=message))
        report["diagnostics"].sort(key=lambda row: (row["source"], row["context"], row["code"]))
    sys.stdout.write(_json(report))
    return 2 if output_problem else (0 if report["valid"] else 1)


if __name__ == "__main__":
    sys.exit(main())
