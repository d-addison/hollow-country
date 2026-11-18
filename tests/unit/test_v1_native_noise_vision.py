"""v1 audit: search makes native AI noise (#15 #20); vision range from clothing,
darkness and lights (#20 #35 #56).

The authored Enforce adapter methods (HCInfectedVision.c, HCSearchNoise.c and
the OnFinishProgressServer hook of HCInteriorAction.c) are translated token by
token into Python by a small Enforce-subset translator (the approach of
test_fuel_siphon_behavior.py) and EXECUTED against explicit SYNTHETIC native
objects: GetGame, NoiseSystem, NoiseParams, PlayerBase, ItemBase and the item
class tree, the native AITargetCallbacksPlayer base and HCInteriorsModule. The
translator refuses constructs it does not know; it never reimplements a method
by hand. These tests prove authored control flow only. They are not Enforce
compilation, not DayZ behavior and not runtime acceptance: the noise config
path, the AI vision multiplier semantics and the factor constants are all
unobserved at runtime, and both features stay behind local-acceptance gates
(vision) or documented acceptance steps (noise).

Engine citations (installed 1.30.164289 scripts):
  3_Game/Noise.c:7            NoiseSystem.AddNoisePos(EntityAI, vector, NoiseParams, float)
  3_Game/Noise.c:25           NoiseParams.LoadFromPath
  4_World/Classes/UserActionsComponent/Actions/Interact/ActionOpenDoors.c:78-90
                              vanilla OnEndServer noise pattern
  4_World/Static/MiscGameplayFunctions.c:1830  GenerateAINoiseAtPositionEx
  3_Game/Systems/AI/AITarget_callbacks.c:13   GetMaxVisionRangeModifier(EntityAI pApplicant)
  4_World/Entities/ManBase/PlayerBase/AITargetCallbacksPlayer.c:45-84
  4_World/Entities/ItemBase.c:865-868         IsLightSource() default false
  3_Game/Entities/EntityAI.c:544-548          IsIgnited() = energy manager working
  4_World/Entities/ItemBase/ChemLight.c:1,66-74,141-154   Chemlight_ColorBase : ItemBase
  4_World/Entities/ItemBase/PortableGasLamp.c:1,34-43     PortableGasLamp : ItemBase
"""
import itertools
import keyword
import math
import os
from pathlib import Path
import re
import unittest

try:
    from .test_fuel_transfer import f32
    from .test_crafting_completion import body
except ImportError:
    from test_fuel_transfer import f32
    from test_crafting_completion import body

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "mods/HollowCountry/scripts/4_World"
VISION = SCRIPTS / "Infected/HCInfectedVision.c"
NOISE = SCRIPTS / "Loot/HCSearchNoise.c"
ACTION = SCRIPTS / "Interiors/HCInteriorAction.c"
NATIVE_CACHE = Path(os.environ.get(
    "HC_NATIVE_SCRIPTS",
    Path.home() / ".cache/hollow-country/native-scripts/scripts-1.30.164289"))
MARKER = "$profile:HollowCountry/acceptance/infected_vision.disable"   # opt-out marker; the override is on by default
NOISE_PATH = "CfgVehicles SurvivorBase NoiseActionDefault"
INF = float("inf")
NAN = float("nan")


def strip_comments(text):
    return re.sub(r"//[^\n]*", "", text)


