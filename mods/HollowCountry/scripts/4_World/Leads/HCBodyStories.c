// #116. Native evidence: scripts-1.30.164289/
// 3_Game/Global/Game.c:703,705,945 (create/delete/players),
// 3_Game/Entities/Object.c:287 (GetPosition),
// 1_Core/proto/EnMath.c:38 (RandomInt),
// 1_Core/proto/EnScript.c:877,902,906 (maps),
// 3_Game/Global/Game.c:612 (ConfigIsExisting),
// 3_Game/Entities/EntityAI.c:885 (GetHierarchyParent).
// 3_Game/Entities/Object.c:517 (IsAlive), Man.c:21 (GetIdentity).
// StaticObj_Dead_pile1 is a vanilla corpse prop in structures_specific.pbo
// (installed config census 2026-11-17); no survivor AI, loadout or third-party
// assets. Its scene's single Paper remains beside the prop, with no other loot.
// HCObserverTransitionGate.CanTransition(pos, 500) (Infected/HCObserverTransitionGate.c:266)
// is consulted before a body is placed or removed, so no player sees it appear.
class HCBodyStories : HCModule
{
    protected static HCBodyStories s_Instance;
    protected ref HCLeadStore m_Store;
    protected ref map<string, Object> m_Props = new map<string, Object>();
    protected float m_Elapsed;
    protected int m_Cursor;
    protected bool m_AdmissionPrinted;

    static HCBodyStories Get() { return s_Instance; }
    override string GetName() { return "BodyStories"; }
    override bool IsEnabled(HCSettings settings) { return settings && settings.EnableLeads; }
    override void OnStart(HCSettings settings)
    {
        if (!IsEnabled(settings) || s_Instance) { return; }
        if (!m_AdmissionPrinted)
        {
            Print(HCV2Admission.Line("BodyStories", true, "EXP-S3", HCV2Gates.Qualified("EXP-S3")));
            m_AdmissionPrinted = true;
        }
        m_Store = HCLeadStore.Get();
        if (!m_Store || !m_Store.Healthy()) { return; }
        s_Instance = this;
        LogCount();
    }

    void LogCount()
    {
        Print("[HollowCountry] V2 body stories placed=" + m_Props.Count().ToString() + "/3");
    }

    // Only call with a reviewed scene/shelter anchor, never an NPC/player
    // position. The existing note is the entire story inventory.
    void Consider(string sceneId, vector position, HCWorldLead lead)
    {
        if (!m_Store || !m_Store.Healthy() || m_Store.Data.Bodies.Count() >= 3 || !HCWorldLimits.Position(position) || !HCLeadPolicy.Valid(lead)) { return; }
        HCWorldModule world = HCWorldModule.Get();
        HCNoteLedger notes = HCNoteLedger.Get();
        if (!world || !notes || !notes.Scene(sceneId)) { return; }
        foreach (HCBodyStoryRow existing : m_Store.Data.Bodies)
        {
            if (existing.SceneId == sceneId) { return; }
        }
        // One rare attempt per newly created scene note; no retry loop/alerts.
        if (Math.RandomInt(0, 10) != 0) { return; }
        string place = world.NearestPlace(position);
        HCWorldData catalog = HCWorldData.Fresh(1);
        HCWorldPlace anchor = catalog.Place(place);
        if (!anchor) { return; }
        HCBodyStoryRow story = new HCBodyStoryRow;
        story.Id = m_Store.NextId("body");
        story.SceneId = sceneId;
        story.PlaceId = anchor.Id;
        story.Position = position;
        story.CreatedAt = HCWorldClock.UTC();
        story.Expires = lead.Expires;
        if (story.Expires <= story.CreatedAt) { return; }
        m_Store.Data.Bodies.Insert(story);
        m_Store.Save();
    }

    void Place(HCBodyStoryRow story)
    {
        if (!HCObserverTransitionGate.CanTransition(story.Position, 500)) { return; }
        HCNoteLedger notes = HCNoteLedger.Get();
        if (!notes) { return; }
        HCLeadNote entry = notes.Scene(story.SceneId);
        if (!entry) { return; }
        Paper paper = HCNoteEntities.Find(entry.Row.Id);
        // Never attach a corpse to a scene after its note has been carried away.
        if (!paper || paper.GetHierarchyParent()) { return; }
        vector notePos = paper.GetPosition();
        float dx = notePos[0] - story.Position[0];
        float dz = notePos[2] - story.Position[2];
        if (dx * dx + dz * dz > 4) { return; }
        if (!GetGame().ConfigIsExisting("CfgVehicles StaticObj_Dead_pile1")) { return; }
        // Reserve the attempt before creating a static prop. Uncertain attempts
        // are not replayed on restart, and count toward the three-body cap.
        story.Phase = 1;
        if (!m_Store.Save()) { return; }
        Object prop = GetGame().CreateObjectEx("StaticObj_Dead_pile1", story.Position, ECE_PLACE_ON_SURFACE);
        if (prop) { m_Props.Set(story.Id, prop); }
        LogCount();
    }

    void Approach(HCBodyStoryRow story, Object prop)
    {
        HCWorldModule world = HCWorldModule.Get();
        if (!prop || !world || story.Phase != 1) { return; }
        array<Man> players = new array<Man>();
        GetGame().GetPlayers(players);
        if (players.Count() > 32) { return; }
        foreach (Man observer : players)
        {
            if (!observer || !observer.IsAlive() || !observer.GetIdentity()) { continue; }
            vector position = observer.GetPosition();
            float dx = position[0] - story.Position[0];
            float dz = position[2] - story.Position[2];
            if (dx * dx + dz * dz > 900) { continue; }
            // At-most-once fact publication: a crash after this save may lose
            // the fact, but never republishes it or creates another prop/note.
            story.Phase = 2;
            if (m_Store.Save()) { world.AddFact("BODY_FOUND", story.PlaceId, 1); }
            return;
        }
    }

    override void OnTick(float deltaTime)
    {
        if (!m_Store || !m_Store.Healthy() || deltaTime <= 0) { return; }
        m_Elapsed += deltaTime;
        if (m_Elapsed < 20) { return; }
        m_Elapsed = 0;
        if (m_Store.Data.Bodies.Count() == 0) { return; }
        if (m_Cursor >= m_Store.Data.Bodies.Count()) { m_Cursor = 0; }
        HCBodyStoryRow story = m_Store.Data.Bodies[m_Cursor++];
        Object prop;
        m_Props.Find(story.Id, prop);
        if (story.Expires <= HCWorldClock.UTC())
        {
            // Review P2: a placed row whose non-persistent prop is gone (restart or failed
            // create) is released too, so expired rows never hold the three slots forever.
            if (story.Phase == 0 || !prop || HCObserverTransitionGate.CanTransition(story.Position, 500))
            {
                if (prop) { GetGame().ObjectDelete(prop); m_Props.Remove(story.Id); }
                m_Store.Data.Bodies.RemoveItem(story);
                if (m_Store.Save()) { LogCount(); }
            }
            return;
        }
        if (story.Phase == 0) { Place(story); }
        else { Approach(story, prop); }
    }

    override void OnStop() { s_Instance = null; }
}
