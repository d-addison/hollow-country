// LC-T414 / EXP-S1. Native evidence scripts-1.30.164289:
// 4_World/Entities/ItemBase/Paper.c:30 GetWrittenNoteData;
// 4_World/Classes/WrittenNoteData.c:73 GetNoteText; 1_Core/proto/EnString.c:171
// ToLower, :286 Contains; 3_Game/Entities/EntityAI.c:1884 GetInventory;
// 3_Game/Systems/Inventory/Cargo.c:28/33 count/item. No note creation or rewrite.
// 3_Game/Systems/Inventory/Inventory.c:138 GetCargo; EntityAI.c:885 parent;
// 3_Game/Entities/Object.c:467/1219 GetType/IsRuined; EnString.c:199 Length;
// 1_Core/proto/EnScript.c:94/380/394/407/470 cast/count/find/insert/remove;
// 1_Core/proto/EnDebug.c:96 Print.
// No available lead API certifies an unsearched site; use the truthful negative
// notification fallback until the leads owner supplies that narrow lookup.
class HCCampMailbox
{
    static bool Keyword(string text)
    {
        if (text.Length() < 1 || text.Length() > 2048) { return false; }
        text.ToLower();
        return text.Contains("medicine") || text.Contains("medical") || text.Contains("food") || text.Contains("water") || text.Contains("fuel") || text.Contains("tools") || text.Contains("shelter") || text.Contains("people") || text.Contains("raider");
    }

    static void Step(HCCampModule module, HCCampRecord camp, HCCampScan scan, int now)
    {
        if (camp.Tier < 1 || (camp.LastMailbox > 0 && now - camp.LastMailbox < 86400) || module.NearMembers(camp, 60) < 1) { return; }
        int examined;
        foreach (ItemBase crate : scan.Crates)
        {
            if (!crate || !crate.GetInventory()) { continue; }
            CargoBase cargo = crate.GetInventory().GetCargo();
            if (!cargo) { continue; }
            int count = cargo.GetItemCount();
            for (int index = 0; index < count && examined < 32; index++)
            {
                examined++;
                Paper paper = Paper.Cast(cargo.GetItem(index));
                if (!paper || paper.GetType() != "Paper" || paper.GetHierarchyParent() != crate || paper.IsRuined() || !paper.GetWrittenNoteData()) { continue; }
                string noteRef = HCCampScan.RefOf(paper);
                if (noteRef == "" || camp.Answered.Find(noteRef) >= 0 || !Keyword(paper.GetWrittenNoteData().GetNoteText())) { continue; }
                if (camp.Answered.Count() >= 32) { camp.Answered.RemoveOrdered(0); }
                camp.Answered.Insert(noteRef);
                camp.LastMailbox = now;
                if (!module.Commit(now)) { return; }
                // Never persist, log, broadcast or quote player-written text.
                module.Tell(camp, "Camp mailbox: nobody has seen any.");
                Print("[HollowCountry] V2 camps mailbox camp=" + camp.Id + " answer=none player-text=private");
                return;
            }
            if (examined >= 32) { return; }
        }
    }
}
