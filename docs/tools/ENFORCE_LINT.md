# Enforce lint rules

Run `python3 -B -m tools.validate.enforce_lint` with the installed scripts cache
supplied through `--native-scripts`. Findings are static evidence; a clean run
does not establish native compile or runtime acceptance.

## Member access (HC-E057)

An explicit `receiver.member` read, write or method call is rejected when its
static receiver type declares the member protected or private and the enclosing
class lacks access. Protected members allow the declaring class and subclasses;
private members allow only the declaring class. An inherited member retains its
original declaring class. Modded bodies belong to the same class. Static access
through a class name is checked too. Each field-chain step is checked separately,
so `held.Group.Count()` diagnoses the protected `Group` access.

Resolution uses explicit locals, parameters, fields, typedefs and field chains,
as in the existing receiver checks. It does not infer runtime subtypes, `auto`,
call returns, indexed elements or generic substitutions. Unknown receivers and
unknown declarations produce no access finding. The summary reports unresolved
receivers divided by all explicit member receivers; JSON exposes total, resolved
and unresolved counts in `member_receivers`. This is receiver coverage, not a
claim that every resolved receiver has a complete member table.

With an extracted native scripts cache, field and method access modifiers are
read from installed declarations; findings on those declarations carry
`native=True`. A names-only index supplies no access evidence. No existing
findings are waived for this rule.

## Rule list

