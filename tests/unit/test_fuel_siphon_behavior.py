"""#53 fuel siphon: execute the authored action control flow (review finding F4).

HCFuelSiphon.c is translated mechanically, token by token, into Python by a small
Enforce-subset translator (classes, fields, methods, if/else, bounded for,
locals, calls, && || ! comparisons, + - * /, new T()). Unsupported constructs are
refused, never hand-reimplemented. Float arithmetic, float parameters and float
assignments are rounded to binary32 with the same f32 helper as authored_policy.
The scalar policy is the real HCFuelTransferPolicy.c through authored_policy().

Everything native is an explicitly SYNTHETIC fake below (CarScript tank, ItemBase
vessel, Liquid, GetGame, HCCraftingGate, FileExist, player). These tests prove
authored control flow only. They are not Enforce compilation, not DayZ behavior
and not runtime acceptance; local-server acceptance stays pending.
"""
import itertools
import keyword
import math
from pathlib import Path
import random
import re
import types
import unittest
from fractions import Fraction

try:
    from . import test_fuel_transfer as transfer
except ImportError:
    import test_fuel_transfer as transfer

ROOT = Path(__file__).resolve().parents[2]
ACTION = ROOT / "mods/HollowCountry/scripts/4_World/Actions/HCFuelSiphon.c"
MARKER = "$profile:HollowCountry/acceptance/fuel_siphon.enable"
f32 = transfer.f32

# --------------------------------------------------------------------------
# Enforce-subset translator
# --------------------------------------------------------------------------
TOKEN = re.compile(
    r'''(?P<ws>\s+|//[^\n]*|/\*.*?\*/)
      |(?P<str>"(?:\\.|[^"\\])*")
      |(?P<num>\d+\.\d*(?:[eE][-+]?\d+)?|\.\d+|\d+)
      |(?P<id>[A-Za-z_]\w*)
      |(?P<op>\+\+|--|\+=|-=|\*=|/=|&&|\|\||==|!=|<=|>=|[{}()\[\];,.<>=+\-*/!%:|&?])''',
    re.S | re.X)
MODIFIERS = {"static", "override", "protected", "private", "const"}
TYPES = {"void", "float", "int", "bool", "string", "vector"}
LOOP_BOUND = 100000


class Unsupported(AssertionError):
    pass


def tokenize(text):
    out, pos = [], 0
    while pos < len(text):
        match = TOKEN.match(text, pos)
        if not match:
            raise Unsupported("unsupported character: " + repr(text[pos:pos + 12]))
        pos = match.end()
        if match.lastgroup != "ws":
            out.append((match.lastgroup, match.group()))
    return out


