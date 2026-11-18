"""Shared offline admission and class ownership for repo-written CE extensions."""


def _registrations():
    # Import lazily: writers also use this helper. Folder names stay owned by their writers;
    # a hollow-country prefix alone never grants admission to an operator extension.
    import importlib
    import importlib.util
    from tools.package import economy, optional_overlays, travel
    types = {'types.xml': 'types'}
    registrations = {
        economy.MANAGED + '/ce': types,
        travel.MANAGED + '/ce': {name.removeprefix('ce/'): kind for name, kind in
                               zip(travel.CE_FILES, ('types', 'events', 'spawnabletypes'))},
        optional_overlays.MANAGED: {name: name[:-4] for name in optional_overlays.GENERATED
                                   if name in {'types.xml', 'events.xml', 'spawnabletypes.xml'}},
    }
    # The standalone friend bundle omits weapon tools. Admit their registrations only
    # when those writers are available, without importing absent optional dependencies.
    for name in ('snafu_optional', 'tactical_flava_optional'):
        qualified = 'tools.package.' + name
        if importlib.util.find_spec(qualified) is not None:
            writer = importlib.import_module(qualified)
            files = dict(types)
            if hasattr(writer, 'SPAWNABLE'):
                files[writer.SPAWNABLE.removeprefix('ce/')] = 'spawnabletypes'
            registrations[writer.MANAGED + '/ce'] = files
    return registrations


def checked_core(data):
    """Admit only unique known folders with writer-supported file declarations."""
    from tools.package import economy
    core = economy.xml(data, 'economycore')
    allowed = _registrations()
    unknown = sorted({ce.get('folder', '<missing folder>') for ce in core.findall('ce')
                      if ce.get('folder') not in allowed})
    if unknown:
        raise ValueError('existing CE extensions need explicit operator reconciliation: ' + ', '.join(unknown))
    seen = set()
    for ce in core.findall('ce'):
        folder = ce.get('folder')
        files = set()
        if ce.attrib != {'folder': folder} or folder in seen:
            raise ValueError('duplicate or unsupported CE registration: ' + folder)
        seen.add(folder)
        for file in ce:
            name = file.get('name')
            if (file.tag != 'file' or len(file) or name in files or name not in allowed[folder]
                    or file.attrib != {'name': name, 'type': allowed[folder].get(name)}):
                raise ValueError('unsupported CE file registration: ' + folder)
            files.add(name)
    return core


def registered_types(source, core):
    """Read every registered types file, with the mission's safe regular-file checks."""
    from tools.package import economy
    types = {}
    for ce in core.findall('ce'):
        for file in ce.findall('file'):
            if file.get('type') == 'types':
                relative = ce.get('folder') + '/' + file.get('name')
                types.update(economy._unique(economy.xml(
                    economy.read_plain(source, relative), 'types').findall('type')))
    return types


def refuse_collisions(names, existing):
    """Class ownership is case-insensitive, including registered managed overrides."""
    taken = {name.lower() for name in existing}
    collisions = sorted(name for name in names if name.lower() in taken)
    if collisions:
        raise ValueError('classes already defined by stock or a registered CE extension: ' + ', '.join(collisions))
