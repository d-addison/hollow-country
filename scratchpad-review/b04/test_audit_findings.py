"""Synthetic source reproductions. Expected RED; never native engine evidence."""
from pathlib import Path
import re
import sys
from types import SimpleNamespace as NS
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests/unit'))
from test_infected_contract import policy_functions, SOURCE
from test_infected_defaults import authored


class Array(list):
    def Count(self): return len(self)
    def Insert(self, value): self.append(value)
    def Remove(self, index): self.pop(index)
    def RemoveItem(self, value):
        if value in self: self.remove(value)
    def Find(self, value): return self.index(value) if value in self else -1


def release_method(context, pending):
    """Translate only the authored Release body; fail on unsupported syntax."""
    source = (SOURCE / 'HCInfectedNavigation.c').read_text()
    body = source.split('    bool Release()\n    {', 1)[1].split('\n    }\n}', 1)[0]
    body = re.sub(r'//[^\n]*', '', body)
    body = re.sub(r'Print\("[^"\n]*"\);', '', body)  # logging has no state effect
    body = re.sub(r'if (\([^\n]+\))\s*([^{};\n]+;)', r'if \1 {\2}', body)
    body = re.sub(r'for \(int (\w+) = ([^;]+); \1 >= 0; \1--\)', r'for \1 in range(\2, -1, -1)', body)
    body = re.sub(r'new array<ref BehaviourGroupInfectedPackWaypointParams>', 'Array()', body)
    body = re.sub(r'ref array<ref BehaviourGroupInfectedPackWaypointParams> ', '', body)
    body = re.sub(r'\bnew (\w+)\(', r'\1(', body)
    lines, indent = ['def run(self):'], 1
    for token in re.split(r'([{};])', body):
        token = token.strip()
        if not token or token == ';': continue
        if token == '{': indent += 1; continue
        if token == '}': indent -= 1; continue
        token = re.sub(r'\b(?:int|ZombieBase|AIWorld|AIGroup|AIAgent|BehaviourGroupInfectedPack)\s+', '', token)
        token = re.sub(r'\b(m_\w+|Group|RouteResult)\b', r'self.\1', token)
        token = re.sub(r'(?<![.\w])GetAIWorld\(', 'self.GetAIWorld(', token)
        token = re.sub(r'\b(self\.m_\w+)\+\+', r'\1 += 1', token)
        token = token.replace('&&', ' and ').replace('||', ' or ')
        token = re.sub(r'!(?!=)', 'not ', token)
        for a, b in [('true','True'), ('false','False'), ('null','None'), ('this','self')]:
            token = re.sub(r'\b'+a+r'\b', b, token)
        if token.startswith('if ('): token = 'if '+token[4:-1]+':'
        elif token.startswith('for '): token += ':'
        lines.append('    '*indent+token)
    scope = dict(Array=Array, s_PendingRelease=pending, Print=lambda *args: None,
                 BehaviourGroupInfectedPack=NS(Cast=lambda x: None),
                 BehaviourGroupInfectedPackWaypointParams=lambda *args: NS(),
                 HCInfectedClock=NS(UtcSeconds=lambda: 100),
                 HCInfectedPolicy=NS(**policy_functions()))
    exec(compile('\n'.join(lines), 'HCInfectedNavigation.c:329 [synthetic translation]', 'exec'), scope)
    return scope['run'](context)


class AuditFindings(unittest.TestCase):
    def test_stalker_and_heavy_maps_do_not_admit_unavailable_physical_variants(self):
        result = authored('HCInfectedProfiles.c', 'static bool ValidateMap(', NS(),
                          configured=Array([3, 4, 0, 1]), enabled=True,
                          HCInfectedPolicy=NS(**policy_functions()))
        self.assertFalse(result,
                         'Requested stalker/heavy map must not count as available without a capability disposition')

    def test_release_does_not_forget_member_after_failed_fallback_add(self):
        agent = NS()
        group = NS(GetBehaviour=lambda: None, RemoveAgent=lambda _: setattr(agent, 'group', None))
        agent.group = group
        agent.GetGroup = lambda: agent.group
        member = NS(GetAIAgent=lambda: agent)
        fallback = NS(AddAgent=lambda _: None)  # explicit injected failure
        context = NS(Group=group, RouteResult=1, m_Releasing=False,
                     m_Members=Array([member]), m_ReleaseAttempts=0, m_NextReleaseUtc=0,
                     GetAIWorld=lambda: NS(CreateDefaultGroup=lambda: fallback))
        pending = Array()
        self.assertFalse(release_method(context, pending))
        self.assertIsNone(agent.group)
        self.assertEqual([member], context.m_Members)
        self.assertFalse(release_method(context, pending),
                         'Unverified fallback add must remain unresolved, not report release success')

    def test_retained_auditory_candidate_is_not_a_confirmed_visual_observation(self):
        source = (SOURCE / 'HCInfectedNavigation.c').read_text()
        self.assertIn('HCInfectedPolicy.DirectlyObserved(true,', source)
        # Explicit synthetic auditory-only retained candidate, within FOV and
        # both ray geometries, with no fresh native visual-perception evidence.
        self.assertFalse(policy_functions()['DirectlyObserved'](True, 100, .8, True, True),
                         'Geometry plus retained target cannot establish lighting-aware native sight')


if __name__ == '__main__': unittest.main(verbosity=2)
