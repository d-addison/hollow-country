"""Complete supplied-cohort utility decisions, not gameplay qualification.

build_review(rows, crafting_census, action_census, provenance, source_files,
             *, proposals=()) returns a bounded JSON workbook without file IO.
source_files maps EVERY manifested path to exact original bytes. Native rows
still require external admission; source hashes prove consistency, not origin.
No model/name-to-material guesses, effective registration, inventory eligibility,
new gameplay recipes or runtime success are inferred. A supported template means
literal direct-RecipeBase Init plus trivial CanDo, not observed effective yield.
Config-default/max quantities remain symbolic. Proposed conversions are
design records, never executable commands or automatic recipe registrations.
"""
from collections import Counter, defaultdict
from fractions import Fraction
import hashlib
import re

from tools.audit import crafting_audit as source
from tools.audit import item_utility as utility

MAX_OUTPUT_BYTES = utility.MAX_OUTPUT_BYTES
MAX_PROPOSALS = 256
MAX_GRAPH_EDGES = 262144
DIMENSIONS = ("native_use", "repair", "craft", "material", "tool",
              "candidate", "exclusion", "unresolved")
STATUSES = ("retain", "candidate", "exclude", "hold", "unknown", "none")
SCALAR_PARAMETERS = {"m_Name", "m_IsInstaRecipe", "m_AnimationLength", "m_Specialty",
                     "m_AnywhereInInventory", "m_RecipeUID"}
INGREDIENT_PARAMETERS = {"m_MinQuantityIngredient", "m_MaxQuantityIngredient",
    "m_MinDamageIngredient", "m_MaxDamageIngredient", "m_IngredientUseSoftSkills",
    "m_IngredientAddHealth", "m_IngredientAddQuantity", "m_IngredientSetHealth",
    "m_IngredientDestroy"}
RESULT_PARAMETERS = {"m_ResultSetFullQuantity", "m_ResultSetQuantity",
    "m_ResultSetHealth", "m_ResultSpawnDistance", "m_ResultToInventory",
    "m_ResultInheritsHealth", "m_ResultInheritsColor", "m_ResultReplacesIngredient",
    "m_ResultUseSoftSkills"}
_require = utility._require


def _files(census, supplied):
    _require(type(supplied) is dict and len(supplied) <= utility.MAX_SOURCES,
             "source-files")
    expected = {s["path"]: s for s in census["sources"]}
    _require(set(supplied) == set(expected), "source-files-manifest")
    total = 0
    for path, record in sorted(expected.items()):
        raw = supplied[path]
        _require(type(raw) is bytes and len(raw) == record["bytes"], "source-bytes")
        total += len(raw)
        _require(total <= utility.MAX_SOURCE_BYTES, "source-total")
        _require(hashlib.sha256(raw).hexdigest() == record["sha256"], "source-sha256")
        # Recheck the recorded decoder, without a permissive replacement policy.
        raw.decode(record["encoding"])
    return expected


def _scalar(tokens):
    text = "".join(t.text for t in tokens)
    if text in ("true", "false"):
        return text == "true", True
    if re.fullmatch(r"-?[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?", text):
        number = float(text) if any(c in text for c in ".eE") else int(text)
        if type(number) is int:
            return (number, True) if number.bit_length() <= 31 else (None, False)
        import math
        return (number, True) if math.isfinite(number) else (None, False)
    if len(tokens) == 1 and tokens[0].kind == "string":
        return source._string(tokens), True
    return None, False


def _parameters(tokens):
    parameters, holds, seen = {}, [], set()
    statements, start = [], 0
    for index, token in enumerate(tokens):
        if token.text == ";":
            statements.append(tokens[start:index])
            start = index + 1
    if start != len(tokens):
        holds.append("unsupported-init-statement")
    for parts in statements:
        if not parts:
            continue
        text = [t.text for t in parts]
        if text[0] in ("InsertIngredient", "AddResult") and len(text) > 2:
            continue
        field, slot, rhs = None, None, None
        if len(text) >= 3 and text[0].startswith("m_") and text[1] == "=":
            field, rhs = text[0], parts[2:]
        elif (len(text) >= 6 and text[0].startswith("m_") and text[1] == "["
              and text[2].isdigit() and text[3:5] == ["]", "="]):
            field, slot, rhs = text[0], int(text[2]), parts[5:]
        if field is None:
            holds.append("unsupported-init-statement")
            continue
        supported = (field in SCALAR_PARAMETERS and slot is None
                     or field in INGREDIENT_PARAMETERS and slot in (0, 1)
                     or field in RESULT_PARAMETERS and slot is not None and 0 <= slot < 10)
        if not supported:
            holds.append("unsupported-recipe-parameter")
        value, known = _scalar(rhs)
        key = (field, slot)
        if key in seen:
            holds.append("repeated-parameter")
        seen.add(key)
        if not known or any(t.conditions for t in parts):
            holds.append("dynamic-or-conditional-parameter")
        parameters.setdefault(field, []).append(dict(
            slot=slot, value=value, literal=known and not any(t.conditions for t in parts),
            expression="".join(t.text for t in rhs),
            line=parts[0].line))
    return dict(sorted(parameters.items())), holds


