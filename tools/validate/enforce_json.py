"""Structural audit of scalar defaults on JSON-loaded Enforce DTOs (#177).

Follow JsonFileLoader/HCGroupJson roots, owned fields, arrays and inheritance.
Accept typed field comparisons/boolean gates as explicit zero handling. This is
a lexical guard check, not control-flow or native serializer acceptance proof.
"""
import re
from functools import lru_cache

from tools.validate import enforce_source as es

RULE = 'HC-S005'
DESCRIPTION = 'JSON-loaded scalar has a nonzero initializer but no explicit zero/default guard'
LOAD = re.compile(r'\b(?:JsonFileLoader|HCGroupJson|HCInteriorJson|HCSearchJson|HCV2ThreatStore|HCEncounterStore)\s*<([^;{}]+?)>\s*\.\s*'
                  r'(?:LoadData|LoadFile|JsonLoadData|JsonLoadFile|Load)\s*\(')


def loaded_classes(project):
    pending = []
    for source in project.sources:
        for match in LOAD.finditer(source.code):
            pending.extend(types_in(match[1]))
    loaded = set()
    while pending:
        name = pending.pop()
        if name in loaded or name not in project.links:
            continue
        loaded.add(name)
        for definition in project.links[name]:
            pending.append(definition.base)
            for field in definition.fields:
                if not field.modifiers & {'static', 'const'}:
                    pending.extend(types_in(field.type))
    return loaded


def types_in(text):
    # Source's compact type spelling is array<refHCRow>, not array<ref HCRow>.
    return [token[3:] if token.startswith('ref') else token
            for token in re.findall(r'\b\w+\b', text)]


def nonzero(field):
    if field.type not in {'int', 'float', 'bool'} or field.modifiers & {'static', 'const'}:
        return False
    value = field.initializer.strip()
    if not value or value == 'false':
        return False
    try:
        return float(value) != 0
    except ValueError:
        return True


def explicit_check(body, access, kind, sentinel=False):
    pattern = access + r'\s*(==|!=|<=|>=|<|>)\s*([\w.\-]+)'
    check = None
    for candidate in re.finditer(pattern, body):
        # A negative-only refusal / nonnegative acceptance cannot detect an
        # absent -1 sentinel: native zero passes it. Require a zero-aware path.
        if candidate[2] in {'0', '0.0'} and candidate[1] in {'<', '>='}:
            continue
        try:
            threshold = float(candidate[2])
        except ValueError:
            if sentinel:
                continue
        else:
            if candidate[1] in {'>', '<='} and threshold > 0:
                continue
            if candidate[1] in {'<', '>='} and threshold < 0:
                continue
        check = candidate
        break
    if not check:
        for candidate in re.finditer(r'([\w.\-]+)\s*(==|!=|<=|>=|<|>)\s*' + access, body):
            if candidate[1] in {'0', '0.0'} and candidate[2] in {'>', '<='}:
                continue
            try:
                threshold = float(candidate[1])
            except ValueError:
                if sentinel:
                    continue
            else:
                if candidate[2] in {'<', '>='} and threshold > 0:
                    continue
                if candidate[2] in {'>', '<='} and threshold < 0:
                    continue
            check = candidate
            break
    if not check and kind == 'bool':
        check = re.search(r'(?:!\s*|\breturn\s+|&&\s*|\|\|\s*)' + access + r'\s*(?=[);&|])', body)
        if not check:
            check = re.search(r'\bif\s*\(\s*' + access + r'\s*\)', body)
    return check