class Translator:
    """Authored Enforce subset to Python source; refuses anything else."""

    def __init__(self, text, natives):
        self.toks = tokenize(text)
        self.pos = 0
        self.natives = set(natives)
        self.native_objs = natives if isinstance(natives, dict) else {}
        self.classes = {}
        self.loops = 0

    # token helpers
    def peek(self, k=0):
        index = self.pos + k
        return self.toks[index] if index < len(self.toks) else ("eof", "")

    def take(self, expect=None):
        tok = self.peek()
        if tok[0] == "eof" or (expect is not None and tok[1] != expect):
            raise Unsupported("expected %r, found %r" % (expect, tok[1]))
        self.pos += 1
        return tok[1]

    def ident(self):
        tok = self.peek()
        if tok[0] != "id" or keyword.iskeyword(tok[1]):
            raise Unsupported("unsupported identifier: " + tok[1])
        self.pos += 1
        return tok[1]

    def skip_block(self):
        self.take("{")
        depth = 1
        while depth:
            tok = self.take()
            depth += {"{": 1, "}": -1}.get(tok, 0)

    # declarations
    def scan(self):
        """First pass: every class, its fields and methods (bodies by token span)."""
        while self.peek()[0] != "eof":
            modded = False
            while self.peek()[1] == "modded":
                self.take()
                modded = True
            self.take("class")
            name = self.ident()
            base = None
            if self.peek()[1] in ("extends", ":"):
                self.take()
                base = self.ident()
            if modded:
                if base is not None:
                    raise Unsupported("modded class with a base: " + name)
                base = name       # a modded class extends the native class of the same name
            cls = {"name": name, "base": base, "fields": {}, "methods": {}, "order": []}
            self.classes[name] = cls
            self.take("{")
            while self.peek()[1] != "}":
                self.scan_member(cls)
            self.take("}")
            if self.peek()[1] == ";":
                self.take()

    def scan_member(self, cls):
        mods = set()
        while self.peek()[1] in MODIFIERS:
            mods.add(self.take())
        rtype = self.ident()
        if self.peek()[1] in ("<", "["):
            raise Unsupported("unsupported generic or array type")
        name = self.ident()
        if self.peek()[1] != "(":
            default = None
            if self.peek()[1] == "=":
                self.take()
                start = self.pos
                while self.peek()[1] != ";":
                    self.take()
                default = (start, self.pos)
            self.take(";")
            cls["fields"][name] = {"type": rtype, "static": "static" in mods or "const" in mods,
                                   "default": default}
            return
        self.take("(")
        params = []
        while self.peek()[1] != ")":
            ptype = self.ident()
            pname = self.ident()
            if self.peek()[1] == "=":
                raise Unsupported("unsupported default parameter: " + name)
            params.append((ptype, pname))
            if self.peek()[1] == ",":
                self.take()
        self.take(")")
        start = self.pos
        self.skip_block()
        ctor = name == cls["name"]
        cls["methods"][name] = {"type": rtype, "params": params, "static": "static" in mods,
                                "span": (start, self.pos), "ctor": ctor}
        cls["order"].append(name)

    # python emission
    def emit(self, select):
        self.scan()
        lines = []
        for cname, only in select.items():
            cls = self.classes[cname]
            if cls["base"] is not None and cls["base"] not in self.natives:
                raise Unsupported("unknown base class " + cls["base"])
            lines += self.emit_class(cls, only)
        return "\n".join(lines) + "\n"

    def zero(self, ftype):
        return {"float": "0.0", "int": "0", "bool": "False", "string": "''"}.get(ftype, "None")

    def emit_class(self, cls, only):
        base = cls["base"] or "object"
        out = ["class %s(%s):" % (cls["name"], base)]
        ctx = {"cls": cls}
        for fname, field in cls["fields"].items():
            if field["static"]:
                if field["default"]:
                    self.pos = field["default"][0]
                    value = self.expr(dict(ctx, locals={}, static=True))
                else:
                    value = self.zero(field["type"])
                out.append("    %s = %s" % (fname, value))
        out.append("    def _hc_zero_fields(self):")
        out.append("        pass")
        for fname, field in cls["fields"].items():
            if not field["static"]:
                out.append("        self.%s = %s" % (fname, self.zero(field["type"])))
        wanted = [n for n in cls["order"] if only is None or n in only]
        if not any(cls["methods"][n]["ctor"] for n in wanted):
            out += ["    def __init__(self, *args):", "        self._hc_zero_fields()"]
        for name in wanted:
            out += self.emit_method(cls, name)
        return out

    def emit_method(self, cls, name):
        method = cls["methods"][name]
        params = [p for _, p in method["params"]]
        locals_ = {p: t for t, p in method["params"]}
        header = "__init__" if method["ctor"] else name
        out = []
        if method["static"]:
            out.append("    @staticmethod")
            out.append("    def %s(%s):" % (header, ", ".join(params)))
        else:
            out.append("    def %s(%s):" % (header, ", ".join(["self"] + params)))
        if method["ctor"]:
            out.append("        self._hc_zero_fields()")
        for ptype, pname in method["params"]:
            if keyword.iskeyword(pname):
                raise Unsupported("keyword parameter " + pname)
            if ptype == "float":
                out.append("        %s = f32(%s)" % (pname, pname))
        ctx = {"cls": cls, "locals": locals_, "static": method["static"],
               "rtype": "void" if method["ctor"] else method["type"], "in_for": False}
        self.pos = method["span"][0]
        self.take("{")
        before = len(out)
        while self.peek()[1] != "}":
            out += self.statement(ctx, 2)
        self.take("}")
        if len(out) == before:
            out.append("        pass")
        return out

    # statements
    def body(self, ctx, level):
        if self.peek()[1] == "{":
            self.take("{")
            out = []
            while self.peek()[1] != "}":
                out += self.statement(ctx, level)
            self.take("}")
        else:
            out = self.statement(ctx, level)
        return out or ["    " * level + "pass"]

    def statement(self, ctx, level):
        pad = "    " * level
        tok = self.peek()
        if tok[1] == "{":
            return self.body(ctx, level)
        if tok[1] == "if":
            self.take()
            self.take("(")
            cond = self.expr(ctx)
            self.take(")")
            out = [pad + "if %s:" % cond] + self.body(ctx, level + 1)
            if self.peek()[1] == "else":
                self.take()
                out += [pad + "else:"] + self.body(ctx, level + 1)
            return out
        if tok[1] == "for":
            return self.for_statement(ctx, level)
        if tok[1] in ("while", "do", "switch", "foreach", "continue", "auto", "ref", "delete"):
            raise Unsupported("unsupported statement: " + tok[1])
        if tok[1] == "break":
            self.take()
            self.take(";")
            return [pad + "break"]
        if tok[1] == "return":
            self.take()
            if self.peek()[1] == ";":
                self.take()
                return [pad + "return"]
            value = self.expr(ctx)
            self.take(";")
            if ctx["rtype"] == "float":
                value = "f32(%s)" % value
            return [pad + "return " + value]
        out = self.simple(ctx, pad)
        self.take(";")
        return out

    def simple(self, ctx, pad):
        a, b, c = self.peek(), self.peek(1), self.peek(2)
        if a[0] == "id" and b[0] == "id" and c[1] in ("=", ";") and a[1] != "new":
            rtype, name = self.ident(), self.ident()
            if name in ctx["locals"] or name in ctx["cls"]["fields"] and False:
                raise Unsupported("redeclared local " + name)
            if keyword.iskeyword(name) or name in self.natives:
                raise Unsupported("unsupported local name " + name)
            ctx["locals"][name] = rtype
            if self.peek()[1] == "=":
                self.take()
                value = self.expr(ctx)
                if rtype == "float":
                    value = "f32(%s)" % value
                return [pad + "%s = %s" % (name, value)]
            return [pad + "%s = %s" % (name, self.zero(rtype))]
        if a[0] == "id" and b[1] in ("=", "+=", "-=", "*=", "/=", "++", "--"):
            target, ttype = self.resolve_target(ctx, self.ident())
            op = self.take()
            if op in ("++", "--"):
                return [pad + "%s %s= 1" % (target, op[0])]
            value = self.expr(ctx)
            if op != "=":
                value = "(%s %s %s)" % (target, op[0], value)
            if ttype == "float" or op != "=":
                value = "f32(%s)" % value
            return [pad + "%s = %s" % (target, value)]
        start = self.pos
        text = self.expr(ctx)
        if self.toks[self.pos - 1][1] != ")" or self.toks[start][0] != "id":
            raise Unsupported("unsupported expression statement")
        return [pad + text]

    def for_statement(self, ctx, level):
        pad = "    " * level
        self.take("for")
        self.take("(")
        init = self.simple(ctx, "")
        self.take(";")
        cond = self.expr(ctx)
        self.take(";")
        step = self.simple(ctx, "")
        self.take(")")
        self.loops += 1
        guard = "_hc_n%d" % self.loops
        sub = dict(ctx, in_for=True)
        body = self.body(sub, level + 1)
        out = [pad + line for line in init]
        out += [pad + "%s = 0" % guard, pad + "while %s:" % cond,
                pad + "    %s += 1" % guard,
                pad + "    if %s > %d: raise AssertionError('loop bound')" % (guard, LOOP_BOUND)]
        out += body
        out += [pad + "    " + line for line in step]
        return out

    # expressions
    def resolve_target(self, ctx, name):
        if keyword.iskeyword(name):
            raise Unsupported("keyword " + name)
        if name in ctx["locals"]:
            return name, ctx["locals"][name]
        field = ctx["cls"]["fields"].get(name)
        if field is None:
            raise Unsupported("assignment to unknown name " + name)
        if field["static"]:
            return "%s.%s" % (ctx["cls"]["name"], name), field["type"]
        if ctx["static"]:
            raise Unsupported("instance field in static method: " + name)
        return "self." + name, field["type"]

    def expr(self, ctx):
        return self.or_expr(ctx)

    def binary(self, ctx, sub, ops, fmt):
        left = sub(ctx)
        while self.peek()[1] in ops:
            op = self.take()
            left = fmt(left, op, sub(ctx))
        return left

    def or_expr(self, ctx):
        return self.binary(ctx, self.and_expr, ("||",), lambda a, o, b: "bool(%s or %s)" % (a, b))

    def and_expr(self, ctx):
        return self.binary(ctx, self.eq_expr, ("&&",), lambda a, o, b: "bool(%s and %s)" % (a, b))

    def eq_expr(self, ctx):
        return self.binary(ctx, self.rel_expr, ("==", "!="), lambda a, o, b: "(%s %s %s)" % (a, o, b))

    def rel_expr(self, ctx):
        return self.binary(ctx, self.add_expr, ("<", ">", "<=", ">="), lambda a, o, b: "(%s %s %s)" % (a, o, b))

    def add_expr(self, ctx):
        return self.binary(ctx, self.mul_expr, ("+", "-"), self.arith)

    def mul_expr(self, ctx):
        return self.binary(ctx, self.unary, ("*", "/"), self.arith)

    def arith(self, left, op, right):
        if left.startswith(("'", '"')) or right.startswith(("'", '"')):
            raise Unsupported("string arithmetic is not translated")
        return "f32(%s %s %s)" % (left, op, right)

    def unary(self, ctx):
        if self.peek()[1] == "!":
            self.take()
            return "(not %s)" % self.unary(ctx)
        if self.peek()[1] == "-":
            self.take()
            return "(-%s)" % self.unary(ctx)
        return self.postfix(ctx)

    def postfix(self, ctx):
        text = self.primary(ctx)
        while self.peek()[1] in (".", "("):
            if self.take() == ".":
                text += "." + self.ident()
            else:
                text += "(%s)" % self.args(ctx)
        if self.peek()[1] in ("[", "?", ":"):
            raise Unsupported("unsupported operator " + self.peek()[1])
        return text

    def args(self, ctx):
        args = []
        while self.peek()[1] != ")":
            args.append(self.expr(ctx))
            if self.peek()[1] == ",":
                self.take()
        self.take(")")
        return ", ".join(args)

    def primary(self, ctx):
        tok = self.peek()
        kind, text = tok
        if kind == "num":
            self.take()
            if "." in text or "e" in text.lower():
                return repr(f32(float(text)))
            return text
        if kind == "str":
            self.take()
            return text
        if text == "(":
            self.take()
            inner = self.expr(ctx)
            self.take(")")
            return "(%s)" % inner
        if text == "new":
            self.take()
            name = self.ident()
            if name not in self.natives and name not in self.classes:
                raise Unsupported("unknown type in new: " + name)
            if self.peek()[1] == "(":
                self.take()
                return "%s(%s)" % (name, self.args(ctx))
            return "%s()" % name
        if kind != "id":
            raise Unsupported("unsupported token " + text)
        name = self.ident()
        if name in ("true", "false", "null", "NULL"):
            return {"true": "True", "false": "False"}.get(name, "None")
        if name == "this":
            raise Unsupported("unsupported this")
        if name == "super":
            if self.peek()[1] != "." or ctx["static"]:
                raise Unsupported("unsupported super use")
            self.take(".")
            member = self.ident()
            base = self.native_objs.get(ctx["cls"]["base"])
            if self.peek()[1] != "(" or base is None or not callable(getattr(base, member, None)):
                raise Unsupported("unsupported super member " + member)
            return "super().%s" % member
        call = self.peek()[1] == "("
        if name in ctx["locals"]:
            return name
        cls = ctx["cls"]
        if call and name in cls["methods"]:
            owner = "%s" % cls["name"] if cls["methods"][name]["static"] else "self"
            if owner == "self" and ctx["static"]:
                raise Unsupported("instance call in static method: " + name)
            return "%s.%s" % (owner, name)
        base = self.native_objs.get(cls["base"])
        if call and not ctx["static"] and base is not None and callable(getattr(base, name, None)):
            return "self." + name          # inherited native method (fake base class)
        if not call and name in cls["fields"]:
            return self.resolve_target(ctx, name)[0]
        if name in self.natives or name in self.classes:
            return name
        raise Unsupported("unknown native or name: " + name)