def _value(parameters, name, slot):
    found = [v for v in parameters.get(name, []) if v["slot"] == slot]
    return found[0]["value"] if len(found) == 1 and found[0]["literal"] else None


def _flag(value):
    # Installed recipes use both bool keywords and integer 0/1 for bool fields.
    # Keep the declared value intact; normalize only the semantic lookup.
    if type(value) is bool or type(value) is int and value in (0, 1):
        return bool(value)
    return None


def _selector(value):
    # RecipeBase selectors are int[] (RecipeBase.c:59-62); installed recipes also
    # write bool literals into them (e.g. m_ResultToInventory[1] = false), which
    # the native compiler accepts as 0/1. Other types never match a selector.
    if type(value) is bool:
        return int(value)
    return value if type(value) is int else None


def _parameter_values(parameters, result_count):
    """Validate literal types/selectors against installed RecipeBase declarations.

    Preserve invalid observations in parameters; a hold prevents interpreting them
    as a usable template. This does not evaluate config limits or native casts.
    """
    holds = []
    boolean = {"m_IsInstaRecipe", "m_AnywhereInInventory", "m_IngredientDestroy",
               "m_IngredientUseSoftSkills", "m_ResultSetFullQuantity", "m_ResultUseSoftSkills"}
    selectors = {"m_ResultInheritsHealth": {-2, -1, 0, 1},
                 "m_ResultInheritsColor": {-1, 0, 1},
                 "m_ResultReplacesIngredient": {-1, 0, 1},
                 "m_ResultToInventory": {-2, -1, 0, 1}}
    if result_count > 10:
        holds.append("result-slot-out-of-range")
    for field, values in parameters.items():
        for entry in values:
            value = entry["value"]
            if field in RESULT_PARAMETERS and (entry["slot"] is None or entry["slot"] >= result_count):
                holds.append("result-slot-out-of-range")
            if not entry["literal"]:
                continue
            valid = (type(value) is str if field == "m_Name" else
                     _flag(value) is not None if field in boolean else
                     _selector(value) in selectors[field] if field in selectors else
                     type(value) is int if field == "m_RecipeUID" else
                     type(value) in (int, float))
            if not valid:
                holds.append("invalid-recipe-parameter-value")
    for slot in (0, 1):
        for low, high in (("m_MinQuantityIngredient", "m_MaxQuantityIngredient"),
                          ("m_MinDamageIngredient", "m_MaxDamageIngredient")):
            minimum, maximum = _value(parameters, low, slot), _value(parameters, high, slot)
            if (type(minimum) in (int, float) and type(maximum) in (int, float)
                    and minimum >= 0 and maximum >= 0 and minimum > maximum):
                holds.append("invalid-recipe-parameter-value")
    return holds