def guards(project):
    """(declaring type, field) -> (source, offset) of a typed explicit check."""
    result = {}
    loaded = loaded_classes(project)
    fields = {}
    for name in project.links:
        visible = {}
        for ancestor in reversed(project.lineage(name)):
            for definition in project.links.get(ancestor, ()):
                visible.update({field.name: (ancestor, field) for field in definition.fields})
        fields[name] = visible

    @lru_cache(maxsize=None)
    def relative_paths(kind, depth=0):
        return tuple(paths(kind, '', depth))

    def paths(kind, prefix, depth=0):
        if depth > 5:
            return
        for field_name, (owner, field) in fields.get(kind, {}).items():
            path = prefix + field_name
            if field.type in {'int', 'float', 'bool'}:
                if owner in loaded and nonzero(field):
                    yield path, owner, field
            elif field.type in loaded:
                for suffix, declaring, item in relative_paths(field.type, depth + 1):
                    yield path + '.' + suffix, declaring, item
            elif field.type.startswith(('array<', 'set<')):
                for element in types_in(field.type):
                    if element in loaded:
                        for suffix, declaring, item in relative_paths(element, depth + 1):
                            yield path + '.*.' + suffix, declaring, item

    # A named range/default helper handles zero at the scalar parameter. Trace
    # exact argument positions rather than exempting any call mentioning a field.
    helpers = {}
    sentinel_helpers = {}
    method_groups = dict(project.methods)
    for methods in project.methods.values():
        for method in methods:
            if method.owner:
                method_groups.setdefault(method.owner.name + '.' + method.name, []).append(method)
    for name, methods in method_groups.items():
        checked = []
        sentinel_checked = []
        for method in methods:
            checked.append({index for index, (kind, param, _) in enumerate(method.parameters())
                            if kind in {'int', 'float', 'bool'} and explicit_check(
                                method.owner.source.body(method), r'(?<![\w.])' + re.escape(param) + r'\b', kind)})
            sentinel_checked.append({index for index, (kind, param, _) in enumerate(method.parameters())
                            if kind in {'int', 'float', 'bool'} and explicit_check(
                                method.owner.source.body(method), r'(?<![\w.])' + re.escape(param) + r'\b', kind, True)})
        if checked:
            helpers[name] = set.intersection(*checked)
            sentinel_helpers[name] = set.intersection(*sentinel_checked)

    for source in project.sources:
        for method in source.methods:
            body = source.body(method)
            receivers = {}
            candidates = []
            if method.owner:
                candidates.extend(paths(method.owner.name, ''))
                receivers['this'] = method.owner.name
                receivers.update({name: item.type for name, (_, item) in fields[method.owner.name].items()})
            receivers.update({name: kind for kind, name, _ in method.parameters()})
            # Includes typed locals and foreach element declarations.
            receivers.update({m[2]: m[1] for m in re.finditer(
                r'\b(\w+)\s+(\w+)\s*(?=[=;:,])', body) if m[1] in fields})
            for receiver, kind in receivers.items():
                candidates.extend(paths(kind, receiver + '.'))
            helper_args = {}
            sentinel_args = {}
            raw_body = source.text[method.body_start:method.body_end + 1]
            present = set(re.findall(r'HCJsonFields\.(?:Has|Every|Check)\([^,]+,\s*"(\w+)"', raw_body))
            # Presence-only helpers keep the raw-text scan in one bounded IO
            # seam. Resolve the exact class-qualified helper, not a name match
            # across unrelated stores.
            for helper in re.finditer(r'(?<![\w.])((?:\w+\.)?HCFieldsPresent)\s*\(', body):
                name = helper[1]
                if '.' not in name and method.owner:
                    name = method.owner.name + '.' + name
                for definition in method_groups.get(name, ()):
                    raw = definition.owner.source.text[definition.body_start:definition.body_end + 1]
                    present.update(re.findall(r'HCJsonFields\.(?:Has|Every|Check)\([^,]+,\s*"(\w+)"', raw))
            for call in re.finditer(r'\b((?:\w+\s*\.\s*)?\w+)\s*\(', body):
                call_name = re.sub(r'\s+', '', call[1])
                if not helpers.get(call_name):
                    continue
                opening = body.find('(', call.start())
                end = es.matching_paren(body, opening)
                args = es.split_top(body[opening + 1:end], ',')
                for index in helpers[call_name]:
                    if index < len(args):
                        helper_args[re.sub(r'\s+', '', args[index])] = call.start()
                        if index in sentinel_helpers[call_name]:
                            sentinel_args[re.sub(r'\s+', '', args[index])] = call.start()
            for path, owner, field in candidates:
                if not nonzero(field):
                    continue
                if field.name in present:
                    result.setdefault((owner, field.name), (source, method.body_start))
                    continue
                if field.name not in body:
                    continue
                access = r'(?<![\w.])' + re.escape(path).replace(r'\.', r'\s*\.\s*') + r'\b'
                # Positive/negative version equality and range checks both name
                # the field explicitly; boolean off gates include !field/return.
                sentinel = field.initializer.startswith('-')
                check = explicit_check(body, access, field.type, sentinel)
                if check:
                    result.setdefault((owner, field.name), (source, method.body_start + check.start()))
                elif path in (sentinel_args if sentinel else helper_args):
                    result.setdefault((owner, field.name), (source, method.body_start + helper_args[path]))
    return result


def rule_json_defaults(project, source):
    # Cache once per project, shared by every source/rule invocation.
    if not hasattr(project, 'json_loaded'):
        project.json_loaded = loaded_classes(project)
        project.json_guards = guards(project)
    from tools.validate.enforce_lint import _finding
    for definition in source.classes:
        if definition.name not in project.json_loaded:
            continue
        for field in definition.fields:
            if nonzero(field) and (definition.name, field.name) not in project.json_guards:
                symbol = definition.name + '.' + field.name
                yield _finding(RULE, source, field.offset, symbol,
                               DESCRIPTION + '; missing ' + field.name + ' loads as zero',
                               key=symbol + ' relies on JSON initializer')


# Reviewed legacy exceptions use the same identity/count/stale mechanism as the
# existing JSON baseline. They live beside this new rule to keep this worker's
# edits within its tools/validate module scope. No unsafe store is excepted.
LEGACY_BASELINE = [
    dict(rule=RULE, path='mods/HollowCountry/scripts/3_Game/Groups/HCGroupData.c',
         symbol='HCGroupRequest.Color', key='HCGroupRequest.Color relies on JSON initializer', count=1,
         review='2026-11-19 #177: HCGroupClient.Send:428-437 JSON-clones only its own complete MakeData payload; Color is serialized, never an external/legacy JSON request.'),
    dict(rule=RULE, path='mods/HollowCountry/scripts/4_World/Infected/HCInfectedState.c',
         symbol='HCInfectedSnapshot.Reserved', key='HCInfectedSnapshot.Reserved relies on JSON initializer', count=1,
         review='2026-11-19 #177: HCInfectedStore.Validate:569-574 requires exact sum of unreleased group reservations. Missing zero succeeds only when the real sum is zero; cannot replenish/admit reservations.'),
    dict(rule=RULE, path='mods/HollowCountry/scripts/4_World/Loot/HCSearchRefresh.c',
         symbol='HCSearchRetirementState.RecentCount', key='HCSearchRetirementState.RecentCount relies on JSON initializer', count=1,
         review='2026-11-19 #177: HCSearchRetirementStore.Open:133 requires RecentCount == Recent.Count(); absent zero admits only an empty recent list; fixed-size Archive is still required at :134. No depletion/history is removed.'),
]
