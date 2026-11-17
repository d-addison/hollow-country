"""Pure, bounded whole-content review over supplied native/config evidence.

``build_review`` consumes already-produced native rows and a crafting census.  It
does not read files, validate manifests, execute scripts, or establish gameplay
acceptance.  Config inheritance and crafting-script inheritance remain separate.
Names, slots, and roots are observations only; they are never balance or runtime
decisions.
"""
from collections import Counter, defaultdict
import hashlib
import json
import math
import re


MAX_ROWS = 16_384
MAX_RECIPES = 32_768
MAX_REGISTRATIONS = 65_536
MAX_REFERENCES = 262_144
MAX_FIELDS = 96
MAX_FIELD_VALUES = 256
MAX_ANCESTORS = 128
MAX_ARRAY_ITEMS = 262_144
MAX_MAPPING_ITEMS = 256
MAX_INPUT_BYTES = 64 * 1024 * 1024
MAX_OUTPUT_BYTES = 128 * 1024 * 1024
MAX_JSON_NODES = 8_000_000
MAX_JSON_DEPTH = 16
MAX_LINKS = 65_536
MAX_STRING = 4096
IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z_0-9]{0,511}\Z")

ROOT_KINDS = {
    "cfgvehicles": "vehicles",
    "cfgweapons": "weapons",
    "cfgmagazines": "magazines",
    "cfgammo": "ammo",
}
REFERENCE_CALLS = {
    "AddResult": "output",
    "InsertIngredient": "ingredient",
    "InsertIngredientEx": "ingredient",
    "RemoveIngredient": "ingredient",
}


def _require(condition, reason):
    if not condition:
        raise ValueError(reason)


def _copy_json(value, budget, depth=0):
    """Make a bounded JSON-compatible copy; cycles fail at the depth bound."""
    budget[1] -= 1
    _require(depth <= MAX_JSON_DEPTH and budget[1] >= 0,
             "input_structure_budget")
    if isinstance(value, dict):
        _require(len(value) <= MAX_MAPPING_ITEMS, "mapping_budget")
        copied = {}
        for key, child in value.items():
            _require(type(key) is str and len(key) <= 256 and not _surrogate(key),
                     "invalid_json_key")
            budget[0] -= len(json.dumps(key, ensure_ascii=True)) + 1
            copied[key] = _copy_json(child, budget, depth + 1)
        budget[0] -= 2
    elif type(value) in (list, tuple):
        _require(len(value) <= MAX_ARRAY_ITEMS, "array_budget")
        copied = [_copy_json(child, budget, depth + 1) for child in value]
        budget[0] -= len(copied) + 2
    else:
        _require(type(value) in (str, int, float, bool, type(None)),
                 "non_json_value")
        if type(value) is str:
            _require(len(value) <= MAX_STRING and not _surrogate(value),
                     "string_budget_or_surrogate")
        elif type(value) is int:
            _require(value.bit_length() <= 63, "integer_budget")
        elif type(value) is float:
            _require(math.isfinite(value), "nonfinite_value")
        rendered = json.dumps(value, ensure_ascii=True, allow_nan=False)
        budget[0] -= len(rendered)
        copied = value
    _require(budget[0] >= 0, "input_byte_budget")
    return copied


def _surrogate(value):
    return any(0xD800 <= ord(character) <= 0xDFFF for character in value)


def _digest(value, limit):
    digest = hashlib.sha256()
    size = 0
    encoder = json.JSONEncoder(sort_keys=True, separators=(",", ":"),
                               ensure_ascii=True, allow_nan=False)
    for text in encoder.iterencode(value):
        encoded = text.encode("ascii")
        size += len(encoded)
        _require(size <= limit, "serialized_byte_budget")
        digest.update(encoded)
    return digest.hexdigest()


def _identifier(value):
    return type(value) is str and IDENTIFIER.fullmatch(value) is not None


def _captured(field):
    value = field.get("ValueCaptured")
    return type(value) in (int, bool) and value == 1


def _number(field):
    if not _captured(field) or field.get("ReadAs") != "number":
        return None
    key = {"CT_INT": "ValueInt", "CT_FLOAT": "ValueFloat"}.get(
        field.get("ConfigTypeName"))
    value = field.get(key) if key else None
    return value if type(value) in (int, float) and math.isfinite(value) else None


