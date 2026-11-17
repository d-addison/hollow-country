"""Generate an isolated stamina transport experiment; never launch DayZ."""
import argparse
import hashlib
import json
from pathlib import Path
import re

INTERFACES = {
    '1_Core/param.c': ('class Param1<Class T1>', 'bool Serialize(Serializer ctx)',
                       'bool Deserializer(Serializer ctx)', 'return ctx.Write(param1)',
                       'return ctx.Read(param1)'),
    '1_Core/proto/Serializer.c': ('class Serializer', 'proto bool Write(void value_out)',
                                 'proto bool Read(void value_in)'),
    '3_Game/gameplay.c': ('class JsonSerializer', 'WriteToString',
                          'ReadFromString', 'class ScriptReadWriteContext',
                          'GetWriteContext', 'GetReadContext', 'class ScriptRPC'),
    '3_Game/CfgGameplayDataJson.c': ('class CfgGameplayJson',
                                    'class ITEM_StaminaData', 'staminaMax',
                                    'ref ITEM_StaminaData StaminaData'),
    '3_Game/CfgGameplayHandler.c': ('static float GetStaminaMax()',
                                   'static void SyncDataSendEx',
                                   'Param1<CfgGameplayJson>', 'static void OnRPC'),
    '3_Game/DayZGame.c': ('override void OnRPC(PlayerIdentity sender',
                         'case ERPCs.RPC_CFG_GAMEPLAY_SYNC:'),
    '5_Mission/mission/missionServer.c': ('void OnClientReadyEvent',
                                         'OnClientPrepareEvent'),
}

