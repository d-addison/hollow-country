"""HC-E058: bounded intraprocedural ownership/use analysis, not an engine model.

Only resolved owning ref fields/arrays/maps and known non-Managed classes are checked.
A structured CFG keeps opposite if arms separate and models loop exits. Unknown
factory results and unknown aliases are deliberately left alone. Small borrowed
accessors (returning a container element/foreach item) are resolved by body, never
by method name. No general call side-effect or interprocedural lifetime inference.
"""
from dataclasses import dataclass
import re

from tools.validate import enforce_source as es

RULE = 'HC-E058'
DESCRIPTION = 'raw non-Managed local used after release by an owning ref field/container'
VALUE = r'[A-Za-z_]\w*(?:\s*\.\s*[A-Za-z_]\w*)*'
ACCESS = re.compile(rf'^({VALUE})(?:\s*\[(.*)\]|\s*\.\s*Get\s*\((.*)\))$', re.S)
MUTATE = re.compile(rf'({VALUE})\s*\.\s*(Remove\w*|Clear|Set|Resize)\s*\(')
STORE = re.compile(rf'^(?:(?:ref|autoptr)\s+)?(?:\w+(?:<[^;]+>)?\s+)?({VALUE})(?:\s*\[([^]]+)\])?\s*=(?!=)\s*(.*)$', re.S)


def compact(text):
    return re.sub(r'\s+', '', text).removeprefix('this.')


def predicate(text):
    comparison = re.fullmatch(r'\s*(\w+)\s*(!=|==)\s*(\w+)\s*', text)
    if comparison:
        return '!='.join(sorted((comparison[1], comparison[3]))), comparison[2] == '!='
    atom = re.fullmatch(r'\s*(!?)\s*(\w+)\s*', text)
    if atom:
        return atom[2], not bool(atom[1])
    return None


def held_on_path(owners, facts):
    facts = dict(facts)
    return any(not owner.startswith('?') or facts.get(owner.split(':', 1)[-1]) is True for owner in owners)


def unmanaged(project, kind, seen=None):
    """Use authored and installed native ancestry; incomplete ancestry is unknown."""
    kind = project.resolve_typedef(kind)
    if kind in es.PRIMITIVES or project.is_enum(kind):
        return False
    # Script containers themselves are non-Managed, regardless of element type.
    if re.fullmatch(r'(?:array|map|set)<.+>', kind):
        return True
    if kind in {'Managed', 'Object', 'PlayerIdentity', 'PlayerIdentityBase', 'Widget'}:
        return False
    seen = (seen or set()) | {kind}
    definitions = [d for d in project.links.get(kind, ()) if not d.modded]
    native = [d for d in project.symbols.get(kind, ()) if not d['modded']]
    if not definitions and not native:
        return False
    parents = {d.base for d in definitions} | {d['parent'] for d in native}
    return all(not p or (p not in seen and unmanaged(project, p, seen)) for p in parents)


def owning(project, resolver, method, expression, offset):
    kind = resolver.receiver(expression, method, offset)
    return bool(re.fullmatch(r'(?:array<ref\w+>|map<[^,<>]+,ref\w+>)', kind))


@dataclass
class Node:
    text: str
    offset: int
    edges: list
    branch: bool = False


