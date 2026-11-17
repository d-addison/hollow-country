"""Bounded, lossless metadata/source utility cohorts; standard library only.

``build_audit(rows, crafting_census, action_census, provenance)`` accepts decoded
JSON, returns a fresh JSON-compatible report, and performs no filesystem access.
Callers must separately admit/rehash native exports and source files. Internal
manifest consistency is checked here; file authenticity is NOT established.

All upstream source records and native fields survive unchanged. Kit/target and
literal/name links use factorized cohorts rather than materializing Cartesian
products. Their exact denominators include ambiguity and duplicate observations.
Config array containers do not establish element types or repair eligibility.
No config/script identity, effective action registration, condition evaluation,
inventory eligibility, balance decision, or engine qualification is inferred.
"""
from collections import Counter
import hashlib
import json
import math
from pathlib import PurePosixPath
import re


MAX_CLASSES = 16384
MAX_RECIPES = 32768
MAX_ACTIONS = 32768
MAX_SCRIPT_CLASSES = 32768
MAX_METHODS = 131072
MAX_BINDINGS = 131072
MAX_REFERENCES = 262144
MAX_SOURCES = 8192
MAX_FIELDS = 96
MAX_FIELD_VALUES = 256
MAX_ARRAY = 262144
MAX_STRING = 8192
MAX_DEPTH = 32
MAX_NODES = 8_000_000
MAX_WORK = 16_000_000
MAX_INPUT_BYTES = 192 * 1024 * 1024
MAX_OUTPUT_BYTES = 256 * 1024 * 1024
MAX_SOURCE_BYTES = 128 * 1024 * 1024
IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z_0-9]{0,511}\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def _require(condition, code):
    if not condition:
        raise ValueError(code)


class _Budget:
    def __init__(self):
        self.nodes = self.bytes = self.work = 0

    def take(self, amount=1):
        self.work += amount
        _require(self.work <= MAX_WORK, "work_limit")

    def copy(self, value, depth=0):
        self.take()
        self.nodes += 1
        _require(self.nodes <= MAX_NODES, "nodes_limit")
        _require(depth <= MAX_DEPTH, "depth_limit")
        if value is None or type(value) is bool:
            size, result = 5, value
        elif type(value) is int:
            _require(value.bit_length() <= 63, "integer_limit")
            size, result = len(str(value)), value
        elif type(value) is float:
            _require(math.isfinite(value), "nonfinite_number")
            size, result = len(repr(value)), value
        elif type(value) is str:
            _require(len(value) <= MAX_STRING, "string_limit")
            size, result = len(json.dumps(value, ensure_ascii=True)), value
        elif type(value) is list:
            _require(len(value) <= MAX_ARRAY, "array_limit")
            # Charge punctuation before recursively allocating children.
            self.bytes += len(value) + 2
            _require(self.bytes <= MAX_INPUT_BYTES, "input_bytes_limit")
            return [self.copy(v, depth + 1) for v in value]
        elif type(value) is dict:
            _require(len(value) <= 256, "mapping_limit")
            self.bytes += len(value) * 2 + 2
            _require(self.bytes <= MAX_INPUT_BYTES, "input_bytes_limit")
            result = {}
            for key, child in value.items():
                _require(type(key) is str, "json_key_type")
                key = self.copy(key, depth + 1)
                result[key] = self.copy(child, depth + 1)
            return result
        else:
            raise ValueError("json_value_type")
        self.bytes += size
        _require(self.bytes <= MAX_INPUT_BYTES, "input_bytes_limit")
        return result


def _digest(value, maximum, code):
    encoder = json.JSONEncoder(sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                               allow_nan=False)
    digest, size = hashlib.sha256(), 0
    for chunk in encoder.iterencode(value):
        raw = chunk.encode("ascii")
        size += len(raw)
        _require(size <= maximum, code)
        digest.update(raw)
    return digest.hexdigest(), size


def _list(value, maximum, code):
    _require(type(value) is list and len(value) <= maximum, code)
    return value


