// Opt-in SYNTHETIC DTO fixtures. No startup hook or world interaction.
// Policy only: not authentication, service replay, network or persistence proof.
// JSON serialization below is in-memory only.
class HCGroupNativeChecks
{
    static const int MAX_STEPS = 64;
    protected ref HCGroupState m_State = new HCGroupState;
    protected ref HCGroupSettings m_Config = new HCGroupSettings;
    protected int m_Steps = 0;
    protected int m_Now = 1000;
    protected string m_Error;

    bool Require(bool condition, string label)
    {
        if (condition) return true;
        m_Error = label + " step=" + m_Steps.ToString();
        return false;
    }

    string Error()
    {
        return m_Error;
    }

    string Completion()
    {
        return "[HC Group Checks] COMPLETE synthetic-policy-fixtures steps=" + m_Steps.ToString() + " wire=2 durable=1 no-network-or-store-proof";
    }

    HCGroupRequest Request(int operation, string actor)
    {
        HCGroupRequest request = new HCGroupRequest;
        request.Op = operation;
        request.Name = "Synthetic group";
        request.Note = "Synthetic fixture";
        request.Position[0] = 100;
        request.Position[1] = 0;
        request.Position[2] = 200;
        HCGroupRecord group = HCGroupRules.FindGroup(m_State, actor);
        if (group) request.ExpectedRevision = group.Revision;
        return request;
    }

