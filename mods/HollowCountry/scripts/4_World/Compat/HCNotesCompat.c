// #232 variety packs: writable-notes pack compatibility. Vanilla classes only; the
// pack is detected at runtime by its config class, so a missing pack changes nothing.
// Native scripts-1.30.164289: 3_Game/Global/Game.c ConfigIsExisting/IsServer/IsMultiplayer,
// 4_World/Classes/Recipes/RecipeBase.c:479 CheckRecipe, 1_Core/proto/EnScript.c array
// Find/RemoveOrdered, 3_Game/Entities/Object.c GetType.
// Contract: lead notes (HCNoteLedger) stay read-only and intact. The note RPC drop,
// the write-action veto and the duplicate-action fold live next to the Paper hooks in
// HCNoteLedger.c; the recipe veto below keeps a lead note from being consumed.
class HCNotesCompat
{
    // 0 unknown, 1 present, 2 absent. A pack cannot appear mid-session.
    protected static int s_Present;

    static bool Present()
    {
        if (s_Present == 0)
        {
            s_Present = 2;
            if (GetGame() && GetGame().ConfigIsExisting("CfgVehicles DZR_PaperWritten")) { s_Present = 1; }
        }
        return s_Present == 1;
    }

    // A lead note was kept intact: assigned, restored after a restart, or a write,
    // read-RPC or crafting attempt was refused. Counts only when the pack is present.
    static void LeadProtected(string how)
    {
        if (!Present()) { return; }
        HCModuleReadiness.HCUse("NotesCompat", "notes_lead_protected");
    }

    // A player note write was accepted by the server (the pack replaces the Paper).
    static void Written()
    {
        if (!Present()) { return; }
        HCModuleReadiness.HCUse("NotesCompat", "notes_written");
    }

    // Keeps the first entry of an action type and drops later duplicates in order.
    static void DedupeAction(TTypenameArray actions, typename action)
    {
        if (!actions) { return; }
        int first = actions.Find(action);
        if (first < 0) { return; }
        for (int index = actions.Count() - 1; index > first; index--)
        {
            if (actions[index] == action) { actions.RemoveOrdered(index); }
        }
    }
}

class HCNotesCompatModule : HCModule
{
    protected bool m_Started;
    protected ref HCOperationalStatus m_Operational = new HCOperationalStatus;

    override string GetName() { return "NotesCompat"; }

    override HCOperationalStatus HCGetOperationalStatus()
    {
        HCModuleReadiness.HCDerive(m_Operational, m_Started, "", "", "notes_compat_started");
        return m_Operational;
    }

    // Enabled only with the pack present; the release audit then expects both counters.
    override bool IsEnabled(HCSettings settings)
    {
        return HCNotesCompat.Present();
    }

    override void RegisterUses()
    {
        HCModuleReadiness.HCRegisterUse("NotesCompat", "notes_lead_protected");
        HCModuleReadiness.HCRegisterUse("NotesCompat", "notes_written");
    }

    override void OnStart(HCSettings settings)
    {
        if (!m_Started && HCNotesCompat.Present() && GetGame() && GetGame().IsServer())
        {
            m_Started = true;
            HCReached.Mark("notes_compat.started");
        }
    }

    override void OnStop() { m_Started = false; }
}

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        Register(new HCNotesCompatModule);
    }
}

// A crafting recipe may take any Paper as an ingredient; a lead note is never
// consumable. The server validates; the client cannot see the note text and so
// still lists the recipe, which then refuses.
modded class RecipeBase
{
    override bool CheckRecipe(ItemBase item1, ItemBase item2, PlayerBase player)
    {
        if (HCNoteEntities.IsLead(item1) || HCNoteEntities.IsLead(item2))
        {
            if (GetGame() && GetGame().IsServer()) { HCNotesCompat.LeadProtected("recipe"); }
            return false;
        }
        return super.CheckRecipe(item1, item2, player);
    }
}