def _explicit_truth(field):
    """Return True only for a captured, explicit boolean/numeric true value."""
    number = _number(field)
    if number is not None:
        return number == 1
    if not _captured(field):
        return False
    if field.get("ReadAs") == "text" and field.get("ConfigTypeName") == "CT_STRING":
        value = field.get("ValueText")
        return type(value) is str and value.casefold() in ("true", "yes", "legacy",
                                                            "abstract", "hidden")
    return False


def _prepare_rows(rows):
    identities = set()
    for row in rows:
        _require(isinstance(row, dict) and _identifier(row.get("ConfigRoot"))
                 and _identifier(row.get("ItemClass")), "invalid_class_identity")
        identity = (row["ConfigRoot"].casefold(), row["ItemClass"].casefold())
        _require(identity not in identities, "duplicate_class_identity")
        identities.add(identity)
        ancestors = row.get("ConfigAncestors")
        fields = row.get("Fields")
        _require(type(ancestors) is list and len(ancestors) <= MAX_ANCESTORS
                 and all(_identifier(value) for value in ancestors),
                 "invalid_config_ancestry")
        _require(type(fields) is list and len(fields) <= MAX_FIELDS,
                 "field_budget_or_shape")
        parent = row.get("ParentClass")
        _require(parent is None or _identifier(parent), "invalid_config_parent")
        paths = set()
        for field in fields:
            _require(isinstance(field, dict)
                     and type(field.get("ConfigPath")) is str
                     and 0 < len(field["ConfigPath"]) <= 512,
                     "invalid_field_path")
            path = field["ConfigPath"].casefold()
            _require(path not in paths, "duplicate_config_field")
            paths.add(path)
            for value in field.values():
                if isinstance(value, list):
                    _require(len(value) <= MAX_FIELD_VALUES, "field_array_budget")
        fields.sort(key=lambda field: (field["ConfigPath"].casefold(),
                                       field["ConfigPath"]))
    rows.sort(key=lambda row: (row["ConfigRoot"].casefold(),
                               row["ItemClass"].casefold(),
                               row["ConfigRoot"], row["ItemClass"]))


def _definition_evidence(row):
    fields = {field["ConfigPath"].casefold(): field for field in row["Fields"]}
    evidence = []

    def add(kind, source, value):
        if kind not in {entry["kind"] for entry in evidence}:
            evidence.append({"kind": kind, "source": source, "value": value})

    scope = _number(fields.get("scope", {}))
    if scope == 0:
        add("hidden", "Fields.scope", 0)
    for key, kind in (("abstract", "abstract"), ("isabstract", "abstract"),
                      ("hidden", "hidden"), ("ishidden", "hidden"),
                      ("legacy", "legacy"), ("islegacy", "legacy"),
                      ("deprecated", "legacy"), ("obsolete", "legacy")):
        if key in fields and _explicit_truth(fields[key]):
            add(kind, "Fields." + fields[key]["ConfigPath"], True)
    for key, kind in (("IsAbstract", "abstract"), ("IsHidden", "hidden"),
                      ("IsLegacy", "legacy")):
        if type(row.get(key)) is bool and row[key]:
            add(kind, key, True)
    status = row.get("DefinitionStatus")
    if type(status) is str and status.casefold() in ("abstract", "hidden", "legacy"):
        add(status.casefold(), "DefinitionStatus", status)
    evidence.sort(key=lambda item: (item["kind"], item["source"]))
    return evidence


def _class_record(row):
    root, name = row["ConfigRoot"], row["ItemClass"]
    evidence = _definition_evidence(row)
    ancestry_keys = [value.casefold() for value in row["ConfigAncestors"]]
    issues = []
    if name.casefold() in ancestry_keys:
        issues.append("config_ancestry_contains_self")
    if len(set(ancestry_keys)) != len(ancestry_keys):
        issues.append("duplicate_config_ancestor")
    kinds = {item["kind"] for item in evidence}
    if kinds.intersection(("abstract", "hidden")):
        review_status = "excluded-definition"
        status_reasons = ["explicit_" + kind + "_definition" for kind in sorted(kinds)
                          if kind in ("abstract", "hidden")]
    elif "legacy" in kinds or issues:
        review_status = "review-unresolved"
        status_reasons = (["explicit_legacy_definition"] if "legacy" in kinds else []) + issues
    else:
        review_status = "retain"
        status_reasons = ["retained_in_whole_content_review"]
    return {
        "id": root + ":" + name,
        "root": root,
        "root_kind": ROOT_KINDS.get(root.casefold(), "other"),
        "inventory_eligibility": "NOT_EVALUATED",
        "name": name,
        "config_parent": row.get("ParentClass"),
        "config_ancestors": row["ConfigAncestors"],
        "config_inheritance_issues": issues,
        "script_inheritance": "UNKNOWN_NOT_DERIVED_FROM_CONFIG",
        "definition_evidence": evidence,
        "review_status": review_status,
        "review_reasons": status_reasons,
        "existing_use_links": [],
        "crafting_links": [],
        "link_counts": {
            "existing_use_possible": 0, "existing_use_emitted": 0,
            "crafting_possible": 0, "crafting_emitted": 0,
        },
    }


