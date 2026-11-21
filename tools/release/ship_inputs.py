"""Shared release PBO catalogue and uncached animation build recipe."""
from pathlib import Path
import sys

ADDONS = Path('/mnt/d/SteamLibrary/steamapps/common/DayZServer/Addons')


def signing_inputs(guard_name=None):
    """The complete shipped PBO catalogue: (stem, mod folder, report label)."""
    rows = [('hollowcountry', 'HollowCountry', 'base'),
            ('hollowcountryanims', 'HollowCountry', 'anims'),
            ('hollowcountryexpansionai', 'HollowCountryExpansionAI', 'addon')]
    if guard_name:
        rows.append((Path(guard_name).stem, 'HollowCountryExpansionAI', 'weapon-pack-guards'))
    return rows


def build_anims(tree, addons, scratch, run):
    """Always rebuild: installed vanilla inputs and all authored inputs are read fresh.

    run(command, cwd) is supplied by the caller for bounded, private diagnostics.
    The installed Addons folder is only read by these generators.
    """
    output = scratch / 'anims'
    for script in ('build_infected_clips.py', 'build_anims_addon.py'):
        run([sys.executable, '-B', tree / 'tools/anim' / script,
             '--addons', addons.absolute(), '--out', output], tree)
    package = output / 'addons/HollowCountryAnims.pbo'
    run([sys.executable, '-B', '-m', 'tools.package.pbo', 'verify',
         '--prefix', 'HollowCountryAnims', package], tree)
    return package
