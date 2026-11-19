// E1: publication points for the HCWorldIncidents registry. Every hook runs super FIRST and then
// makes ONE call; none changes native behavior and none creates, moves or deletes an entity.
// Native scripts-1.30.164289 (4_World/Classes/ContaminatedArea unless noted):
//   EffectArea.c:54 m_Position, :61 m_Radius (public fields), :197-213 InitZone sets m_Position then
//   calls InitZoneServer on the server, :216 InitZoneServer(), :549 EEDelete(EntityAI);
//   ContaminatedArea.c:1 ContaminatedArea_Base (does NOT override InitZoneServer; it overrides EEDelete
//   at :24, super first), :33 ContaminatedArea_Static (InitZoneServer :56-63 calls super);
//   ContaminatedArea_DynamicBase.c:30-33 GetRemainingTime(), :78-85 InitZoneServer (calls super);
//   ContaminatedArea_Dynamic.c InitZoneServer after the artillery delay (super first, :163-167);
//   ContaminatedArea_Local.c radius 10, lifetime 360, InitZone called directly from SetupZoneData.
//   One hook on ContaminatedArea_Base therefore sees static, dynamic and local zones.
//   4_World/Entities/Building/CrashBase.c:15-19 EEOnCECreate (super then the RPC sound), :46-53 EEDelete
//   (does not call super, so the retire call runs after the existing HC link and native delete).
//   3_Game/Entities/Object.c:287 GetPosition, :511 IsKindOf; EntityAI.c EEDelete(EntityAI).
// Wreck_Mi8 (cold wreck, no smoke particle) and Wreck_Mi8_Crashed are unrelated siblings, so
// IsKindOf("Wreck_Mi8") separates the cold wreck. Airdrops: no native hook exists in 1.30.
// Other danger areas (geyser, hot spring, volcanic) are not gas zones and are not published here.
// Runtime acceptance PENDING.
class HCIncidentSources
{
    static void HCZone(EffectArea area)
    {
        if (!area || !GetGame() || !GetGame().IsServer()) { return; }
        string kind = "gas_dynamic";
        if (ContaminatedArea_Local.Cast(area)) { kind = "gas_local"; }
        else if (ContaminatedArea_Static.Cast(area)) { kind = "gas_static"; }
        int life = 0;
        ContaminatedArea_DynamicBase timed = ContaminatedArea_DynamicBase.Cast(area);
        if (timed) { life = Math.Floor(timed.GetRemainingTime()); }
        if (life < 0) { life = 0; }
        HCWorldIncidents.HCPublish(kind, area.m_Position, area.m_Radius, life, area);
    }

    static string HCCrashKind(CrashBase wreck)
    {
        if (wreck.IsKindOf("Wreck_Mi8")) { return "crash_cold"; }
        return "crash";
    }

    static void HCCrash(CrashBase wreck)
    {
        if (!wreck || !GetGame() || !GetGame().IsServer()) { return; }
        HCWorldIncidents.HCPublish(HCIncidentSources.HCCrashKind(wreck), wreck.GetPosition(), 0, 0, wreck);
    }
}

modded class ContaminatedArea_Base
{
    override void InitZoneServer()
    {
        super.InitZoneServer();
        HCIncidentSources.HCZone(this);
    }

    override void EEDelete(EntityAI parent)
    {
        super.EEDelete(parent);
        HCWorldIncidents.HCRetire(this);
    }
}

modded class CrashBase
{
    override void EEOnCECreate()
    {
        super.EEOnCECreate();
        HCIncidentSources.HCCrash(this);
    }

    override void EEDelete(EntityAI parent)
    {
        super.EEDelete(parent);
        HCWorldIncidents.HCRetire(this);
    }
}

// Subscribes to the existing world-fact ledger without editing its publishers. Only the kinds the
// incident policy names become incidents; the original verdict is returned unchanged.
modded class HCWorldModule
{
    override bool AddFact(string kind, string place, int severity)
    {
        bool added = super.AddFact(kind, place, severity);
        if (!added) { return false; }
        HCWorldPlace anchor = m_Data.Place(place);
        if (!anchor) { return true; }
        string faction = "";
        foreach (HCWorldHoldout holdout : m_Data.Holdouts)
        {
            if (holdout.PlaceId == anchor.Id) { faction = holdout.FactionId; }
        }
        HCWorldIncidents.HCPublishFact(kind, anchor.Position, severity, faction);
        return true;
    }
}