class Flow:
    """Parse statements into a CFG; switch bodies are skipped (precision first)."""
    def __init__(self, source, method):
        self.code = source.code
        self.nodes = []
        self.stop = method.body_end
        self.entry, _ = self.statement(method.body_start, None, None, None)

    def node(self, text, offset, edges=(), branch=False):
        self.nodes.append(Node(text, offset, list(edges), branch))
        return len(self.nodes) - 1

    def space(self, pos):
        while pos < self.stop and self.code[pos].isspace():
            pos += 1
        return pos

    def extent(self, pos):
        pos = self.space(pos)
        if self.code[pos] == '{':
            return es.matching_brace(self.code, pos) + 1
        word = re.match(r'\w+', self.code[pos:])
        if word and word[0] in {'if', 'for', 'foreach', 'while', 'switch'}:
            close = es.matching_paren(self.code, self.code.find('(', pos))
            end = self.extent(close + 1)
            after = self.space(end)
            if word[0] == 'if' and re.match(r'else\b', self.code[after:]):
                end = self.extent(after + 4)
            return end
        depth = 0
        for end in range(pos, self.stop):
            ch = self.code[end]
            depth += (ch == '(') - (ch == ')')
            if ch in ';}' and depth == 0:
                return end + 1
        return self.stop

    def statement(self, pos, following, breaking, continuing):
        pos = self.space(pos)
        if pos >= self.stop:
            return following, pos
        if self.code[pos] == '{':
            end = es.matching_brace(self.code, pos)
            # Collect statement extents, then wire the sequence backwards.
            starts, cursor = [], pos + 1
            while self.space(cursor) < end:
                starts.append(self.space(cursor))
                cursor = self.extent(cursor)
            entry = following
            for start in reversed(starts):
                entry, _ = self.statement(start, entry, breaking, continuing)
            return entry, end + 1
        word = re.match(r'\w+', self.code[pos:])
        word = word[0] if word else ''
        if word in {'if', 'for', 'foreach', 'while', 'switch'}:
            opening = self.code.find('(', pos)
            close = es.matching_paren(self.code, opening)
            condition = self.code[opening + 1:close]
            if word == 'switch':
                start = self.space(close + 1)
                end = es.matching_brace(self.code, start) if self.code[start] == '{' else close
                return following, end + 1
            branch = self.node(condition, opening + 1, branch=True)
            loop = word != 'if'
            repeat = branch
            if word == 'foreach':
                repeat = self.node('foreach ' + condition, opening + 1, [(branch, None)])
                self.nodes[branch].text = ''
            yes, end = self.statement(close + 1, repeat if loop else following,
                                      following if loop else breaking,
                                      repeat if loop else continuing)
            no = following
            after = self.space(end)
            if not loop and re.match(r'else\b', self.code[after:]):
                no, end = self.statement(after + 4, following, breaking, continuing)
            self.nodes[branch].edges = [(yes, True), (no, False)]
            if word == 'foreach':
                return repeat, end
            return branch, end
        # Semicolons inside call arguments are not statement separators.
        end, depth = pos, 0
        while end < self.stop:
            ch = self.code[end]
            depth += (ch == '(') - (ch == ')')
            if ch == ';' and depth == 0:
                break
            if ch == '}' and depth == 0:
                break
            end += 1
        text = self.code[pos:end]
        target = following
        if word == 'return':
            target = None
        elif word == 'break':
            target = breaking
        elif word == 'continue':
            target = continuing
        return self.node(text, pos, [(target, None)]), end + 1


def borrow(expression):
    expression = expression.strip()
    match = ACCESS.fullmatch(expression)
    if match:
        if match[3] is not None and es.matching_paren(expression, expression.find('(')) != len(expression) - 1:
            return None
        return compact(match[1]), compact(match[2] if match[2] is not None else match[3])
    return None


def accessor(resolver, expression, method, offset):
    call = resolver.call(expression, method, offset)
    if not call or not call[0]:
        return None
    origins = set()
    for candidate in call[0]:
        source = resolver.sources[id(candidate)]
        body = source.body(candidate)
        returns = re.findall(r'\breturn\s+([^;]+);', body)
        for value in returns:
            if value.strip() == 'null':
                continue
            origin = borrow(value)
            if not origin:
                loop = re.search(rf'foreach\s*\(\s*\w+\s+{re.escape(value.strip())}\s*:\s*({VALUE})\s*\)', body)
                if loop:
                    origin = compact(loop[1]), '*'
            if not origin:
                return None
            # Only same-instance accessors; translating arbitrary receiver paths
            # would require alias analysis beyond this rule.
            if call[1] != (method.owner.name if method.owner else ''):
                return None
            origins.add(origin)
    return next(iter(origins)) if len(origins) == 1 else None