LOCAL = r'''
// DISPOSABLE experiment. These fields never enable HC stamina gameplay.
modded class ITEM_StaminaData
{
    int HCProbeSchema = 0;
    float HCProbeExertion = 1.0;
    float HCProbeRecovery = 1.0;
}

modded class CfgGameplayHandler
{
    // New static member only: does NOT claim static override interception.
    static float HCProbeStaticWrapper()
    {
        return GetStaminaMax();
    }
}

class HCStaminaTransportProbe
{
    static CfgGameplayJson Fixture()
    {
        CfgGameplayJson data = new CfgGameplayJson;
        ITEM_StaminaData item = new ITEM_StaminaData;
        item.staminaMax = 147.25;
        item.HCProbeSchema = 900001;
        item.HCProbeExertion = 0.5;
        item.HCProbeRecovery = 1.75;
        data.PlayerData.StaminaData = item;
        return data;
    }

    // Diagnostic tolerance only: finite nonnegative fields, absolute + relative.
    static bool Near(float actual, float expected)
    {
        if (!(actual >= 0 && actual <= 10000) || !(expected >= 0 && expected <= 10000))
            return false;
        return Math.AbsFloat(actual - expected) <= 0.00002 + 0.00002 * Math.AbsFloat(expected);
    }

    static bool Equal(CfgGameplayJson data)
    {
        if (!data || !data.PlayerData || !data.PlayerData.StaminaData)
            return false;
        ITEM_StaminaData item = data.PlayerData.StaminaData;
        return Near(item.staminaMax, 147.25) && item.HCProbeSchema == 900001 && Near(item.HCProbeExertion, 0.5) && Near(item.HCProbeRecovery, 1.75);
    }

    static void ContextScalar(bool paramAPI)
    {
        ScriptReadWriteContext buffer = new ScriptReadWriteContext;
        ParamsWriteContext writer = buffer.GetWriteContext();
        Param1<float> packet = new Param1<float>(147.25);
        Param1<float> copy = new Param1<float>(-1);
        bool writerOK = false;
        if (writer && paramAPI) writerOK = packet.Serialize(writer);
        else if (writer) writerOK = writer.Write(packet);
        ParamsReadContext reader = buffer.GetReadContext();
        bool readerOK = false;
        if (writerOK && reader && paramAPI) readerOK = copy.Deserializer(reader);
        else if (writerOK && reader) readerOK = reader.Read(copy);
        string name = "scalar-wrapper";
        if (paramAPI) name = "scalar-param";
        Print("[HC Stamina Transport] CONTROL " + name + " writer=" + writerOK + " reader=" + readerOK + " fields=value=" + copy.param1);
    }

    static bool ContextCfg(string name, CfgGameplayJson source, bool paramAPI)
    {
        ScriptReadWriteContext buffer = new ScriptReadWriteContext;
        ParamsWriteContext writer = buffer.GetWriteContext();
        Param1<CfgGameplayJson> packet = new Param1<CfgGameplayJson>(source);
        Param1<CfgGameplayJson> copy = new Param1<CfgGameplayJson>(null);
        bool writerOK = false;
        if (writer && paramAPI) writerOK = packet.Serialize(writer);
        else if (writer) writerOK = writer.Write(packet);
        ParamsReadContext reader = buffer.GetReadContext();
        bool readerOK = false;
        if (writerOK && reader && paramAPI) readerOK = copy.Deserializer(reader);
        else if (writerOK && reader) readerOK = reader.Read(copy);
        float cap = -1;
        int schema = -1;
        float exertion = -1;
        float recovery = -1;
        if (copy.param1 && copy.param1.PlayerData && copy.param1.PlayerData.StaminaData)
        {
            ITEM_StaminaData item = copy.param1.PlayerData.StaminaData;
            cap = item.staminaMax;
            schema = item.HCProbeSchema;
            exertion = item.HCProbeExertion;
            recovery = item.HCProbeRecovery;
        }
        Print("[HC Stamina Transport] CONTROL " + name + " writer=" + writerOK + " reader=" + readerOK + " fields=max=" + cap + " schema=" + schema + " exertion=" + exertion + " recovery=" + recovery);
        ITEM_StaminaData expected = source.PlayerData.StaminaData;
        return writerOK && readerOK && Near(cap, expected.staminaMax) && schema == expected.HCProbeSchema && Near(exertion, expected.HCProbeExertion) && Near(recovery, expected.HCProbeRecovery);
    }

    static void Local()
    {
        CfgGameplayJson source = Fixture();
        CfgGameplayJson decoded = new CfgGameplayJson;
        JsonSerializer json = new JsonSerializer;
        string text;
        string error;
        bool jsonOK = json.WriteToString(source, false, text);
        if (jsonOK)
            jsonOK = json.ReadFromString(decoded, text, error) && Equal(decoded);

        ContextScalar(false);
        ContextScalar(true);
        CfgGameplayJson baseline = new CfgGameplayJson;
        baseline.PlayerData.StaminaData.staminaMax = 147.25;
        ContextCfg("defaults-wrapper", baseline, false);
        ContextCfg("defaults-param", baseline, true);
        ContextCfg("custom-wrapper", source, false);
        bool contextOK = ContextCfg("custom-param", source, true);
        bool staticOK = CfgGameplayHandler.HCProbeStaticWrapper() == CfgGameplayHandler.GetStaminaMax();
        Print("[HC Stamina Transport] LOCAL json=" + jsonOK + " context=" + contextOK + " static=" + staticOK);
    }
}
'''

RPC = r'''
// Opt-in, matched-build experiment. At most two recipients and one ACK each.
// This uses the native configuration packet shape on separate diagnostic RPCs.
// It does NOT test interception of RPC_CFG_GAMEPLAY_SYNC or activation ordering.
class HCStaminaProbeWire
{
    static ref array<PlayerIdentity> Seen = new array<PlayerIdentity>;
    static ref array<PlayerIdentity> Acked = new array<PlayerIdentity>;
    static bool ClientSeen;

    static void SendTo(PlayerIdentity identity)
    {
        if (!GetGame().IsServer() || !identity || Seen.Count() >= 2 || Seen.Find(identity) >= 0)
            return;
        Seen.Insert(identity);
        Param1<CfgGameplayJson> packet = new Param1<CfgGameplayJson>(HCStaminaTransportProbe.Fixture());
        ScriptRPC rpc = new ScriptRPC;
        if (!rpc.Write(packet))
        {
            Print("[HC Stamina Transport] RPC_SEND payload=0");
            return;
        }
        rpc.Send(null, 4853791, true, identity);
    }

    static void Receive(PlayerIdentity sender, Object target, int rpcType, ParamsReadContext ctx)
    {
        if (GetGame().IsServer())
        {
            if (target || rpcType != 4853792 || !sender)
                return;
            if (Seen.Find(sender) < 0 || Acked.Find(sender) >= 0)
                return;
            // Consume the single diagnostic attempt even if decoding fails.
            Acked.Insert(sender);
            Param1<CfgGameplayJson> reply = new Param1<CfgGameplayJson>(null);
            bool serverOK = ctx.Read(reply) && reply && HCStaminaTransportProbe.Equal(reply.param1);
            Print("[HC Stamina Transport] RPC_SERVER payload=" + serverOK);
            return;
        }
        if (rpcType != 4853791 || sender || target || ClientSeen)
            return;
        ClientSeen = true;
        Param1<CfgGameplayJson> packet = new Param1<CfgGameplayJson>(null);
        bool clientOK = ctx.Read(packet) && packet && HCStaminaTransportProbe.Equal(packet.param1);
        Print("[HC Stamina Transport] RPC_CLIENT payload=" + clientOK);
        if (!clientOK)
            return;
        ScriptRPC rpc = new ScriptRPC;
        if (!rpc.Write(packet))
        {
            Print("[HC Stamina Transport] RPC_ACK payload=0");
            return;
        }
        rpc.Send(null, 4853792, true);
    }
}

modded class DayZGame
{
    override void OnRPC(PlayerIdentity sender, Object target, int rpcType, ParamsReadContext ctx)
    {
        super.OnRPC(sender, target, rpcType, ctx);
        if (rpcType == 4853791 || rpcType == 4853792)
            HCStaminaProbeWire.Receive(sender, target, rpcType, ctx);
    }
}
'''