def _family(recipe, parsed, text_tokens):
    definitions = [d for d in parsed if d["class"] == recipe["class"]]
    actual_refs, actual_methods, actual_definitions, actual_unresolved = [], [], [], []
    for definition in definitions:
        tokens, pairs = text_tokens[definition["source"]]
        refs, unresolved = source._literal_references(definition, tokens, pairs)
        actual_refs.extend(refs)
        actual_unresolved.extend(unresolved)
        actual_methods.extend(source._public(m) for m in definition["methods"])
        actual_definitions.append({k: definition[k] for k in
                                  ("source", "line", "parent", "modded", "conditions")})
    _require(actual_refs == recipe.get("literal_references")
             and actual_methods == recipe.get("methods")
             and actual_definitions == recipe.get("definitions"), "recipe-source-facts")
    holds, parameters, roles = [], {}, {}
    if actual_unresolved:
        holds.append("dynamic-or-unparsed-item-reference")
    if any(r["conditions"] for r in actual_refs):
        holds.append("conditional-item-reference")
    if (len(definitions) != 1 or recipe.get("recipe_ancestry_resolved") is not True
            or recipe.get("ancestry") != [recipe["class"], "RecipeBase"]):
        holds.append("inherited-or-ambiguous-semantics")
    elif definitions[0]["conditions"] or definitions[0]["modded"]:
        holds.append("conditional-or-modded-definition")
    else:
        definition = definitions[0]
        tokens, _ = text_tokens[definition["source"]]
        initializers = [m for m in definition["methods"] if m["name"] == "Init"]
        if len(initializers) != 1:
            holds.append("missing-or-ambiguous-init")
        else:
            init = initializers[0]
            parameters, failures = _parameters(tokens[init["_start"] + 1:init["_end"]])
            holds.extend(failures)
        if sum(m["name"] == "CanDo" for m in definition["methods"]) != 1:
            holds.append("missing-or-ambiguous-cando")
        for method in definition["methods"]:
            body = [t.text for t in tokens[method["_start"] + 1:method["_end"]]]
            if method["conditions"]:
                holds.append("conditional-method")
            if method["name"] == "CanDo":
                if body != ["return", "true", ";"]:
                    holds.append("native-custom-condition")
            elif method["name"] != "Init":
                holds.append("custom-mutation-or-method")
    inputs, outputs = [], []
    for reference in actual_refs:
        if reference["call"] == "InsertIngredient" and reference["method"] == "Init":
            inputs.append(reference)
        elif reference["call"] == "AddResult" and reference["method"] == "Init":
            index = len(outputs)
            full = _flag(_value(parameters, "m_ResultSetFullQuantity", index))
            quantity = _value(parameters, "m_ResultSetQuantity", index)
            color = _value(parameters, "m_ResultInheritsColor", index)
            if color is None or type(color) is not int or color != -1:
                holds.append("dynamic-output-class")
            if full is True:
                amount = dict(kind="config-max", value=None)
            elif full is False and type(quantity) in (int, float):
                amount = dict(kind="config-default" if quantity == -1 else "literal",
                              value=None if quantity == -1 else quantity)
                if quantity != -1 and quantity <= 0:
                    holds.append("nonpositive-output-quantity")
                if type(quantity) is float and not quantity.is_integer():
                    # RecipeBase copies this float into int value_delta before
                    # SetQuantity/ServerSetAmmoCount; never publish it as yield.
                    amount = dict(kind="unknown", value=None)
                    holds.append("fractional-output-quantity")
            else:
                amount = dict(kind="unknown", value=None)
                holds.append("unknown-output-quantity")
            outputs.append(dict(index=index, reference=reference, quantity=amount))
        else:
            holds.append("custom-ingredient-or-result-semantics")
    if {r["slot"] for r in inputs} != {0, 1}:
        holds.append("incomplete-declared-ingredient-slots")
    holds.extend(_parameter_values(parameters, len(outputs)))
    for slot in ("0", "1"):
        number = int(slot)
        destroy = _flag(_value(parameters, "m_IngredientDestroy", number))
        delta = _value(parameters, "m_IngredientAddQuantity", number)
        wear = _value(parameters, "m_IngredientAddHealth", number)
        set_health = _value(parameters, "m_IngredientSetHealth", number)
        roles[slot] = ("material" if destroy is True or type(delta) in (int, float) and delta < 0
                      else "tool" if destroy is False and type(delta) in (int, float) and delta == 0
                      and type(wear) in (int, float) and wear <= 0 and set_health == -1 else "unknown")
    if holds:
        roles = {"0": "unknown", "1": "unknown"}
    status = recipe.get("source_status")
    if status not in ("registered", "disabled", "unregistered"):
        holds.append("conditional-or-unresolved-registration")
        roles = {"0": "unknown", "1": "unknown"}
    decision = ("preserve-native" if status == "registered" else
                "retain-disabled-definition" if status == "disabled" else
                "retain-unregistered-definition" if status == "unregistered" else
                "hold-conditional-or-unresolved-registration")
    return dict(id=recipe["class"], decision=decision, source_status=status,
                source_template_supported=not holds, holds=sorted(set(holds)),
                parameters=parameters, ingredient_roles=roles, inputs=inputs, outputs=outputs,
                adds_new_recipe=False, implementation_approved=False,
                runtime_qualified=False, source_evidence=recipe)


