// Authored transaction rules. Service supplies authenticated sender.GetId(),
// server UTC/world size and a disposable clone. Never commit a rejected clone.
class HCGroupRules
{
    static bool SettingsValid(HCGroupSettings c)
    {
        // Native probe031 rejected the previous single long formula. Keep
        // each guard small; positive float ranges also reject NaN/infinity.
        if (!c || c.SchemaVersion != 1)
        {
            return false;
        }
        if (!(c.MaxGroups >= 1 && c.MaxGroups <= 90))
        {
            return false;
        }
        if (!(c.MaxMembers >= 1 && c.MaxMembers <= 90))
        {
            return false;
        }
        if (!(c.MaxMarkers >= 1 && c.MaxMarkers <= 256))
        {
            return false;
        }
        if (!(c.MaxInvites >= 1 && c.MaxInvites <= 256))
        {
            return false;
        }
        if (!(c.MaxRequestsPerSecond >= 1 && c.MaxRequestsPerSecond <= 16))
        {
            return false;
        }
        if (!(c.MaxStoreBytes >= 16384 && c.MaxStoreBytes <= 1048576))
        {
            return false;
        }
        if (!(c.KeepRevisions >= 2 && c.KeepRevisions <= 32))
        {
            return false;
        }
        if (!(c.InviteSeconds >= 10 && c.InviteSeconds <= 3600))
        {
            return false;
        }
        if (!(c.MarkerRetentionSeconds >= 0 && c.MarkerRetentionSeconds <= 2592000))
        {
            return false;
        }
        if (!(c.PositionIntervalSeconds >= 1.0 && c.PositionIntervalSeconds <= 30.0))
        {
            return false;
        }
        if (!(c.PositionStaleSeconds >= c.PositionIntervalSeconds && c.PositionStaleSeconds <= 120.0))
        {
            return false;
        }
        if (!(c.MaxIconDistance >= 10.0 && c.MaxIconDistance <= 5000.0))
        {
            return false;
        }
        if (c.RequireLOS || c.RequireRadio)
        {
            return false;
        }
        return true;
    }

    static bool TextValid(string text, int limit, bool emptyAllowed)
    {
        if (text.Contains("\n") || text.Contains("\r") || text.Contains("\t"))
        {
            return false;
        }
        return text.Length() <= limit && (emptyAllowed || text.Trim().Length() > 0);
    }

    static bool PositionValid(vector position)
    {
        if (!(position[0] >= 0.0 && position[0] <= 50000.0))
        {
            return false;
        }
        if (!(position[1] >= -1000.0 && position[1] <= 10000.0))
        {
            return false;
        }
        return position[2] >= 0.0 && position[2] <= 50000.0;
    }

    static HCGroupRecord FindGroup(HCGroupState state, string uid)
    {
        foreach (HCGroupRecord group : state.Groups)
        {
            if (group.Members.Find(uid) >= 0)
            {
                return group;
            }
        }
        return null;
    }

    static HCGroupRecord ById(HCGroupState state, int id)
    {
        foreach (HCGroupRecord group : state.Groups)
        {
            if (group.Id == id)
            {
                return group;
            }
        }
        return null;
    }