_TRANSLATED = {}


def translate(path, select, natives):
    text = Path(path).read_text()
    key = (text, repr(sorted((k, sorted(v) if v else v) for k, v in select.items())))
    if key not in _TRANSLATED:      # translation is pure in (source, selection, native names)
        _TRANSLATED[key] = Translator(text, natives).emit(select)
    return _TRANSLATED[key]


# --------------------------------------------------------------------------
# Explicitly synthetic fake natives
# --------------------------------------------------------------------------
class UnitObject:
    pass


class CarFluid:
    FUEL = "FUEL"


class UAQuantityConsumed:
    FUEL = 500.0   # synthetic ml per second, not the engine balance value


class CAContinuousBase:
    def __init__(self, *args):
        self.completed = 0

    def OnCompletePogress(self, action_data):
        self.completed = getattr(self, "completed", 0) + 1


class TStringArray(list):
    def Count(self):
        return len(self)

    def Get(self, index):
        return self[index]

    def Insert(self, value):
        self.append(value)


class Math:
    @staticmethod
    def Min(a, b):
        return min(a, b)


class vector:
    @staticmethod
    def DistanceSq(a, b):
        return f32(sum(f32((x - y) * (x - y)) for x, y in zip(a, b)))


class ItemBase(UnitObject):
    """Synthetic held vessel; quantity in ml, max as int like the native."""

    def __init__(self, quantity=0.0, maximum=5000, liquid=1, coef=1.0):
        self.quantity, self.maximum, self.liquid, self.coef = f32(quantity), maximum, liquid, coef
        self.destroyed, self.container = False, True

    def GetQuantity(self):
        return self.quantity

    def GetQuantityMax(self):
        return self.maximum

    def GetLiquidType(self):
        return self.liquid

    def IsLiquidContainer(self):
        return self.container

    def IsDamageDestroyed(self):
        return self.destroyed

    def GetLiquidThroughputCoef(self):
        return self.coef


class CarScript(UnitObject):
    """Synthetic car: dyadic default so binary32 readbacks are exact."""

    def __init__(self, capacity=64.0, liters=16.0):
        self.capacity, self.liters = f32(capacity), f32(liters)
        self.destroyed, self.engine, self.moving = False, False, False
        self.reach, self.refill = 2.0, (0.0, 0.0, 0.0)
        self.comp, self.selections = "fuel_comp", ["body", "fuel_comp"]
        self.coef, self.leak_mode, self.leaks = 1.0, "normal", []

    @staticmethod
    def Cast(obj):
        return obj if isinstance(obj, CarScript) else None

    def GetFluidCapacity(self, fluid):
        assert fluid is CarFluid.FUEL
        return self.capacity

    def GetFluidFraction(self, fluid):
        assert fluid is CarFluid.FUEL
        return f32(self.liters / self.capacity)

    def Leak(self, fluid, amount):
        assert fluid is CarFluid.FUEL
        self.leaks.append(amount)
        factor = {"normal": 1.0, "noop": 0.0, "half": 0.5, "double": 2.0}[self.leak_mode]
        self.liters = max(0.0, f32(self.liters - f32(amount * factor)))

    def IsDamageDestroyed(self):
        return self.destroyed

    def EngineIsOn(self):
        return self.engine

    def IsMoving(self):
        return self.moving

    def GetActionDistanceFuel(self):
        return self.reach

    def GetRefillPointPosWS(self):
        return self.refill

    def GetActionCompNameFuel(self):
        return self.comp

    def GetActionComponentNameList(self, index, names):
        names.extend(self.selections)

    def GetLiquidThroughputCoef(self):
        return self.coef


class ActionFillFuel:
    """Native refuel action: the decoy a wrong registration would name."""


class Bottle_Base:
    def __init__(self):
        self.actions = []

    def SetActions(self):
        self.actions = ["native"]

    def AddAction(self, action_class):
        self.actions.append(action_class)


class ActionConstructor:
    def RegisterActions(self, actions):
        actions.Insert("native")


class ActionTarget:
    def __init__(self, obj, index=0):
        self.obj, self.index = obj, index

    def GetObject(self):
        return self.obj

    def GetComponentIndex(self):
        return self.index


class PlayerBase:
    def __init__(self, hands=None):
        self.hands, self.vehicle, self.pos, self.delta = hands, False, (1.0, 0.0, 0.0), 0.5

    def GetItemInHands(self):
        return self.hands

    def IsInVehicle(self):
        return self.vehicle

    def GetPosition(self):
        return self.pos

    def GetDeltaT(self):
        return self.delta


class ActionData:
    def __init__(self, player, target, item):
        self.m_Player, self.m_Target, self.m_MainItem = player, target, item


