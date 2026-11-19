"""Offline port of the shared core-tick work budget (wave 13, issue #138).

Translates the AUTHORED Core/HCUnitBudget.c methods and the authored HCServer.HCTickWork accessor with
the repo's syntax-only translator, so module harnesses can be handed the same budget object HCServer
would own. Everything here is a synthetic offline port: no DayZ timing or engine behaviour is claimed.
"""
import functools
from pathlib import Path
import re
from types import SimpleNamespace as N

from tests.unit.test_hc_unit_budget import translated

SCRIPTS = Path(__file__).resolve().parents[2] / "mods/HollowCountry/scripts"
BUDGET = SCRIPTS / "4_World/Core/HCUnitBudget.c"
SERVER = SCRIPTS / "4_World/Core/HCServer.c"

_FIELDS = ("m_Limit", "m_Used", "m_Items", "m_Served", "m_Starved", "m_WindowUsedMax", "m_WindowStarved",
           "m_WindowTicks", "m_WindowIndex", "m_WindowElapsed")


def constants():
    return {m[1]: int(m[2]) for m in re.finditer(r"static const int (\w+) = (\d+);", BUDGET.read_text())}


def budget_methods():
    text = BUDGET.read_text()
    return [m[1] for m in re.finditer(r"^    (?:bool|int|void|string|float) (\w+)\(", text, re.M)]


class _Store:
    s_IdleWork = None


def new_budget():
    """A fresh transpiled HCUnitBudget instance (members zeroed like the Enforce constructor)."""
    text = BUDGET.read_text()
    budget = N(**{name: 0 for name in _FIELDS})
    for name in budget_methods():
        fn = translated(text, name, {}, "HCUnitBudget", integer_division=True)
        setattr(budget, name, functools.partial(fn, budget))
    return budget


class _BudgetClass:
    """Static side of HCUnitBudget: its constants, and `new HCUnitBudget()`."""

    def __call__(self):
        return new_budget()


def budget_class():
    klass = _BudgetClass()
    vars(klass).update(constants())
    return klass


def tick_work_accessor(state, klass):
    """The authored static HCServer.HCTickWork(), bound to a state object (s_Instance)."""
    # The idle budget is a static of HCServer; the translator cannot assign globals, so it lives on `store`.
    text = SERVER.read_text().replace("s_IdleWork", "store.s_IdleWork")
    env = {"s_Instance": state, "HCUnitBudget": klass, "store": _Store()}
    return translated(text, "HCTickWork", env, "HCServer", member=False)


def install(env, state=None, klass=None):
    """Add HCUnitBudget and HCServer.HCTickWork to a module-harness env (existing HCServer.Get kept).

    With no state the accessor sees no HCServer instance, i.e. the idle (never refusing) budget.
    """
    klass = klass or budget_class()
    holder = state if state is not None else None
    accessor = tick_work_accessor(holder, klass)
    server = env.get("HCServer")
    if server is None:
        server = N()
        env["HCServer"] = server
    server.HCTickWork = accessor
    env["HCUnitBudget"] = klass
    return klass