def _scope(record):
    for field in record["evidence"]["Fields"]:
        if field["ConfigPath"].casefold() == "scope":
            # Native JSON emits unused scalar defaults and empty arrays. Nondefault
            # alternate values contradict the integer observation, even if the
            # first matching field would otherwise appear usable.
            _require(field.get("ValueFloat", 0) == 0
                     and field.get("ValueString", "") == ""
                     and field.get("ValueText", "") == ""
                     and not any(field.get(k) for k in ("IntValues", "FloatValues", "TextValues")),
                     "scope-contradiction")
            if (utility._captured(field) and field.get("Status") == "captured"
                    and field.get("ConfigTypeName") == "CT_INT"
                    and type(field.get("ConfigType")) is int and field["ConfigType"] == 0
                    and field.get("ReadAs") == "number"
                    and not field.get("UnresolvedReasons")
                    and type(field.get("ValueInt")) is int):
                return field["ValueInt"]
    return None


def _decision(status, reason, cohorts=()):
    return dict(status=status, reason=reason, cohorts=sorted(set(cohorts)))


def _native_weights(families, by_name, identities, budget):
    """Exact rational upper bounds, only for audited literal native mutations.

    Custom Do/actions/default yields remain unknown. Unknown edges participate
    in reachability and veto any proposed cycle that needs them.
    """
    weights = defaultdict(list)
    # These custom paths are outside literal RecipeBase Init analysis. Preserve
    # reachability without claiming effective yields, including HC action paths.
    unknown_routes = [('CamoNet', 'Netting'), ('CableReel', 'MetalWire')]
    for color in ('Green', 'Orange', 'Yellow'):
        unknown_routes += [('DrysackBag_'+color, 'WaterproofBag_'+color),
                           ('DrysackBag_'+color, 'Rope')]
    for before, after in unknown_routes:
        for source_id in by_name.get(before.casefold(), ()):
            for output_id in by_name.get(after.casefold(), ()):
                budget.take()
                weights[source_id, output_id].append(None)
    # Native same-class split/stack operations are not recipe declarations. A
    # captured splittable flag identifies their class-level self edge, but does
    # not prove their quantity bound or mixed object/stack unit conservation.
    for identity, record in identities.items():
        fields = {f['ConfigPath'].casefold():f for f in record['evidence']['Fields']}
        flag = fields.get('canbesplit', {})
        if (utility._captured(flag) and flag.get('Status') == 'captured'
                and type(flag.get('ValueInt')) is int and flag['ValueInt'] > 0):
            budget.take()
            weights[identity, identity].append(None)
    blockers = {"missing-or-ambiguous-init", "missing-or-ambiguous-cando", "custom-mutation-or-method",
                "native-custom-condition", "unsupported-recipe-parameter", "dynamic-output-class",
                "unresolved-or-ambiguous-input-class", "unresolved-or-ambiguous-output-class",
                "result-slot-out-of-range", "non-item-input-config-root", "non-item-output-config-root",
                "conditional-method", "conditional-or-modded-definition",
                "unsupported-init-statement", "inherited-or-ambiguous-semantics",
                "conditional-item-reference", "dynamic-or-unparsed-item-reference",
                "custom-ingredient-or-result-semantics",
                "invalid-recipe-parameter-value", "conditional-or-unresolved-registration"}
    for family in families:
        params = family["parameters"]
        safe = family["source_status"] == "registered" and not blockers.intersection(family["holds"])
        # Display-name expressions cannot change quantities. Repeated identical
        # literal writes (present in the native nailed-bat recipe) are harmless
        # for this bound; contradictory or conditional writes remain unknown.
        for field_name, entries in params.items():
            if field_name == "m_Name":
                continue
            for slot_id in {e["slot"] for e in entries}:
                selected = [e for e in entries if e["slot"] == slot_id]
                if not all(e["literal"] for e in selected) or len({str(e["value"]) for e in selected}) != 1:
                    safe = False
        for ref in family["inputs"]:
            slot = ref["slot"]
            destroy = _flag(_value(params, "m_IngredientDestroy", slot))
            delta = _value(params, "m_IngredientAddQuantity", slot)
            minimum = _value(params, "m_MinQuantityIngredient", slot)
            debit = None
            if destroy is True:
                debit = 1  # whole object units, not its config-default stack size
            elif destroy is False and type(delta) in (int, float) and delta < 0:
                if type(minimum) in (int, float) and minimum >= -delta:
                    debit = -delta
            node = "ingredient:" + ref["item"].casefold()
            for out in family["outputs"]:
                amount = out["quantity"]
                ratio = None
                if (safe and debit and amount["kind"] == "literal"
                        and _flag(_value(params, "m_IngredientUseSoftSkills", slot)) is not True
                        and _flag(_value(params, "m_ResultUseSoftSkills", out["index"])) is not True):
                    ratio = Fraction(str(amount["value"])) / Fraction(str(debit))
                for candidate in by_name.get(out["reference"]["item"].casefold(), ()):
                    budget.take()
                    candidate_ratio = ratio
                    if safe and debit and amount["kind"] == "config-default":
                        # One AddResult allocates one object. A non-stackable,
                        # non-quantity config object is exactly one material unit.
                        fields = {f["ConfigPath"].casefold(): f for f in identities[candidate]["evidence"]["Fields"]}
                        def observed_zero(key):
                            value = fields.get(key, {})
                            return (utility._captured(value) and value.get("Status") == "captured"
                                    and value.get("ReadAs") == "number"
                                    and type(value.get("ConfigType")) is int and value["ConfigType"] == 0
                                    and type(value.get("ValueInt")) is int and value["ValueInt"] == 0)
                        # The complete native exporter omits nonexistent paths;
                        # native ConfigGetInt returns zero for absent quantity
                        # limits. Require a captured non-stackable flag, never
                        # infer singleton status from just a missing field.
                        limits_zero = all(k not in fields or observed_zero(k)
                                          for k in ("varquantitymin", "varquantitymax"))
                        if observed_zero("canbesplit") and limits_zero:
                            candidate_ratio = Fraction(1) / Fraction(str(debit))
                    weights[node, candidate].append(candidate_ratio)
    return weights


