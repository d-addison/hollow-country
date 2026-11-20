"""Build the original, optional client/server bipod-sway guard for issue #302.

Run before signing/bundling:
  python3 -B -m tools.package.weapon_pack_guards --workshop <221100> --out <new-dir>

Include hollowcountry_weapon_pack_guards.pbo alongside the adapter PBO on BOTH
peers when status is generated. Sign it with the usual release key. Do not add
script_a to HollowCountry or HollowCountryExpansionAI requiredAddons: only the
separate PBO depends on it. An absent pack emits no PBO; an unfamiliar installed
script refuses generation for review. No Workshop code is copied into output.

The source .c is deliberately inactive in the ordinary adapter; only this builder
activates it. The lead must wire this builder into release/native compile inputs.
"""
import argparse
import hashlib
import json
from pathlib import Path

from tools.audit.pbo_config import read_configs, read_member, read_pbo_index
from tools.package import pbo

ROOT = Path(__file__).resolve().parents[2]
ITEM = '2646817942'
PATCH = 'script_a'
SOURCE = ROOT / 'mods/HollowCountryExpansionAI/scripts/4_World/HCXWeaponPackGuards.c'
MEMBER = 'weapon-pack-guards/4_World/HCXWeaponPackGuards.c'
PBO_NAME = 'hollowcountry_weapon_pack_guards.pbo'
# Read-only installed evidence, 2026-11-20. Pin the two relevant methods, not assets.
PINS = {
    'Scripts/4_World/Weapons/Bipod/TF_BipodSway.c':
        '1ba6df3cfe4deee93cc03f962c3567b5c66e7c5b20151719ca12c09f6069f16c',
    'Scripts/4_World/Weapons/TF_WeaponBase.c':
        '9c70844b021761cde47af45b9302e36105073c27ef11bdca8c872643f6f37140',
}
CONFIG = '''class CfgPatches
{
    class HCXWeaponPackGuards
    {
        units[] = {};
        weapons[] = {};
        requiredVersion = 0.1;
        requiredAddons[] = {"HollowCountryExpansionAI", "script_a"};
    };
};
class CfgMods
{
    class HCXWeaponPackGuards
    {
        type = "mod";
        dependencies[] = {"World"};
        class defs
        {
            class worldScriptModule
            {
                value = "";
                files[] = {"HollowCountryExpansionAI/weapon-pack-guards/4_World"};
            };
        };
    };
};
'''


def generate(workshop):
    """Return original PBO bytes and a privacy-safe receipt, or an absent receipt."""
    workshop = Path(workshop)
    if not workshop.is_dir():
        raise ValueError('Workshop content root is missing; absence is not verified')
    item = workshop / ITEM
    if not item.exists():
        return None, {'status': 'absent', 'runtime': 'PENDING'}
    candidates = [path for path in item.iterdir()
                  if path.is_dir() and path.name.lower() == 'addons']
    if len(candidates) != 1:
        raise ValueError('installed weapon pack has no unique addons directory')
    candidates = [path for path in candidates[0].iterdir()
                  if path.is_file() and path.name.lower() == 'script_a.pbo']
    if len(candidates) != 1:
        raise ValueError('installed weapon pack has no unique script PBO')
    installed = candidates[0]
    index = read_pbo_index(installed)
    if PATCH not in read_configs(installed, ('CfgPatches',), index)['CfgPatches']:
        raise ValueError('weapon pack script CfgPatches changed; review required')
    for member, expected in PINS.items():
        data = read_member(installed, index, member)
        if data is None or hashlib.sha256(data).hexdigest() != expected:
            raise ValueError('weapon pack sway API changed; review required: ' + member)
    source = SOURCE.read_bytes()
    marker = b'#ifdef HCX_WEAPON_PACK_GUARDS\n'
    if source.count(marker) != 1 or not source.endswith(b'#endif\n'):
        raise ValueError('guard activation markers changed')
    # Strip the wrapper, leaving ordinary inspectable Enforce in the generated PBO.
    script = source.replace(marker, b'', 1).removesuffix(b'#endif\n')
    files = {'config.cpp': CONFIG.encode(), MEMBER: script}
    blob = pbo.pack(files, prefix='HollowCountryExpansionAI')
    parsed = pbo.parse(blob, prefixes=('HollowCountryExpansionAI',))
    # Verify all original bytes survive the standard packer; no third-party payload.
    if parsed != ('HollowCountryExpansionAI', files):
        raise ValueError('guard PBO roundtrip differs')
    return blob, {
        'status': 'generated', 'runtime': 'PENDING', 'pbo': PBO_NAME,
        'sha256': hashlib.sha256(blob).hexdigest(),
        'source_sha256': hashlib.sha256(source).hexdigest(),
        'installed_script_pins': PINS,
        'requiredAddons': ['HollowCountryExpansionAI', PATCH],
        'native_compile': 'PENDING', 'one_server_one_client': 'PENDING',
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workshop', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True,
                        help='new staging directory; existing output is refused')
    args = parser.parse_args(argv)
    if args.out.exists():
        parser.exit(1, 'weapon_pack_guards: output already exists; use fresh staging\n')
    try:
        blob, receipt = generate(args.workshop)
    except (OSError, ValueError) as error:
        # OSError paths can contain account names; never echo them.
        reason = str(error) if isinstance(error, ValueError) else 'installed/source read failed'
        parser.exit(1, 'weapon_pack_guards: ' + reason + '\n')
    args.out.mkdir(parents=True)
    if blob is not None:
        (args.out / PBO_NAME).write_bytes(blob)
    (args.out / 'weapon-pack-guards.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print('weapon_pack_guards: ' + receipt['status'] + ' runtime=PENDING')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