    static bool StateValid(HCGroupState state, HCGroupSettings c, string world)
    {
        if (!HCGroupRules.SettingsValid(c) || !HCGroupRules.TextValid(world, 128, false))
        {
            return false;
        }
        if (!state || !state.Groups || !state.Invitations)
        {
            return false;
        }
        if (state.Version != 1 || state.WorldName != world)
        {
            return false;
        }
        if (state.Revision < 0 || state.Revision > 1000000000 || state.NextId < 1 || state.NextId > 1000000000)
        {
            return false;
        }
        if (state.Groups.Count() > c.MaxGroups || state.Invitations.Count() > c.MaxInvites)
        {
            return false;
        }
        array<string> seenMembers = new array<string>();
        array<int> seenIds = new array<int>();
        foreach (HCGroupRecord group : state.Groups)
        {
            if (!group || !group.Members || !group.Markers)
            {
                return false;
            }
            if (group.Id < 1 || group.Id >= state.NextId || group.Revision < 1 || group.Revision > 1000000000)
            {
                return false;
            }
            if (group.Epoch < 1 || group.Epoch > group.Revision || !HCGroupRules.TextValid(group.Name, 48, false))
            {
                return false;
            }
            if (group.Members.Count() < 1 || group.Members.Count() > c.MaxMembers || group.Members.Find(group.OwnerId) < 0 || group.Markers.Count() > c.MaxMarkers)
            {
                return false;
            }
            if (seenIds.Find(group.Id) >= 0)
            {
                return false;
            }
            seenIds.Insert(group.Id);
            foreach (string uid : group.Members)
            {
                // Persistent accounts are bounded by MaxGroups * MaxMembers,
                // not the separately bounded concurrent connection workload.
                if (!HCGroupRules.TextValid(uid, 128, false) || seenMembers.Find(uid) >= 0)
                {
                    return false;
                }
                seenMembers.Insert(uid);
            }
            foreach (HCGroupMarker marker : group.Markers)
            {
                if (!marker || marker.Id < 1 || marker.Id >= state.NextId)
                {
                    return false;
                }
                if (!HCGroupRules.TextValid(marker.CreatorId, 128, false) || !HCGroupRules.TextValid(marker.Name, 64, false) || !HCGroupRules.TextValid(marker.Note, 512, true))
                {
                    return false;
                }
                if (!HCGroupRules.PositionValid(marker.Position) || marker.Icon < 0 || marker.Icon > 19)
                {
                    return false;
                }
                if (marker.ExpiresUtc < 0 || marker.ExpiresUtc > 2000000000)
                {
                    return false;
                }
                if (seenIds.Find(marker.Id) >= 0)
                {
                    return false;
                }
                seenIds.Insert(marker.Id);
            }
        }
        foreach (HCGroupInvitation invite : state.Invitations)
        {
            if (!invite || invite.Id < 1 || invite.Id >= state.NextId || seenIds.Find(invite.Id) >= 0)
            {
                return false;
            }
            if (!HCGroupRules.TextValid(invite.InviteeId, 128, false) || !HCGroupRules.TextValid(invite.GroupName, 48, false))
            {
                return false;
            }
            if (invite.ExpiresUtc < 1 || invite.ExpiresUtc > 2000000000)
            {
                return false;
            }
            HCGroupRecord offered = HCGroupRules.ById(state, invite.GroupId);
            if (!offered || offered.OwnerId != invite.InviterId || offered.Name != invite.GroupName || HCGroupRules.FindGroup(state, invite.InviteeId))
            {
                return false;
            }
            seenIds.Insert(invite.Id);
        }
        return true;
    }

    // No fallback to previous ACL after any incomplete highest revision. Hash is
    // the native noncryptographic string.Hash(), corruption checking only.
    static bool LatestComplete(int intent, int image, int commit, int receiptRevision, int imageRevision, int receiptLength, int imageLength, int receiptHash, int imageHash)
    {
        if (intent < 1 || intent != image || image != commit)
        {
            return false;
        }
        if (commit != receiptRevision || commit != imageRevision)
        {
            return false;
        }
        return receiptLength > 0 && receiptLength == imageLength && receiptHash == imageHash;
    }

