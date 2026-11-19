"""Coordinate receipt-backed overlay removal from a stopped private mission.

The default all-overlay request fails explicitly: inventory_sizes generates
addon overrides and has no receipt/rollback API. Select loot vehicles to remove
those mission overlays. A scratch rehearsal precedes every live removal. The
operation is resumable, not a transaction across installers; keep the server
stopped and retain recovery data if any live rollback refuses.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.package import economy, inventory_sizes, loot_boost, travel

OVERLAYS = ('loot', 'inventory', 'vehicles')
INVENTORY_GAP = ('inventory receipt rollback unavailable: inventory_sizes.py generates '
                 'CfgVehicles overrides inside the HC PBO; it has no install receipt or rollback '
                 'function. Rebuild and redistribute a reviewed addon without that generated '
                 'block; mission rollback cannot remove it.')


def _undo(mission, selected):
    removed = []
    # Loot can hold travel's types.xml, so reverse their install order.
    for name, installer in (('loot', loot_boost), ('vehicles', travel)):
        managed = economy.child(mission, installer.MANAGED)
        if name in selected and os.path.lexists(managed):
            installer.rollback(mission)
            removed.append(name)
    return removed


def remove(mission, overlays=OVERLAYS, *, stopped=False, dry_run=False):
    selected = tuple(overlays)
    if not selected or len(set(selected)) != len(selected) or set(selected) - set(OVERLAYS):
        raise ValueError('select unique known overlay names: loot inventory vehicles')
    if not dry_run and not stopped:
        raise ValueError('live removal requires --server-stopped; stop the server first')
    if 'inventory' in selected:
        # This existing generator is the authoritative source of block syntax;
        # an empty block is still a source build, never a mission receipt undo.
        inventory_sizes.render_block([])
        raise ValueError(INVENTORY_GAP)
    target = economy._target(mission)
    # Validate before copytree: no symlinks, hard links, special files or escaped
    # paths can be laundered into ordinary scratch files. Never copy live saves.
    for directory, folders, files in os.walk(target, followlinks=False):
        root = Path(directory)
        for name in folders + files:
            path = root / name
            economy.child(target, path.relative_to(target).as_posix())
            if not path.is_dir():
                economy.plain_file(target, path)
        if root == target:
            folders[:] = [name for name in folders if not name.startswith('storage_')]
    with tempfile.TemporaryDirectory(prefix='hc-overlay-remove-') as temporary:
        scratch = Path(temporary) / 'mission'
        shutil.copytree(target, scratch,
                        ignore=lambda directory, names: [name for name in names
                            if Path(directory) == target and name.startswith('storage_')])
        planned = _undo(scratch, selected)
        removed = []
        if not dry_run:
            removed = _undo(target, selected)
    return {'planned': planned, 'removed': removed, 'dry_run': dry_run,
            'inventory': 'not_removed; source_rebuild_required', 'runtime': 'PENDING'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mission', type=Path, required=True)
    parser.add_argument('--overlays', nargs='+', choices=OVERLAYS, default=OVERLAYS)
    parser.add_argument('--server-stopped', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args(argv)
    try:
        result = remove(args.mission, args.overlays, stopped=args.server_stopped, dry_run=args.dry_run)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print('overlay_remove refused: ' + str(error), file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    print('overlay_remove runtime=PENDING; inventory source rebuild remains separate')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
