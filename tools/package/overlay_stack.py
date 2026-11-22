"""One ordered, validated stack of CE and overlay layers (W5-02).

A layer is a named contribution (a CE extension folder with its registered files, or an
optional-overlay pack). The stack validates the whole set, rejects conflicts with a reason,
and resolves one deterministic order, so every consumer (ce_extensions admission, rag_optional
pack application) reads the same answer instead of keeping its own table.

Pure standard library: no filesystem access, no XML and no imports from other package
modules, so the friend bundle can ship it unchanged.

Ordering: `after` is a soft constraint (a named layer is placed earlier only when it is
present, because optional writers may be absent from a bundle); `requires` is hard (a missing
layer is an error). Ties resolve by layer name, never by registration or dict order.
"""
from dataclasses import dataclass

KINDS = ('types', 'events', 'spawnabletypes')


@dataclass(frozen=True)
class Layer:
    name: str
    # Mission-relative CE folder this layer owns; empty for layers that only add entries
    # to an existing file and register no folder of their own.
    folder: str = ''
    # ((file name, kind), ...); kind is one of KINDS.
    files: tuple = ()
    after: tuple = ()
    requires: tuple = ()


def _valid_folder(folder):
    parts = folder.split('/')
    return not (folder.startswith('/') or '\\' in folder or ':' in folder
                or any(part in ('', '.', '..') for part in parts))


class Stack:
    def __init__(self, layers=()):
        self._layers = {}
        self._folders = {}
        for layer in layers:
            self.add(layer)

    def add(self, layer):
        if not isinstance(layer, Layer) or not layer.name:
            raise ValueError('overlay layer needs a name')
        if layer.name in self._layers:
            raise ValueError('duplicate overlay layer: ' + layer.name)
        if layer.name in layer.after or layer.name in layer.requires:
            raise ValueError('overlay layer depends on itself: ' + layer.name)
        if layer.folder:
            if not _valid_folder(layer.folder):
                raise ValueError('unsafe overlay folder for ' + layer.name + ': ' + layer.folder)
            owner = self._folders.get(layer.folder.casefold())
            if owner is not None:
                raise ValueError('overlay folder claimed twice: ' + layer.folder
                                 + ' by ' + owner + ' and ' + layer.name)
        elif layer.files:
            raise ValueError('overlay layer registers files without a folder: ' + layer.name)
        seen = set()
        for name, kind in layer.files:
            if kind not in KINDS:
                raise ValueError('unsupported overlay file kind for ' + layer.name + ': ' + str(kind))
            if not name or '/' in name or '\\' in name or name in ('.', '..') or name.casefold() in seen:
                raise ValueError('invalid or duplicate overlay file for ' + layer.name + ': ' + str(name))
            seen.add(name.casefold())
        self._layers[layer.name] = layer
        if layer.folder:
            self._folders[layer.folder.casefold()] = layer.name
        return self

    def ordered(self):
        """Layers in one deterministic dependency order; raises on a missing hard dependency
        or a cycle."""
        for layer in self._layers.values():
            missing = sorted(name for name in layer.requires if name not in self._layers)
            if missing:
                raise ValueError('overlay layer ' + layer.name + ' requires missing layer: ' + ', '.join(missing))
        before = {name: {d for d in (*layer.after, *layer.requires) if d in self._layers}
                  for name, layer in self._layers.items()}
        done, result = set(), []
        while len(result) < len(self._layers):
            ready = sorted(name for name, deps in before.items() if name not in done and deps <= done)
            if not ready:
                raise ValueError('overlay layer ordering cycle among: '
                                 + ', '.join(sorted(set(self._layers) - done)))
            done.add(ready[0])
            result.append(self._layers[ready[0]])
        return tuple(result)

    def registrations(self):
        """{folder: {file name: kind}} in stack order, for CE admission."""
        return {layer.folder: dict(layer.files) for layer in self.ordered() if layer.folder}


def refuse_class_collisions(names, existing):
    """Class ownership is case-insensitive across every layer and stock."""
    taken = {name.lower() for name in existing}
    collisions = sorted(name for name in names if name.lower() in taken)
    if collisions:
        raise ValueError('classes already defined by stock or a registered CE extension: ' + ', '.join(collisions))