def class_text(path, name):
    """Text of one top-level class (up to the next top-level class)."""
    source = path.read_text()
    match = re.search(r"^(?:modded )?class " + re.escape(name) + r"\b", source, re.M)
    if not match:
        raise AssertionError("missing authored class: " + name)
    rest = source[match.start():]
    tail = re.search(r"^(?:modded )?class ", rest[1:], re.M)
    return rest[: tail.start() + 1] if tail else rest


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
        self.native_objs = natives
        self.classes = {}
        self.loops = 0

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
            depth += {"{": 1, "}": -1}.get(self.take(), 0)

    # declarations
    def scan(self):
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
                base = name  # a modded class extends the native class of the same name
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
            if self.peek()[1] in ("out", "inout"):
                self.take()
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
        cls["methods"][name] = {"type": rtype, "params": params, "static": "static" in mods,
                                "span": (start, self.pos), "ctor": name == cls["name"]}
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

    @staticmethod
    def zero(ftype):
        return {"float": "0.0", "int": "0", "bool": "False", "string": "''"}.get(ftype, "None")

    def emit_class(self, cls, only):
        out = ["class %s(%s):" % (cls["name"], cls["base"] or "object")]
        ctx = {"cls": cls}
        for fname, field in cls["fields"].items():
            if field["static"]:
                if field["default"]:
                    self.pos = field["default"][0]
                    value = self.expr(dict(ctx, locals={}, static=True))
                else:
                    value = self.zero(field["type"])
                out.append("    %s = %s" % (fname, value))
        out += ["    def _hc_zero_fields(self):", "        pass"]
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
        header = "__init__" if method["ctor"] else name
        out = []
        if method["static"]:
            out += ["    @staticmethod", "    def %s(%s):" % (header, ", ".join(params))]
        else:
            out.append("    def %s(%s):" % (header, ", ".join(["self"] + params)))
        if method["ctor"]:
            out.append("        self._hc_zero_fields()")
        for ptype, pname in method["params"]:
            if keyword.iskeyword(pname):
                raise Unsupported("keyword parameter " + pname)
            if ptype == "float":
                out.append("        %s = f32(%s)" % (pname, pname))
        ctx = {"cls": cls, "locals": {p: t for t, p in method["params"]}, "static": method["static"],
               "rtype": "void" if method["ctor"] else method["type"]}
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
    def block(self, ctx, level):
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
            return self.block(ctx, level)
        if tok[1] == "if":
            self.take()
            self.take("(")
            cond = self.expr(ctx)
            self.take(")")
            out = [pad + "if %s:" % cond] + self.block(ctx, level + 1)
            if self.peek()[1] == "else":
                self.take()
                out += [pad + "else:"] + self.block(ctx, level + 1)
            return out
        if tok[1] == "for":
            return self.for_statement(ctx, level)
        if tok[1] in ("while", "do", "switch", "foreach", "continue", "break", "auto", "ref", "delete"):
            raise Unsupported("unsupported statement: " + tok[1])
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
            if name in ctx["locals"]:
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
        out = [pad + line for line in init]
        out += [pad + "%s = 0" % guard, pad + "while %s:" % cond,
                pad + "    %s += 1" % guard,
                pad + "    if %s > %d: raise AssertionError('loop bound')" % (guard, LOOP_BOUND)]
        out += self.block(ctx, level + 1)
        out += [pad + "    " + line for line in step]
        return out

    # expressions
    def resolve_target(self, ctx, name):
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
        return self.binary(ctx, self.and_expr, ("||",), lambda a, o, b: "bool(%s or %s)" % (a, b))

    def and_expr(self, ctx):
        return self.binary(ctx, self.eq_expr, ("&&",), lambda a, o, b: "bool(%s and %s)" % (a, b))

    def eq_expr(self, ctx):
        return self.binary(ctx, self.rel_expr, ("==", "!="), lambda a, o, b: "(%s %s %s)" % (a, o, b))

    def rel_expr(self, ctx):
        return self.binary(ctx, self.add_expr, ("<", ">", "<=", ">="),
                           lambda a, o, b: "(%s %s %s)" % (a, o, b))

    def add_expr(self, ctx):
        return self.binary(ctx, self.mul_expr, ("+", "-"), self.arith)

    def mul_expr(self, ctx):
        return self.binary(ctx, self.unary, ("*", "/"), self.arith)

    def binary(self, ctx, sub, ops, fmt):
        left = sub(ctx)
        while self.peek()[1] in ops:
            op = self.take()
            left = fmt(left, op, sub(ctx))
        return left

    @staticmethod
    def arith(left, op, right):
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
        kind, text = self.peek()
        if kind == "num":
            self.take()
            return repr(f32(float(text))) if ("." in text or "e" in text.lower()) else text
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
            owner = cls["name"] if cls["methods"][name]["static"] else "self"
            if owner == "self" and ctx["static"]:
                raise Unsupported("instance call in static method: " + name)
            return "%s.%s" % (owner, name)
        base = self.native_objs.get(cls["base"])
        if call and not ctx["static"] and base is not None and callable(getattr(base, name, None)):
            return "self." + name  # inherited native method (fake base class)
        if not call and name in cls["fields"]:
            return self.resolve_target(ctx, name)[0]
        if name in self.natives or name in self.classes:
            return name
        raise Unsupported("unknown native or name: " + name)


_TRANSLATED = {}


def execute(path, select, natives):
    """Translate the selected classes of an authored file and run the class
    definitions in a namespace of explicit synthetic natives."""
    text = Path(path).read_text()
    key = (text, repr(sorted((k, sorted(v) if v else v) for k, v in select.items())), tuple(sorted(natives)))
    if key not in _TRANSLATED:
        _TRANSLATED[key] = Translator(text, natives).emit(select)
    namespace = dict(natives)
    namespace["f32"] = f32
    exec(compile(_TRANSLATED[key], "authored-enforce:" + Path(path).name, "exec"), namespace)
    return namespace


# --------------------------------------------------------------------------
# Explicitly synthetic native objects
# --------------------------------------------------------------------------
class Cast:
    @classmethod
    def Cast(cls, value):
        return value if isinstance(value, cls) else None


class ItemBase(Cast):
    """Native ItemBase: IsLightSource() is false unless a subclass overrides it
    (ItemBase.c:865-868); IsIgnited() is the energy-manager working state."""
    light_source = False

    def __init__(self, working=False, attachments=(), inventory=True):
        self.working = working
        self.attachments = list(attachments)
        self.has_inventory = inventory
        self.visits = []

    def IsLightSource(self):
        return self.light_source

    def IsIgnited(self):
        return self.working

    def GetInventory(self):
        return Inventory(self) if self.has_inventory else None


class Inventory:
    def __init__(self, owner):
        self.owner = owner

    def AttachmentCount(self):
        return len(self.owner.attachments)

    def GetAttachmentFromIndex(self, index):
        self.owner.visits.append(index)
        return self.owner.attachments[index]


