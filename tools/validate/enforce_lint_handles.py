"""HC-E041 (#334): no Expansion group is stored outside the bridge file.

`eAIGroup` is not Managed, so a raw member, static or container element dangles
once the provider frees the group. Outside HCXExpansionBridge.c only a bridge
handle (HCXAIGroupHold) may be kept. A `ref`/`autoptr` eAIBase member is refused
too: an agent is an engine-owned entity and a strong member would outlive it.
Locals and parameters are short-lived and are not flagged. Pure source scan on
the shared enforce_source model; it proves nothing about DayZ behaviour.
"""
from dataclasses import dataclass
import re

BRIDGE_FILE = 'mods/HollowCountryExpansionAI/scripts/4_World/HCXExpansionBridge.c'
RULE = 'HC-E041'
DESCRIPTION = ('Expansion group or agent stored outside the bridge (eAIGroup member/static/container element, '
               'or a ref eAIBase member): keep an HCXAIGroupHold handle and resolve it through HCHold* calls')

# Field types arrive with whitespace removed (`array<refeAIGroup>`), so the
# `ref`/`autoptr` word runs into the type name. Element names are bounded by
# the generic punctuation, which keeps `eAIGroupFoo` and `HCeAIGroup` out.
_GROUP = re.compile(r'(?:^|[<,])(?:ref|autoptr)?eAIGroup(?=$|[>,])')
_STRONG_AGENT = re.compile(r'(?:^|[<,])(?:ref|autoptr)eAIBase(?=$|[>,])')


@dataclass(frozen=True)
class HandleFinding:
    rule: str
    path: str
    offset: int
    symbol: str
    message: str
    key: str


def stored_handles(source):
    """Yield HandleFinding for each offending class field of one Source."""
    if source.rel == BRIDGE_FILE:
        return
    for definition in source.classes:
        for member in definition.fields:
            kind = ''
            if _GROUP.search(member.type):
                kind = 'eAIGroup'
            elif _STRONG_AGENT.search(member.type) or (member.strong and member.type == 'eAIBase'):
                kind = 'ref eAIBase'
            if not kind:
                continue
            symbol = definition.name + '.' + member.name
            yield HandleFinding(RULE, source.rel, member.offset, symbol,
                                f'{symbol}: {member.type} stores {kind} outside the bridge; '
                                'keep a HCXAIGroupHold and read it through HCHold*',
                                f'{symbol}:{member.type}')