def _prepare_census(census):
    _require(type(census) is dict, "crafting_census_shape")
    recipes = census.get("recipes")
    registrations = census.get("registrations")
    _require(type(recipes) is list and len(recipes) <= MAX_RECIPES,
             "recipe_budget_or_shape")
    _require(type(registrations) is list and len(registrations) <= MAX_REGISTRATIONS,
             "registration_budget_or_shape")
    total_references = 0
    for recipe in recipes:
        _require(isinstance(recipe, dict) and _identifier(recipe.get("class")),
                 "invalid_recipe_identity")
        facts = recipe.get("literal_references")
        _require(type(facts) is list, "reference_shape")
        total_references += len(facts)
        _require(total_references <= MAX_REFERENCES, "reference_budget")
        for fact in facts:
            # Keep malformed literals as unresolved source evidence. All strings
            # are already bounded by _copy_json; never repair them into classes.
            _require(isinstance(fact, dict) and type(fact.get("item")) is str,
                     "invalid_item_reference")
    for registration in registrations:
        _require(isinstance(registration, dict), "registration_shape")
    recipes.sort(key=lambda recipe: (recipe["class"].casefold(), recipe["class"],
                                     _digest(recipe, MAX_INPUT_BYTES)))
    registrations.sort(key=lambda item: (
        str(item.get("source", "")), item.get("line", 0),
        bool(item.get("disabled", False)), str(item.get("call", "")),
        str(item.get("class", "")), _digest(item, MAX_INPUT_BYTES)))
    return total_references


def _recipe_records(recipes, classes_by_name, census_valid):
    records = []
    occurrence = Counter()
    for recipe in recipes:
        name = recipe["class"]
        occurrence[name.casefold()] += 1
        recipe_id = "recipe:" + name + ":" + str(occurrence[name.casefold()])
        references = []
        for index, fact in enumerate(recipe["literal_references"]):
            candidates = classes_by_name.get(fact["item"].casefold(), ())
            resolution = ("unresolved" if not candidates else
                          "confirmed" if len(candidates) == 1 else "ambiguous")
            role = REFERENCE_CALLS.get(fact.get("call"), "unresolved")
            references.append({
                "id": recipe_id + ":reference:" + str(index + 1),
                "item": fact["item"],
                "role": role,
                "call": fact.get("call"),
                "slot": fact.get("slot"),
                "resolution": resolution,
                "candidate_count": len(candidates),
                "emitted_candidate_count": 0,
                "evidence": fact,
            })
        unresolved = recipe.get("unresolved")
        _require(type(unresolved) is list, "recipe_unresolved_shape")
        status = recipe.get("source_status", "unknown")
        reasons = []
        if not census_valid:
            reasons.append("upstream_crafting_census_not_valid")
        if status not in ("registered", "unregistered", "disabled"):
            reasons.append("registration_status_" + str(status))
        if unresolved:
            reasons.append("recipe_semantics_unresolved")
        if any(reference["resolution"] != "confirmed" or
               reference["role"] == "unresolved" for reference in references):
            reasons.append("item_references_unresolved_or_ambiguous")
        records.append({
            "id": recipe_id,
            "class": name,
            "declaration_status": recipe.get("declaration_status", "unknown"),
            "source_status": status,
            "runtime_status": recipe.get("runtime_status", "unknown"),
            "script_ancestry": recipe.get("ancestry", []),
            "script_ancestry_resolved": bool(recipe.get("recipe_ancestry_resolved", False)),
            "config_inheritance": "NOT_INFERRED_FROM_SCRIPT",
            "definitions": recipe.get("definitions", []),
            "registrations": recipe.get("registrations", []),
            "disabled_registrations": recipe.get("disabled_registrations", []),
            "unregistrations": recipe.get("unregistrations", []),
            "unresolved": unresolved,
            "references": references,
            "review_status": "review-unresolved" if reasons else "retain",
            "review_reasons": reasons or ["source_evidence_retained"],
        })
    return records