def _identifier(value):
    return type(value) is str and IDENTIFIER.fullmatch(value) is not None


def _count(coverage, key, actual):
    _require(type(coverage.get(key)) is int and coverage[key] == actual,
             "coverage_mismatch:" + key)


def _manifest(census, budget):
    _require(type(census) is dict and type(census.get("schema_version")) is int
             and census["schema_version"] == 1
             and census.get("evidence_layer") == "T0_source_only"
             and census.get("valid") is True and census.get("inputs_complete") is True,
             "incomplete_source_census")
    coverage = census.get("coverage")
    _require(type(coverage) is dict and coverage.get("source_census_complete") is True,
             "incomplete_source_coverage")
    sources = _list(census.get("sources"), MAX_SOURCES, "source_count")
    paths, total = set(), 0
    for source in sources:
        budget.take()
        _require(type(source) is dict, "source_record")
        path = source.get("path")
        _require(type(path) is str and len(path) <= 1024 and path
                 and "\\" not in path and ":" not in path
                 and all(part not in ("", ".", "..") for part in path.split("/"))
                 and not PurePosixPath(path).is_absolute() and path.lower().endswith(".c"),
                 "source_path")
        _require(path not in paths, "duplicate_source_path")
        paths.add(path)
        size = source.get("bytes")
        _require(type(size) is int and 0 <= size <= 2 * 1024 * 1024, "source_bytes")
        total += size
        _require(total <= MAX_SOURCE_BYTES, "source_bytes_limit")
        _require(type(source.get("sha256")) is str and SHA256.fullmatch(source["sha256"]),
                 "source_sha256")
        _require(source.get("encoding") in ("utf-8-sig", "cp1252"), "source_encoding")
    _count(coverage, "source_files", len(sources))
    _count(coverage, "source_bytes", total)
    fallback = census.get("fallback_encoding")
    _require(fallback in (None, "cp1252"), "source_encoding_policy")
    _require(fallback == "cp1252" or all(s["encoding"] != "cp1252" for s in sources),
             "source_encoding_policy")
    manifest = dict(schema_version=1, suffix=".c (case-insensitive)",
                    fallback_encoding=fallback, sources=sorted(sources, key=lambda s: s["path"]))
    pin, _ = _digest(manifest, MAX_INPUT_BYTES, "manifest_bytes_limit")
    _require(census.get("manifest_sha256") == pin, "source_manifest_digest")

    def visit(value):
        budget.take()
        if type(value) is dict:
            if "source" in value:
                _require(type(value["source"]) is str and value["source"] in paths,
                         "unmanifested_source")
            for child in value.values():
                visit(child)
        elif type(value) is list:
            for child in value:
                visit(child)
    visit(census)
    return manifest


def _unique(records, key, budget, code, identifier=False):
    indexed = {}
    for record in records:
        budget.take()
        _require(type(record) is dict, code)
        name = record.get(key)
        _require(_identifier(name) if identifier else type(name) is str and bool(name), code)
        _require(name not in indexed, "duplicate_" + code)
        indexed[name] = record
    return indexed