def _proposals(records, identities, graph, add_edge, budget, weights):
    _require(type(records) in (list, tuple) and len(records) <= MAX_PROPOSALS, "proposals")
    result, names = [], set()
    basic = {"id", "inputs", "outputs", "rationale"}
    for record in records:
        _require(type(record) is dict and set(record) in
                 (basic, basic | {"tools", "yield_policy"}), "proposal-schema")
        extended = "yield_policy" in record
        identity, reason = record["id"], record["rationale"]
        _require(utility._identifier(identity) and identity.casefold() not in names, "proposal-id")
        names.add(identity.casefold())
        _require(type(reason) is str and 1 <= len(reason) <= 2048, "proposal-rationale")
        copied = dict(id=identity, rationale=reason)
        if extended:
            # Each listed input is an alternative whole source. Multiple outputs
            # are mandatory co-products, never choices or expected random yields.
            _require(record["yield_policy"] == "fixed-per-source", "proposal-yield-policy")
            copied["yield_policy"] = record["yield_policy"]
        for side in ("inputs", "outputs", "tools") if extended else ("inputs", "outputs"):
            values = record[side]
            _require(type(values) is list and 1 <= len(values) <= 64, "proposal-arity")
            copied[side], seen = [], set()
            for value in values:
                budget.take()
                keys = {"item", "quantity", "wear_hp"} if side == "tools" else {"item", "quantity"}
                _require(type(value) is dict and set(value) == keys, "proposal-operand")
                name, quantity = value["item"], value["quantity"]
                _require(type(name) is str and name in identities, "proposal-class")
                _require(name not in seen, "proposal-duplicate-operand")
                seen.add(name)
                _require(type(quantity) is int and 0 < quantity <= 1000000, "proposal-quantity")
                _require(_scope(identities[name]) == 2
                         and identities[name]["root"] in ("CfgVehicles", "CfgWeapons", "CfgMagazines"),
                         "proposal-public-item-definition-required")
                operand = dict(item=name, quantity=quantity)
                if side == "tools":
                    wear = value["wear_hp"]
                    _require(quantity == 1 and type(wear) in (int, float) and 0 < wear <= 1000000,
                             "proposal-tool-wear")
                    operand["wear_hp"] = wear
                copied[side].append(operand)
        if extended:
            _require(all(x["quantity"] == 1 for x in copied["inputs"]), "proposal-whole-source")
            _require(not {x["item"] for x in copied["tools"]}.intersection(
                x["item"] for x in copied["inputs"] + copied["outputs"]), "proposal-tool-material-overlap")
        result.append(copied)
    for record in result:
        for before in record["inputs"]:
            for after in record["outputs"]:
                add_edge(before["item"], after["item"])
                weights[before["item"], after["item"]].append(
                    Fraction(after["quantity"], before["quantity"]) if "yield_policy" in record else None)
    reverse = defaultdict(set)
    for start, ends in graph.items():
        for end in ends:
            budget.take()
            reverse[end].add(start)

    def cycle_check(start, target, initial):
        # Prune branches that cannot close this cycle; enumerate simple paths.
        # Every material node's product must be strictly <1, not merely the sum
        # of all materials. Exact fractions avoid rounding equality into loss.
        pending, reachable = [target], set()
        while pending:
            current = pending.pop()
            budget.take()
            if current not in reachable:
                reachable.add(current)
                pending.extend(reverse.get(current, ()))
        if start not in reachable:
            return False, True
        stack = [(start, initial, frozenset())]
        found = False
        while stack:
            current, product, visited = stack.pop()
            budget.take()
            # A split/stack self edge can be traversed before continuing a
            # closing path. Simple-path enumeration would otherwise omit it.
            if None in weights.get((current, current), ()):
                product = None
            if current == target:
                found = True
                if product is None or product >= 1:
                    return True, False
                continue
            visited = visited | {current}
            for successor in sorted(graph.get(current, ())):
                budget.take()
                if successor not in reachable or successor in visited:
                    continue
                candidates = weights.get((current, successor), [None])
                # Membership edges preserve units. Missing mutation bounds fail
                # closed; no custom action or Do is assigned a guessed yield.
                if successor.startswith("ingredient:"):
                    candidates = [Fraction(1)]
                bound = None if None in candidates else max(candidates)
                next_product = None if product is None or bound is None else product * bound
                stack.append((successor, next_product, visited))
        return found, True

    for record in result:
        cyclic, admissible = False, True
        for before in record["inputs"]:
            for after in record["outputs"]:
                found, lossy = cycle_check(after["item"], before["item"],
                    Fraction(after["quantity"], before["quantity"]) if "yield_policy" in record else None)
                cyclic |= found
                admissible &= lossy
        status = "cycle-veto" if not admissible else "lossy-cycle-admissible" if cyclic else "acyclic-declared-graph"
        record.update(cycle_status=status, quantity_gate_passed=admissible,
                      implementation_approved=False, gameplay_acceptance=False,
                      holds=["cycle-veto"] if not admissible else [
                          "custom-native-paths-not-semantically-evaluated", "runtime-conservation-required"])
    return sorted(result, key=lambda r: r["id"])