class World:
    """One synthetic server process: natives, translated classes, scenario objects."""

    def __init__(self, server=True, gate=True, marker=True, liters=16.0, capacity=64.0,
                 quantity=0.0, maximum=5000, rate=500.0, step_seconds=0.5, delta=0.5,
                 action=None, policy=None):
        self.server, self.gate, self.marker = server, gate, marker
        self.file_calls, self.prints, self.fills = [], [], []
        self.fill_mode, self.can_fill = "normal", True
        self.car = CarScript(capacity, liters)
        self.vessel = ItemBase(quantity, maximum)
        self.player = PlayerBase(self.vessel)
        self.player.delta = delta
        self.target = ActionTarget(self.car)
        self.data = ActionData(self.player, self.target, self.vessel)
        world = self

        class Game:
            def IsServer(self):
                return world.server

        class Liquid:
            @staticmethod
            def CanFillContainer(container, liquid_type, ignore_fullness_check=False):
                return world.can_fill

            @staticmethod
            def FillContainer(container, liquid_type, amount):
                world.fills.append((container, liquid_type, amount))
                gain = {"normal": amount, "none": 0.0, "double": amount * 2}[world.fill_mode]
                container.quantity = f32(min(float(container.maximum), f32(container.quantity + gain)))
                container.liquid = liquid_type

        class HCCraftingGate:
            @staticmethod
            def CanPreviewOrCraft():
                return world.gate

        def file_exist(path):
            self.file_calls.append(path)
            return self.marker and path == MARKER

        policy_ns = transfer.authored_policy() if policy is None else policy
        scalar = {n: staticmethod(f) for n, f in policy_ns.items()
                  if getattr(f, "__globals__", None) is policy_ns}
        natives = {
            "f32": f32, "GetGame": lambda: world.game, "Liquid": Liquid, "HCCraftingGate": HCCraftingGate,
            "FileExist": file_exist, "Print": self.prints.append, "CarScript": CarScript,
            "CarFluid": CarFluid, "UAQuantityConsumed": UAQuantityConsumed, "Math": Math,
            "vector": vector, "TStringArray": TStringArray, "CAContinuousBase": CAContinuousBase,
            "ItemBase": ItemBase, "PlayerBase": PlayerBase, "ActionTarget": ActionTarget,
            "LIQUID_GASOLINE": 1, "UA_PROCESSING": 2, "UA_FINISHED": 4, "UA_CANCEL": 5, "UA_ERROR": 24,
            "ActionData": ActionData, "ActionContinuousBase": object, "ActionFillFuel": ActionFillFuel,
            "Bottle_Base": Bottle_Base, "ActionConstructor": ActionConstructor,
            "HCFuelTransferPolicy": type("HCFuelTransferPolicy", (), scalar),
        }
        self.game = Game()
        select = {"HCFuelSiphonQualification": None, "HCFuelSiphon": None,
                  "CAContinuousHCSiphonFuel": None,
                  "HCActionSiphonFuelFromCar": {"ActionCondition", "ActionConditionContinue"},
                  "ActionConstructor": None, "Bottle_Base": None}
        src = translate(action or ACTION, select, natives)
        self.ns = dict(natives)
        exec(compile(src, "HCFuelSiphon.c(translated)", "exec"), self.ns)
        self.Siphon = self.ns["HCFuelSiphon"]
        self.Qual = self.ns["HCFuelSiphonQualification"]
        self.rate, self.step_seconds = rate, step_seconds

    def component(self, setup=True):
        comp = self.ns["CAContinuousHCSiphonFuel"](self.rate, self.step_seconds)
        if setup:
            comp.Setup(self.data)
        return comp

    def action(self):
        return self.ns["HCActionSiphonFuelFromCar"]()

    def snapshot(self):
        return (self.car.liters, self.vessel.quantity, self.vessel.liquid,
                len(self.car.leaks), len(self.fills))

    def run(self, comp, limit=400):
        results = []
        for _ in range(limit):
            results.append(comp.Execute(self.data))
            if results[-1] != 2:
                return results
        raise AssertionError("session did not end")


def calls(world):
    return len(world.car.leaks), len(world.fills)


class BehaviorCase(unittest.TestCase):
    def world(self, **kw):
        return World(**kw)


# --------------------------------------------------------------------------
# Translator guard rails
# --------------------------------------------------------------------------
class TranslatorTests(unittest.TestCase):
    def test_unsupported_constructs_are_refused_not_guessed(self):
        base = "class Probe\n{\n    static float Run(float a)\n    {\n%s\n    }\n}\n"
        refused = ("while (a > 0) { a = a - 1; }", "return a ? 1 : 0;", "float b = a[0];",
                   "foreach (float b : a) { }", "return super.Run(a);", "return Unknown(a);",
                   "string s = \"x\" + a;", "switch (a) { }", "return a;;;", "int i = 0; for (i = 0; i < 2; i++) { continue; }")
        for statement in refused:
            with self.subTest(statement=statement):
                with self.assertRaises(Unsupported):
                    Translator(base % statement, set()).emit({"Probe": None})

    def test_float_arithmetic_is_rounded_to_binary32(self):
        src = "class Probe\n{\n    static float Run(float a, float b)\n    {\n        return a * b + 0.1;\n    }\n}\n"
        ns = {"f32": f32}
        exec(Translator(src, {"f32"}).emit({"Probe": None}), ns)
        self.assertEqual(f32(f32(f32(0.1) * f32(0.1)) + f32(0.1)), ns["Probe"].Run(0.1, 0.1))

    def test_production_file_translates_and_world_builds(self):
        world = World()
        self.assertTrue(callable(world.Siphon.Allowed))


# --------------------------------------------------------------------------
# HCFuelSiphonQualification / ServerEnabled
# --------------------------------------------------------------------------
class AdmissionTests(BehaviorCase):
    def test_fuel_admission_defaults_closed_without_the_marker(self):
        world = self.world(marker=False)
        self.assertFalse(world.Qual.Qualified())
        self.assertFalse(world.Qual.Admitted())
        self.assertIn("not admitted", " ".join(world.prints))

    def test_marker_opts_in_and_is_logged_experimental(self):
        world = self.world(marker=True)
        self.assertTrue(world.Qual.Admitted())
        self.assertEqual([MARKER], world.file_calls)
        self.assertEqual(1, len(world.prints))
        self.assertIn("EXPERIMENTAL", world.prints[0])
        self.assertIn("PENDING", world.prints[0])

    def test_marker_is_probed_once_per_process_whatever_it_answers(self):
        for marker in (False, True):
            with self.subTest(marker=marker):
                world = self.world(marker=marker)
                answers = [world.Qual.Admitted() for _ in range(6)]
                self.assertEqual([marker] * 6, answers)
                self.assertEqual([MARKER], world.file_calls)
                self.assertEqual(1, len(world.prints))
                world.marker = not marker          # a later file change is ignored
                self.assertEqual(marker, world.Qual.Admitted())
                self.assertEqual([MARKER], world.file_calls)

    def test_server_gate_truth_table(self):
        for server, gate, marker in itertools.product((False, True), repeat=3):
            with self.subTest(server=server, gate=gate, marker=marker):
                world = self.world(server=server, gate=gate, marker=marker)
                self.assertEqual(server and gate and marker, world.Siphon.ServerEnabled())

    def test_missing_game_is_closed(self):
        world = self.world()
        world.ns["GetGame"] = lambda: None
        self.assertFalse(world.Siphon.ServerEnabled())

    def test_client_never_probes_the_marker_or_the_gate(self):
        world = self.world(server=False)
        self.assertFalse(world.Siphon.ServerEnabled())
        self.assertEqual([], world.file_calls)


