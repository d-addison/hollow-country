// E1 source adapters: super-first receipts, no polling or world mutation.
// Spec/plan/task: physical source -> bounded HCWorldIncidents -> member perception.
// Default ON; shared operator opt-out: acceptance/world_incidents.disable.
// All ranges, lifetimes, merge distance and caps come from HCWorldIncidentPolicy.
// Readiness remains HCWorldIncidents.HCGetOperationalStatus; no new module/slot.
// Native scripts-1.30.164289:
// 4_World/Entities/Grenade_Base/SmokeGrenadeBase.c:175 OnWorkStart (actual smoke,
// reached by HCSituationSignals.HCSmoke -> Unpin :158 -> OnActivateFinished :168).
// 4_World/Entities/Firearms/Weapon_Base.c:341 EEFired; its client effects are guarded
// at :345. 3_Game/Entities/EntityAI.c:4927 declares the engine fired callback.
// 3_Game/Entities/Object.c:287 GetPosition, :511 IsKindOf;
// 3_Game/Global/Game.c:1120 IsServer; 3_Game/gameplay.c:636 GetGame;
// 1_Core/proto/EnScript.c:380 Count; 1_Core/proto/EnDebug.c:96 Print.
// HCEventRuntime.Announce and HCNativeInfectedPack.Start are authored HC ports.
// No town/ledger anchors, synthetic shots, repeated frame publication or new timers.
// Gas and crash lifecycle sources already live in HCIncidentSources.c.
// No airdrop observer exists here; faction_clash data outcomes are not physical
// observations. Neither is converted into a fabricated incident. Runtime PENDING.
class E1IncidentSources
{
    protected static bool s_Logged;

    static void HCPublish(string kind, vector position, Object anchor)
    {
        if (!GetGame() || !GetGame().IsServer()) { return; }
        int incidentId = HCWorldIncidents.HCPublish(kind, position, 0, 0, anchor);
        if (incidentId > 0 && !E1IncidentSources.s_Logged)
        {
            E1IncidentSources.s_Logged = true;
            Print("[HC Incidents] E1_SOURCES admitted_unverified policy=shared runtime=PENDING");
            Print("[HC Incidents] E1_AIRDROP_OBSERVER_PENDING reason=no_existing_observer runtime=PENDING");
        }
    }
}

// The actual native work transition also covers player-deployed smoke. Publishing
// after Unpin alone would advertise smoke before activation completed. Snapshot,
// not a moving anchor: the stored location must not follow a later carrier.
modded class SmokeGrenadeBase
{
    override void OnWorkStart()
    {
        super.OnWorkStart();
        if (!GetGame() || !GetGame().IsServer()) { return; }
        E1IncidentSources.HCPublish("signal_smoke", GetPosition(), null);
    }
}

// One receipt per real engine fired callback. Location snapshots de-duplicate by
// kind/position; an anchored weapon would incorrectly merge later distant shots.
// Sound range/window (including suppressed shots) remains policy, unmeasured.
modded class Weapon_Base
{
    override void EEFired(int muzzleType, int mode, string ammoType)
    {
        super.EEFired(muzzleType, mode, ammoType);
        if (!GetGame() || !GetGame().IsServer() || IsKindOf("Archery_Base")) { return; }
        E1IncidentSources.HCPublish("gunfire", GetPosition(), null);
    }
}

// OK means the provider started AND the ACTIVE run was durably published. No
// incident on prepare failure, activation write failure or a participant join.
modded class HCEventRuntime
{
    override int Announce(HCEventMission mission, HCEventContext context)
    {
        int result = super.Announce(mission, context);
        if (result == HCEventCode.OK && mission)
        {
            E1IncidentSources.HCPublish("scene", mission.Source, null);
        }
        return result;
    }
}

// Accepted native cohort creation, not an adoption intent or remembered route.
// Search packs are individual investigations, not hordes. Use a live member's
// real position, never destination, navmesh sample, persisted anchor or clue.
modded class HCNativeInfectedPack
{
    override bool Start(array<HCInfectedActor> actors, vector destination, bool search, float now, float expires)
    {
        bool started = super.Start(actors, destination, search, now, expires);
        if (started && !search && actors && actors.Count() > 0)
        {
            HCInfectedActor first = actors[0];
            if (first && first.InfectedEntity)
            {
                E1IncidentSources.HCPublish("horde", first.InfectedEntity.GetPosition(), null);
            }
        }
        return started;
    }
}