def _registration_counts(registrations):
    return {
        "registration_records": len(registrations),
        "active_registration_calls": sum(
            row.get("call") == "RegisterRecipe" and not row.get("disabled", False)
            for row in registrations),
        "comment_disabled_registration_calls": sum(
            row.get("call") == "RegisterRecipe" and bool(row.get("disabled", False))
            for row in registrations),
        "active_unregistration_calls": sum(
            row.get("call") == "UnregisterRecipe" and not row.get("disabled", False)
            for row in registrations),
        "comment_disabled_unregistration_calls": sum(
            row.get("call") == "UnregisterRecipe" and bool(row.get("disabled", False))
            for row in registrations),
        "unresolved_registration_records": sum(bool(row.get("unresolved"))
                                                for row in registrations),
    }


def _link_review(classes, recipes):
    by_id = {item["id"]: item for item in classes}
    by_identity = {(item["root"].casefold(), item["name"].casefold()): item
                   for item in classes}
    by_name = defaultdict(list)
    for item in classes:
        by_name[item["name"].casefold()].append(item)
    for values in by_name.values():
        values.sort(key=lambda item: (item["id"].casefold(), item["id"]))

    config_edges = []
    for child in classes:
        parent_name = child["config_parent"]
        if parent_name is None:
            continue
        parent = by_identity.get((child["root"].casefold(), parent_name.casefold()))
        if parent is None or parent is child:
            child["config_inheritance_issues"].append(
                "self_config_parent" if parent is child else "unresolved_config_parent")
            if child["review_status"] == "retain":
                child["review_status"] = "review-unresolved"
                child["review_reasons"] = [child["config_inheritance_issues"][-1]]
            continue
        child["link_counts"]["existing_use_possible"] += 1
        parent["link_counts"]["existing_use_possible"] += 1
        config_edges.append((child, parent))

    reference_rows = []
    references_by_name = Counter()
    possible = len(config_edges)
    for recipe in recipes:
        for reference in recipe["references"]:
            name = reference["item"].casefold()
            candidates = by_name.get(name, ())
            reference_rows.append((recipe, reference, candidates))
            references_by_name[name] += 1
            possible += len(candidates)

    # Count ambiguous possibilities algebraically. Visiting every candidate for
    # every reference would do rows*references work before the emission budget.
    for item in classes:
        item["link_counts"]["crafting_possible"] = references_by_name[item["name"].casefold()]

    links = []

    def emit(kind, payload, attached):
        if len(links) >= MAX_LINKS:
            return False
        link_id = "link:" + str(len(links) + 1)
        links.append({"id": link_id, "kind": kind, **payload})
        for item, bucket in attached:
            item[bucket].append(link_id)
            counter = "existing_use_emitted" if bucket == "existing_use_links" else "crafting_emitted"
            item["link_counts"][counter] += 1
        return True

    for child, parent in config_edges:
        emit("config_inheritance", {"child": child["id"], "parent": parent["id"],
                                    "resolution": "confirmed",
                                    "evidence": "ParentClass_same_root"},
             ((child, "existing_use_links"), (parent, "existing_use_links")))
    for recipe, reference, candidates in reference_rows:
        for candidate in candidates:
            if not emit("crafting_reference",
                        {"recipe": recipe["id"], "reference": reference["id"],
                         "class": candidate["id"], "role": reference["role"],
                         "resolution": reference["resolution"]},
                        ((candidate, "crafting_links"),)):
                break
            reference["emitted_candidate_count"] += 1
        if len(links) >= MAX_LINKS:
            break
    for item in classes:
        item["config_inheritance_issues"] = sorted(set(item["config_inheritance_issues"]))
        item["existing_use_links"].sort(key=lambda value: int(value.split(":")[1]))
        item["crafting_links"].sort(key=lambda value: int(value.split(":")[1]))
    return links, possible, by_id


