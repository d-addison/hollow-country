// Authored transaction rules. Service supplies authenticated sender.GetId(),
// server UTC/world size and a disposable clone. Never commit a rejected clone.
class HCGroupRules
{
    static bool TimestampValid(int value)
    {
        return value >= 1 && value <= 2147483647;
    }

    static bool ClockAllows(HCGroupState state, int now)
    {
        if (!state || !HCGroupRules.TimestampValid(now))
        {
            return false;
        }
        return state.LastMutationUtc >= 0 && state.LastMutationUtc <= now;
    }

    static bool DeadlineFits(int now, int seconds)
    {
        if (!HCGroupRules.TimestampValid(now) || seconds < 1 || seconds > 2592000)
        {
            return false;
        }
        // Check BEFORE adding. Native Enforce int is signed 32-bit.
        return now <= 2147483647 - seconds;
    }

    static bool MutationIdValid(int value)
    {
        return value >= 0 && value <= 1000000;
    }

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
        if (c.MaxLOSRaysPerTick < 1 || c.MaxLOSRaysPerTick > 256)
        {
            return false;
        }
        if (c.MaxDiscoveries < 1 || c.MaxDiscoveries > 256 || c.MaxExplorers < 1 || c.MaxExplorers > 512)
        {
            return false;
        }
        if (!(c.DiscoveryIntervalSeconds >= 5.0 && c.DiscoveryIntervalSeconds <= 300.0))
        {
            return false;
        }
        if (!(c.IconScale >= 0.75 && c.IconScale <= 2.0))
        {
            return false;
        }
        if (!(c.LabelScale >= 0.75 && c.LabelScale <= 2.0))
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
        if (state.LastMutationUtc < 0 || state.LastMutationUtc > 2147483647)
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
            if (!group || !group.Members || !group.Markers || !group.Officers)
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
            array<string> seenOfficers = new array<string>();
            foreach (string officerId : group.Officers)
            {
                if (officerId == group.OwnerId || group.Members.Find(officerId) < 0 || seenOfficers.Find(officerId) >= 0)
                {
                    return false;
                }
                seenOfficers.Insert(officerId);
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
                if (marker.ExpiresUtc < 0 || marker.ExpiresUtc > 2147483647)
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
            if (!HCGroupRules.TimestampValid(invite.ExpiresUtc))
            {
                return false;
            }
            HCGroupRecord offered = HCGroupRules.ById(state, invite.GroupId);
            if (!offered || HCGroupRules.Role(offered, invite.InviterId) < HCGroupRole.OFFICER || offered.Name != invite.GroupName || HCGroupRules.FindGroup(state, invite.InviteeId))
            {
                return false;
            }
            seenIds.Insert(invite.Id);
        }
        return HCGroupRules.ExplorersValid(state, c);
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
        if (!q || q.Version != HCGroupProtocol.VERSION || q.Op < 1 || q.Op > 13)
        {
            return HCGroupCode.INVALID;
        }
        if (!HCGroupRules.TextValid(actor, 128, false) || !HCGroupRules.ClockAllows(state, now) || state.NextId >= 1000000000)
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
        bool officer = HCGroupRules.Role(group, actor) >= HCGroupRole.OFFICER;
        if (q.Op == HCGroupOp.SET_ROLE)
        {
            if (!owner)
            {
                return HCGroupCode.DENIED;
            }
            if (q.TargetId == actor || group.Members.Find(q.TargetId) < 0 || q.Role < 0 || q.Role > 1)
            {
                return HCGroupCode.INVALID;
            }
            HCGroupRules.RemoveOfficer(group, q.TargetId);
            if (q.Role == HCGroupRole.OFFICER)
            {
                group.Officers.Insert(q.TargetId);
            }
            HCGroupRules.DropInvites(state, group.Id, "");
            HCGroupRules.Touch(group, true);
            return HCGroupCode.OK;
        }
        if (q.Op == HCGroupOp.INVITE)
        {
            if (!officer)
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
            if (!HCGroupRules.DeadlineFits(now, c.InviteSeconds))
            {
                return HCGroupCode.INVALID;
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
            HCGroupRules.RemoveOfficer(group, actor);
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
            if (!officer)
            {
                return HCGroupCode.DENIED;
            }
            if (!owner && (q.Op == HCGroupOp.TRANSFER || q.Op == HCGroupOp.DISBAND))
            {
                return HCGroupCode.DENIED;
            }
            if (!owner && q.Op == HCGroupOp.KICK && HCGroupRules.Role(group, q.TargetId) != HCGroupRole.MEMBER)
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
                HCGroupRules.RemoveOfficer(group, q.TargetId);
                group.OwnerId = q.TargetId;
            }
            else
            {
                HCGroupRules.RemoveOfficer(group, q.TargetId);
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
            if (!officer && marker.CreatorId != actor)
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
        // Updates edit content only. Client clocks never select or refresh an
        // existing deadline, including a marker that was created forever.
        if (q.Op == HCGroupOp.MARKER_UPDATE && q.TtlSeconds != 0)
        {
            return HCGroupCode.INVALID;
        }
        int ttl = q.TtlSeconds;
        if (q.Op == HCGroupOp.MARKER_CREATE)
        {
            if (ttl == 0)
            {
                ttl = c.MarkerRetentionSeconds;
            }
            if (c.MarkerRetentionSeconds > 0 && (ttl == 0 || ttl > c.MarkerRetentionSeconds))
            {
                return HCGroupCode.INVALID;
            }
            if (group.Markers.Count() >= c.MaxMarkers)
            {
                return HCGroupCode.LIMIT;
            }
            if (ttl > 0 && !HCGroupRules.DeadlineFits(now, ttl))
            {
                return HCGroupCode.INVALID;
            }
            marker = new HCGroupMarker;
            marker.Id = state.NextId;
            state.NextId = state.NextId + 1;
            marker.CreatorId = actor;
            marker.ExpiresUtc = 0;
            if (ttl > 0)
            {
                marker.ExpiresUtc = now + ttl;
            }
            group.Markers.Insert(marker);
        }
        marker.Name = q.Name;
        marker.Note = q.Note;
        marker.Position = q.Position;
        marker.Color = q.Color;
        marker.Icon = q.Icon;
        HCGroupRules.Touch(group, false);
        return HCGroupCode.OK;
    }

    static int Role(HCGroupRecord group, string uid)
    {
        if (!group || group.Members.Find(uid) < 0)
        {
            return -1;
        }
        if (group.OwnerId == uid)
        {
            return HCGroupRole.OWNER;
        }
        if (group.Officers.Find(uid) >= 0)
        {
            return HCGroupRole.OFFICER;
        }
        return HCGroupRole.MEMBER;
    }

    static void RemoveOfficer(HCGroupRecord group, string uid)
    {
        int index = group.Officers.Find(uid);
        if (index >= 0)
        {
            group.Officers.Remove(index);
        }
    }

    static bool PlaceValid(HCGroupPlace place)
    {
        if (!place || !HCGroupRules.TextValid(place.Id, 128, false) || !HCGroupRules.TextValid(place.Name, 64, false))
        {
            return false;
        }
        return HCGroupRules.PositionValid(place.Position) && place.Radius >= 5.0 && place.Radius <= 500.0;
    }

    static bool ExplorersValid(HCGroupState state, HCGroupSettings c)
    {
        if (!state.Explorers || state.Explorers.Count() > c.MaxExplorers)
        {
            return false;
        }
        array<string> accounts = new array<string>();
        foreach (HCGroupExplorer explorer : state.Explorers)
        {
            if (!explorer || !explorer.Visits || !explorer.PlaceIds || explorer.LastSeenUtc < 0 || !HCGroupRules.TextValid(explorer.Id, 128, false))
            {
                return false;
            }
            if (accounts.Find(explorer.Id) >= 0 || explorer.Visits.Count() + explorer.PlaceIds.Count() > c.MaxDiscoveries)
            {
                return false;
            }
            accounts.Insert(explorer.Id);
            array<string> places = new array<string>();
            foreach (string placeId : explorer.PlaceIds)
            {
                if (!HCGroupRules.TextValid(placeId, 128, false) || places.Find(placeId) >= 0)
                {
                    return false;
                }
                places.Insert(placeId);
            }
            foreach (HCGroupPlace visited : explorer.Visits)
            {
                if (!HCGroupRules.PlaceValid(visited) || places.Find(visited.Id) >= 0)
                {
                    return false;
                }
                places.Insert(visited.Id);
            }
        }
        return true;
    }

    // Called only with a live server player's actual position, never an RPC
    // position. Visits survive death/reconnect, shared knowledge is a view of
    // CURRENT membership and never copied to another account's journal.
    static bool RecordVisit(HCGroupState state, HCGroupSettings c, string uid, HCGroupPlace place, vector actual)
    {
        if (!place) { return false; }
        float dx = actual[0] - place.Position[0];
        float dz = actual[2] - place.Position[2];
        if (dx * dx + dz * dz > place.Radius * place.Radius)
        {
            return false;
        }
        if (!c.DiscoveryLayer || !HCGroupRules.PlaceValid(place) || !HCGroupRules.PositionValid(actual) || !HCGroupRules.TextValid(uid, 128, false))
        {
            return false;
        }
        HCGroupExplorer found;
        foreach (HCGroupExplorer candidate : state.Explorers)
        {
            if (candidate.Id == uid)
            {
                found = candidate;
            }
        }
        if (!found)
        {
            if (state.Explorers.Count() >= c.MaxExplorers)
            {
                return false;
            }
            found = new HCGroupExplorer;
            found.Id = uid;
            state.Explorers.Insert(found);
        }
        if (found.PlaceIds.Find(place.Id) >= 0)
        {
            return false;
        }
        if (found.PlaceIds.Count() >= c.MaxDiscoveries)
        {
            return false;
        }
        found.PlaceIds.Insert(place.Id);
        return true;
    }

    static array<ref HCGroupPlace> KnownPlaces(HCGroupState state, HCGroupSettings c, string uid, HCGroupPlaceCatalog catalog)
    {
        array<ref HCGroupPlace> known = new array<ref HCGroupPlace>();
        array<string> ids = new array<string>();
        if (!c.DiscoveryLayer)
        {
            return known;
        }
        HCGroupRecord group = HCGroupRules.FindGroup(state, uid);
        foreach (HCGroupExplorer explorer : state.Explorers)
        {
            bool permitted = explorer.Id == uid;
            if (c.ShareDiscovery && group && group.Members.Find(explorer.Id) >= 0)
            {
                permitted = true;
            }
            if (permitted)
            {
                if (!catalog) { continue; }
                foreach (HCGroupPlace place : catalog.Places)
                {
                    if (explorer.PlaceIds.Find(place.Id) >= 0 && ids.Find(place.Id) < 0 && known.Count() < c.MaxDiscoveries)
                    {
                        ids.Insert(place.Id);
                        known.Insert(place);
                    }
                }
            }
        }
        return known;
    }

    static bool HasExplorer(HCGroupState state, string uid)
    {
        foreach (HCGroupExplorer explorer : state.Explorers)
        {
            if (explorer.Id == uid)
            {
                return true;
            }
        }
        return false;
    }

    static bool HasVisit(HCGroupState state, string uid, string placeId)
    {
        foreach (HCGroupExplorer explorer : state.Explorers)
        {
            if (explorer.Id == uid && explorer.PlaceIds.Find(placeId) >= 0)
            {
                return true;
            }
        }
        return false;
    }

    static void MigrateExplorers(HCGroupState state)
    {
        // Validated before migration; no catalog metadata survives the next save.
        foreach (HCGroupExplorer explorer : state.Explorers)
        {
            foreach (HCGroupPlace legacy : explorer.Visits)
            {
                explorer.PlaceIds.Insert(legacy.Id);
            }
            explorer.Visits.Clear();
        }
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
