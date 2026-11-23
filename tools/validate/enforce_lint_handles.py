"""HC-E041 (#334): no Expansion group is stored outside the bridge file.

`eAIGroup` is not Managed, so a raw member, static or container element dangles
once the provider frees the group. Outside HCXExpansionBridge.c only a bridge
handle (HCXAIGroupHold) may be kept. An eAIBase member in any form (plain, `ref`,
`autoptr`, `array<eAIBase>`, `ref array<ref eAIBase>`, map values, statics) is
refused too: an agent is an engine-owned entity the provider deletes on its own
schedule, so only an HCXAIAgentHold handle may be kept. The provider's raw
`eAIDynamicPatrol.m_Group` field is read only inside the bridge file; any other
mention under mods/HollowCountryExpansionAI is a finding. Locals and parameters
are short-lived and are not flagged. Pure source scan on the shared
enforce_source model; it proves nothing about DayZ behaviour.
"""
from dataclasses import dataclass
import re

BRIDGE_FILE = 'mods/HollowCountryExpansionAI/scripts/4_World/HCXExpansionBridge.c'
RULE = 'HC-E041'
DESCRIPTION = ('Expansion group or agent stored outside the bridge (eAIGroup or eAIBase member/static/container '
               'element, or a raw provider m_Group read): keep an HCXAIGroupHold / HCXAIAgentHold handle and '
               'resolve it through the bridge')

# Field types arrive with whitespace removed (`array<refeAIGroup>`), so the
# `ref`/`autoptr` word runs into the type name. Element names are bounded by
# the generic punctuation, which keeps `eAIGroupFoo` and `HCeAIGroup` out.
_GROUP = re.compile(r'(?:^|[<,])(?:ref|autoptr)?eAIGroup(?=$|[>,])')
_AGENT = re.compile(r'(?:^|[<,])(?:ref|autoptr)?eAIBase(?=$|[>,])')
_RAW_SLOT = re.compile(r'\bm_Group\b')
EXPANSION_AI_ROOT = 'mods/HollowCountryExpansionAI/'


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
            elif _AGENT.search(member.type):
                kind = 'eAIBase'
            if not kind:
                continue
            symbol = definition.name + '.' + member.name
            handle = 'HCXAIGroupHold and read it through HCHold*'
            if kind == 'eAIBase':
                handle = 'HCXAIAgentHold and read it through HCXExpansionBridge.HCAgent'
            yield HandleFinding(RULE, source.rel, member.offset, symbol,
                                f'{symbol}: {member.type} stores {kind} outside the bridge; keep a {handle}',
                                f'{symbol}:{member.type}')
    if source.rel.startswith(EXPANSION_AI_ROOT):
        for match in _RAW_SLOT.finditer(source.code):
            yield HandleFinding(RULE, source.rel, match.start(), 'm_Group',
                                'raw provider m_Group outside the bridge file; use patrol.HCGroupHold() '
                                'with HCXExpansionBridge.HCHold* (HCHasGroup for slot presence)',
                                'm_Group:' + source.line_text(match.start())[:80])