def build_review(rows, crafting_census, provenance):
    """Build a deterministic review workbook from caller-supplied evidence.

    All inputs are copied and bounded before classification.  Oversize, cyclic,
    non-JSON, non-finite, or duplicate class identities raise ``ValueError``.
    Link overflow retains every class, recipe and reference while reporting exact
    possible/emitted/omitted counts.  Provenance is copied, not authenticated.
    """
    _require(type(rows) in (list, tuple) and len(rows) <= MAX_ROWS,
             "row_budget_or_shape")
    _require(type(crafting_census) is dict, "crafting_census_shape")
    _require(type(provenance) is dict, "provenance_shape")
    copied = _copy_json({"rows": rows, "crafting_census": crafting_census,
                         "provenance": provenance},
                        [MAX_INPUT_BYTES, MAX_JSON_NODES])
    rows = copied["rows"]
    census = copied["crafting_census"]
    provenance = copied["provenance"]
    _prepare_rows(rows)
    total_references = _prepare_census(census)
    classes = [_class_record(row) for row in rows]
    classes_by_name = defaultdict(list)
    for item in classes:
        classes_by_name[item["name"].casefold()].append(item)
    census_valid = census.get("valid") is True
    recipes = _recipe_records(census["recipes"], classes_by_name, census_valid)
    links, possible_links, _ = _link_review(classes, recipes)

    references = [reference for recipe in recipes for reference in recipe["references"]]
    registration_counts = _registration_counts(census["registrations"])
    denominators = {
        "input_classes": len(rows),
        "output_classes": len(classes),
        "input_recipes": len(census["recipes"]),
        "output_recipes": len(recipes),
        "literal_references": total_references,
        "confirmed_references": sum(row["resolution"] == "confirmed" for row in references),
        "ambiguous_references": sum(row["resolution"] == "ambiguous" for row in references),
        "unresolved_references": sum(row["resolution"] == "unresolved" for row in references),
        "by_root": dict(sorted(Counter(item["root"] for item in classes).items())),
        "by_root_kind": dict(sorted(Counter(item["root_kind"] for item in classes).items())),
        "by_review_status": dict(sorted(Counter(item["review_status"] for item in classes).items())),
        "recipes_by_source_status": dict(sorted(Counter(
            recipe["source_status"] for recipe in recipes).items())),
        **registration_counts,
    }
    result = {
        "schema_version": 1,
        "kind": "whole_content_item_review",
        "provenance": provenance,
        "provenance_authenticated": False,
        "source_inputs_sha256": _digest(copied, MAX_INPUT_BYTES),
        "upstream_crafting_census_valid": census_valid,
        "upstream_reported_coverage": census.get("coverage"),
        "upstream_manifest_validation": "NOT_PERFORMED_BY_THIS_FUNCTION",
        "denominators": denominators,
        "classes": classes,
        "recipes": recipes,
        "registrations": census["registrations"],
        "links": links,
        "link_enumeration": {
            "possible": possible_links,
            "emitted": len(links),
            "omitted": possible_links - len(links),
            "complete": len(links) == possible_links,
            "stop_reason": "" if len(links) == possible_links else "link_budget",
        },
        "full_coverage": False,
        "full_feature_pass": False,
        "feature_acceptance": "NOT_EVALUATED",
        "review_status_meaning": {
            "retain": "retained in this review denominator; not a gameplay or balance decision",
            "review-unresolved": "retained with unresolved evidence; not a rejection",
            "excluded-definition": "explicit abstract/hidden definition evidence only; not gameplay incompatibility",
        },
        "limitations": [
            "No file ingestion, native execution, manifest authentication, or runtime registry verification is performed.",
            "Config roots identify observed namespaces, not inventory or equipment eligibility.",
            "Config inheritance is not script inheritance; names and slot metadata do not prove gameplay usability or craftability.",
            "Registered and comment-disabled source calls do not establish the live recipe registry.",
            "Literal ingredient/output references do not establish effective inherited recipe semantics or yields.",
            "Caller provenance and upstream coverage are copied, not authenticated.",
        ],
        "limits": {
            "rows": MAX_ROWS, "recipes": MAX_RECIPES,
            "registrations": MAX_REGISTRATIONS, "references": MAX_REFERENCES,
            "input_bytes": MAX_INPUT_BYTES, "output_bytes": MAX_OUTPUT_BYTES,
            "json_nodes": MAX_JSON_NODES, "json_depth": MAX_JSON_DEPTH,
            "links": MAX_LINKS,
        },
    }
    _digest(result, MAX_OUTPUT_BYTES)
    return result