MISSION = r'''
// Only load this addon into an explicitly disposable diagnostic mission.
modded class MissionServer
{
    protected bool m_HCStaminaTransportExecuted;
    override void OnInit()
    {
        super.OnInit();
        if (!GetGame().IsServer() || m_HCStaminaTransportExecuted)
            return;
        m_HCStaminaTransportExecuted = true;
        HCStaminaTransportProbe.Local();
    }
@READY@
}
'''

READY = r'''
    override void OnClientReadyEvent(PlayerIdentity identity, PlayerBase player)
    {
        super.OnClientReadyEvent(identity, player);
        HCStaminaProbeWire.SendTo(identity);
    }
'''

CONFIG = r'''
class CfgPatches
{
    class HCStaminaTransportProbe
    {
        units[] = {};
        weapons[] = {};
        requiredVersion = 0.1;
        requiredAddons[] = {"DZ_Data", "DZ_Scripts"};
    };
};
class CfgMods
{
    class HCStaminaTransportProbe
    {
        dir = "HCStaminaTransportProbe";
        name = "HC disposable stamina transport experiment";
        type = "mod";
        dependencies[] = {"Game", "World", "Mission"};
        class defs
        {
            class gameScriptModule
            {
                value = "";
                files[] = {"HCStaminaTransportProbe/scripts/3_Game"};
            };
            class missionScriptModule
            {
                value = "";
                files[] = {"HCStaminaTransportProbe/scripts/5_Mission"};
            };
        };
    };
};
'''


def _safe(value):
    path = Path(value).absolute()
    if '..' in path.parts or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('parent traversal and symlink paths are forbidden')
    if any(p.casefold() in {'.git', 'steamapps'} for p in path.parts):
        raise ValueError('use an isolated location outside Steam and Git')
    return path