    bool ApplyCase(HCGroupRequest request, string actor, int expected, string label)
    {
        if (m_Steps >= MAX_STEPS) return Require(false, "step_budget");
        string before;
        string encodeError;
        bool serialized = JsonFileLoader<HCGroupState>.MakeData(m_State, before, encodeError);
        if (!Require(serialized, "snapshot_before")) return false;
        int result = HCGroupRules.Apply(m_State, m_Config, request, actor, m_Now);
        m_Steps = m_Steps + 1;
        if (!Require(result == expected, label)) return false;
        if (expected != HCGroupCode.OK)
        {
            string after;
            bool checked = JsonFileLoader<HCGroupState>.MakeData(m_State, after, encodeError);
            if (!Require(checked && after == before, "rejected_state_changed")) return false;
        }
        return Require(HCGroupRules.StateValid(m_State, m_Config, "hc_synthetic_world"), "state_invalid");
    }
    bool BeginCases()
    {
        string owner = "fixture_alice";
        string member = "fixture_bob";
        string third = "fixture_charlie";
        HCGroupRequest request = Request(HCGroupOp.CREATE, owner);
        if (!ApplyCase(request, owner, HCGroupCode.OK, "create")) return false;
        if (!ApplyCase(request, owner, HCGroupCode.CONFLICT, "replay_create")) return false;
        request = Request(HCGroupOp.CREATE, "fixture_old_wire");
        request.Version = 1;
        if (!ApplyCase(request, "fixture_old_wire", HCGroupCode.INVALID, "old_wire_rejected")) return false;
        request = Request(HCGroupOp.INVITE, owner);
        request.TargetId = member;
        if (!ApplyCase(request, owner, HCGroupCode.OK, "invite")) return false;
        int inviteId = m_State.Invitations[0].Id;
        request = Request(HCGroupOp.ACCEPT, "fixture_mallory");
        request.EntityId = inviteId;
        if (!ApplyCase(request, "fixture_mallory", HCGroupCode.DENIED, "outsider_accept")) return false;
        request = Request(HCGroupOp.DECLINE, member);
        request.EntityId = inviteId;
        if (!ApplyCase(request, member, HCGroupCode.OK, "decline")) return false;
        if (!ApplyCase(request, member, HCGroupCode.NOT_FOUND, "replay_decline")) return false;
        request = Request(HCGroupOp.INVITE, owner);
        request.TargetId = member;
        if (!ApplyCase(request, owner, HCGroupCode.OK, "reinvite")) return false;
        request = Request(HCGroupOp.ACCEPT, member);
        request.EntityId = m_State.Invitations[0].Id;
        if (!ApplyCase(request, member, HCGroupCode.OK, "accept")) return false;
        if (!ApplyCase(request, member, HCGroupCode.NOT_FOUND, "replay_accept")) return false;
        request = Request(HCGroupOp.LEAVE, owner);
        if (!ApplyCase(request, owner, HCGroupCode.DENIED, "owner_leave")) return false;
        request = Request(HCGroupOp.INVITE, member);
        if (!ApplyCase(request, member, HCGroupCode.DENIED, "member_invite")) return false;
        request.Op = HCGroupOp.KICK;
        if (!ApplyCase(request, member, HCGroupCode.DENIED, "member_kick")) return false;
        request.Op = HCGroupOp.TRANSFER;
        if (!ApplyCase(request, member, HCGroupCode.DENIED, "member_transfer")) return false;
        request.Op = HCGroupOp.DISBAND;
        if (!ApplyCase(request, member, HCGroupCode.DENIED, "member_disband")) return false;
        request.Op = HCGroupOp.RENAME;
        if (!ApplyCase(request, member, HCGroupCode.DENIED, "member_rename")) return false;
        request = Request(HCGroupOp.INVITE, owner);
        request.TargetId = third;
        if (!ApplyCase(request, owner, HCGroupCode.OK, "third_invite")) return false;
        request = Request(HCGroupOp.RENAME, owner);
        request.Name = "Renamed synthetic group";
        if (!ApplyCase(request, owner, HCGroupCode.OK, "rename")) return false;
        if (!Require(m_State.Invitations[0].GroupName == request.Name, "invite_name_refreshed")) return false;
        request = Request(HCGroupOp.ACCEPT, third);
        request.EntityId = m_State.Invitations[0].Id;
        if (!ApplyCase(request, third, HCGroupCode.OK, "third_accept")) return false;
        request = Request(HCGroupOp.RENAME, owner);
        request.ExpectedRevision = request.ExpectedRevision - 1;
        return ApplyCase(request, owner, HCGroupCode.CONFLICT, "stale_revision");
    }
    bool MarkerCases()
    {
        string owner = "fixture_alice";
        string member = "fixture_bob";
        string third = "fixture_charlie";
        HCGroupRecord group = HCGroupRules.FindGroup(m_State, owner);
        HCGroupRequest request = Request(HCGroupOp.MARKER_CREATE, member);
        request.TtlSeconds = 60;
        if (!ApplyCase(request, member, HCGroupCode.OK, "marker_create")) return false;
        int markerId = group.Markers[0].Id;
        int deadline = group.Markers[0].ExpiresUtc;
        if (!Require(deadline == 1060, "initial_expiry")) return false;
        request = Request(HCGroupOp.MARKER_UPDATE, third);
        request.EntityId = markerId;
        if (!ApplyCase(request, third, HCGroupCode.DENIED, "marker_edit_acl")) return false;
        request.Op = HCGroupOp.MARKER_DELETE;
        if (!ApplyCase(request, third, HCGroupCode.DENIED, "marker_delete_acl")) return false;
        request = Request(HCGroupOp.MARKER_CREATE, owner);
        request.TtlSeconds = 1;
        if (!ApplyCase(request, owner, HCGroupCode.OK, "expiring_marker")) return false;
        int expiredId = group.Markers[1].Id;
        request = Request(HCGroupOp.MARKER_CREATE, owner);
        if (!ApplyCase(request, owner, HCGroupCode.LIMIT, "marker_limit")) return false;
        m_Now = 1005;
        request = Request(HCGroupOp.MARKER_DELETE, owner);
        request.EntityId = expiredId;
        if (!ApplyCase(request, owner, HCGroupCode.NOT_FOUND, "expired_marker")) return false;
        request = Request(HCGroupOp.MARKER_UPDATE, member);
        request.EntityId = markerId;
        request.Note = "Edited synthetic note";
        if (!ApplyCase(request, member, HCGroupCode.OK, "marker_update")) return false;
        if (!Require(group.Markers[0].ExpiresUtc == deadline, "expiry_preserved")) return false;
        if (!Require(group.Markers[0].Note == request.Note, "note_updated")) return false;
        if (!ApplyCase(request, member, HCGroupCode.CONFLICT, "replay_update")) return false;
        request = Request(HCGroupOp.MARKER_UPDATE, member);
        request.EntityId = markerId;
        request.TtlSeconds = 1;
        if (!ApplyCase(request, member, HCGroupCode.INVALID, "renewal_rejected")) return false;
        request = Request(HCGroupOp.MARKER_DELETE, member);
        request.EntityId = markerId;
        if (!ApplyCase(request, member, HCGroupCode.OK, "marker_delete")) return false;
        m_Config.MarkerRetentionSeconds = 0;
        request = Request(HCGroupOp.MARKER_CREATE, owner);
        if (!ApplyCase(request, owner, HCGroupCode.OK, "forever_create")) return false;
        int foreverId = group.Markers[1].Id;
        if (!Require(group.Markers[1].ExpiresUtc == 0, "forever_created")) return false;
        m_Config.MarkerRetentionSeconds = 604800;
        request = Request(HCGroupOp.MARKER_UPDATE, owner);
        request.EntityId = foreverId;
        if (!ApplyCase(request, owner, HCGroupCode.OK, "forever_update")) return false;
        if (!Require(group.Markers[1].ExpiresUtc == 0, "forever_preserved")) return false;
        request = Request(HCGroupOp.MARKER_DELETE, owner);
        request.EntityId = foreverId;
        return ApplyCase(request, owner, HCGroupCode.OK, "forever_delete");
    }
    bool FinishCases()
    {
        string owner = "fixture_alice";
        string member = "fixture_bob";
        string third = "fixture_charlie";
        HCGroupRequest request = Request(HCGroupOp.INVITE, owner);
        request.TargetId = "fixture_dave";
        if (!ApplyCase(request, owner, HCGroupCode.LIMIT, "member_limit")) return false;
        request = Request(HCGroupOp.TRANSFER, owner);
        request.TargetId = member;
        if (!ApplyCase(request, owner, HCGroupCode.OK, "transfer")) return false;
        HCGroupRecord group = HCGroupRules.FindGroup(m_State, member);
        if (!Require(group.OwnerId == member, "owner_transferred")) return false;
        request = Request(HCGroupOp.RENAME, owner);
        if (!ApplyCase(request, owner, HCGroupCode.DENIED, "former_owner")) return false;
        request = Request(HCGroupOp.KICK, member);
        request.TargetId = third;
        if (!ApplyCase(request, member, HCGroupCode.OK, "kick")) return false;
        if (!Require(!HCGroupRules.FindGroup(m_State, third), "kick_removed_acl")) return false;
        request = Request(HCGroupOp.MARKER_DELETE, third);
        if (!ApplyCase(request, third, HCGroupCode.DENIED, "kicked_actor")) return false;
        request = Request(HCGroupOp.LEAVE, owner);
        if (!ApplyCase(request, owner, HCGroupCode.OK, "leave")) return false;
        if (!Require(group.Members.Count() == 1, "leave_removed_acl")) return false;
        request = Request(HCGroupOp.DISBAND, member);
        if (!ApplyCase(request, member, HCGroupCode.OK, "disband")) return false;
        if (!ApplyCase(request, member, HCGroupCode.DENIED, "replay_disband")) return false;
        if (!Require(m_State.Groups.Count() == 0, "groups_empty")) return false;
        return Require(m_State.Invitations.Count() == 0, "invitations_empty");
    }

