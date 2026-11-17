"""Bounded T0 action/item-use census of every supplied .c/.C source file.

Shares crafting_audit's source traversal, lexer, class/method parser and manifest
contract. No scripts, preprocessors, conditions, dispatch or game calls execute.
Bindings are lexical evidence, not effective actions or inventory eligibility.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import re

from . import crafting_audit as crafting

MAX_CLASSES = 32768
MAX_METHODS = 131072
MAX_BINDINGS = 131072
MAX_CONTROLS = 262144
MAX_ALIASES = 32768
MAX_ANCESTRY = 128
MAX_ANALYSIS_WORK = 16_000_000
MAX_EXPRESSION = 512
MAX_OUTPUT_BYTES = 128 * 1024 * 1024
CALLS = {'AddAction', 'RemoveAction', 'SetActions'}
CALLBACKS = {
    **dict.fromkeys(('CanBeRepairedByCrafting','CanRepair','Repair'), 'repair'),
    **dict.fromkeys(('OnConsume','Consume'), 'consume'),
    **dict.fromkeys(('OnFoodStageChange','CanBeCooked','CanBeCookedOnStick',
                     'RefreshAudioVisualsOnClient','ProcessItemToCook',
                     'CookWithEquipment','CookOnStick'), 'cooking'),
    **dict.fromkeys(('EEItemAttached','EEItemDetached','CanReceiveAttachment',
                     'CanReleaseAttachment','OnWasAttached','OnWasDetached'), 'attachment'),
}
LIMITATIONS = [
    'Source census only; no native execution, registry membership or runtime acceptance.',
    'All nested .c/.C files are scanned; external includes and other suffixes are not parsed.',
    'Class, typedef and callback names are observations; config identities are not linked by name heuristics.',
    'Preprocessor branches, runtime controls, overload resolution, invocation/order and dispatch are not evaluated.',
    'Ancestor registration sources are declared candidates, not an effective inherited action list.',
    'Qualified receivers and typename shadows remain unresolved; comment calls never enable actions.',
    'Typename shadows are conservative across class/ancestors or all global scopes in one file, not a scope/type checker.',
    'Callback categories are name observations on methods/global functions, not dispatch evidence; other declarations are retained.',
    'Function/method signatures use the shared lexical grammar, not compilation or full language/type validation.',
    'Conditions/expression excerpts may be truncated with hashes; source bodies are not emitted.',
    'Hashes pin supplied paths/bytes, not extraction authenticity; input must remain quiescent.',
]


def _bound(ok, source='.', line=0):
    if not ok:
        raise crafting.CensusError('resource_limit', source, line)


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _excerpt(parts, text):
    raw = text[parts[0].start:parts[-1].end] if parts else ''
    return dict(expression=raw[:MAX_EXPRESSION], expression_sha256=_sha(raw.encode('utf-8')),
                expression_truncated=len(raw)>MAX_EXPRESSION)


def _public(record):
    return {key:value for key,value in record.items() if not key.startswith('_')}


def _take(budget, key, maximum, source, line, amount=1):
    budget[key] += amount
    _bound(budget[key] <= maximum, source, line)


def _method(owner, name, source, line, index, *, declaration_only=False,
            digest=None, conditions=(), stop=0):
    return dict(id=source+':method:'+str(index), owner_class=owner['class'] if owner else None,
                owner_definition=owner['_id'] if owner else None, name=name,
                source=source, line=line, conditions=list(conditions),
                declaration_only=declaration_only, sha256=digest,
                runtime_control_flow=[], _start=index, _end=stop)


def _call(tokens, index, pairs, text, source, owner, method, *, disabled=False):
    token = tokens[index]
    args = crafting._arguments(tokens, index+1, pairs)
    argument = tokens[index+2:pairs[index+1]]
    candidate = argument[0].text if len(argument)==1 and argument[0].kind=='identifier' else None
    receiver = 'implicit'
    if index and tokens[index-1].text=='.':
        receiver = tokens[index-2].text if index>=2 else ''
        receiver = receiver if receiver in ('this','super') else 'qualified_unresolved'
    registry = token.text=='Insert'
    owner_name = owner['class'] if owner else None
    result = dict(call=token.text, kind='constructor_registry_candidate' if registry else 'item_action_call',
                  source=source, line=token.line, enclosing_class=owner_name,
                  owner_class=owner_name if receiver!='qualified_unresolved' and not registry else None,
                  method_id=method['id'] if method else None, receiver=receiver,
                  candidate=candidate if token.text!='SetActions' else None,
                  action_class=None, disabled=disabled, conditions=list(token.conditions),
                  runtime_conditions='NOT_EVALUATED', unresolved=[], **_excerpt(argument,text))
    if receiver=='qualified_unresolved': result['unresolved'].append('receiver_not_resolved')
    if not method: result['unresolved'].append('invocation_context_unresolved')
    if token.text!='SetActions' and len(args)!=1: result['unresolved'].append('argument_arity')
    return result


def _parse(text, source, token_budget, budget):
    tokens, comments, directives = crafting._lex(text, source, token_budget)
    _take(budget,'analysis_work',MAX_ANALYSIS_WORK,source,0,len(tokens))
    pairs = crafting._pairs(tokens, source)
    definitions, declarations = crafting._classes(tokens, pairs, text, source)
    # The shared scanner skips braced class bodies at file scope, retaining
    # global definitions/prototypes without treating body calls as declarations.
    globals_, names = crafting._methods(tokens, -1, len(tokens), pairs, text, source)
    declarations.update(names)
    methods, bindings, aliases = [], [], []
    class_starts, method_starts, global_shadows = {}, {}, set()
    for old in globals_:
        row = _method(None, old['name'], source, old['line'], old['_start'],
                      digest=old['sha256'], conditions=old['conditions'], stop=old['_end'])
        _take(budget, 'methods', MAX_METHODS, source, row['line'])
        methods.append(row); method_starts[row['_start']] = row
    for owner in definitions:
        _take(budget, 'classes', MAX_CLASSES, source, owner['line'])
        owner['_id'] = source+':class:'+str(owner['_start'])
        owner['_shadows'] = set()
        class_starts[owner['_start']] = owner
        for old in owner.pop('methods'):
            row = _method(owner, old['name'], source, old['line'], old['_start'],
                          digest=old['sha256'], conditions=old['conditions'], stop=old['_end'])
            _take(budget, 'methods', MAX_METHODS, source, row['line'])
            methods.append(row); method_starts[row['_start']] = row
    owners, active = [], []
    for i, token in enumerate(tokens):
        while owners and owners[-1]['_end'] <= i: owners.pop()
        while active and active[-1]['_end'] <= i: active.pop()
        if i in class_starts: owners.append(class_starts[i])
        if i in method_starts: active.append(method_starts[i])
        owner, method = (owners[-1] if owners else None), (active[-1] if active else None)
        if token.text=='typename' and i+1<len(tokens) and tokens[i+1].kind=='identifier':
            (owner['_shadows'] if owner else global_shadows).add(tokens[i+1].text)
        if i in declarations and i+1 in pairs:
            close = pairs[i+1]
            if close+1<len(tokens) and tokens[close+1].text==';':
                _take(budget, 'methods', MAX_METHODS, source, token.line)
                methods.append(_method(owner, token.text, source, token.line, i,
                    declaration_only=True, conditions=token.conditions, stop=close+1))
        is_registry = token.text=='Insert' and method and method['name']=='RegisterActions'
        if (token.text in CALLS or is_registry) and i not in declarations and i+1 in pairs and tokens[i+1].text=='(':
            _take(budget, 'bindings', MAX_BINDINGS, source, token.line)
            bindings.append(_call(tokens, i, pairs, text, source, owner, method))
        if method and token.text in ('if','else','for','foreach','while','switch','case','?'):
            _take(budget, 'controls', MAX_CONTROLS, source, token.line)
            parts = tokens[i+2:pairs[i+1]] if i+1 in pairs and tokens[i+1].text=='(' else []
            method['runtime_control_flow'].append(dict(kind=token.text, line=token.line,
                conditions=list(token.conditions), **_excerpt(parts,text)))
        if token.text=='typedef':
            end=i+1
            while end<len(tokens) and tokens[end].text!=';':
                _take(budget,'analysis_work',MAX_ANALYSIS_WORK,source,token.line)
                end+=1
            _bound(end<len(tokens),source,token.line)
            parts=tokens[i+1:end]
            _take(budget, 'aliases', MAX_ALIASES, source, token.line)
            simple=len(parts)==2 and all(t.kind=='identifier' for t in parts)
            aliases.append(dict(name=parts[-1].text if parts else None,
                target=parts[0].text if simple else None, source=source, line=token.line,
                conditions=list(token.conditions), unresolved=[] if simple else ['complex_alias'],
                **_excerpt(parts,text)))
    # Comment candidates are evidence only. Ambiguous same-line owners/methods
    # are deliberately not assigned to one of several declarations.
    for comment, line, conditions in comments:
        if not any(word in comment for word in CALLS|{'Insert'}): continue
        _take(budget,'analysis_work',MAX_ANALYSIS_WORK,source,line,len(definitions)+len(methods))
        owner_rows=[d for d in definitions if d['line']<=line<=tokens[d['_end']].line]
        method_rows=[m for m in methods if m['line']<=line<=tokens[m['_end']].line and not m['declaration_only']]
        owner=owner_rows[0] if len(owner_rows)==1 else None
        method=method_rows[0] if len(method_rows)==1 else None
        ct, _, _ = crafting._lex(comment,source,token_budget,first_line=line,strict=False,inherited=conditions)
        cp=crafting._pairs(ct,source,strict=False)
        for i, token in enumerate(ct):
            registry=token.text=='Insert' and method and method['name']=='RegisterActions'
            if (token.text in CALLS or registry) and i+1 in cp and ct[i+1].text=='(':
                _take(budget,'bindings',MAX_BINDINGS,source,token.line)
                bindings.append(_call(ct,i,cp,comment,source,owner,method,disabled=True))
    for binding in bindings:
        if binding['enclosing_class'] is None and binding['candidate'] in global_shadows:
            binding['unresolved'].append('identifier_shadowed')
    return definitions, methods, bindings, aliases, directives


def _ancestry(name, grouped, aliases, budget):
    seen, active, unresolved = set(), set(), set()
    stack=[(name,False)]
    while stack:
        _take(budget,'analysis_work',MAX_ANALYSIS_WORK,'.',0)
        current, leaving=stack.pop()
        if leaving:
            active.discard(current); continue
        if current in active:
            unresolved.add('cycle'); continue
        if current in seen: continue
        _bound(len(seen)<MAX_ANCESTRY)
        seen.add(current); active.add(current); stack.append((current,True))
        defs=grouped.get(current,[]); als=aliases.get(current,[])
        if not defs and not als:
            unresolved.add('missing_parent'); continue
        ordinary=0
        for row in defs:
            _take(budget,'analysis_work',MAX_ANALYSIS_WORK,row['source'],row['line'])
            ordinary+=not row['modded']
            if row['conditions']: unresolved.add('conditional_definition')
            if row['header_unresolved']: unresolved.add('header_unresolved')
            if row['modded']: unresolved.add('modded_order_not_evaluated')
            if row['parent']:
                _take(budget,'analysis_work',MAX_ANALYSIS_WORK,row['source'],row['line'])
                stack.append((row['parent'],False))
        if ordinary+len(als)!=1:
            unresolved.add('ambiguous_definition')
        for row in als:
            _take(budget,'analysis_work',MAX_ANALYSIS_WORK,row['source'],row['line'])
            if row['conditions']: unresolved.add('conditional_alias')
            if row['target']:
                _take(budget,'analysis_work',MAX_ANALYSIS_WORK,row['source'],row['line'])
                stack.append((row['target'],False))
            else: unresolved.add('complex_alias')
    return dict(observed_classes=sorted(seen), unresolved=sorted(unresolved),
                resolved=not unresolved)


def _reconcile(definitions, methods, bindings, aliases, budget):
    grouped, alias_map, own_bindings, own_methods = (defaultdict(list) for _ in range(4))
    shadows=defaultdict(set)
    for d in definitions:
        grouped[d['class']].append(d)
        shadows[d['class']].update(d['_shadows'])
    for a in aliases:
        if a['name']: alias_map[a['name']].append(a)
    ancestry={name:_ancestry(name,grouped,alias_map,budget) for name in sorted(grouped)}
    ancestor_sets={}
    for name, info in ancestry.items():
        observed=info['observed_classes']
        _take(budget,'analysis_work',MAX_ANALYSIS_WORK,'.',0,len(observed))
        ancestor_sets[name]=set(observed)
    for i, b in enumerate(bindings):
        b['id']='binding:'+str(i)
        if b['owner_class']: own_bindings[b['owner_class']].append(b['id'])
        name=b['candidate']; lineage=ancestry.get(b['enclosing_class'],{})
        observed=lineage.get('observed_classes',[])
        _take(budget,'analysis_work',MAX_ANALYSIS_WORK,b['source'],b['line'],len(observed))
        shadowed=('identifier_shadowed' in b['unresolved'] or
                  any(name in shadows[parent] for parent in observed))
        if b['call']=='SetActions': resolution='not_applicable'
        elif shadowed:
            resolution='shadowed_identifier'
            if 'identifier_shadowed' not in b['unresolved']:
                b['unresolved'].append('identifier_shadowed')
        elif name is None: resolution='dynamic_expression'
        elif name not in ancestry: resolution='missing_or_dynamic_identifier'
        elif ancestry[name]['unresolved']: resolution='ambiguous'
        elif 'ActionBase' not in ancestor_sets[name]: resolution='declared_non_action'
        else: resolution='declared'; b['action_class']=name
        b['action_resolution']=resolution
        if resolution not in ('declared','not_applicable'):
            b['unresolved'].append(resolution)
    for m in methods:
        if m['owner_class']: own_methods[m['owner_class']].append(m['id'])
    classes, actions = [], []
    adds=defaultdict(list); registry=defaultdict(list)
    for b in bindings:
        if b['action_class']:
            if b['call']=='AddAction' and b['owner_class']: adds[b['action_class']].append(b)
            if b['kind']=='constructor_registry_candidate': registry[b['action_class']].append(b)
    for name in sorted(grouped):
        ancestors=ancestry[name]; observed=ancestors['observed_classes']
        # Charge each ancestry pass before building membership/registration views.
        _take(budget,'analysis_work',MAX_ANALYSIS_WORK,'.',0,len(observed))
        observed_set=ancestor_sets[name]
        action='ActionBase' in observed_set
        row={'class':name, 'definitions':[_public(d) for d in grouped[name]],
             'ancestry':ancestors, 'declared_method_ids':own_methods[name],
             'direct_binding_ids':own_bindings[name],
             'inherited_registration_sources':sorted(p for p in observed if p!=name and own_bindings[p]),
             'effective_actions':'UNKNOWN_NOT_EXECUTED',
             'action_candidate':action,
             'action_candidate_status':('declared-path' if action else
                 'UNKNOWN-unresolved-ancestry' if ancestors['unresolved'] else 'no-source-path'),
             'action_exclusion':None if action or ancestors['unresolved'] else 'no_declared_ActionBase_path',
             'item_ancestry_observed':'ItemBase' in observed_set}
        classes.append(row)
        if action:
            refs=adds[name]
            status=('source-add-call' if any(not b['disabled'] for b in refs) else
                    'comment-disabled-only' if refs else 'no-item-add-call-observed')
            actions.append({'class':name,'ancestry':ancestors,
                'path_kinds':[kind for base,kind in (('ActionContinuousBase','continuous'),
                    ('ActionInteractBase','interact')) if base in observed_set],
                'source_status':status, 'item_binding_ids':[b['id'] for b in refs],
                'constructor_binding_ids':[b['id'] for b in registry[name]],
                'runtime_status':'UNKNOWN'})
    return classes, actions


def audit_tree(root, *, expected_manifest_sha256=None, fallback_encoding=None):
    """Read-only, deterministic lexical census. ``valid`` is not runtime proof."""
    sources, definitions, methods, bindings, aliases, directives, diagnostics = ([] for _ in range(7))
    complete, token_budget, budget = True, [0], Counter()
    def error(code, source='.', line=0):
        diagnostics.append(dict(code=code,source=source,line=line,severity='error'))
    if fallback_encoding not in (None,'cp1252'):
        error('invalid_encoding_policy'); fallback_encoding=None
    try:
        for source, content in crafting._sources(root):
            record=dict(path=source,bytes=len(content),sha256=_sha(content)); sources.append(record)
            try:
                try:
                    text=content.decode('utf-8-sig'); record['encoding']='utf-8-sig'
                except UnicodeError:
                    if fallback_encoding is None: raise crafting.CensusError('invalid_source',source) from None
                    try:
                        text=content.decode(fallback_encoding); record['encoding']=fallback_encoding
                    except UnicodeError: raise crafting.CensusError('invalid_source',source) from None
                ds, ms, bs, als, dirs = _parse(text,source,token_budget,budget)
                definitions.extend(ds); methods.extend(ms); bindings.extend(bs)
                aliases.extend(als); directives.extend(dirs)
            except crafting.CensusError as exc:
                if exc.code=='resource_limit': raise
                complete=False; error(exc.code,exc.source,exc.line)
    except crafting.CensusError as exc:
        complete=False; error(exc.code,exc.source,exc.line)
    sources.sort(key=lambda r:r['path'])
    for rows in (definitions,methods,bindings,aliases,directives):
        rows.sort(key=lambda r:(r['source'],r['line']))
    if not sources:
        complete=False; error('no_sources')
    try:
        classes, actions=_reconcile(definitions,methods,bindings,aliases,budget)
    except crafting.CensusError as exc:
        classes,actions=[],[];complete=False;error(exc.code,exc.source,exc.line)
    manifest=None
    if complete:
        payload=dict(schema_version=1,suffix='.c (case-insensitive)',
                     fallback_encoding=fallback_encoding,sources=sources)
        manifest=_sha(json.dumps(payload,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode())
    if expected_manifest_sha256 is not None:
        if not isinstance(expected_manifest_sha256,str) or not re.fullmatch('[0-9a-fA-F]{64}',expected_manifest_sha256):
            error('invalid_manifest_pin')
        elif manifest!=expected_manifest_sha256.lower(): error('manifest_mismatch')
    callbacks=[dict(_public(m),category=CALLBACKS[m['name']]) for m in methods if m['name'] in CALLBACKS]
    valid=complete and not diagnostics
    report=dict(schema_version=1,evidence_layer='T0_source_only',valid=valid,inputs_complete=complete,
        manifest_sha256=manifest,sources=sources,fallback_encoding=fallback_encoding,
        classes=classes,actions=actions,methods=[_public(m) for m in methods],
        callbacks=callbacks,bindings=bindings,aliases=aliases,directives=directives,
        diagnostics=sorted(diagnostics,key=lambda r:(r['source'],r['line'],r['code'])),
        limitations=list(LIMITATIONS),supported_callback_names=CALLBACKS,
        full_effective_behavior_coverage=False,runtime_acceptance='NOT_EVALUATED',
        coverage=dict(source_census_complete=valid,source_files=len(sources),
            source_bytes=sum(s['bytes'] for s in sources),tokens=token_budget[0],analysis_work=budget['analysis_work'],
            class_declarations=len(definitions),classes=len(classes),action_candidates=len(actions),
            aliases=len(aliases),method_declarations=len(methods),callbacks=len(callbacks),
            callbacks_by_category=dict(sorted(Counter(c['category'] for c in callbacks).items())),
            emitted_bindings=len(bindings),bindings_by_call=dict(sorted(Counter(b['call'] for b in bindings).items())),
            disabled_bindings=sum(b['disabled'] for b in bindings),
            unresolved_bindings=sum(bool(b['unresolved']) for b in bindings),
            unresolved_ancestry_classes=sum(bool(c['ancestry']['unresolved']) for c in classes),
            excluded_non_action_classes=sum(c['action_exclusion'] is not None for c in classes),
            unknown_action_ancestry_classes=sum(c['action_candidate_status']=='UNKNOWN-unresolved-ancestry' for c in classes),
            unregistered_item_action_candidates=sum(a['source_status']=='no-item-add-call-observed' for a in actions)))
    size=0
    for piece in json.JSONEncoder(ensure_ascii=True,allow_nan=False).iterencode(report):
        size+=len(piece)
        if size>MAX_OUTPUT_BYTES:
            # No silently truncated successful report, even with complete reads.
            return dict(schema_version=1,valid=False,inputs_complete=False,
                runtime_acceptance='NOT_EVALUATED',full_effective_behavior_coverage=False,
                diagnostics=[dict(code='resource_limit',source='.',line=0,severity='error')],
                coverage=dict(source_census_complete=False),omission='output_budget_exceeded')
    return report


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',required=True)
    parser.add_argument('--expect-manifest-sha256')
    parser.add_argument('--fallback-encoding',choices=['cp1252'])
    args=parser.parse_args(argv)
    report=audit_tree(args.root,expected_manifest_sha256=args.expect_manifest_sha256,
                      fallback_encoding=args.fallback_encoding)
    print(json.dumps(report,sort_keys=True,ensure_ascii=True,allow_nan=False))
    return 0 if report['valid'] else 1


if __name__=='__main__':
    raise SystemExit(main())