class Flashlight(ItemBase): pass                       # Flashlight.c:1
class Roadflare(ItemBase): pass                        # Roadflare.c:24
class FlammableBase(ItemBase): pass                    # Torch.c:1
class Chemlight_ColorBase(ItemBase): pass              # ChemLight.c:1
class Chemlight_Red(Chemlight_ColorBase): pass         # ChemLight.c:203
class PortableGasLamp(ItemBase): pass                  # PortableGasLamp.c:1
class NonLight(ItemBase): pass
class Headtorch_ColorBase(ItemBase): light_source = True   # Headtorch_ColorBase.c:243
class UniversalLight(ItemBase): light_source = True        # UniversalLight.c:117
class TLRLight(ItemBase): light_source = True              # TLRLight.c:99

LIGHT_NATIVES = {"ItemBase": ItemBase, "Flashlight": Flashlight, "Roadflare": Roadflare,
                 "FlammableBase": FlammableBase, "Chemlight_ColorBase": Chemlight_ColorBase,
                 "PortableGasLamp": PortableGasLamp}
# kind, class, whether the native class itself answers IsLightSource() true
LIGHT_KINDS = (
    ("Flashlight", Flashlight), ("Roadflare", Roadflare), ("FlammableBase", FlammableBase),
    ("Chemlight_ColorBase", Chemlight_ColorBase), ("Chemlight_Red", Chemlight_Red),
    ("PortableGasLamp", PortableGasLamp), ("Headtorch_ColorBase", Headtorch_ColorBase),
    ("UniversalLight", UniversalLight), ("TLRLight", TLRLight))


class Player(Cast):
    """Synthetic PlayerBase target."""

    def __init__(self, held=None, headgear=None, coef=1.0, alive=True):
        self.held, self.headgear, self.coef, self.alive = held, headgear, coef, alive
        self.slots = []
        self.coef_reads = 0

    def GetItemInHands(self):
        return self.held

    def FindAttachmentBySlotName(self, slot):
        self.slots.append(slot)
        return self.headgear if slot == "Headgear" else None

    def GetVisibilityCoef(self):
        self.coef_reads += 1
        return self.coef

    def IsAlive(self):
        return self.alive

    def GetPosition(self):
        return "synthetic-player-position"


class Game:
    def __init__(self, server=True, day_time=12.0, noise=None):
        self.server, self.day_time, self.noise = server, day_time, noise
        self.reads = []

    def IsServer(self):
        self.reads.append("IsServer")
        return self.server

    def GetDayTime(self):
        self.reads.append("GetDayTime")
        return self.day_time

    def GetNoiseSystem(self):
        self.reads.append("GetNoiseSystem")
        return self.noise


class VisionWorld:
    """Authored HCInfectedVision.c running over synthetic natives."""

    def __init__(self, server=True, day_time=12.0, disabled=False, native_range=0.9, game=True):
        self.log = []
        self.game = Game(server, day_time) if game else None
        log, marker_present, native_value = self.log, disabled, native_range   # marker_present: a .disable file exists

        class AITargetCallbacksPlayer:  # native base (AITargetCallbacksPlayer.c:45-84)
            def GetMaxVisionRangeModifier(self, pApplicant):
                log.append(("native", pApplicant))
                return native_value

        natives = dict(LIGHT_NATIVES)
        natives.update({
            "GetGame": lambda: self.game,
            "FileExist": lambda path: log.append(("FileExist", path)) or marker_present,
            "Print": lambda text: log.append(("Print", text)),
            "AITargetCallbacksPlayer": AITargetCallbacksPlayer})
        self.ns = execute(VISION, {
            "HCInfectedVisionQualification": None, "HCInfectedVisionPolicy": None,
            "HCInfectedVision": None, "AITargetCallbacksPlayer": None}, natives)

    def replace(self, cls, name, function):
        setattr(self.ns[cls], name, staticmethod(function))

    def callbacks(self, player):
        return self.ns["AITargetCallbacksPlayer"](player)


def vision_policy():
    return VisionWorld().ns["HCInfectedVisionPolicy"]


class NoiseWorld:
    """Authored HCSearchNoise.c running over a synthetic NoiseSystem."""

    class Action(Cast):  # explicit synthetic HCInteriorActionData
        def __init__(self, phase, player):
            self.Site = None if phase is None else type("Site", (), {"Phase": phase})()
            self.m_Player = player

    def __init__(self, server=True, noise_system=True, game=True):
        self.log = []
        self.params = []
        log, params = self.log, self.params

        class NoiseParams:
            def __init__(self):
                params.append(self)

            def LoadFromPath(self, path):
                log.append(("load", path))

        class NoiseSystem:
            def AddNoisePos(self, source, position, noise_params):
                log.append(("emit", source, position, noise_params))

        self.noise = NoiseSystem() if noise_system else None
        self.game = Game(server, noise=self.noise) if game else None
        natives = {"GetGame": lambda: self.game, "NoiseParams": NoiseParams,
                   "HCInteriorActionData": NoiseWorld.Action}
        self.ns = execute(NOISE, {"HCSearchNoisePolicy": None, "HCSearchNoise": None}, natives)

    @property
    def emissions(self):
        return [entry for entry in self.log if entry[0] == "emit"]