# --------------------------------------------------------------------------
# TankLiters / Allowed / ActionCondition
# --------------------------------------------------------------------------
class EligibilityTests(BehaviorCase):
    def allowed(self, world):
        return world.Siphon.Allowed(world.player, world.target, world.vessel)

    def test_tank_liters_is_capacity_times_fraction_in_binary32(self):
        world = self.world(capacity=60.0, liters=7.3)
        expect = f32(f32(60.0) * f32(f32(7.3) / f32(60.0)))
        self.assertEqual(expect, world.Siphon.TankLiters(world.car))
        self.assertEqual(0, world.Siphon.TankLiters(None))

    def test_baseline_is_allowed(self):
        self.assertTrue(self.allowed(self.world()))

    def test_each_single_failure_refuses(self):
        def no_container(w): w.vessel.container = False
        def other_liquid(w): w.vessel.quantity, w.vessel.liquid = 100.0, 7
        cases = {
            "in vehicle": lambda w: setattr(w.player, "vehicle", True),
            "not in hands": lambda w: setattr(w.player, "hands", ItemBase()),
            "empty hands": lambda w: setattr(w.player, "hands", None),
            "car destroyed": lambda w: setattr(w.car, "destroyed", True),
            "engine on": lambda w: setattr(w.car, "engine", True),
            "moving": lambda w: setattr(w.car, "moving", True),
            "tank empty": lambda w: setattr(w.car, "liters", 0.0),
            "not container": no_container,
            "vessel destroyed": lambda w: setattr(w.vessel, "destroyed", True),
            "vessel full": lambda w: setattr(w.vessel, "quantity", 5000.0),
            "other liquid": other_liquid,
            "cannot fill": lambda w: setattr(w, "can_fill", False),
            "out of reach": lambda w: setattr(w.player, "pos", (5.0, 0.0, 0.0)),
            "wrong selection": lambda w: setattr(w.car, "selections", ["body", "wheel"]),
            "no selection": lambda w: setattr(w.car, "selections", []),
            "not a car": lambda w: setattr(w.target, "obj", UnitObject()),
            "no object": lambda w: setattr(w.target, "obj", None),
        }
        for label, mutate in cases.items():
            with self.subTest(label):
                world = self.world()
                mutate(world)
                self.assertFalse(self.allowed(world))

    def test_null_arguments_refuse(self):
        world = self.world()
        for args in ((None, world.target, world.vessel), (world.player, None, world.vessel),
                     (world.player, world.target, None)):
            self.assertFalse(world.Siphon.Allowed(*args))

    def test_empty_vessel_accepts_any_existing_liquid_type_and_gasoline_partial(self):
        world = self.world()
        world.vessel.liquid = 7                  # empty: type is irrelevant
        self.assertTrue(self.allowed(world))
        world.vessel.quantity, world.vessel.liquid = 100.0, 1
        self.assertTrue(self.allowed(world))     # partial gasoline accepted

    def test_reach_boundary_is_exclusive_and_squared(self):
        for dist, expected in ((1.99, True), (2.0, False), (2.01, False), (0.0, True)):
            with self.subTest(dist=dist):
                world = self.world()
                world.player.pos = (dist, 0.0, 0.0)
                self.assertEqual(expected, self.allowed(world))
        world = self.world()
        world.car.reach = 0.5                    # reach squared, not reach
        world.player.pos = (0.6, 0.0, 0.0)
        self.assertFalse(self.allowed(world))
        world.player.pos = (0.4, 0.0, 0.0)
        self.assertTrue(self.allowed(world))
        world.car.refill = (10.0, 0.0, 0.0)      # distance is to the refill point
        self.assertFalse(self.allowed(world))
        world.player.pos = (10.0, 0.0, 0.0)
        self.assertTrue(self.allowed(world))

    def test_selection_scan_is_bounded_to_32_entries(self):
        for position, expected in ((0, True), (31, True), (32, False), (60, False)):
            with self.subTest(position=position):
                world = self.world()
                names = ["x%d" % i for i in range(70)]
                names[position] = world.car.comp
                world.car.selections = names
                self.assertEqual(expected, self.allowed(world))

    def test_action_is_registered_after_super_on_the_native_registries(self):
        world = self.world()
        siphon = world.ns["HCActionSiphonFuelFromCar"]
        bottle = world.ns["Bottle_Base"]()
        bottle.SetActions()
        self.assertEqual(["native", siphon], bottle.actions)
        actions = TStringArray()               # synthetic stand-in for TTypenameArray
        world.ns["ActionConstructor"]().RegisterActions(actions)
        self.assertEqual(["native", siphon], actions)

    def test_action_condition_client_needs_allowed_only_server_needs_gate(self):
        for server, gate, marker in itertools.product((False, True), repeat=3):
            with self.subTest(server=server, gate=gate, marker=marker):
                world = self.world(server=server, gate=gate, marker=marker)
                action = world.action()
                want = (not server) or (gate and marker)
                self.assertEqual(want, action.ActionCondition(world.player, world.target, world.vessel))
                self.assertEqual(want, action.ActionConditionContinue(world.data))
                world.car.engine = True
                self.assertFalse(action.ActionCondition(world.player, world.target, world.vessel))
                self.assertFalse(action.ActionConditionContinue(world.data))


# --------------------------------------------------------------------------
# CAContinuousHCSiphonFuel
# --------------------------------------------------------------------------
class SetupTests(BehaviorCase):
    def test_setup_session_is_tank_or_free_space_and_throughput_scales_rate(self):
        world = self.world(liters=5.0, capacity=64.0, quantity=0.0, maximum=20000)
        comp = world.component()
        self.assertEqual(5000.0, comp.m_SessionMl)
        self.assertEqual(500.0, comp.m_AdjustedRate)
        world = self.world(liters=50.0, quantity=2000.0, maximum=5000)
        self.assertEqual(3000.0, world.component().m_SessionMl)
        world = self.world()
        world.vessel.coef, world.car.coef = 0.5, 0.25
        self.assertEqual(125.0, world.component().m_AdjustedRate)
        world.vessel.coef, world.car.coef = 0.25, 0.5
        self.assertEqual(125.0, world.component().m_AdjustedRate)

    def test_setup_resets_state_of_a_reused_component(self):
        world = self.world()
        comp = world.component()
        comp.m_MovedMl, comp.m_PendingMl, comp.m_Stopped, comp.m_Elapsed = 9.0, 9.0, True, 9.0
        comp.Setup(world.data)
        self.assertEqual((0, 0, False, 0), (comp.m_MovedMl, comp.m_PendingMl, comp.m_Stopped, comp.m_Elapsed))
        self.assertEqual(0, comp.m_AdjustedRate - 500.0)

    def test_setup_without_target_or_vessel_leaves_a_dead_session(self):
        for target, item in ((None, True), (True, None)):
            with self.subTest(target=target, item=item):
                world = self.world()
                world.data.m_Target = world.target if target else None
                world.data.m_MainItem = world.vessel if item else None
                comp = world.component()
                self.assertEqual(0, comp.m_SessionMl)
                self.assertEqual(4, comp.Execute(world.data))
                self.assertEqual(1, comp.GetProgress())
                self.assertEqual((0, 0), calls(world))
        world = self.world()
        world.data.m_Target = ActionTarget(UnitObject())
        self.assertEqual(0, world.component().m_SessionMl)

    def test_execute_and_cancel_without_player_are_errors_without_effect(self):
        world = self.world()
        comp = world.component()
        world.data.m_Player = None
        before = world.snapshot()
        self.assertEqual(24, comp.Execute(world.data))
        self.assertEqual(24, comp.Cancel(world.data))
        self.assertEqual(before, world.snapshot())