def _validate_sources(crafting, actions, budget):
    first = _manifest(crafting, budget)
    second = _manifest(actions, budget)
    _require(first == second, "source_manifest_mismatch")
    recipes = _list(crafting.get("recipes"), MAX_RECIPES, "recipe_count")
    _unique(recipes, "class", budget, "recipe_class", True)
    _count(crafting["coverage"], "declared_recipe_classes", len(recipes))
    _list(crafting.get("registrations"), MAX_BINDINGS, "registration_count")
    specs = (("classes", MAX_SCRIPT_CLASSES, "classes", "class", True),
             ("actions", MAX_ACTIONS, "action_candidates", "class", True),
             ("methods", MAX_METHODS, "method_declarations", "id", False),
             ("bindings", MAX_BINDINGS, "emitted_bindings", "id", False))
    indexes = {}
    for key, maximum, coverage_key, identity, identifier in specs:
        records = _list(actions.get(key), maximum, key + "_count")
        if key == "methods":
            # Native lexical censuses can repeat a declaration ID. Retain every
            # occurrence and bind references to the whole cohort, never last-wins.
            grouped, signatures, occurrences = {}, {}, {}
            for index, record in enumerate(records):
                budget.take()
                _require(type(record) is dict and type(record.get("id")) is str
                         and bool(record["id"]), "method_id")
                name = record["id"]
                grouped.setdefault(name, []).append(record)
                occurrences.setdefault(name, []).append(index)
                signature, _ = _digest(record, MAX_INPUT_BYTES, "method_bytes_limit")
                signatures.setdefault(name, set()).add(signature)
            indexes[key] = grouped
            indexes["method_signatures"] = signatures
            indexes["method_id_cohorts"] = occurrences
        else:
            indexes[key] = _unique(records, identity, budget, key, identifier)
        _count(actions["coverage"], coverage_key, len(records))
    callbacks = _list(actions.get("callbacks"), MAX_METHODS, "callback_count")
    _count(actions["coverage"], "callbacks", len(callbacks))
    for callback in callbacks:
        budget.take()
        _require(type(callback) is dict and type(callback.get("id")) is str
                 and bool(callback["id"]), "callback_id")
        signature, _ = _digest({k: v for k, v in callback.items() if k != "category"},
                               MAX_INPUT_BYTES, "callback_bytes_limit")
        _require(signature in indexes["method_signatures"].get(callback["id"], ()),
                 "callback_method_mismatch")
    aliases = _list(actions.get("aliases"), MAX_SCRIPT_CLASSES, "alias_count")
    _count(actions["coverage"], "aliases", len(aliases))
    candidates = set()
    for name, record in indexes["classes"].items():
        budget.take()
        _require(type(record.get("action_candidate")) is bool, "action_candidate_type")
        if record["action_candidate"]:
            candidates.add(name)
        for key, target in (("declared_method_ids", "methods"), ("direct_binding_ids", "bindings")):
            for identity in _list(record.get(key), MAX_BINDINGS, key):
                budget.take()
                _require(type(identity) is str and identity in indexes[target], "dangling_" + target[:-1])
        for parent in _list(record.get("inherited_registration_sources"), 128, "inherited_sources"):
            budget.take()
            _require(type(parent) is str and parent in indexes["classes"], "dangling_script_class")
    _require(candidates == set(indexes["actions"]), "action_candidate_mismatch")
    for record in indexes["actions"].values():
        for key in ("item_binding_ids", "constructor_binding_ids"):
            for identity in _list(record.get(key), MAX_BINDINGS, key):
                budget.take()
                _require(type(identity) is str and identity in indexes["bindings"], "dangling_binding")
    return indexes


def _captured(field):
    return (type(field) is dict and type(field.get("ValueCaptured")) in (bool, int)
            and field["ValueCaptured"] == 1)


def _kit_id(field):
    if not (_captured(field) and field.get("ReadAs") == "number"
            and field.get("ConfigTypeName") == "CT_INT"
            and type(field.get("ConfigType")) is int and field["ConfigType"] == 0
            and field.get("Status") == "captured" and not field.get("UnresolvedReasons")):
        return None
    value = field.get("ValueInt")
    return value if type(value) is int and value > 0 else None


def _array(field, integers):
    if not (_captured(field) and field.get("ConfigTypeName") == "CT_ARRAY"
            and type(field.get("ConfigType")) is int and field["ConfigType"] == 3
            and field.get("ReadAs") == ("int_array" if integers else "float_array")
            and field.get("Status") in ("captured", "captured_unresolved")):
        return None
    value = field.get("IntValues" if integers else "FloatValues")
    return value if type(value) is list else None