def build_review(rows, crafting_census, action_census, provenance, source_files, *, proposals=()):
    """Return the complete workbook, or raise; never a successful partial report."""
    audit = utility.build_audit(rows, crafting_census, action_census, provenance)
    craft, actions = audit["source_censuses"]["crafting"], audit["source_censuses"]["actions"]
    manifest = _files(craft, source_files)
    budget = utility._Budget()
    # Reconstruct the complete recipe catalog and registration facts, including
    # definitions omitted from a caller's census. Hashing bytes alone cannot
    # authenticate a supplied classification or the absence of a recipe row.
    all_definitions, registrations, parse_budget = [], [], [0]
    for path in sorted(manifest):
        definitions, calls, _ = source._parse(
            source_files[path].decode(manifest[path]["encoding"]), path, parse_budget)
        source._bounded(len(all_definitions) + len(definitions) <= source.MAX_CLASSES, path)
        all_definitions.extend(definitions)
        registrations.extend(calls)
    all_definitions.sort(key=lambda r: (r["source"], r["line"]))
    registrations.sort(key=lambda r: (r["source"], r["line"], r["disabled"], r["call"], r["class"] or ""))
    _require(source._reconcile(all_definitions, registrations) == craft["recipes"]
             and registrations == craft["registrations"], "recipe-source-facts")
    needed = sorted({d["source"] for r in craft["recipes"] for d in r.get("definitions", [])})
    parsed, text_tokens, token_budget = [], {}, [0]
    for path in needed:
        text = source_files[path].decode(manifest[path]["encoding"])
        tokens, _, _ = source._lex(text, path, token_budget)
        pairs = source._pairs(tokens, path)
        definitions, _ = source._classes(tokens, pairs, text, path)
        parsed.extend(definitions)
        text_tokens[path] = (tokens, pairs)
    families = [_family(r, parsed, text_tokens) for r in craft["recipes"]]
    families.sort(key=lambda r: r["id"])
    identities = {r["id"]: r for r in audit["classes"]}
    by_name, inherited, ancestors = defaultdict(list), defaultdict(list), {}
    for record in audit["classes"]:
        chain = record["evidence"].get("ConfigAncestors")
        _require(type(chain) is list and len(chain) <= 128
                 and all(utility._identifier(n) for n in chain), "config-ancestry")
        _require(len({n.casefold() for n in chain}) == len(chain), "config-ancestry-duplicates")
        parent = record["evidence"].get("ParentClass")
        _require(type(parent) is str or parent is None, "config-parent")
        _require(record["name"].casefold() not in {n.casefold() for n in chain},
                 "config-ancestry-self")
        _require(not parent and not chain or parent and chain
                 and parent.casefold() == chain[0].casefold(), "config-parent-ancestry")
        ancestors[record["id"]] = sorted({record["name"].casefold(), *(n.casefold() for n in chain)})
        by_name[record["name"].casefold()].append(record["id"])
        for name in ancestors[record["id"]]:
            budget.take()
            inherited[name].append(record["id"])
    for family in families:
        bindings = []
        for reference in family["inputs"]:
            key = reference["item"].casefold()
            exact, candidates = sorted(by_name.get(key, ())), sorted(inherited.get(key, ()))
            bindings.append(dict(reference=reference, exact_candidates=exact,
                                 config_ancestry_candidates=candidates, eligibility="NOT_EVALUATED"))
            if len(exact) != 1 or not candidates:
                family["holds"].append("unresolved-or-ambiguous-input-class")
            elif identities[exact[0]]["root"] not in ("CfgVehicles", "CfgWeapons", "CfgMagazines"):
                family["holds"].append("non-item-input-config-root")
        for output in family["outputs"]:
            exact = sorted(by_name.get(output["reference"]["item"].casefold(), ()))
            output["config_candidates"] = exact
            if len(exact) != 1 or _scope(identities[exact[0]]) != 2:
                family["holds"].append("unresolved-or-ambiguous-output-class")
            elif identities[exact[0]]["root"] not in ("CfgVehicles", "CfgWeapons", "CfgMagazines"):
                family["holds"].append("non-item-output-config-root")
        family["config_bindings"] = bindings
        family["holds"] = sorted(set(family["holds"]))
        family["source_template_supported"] = not family["holds"]
        if family["holds"]:
            family["ingredient_roles"] = {"0": "unknown", "1": "unknown"}
    cohorts, uses, graph, edge_count = {}, defaultdict(list), defaultdict(set), 0
    def add_edge(before, after):
        nonlocal edge_count
        budget.take()
        if after not in graph[before]:
            edge_count += 1
            _require(edge_count <= MAX_GRAPH_EDGES, "graph-edge-budget")
            graph[before].add(after)
    for family in families:
        outputs = [out["reference"]["item"].casefold() for out in family["outputs"]]
        for out in outputs:
            uses[out].append(dict(recipe=family["id"], role="output"))
        for reference in family["inputs"]:
            key = reference["item"].casefold()
            cohort = cohorts.setdefault(key, dict(
                exact_candidates=sorted(by_name.get(key, ())),
                config_candidates=sorted(inherited.get(key, ())), references=[], roles=[],
                name_resolution="ambiguous" if len(by_name.get(key, ())) > 1 else
                "single" if by_name.get(key) else "unresolved",
                eligibility="NOT_EVALUATED"))
            role = family["ingredient_roles"].get(str(reference["slot"]), "unknown")
            cohort["references"].append(dict(recipe=family["id"], reference=reference, role=role))
            cohort["roles"].append(role)
            if role != "tool":
                node = "ingredient:" + key
                for candidate in cohort["config_candidates"]:
                    add_edge(candidate, node)
                for out in outputs:
                    for candidate in by_name.get(out, ()):
                        add_edge(node, candidate)
    for cohort in cohorts.values():
        cohort["roles"] = sorted(set(cohort["roles"]))
    classes, totals = [], Counter()
    for record in audit["classes"]:
        identity, name = record["id"], record["name"].casefold()
        selected = [k for k in ancestors[identity] if k in cohorts]
        materials = [k for k in selected if "material" in cohorts[k]["roles"]]
        tools = [k for k in selected if "tool" in cohorts[k]["roles"]]
        scope, repair = _scope(record), record["repair"]
        nonpublic = scope is not None and scope != 2
        outside = record["root"] not in {"CfgVehicles", "CfgWeapons", "CfgMagazines"}
        source_names = audit["name_cohorts"][record["name_cohort"]]["script_classes"]
        dispositions = dict(
            native_use=_decision("retain" if outside else "candidate" if source_names else "unknown",
                "native-config-domain-retained" if outside else
                "source-name-correspondence-only" if source_names else "native-use-not-observed"),
            repair=_decision("candidate" if repair["entries"] or repair["kit_id"] else "unknown",
                "preserve-native-kit-target-observations" if repair["entries"] or repair["kit_id"]
                else "no-positive-repair-eligibility-established"),
            craft=_decision("candidate" if selected or uses[name] else "unknown",
                "declared-native-recipe-path" if selected or uses[name] else "no-recipe-reference-observed",
                selected),
            material=_decision("candidate" if materials else "unknown",
                "source-consumption-and-native-ancestry" if materials else "material-mapping-not-established",
                materials),
            tool=_decision("candidate" if tools else "unknown",
                "source-retained-worn-ingredient" if tools else "tool-role-not-established", tools),
            candidate=_decision("hold", "new-conversion-needs-material-yield-and-state-policy"),
            exclusion=_decision("exclude" if nonpublic or outside else "none",
                "non-public-definition-not-new-output" if nonpublic else
                "outside-item-conversion-domain" if outside else "no-blanket-item-exclusion"),
            unresolved=_decision("hold", "runtime-use-state-transfer-and-compatibility-not-evaluated"))
        decision = ("retain-definition-no-new-conversion" if nonpublic or outside else
                    "preserve-native-path-and-qualify" if selected or uses[name]
                    or repair["entries"] or repair["kit_id"] else "retain-native-hold-new-conversion")
        totals[decision] += 1
        classes.append(dict(id=identity, decision=decision, dispositions=dispositions,
                            source_name_cohort=record["name_cohort"], repair=repair,
                            native_output_references=uses[name], runtime_qualified=False))
    native_weights = _native_weights(families, by_name, identities, budget)
    for before, after in native_weights:
        add_edge(before, after)
    proposal_rows = _proposals(proposals, identities, graph, add_edge, budget, native_weights)
    result = dict(schema_version=1, kind="whole-content-utility-decisions",
        dimensions=list(DIMENSIONS), decision_enumeration_complete=True,
        gameplay_acceptance=False, runtime_qualified=False, provenance_authenticated=False,
        source_bytes_matched=True, source_manifest_sha256=craft["manifest_sha256"],
        evidence=audit, classes=classes, ingredient_cohorts=dict(sorted(cohorts.items())),
        recipe_families=families, actions=[
            dict(id=r["class"], decision="preserve-native-source-action",
                 reason="source-path-is-not-effective-registration-or-item-eligibility",
                 runtime_qualified=False, evidence=r) for r in sorted(actions["actions"], key=lambda r:r["class"])],
        proposals=proposal_rows, denominators=dict(audit["denominators"]),
        decision_counts=dict(sorted(totals.items())), graph_edges=edge_count,
        graph_policy="quantity-weighted-strict-loss-on-every-cycle-material; unknown-bounds-veto",
        resource_conservation="NOT_EVALUATED",
        limitations=["Complete means all supplied class/recipe/action decisions, not gameplay acceptance.",
                     "Existing native routes are reused, never duplicated or automatically enabled.",
                     "HC CamoNet/CableReel salvage, drysack decraft and captured splittable native split/stack paths are seeded as unknown bounds and veto feedback cycles.",
                     "The gate covers declared and explicitly seeded edges only; unmodeled native actions, missing split flags and cross-class stack compatibility remain unproved.",
                     "Custom conditions, Do methods, dynamic outputs and defaults retain explicit holds.",
                     "Config ancestry creates candidates, not effective runtime ingredient eligibility.",
                     "No general material recovery yields or new recipe authorizations are invented."])
    _require(len(classes) == audit["denominators"]["classes"]
             and len(families) == audit["denominators"]["recipes"]
             and len(result["actions"]) == audit["denominators"]["actions"], "decision-denominators")
    result["analysis_work"] = budget.work
    utility._digest(result, MAX_OUTPUT_BYTES, "output-bytes-budget")
    return result
