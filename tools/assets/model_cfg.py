"""Deterministic model.cfg for static props; stdlib only, no native tool runs.

Schema reference: https://community.bistudio.com/wiki/Model_Config
Named sections must match selections in the model. An empty skeleton is used:
this emitter makes no bones, animations, inheritance or engine acceptance claims.
"""
import re
from collections.abc import Iterable


def emit_model_cfg(model_name: str, sections: Iterable[str] = ()) -> str:
    """Emit CfgSkeletons/CfgModels using a model basename and named sections.

    Class names are identifiers, never paths or filenames. Sections accept a
    conservative ASCII selection alphabet, preventing config string injection.
    The caller chooses sections explicitly (memory/component selections should
    not automatically become render sections). Sorting removes input order.
    """
    if (not isinstance(model_name, str)
            or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', model_name)
            or model_name.casefold() == 'default'):
        raise ValueError('model name must be a non-Default config identifier')
    if isinstance(sections, str):
        raise ValueError('sections must be an iterable of names')
    names = list(sections)
    if any(not isinstance(name, str) or len(name) > 63
           or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_. -]*', name) for name in names):
        raise ValueError('invalid section name')
    if len({name.casefold() for name in names}) != len(names):
        raise ValueError('duplicate section name')
    quoted = ', '.join('"' + name + '"' for name in sorted(names))
    return (
        'class CfgSkeletons\n{\n'
        '    class Default\n    {\n'
        '        isDiscrete = 1;\n'
        '        skeletonInherit = "";\n'
        '        skeletonBones[] = {};\n'
        '    };\n};\n'
        'class CfgModels\n{\n'
        f'    class {model_name}\n    {{\n'
        '        sectionsInherit = "";\n'
        f'        sections[] = {{{quoted}}};\n'
        '        skeletonName = "";\n'
        '    };\n};\n'
    )