def strong_field(project, resolver, method, expression, offset):
    if not re.fullmatch(VALUE, expression.strip()):
        return False
    parts = compact(expression).rsplit('.', 1)
    kind = resolver.receiver(parts[0], method, offset) if len(parts) == 2 else method.owner.name if method.owner else ''
    name = parts[-1]
    return any(field.name == name and field.strong
               for ancestor in project.lineage(kind)
               for definition in project.links.get(ancestor, ()) for field in definition.fields)


def retained_getter(project, resolver, method, expression, offset):
    call = resolver.call(expression, method, offset)
    if not call or not call[0]:
        return False
    for getter in call[0]:
        source = resolver.sources[id(getter)]
        returns = [value for value in re.findall(r'\breturn\s+([^;]+);', source.body(getter)) if value.strip() != 'null']
        if not returns or any(not strong_field(project, resolver, getter, value, getter.body_end)
                              or not owning(project, resolver, getter, value, getter.body_end)
                              for value in returns):
            return False
    return True


def retained_collections(project, resolver, source):
    """Secondary field lists filled ONLY from a retained owner's collection.

    Recognise registry-style admission: typed collection = owner.GetRows();
    foreach (T row : collection) secondary.Insert(row). Require every insertion
    to have that provenance. This does not bless arbitrary same-type containers.
    """
    result = set()
    for definition in source.classes:
        inserts = {}
        for method in definition.methods:
            body = source.body(method)
            for hit in re.finditer(rf'({VALUE})\.Insert\(([^;]*?)\)', body):
                destination, item = compact(hit[1]), hit[2].strip()
                if not re.fullmatch(r'\w+', item):
                    inserts.setdefault((definition.name, destination), []).append(False)
                    continue
                safe = False
                origins = []
                for loop in re.finditer(rf'foreach\s*\(\s*\w+\s+{item}\s*:\s*(\w+)\s*\)\s*\{{', body):
                    start = method.body_start + loop.end() - 1
                    if start < method.body_start + hit.start() < es.matching_brace(source.code, start):
                        origins.append(loop[1])
                for assignment in re.finditer(rf'\b{item}\s*=\s*(\w+)\s*\[[^]]+\]', body[:hit.start()]):
                    if assignment[1] != destination:
                        origins.append(assignment[1])
                for origin in origins:
                    init = re.search(rf'\b{origin}\s*=\s*([^;]+);', body[:hit.start()])
                    if init and retained_getter(project, resolver, method, init[1], method.body_start + init.start()):
                        safe = True
                inserts.setdefault((definition.name, destination), []).append(safe)
        result.update(key for key, evidence in inserts.items() if all(evidence))
    return result