class ClientPredictionTests(BehaviorCase):
    def test_client_only_advances_progress_and_never_mutates(self):
        world = self.world(server=False, liters=1.0, marker=True)
        comp = world.component()
        before = world.snapshot()
        progress = []
        results = []
        for _ in range(50):
            results.append(comp.Execute(world.data))
            progress.append(comp.GetProgress())
            if results[-1] != 2:
                break
        self.assertEqual(before, world.snapshot())
        self.assertEqual((0, 0), calls(world))
        self.assertEqual([2] * (len(results) - 1) + [4], results)
        self.assertEqual(sorted(progress, reverse=True), progress)     # monotone toward -1
        self.assertEqual(-1.0, progress[-1])
        self.assertTrue(all(p <= 0 for p in progress))
        self.assertEqual(1, comp.completed)
        self.assertEqual([], world.file_calls)

    def test_client_prediction_is_capped_by_the_session(self):
        world = self.world(server=False, liters=0.3, delta=10.0)
        comp = world.component()
        self.assertEqual(300.0, comp.m_SessionMl)
        comp.Execute(world.data)
        self.assertEqual(300.0, comp.m_MovedMl)
        self.assertEqual(-1.0, comp.GetProgress())

    def test_client_cancel_flushes_prediction_only(self):
        world = self.world(server=False)
        comp = world.component()
        comp.Execute(world.data)
        before = world.snapshot()
        self.assertEqual(5, comp.Cancel(world.data))
        self.assertEqual(before, world.snapshot())
        self.assertEqual(0, comp.m_PendingMl)
        self.assertEqual(comp.Cancel(world.data), 5)
        self.assertEqual(before, world.snapshot())

    def test_client_invalid_state_is_still_not_a_mutation(self):
        world = self.world(server=False)
        comp = world.component()
        world.car.engine = True
        for _ in range(4):
            comp.Execute(world.data)
        self.assertEqual((0, 0), calls(world))