class AuthoredPolicyBehavior(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = vision_policy()

    def factor(self, coef=1.0, hour=12.0, lit=0.0):
        return self.policy.Factor(coef, hour, lit)

    def test_given_neutral_clothing_daylight_no_light_then_exactly_native(self):
        self.assertEqual(1.0, self.factor())

    def test_given_any_inputs_then_factor_is_finite_and_clamped_to_0_6_1_3(self):
        coefs = (-5.0, 0.0, 0.1, 0.5, 0.6, 0.9, 1.0, 1.2, 1.3, 2.0, 1e30, INF, -INF, NAN)
        hours = [h / 2.0 for h in range(-2, 52)] + [INF, -INF, NAN]
        for coef in coefs:
            for hour in hours:
                for lit in (0.0, 1.0, 0.5, NAN, INF):
                    value = self.factor(coef, hour, lit)
                    self.assertTrue(math.isfinite(value), (coef, hour, lit))
                    self.assertGreaterEqual(value, 0.6 - 1e-6, (coef, hour, lit))
                    self.assertLessEqual(value, 1.3 + 1e-6, (coef, hour, lit))

    def test_given_extreme_inputs_then_native_product_stays_inside_documented_bounds(self):
        # Native finite speed/stance constants give 0.225 <= result <= 1.25
        # (AITargetCallbacksPlayer.c:45-84); the authored factor never widens that
        # beyond 0.135 .. 1.625 whatever the inputs.
        values = (NAN, INF, -INF, -1000001, -1, 0, 0.49, 0.5, 0.6, 1, 1.3, 2, 23.999, 24, 1000000, 1000001)
        for coef, hour, lit in itertools.product(values, repeat=3):
            factor = self.factor(coef, hour, lit)
            self.assertTrue(0.6 - 1e-6 <= factor <= 1.3 + 1e-6, (coef, hour, lit))
            self.assertGreaterEqual(0.225 * factor, 0.135 - 1e-6)
            self.assertLessEqual(1.25 * factor, 1.625 + 1e-6)

    def test_given_invalid_or_uninitialised_inputs_then_neutral_not_a_penalty(self):
        self.assertEqual(1.0, self.policy.ClothingFactor(0.0))
        self.assertEqual(1.0, self.policy.ClothingFactor(-1.0))
        self.assertEqual(1.0, self.policy.ClothingFactor(NAN))
        self.assertEqual(0.0, self.policy.Nightness(NAN))
        self.assertEqual(0.0, self.policy.Nightness(-1.0))
        self.assertEqual(0.0, self.policy.Nightness(24.0))

    def test_given_camouflaging_clothing_then_shorter_range_floored_at_0_6(self):
        self.assertLess(self.factor(coef=0.8), self.factor(coef=1.0))
        self.assertEqual(f32(0.8), self.factor(coef=0.8))
        self.assertEqual(f32(0.6), self.factor(coef=0.2))

    def test_given_hour_then_nightness_ramps_at_dusk_and_dawn(self):
        n = self.policy.Nightness
        self.assertEqual(0.0, n(12.0))
        self.assertEqual(0.0, n(7.0))
        self.assertEqual(0.0, n(19.0))
        self.assertEqual(1.0, n(21.0))
        self.assertEqual(1.0, n(23.5))
        self.assertEqual(1.0, n(0.0))
        self.assertEqual(1.0, n(4.9))
        self.assertEqual(0.5, n(6.0))
        self.assertEqual(0.5, n(20.0))

    def test_given_darkness_then_unlit_player_is_seen_from_less_far(self):
        self.assertEqual(f32(0.75), self.factor(hour=2.0))
        self.assertLess(self.factor(hour=2.0), self.factor(hour=12.0))

    def test_given_lit_light_at_night_then_seen_from_further_than_unlit(self):
        unlit = self.factor(hour=2.0, lit=0.0)
        lit = self.factor(hour=2.0, lit=1.0)
        self.assertGreater(lit, unlit)
        self.assertAlmostEqual(1.125, lit, places=5)

    def test_given_lit_light_in_daylight_then_small_bounded_gain_only(self):
        self.assertAlmostEqual(1.1, self.factor(hour=12.0, lit=1.0), places=5)

    def test_given_best_case_for_detection_then_capped_at_1_3(self):
        self.assertEqual(f32(1.3), self.factor(coef=1.3, hour=2.0, lit=1.0))
        self.assertEqual(f32(1.3), self.factor(coef=1.3, hour=12.0, lit=1.0))


class LitItemClassification(unittest.TestCase):
    """The authored LitItem executed against the native class tree. Native
    IsLightSource() is true only for Headtorch_ColorBase, UniversalLight and
    TLRLight; Chemlight_ColorBase and PortableGasLamp inherit the false default
    but are working light sources through the energy manager (IsIgnited)."""

    def lit(self, item):
        return VisionWorld().ns["HCInfectedVision"].LitItem(item)

    def test_given_working_light_of_every_native_kind_then_lit(self):
        for kind, cls in LIGHT_KINDS:
            self.assertTrue(self.lit(cls(working=True)), kind)

    def test_given_switched_off_light_of_every_native_kind_then_unlit(self):
        for kind, cls in LIGHT_KINDS:
            self.assertFalse(self.lit(cls(working=False)), kind)

    def test_given_working_chemlight_then_lit_although_native_is_light_source_is_false(self):
        item = Chemlight_Red(working=True)
        self.assertFalse(item.IsLightSource())
        self.assertTrue(self.lit(item))
        self.assertFalse(self.lit(Chemlight_Red(working=False)))

    def test_given_working_gas_lamp_then_lit_although_native_is_light_source_is_false(self):
        item = PortableGasLamp(working=True)
        self.assertFalse(item.IsLightSource())
        self.assertTrue(self.lit(item))
        self.assertFalse(self.lit(PortableGasLamp(working=False)))

    def test_given_no_item_or_non_light_item_then_unlit_even_when_working(self):
        self.assertFalse(self.lit(None))
        self.assertFalse(self.lit(NonLight(working=True)))
        self.assertFalse(self.lit(ItemBase(working=True)))

    @unittest.skipUnless(NATIVE_CACHE.is_dir(), "installed native script cache absent")
    def test_native_cache_declares_the_two_classes_without_an_is_light_source_override(self):
        item_dir = NATIVE_CACHE / "4_World/Entities/ItemBase"
        for relative, declaration in (("ChemLight.c", r"^class Chemlight_ColorBase\s*:\s*ItemBase\b"),
                                      ("PortableGasLamp.c", r"^class PortableGasLamp\s+extends\s+ItemBase\b")):
            text = (item_dir / relative).read_text(errors="replace")
            self.assertRegex(text, re.compile(declaration, re.M), relative)
            self.assertNotIn("IsLightSource", text, relative)
            self.assertIn("OnWork", text, relative)
        entity = (NATIVE_CACHE / "3_Game/Entities/EntityAI.c").read_text(errors="replace")
        self.assertRegex(entity, r"bool IsIgnited\(\)\s*\{\s*if \(m_EM\)\s*return m_EM\.IsWorking\(\);")


class LightScanBehavior(unittest.TestCase):
    def scan(self, player):
        return VisionWorld().ns["HCInfectedVision"].HasLitLight(player)

    def test_given_no_player_or_empty_hands_and_head_then_unlit(self):
        self.assertFalse(self.scan(None))
        player = Player()
        self.assertFalse(self.scan(player))
        self.assertEqual(["Headgear"], player.slots)

    def test_given_lit_held_item_then_lit_without_looking_further(self):
        held = Flashlight(working=True, attachments=[Flashlight(working=True)])
        player = Player(held=held)
        self.assertTrue(self.scan(player))
        self.assertEqual([], player.slots)
        self.assertEqual([], held.visits)

    def test_given_lit_headgear_with_unlit_hands_then_lit(self):
        player = Player(held=NonLight(), headgear=Headtorch_ColorBase(working=True))
        self.assertTrue(self.scan(player))
        self.assertEqual(["Headgear"], player.slots)

    def test_given_lit_headgear_and_empty_hands_then_lit(self):
        self.assertTrue(self.scan(Player(headgear=Headtorch_ColorBase(working=True))))

    def test_given_unlit_headgear_then_unlit(self):
        self.assertFalse(self.scan(Player(headgear=Headtorch_ColorBase(working=False))))

    def test_given_lit_weapon_attachment_on_unlit_held_item_then_lit_after_visiting_it(self):
        held = NonLight(attachments=[NonLight(), TLRLight(working=True), NonLight()])
        self.assertTrue(self.scan(Player(held=held)))
        self.assertEqual([0, 1], held.visits)

    def test_given_held_item_without_inventory_or_attachments_then_unlit(self):
        self.assertFalse(self.scan(Player(held=NonLight(inventory=False))))
        held = NonLight()
        self.assertFalse(self.scan(Player(held=held)))
        self.assertEqual([], held.visits)

    def test_given_many_unlit_attachments_then_exactly_eight_are_visited(self):
        held = NonLight(attachments=[NonLight() for _ in range(20)])
        self.assertFalse(self.scan(Player(held=held)))
        self.assertEqual(list(range(8)), held.visits)

    def test_given_lit_attachment_beyond_the_cap_then_never_seen(self):
        attachments = [NonLight() for _ in range(12)]
        attachments[9] = TLRLight(working=True)
        held = NonLight(attachments=attachments)
        self.assertFalse(self.scan(Player(held=held)))
        self.assertEqual(list(range(8)), held.visits)

    def test_given_lit_attachment_at_the_last_allowed_index_then_lit(self):
        attachments = [NonLight() for _ in range(12)]
        attachments[7] = TLRLight(working=True)
        held = NonLight(attachments=attachments)
        self.assertTrue(self.scan(Player(held=held)))
        self.assertEqual(list(range(8)), held.visits)

    def test_given_working_chemlight_or_gas_lamp_in_hand_then_lit(self):
        for cls in (Chemlight_Red, PortableGasLamp):
            self.assertTrue(self.scan(Player(held=cls(working=True))), cls.__name__)
            self.assertFalse(self.scan(Player(held=cls(working=False))), cls.__name__)

    def test_player_factor_combines_clothing_clock_and_light_reading_each_once(self):
        world = VisionWorld(day_time=2.0)
        factor = world.ns["HCInfectedVision"].PlayerFactor
        self.assertEqual(1.0, factor(None))
        unlit = Player(held=NonLight(), coef=1.0)
        self.assertEqual(f32(0.75), factor(unlit))
        self.assertEqual(1, unlit.coef_reads)
        lit = Player(held=Chemlight_Red(working=True), coef=1.0)
        self.assertAlmostEqual(1.125, factor(lit), places=5)
        self.assertEqual(1, lit.coef_reads)
        self.assertEqual(["GetDayTime", "GetDayTime"], world.game.reads)


class VisionOverrideBehavior(unittest.TestCase):
    APPLICANT = object()

    def recording(self, world, admitted, factor):
        calls = []

        def admission():
            calls.append("admission")
            return admitted

        def player_factor(player):
            calls.append(("factor", player))
            return factor

        world.replace("HCInfectedVisionQualification", "Admitted", admission)
        world.replace("HCInfectedVision", "PlayerFactor", player_factor)
        return calls

    def call(self, world, player):
        return world.callbacks(player).GetMaxVisionRangeModifier(self.APPLICANT)

    def test_client_returns_exact_native_with_no_admission_and_no_factor(self):
        world = VisionWorld(server=False)
        calls = self.recording(world, admitted=True, factor=0.75)
        self.assertEqual(f32(0.9), self.call(world, Player()))
        self.assertEqual([], calls)
        self.assertEqual([("native", self.APPLICANT)], world.log)

    def test_client_with_the_real_gate_never_probes_the_acceptance_marker(self):
        world = VisionWorld(server=False, disabled=True)
        self.assertEqual(f32(0.9), self.call(world, Player(held=Flashlight(working=True))))
        self.assertEqual([("native", self.APPLICANT)], world.log)

    def test_closed_server_gate_returns_exact_native_without_computing_a_factor(self):
        world = VisionWorld()
        calls = self.recording(world, admitted=False, factor=0.75)
        self.assertEqual(f32(0.9), self.call(world, Player()))
        self.assertEqual(["admission"], calls)

    def test_admitted_server_multiplies_native_once_by_the_captured_target_factor(self):
        world = VisionWorld()
        target = Player()
        calls = self.recording(world, admitted=True, factor=0.75)
        self.assertAlmostEqual(0.675, self.call(world, target), places=6)
        self.assertEqual(["admission", ("factor", target)], calls)
        self.assertEqual(1, len(world.log))

    def test_missing_game_or_missing_captured_player_keeps_exact_native(self):
        world = VisionWorld(game=False)
        calls = self.recording(world, admitted=True, factor=0.75)
        self.assertEqual(f32(0.9), self.call(world, Player()))
        self.assertEqual([], calls)
        world = VisionWorld()
        calls = self.recording(world, admitted=True, factor=0.75)
        self.assertEqual(f32(0.9), self.call(world, None))
        self.assertEqual(["admission"], calls)

    def test_the_target_is_the_player_captured_by_the_constructor(self):
        world = VisionWorld()
        first, second = Player(), Player()
        seen = self.recording(world, admitted=True, factor=1.0)
        callbacks = world.callbacks(first)
        other = world.callbacks(second)
        callbacks.GetMaxVisionRangeModifier(self.APPLICANT)
        other.GetMaxVisionRangeModifier(self.APPLICANT)
        self.assertEqual([("factor", first), ("factor", second)], [c for c in seen if c != "admission"])

    def test_disable_marker_closes_the_gate_and_the_override_is_exactly_native(self):
        world = VisionWorld(day_time=2.0, disabled=True)
        gate = world.ns["HCInfectedVisionQualification"]
        self.assertIs(False, gate.Qualified())
        player = Player(held=Flashlight(working=True), coef=0.5)
        for _ in range(3):
            self.assertEqual(f32(0.9), self.call(world, player))
        self.assertEqual(0, player.coef_reads)
        self.assertEqual([("FileExist", MARKER)], [e for e in world.log if e[0] == "FileExist"])
        prints = [e[1] for e in world.log if e[0] == "Print"]
        self.assertEqual(1, len(prints))
        self.assertIn("not admitted", prints[0])
        self.assertIn("PENDING", prints[0])

    def test_default_without_a_marker_admits_logs_experimental_and_probes_once(self):
        world = VisionWorld(day_time=2.0)
        player = Player(held=Chemlight_Red(working=True), coef=1.0)
        for _ in range(3):
            self.assertAlmostEqual(0.9 * 1.125, self.call(world, player), places=5)
        self.assertEqual([("FileExist", MARKER)], [e for e in world.log if e[0] == "FileExist"])
        prints = [e[1] for e in world.log if e[0] == "Print"]
        self.assertEqual(1, len(prints))
        self.assertIn("EXPERIMENTAL", prints[0])
        self.assertIn("runtime acceptance PENDING", prints[0])
        self.assertEqual(3, player.coef_reads)

    def test_end_to_end_unlit_night_player_is_shorter_and_lit_chemlight_longer_than_native(self):
        world = VisionWorld(day_time=2.0)
        self.assertAlmostEqual(0.9 * 0.75, self.call(world, Player(held=NonLight())), places=5)
        self.assertGreater(self.call(world, Player(held=PortableGasLamp(working=True))), f32(0.9))
        self.assertAlmostEqual(0.9 * 0.6, self.call(world, Player(held=NonLight(), coef=0.1)), places=5)


class NoiseEmitterBehavior(unittest.TestCase):
    def test_server_emits_once_with_config_path_actor_and_actor_position(self):
        world = NoiseWorld()
        player = Player()
        world.ns["HCSearchNoise"].Emit(player)
        self.assertEqual(1, len(world.params))
        self.assertEqual(("load", NOISE_PATH), world.log[0])
        self.assertEqual([("emit", player, "synthetic-player-position", world.params[0])], world.emissions)
        self.assertEqual(2, len(world.log))

    def test_client_falls_back_silently_with_zero_downstream_calls(self):
        world = NoiseWorld(server=False)
        world.ns["HCSearchNoise"].Emit(Player())
        self.assertEqual([], world.log)
        self.assertEqual([], world.params)
        self.assertEqual(["IsServer"], world.game.reads)

    def test_dead_null_missing_system_or_missing_game_are_silent(self):
        for kwargs, player in (({}, Player(alive=False)), ({}, None),
                               ({"noise_system": False}, Player()), ({"game": False}, Player())):
            world = NoiseWorld(**kwargs)
            world.ns["HCSearchNoise"].Emit(player)
            self.assertEqual([], world.log, kwargs)
            self.assertEqual([], world.params, kwargs)

    def test_config_path_constant_is_the_vanilla_reference(self):
        self.assertEqual(NOISE_PATH, NoiseWorld().ns["HCSearchNoise"].NOISE_PATH)


class NoisePolicyBehavior(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = NoiseWorld().ns["HCSearchNoisePolicy"]

    def test_given_commit_took_site_from_open_to_complete_then_one_emission(self):
        self.assertTrue(self.policy.ShouldEmit(0, 2))

    def test_given_refusal_cancel_stopped_or_repeat_then_no_emission(self):
        # Phase meanings from HCInteriorModule.CommitSearch: 0 open, 1 reserved,
        # 2 complete, 3 stopped/unavailable. A commit that did not move 0 -> 2
        # (refused, failed, cancelled before commit, or already complete) is silent.
        for before, after in ((0, 0), (0, 1), (0, 3), (1, 2), (2, 2), (3, 3), (-1, 2), (0, -1), (2, 0)):
            self.assertFalse(self.policy.ShouldEmit(before, after), (before, after))

    def test_given_either_phase_alone_matching_then_no_emission(self):
        self.assertFalse(self.policy.ShouldEmit(0, 1))
        self.assertFalse(self.policy.ShouldEmit(1, 2))


class NoiseCommitBehavior(unittest.TestCase):
    def committed(self, world, phase, before, player):
        action = NoiseWorld.Action(phase, player)
        world.ns["HCSearchNoise"].OnCommitted(action, before)
        return action

    def test_phase_of_reads_the_bound_site_or_minus_one(self):
        world = NoiseWorld()
        phase_of = world.ns["HCSearchNoise"].PhaseOf
        self.assertEqual(2, phase_of(NoiseWorld.Action(2, Player())))
        self.assertEqual(-1, phase_of(NoiseWorld.Action(None, Player())))
        self.assertEqual(-1, phase_of(object()))
        self.assertEqual(-1, phase_of(None))

    def test_completed_search_emits_exactly_one_noise_at_the_actor(self):
        world = NoiseWorld()
        player = Player()
        self.committed(world, 2, 0, player)
        self.assertEqual(1, len(world.emissions))
        self.assertIs(player, world.emissions[0][1])

    def test_refusal_failure_repeat_cancel_stop_and_unbound_site_are_silent(self):
        world = NoiseWorld()
        for before, after in ((0, 0), (0, 1), (1, 1), (1, 2), (0, 3), (2, 2), (3, 3)):
            self.committed(world, after, before, Player())
        self.committed(world, None, 0, Player())
        world.ns["HCSearchNoise"].OnCommitted(None, 0)
        self.assertEqual([], world.log)

    def test_client_completion_stays_silent_even_when_the_site_completed(self):
        world = NoiseWorld(server=False)
        self.committed(world, 2, 0, Player())
        self.assertEqual([], world.log)


class ActionHookBehavior(unittest.TestCase):
    """HCActionSearchInterior.OnFinishProgressServer executed with a synthetic
    HCInteriorsModule; CommitSearch itself is a synthetic stand-in, never engine proof."""

    def run_hook(self, commit_to, phase=0, module_present=True, server=True):
        world = NoiseWorld(server=server)
        order = []
        action = NoiseWorld.Action(phase, Player())
        phase_seen = []

        class Module:
            def CommitSearch(self, action_data):
                phase_seen.append(action_data.Site.Phase)
                order.append("commit")
                action_data.Site.Phase = commit_to

        module = Module()
        natives = {"ActionContinuousBase": object, "HCSearchNoise": world.ns["HCSearchNoise"],
                   "HCInteriorsModule": type("HCInteriorsModule", (), {
                       "Get": staticmethod(lambda: module if module_present else None)})}
        ns = execute(ACTION, {"HCActionSearchInterior": {"OnFinishProgressServer"}}, natives)
        world.ns["HCSearchNoise"].Emit = staticmethod(
            lambda player, emit=world.ns["HCSearchNoise"].Emit: (order.append("emit"), emit(player)))
        ns["HCActionSearchInterior"]().OnFinishProgressServer(action)
        return world, order, phase_seen

    def test_completing_commit_emits_exactly_once_after_the_commit(self):
        world, order, seen = self.run_hook(commit_to=2)
        self.assertEqual(["commit", "emit"], order)
        self.assertEqual([0], seen)
        self.assertEqual(1, len(world.emissions))

    def test_refused_or_failed_commit_is_silent(self):
        for commit_to in (0, 1, 3):
            world, order, _ = self.run_hook(commit_to=commit_to)
            self.assertEqual(["commit"], order, commit_to)
            self.assertEqual([], world.emissions, commit_to)

    def test_already_complete_repeat_is_silent(self):
        world, order, _ = self.run_hook(commit_to=2, phase=2)
        self.assertEqual(["commit"], order)
        self.assertEqual([], world.emissions)

    def test_missing_module_commits_nothing_and_emits_nothing(self):
        world, order, _ = self.run_hook(commit_to=2, module_present=False)
        self.assertEqual([], order)
        self.assertEqual([], world.emissions)

    def test_client_side_completion_emits_nothing(self):
        world, order, _ = self.run_hook(commit_to=2, server=False)
        self.assertEqual(["commit", "emit"], order)  # the emitter is asked, and refuses on a client
        self.assertEqual([], world.log)
        self.assertEqual([], world.params)


class SourceShape(unittest.TestCase):
    """Authored-source shape that execution cannot show: engine prototype
    names, unreadable private members and compile-rejected statement forms."""

    @classmethod
    def setUpClass(cls):
        cls.source = VISION.read_text()
        cls.action = ACTION.read_text()

    def test_open_by_default_disable_marker_path_and_wording(self):
        qual = class_text(VISION, "HCInfectedVisionQualification")
        self.assertRegex(body(str(VISION), "Qualified"), r"return false;")
        self.assertIn('!FileExist("%s")' % MARKER, qual)
        self.assertNotIn("infected_vision.enable", qual)
        self.assertEqual(1, qual.count("FileExist("))
        self.assertIn("EXPERIMENTAL", qual)
        self.assertIn("runtime acceptance PENDING", qual)

    def test_override_matches_engine_prototype_names(self):
        self.assertIn("modded class AITargetCallbacksPlayer", self.source)
        self.assertIn("override float GetMaxVisionRangeModifier(EntityAI pApplicant)", self.source)
        self.assertIn("super.GetMaxVisionRangeModifier(pApplicant)", self.source)

    def test_player_comes_from_own_constructor_capture_never_private_m_player(self):
        # AITargetCallbacksPlayer.c:5 declares m_Player private; a modded class
        # cannot read it, so the player is captured in a modded constructor.
        self.assertNotRegex(strip_comments(self.source), r"\bm_Player\b")
        modded = class_text(VISION, "AITargetCallbacksPlayer")
        self.assertIn("protected PlayerBase m_HCVisionPlayer;", modded)
        self.assertIn("void AITargetCallbacksPlayer(PlayerBase pPlayer)", modded)

    def test_hot_path_allocates_nothing_and_reads_only_target_local_state(self):
        for method in ("GetMaxVisionRangeModifier", "PlayerFactor", "LitItem", "HasLitLight"):
            text = strip_comments(body(str(VISION), method))
            self.assertNotIn("new ", text, method)
            self.assertNotIn("FileExist", text, method)
            self.assertNotIn("GetGame().GetPlayers", text, method)
            self.assertNotIn("GetObjectsAtPosition", text, method)
            self.assertNotIn("pApplicant.", text, method)

    def test_noise_uses_the_vanilla_native_pattern_only(self):
        text = strip_comments(NOISE.read_text())
        self.assertIn('"%s"' % NOISE_PATH, text)
        self.assertIn("GetGame().GetNoiseSystem()", text)
        self.assertEqual(1, text.count(".AddNoisePos("))
        self.assertNotIn(".AddNoiseTarget(", text)
        self.assertNotIn(".AddNoise(", text)

    def test_action_hook_lives_only_in_the_server_completion_override(self):
        for hook in ("OnStartServer", "OnEndServer", "ActionCondition", "ActionConditionContinue"):
            self.assertNotIn("HCSearchNoise", strip_comments(body(str(ACTION), hook)), hook)
        self.assertEqual(2, strip_comments(self.action).count("HCSearchNoise."))

    def test_crafting_salvage_files_are_untouched_by_noise_work(self):
        for path in (SCRIPTS / "Crafting").glob("*.c"):
            self.assertNotIn("HCSearchNoise", path.read_text(), path.name)

    def test_no_forbidden_enforce_shapes(self):
        for path in (VISION, NOISE):
            text = strip_comments(path.read_text())
            self.assertNotRegex(text, r"\?[^\n:]*:", path.name)  # no ternary
            for line in text.splitlines():
                self.assertFalse(line.lstrip().startswith(("||", "&&")), line)
                self.assertLessEqual(line.count("+"), 8, line)

    def test_no_personal_home_path_in_sources(self):
        for path in (VISION, NOISE, Path(__file__)):
            self.assertNotRegex(path.read_text(), r"/home/[a-z]")


if __name__ == "__main__":
    unittest.main()