| Rule | Check |
| --- | --- |
| HC-E001 | ternary operator (the native compiler rejects ?:) |
| HC-E002 | type used in a lower script layer than the one that defines it (3_Game cannot see 4_World) |
| HC-E003 | new assigned to a member that is not a strong ref (object is released at once) |
| HC-E004 | new inserted into a collection whose element type is not ref |
| HC-E005 | modded link calls a method that only another modded link of the class declares |
| HC-E006 | Substring on a receiver whose Length() the method never consults (Wrong parameter value) |
| HC-E007 | method named like a visible type (unqualified calls resolve to the type) |
| HC-E008 | unbalanced method attribute (the source model cannot inspect the declaration) |
| HC-E009 | variable named after a pinned engine type (native compile refusal) |
| HC-E010 | integer assigned to a FileHandle (native compile: Incompatible parameter); track open state in a bool |
| HC-E011 | Enforce keyword used as a variable, member or parameter name (native compile: Expected name, not a keyword) |
| HC-E012 | method absent from the declared receiver type and its visible ancestors/modded bodies |
| HC-E013 | type only defined in a higher script layer than its use |
| HC-E014 | modded class declared outside the script module of its original class |
| HC-E015 | unsupported map key or set element type (use int/string/typename/class types) |
| HC-E016 | FileHandle/FindFileHandle compared with null (use truthiness) |
| HC-E017 | vanilla storage override without an explicit migration-plan allowlist entry |
| HC-E018 | variable name shadows a type visible in this script module |
| HC-E019 | member declared only by a later file in the same modded-class chain |
| HC-E020 | string concatenation with too many + operands into a typed string (assignment, string parameter or return; Print is exempt) (native compile: Formula too complex); build it in steps with += |
| HC-E021 | line starts with a binary operator continuing the previous line (native compile: Unknown type / Syntax error) |
| HC-E022 | Expansion AI call outside HCXExpansionBridge.c (dependency invariant boundary) |
| HC-E023 | else is not adjacent to an if body; move the intervening statement outside the if/else chain |
| HC-E024 | typename cannot return null; declare an empty typename and return it |
| HC-E025 | method collides with a native global function or class and is called unqualified; rename it |
| HC-E026 | fresh unowned call result passed as an argument; hold it in a local first (build 161 crash) |
| HC-E027 | COT/CF/ExpansionStatic call outside its owned dependency bridge |
| HC-E028 | initializer must be a literal; a non-literal static const read as 0 natively (build 169) |
| HC-E029 | duplicate local declaration or local shadows a parameter (Enforce function scope is flat) |
| HC-E030 | boolean expression combines too many terms with inline string concatenation (native compile: Formula too complex); hold the string in a local first |
| HC-E031 | unguarded ConfigGet* read: check ConfigIsExisting first or go through HCConfigHelper (logs No entry / error value on a missing path) |
| HC-E032 | FindPath output array is null or never allocated (native FindPath dereferences it) |
| HC-E033 | navmesh query with a PGFilter that never had SetFlags (an empty filter matches no polygon) |
| HC-E034 | AIWorld.DeleteGroup without a living-member check (it destroys every agent still attached) |
| HC-E035 | StartCommand_ScriptInst on a DayZInfected (engine builds the command with null constructor arguments); use StartCommand_Script(new Command(this)) |
| HC-E036 | new X passed directly as an argument to a call that does not store it (the temporary has no owner) |
| HC-E037 | UpdatePathgraphRegionByObject refreshes a flat-Y region; use HCPathgraphRefresh bounds with explicit Y margins |
| HC-E038 | array.Remove(0) moves the LAST element into slot 0 (native EnScript.c Remove, unordered); use RemoveOrdered(0) or annotate "// HC-ORDER: unordered ok" |
| HC-E040 | use counter reached unconditionally from an init path (OnInit, OnStart, constructor, Load/Migrate/Restore, entity init); count from the gameplay path with HCUseGuarded |
| HC-E041 | Expansion group or agent stored outside the bridge (eAIGroup or eAIBase member/static/container element, or a raw provider m_Group read): keep an HCXAIGroupHold / HCXAIAgentHold handle and resolve it through the bridge |
| HC-E042 | method redefines or overrides a parent declaration with a different signature (missing override, parameter/return/static mismatch, or no parent method) |
| HC-E043 | method named like an engine name the compiler resolves itself (native compile: statement-form Wait( failed); rename it |
| HC-E044 | Enforce keyword used as a name (native compile: Expected name, not a keyword); tokenised, includes foreach slots and enum members |
| HC-E045 | bitwise or % operator inside a float expression (native compile: Unknown operator); compute it in int-only statements first |
| HC-E046 | field read on a typed receiver that has no such field (including parents and modded bodies) |
| HC-E047 | initializer must be a literal: non-static const, vector const or a static primitive that reads another class or constant (read as 0 natively, build 169) |
| HC-E048 | foreach iterates a call result directly (native VME NULL pointer to instance, #337); hold the collection in a typed local first |
| HC-E049 | modded class of an engine class the compiler refuses to mod (native compile: Engine class cannot be modded); hook the scripted subclass instead |
| HC-E050 | bare name resolves to no local, parameter, member of the class or its ancestors, global, class, enum or constant (native compile: Can't find variable; a renamed or removed field read by a subclass) |
| HC-E051 | assignment into an indexed slot whose index calls a function (native compile: Function definition inside block); hold the index in a local first |
| HC-E052 | GunPile and reach fixtures must use config compatibility, never weapon magazine/muzzle/chamber natives |
| HC-E053 | method overrides or redeclares an inherited proto method, or adds an overload of its native name (build 185: Multiple declaration of function); hook a script method instead |
| HC-E054 | two HC script RPC ids share a value; each RPC needs its own id |
| HC-E055 | test addon HCOwns fx_ command is absent from HCAdminCatalog; HCReceive rejects it before the provider |
| HC-E056 | PlayerIdentity script references compared; use HCPlayerIdentity.Same with non-empty GetId values |
| HC-E057 | protected or private member accessed outside its declaring class or permitted subclass |
| HC-L001 | Print of a bare variable (the engine logs "string name = '...'" instead of the text) |
| HC-O026 | unresolved call-result ownership; inspect the factory and hold fresh results in a local |
| HC-S001 | server commit point returns early without logging or telling the player why |
| HC-S002 | server gate returns false without a reason code, log line or player message |
| HC-S003 | client-predicted action whose server path never sends the player a refusal message |
| HC-S004 | literal engine/build version comparison without a Print or log in the same method |
| HC-S005 | JSON-loaded scalar has a nonzero initializer but no explicit zero/default guard |
| HC-S006 | registered HCModule subclass has no authored GetName override |