class ServerStepTests(BehaviorCase):
    def test_gate_closed_never_leaks_or_fills(self):
        for gate, marker in ((False, True), (True, False), (False, False)):
            with self.subTest(gate=gate, marker=marker):
                world = self.world(gate=gate, marker=marker)
                comp = world.component()
                before = world.snapshot()
                results = world.run(comp)
                self.assertEqual([2, 4], results)
                self.assertEqual(before, world.snapshot())
                self.assertEqual((0, 0), calls(world))
                self.assertTrue(comp.m_Stopped)
                self.assertEqual(0, comp.m_MovedMl)

    def test_each_step_is_exactly_one_leak_and_one_fill(self):
        world = self.world(liters=16.0)
        comp = world.component()
        for step in range(1, 5):
            self.assertEqual(2, comp.Execute(world.data))
            self.assertEqual((step, step), calls(world))
        self.assertEqual([0.25] * 4, world.car.leaks)              # 250 ml debit in liters
        self.assertEqual([249.0] * 4, [f[2] for f in world.fills])  # 1 ml spill per step
        self.assertTrue(all(f[0] is world.vessel and f[1] == 1 for f in world.fills))
        self.assertEqual(996.0, world.vessel.quantity)
        self.assertEqual(15.0, world.car.liters)
        self.assertEqual(996.0, comp.m_MovedMl)
        self.assertEqual(f32(-(996.0 / comp.m_SessionMl)), comp.GetProgress())

    def test_debit_is_step_milliliters_times_0_001_in_liters(self):
        world = self.world(rate=300.0, step_seconds=0.5, delta=0.5)   # 150 ml per step
        comp = world.component()
        comp.Execute(world.data)
        self.assertEqual([f32(150.0 * f32(0.001))], world.car.leaks)
        self.assertAlmostEqual(149.0, world.fills[0][2], places=3)   # 1 ml spill under binary32 loss
        self.assertLess(world.fills[0][2], world.car.leaks[0] * 1000.0)

    def test_server_progress_advances_by_credit_not_by_prediction(self):
        world = self.world()
        comp = world.component()
        comp.Execute(world.data)
        self.assertEqual(249.0, comp.m_MovedMl)
        self.assertEqual(0, comp.m_PendingMl)
        self.assertEqual(0, comp.m_Elapsed)

    def test_between_steps_nothing_is_mutated(self):
        world = self.world(delta=0.1)
        comp = world.component()
        for _ in range(4):                       # 0.4 s: below the 0.5 s step
            self.assertEqual(2, comp.Execute(world.data))
        self.assertEqual((0, 0), calls(world))
        self.assertAlmostEqual(200.0, comp.m_PendingMl, places=3)
        comp.Execute(world.data)
        self.assertEqual((1, 1), calls(world))

    def test_credit_is_below_what_the_tank_actually_lost(self):
        for mode, tank_loss_ml, credit in (("normal", 250.0, 249.0), ("half", 125.0, 124.0),
                                           ("double", 500.0, 249.0)):
            with self.subTest(mode=mode):
                world = self.world()
                world.car.leak_mode = mode
                comp = world.component()
                comp.Execute(world.data)
                self.assertEqual(1, len(world.fills))
                self.assertEqual(16.0 - tank_loss_ml / 1000.0, world.car.liters)
                self.assertEqual(credit, world.fills[0][2])
                self.assertLess(world.fills[0][2], tank_loss_ml)

    def test_a_leak_that_removes_nothing_credits_nothing_and_stops(self):
        world = self.world()
        world.car.leak_mode = "noop"
        comp = world.component()
        comp.Execute(world.data)
        self.assertEqual((1, 0), calls(world))
        self.assertTrue(comp.m_Stopped)
        self.assertEqual(0, comp.m_MovedMl)
        self.assertEqual(4, comp.Execute(world.data))
        self.assertEqual((1, 0), calls(world))

    def test_step_uses_the_fresh_tank_not_the_session_snapshot(self):
        world = self.world(liters=16.0)
        comp = world.component()
        world.car.liters = 0.1               # someone else drained the tank after Setup
        comp.Execute(world.data)
        self.assertEqual([f32(100.0 * f32(0.001))], world.car.leaks)   # capped at 100 ml
        self.assertEqual([99.0], [f[2] for f in world.fills])
        self.assertEqual(0.0, world.car.liters)

    def test_step_uses_the_fresh_free_space_not_the_session_snapshot(self):
        world = self.world(maximum=5000)
        comp = world.component()
        world.vessel.quantity = 4900.0       # vessel was filled elsewhere after Setup
        comp.Execute(world.data)
        self.assertEqual([f32(100.0 * f32(0.001))], world.car.leaks)
        self.assertEqual([99.0], [f[2] for f in world.fills])
        self.assertEqual(4999.0, world.vessel.quantity)

    def test_step_never_exceeds_the_remaining_session(self):
        world = self.world(liters=0.6, delta=10.0)      # 5000 ml of pending, 600 ml session
        comp = world.component()
        comp.Execute(world.data)
        self.assertEqual([f32(600.0 * f32(0.001))], world.car.leaks)
        self.assertEqual([599.0], [f[2] for f in world.fills])
        self.assertGreaterEqual(world.car.liters, 0)

    def test_step_never_exceeds_the_session_even_if_the_tank_or_vessel_grows_mid_session(self):
        world = self.world(liters=0.5, delta=10.0)       # 500 ml session, 5000 ml of pending
        comp = world.component()
        world.car.liters = 16.0                          # tank refilled by someone else after Setup
        comp.Execute(world.data)
        self.assertEqual([f32(500.0 * f32(0.001))], world.car.leaks)
        self.assertEqual([499.0], [f[2] for f in world.fills])
        world = self.world(liters=16.0, quantity=4500.0, maximum=5000, delta=10.0)   # 500 ml session
        comp = world.component()
        world.vessel.quantity = 0.0                      # vessel emptied elsewhere after Setup
        comp.Execute(world.data)
        self.assertEqual([f32(500.0 * f32(0.001))], world.car.leaks)

    def test_remaining_session_shrinks_by_what_was_credited(self):
        world = self.world(liters=1.0)                   # 1000 ml session
        comp = world.component()
        comp.Execute(world.data)                         # 250 ml step, 249 ml credited
        self.assertEqual(249.0, comp.m_MovedMl)
        world.car.liters = 16.0                          # tank refilled elsewhere
        world.player.delta = 10.0
        comp.Execute(world.data)
        self.assertEqual(f32(751.0 * f32(0.001)), world.car.leaks[-1])   # session 1000 - moved 249
        self.assertEqual(2, len(world.fills))

    def test_garbage_tank_readback_stops_the_session_without_mutation(self):
        for bad in (math.nan, math.inf, -1.0):
            with self.subTest(bad=bad):
                world = self.world()
                comp = world.component()
                world.car.GetFluidFraction = lambda fluid, value=bad: value
                before = world.snapshot()
                self.assertEqual(2, comp.Execute(world.data))
                self.assertEqual(before, world.snapshot())
                self.assertTrue(comp.m_Stopped)
                self.assertEqual(4, comp.Execute(world.data))
                self.assertEqual(5, comp.Cancel(world.data))
                self.assertEqual(before, world.snapshot())

    def test_receipt_mismatch_stops_without_retry_or_refund(self):
        for mode in ("none", "double"):
            with self.subTest(mode=mode):
                world = self.world()
                world.fill_mode = mode
                comp = world.component()
                comp.Execute(world.data)
                self.assertEqual((1, 1), calls(world))
                self.assertTrue(comp.m_Stopped)
                self.assertTrue(any("receipt mismatch" in line for line in world.prints))
                self.assertEqual(0, comp.m_MovedMl)
                lost = world.car.liters
                self.assertEqual(4, comp.Execute(world.data))
                self.assertEqual(4, comp.Execute(world.data))
                self.assertEqual(5, comp.Cancel(world.data))
                self.assertEqual((1, 1), calls(world))       # no retry
                self.assertEqual(lost, world.car.liters)     # no refund to the tank

    def test_stopped_session_finishes_without_further_mutation(self):
        world = self.world()
        comp = world.component()
        comp.m_Stopped = True
        self.assertEqual(4, comp.Execute(world.data))
        self.assertEqual((0, 0), calls(world))
        comp = world.component()
        comp.m_AdjustedRate = 0
        self.assertEqual(4, comp.Execute(world.data))

    def test_session_ends_when_the_tank_is_empty(self):
        world = self.world(liters=0.5)
        comp = world.component()
        results = world.run(comp)
        self.assertEqual(4, results[-1])
        self.assertEqual(0.0, world.car.liters)
        self.assertEqual(len(world.car.leaks), len(world.fills))
        self.assertEqual(2, len(world.fills))
        self.assertEqual(498.0, world.vessel.quantity)
        leaks_at_end = len(world.car.leaks)
        self.assertEqual(4, comp.Execute(world.data))
        self.assertEqual(leaks_at_end, len(world.car.leaks))

    def test_session_ends_when_the_vessel_is_full(self):
        world = self.world(liters=16.0, quantity=4700.0, maximum=5000)
        comp = world.component()
        results = world.run(comp)
        self.assertEqual(4, results[-1])
        self.assertLessEqual(world.vessel.quantity, 5000.0)
        self.assertGreater(world.vessel.quantity, 4900.0)
        # a final sub-millilitre step can leak with zero credit: fuel is lost, never created
        self.assertIn(len(world.car.leaks) - len(world.fills), (0, 1))
        for leak, fill in zip(world.car.leaks, world.fills):
            self.assertLess(fill[2], leak * 1000.0 + 1e-6)
        leaks = len(world.car.leaks)
        world.run(comp)
        self.assertEqual(leaks, len(world.car.leaks))

    def test_completion_branch_flushes_and_reports_once(self):
        world = self.world(server=False, liters=1.0)
        comp = world.component()
        results = world.run(comp)
        self.assertEqual(1, comp.completed)
        self.assertEqual(4, results[-1])
        comp = world.component()
        comp.m_MovedMl, comp.m_PendingMl = comp.m_SessionMl, 0.0
        self.assertEqual(4, comp.Execute(world.data))
        self.assertEqual(1, comp.completed)

    def test_session_completion_never_steps_past_the_session(self):
        world = self.world(liters=16.0, quantity=4000.0, maximum=5000)   # 1000 ml session
        comp = world.component()
        world.run(comp)
        self.assertLessEqual(world.vessel.quantity - 4000.0, 1000.0)
        self.assertLessEqual(comp.m_MovedMl, comp.m_SessionMl)