def prepare(output, native_root, *, matched_rpc=False):
    """Write source artifacts only; source inspection is not runtime proof."""
    output, native_root = _safe(output), _safe(native_root)
    checkout = Path(__file__).absolute().parents[2]
    if output == checkout or checkout in output.parents:
        raise ValueError('generated experiment must be outside the checkout')
    if output.exists():
        raise ValueError('output must be fresh; existing artifacts are preserved')
    if not native_root.is_dir():
        raise ValueError('installed native script directory required')
    native_sources = {}
    for name, tokens in INTERFACES.items():
        path = _safe(native_root / name)
        if not path.is_file():
            raise ValueError('missing native source: ' + name)
        with path.open('rb') as stream:
            blob = stream.read(1048577)
        if len(blob) > 1048576:
            raise ValueError('native interface file exceeds one MiB: ' + name)
        text = ' '.join(blob.decode('utf-8-sig').split())
        if any(' '.join(token.split()) not in text for token in tokens):
            raise ValueError('native interface mismatch: ' + name)
        native_sources[name] = hashlib.sha256(blob).hexdigest()
    sources = {
        'config.cpp': CONFIG,
        '$PBOPREFIX$': 'HCStaminaTransportProbe',
        'scripts/3_Game/HCStaminaTransportProbe.c': LOCAL + (RPC if matched_rpc else ''),
        'scripts/5_Mission/HCStaminaTransportMission.c':
            MISSION.replace('@READY@', READY if matched_rpc else ''),
    }
    result = {
        'schema_version': 1,
        'kind': 'disposable-stamina-transport-source-probe',
        'execution': 'not-run',
        'runtime_acceptance': 'pending',
        'rpc_probe': 'opt-in-matched-pair' if matched_rpc else 'disabled',
        'native_sources': native_sources,
        'generator_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'generated_sources': {
            name: hashlib.sha256(text.encode('utf-8')).hexdigest()
            for name, text in sources.items()
        },
        'integration': {
            'standalone_config': 'recipe only; not evidence of the loaded configuration',
            'existing_addon': 'the two generated script files may instead be injected into a frozen diagnostic PBO using its existing prefix/config',
            'required_provenance': [
                'actual loaded PBO SHA256', 'actual config and mission hashes',
                'native executable build/hash', 'engine logs',
                'same generated script hashes on any matched client and server',
            ],
        },
        'limitations': [
            'No compilation, engine launch, client connection or subscription performed.',
            'Native source tokens and hashes establish inspected interfaces only.',
            'New static member wrapping is tested; original static-method interception is unproven.',
            'Local JSON/context markers do not establish network delivery.',
            'Diagnostic RPCs use Param1<CfgGameplayJson>; the built-in gameplay-config RPC is not intercepted or exercised.',
            'Native configuration-file loading and installation before prediction remain unproven.',
            'Synthetic native configuration constructors may register temporary items; use only a fresh disposable process.',
            'Matched RPC mode permits at most two ready-event recipients and one ACK attempt per recipient.',
            'Probe RPC IDs require collision review against the actual loaded mod set.',
            'No production stamina settings, gameplay enablement or activation changes are made.',
        ],
    }
    output.mkdir(parents=True)
    for name, text in sources.items():
        path = output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('x', encoding='utf-8', newline='\n') as stream:
            stream.write(text)
    with (output / 'manifest.json').open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    return result


def observe(log):
    """Classify unverified log markers; never grant runtime acceptance."""
    if not isinstance(log, str) or len(log) > 4 * 1024 * 1024:
        raise ValueError('expected at most four MiB of log text')
    result = {
        'observation': 'unknown',
        'network_roundtrip': 'unknown',
        'runtime_acceptance': 'pending',
    }
    if re.search(r"SCRIPT\s*\(E\)|Can't compile|Cannot compile", log):
        result['observation'] = 'compiler-error'
        return result
    flag = r'(1|0|true|false)'
    local = re.findall(
        r'\[HC Stamina Transport\] LOCAL json=' + flag +
        r' context=' + flag + r' static=' + flag, log, re.IGNORECASE)
    if local:
        ok = all(all(value.lower() in {'1', 'true'} for value in row)
                 for row in local)
        result['observation'] = 'local-marker-only' if ok else 'local-failure-marker'
    result['local_controls'] = []
    for name, writer, reader, fields in re.findall(
            r'\[HC Stamina Transport\] CONTROL ([a-z-]+) writer=' + flag +
            r' reader=' + flag + r' fields=([^\r\n]{1,240})', log, re.IGNORECASE):
        result['local_controls'].append({
            'case': name, 'writer_ok': writer.lower() in {'1', 'true'},
            'reader_ok': reader.lower() in {'1', 'true'}, 'fields': fields,
        })
    remote = {}
    for stage, value in re.findall(
            r'\[HC Stamina Transport\] RPC_(CLIENT|SERVER|SEND|ACK) payload=' +
            flag, log, re.IGNORECASE):
        remote.setdefault(stage.upper(), []).append(value.lower() in {'1', 'true'})
    if remote and not all(all(values) for values in remote.values()):
        result['network_roundtrip'] = 'failure-marker'
    elif remote.get('CLIENT') and remote.get('SERVER'):
        result['network_roundtrip'] = 'unverified-pair-markers'
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output')
    parser.add_argument('--scripts-root', required=True)
    parser.add_argument('--matched-rpc', action='store_true')
    args = parser.parse_args()
    result = prepare(args.output, args.scripts_root, matched_rpc=args.matched_rpc)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