    bool Exercise()
    {
        m_State.WorldName = "hc_synthetic_world";
        m_Config.Enabled = true;
        m_Config.MaxGroups = 2;
        m_Config.MaxMembers = 3;
        m_Config.MaxMarkers = 2;
        m_Config.MaxInvites = 2;
        HCGroupRequest request = new HCGroupRequest;
        HCGroupSnapshot snapshot = new HCGroupSnapshot;
        HCGroupReply reply = new HCGroupReply;
        HCGroupReceipt receipt = new HCGroupReceipt;
        if (!Require(HCGroupProtocol.VERSION == 2 && request.Version == 2, "wire_version")) return false;
        if (!Require(snapshot.Version == 2 && reply.Version == 2, "wire_dto_version")) return false;
        if (!Require(m_State.Version == 1 && receipt.Version == 1, "durable_version")) return false;
        if (!BeginCases()) return false;
        if (!MarkerCases()) return false;
        if (!FinishCases()) return false;
        return Require(m_Steps > 0 && m_Steps <= MAX_STEPS, "step_total");
    }

    static bool Run(out string error)
    {
        error = "";
        HCGroupNativeChecks fixture = new HCGroupNativeChecks;
        bool passed = fixture.Exercise();
        error = fixture.Error();
        if (!passed) return false;
        Print(fixture.Completion());
        return true;
    }
}