def _prepare_rows(rows, budget):
    _list(rows, MAX_CLASSES, "class_count")
    identities, prepared = set(), []
    for row in rows:
        budget.take()
        _require(type(row) is dict and _identifier(row.get("ConfigRoot"))
                 and _identifier(row.get("ItemClass")), "class_identity")
        root, name = row["ConfigRoot"], row["ItemClass"]
        identity = root + ":" + name
        _require(identity.casefold() not in identities, "duplicate_class_identity")
        identities.add(identity.casefold())
        fields = {}
        for field in _list(row.get("Fields"), MAX_FIELDS, "field_count"):
            budget.take()
            _require(type(field) is dict and type(field.get("ConfigPath")) is str
                     and bool(field["ConfigPath"]), "field_path")
            key = field["ConfigPath"].casefold()
            _require(key not in fields, "duplicate_field")
            fields[key] = field
            for array in ("IntValues", "FloatValues", "TextValues"):
                if array in field:
                    _list(field[array], MAX_FIELD_VALUES, "field_values")
        prepared.append((identity, root, name, fields, row))
    return sorted(prepared, key=lambda r: (r[0].casefold(), r[0]))


def build_audit(rows, crafting_census, action_census, provenance):
    """Enumerate complete admitted cohorts, or raise ValueError without output.

    Limits apply before copying/expansion. Passing decoded input is not secure
    ZIP/file admission. Source manifest validation checks consistency only.
    ``analysis_work`` charges copied nodes, inspected nodes and index operations;
    hashing/sorting are independently bounded by byte and collection limits.
    """
    budget = _Budget()
    _list(rows, MAX_CLASSES, "class_count")
    rows, crafting, actions, provenance = budget.copy([rows, crafting_census, action_census, provenance])
    _require(type(provenance) is dict, "provenance_type")
    source_indexes = _validate_sources(crafting, actions, budget)
    prepared = _prepare_rows(rows, budget)
    kits, names = {}, {}

    def name_cohort(name):
        key = name.casefold()
        if key not in names:
            names[key] = dict(config_classes=[], script_classes=[], recipe_references=[],
                              identity="UNKNOWN_CONFIG_SCRIPT_RELATIONSHIP")
        return names[key]

    for identity, root, name, fields, evidence in prepared:
        budget.take()
        name_cohort(name)["config_classes"].append(identity)
        kit = _kit_id(fields.get("repairkittype"))
        if kit is not None:
            kits.setdefault(str(kit), []).append(identity)
    for name in sorted(source_indexes["classes"]):
        budget.take()
        name_cohort(name)["script_classes"].append(name)

    references, recipe_links = [], 0
    for recipe in crafting["recipes"]:
        refs = _list(recipe.get("literal_references"), MAX_REFERENCES, "reference_count")
        _require(len(references) + len(refs) <= MAX_REFERENCES, "reference_count")
        for index, reference in enumerate(refs):
            budget.take()
            _require(type(reference) is dict and type(reference.get("item")) is str,
                     "literal_reference")
            name = reference["item"]
            cohort = name_cohort(name) if _identifier(name) else None
            count = len(cohort["config_classes"]) if cohort else 0
            resolution = ("invalid_identifier" if cohort is None else "ambiguous_name" if count > 1
                          else "single_name_candidate" if count else "unresolved_name")
            record = dict(recipe=recipe["class"], reference_index=index, evidence=reference,
                          name_cohort=name.casefold() if cohort else None, resolution=resolution,
                          eligibility="NOT_EVALUATED")
            if cohort is not None:
                cohort["recipe_references"].append(len(references))
            references.append(record)
            recipe_links += count

    classes, counts, roots, possible, entries_total = [], Counter(), Counter(), 0, 0
    for identity, root, name, fields, evidence in prepared:
        budget.take()
        allowed = _array(fields.get("repairablewithkits"), True)
        costs = _array(fields.get("repaircosts"), False)
        if "repairablewithkits" not in fields:
            cohort = "field_absent"
        elif allowed is None:
            cohort = "unknown_metadata"
        elif not allowed:
            cohort = "empty_observation"
        elif any(type(v) is int and v > 0 for v in allowed):
            cohort = "positive_id_observed"
        elif all(type(v) is int and v <= 0 for v in allowed):
            cohort = "nonpositive_only"
        else:
            cohort = "unknown_metadata"
        entries = []
        for index, value in enumerate(allowed or []):
            budget.take()
            entries_total += 1
            _require(entries_total <= MAX_REFERENCES, "target_reference_count")
            positive = type(value) is int and value > 0
            key = str(value) if positive else None
            candidates = len(kits.get(key, ()))
            possible += candidates
            resolution = ("unknown_observation" if type(value) is not int else
                          "nonpositive_observation" if not positive else
                          "ambiguous_metadata_candidates" if candidates > 1 else
                          "single_metadata_candidate" if candidates else "no_metadata_candidate")
            cost = costs[index] if costs is not None and index < len(costs) else None
            status = ("unknown_array" if costs is None else "missing" if index >= len(costs)
                      else "observed_nonnegative" if type(cost) in (int, float) and cost >= 0
                      else "invalid_observation")
            entries.append(dict(index=index, observed_id=value, kit_cohort=key,
                                resolution=resolution, cost=cost, cost_status=status))
        alignment = ("unknown" if allowed is None or costs is None else
                     "aligned_observations" if len(allowed) == len(costs) else
                     "missing_costs" if len(allowed) > len(costs) else "surplus_costs")
        counts[cohort] += 1
        roots[root] += 1
        classes.append(dict(id=identity, root=root, name=name, evidence=evidence,
            name_cohort=name.casefold(), inventory_eligibility="NOT_EVALUATED",
            repair=dict(cohort=cohort, kit_id=_kit_id(fields.get("repairkittype")),
                        entries=entries, array_element_typing="UNKNOWN",
                        compatibility="NOT_EVALUATED", cost_alignment=alignment,
                        surplus_costs=costs[len(allowed):] if costs is not None and allowed is not None else [])))

    report = dict(schema_version=1, kind="whole_content_item_utility_cohorts",
        evidence_layer="T0_metadata_source_only", provenance=provenance,
        provenance_authenticated=False, runtime_qualified=False,
        cohort_enumeration_complete=True, link_representation="complete_factorized_cohorts",
        classes=classes, kit_cohorts=dict(sorted(kits.items())), name_cohorts=dict(sorted(names.items())),
        recipe_references=references, source_censuses=dict(crafting=crafting, actions=actions),
        source_method_id_cohorts=source_indexes["method_id_cohorts"],
        denominators=dict(classes=len(classes), recipes=len(crafting["recipes"]),
            actions=len(actions["actions"]), script_classes=len(actions["classes"]),
            sources=len(crafting["sources"]), source_bytes=crafting["coverage"]["source_bytes"],
            methods=len(actions["methods"]), global_functions=sum(m.get("owner_class") is None for m in actions["methods"]),
            repeated_method_id_records=len(actions["methods"]) - len(source_indexes["methods"]),
            callbacks=len(actions["callbacks"]), bindings=len(actions["bindings"]),
            recipe_references=len(references), recipe_config_possible_links=recipe_links,
            target_entries=entries_total, kit_classes=sum(map(len, kits.values())),
            kit_ids=len(kits), kit_target_possible_links=possible,
            repair_cohorts=dict(sorted(counts.items())), by_root=dict(sorted(roots.items()))),
        limitations=["Input files and native run receipts must be independently admitted and rehashed.",
            "Complete means supplied cohort enumeration; gameplay usefulness remains unevaluated.",
            "Array element typing is unknown even for captured native array containers.",
            "Name correspondences do not establish config/script identity or runtime eligibility.",
            "Source conditions, inherited actions, callbacks and registrations are not executed."],
        limits=dict(input_bytes=MAX_INPUT_BYTES, output_bytes=MAX_OUTPUT_BYTES,
                    nodes=MAX_NODES, work=MAX_WORK, classes=MAX_CLASSES, references=MAX_REFERENCES))
    report["input_sha256"], _ = _digest([rows, crafting, actions, provenance], MAX_INPUT_BYTES, "input_bytes_limit")
    report["analysis_work"] = budget.work
    # Stream the full result before returning: no successful partial/truncated report.
    _digest(report, MAX_OUTPUT_BYTES, "output_bytes_limit")
    return report
