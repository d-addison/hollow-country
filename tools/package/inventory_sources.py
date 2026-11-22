"""Read-only inventory config inputs; never extracts scripts or assets."""
from pathlib import Path
from tools.audit import pbo_config as reader

# Folder aliases keep restricted provider identifiers out of packaged config data.
WORKSHOP_FOLDERS = {
    '@CF': '1559212036', '@COT': '1564026768', '@DabsFramework': '2545327648',
    '@Expansion-Core': '2291785308', '@Expansion-Licensed': '2116157322',
    '@Expansion-Vehicles': '2291785437', '@Expansion-AI': '2792982069',
    '@Expansion-Navigation': '2792984722',
    '@AmbientAnimals': '3114410963',
    '@RaG_Core': '3556131153', '@RaG_Immersive_Vehicles': '3105330157',
    '@WeaponPackA': '2646817942', '@WeaponPackB': '2443122116',
}
BANNED = ('snafu', 'tacticalflava', '2646817942', '2291785308', '2792982069')


def safe_text(text):
    compact = ''.join(c for c in text.lower() if c.isalnum())
    return not any(word in compact for word in BANNED)


def text_rows(data, fields):
    """Use the audit reader's bounded lexer, retaining numeric inventory arrays."""
    if len(data) > reader.MAX_CONFIG_BYTES:
        raise ValueError('text inventory config exceeds budget')
    tokens = reader._Tokens(reader._strip_text(data.decode('latin-1')), reader.MAX_TEXT_TOKENS)

    def body(depth):
        if depth > reader.MAX_TEXT_DEPTH:
            raise ValueError('text inventory nesting exceeds budget')
        classes, values = {}, {}
        while True:
            kind, name = tokens.next()
            if kind == 'eof':
                if depth == 0:
                    return classes, values
                raise ValueError('truncated inventory config')
            if (kind, name) == ('op', '}'):
                return classes, values
            if (kind, name) == ('op', ';'):
                continue
            if (kind, name) == ('id', 'class'):
                _, cname = tokens.next()
                parent = ''
                nxt = tokens.next()
                if nxt == ('op', ':'):
                    _, parent = tokens.next()
                    nxt = tokens.next()
                if nxt == ('op', ';'):
                    continue
                if nxt != ('op', '{'):
                    raise ValueError('malformed inventory class')
                children, props = body(depth + 1)
                reader._expect(tokens, ';')
                for child_name, (_, _, child_props) in children.items():
                    if child_name.lower() == 'opticsinfo':
                        props.update({k: v for k, v in child_props.items()
                                      if k in {'opticsZoomMin', 'opticsZoomMax'}})
                classes[cname] = (parent, children, props)
            elif kind == 'id' and tokens.peek() == ('op', '['):
                tokens.next()
                reader._expect(tokens, ']')
                _, op = tokens.next()
                if op not in ('=', '+='):
                    raise ValueError('malformed inventory array')
                value = reader._text_array(tokens)
                reader._expect(tokens, ';')
                if name in fields | {'units', 'requiredAddons'}:
                    if op == '+=' and name in {'inventorySlot', 'attachments'}:
                        values['append:' + name] = values.get('append:' + name, []) + value
                    elif op == '+=' and name in {'units', 'requiredAddons'}:
                        values[name] = values.get(name, []) + value
                    elif op == '+=':
                        raise ValueError('unsupported inventory array append: ' + name)
                    else:
                        values[name] = value
                        values.pop('append:' + name, None)
            elif kind == 'id' and tokens.peek() == ('op', '='):
                tokens.next()
                value = reader._text_scalar(tokens)
                if name in fields:
                    if name == 'scope' and isinstance(value, str):
                        value = reader._KEYWORD_SCOPE.get(value.lower())
                    if value is not None:
                        values[name] = value
            else:
                reader._skip_statement_from(tokens, kind, name)
    roots, _ = body(0)
    patches, rows = {}, {}
    for name, (_, children, _) in roots.items():
        if name.lower() == 'cfgpatches':
            patches.update({n: props for n, (_, _, props) in children.items()})
        elif name.lower() in {'cfgvehicles', 'cfgmagazines', 'cfgweapons'}:
            root = {'cfgvehicles': 'CfgVehicles', 'cfgmagazines': 'CfgMagazines', 'cfgweapons': 'CfgWeapons'}[name.lower()]
            rows.update({(n if root == 'CfgVehicles' else root + '::' + n):
                         {'name': n, 'root': root, 'parent': parent, 'fields': props}
                         for n, (parent, _, props) in children.items()})
    return patches, rows


def documents(addons, source, fields, rap_rows, vanilla=False):
    addons = Path(addons)
    if not addons.is_dir():
        raise ValueError('inventory source directory missing: ' + source)
    docs, skipped = [], []
    families = ('characters_', 'gear_', 'weapon_', 'weapons_', 'vehicles_')
    for path in sorted(addons.iterdir(), key=lambda p: p.name.lower()):
        if path.suffix.lower() == '.ebo':
            skipped.append({'pbo': path.name, 'reason': 'encrypted-ebo'})
            continue
        if path.suffix.lower() != '.pbo':
            continue
        if vanilla and not (path.name.startswith(families) or path.name in {'dz.pbo', 'plants.pbo'}):
            continue
        index = reader.read_pbo_index(path)
        entries = sorted(index['entries'], key=lambda e: e['name'].lower())
        # A bin supersedes cpp only in the same config directory.
        bins = {e['name'].lower().replace('\\', '/')[:-3] for e in entries
                if e['name'].lower().endswith('config.bin')}
        for entry in entries:
            member = entry['name'].lower().replace('\\', '/')
            if not member.endswith(('config.bin', 'config.cpp')):
                continue
            if member.endswith('.cpp') and member[:-3] in bins:
                continue
            data = reader.read_member(path, index, entry['name'])
            patches, rows = rap_rows(data) if data[:4] == b'\0raP' else text_rows(data, fields)
            docs.append({'source': source, 'pbo': path.name, 'member': entry['name'],
                         'patches': patches, 'rows': rows})
    # Text fragments without CfgPatches belong to the nearest enclosing config
    # directory in the same PBO. Never infer ownership from a provider's name.
    for doc in docs:
        if doc['patches']:
            continue
        member = doc['member'].lower().replace('\\', '/')
        enclosing = [d for d in docs if d['pbo'] == doc['pbo'] and d['patches'] and
                     member.startswith(d['member'].lower().replace('\\', '/').rsplit('/', 1)[0] + '/')]
        roots = [d for d in docs if d['pbo'] == doc['pbo'] and d['patches'] and
                 '/' not in d['member'].replace('\\', '/')]
        candidates = sorted(enclosing or roots, key=lambda d: len(d['member']), reverse=True)
        if candidates:
            doc['enclosing_patches'] = candidates[0]['patches']
    return docs, skipped
