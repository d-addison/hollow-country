// #232 variety packs: writable-notes pack compatibility. Vanilla classes only; the
// pack is detected at runtime by its config class, so a missing pack changes nothing
// for the pack itself. Three guards act with or without the pack because they protect
// an HC invariant on vanilla classes: the lead-note write/read RPC drop (Paper.OnRPC),
// the write-action veto (ActionWritePaper) and the recipe veto below (RecipeBase).
// Native scripts-1.30.164289: 3_Game/Global/Game.c ConfigIsExisting/IsServer/IsMultiplayer,
// 4_World/Classes/Recipes/RecipeBase.c:479 CheckRecipe, 1_Core/proto/EnScript.c array
// Find/RemoveOrdered, 3_Game/Entities/Object.c GetType.
// Contract: lead notes (HCNoteLedger) stay read-only on the server. The note RPC drop,
// the write-action veto and the duplicate-action fold live next to the Paper hooks in
// HCNoteLedger.c; the recipe veto below keeps a lead note from being used as a recipe
// ingredient. It does not keep a lead note from burning: vanilla fire paths (indoor
// fireplace action, fireplace kindling attachment) still accept any Paper.
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

    protected static int s_ReasonsSeen;

    // A real refusal kept a lead note intact: how is "rpc" (note write/read RPC
    // dropped), "write_action" (write action vetoed) or "recipe" (recipe ingredient
    // refused). Anything else is not a refusal and is ignored. The first refusal of
    // each reason prints one line. Counts only when the pack is present.
    static void LeadProtected(string how)
    {
        if (!Present()) { return; }
        int bit = 0;
        if (how == "rpc") { bit = 1; }
        if (how == "write_action") { bit = 2; }
        if (how == "recipe") { bit = 4; }
        if (bit == 0) { return; }
        HCModuleReadiness.HCUse("NotesCompat", "notes_lead_protected");
        if ((s_ReasonsSeen & bit) != 0) { return; }
        s_ReasonsSeen = s_ReasonsSeen | bit;
        Print("[HC Notes] lead_protected reason=" + how);
    }

    // A lead note id was assigned to a Paper (spawn or restore after a restart). This
    // is assignment evidence only; nothing was refused. Counts only with the pack.
    static void LeadTracked()
    {
        if (!Present()) { return; }
        HCModuleReadiness.HCUse("NotesCompat", "notes_lead_tracked");
    }

    // A note write RPC from a client passed through to the pack handler (the lead-note
    // drop did not apply). The server did not confirm a replacement note; this is
    // pass-through evidence only.
    static void WriteRpcPassed()
    {
        if (!Present()) { return; }
        HCModuleReadiness.HCUse("NotesCompat", "write_rpc_passed");
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

    // Enabled only with the pack present; the release audit then expects all counters.
    override bool IsEnabled(HCSettings settings)
    {
        return HCNotesCompat.Present();
    }

    override void RegisterUses()
    {
        HCModuleReadiness.HCRegisterUse("NotesCompat", "notes_lead_protected");
        HCModuleReadiness.HCRegisterUse("NotesCompat", "notes_lead_tracked");
        HCModuleReadiness.HCRegisterUse("NotesCompat", "write_rpc_passed");
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

// A crafting recipe may take any Paper as an ingredient (vanilla fireplace and letter
// recipes do); a lead note is never accepted as a recipe ingredient, with or without
// the pack. The server validates; the client cannot see the note text and so still
// lists the recipe, which then refuses. Burning is not covered here (see the header).
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