def findings(api, project, source):
    resolver = api._ownership(project)
    retained = retained_collections(project, resolver, source)
    for method in api._all_methods(source):
        declarations = source.local_declarations(method)
        types = {name: kind for name, kind, _, _ in declarations}
        types.update({name: kind for kind, name, _ in method.parameters()})
        strong = set()
        for name, _, offset, _ in declarations:
            prefix = source.code[max(method.body_start, offset - 16):offset]
            if re.search(r'\b(?:ref|autoptr)\s*$', prefix):
                strong.add(name)
        candidates = {name for name, kind in types.items() if name not in strong and unmanaged(project, kind)}
        if not candidates:
            continue
        flow = Flow(source, method)
        for name in sorted(candidates):
            seen, pending = set(), [(flow.entry, None, frozenset(), frozenset())]
            emitted = set()
            while pending:
                index, origin, owners, facts = pending.pop()
                state = index, origin, owners, facts
                if index is None or state in seen:
                    continue
                seen.add(state)
                node = flow.nodes[index]
                text = node.text
                store = STORE.fullmatch(text.strip())
                dead = origin is not None and origin[2]
                # Check reads before assignment kills (row = row.Next is a read).
                assignment = re.match(rf'(?:(?:ref|autoptr)\s+)?(?:\w+(?:<[^;]+>)?\s+)?{name}\s*=(?!=)\s*(.*)', text, re.S)
                read_text = assignment[1] if assignment else text
                if node.branch:
                    terms = es.split_top(read_text, '&&')
                    kept = []
                    for term in terms:
                        kept.append(term)
                        atom = re.fullmatch(r'\s*(!?)\s*(\w+)\s*', term)
                        if atom and atom[2] in dict(facts) and dict(facts)[atom[2]] == bool(atom[1]):
                            break
                    read_text = '&&'.join(kept)
                # Container identity operations only compare a pointer value;
                # passing a released pointer to gameplay code can dereference it.
                for identity_call in list(re.finditer(rf'({VALUE})\s*\.\s*(?:Remove\w*|Find|Contains)\s*\(\s*{name}\s*\)', read_text)):
                    kind = resolver.receiver(identity_call[1], method, node.offset)
                    if re.match(r'(?:array|map|set)<', kind):
                        read_text = read_text.replace(identity_call[0], ' ' * len(identity_call[0]))
                if dead and not held_on_path(owners, facts) and (re.search(rf'\b{name}\s*[.\[]', read_text) or
                             re.search(rf'(?:\(|,)\s*{name}\s*(?=[,)])', read_text) or
                             (store and re.search(rf'\b{name}\b', store[3])) or
                             re.match(rf'return\s+{name}\b', read_text)):
                    if node.offset not in emitted:
                        emitted.add(node.offset)
                        yield api._finding(RULE, source, node.offset, api._symbol(method),
                                           f'{name} used after {origin[0]} released its owning ref; retain a ref local or read before removal',
                                           key=f'{api._symbol(method)}:{name}:{source.line_text(node.offset)}')
                    # One diagnostic per path to avoid flooding every later read.
                    continue
                if assignment:
                    found = borrow(assignment[1]) or accessor(resolver, assignment[1], method, node.offset)
                    origin = (*found, False) if found and owning(project, resolver, method, found[0], node.offset) else None
                    if not origin and strong_field(project, resolver, method, assignment[1], node.offset):
                        origin = compact(assignment[1]), '@field', False
                    owners = frozenset({compact(assignment[1])}) if strong_field(project, resolver, method, assignment[1], node.offset) else frozenset()
                loop = re.match(rf'foreach\s+\w+\s+{name}\s*:\s*({VALUE})\s*$', text)
                if loop and owning(project, resolver, method, loop[1], node.offset):
                    origin = compact(loop[1]), '*', False
                # Find(key, outLocal) establishes a borrow on the successful path.
                for find in re.finditer(rf'({VALUE})\s*\.\s*Find\s*\(([^;]*?),\s*{name}\s*\)', text):
                    if owning(project, resolver, method, find[1], node.offset):
                        origin = compact(find[1]), compact(find[2]), False
                # Array Find(parameter) establishes which owner the raw parameter
                # belongs to, including later stores through the returned slot.
                for find in re.finditer(rf'({VALUE})\s*\.\s*Find\s*\(\s*{name}\s*\)', text):
                    if origin is None and owning(project, resolver, method, find[1], node.offset):
                        origin = compact(find[1]), '*', False
                releases = []
                for mutation in MUTATE.finditer(text):
                    opening = mutation.end() - 1
                    close = es.matching_paren(text, opening)
                    args = [compact(a) for a in es.split_top(text[opening + 1:close], ',')]
                    if mutation[2] != 'Resize' or args == ['0']:
                        releases.append((compact(mutation[1]), mutation[2], args))
                if store:
                    destination = compact(store[1])
                    if store[2] is not None:
                        releases.append((destination, 'Set', [compact(store[2]), compact(store[3])]))
                    else:
                        releases.append((destination, 'Replace', [compact(store[3])]))
                for container, operation, args in releases:
                    if operation != 'Replace' and not owning(project, resolver, method, container, node.offset):
                        continue
                    # Removal of a raw parameter by value / Find(parameter) is
                    # also direct evidence of its owning container.
                    by_value = args and (operation == 'RemoveItem' and args[0] == name or
                                         args[0] == f'{container}.Find({name})')
                    if origin is None and by_value:
                        origin = container, '*', False
                    if origin and origin[0] == container:
                        owner_key = (method.owner.name if method.owner else '', container)
                        if owner_key in retained:
                            continue
                        if origin[1] == '@field' and operation != 'Replace':
                            continue
                        if operation == 'Replace' and args == [name]:
                            continue
                        # A different proven literal slot cannot release this value.
                        different = args and origin[1].isdigit() and args[0].isdigit() and origin[1] != args[0]
                        if operation == 'Set' and len(args) > 1 and args[1] == name:
                            continue
                        if not different or operation in {'Clear', 'Resize', 'Replace'}:
                            origin = origin[0], origin[1], True
                # Strong locals, strong fields, and another owning slot retain
                # the borrowed value. Invalidation of these owners is tracked.
                held = set(owners)
                for owner in list(held):
                    if owner.startswith('?'):
                        container = owner[1:].split(':', 1)[0]
                        if any(receiver == container for receiver, _, _ in releases):
                            held.discard(owner)
                        continue
                    slot = re.fullmatch(r'(.+)\[([^]]+)\]', owner)
                    if slot:
                        for receiver, operation, args in releases:
                            if receiver != slot[1]:
                                continue
                            if operation == 'Set' and args[1] == name:
                                continue
                            arg = args[0] if args else ''
                            if operation not in {'Clear', 'Resize', 'Replace'} and arg.isdigit() and slot[2].isdigit() and arg != slot[2]:
                                continue
                            held.discard(owner)
                            if operation not in {'Clear', 'Resize', 'Replace'} and arg != slot[2]:
                                condition = predicate(slot[2] + '!=' + arg)
                                if condition:
                                    held.add('?' + slot[1] + ':' + condition[0])
                    elif any(receiver == owner and (operation == 'Replace' or origin and origin[1] != '@field')
                             for receiver, operation, _ in releases):
                        held.discard(owner)
                if not origin or not origin[2] or held_on_path(owners, facts):
                    if store and store[2] is None and compact(store[3]) == name:
                        owner = compact(store[1])
                        if owner in strong or strong_field(project, resolver, method, owner, node.offset):
                            held.add(owner)
                    for insert in re.finditer(rf'({VALUE})\s*\.\s*(Insert|InsertAt|Set)\s*\(([^;]*)\)', text):
                        args = [compact(a) for a in es.split_top(insert[3], ',')]
                        value = args[0] if args and insert[2] == 'InsertAt' else args[-1] if args else ''
                        if value == name and owning(project, resolver, method, insert[1], node.offset):
                            container = compact(insert[1])
                            slot_key = args[1] if insert[2] == 'InsertAt' and len(args) > 1 else args[0] if len(args) > 1 else '*'
                            held.add(container + '[' + slot_key + ']')
                    slot = re.match(rf'({VALUE})\s*\[[^]]+\]\s*=\s*{name}\s*$', text)
                    if slot and owning(project, resolver, method, slot[1], node.offset):
                        held.add(compact(slot[0]).split('=')[0])
                owners = frozenset(held)
                # Track stable boolean guards and slot equality; assignments
                # invalidate facts about the changed variable.
                for target, truth in node.edges:
                    next_facts = dict(facts)
                    if node.branch:
                        terms = es.split_top(text, '&&') if truth else [text]
                        valid = True
                        for term in terms:
                            pred = predicate(term)
                            if pred and ('!=' in pred[0] or types.get(pred[0]) == 'bool'):
                                key, positive = pred
                                value = bool(truth) == positive
                                if key in next_facts and next_facts[key] != value:
                                    valid = False
                                next_facts[key] = value
                        if not valid:
                            continue
                    else:
                        for fact in list(next_facts):
                            variables = fact.split('!=')
                            if any(re.search(rf'\b{re.escape(variable)}\s*(?:=(?!=)|[+*-]=|\+\+|--)', text) for variable in variables):
                                del next_facts[fact]
                    pending.append((target, origin, owners, frozenset(next_facts.items())))
