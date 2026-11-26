// Entry-local roster port: native scripts-1.30.164289 3_Game/Global/Game.c:945;
// resolver identity/life: Entities/Man.c:21, gameplay.c:368, Entities/Object.c:517.
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
        if (!c || c.SchemaVersion != 2)
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
        for (int memberGroupIndex = 0; memberGroupIndex < state.Groups.Count(); memberGroupIndex++)
        {
            HCGroupRecord group = state.Groups.Get(memberGroupIndex);
            if (group.Members.Find(uid) >= 0)
            {
                return group;
            }
        }
        return null;
    }

    static HCGroupRecord ById(HCGroupState state, int id)
    {
        for (int idGroupIndex = 0; idGroupIndex < state.Groups.Count(); idGroupIndex++)
        {
            HCGroupRecord group = state.Groups.Get(idGroupIndex);
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
        map<string, bool> seenMembers = new map<string, bool>();
        map<int, bool> seenIds = new map<int, bool>();
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
            if (seenIds.Contains(group.Id))
            {
                return false;
            }
            seenIds.Set(group.Id, true);
            foreach (string uid : group.Members)
            {
                // Persistent accounts are bounded by MaxGroups * MaxMembers,
                // not the separately bounded concurrent connection workload.
                if (!HCGroupRules.TextValid(uid, 128, false) || seenMembers.Contains(uid))
                {
                    return false;
                }
                seenMembers.Set(uid, true);
            }
            map<string, bool> seenOfficers = new map<string, bool>();
            foreach (string officerId : group.Officers)
            {
                if (officerId == group.OwnerId || group.Members.Find(officerId) < 0 || seenOfficers.Contains(officerId))
                {
                    return false;
                }
                seenOfficers.Set(officerId, true);
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
                if (seenIds.Contains(marker.Id))
                {
                    return false;
                }
                seenIds.Set(marker.Id, true);
            }
        }
        foreach (HCGroupInvitation invite : state.Invitations)
        {
            if (!invite || invite.Id < 1 || invite.Id >= state.NextId || seenIds.Contains(invite.Id))
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
            HCGroupRecord hcFoundGroup1 = HCGroupRules.FindGroup(state, invite.InviteeId);
            if (!offered || HCGroupRules.Role(offered, invite.InviterId) < HCGroupRole.OFFICER || offered.Name != invite.GroupName || hcFoundGroup1)
            {
                return false;
            }
            seenIds.Set(invite.Id, true);
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
            for (int inviteIndex = 0; inviteIndex < state.Invitations.Count(); inviteIndex++)
            {
                HCGroupInvitation invite = state.Invitations[inviteIndex];
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
                        state.Invitations.Remove(inviteIndex);
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
            HCGroupRecord hcFoundGroup2 = HCGroupRules.FindGroup(state, q.TargetId);
            if (!HCGroupRules.TextValid(q.TargetId, 128, false) || q.TargetId == actor || hcFoundGroup2)
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
        map<string, bool> accounts = new map<string, bool>();
        foreach (HCGroupExplorer explorer : state.Explorers)
        {
            if (!explorer || !explorer.Visits || !explorer.PlaceIds || explorer.LastSeenUtc < 0 || !HCGroupRules.TextValid(explorer.Id, 128, false))
            {
                return false;
            }
            if (accounts.Contains(explorer.Id) || explorer.Visits.Count() + explorer.PlaceIds.Count() > c.MaxDiscoveries)
            {
                return false;
            }
            accounts.Set(explorer.Id, true);
            map<string, bool> places = new map<string, bool>();
            foreach (string placeId : explorer.PlaceIds)
            {
                if (!HCGroupRules.TextValid(placeId, 128, false) || places.Contains(placeId))
                {
                    return false;
                }
                places.Set(placeId, true);
            }
            foreach (HCGroupPlace visited : explorer.Visits)
            {
                if (!HCGroupRules.PlaceValid(visited) || places.Contains(visited.Id))
                {
                    return false;
                }
                places.Set(visited.Id, true);
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

    static array<ref HCGroupPlace> KnownPlaces(HCGroupState state, HCGroupSettings c, string uid, HCGroupPlaceCatalog catalog, map<string, PlayerBase> hcPlayers)
    {
        array<ref HCGroupPlace> known = new array<ref HCGroupPlace>();
        map<string, bool> ids = new map<string, bool>();
        if (!c.DiscoveryLayer)
        {
            return known;
        }
        HCGroupRecord group = HCGroupRules.FindGroup(state, uid);
        // One membership index and one per-explorer visit index replace the
        // catalogue x journal Find scans; iteration order is unchanged.
        map<string, bool> memberIds = new map<string, bool>();
        if (c.ShareDiscovery && group)
        {
            foreach (string memberId : group.Members) { memberIds.Set(memberId, true); }
        }
        map<string, bool> visitedIds;
        foreach (HCGroupExplorer explorer : state.Explorers)
        {
            bool permitted = explorer.Id == uid;
            if (memberIds.Contains(explorer.Id))
            {
                permitted = true;
            }
            if (permitted)
            {
                if (!catalog) { continue; }
                visitedIds = new map<string, bool>();
                foreach (string visitedId : explorer.PlaceIds) { visitedIds.Set(visitedId, true); }
                foreach (HCGroupPlace place : catalog.Places)
                {
                    if (visitedIds.Contains(place.Id) && !ids.Contains(place.Id) && known.Count() < c.MaxDiscoveries)
                    {
                        ids.Set(place.Id, true);
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

    static bool MarkersExpired(HCGroupState state, int now)
    {
        foreach (HCGroupRecord group : state.Groups)
        {
            foreach (HCGroupMarker marker : group.Markers)
            {
                if (marker.ExpiresUtc > 0 && marker.ExpiresUtc <= now)
                {
                    return true;
                }
            }
        }
        return false;
    }

    // Expired markers are already hidden from every snapshot and client. A
    // batch flush touches their groups; a user mutation clone prunes without
    // a touch so the client's ExpectedRevision still matches.
    static bool ExpireMarkers(HCGroupState state, int now, bool touch)
    {
        bool removed = false;
        foreach (HCGroupRecord group : state.Groups)
        {
            bool touched = false;
            int index = group.Markers.Count() - 1;
            while (index >= 0)
            {
                HCGroupMarker marker = group.Markers.Get(index);
                if (marker.ExpiresUtc > 0 && marker.ExpiresUtc <= now)
                {
                    group.Markers.Remove(index);
                    touched = true;
                }
                index = index - 1;
            }
            if (touched && touch)
            {
                HCGroupRules.Touch(group, false);
            }
            if (touched)
            {
                removed = true;
            }
        }
        return removed;
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