    static int Apply(HCGroupState state, HCGroupSettings c, HCGroupRequest q, string actor, int now)
    {
        if (!c.Enabled)
        {
            return HCGroupCode.DISABLED;
        }
        if (!q || q.Version != 1 || q.Op < 1 || q.Op > 12)
        {
            return HCGroupCode.INVALID;
        }
        if (!HCGroupRules.TextValid(actor, 128, false) || now < 1 || now > 1990000000 || state.NextId >= 1000000000)
        {
            return HCGroupCode.INVALID;
        }
        HCGroupRecord group = HCGroupRules.FindGroup(state, actor);
        if (q.Op == HCGroupOp.CREATE)
        {
            if (group)
            {
                return HCGroupCode.CONFLICT;
            }
            if (!HCGroupRules.TextValid(q.Name, 48, false))
            {
                return HCGroupCode.INVALID;
            }
            if (state.Groups.Count() >= c.MaxGroups)
            {
                return HCGroupCode.LIMIT;
            }
            HCGroupRecord created = new HCGroupRecord;
            created.Id = state.NextId;
            state.NextId = state.NextId + 1;
            created.Name = q.Name;
            created.OwnerId = actor;
            created.Members.Insert(actor);
            created.Revision = 1;
            created.Epoch = 1;
            state.Groups.Insert(created);
            HCGroupRules.DropInvites(state, 0, actor);
            return HCGroupCode.OK;
        }
        if (q.Op == HCGroupOp.ACCEPT || q.Op == HCGroupOp.DECLINE)
        {
            foreach (HCGroupInvitation invite : state.Invitations)
            {
                if (invite.Id == q.EntityId)
                {
                    if (invite.InviteeId != actor)
                    {
                        return HCGroupCode.DENIED;
                    }
                    HCGroupRecord offered = HCGroupRules.ById(state, invite.GroupId);
                    if (!offered || invite.ExpiresUtc <= now)
                    {
                        return HCGroupCode.NOT_FOUND;
                    }
                    if (q.Op == HCGroupOp.DECLINE)
                    {
                        state.Invitations.Remove(state.Invitations.Find(invite));
                        return HCGroupCode.OK;
                    }
                    if (group)
                    {
                        return HCGroupCode.CONFLICT;
                    }
                    if (offered.Members.Count() >= c.MaxMembers)
                    {
                        return HCGroupCode.LIMIT;
                    }
                    offered.Members.Insert(actor);
                    HCGroupRules.DropInvites(state, 0, actor);
                    HCGroupRules.Touch(offered, true);
                    return HCGroupCode.OK;
                }
            }
            return HCGroupCode.NOT_FOUND;
        }
        if (!group)
        {
            return HCGroupCode.DENIED;
        }
        if (q.ExpectedRevision != group.Revision)
        {
            return HCGroupCode.CONFLICT;
        }
        bool owner = group.OwnerId == actor;
        if (q.Op == HCGroupOp.INVITE)
        {
            if (!owner)
            {
                return HCGroupCode.DENIED;
            }
            if (!HCGroupRules.TextValid(q.TargetId, 128, false) || q.TargetId == actor || HCGroupRules.FindGroup(state, q.TargetId))
            {
                return HCGroupCode.INVALID;
            }
            if (state.Invitations.Count() >= c.MaxInvites || group.Members.Count() >= c.MaxMembers)
            {
                return HCGroupCode.LIMIT;
            }
            foreach (HCGroupInvitation pending : state.Invitations)
            {
                if (pending.GroupId == group.Id && pending.InviteeId == q.TargetId && pending.ExpiresUtc > now)
                {
                    return HCGroupCode.CONFLICT;
                }
            }
            HCGroupInvitation invitation = new HCGroupInvitation;
            invitation.Id = state.NextId;
            state.NextId = state.NextId + 1;
            invitation.GroupId = group.Id;
            invitation.GroupName = group.Name;
            invitation.InviterId = actor;
            invitation.InviteeId = q.TargetId;
            invitation.ExpiresUtc = now + c.InviteSeconds;
            state.Invitations.Insert(invitation);
            HCGroupRules.Touch(group, false);
            return HCGroupCode.OK;
        }
        if (q.Op == HCGroupOp.LEAVE)
        {
            if (owner && group.Members.Count() > 1)
            {
                return HCGroupCode.DENIED;
            }
            group.Members.Remove(group.Members.Find(actor));
            HCGroupRules.Touch(group, true);
            HCGroupRules.DropInvites(state, group.Id, actor);
            if (group.Members.Count() == 0)
            {
                state.Groups.Remove(state.Groups.Find(group));
            }
            return HCGroupCode.OK;
        }
        if (q.Op == HCGroupOp.KICK || q.Op == HCGroupOp.TRANSFER || q.Op == HCGroupOp.DISBAND || q.Op == HCGroupOp.RENAME)
        {
            if (!owner)
            {
                return HCGroupCode.DENIED;
            }
            if (q.Op == HCGroupOp.RENAME)
            {
                if (!HCGroupRules.TextValid(q.Name, 48, false))
                {
                    return HCGroupCode.INVALID;
                }
                group.Name = q.Name;
                foreach (HCGroupInvitation renamedInvite : state.Invitations)
                {
                    if (renamedInvite.GroupId == group.Id)
                    {
                        renamedInvite.GroupName = group.Name;
                    }
                }
                HCGroupRules.Touch(group, false);
                return HCGroupCode.OK;
            }
            if (q.Op == HCGroupOp.DISBAND)
            {
                HCGroupRules.DropInvites(state, group.Id, "");
                state.Groups.Remove(state.Groups.Find(group));
                return HCGroupCode.OK;
            }
            int memberIndex = group.Members.Find(q.TargetId);
            if (memberIndex < 0 || q.TargetId == actor)
            {
                return HCGroupCode.INVALID;
            }
            if (q.Op == HCGroupOp.TRANSFER)
            {
                group.OwnerId = q.TargetId;
            }
            else
            {
                group.Members.Remove(memberIndex);
            }
            HCGroupRules.DropInvites(state, group.Id, "");
            HCGroupRules.Touch(group, true);
            return HCGroupCode.OK;
        }
        HCGroupMarker marker;
        if (q.Op != HCGroupOp.MARKER_CREATE)
        {
            foreach (HCGroupMarker existing : group.Markers)
            {
                if (existing.Id == q.EntityId)
                {
                    marker = existing;
                }
            }
            if (!marker || (marker.ExpiresUtc > 0 && marker.ExpiresUtc <= now))
            {
                return HCGroupCode.NOT_FOUND;
            }
            if (!owner && marker.CreatorId != actor)
            {
                return HCGroupCode.DENIED;
            }
        }
        if (q.Op == HCGroupOp.MARKER_DELETE)
        {
            group.Markers.Remove(group.Markers.Find(marker));
            HCGroupRules.Touch(group, false);
            return HCGroupCode.OK;
        }
        if (!HCGroupRules.TextValid(q.Name, 64, false) || !HCGroupRules.TextValid(q.Note, 512, true) || !HCGroupRules.PositionValid(q.Position))
        {
            return HCGroupCode.INVALID;
        }
        if (q.Icon < 0 || q.Icon > 19 || q.TtlSeconds < 0 || q.TtlSeconds > 2592000)
        {
            return HCGroupCode.INVALID;
        }
        int ttl = q.TtlSeconds;
        if (ttl == 0)
        {
            ttl = c.MarkerRetentionSeconds;
        }
        if (c.MarkerRetentionSeconds > 0 && (ttl == 0 || ttl > c.MarkerRetentionSeconds))
        {
            return HCGroupCode.INVALID;
        }
        if (q.Op == HCGroupOp.MARKER_CREATE)
        {
            if (group.Markers.Count() >= c.MaxMarkers)
            {
                return HCGroupCode.LIMIT;
            }
            marker = new HCGroupMarker;
            marker.Id = state.NextId;
            state.NextId = state.NextId + 1;
            marker.CreatorId = actor;
            group.Markers.Insert(marker);
        }
        marker.Name = q.Name;
        marker.Note = q.Note;
        marker.Position = q.Position;
        marker.Color = q.Color;
        marker.Icon = q.Icon;
        marker.ExpiresUtc = 0;
        if (ttl > 0)
        {
            marker.ExpiresUtc = now + ttl;
        }
        HCGroupRules.Touch(group, false);
        return HCGroupCode.OK;
    }

    static void Touch(HCGroupRecord group, bool membershipChanged)
    {
        group.Revision = group.Revision + 1;
        if (membershipChanged)
        {
            group.Epoch = group.Epoch + 1;
        }
    }

    static void DropInvites(HCGroupState state, int groupId, string uid)
    {
        int index = state.Invitations.Count() - 1;
        while (index >= 0)
        {
            HCGroupInvitation invite = state.Invitations.Get(index);
            if ((groupId > 0 && invite.GroupId == groupId) || (uid != "" && invite.InviteeId == uid))
            {
                state.Invitations.Remove(index);
            }
            index = index - 1;
        }
    }
}
