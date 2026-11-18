"""Synthetic config/native-array ports, executing the authored AI budget."""
from types import SimpleNamespace as N
from tests.unit.test_ai_limits import LIMITS, authored
from tests.unit.test_map_layers import EStr, translate
from tests.unit.test_group_server import EArray


def install(env, **overrides):
    cfg, api, local, logs = authored()
    vars(cfg).update(overrides)
    api.GroupSize = lambda seed, row, kind: local['GroupSize'](seed, EStr(row), EStr(kind))
    env['HCAILimits'] = api
    budget = N(s_Rows=EArray(), s_Blocked=False)
    ports = dict(HCAILimits=api, HCAIBudget=budget, HCAIReservation=N,
                 Print=env.get('Print', logs.append))
    source = LIMITS.read_text().replace('s_Rows', 'HCAIBudget.s_Rows').replace('s_Blocked', 'HCAIBudget.s_Blocked')
    translate(source, 'HCAIBudget', ports, budget)
    for key in ('Actors','Groups','Fits','TryReserve','Restore','Release','Block'):
        setattr(budget, key, ports[key])
    env['HCAIBudget'] = budget
    return cfg