class CancelTests(BehaviorCase):
    def partial(self, world):
        comp = world.component()
        world.player.delta = 0.2
        self.assertEqual(2, comp.Execute(world.data))   # 100 ml pending, below the step
        self.assertEqual((0, 0), calls(world))
        return comp

    def test_voluntary_cancel_flushes_exactly_the_pending_partial_step(self):
        world = self.world()
        comp = self.partial(world)
        self.assertEqual(5, comp.Cancel(world.data))
        self.assertEqual([f32(100.0 * f32(0.001))], world.car.leaks)
        self.assertEqual([99.0], [f[2] for f in world.fills])
        self.assertEqual(99.0, world.vessel.quantity)
        self.assertEqual(0, comp.m_PendingMl)

    def test_repeated_cancel_is_idempotent(self):
        world = self.world()
        comp = self.partial(world)
        comp.Cancel(world.data)
        after = world.snapshot()
        for _ in range(3):
            self.assertEqual(5, comp.Cancel(world.data))
        self.assertEqual(after, world.snapshot())
        self.assertEqual((1, 1), calls(world))

    def test_cancel_with_nothing_pending_changes_nothing(self):
        world = self.world()
        comp = world.component()
        before = world.snapshot()
        self.assertEqual(5, comp.Cancel(world.data))
        self.assertEqual(before, world.snapshot())

    def test_cancel_after_a_flushed_step_does_not_replay_it(self):
        world = self.world()
        comp = world.component()
        comp.Execute(world.data)
        self.assertEqual((1, 1), calls(world))
        comp.Cancel(world.data)
        comp.Cancel(world.data)
        self.assertEqual((1, 1), calls(world))

    def test_invalidation_before_cancel_debits_nothing(self):
        invalidations = {
            "out of reach": lambda w: setattr(w.player, "pos", (9.0, 0.0, 0.0)),
            "item left hands": lambda w: setattr(w.player, "hands", None),
            "other item in hands": lambda w: setattr(w.player, "hands", ItemBase()),
            "engine on": lambda w: setattr(w.car, "engine", True),
            "car destroyed": lambda w: setattr(w.car, "destroyed", True),
            "car moving": lambda w: setattr(w.car, "moving", True),
            "gate closed": lambda w: setattr(w, "gate", False),
            "player in vehicle": lambda w: setattr(w.player, "vehicle", True),
            "vessel destroyed": lambda w: setattr(w.vessel, "destroyed", True),
            "target gone": lambda w: setattr(w.target, "obj", None),
        }
        for label, invalidate in invalidations.items():
            with self.subTest(label):
                world = self.world()
                comp = self.partial(world)
                before = world.snapshot()
                invalidate(world)
                self.assertEqual(5, comp.Cancel(world.data))
                self.assertEqual(before, world.snapshot())
                self.assertEqual(0, comp.m_PendingMl)
                self.assertTrue(comp.m_Stopped)
                self.assertEqual(5, comp.Cancel(world.data))
                self.assertEqual(before, world.snapshot())
                self.assertEqual(4, comp.Execute(world.data))

    def test_invalidation_at_a_step_boundary_debits_nothing(self):
        for label, invalidate in (("engine", lambda w: setattr(w.car, "engine", True)),
                                  ("hands", lambda w: setattr(w.player, "hands", None)),
                                  ("reach", lambda w: setattr(w.player, "pos", (9.0, 0.0, 0.0))),
                                  ("gate", lambda w: setattr(w, "gate", False)),
                                  ("destroyed", lambda w: setattr(w.car, "destroyed", True))):
            with self.subTest(label):
                world = self.world()
                comp = world.component()
                invalidate(world)
                self.assertEqual(2, comp.Execute(world.data))
                self.assertEqual((0, 0), calls(world))
                self.assertEqual(4, comp.Execute(world.data))

    def test_receipt_mismatch_then_cancel_does_not_flush_again(self):
        world = self.world(delta=0.2)
        comp = world.component()
        world.fill_mode = "none"
        comp.Execute(world.data)
        comp.Cancel(world.data)
        self.assertEqual((1, 1), calls(world))


# --------------------------------------------------------------------------
# Binary32 conservation through the executed action
# --------------------------------------------------------------------------
class ConservationTests(BehaviorCase):
    def test_random_sessions_never_credit_more_than_the_exact_tank_loss(self):
        rng = random.Random(5301)
        for case in range(120):
            capacity = f32(rng.choice((20.0, 60.0, 100.0, 4000.0, rng.uniform(5.0, 4000.0))))
            liters = f32(rng.uniform(0.01, 1.0) * capacity)
            quantity = f32(rng.choice((0.0, 1023.9999389648438, rng.uniform(0.0, 19000.0))))
            world = self.world(capacity=capacity, liters=liters, quantity=quantity, maximum=20000,
                               rate=f32(rng.uniform(50.0, 900.0)), delta=f32(rng.uniform(0.05, 0.6)))
            world.car.leak_mode = rng.choice(("normal", "normal", "half"))
            comp = world.component()
            for _ in range(200):
                before = (world.Siphon.TankLiters(world.car), world.vessel.quantity)
                n = len(world.fills)
                result = comp.Execute(world.data)
                after = (world.Siphon.TankLiters(world.car), world.vessel.quantity)
                self.assertLessEqual(len(world.fills) - n, 1)
                if len(world.fills) > n:
                    loss = (Fraction(before[0]) - Fraction(after[0])) * 1000
                    gain = Fraction(after[1]) - Fraction(before[1])
                    self.assertGreaterEqual(gain, 0, case)
                    if gain == 0:                 # absorbed by binary32: receipt must refuse
                        self.assertTrue(comp.m_Stopped, case)
                    self.assertLess(gain, loss, (case, before, after))
                    self.assertGreaterEqual(after[0], 0)
                    self.assertLessEqual(after[1], 20000.0)
                if result != 2:
                    break


# --------------------------------------------------------------------------
# Siphon* scalar helper grids (authored policy, binary32)
# --------------------------------------------------------------------------
BAD = (math.nan, math.inf, -math.inf, -1.0)


class SiphonScalarGridTests(unittest.TestCase):
    def setUp(self):
        self.p = transfer.authored_policy()

    def test_every_argument_of_every_siphon_helper_fails_closed_on_bad_values(self):
        good = {
            "SiphonSessionMl": (10.0, 0.0, 5000.0),
            "SiphonStepMl": (10.0, 0.0, 5000.0, 250.0, 5000.0),
            "SiphonCreditMl": (250.0, 10.0, 9.75, 0.0, 20000.0),
            "SiphonReceiptOk": (249.0, 1000.0, 1249.0),
        }
        for name, args in good.items():
            fail = False if name == "SiphonReceiptOk" else 0
            self.assertNotEqual(fail, self.p[name](*args), name)
            for index, bad in itertools.product(range(len(args)), BAD):
                probe = list(args)
                probe[index] = bad
                with self.subTest(name=name, index=index, bad=bad):
                    self.assertEqual(fail, self.p[name](*probe))

    def test_float_max_overflow_is_refused_not_wrapped(self):
        p = self.p
        self.assertEqual(0, p["SiphonSessionMl"](transfer.FLOAT_MAX, 0.0, transfer.FLOAT_MAX))
        self.assertEqual(0, p["SiphonStepMl"](10.0, 0.0, 5000.0, transfer.FLOAT_MAX, math.inf))
        self.assertEqual(0, p["SiphonCreditMl"](250.0, 10.0, 9.75, 0.0, math.inf))

    def test_creditmax_and_tank_bounds_are_enforced(self):
        credit = self.p["SiphonCreditMl"]
        self.assertGreater(credit(250.0, 4096.0, 4095.75, 0.0, 1048576.0), 0)
        self.assertEqual(0, credit(250.0, 4097.0, 4096.75, 0.0, 1048576.0))
        self.assertEqual(0, credit(250.0, 10.0, 9.75, 0.0, 1048577.0))


if __name__ == "__main__":
    unittest.main()
