"""Shared release PBO catalogue, catalog provenance gate and animation build recipe."""
from pathlib import Path
import sys

ADDONS = Path('/mnt/d/SteamLibrary/steamapps/common/DayZServer/Addons')


COMPAT_STEM = 'hollowcountry_compat'


def compat_label(name):
    """Report label of a compat PBO: 'compat' for the base, 'compat-<slot>' for an optional one."""
    stem = Path(name).stem
    if stem == COMPAT_STEM:
        return 'compat'
    if not stem.startswith(COMPAT_STEM + '_') or '_' in stem[len(COMPAT_STEM) + 1:]:
        raise ValueError('not a compat PBO name: ' + name)
    return 'compat-' + stem[len(COMPAT_STEM) + 1:]


def signing_inputs(guard_name=None, compat_names=()):
    """The complete shipped PBO catalogue: (stem, mod folder, report label).

    compat_names are the PBO file names tools.package.compat_addon generated for this build
    (the base PBO always, plus one per declared optional provider)."""
    rows = [('hollowcountry', 'HollowCountry', 'base'),
            ('hollowcountryanims', 'HollowCountry', 'anims'),
            ('hollowcountryexpansionai', 'HollowCountryExpansionAI', 'addon')]
    if guard_name:
        rows.append((Path(guard_name).stem, 'HollowCountryExpansionAI', 'weapon-pack-guards'))
    for name in compat_names:
        rows.append((Path(name).stem, 'HollowCountryExpansionAI', compat_label(name)))
    return rows


def build_anims(tree, addons, scratch, run):
    """Always rebuild: installed vanilla inputs and all authored inputs are read fresh.

    run(command, cwd) is supplied by the caller for bounded, private diagnostics.
    Both release and compile-gate builds refuse stale admin map inputs offline.
    The installed Addons folder is only read by these generators.
    """
    run([sys.executable, '-B', '-m', 'tools.package.admin_world_catalog', '--check'], tree)
    output = scratch / 'anims'
    for script in ('build_infected_clips.py', 'build_anims_addon.py'):
        run([sys.executable, '-B', tree / 'tools/anim' / script,
             '--addons', addons.absolute(), '--out', output], tree)
    package = output / 'addons/HollowCountryAnims.pbo'
    run([sys.executable, '-B', '-m', 'tools.package.pbo', 'verify',
         '--prefix', 'HollowCountryAnims', package], tree)
    return package
