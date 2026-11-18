class HCGroupMapMenu extends UIScriptedMenu
{
    protected MapWidget mHCMap;
    protected EditBoxWidget mHCName;
    protected EditBoxWidget mHCNote;
    protected EditBoxWidget mHCGroupName;
    protected TextWidget mHCStatus;
    protected TextListboxWidget mHCMarkers;
    protected TextListboxWidget mHCMembers;
    protected TextListboxWidget mHCCandidates;
    protected TextListboxWidget mHCInvites;
    protected ref HCGroupSnapshot mHCBound;
    protected ref array<ref HCGroupMarker> mHCMarkerRows = new array<ref HCGroupMarker>();
    protected int mHCMarkerId;
    protected int mHCColor = -1;
    protected int mHCIcon;
    protected int mHCExpires;
    protected vector mHCPoint;
    protected bool mHCHasPoint;
    protected bool mHCOpening = true;
    protected float mHCRenderTime;
    protected ref HCGroupMarker mHCOriginal;
    protected ref HCGroupMapLayers mHCLayers;
    protected ref HCInfoLayerControls mHCInfo;
    protected bool mHCConflict;
    protected bool mHCCenterLogged;
    protected bool mHCRefreshing;
    protected string mHCMessage;

    override Widget Init()
    {
        layoutRoot = GetGame().GetWorkspace().CreateWidgets("HollowCountry/gui/layouts/hc_group_map.layout");
        if (!layoutRoot) return null;
        mHCMap = MapWidget.Cast(layoutRoot.FindAnyWidget("HCMap"));
        mHCName = EditBoxWidget.Cast(layoutRoot.FindAnyWidget("HCMarkerName"));
        mHCNote = EditBoxWidget.Cast(layoutRoot.FindAnyWidget("HCMarkerNote"));
        mHCGroupName = EditBoxWidget.Cast(layoutRoot.FindAnyWidget("HCGroupName"));
        mHCStatus = TextWidget.Cast(layoutRoot.FindAnyWidget("HCStatus"));
        mHCMarkers = TextListboxWidget.Cast(layoutRoot.FindAnyWidget("HCMarkers"));
        mHCMembers = TextListboxWidget.Cast(layoutRoot.FindAnyWidget("HCMembers"));
        mHCCandidates = TextListboxWidget.Cast(layoutRoot.FindAnyWidget("HCCandidates"));
        mHCInvites = TextListboxWidget.Cast(layoutRoot.FindAnyWidget("HCInvites"));
        CenterMap();
        mHCLayers = new HCGroupMapLayers;
        mHCLayers.Init(layoutRoot);
        mHCInfo = new HCInfoLayerControls;
        mHCInfo.Init(layoutRoot);
        return layoutRoot;
    }

    bool CenterMap()
    {
        if (!mHCMap) return false;
        string worldName;
        GetGame().GetWorldName(worldName);
        string path = "CfgWorlds " + worldName + " centerPosition";
        vector centre = vector.Zero;
        bool configured = GetGame().ConfigIsExisting(path);
        if (configured)
        {
            centre = GetGame().ConfigGetVector(path);
        }
        else
        {
            float half = GetGame().GetWorld().GetWorldSize() * 0.5;
            centre = Vector(half, 0, half);
            if (!mHCCenterLogged)
            {
                mHCCenterLogged = true;
                Print("[HC Groups] map centerPosition missing; using world centre");
            }
        }
        mHCMap.SetMapPos(centre);
        mHCMap.SetScale(0.33);
        return configured;
    }

    void ResetEditor()
    {
        mHCOriginal = null;
        mHCConflict = false;
        mHCMessage = "";
        mHCMarkerId = 0;
        mHCColor = -1;
        mHCIcon = 0;
        mHCExpires = 0;
        mHCHasPoint = false;
        mHCPoint = vector.Zero;
        if (mHCName) mHCName.SetText("");
        if (mHCNote) mHCNote.SetText("");
    }

    void EditMarker(HCGroupMarker marker)
    {
        if (!marker || !mHCName || !mHCNote) return;
        mHCOriginal = marker;
        mHCConflict = false;
        mHCMessage = "";
        mHCMarkerId = marker.Id;
        mHCPoint = marker.Position;
        mHCColor = marker.Color;
        mHCIcon = marker.Icon;
        mHCExpires = marker.ExpiresUtc;
        mHCHasPoint = true;
        mHCName.SetText(marker.Name);
        mHCNote.SetText(marker.Note);
    }

    override bool OnDoubleClick(Widget w, int x, int y, int button)
    {
        if (w == mHCMarkers)
        {
            if (mHCRefreshing) return true;
            int selectedRow = Selected(mHCMarkers, mHCMarkerRows.Count());
            if (selectedRow >= 0)
            {
                EditMarker(mHCMarkerRows.Get(selectedRow));
            }
            return true;
        }
        if (w != mHCMap || !mHCMap)
            return super.OnDoubleClick(w, x, y, button);
        if (mHCMarkerId == 0) ResetEditor();
        mHCPoint = mHCMap.ScreenToMap(Vector(x, y, 0));
        mHCHasPoint = true;
        return true;
    }

    override void Update(float timeslice)
    {
        super.Update(timeslice);
        if (HCMenuInput.BackPressed()) { Close(); return; }
        PlayerBase viewer = PlayerBase.Cast(GetGame().GetPlayer());
        if (!viewer)
        {
            Close();
            return;
        }
        if (!viewer.IsAlive() || viewer.IsUnconscious())
        {
            Close();
            return;
        }
        HCGroupClient client = HCGroupClient.Get();
        HCGroupSnapshot frame;
        if (client) frame = client.GetSnapshot();
        if (!frame || !frame.Enabled || !mHCMap)
        {
            Close();
            return;
        }
        if (frame != mHCBound)
        {
            RebuildLists(frame);
            mHCBound = frame;
        }
        mHCRenderTime += timeslice;
        if (mHCRenderTime >= 0.25)
        {
            if (!HCGroupEquipment.Read(viewer).HasMap)
            {
                Close();
                return;
            }
            if (mHCLayers) mHCLayers.Draw(mHCMap, frame, viewer);
            mHCRenderTime = 0;
        }
        if (mHCStatus)
        {
            if (mHCMessage != "")
            {
                mHCStatus.SetText(mHCMessage);
            }
            else
            {
                mHCStatus.SetText(client.GetNotice());
            }
        }
        if (mHCOpening) { mHCOpening = false; return; }
        if (EditBoxWidget.Cast(GetFocus())) return;
        if (GetGame().GetInput().LocalPress_ID(UAMapToggle, false))
            Close();
    }

    void ClearLists()
    {
        if (mHCMarkers) mHCMarkers.ClearItems();
        if (mHCMembers) mHCMembers.ClearItems();
        if (mHCCandidates) mHCCandidates.ClearItems();
        if (mHCInvites) mHCInvites.ClearItems();
        mHCMarkerRows.Clear();
    }

    void RebuildLists(HCGroupSnapshot frame)
    {
        int markerId;
        int inviteId;
        int row;
        string memberId;
        string candidateId;
        bool sameScope = mHCBound && frame.GroupId == mHCBound.GroupId && frame.Session == mHCBound.Session;
        bool setGroupName = !sameScope;
        if (sameScope)
        {
            row = Selected(mHCMarkers, mHCMarkerRows.Count());
            if (row >= 0) markerId = mHCMarkerRows.Get(row).Id;
            row = Selected(mHCMembers, mHCBound.Members.Count());
            if (row >= 0) memberId = mHCBound.Members.Get(row).Id;
            row = Selected(mHCCandidates, mHCBound.Candidates.Count());
            if (row >= 0) candidateId = mHCBound.Candidates.Get(row).Id;
            row = Selected(mHCInvites, mHCBound.Invitations.Count());
            if (row >= 0) inviteId = mHCBound.Invitations.Get(row).Id;
            if (mHCGroupName)
            {
                if (mHCGroupName.GetText() == mHCBound.Name)
                    setGroupName = true;
            }
            CheckDraft(frame);
        }
        else
        {
            ResetEditor();
        }
        mHCRefreshing = true;
        ClearLists();
        foreach (HCGroupMarker marker : frame.Markers)
        {
            mHCMarkerRows.Insert(marker);
            if (mHCMarkers)
            {
                int mr = mHCMarkers.AddItem(marker.Name, null, 0);
                if (marker.Id == markerId) mHCMarkers.SelectRow(mr);
            }
        }
        foreach (HCGroupMember member : frame.Members)
        {
            if (mHCMembers)
            {
                int ur = mHCMembers.AddItem(member.Name + " [" + HCGroupWorldIcons.RoleLabel(member.Role) + "]", null, 0);
                if (member.Id == memberId) mHCMembers.SelectRow(ur);
            }
        }
        foreach (HCGroupMember candidate : frame.Candidates)
        {
            if (mHCCandidates)
            {
                int cr = mHCCandidates.AddItem(candidate.Name, null, 0);
                if (candidate.Id == candidateId) mHCCandidates.SelectRow(cr);
            }
        }
        foreach (HCGroupInvitation invite : frame.Invitations)
        {
            if (mHCInvites)
            {
                int ir = mHCInvites.AddItem(invite.GroupName, null, 0);
                if (invite.Id == inviteId) mHCInvites.SelectRow(ir);
            }
        }
        mHCRefreshing = false;
        if (mHCGroupName && setGroupName)
            mHCGroupName.SetText(frame.Name);
    }

    int Selected(TextListboxWidget list, int count)
    {
        if (!list) return -1;
        int row = list.GetSelectedRow();
        if (row < 0 || row >= count) return -1;
        return row;
    }

    override bool OnItemSelected(Widget w, int x, int y, int row, int column, int oldRow, int oldColumn)
    {
        if (w == mHCMarkers)
        {
            if (mHCRefreshing) return true;
            if (row >= 0 && row < mHCMarkerRows.Count())
            {
                if (mHCHasPoint && mHCMarkerRows.Get(row).Id == mHCMarkerId)
                    return true;
                EditMarker(mHCMarkerRows.Get(row));
            }
            return true;
        }
        return super.OnItemSelected(w, x, y, row, column, oldRow, oldColumn);
    }

    override bool OnClick(Widget w, int x, int y, int button)
    {
        if (!w) return false;
        if (mHCInfo && mHCInfo.OnClick(w)) return true;
        string action = w.GetName();
        if (action == "HCClose") { Close(); return true; }
        if (action == "HCNew") { NewMarker(); return true; }
        HCGroupClient client = HCGroupClient.Get();
        if (!client || !mHCBound) return false;
        if (client.GetSnapshot() != mHCBound) return true;
        HCGroupRequest q = new HCGroupRequest;
        switch (action)
        {
            case "HCCreateGroup": q.Op = HCGroupOp.CREATE; break;
            case "HCRenameGroup": q.Op = HCGroupOp.RENAME; break;
            case "HCInvite": q.Op = HCGroupOp.INVITE; break;
            case "HCAccept": q.Op = HCGroupOp.ACCEPT; break;
            case "HCDecline": q.Op = HCGroupOp.DECLINE; break;
            case "HCLeave": q.Op = HCGroupOp.LEAVE; break;
            case "HCOfficer": q.Op = HCGroupOp.SET_ROLE; q.Role = HCGroupRole.OFFICER; break;
            case "HCMember": q.Op = HCGroupOp.SET_ROLE; q.Role = HCGroupRole.MEMBER; break;
            case "HCKick": q.Op = HCGroupOp.KICK; break;
            case "HCTransfer": q.Op = HCGroupOp.TRANSFER; break;
            case "HCDisband": q.Op = HCGroupOp.DISBAND; break;
            case "HCDelete": q.Op = HCGroupOp.MARKER_DELETE; break;
            case "HCSave": return SaveMarker(client);
            default: return super.OnClick(w, x, y, button);
        }
        if (q.Op == HCGroupOp.CREATE || q.Op == HCGroupOp.RENAME)
        {
            if (!mHCGroupName) return true;
            q.Name = mHCGroupName.GetText();
            if (!HCGroupRules.TextValid(q.Name, 48, false)) return true;
        }
        if (!FillSelection(q)) return true;
        client.Send(q);
        return true;
    }

    bool FillSelection(HCGroupRequest q)
    {
        int row;
        if (q.Op == HCGroupOp.INVITE)
        {
            row = Selected(mHCCandidates, mHCBound.Candidates.Count());
            if (row < 0) return false;
            q.TargetId = mHCBound.Candidates.Get(row).Id;
        }
        if (q.Op == HCGroupOp.ACCEPT || q.Op == HCGroupOp.DECLINE)
        {
            row = Selected(mHCInvites, mHCBound.Invitations.Count());
            if (row < 0) return false;
            q.EntityId = mHCBound.Invitations.Get(row).Id;
        }
        if (q.Op == HCGroupOp.KICK || q.Op == HCGroupOp.TRANSFER || q.Op == HCGroupOp.SET_ROLE)
        {
            row = Selected(mHCMembers, mHCBound.Members.Count());
            if (row < 0) return false;
            q.TargetId = mHCBound.Members.Get(row).Id;
        }
        if (q.Op == HCGroupOp.MARKER_DELETE)
        {
            if (mHCMarkerId < 1) return false;
            q.EntityId = mHCMarkerId;
        }
        return true;
    }

    bool SaveMarker(HCGroupClient client)
    {
        if (mHCConflict)
            return true;
        if (!mHCHasPoint || !mHCName || !mHCNote)
            return true;
        HCGroupRequest q = new HCGroupRequest;
        q.Op = HCGroupOp.MARKER_CREATE;
        if (mHCMarkerId > 0)
            q.Op = HCGroupOp.MARKER_UPDATE;
        q.EntityId = mHCMarkerId;
        q.Name = mHCName.GetText();
        q.Note = mHCNote.GetText();
        if (!HCGroupRules.TextValid(q.Name, 64, false))
            return true;
        if (!HCGroupRules.TextValid(q.Note, 512, true))
            return true;
        q.Position = mHCPoint;
        q.Color = mHCColor;
        q.Icon = mHCIcon;
        // UPDATE leaves TTL zero; server preserves its absolute expiry.
        client.Send(q);
        return true;
    }

    bool SameMarker(HCGroupMarker marker)
    {
        if (!marker || !mHCOriginal) return false;
        if (marker.Id != mHCOriginal.Id) return false;
        if (marker.CreatorId != mHCOriginal.CreatorId) return false;
        if (marker.Name != mHCOriginal.Name) return false;
        if (marker.Note != mHCOriginal.Note) return false;
        if (marker.Color != mHCOriginal.Color) return false;
        if (marker.Icon != mHCOriginal.Icon) return false;
        if (marker.ExpiresUtc != mHCOriginal.ExpiresUtc) return false;
        if (marker.Position[0] != mHCOriginal.Position[0]) return false;
        if (marker.Position[1] != mHCOriginal.Position[1]) return false;
        return marker.Position[2] == mHCOriginal.Position[2];
    }

    void CheckDraft(HCGroupSnapshot frame)
    {
        if (mHCMarkerId < 1) return;
        HCGroupMarker current;
        foreach (HCGroupMarker marker : frame.Markers)
        {
            if (marker.Id == mHCMarkerId)
                current = marker;
        }
        if (!SameMarker(current))
            mHCConflict = true;
        if (mHCConflict)
            mHCMessage = "Marker changed/deleted. Double-click its list entry to reload; New keeps this draft as a new marker.";
    }

    void NewMarker()
    {
        if (mHCConflict)
        {
            mHCMarkerId = 0;
            mHCOriginal = null;
            mHCConflict = false;
            mHCMessage = "Draft kept as new marker. Save creates it.";
            return;
        }
        ResetEditor();
    }

    override void OnShow()
    {
        super.OnShow();
        HCMenuInput.Lock();
        HCEventClient.Get().SetBrowsing(true);
    }

    override void OnHide()
    {
        HCMenuInput.Unlock();
        HCEventClient.Get().SetBrowsing(false);
        if (mHCLayers) mHCLayers.Clear();
        if (mHCMap)
            mHCMap.ClearUserMarks();
        ClearLists();
        ResetEditor();
        if (mHCGroupName)
            mHCGroupName.SetText("");
        if (mHCStatus)
            mHCStatus.SetText("");
        mHCBound = null;
        mHCOpening = true;
        // Inherited OnShow owns LockControls; release it exactly once here.
        super.OnHide();
    }
}
