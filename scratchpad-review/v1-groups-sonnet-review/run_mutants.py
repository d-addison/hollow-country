import shutil, subprocess, sys, os, re
SRC='/code/hc-worktrees/v1-groups'
BASE=os.path.join(SRC,'scratchpad-review/v1-groups-sonnet-review/mut')
S='mods/HollowCountry/scripts/'
R=S+'4_World/Groups/HCGroupRules.c'; V=S+'4_World/Groups/HCGroupService.c'; Q=S+'4_World/Groups/HCGroupVisibility.c'
C=S+'5_Mission/Groups/HCGroupClient.c'; L=S+'5_Mission/Groups/HCGroupMapLayers.c'; D=S+'3_Game/Groups/HCGroupData.c'
M=[
('M00 baseline unmutated','mods/HollowCountry/scripts/4_World/Groups/HCGroupRules.c','static int Apply','static int Apply'),
('M01 SET_ROLE owner-only guard off',R,'''        if (q.Op == HCGroupOp.SET_ROLE)
        {
            if (!owner)''','''        if (q.Op == HCGroupOp.SET_ROLE)
        {
            if (false)'''),
('M02 officer may kick officers/owner',R,'if (!owner && q.Op == HCGroupOp.KICK && HCGroupRules.Role(group, q.TargetId) != HCGroupRole.MEMBER)','if (false)'),
('M03 officer may transfer',R,'if (!owner && (q.Op == HCGroupOp.TRANSFER || q.Op == HCGroupOp.DISBAND))','if (!owner && q.Op == HCGroupOp.DISBAND)'),
('M04 officer may disband',R,'if (!owner && (q.Op == HCGroupOp.TRANSFER || q.Op == HCGroupOp.DISBAND))','if (!owner && q.Op == HCGroupOp.TRANSFER)'),
('M05 kick leaves stale officer',R,'''            else
            {
                HCGroupRules.RemoveOfficer(group, q.TargetId);
                group.Members.Remove(memberIndex);''','''            else
            {
                group.Members.Remove(memberIndex);'''),
('M06 leave leaves stale officer',R,'''            HCGroupRules.RemoveOfficer(group, actor);
            group.Members.Remove''','''            group.Members.Remove'''),
('M07 transfer keeps new owner in officers',R,'''                HCGroupRules.RemoveOfficer(group, q.TargetId);
                group.OwnerId = q.TargetId;''','''                group.OwnerId = q.TargetId;'''),
('M08 member may invite (officer check off)',R,'''        if (q.Op == HCGroupOp.INVITE)
        {
            if (!officer)''','''        if (q.Op == HCGroupOp.INVITE)
        {
            if (false)'''),
('M09 marker edit any member',R,'if (!officer && marker.CreatorId != actor)','if (false)'),
('M10 rename any member',R,'''            if (!officer)
            {
                return HCGroupCode.DENIED;
            }
            if (!owner && (q.Op''','''            if (false)
            {
                return HCGroupCode.DENIED;
            }
            if (!owner && (q.Op'''),
('M11 SET_ROLE keeps stale invites',R,'''            HCGroupRules.DropInvites(state, group.Id, "");
            HCGroupRules.Touch(group, true);
            return HCGroupCode.OK;
        }
        if (q.Op == HCGroupOp.INVITE)''','''            HCGroupRules.Touch(group, true);
            return HCGroupCode.OK;
        }
        if (q.Op == HCGroupOp.INVITE)'''),
('M12 SET_ROLE allows role 2 (owner)',R,'q.Role < 0 || q.Role > 1','q.Role < 0 || q.Role > 2'),
('M13 StateValid ignores officer not member',R,'|| group.Members.Find(officerId) < 0','' ),
('M14 StateValid allows owner as officer',R,'officerId == group.OwnerId || ',''),
('M15 invite validity any member',R,'HCGroupRules.Role(offered, invite.InviterId) < HCGroupRole.OFFICER','HCGroupRules.Role(offered, invite.InviterId) < HCGroupRole.MEMBER'),
('M16 RecordVisit radius ignored',R,'if (dx * dx + dz * dz > place.Radius * place.Radius)','if (false)'),
('M17 RecordVisit ignores MaxDiscoveries',R,'if (found.Visits.Count() >= c.MaxDiscoveries)','if (false)'),
('M18 RecordVisit ignores MaxExplorers',R,'if (state.Explorers.Count() >= c.MaxExplorers)','if (false)'),
('M19 RecordVisit ignores DiscoveryLayer off',R,'if (!c.DiscoveryLayer || !HCGroupRules.PlaceValid(place)','if (!HCGroupRules.PlaceValid(place)'),
('M20 KnownPlaces leaks every explorer',R,'bool permitted = explorer.Id == uid;','bool permitted = true;'),
('M21 ShareDiscovery ignores membership',R,'group.Members.Find(explorer.Id) >= 0','true'),
('M22 ShareDiscovery ignores setting',R,'if (c.ShareDiscovery && group &&','if (group &&'),
('M23 KnownPlaces unbounded',R,'&& known.Count() < c.MaxDiscoveries',''),
('M24 DiscoveryLayer off still lists',R,'''        if (!c.DiscoveryLayer)
        {
            return known;
        }
        HCGroupRecord group''','''        HCGroupRecord group'''),
('M25 visibility filter not applied',V,'&& VisibilityAllows(source, recipient))',')'),
('M26 LOS ray budget off',V,'if (m_LOSRays >= m_Config.MaxLOSRaysPerTick) return false;',''),
('M27 LOS ray not counted',V,'m_LOSRays++;',''),
('M28 LOS skipped',V,'if (!HCGroupVisibility.HasLOS(source.Player, recipient.Player)) return false;',''),
('M29 radio skipped',V,'if (!HCGroupVisibility.RadioMatches(sourceGear, recipientGear)) return false;',''),
('M30 unconscious sources visible',V,'if (source.Player.IsUnconscious() || recipient.Player.IsUnconscious()) return false;',''),
('M31 tick ray budget never reset',V,'        m_LOSRays = 0;\n',''),
('M32 radio always matches',Q,'if (recipient.Frequencies.Find(frequency) >= 0) return true;','return true;'),
('M33 LOS: any hit allowed',Q,'return hits.Count() == 1 && hits.Get(0) == recipient;','return true;'),
('M34 LOS: unknown bone allowed',Q,'if (sourceBone < 0 || recipientBone < 0) return false;',''),
('M35 radio: not-working accepted',Q,'if (!handheld.GetCompEM().IsWorking()) continue;',''),
('M36 radio: not-owned accepted',Q,'|| item.GetHierarchyRootPlayer() != player',''),
('M37 radio: ruined accepted',Q,'item.IsRuined() ||',''),
('M38 gps: off accepted',Q,'if (gps && gps.IsTurnedOn()) equipment.HasGPS = true;','if (gps) equipment.HasGPS = true;'),
('M39 equipment over-budget accepted',Q,'if (items.Count() > 512) return equipment;',''),
('M40 radio base transmitter accepted',Q,'if (!handheld || !handheld.IsTransmitter() || !handheld.GetCompEM()) continue;','if (!handheld || !handheld.GetCompEM()) continue;'),
('M41 places only when alive off',V,'kind == HCGroupSnapshotKind.FULL && peer.Player.IsAlive())','kind == HCGroupSnapshotKind.FULL)'),
('M42 places sent on POSITIONS too',V,'kind == HCGroupSnapshotKind.FULL && peer.Player.IsAlive())','peer.Player.IsAlive())'),
('M43 discover skips alive/uncons check',V,'if (!Live(explorer) || !explorer.Player.IsAlive() || explorer.Player.IsUnconscious()) continue;','if (!Live(explorer)) continue;'),
('M44 discover examines unbounded',V,'while (examined < 6 && examined < m_Peers.Count())','while (examined < m_Peers.Count())'),
('M45 mission layer shows expired',L,'row.RemainingSeconds <= 0 || ',''),
('M46 mission layer ignores setting',L,'if (!settings.MissionLayer) return;',''),
('M47 mission layer stale OK',L,'if (!events || !events.Fresh())','if (!events)'),
('M48 grid without map',L,'if (!equipment.HasMap) return;',''),
('M49 coords without GPS',L,'if (!equipment.HasGPS)','if (false)'),
('M50 navigation layer setting ignored',L,'if (!settings.NavigationLayer) return;',''),
('M51 client accepts unbounded places',C,'frame.Places.Count() > frame.Settings.MaxDiscoveries','false'),
('M52 client accepts bad member role',C,'member.Role < HCGroupRole.MEMBER || member.Role > HCGroupRole.OWNER','false'),
('M53 settings IconScale unbounded',R,'if (!(c.IconScale >= 0.75 && c.IconScale <= 2.0))','if (false)'),
('M54 settings Rays unbounded',R,'c.MaxLOSRaysPerTick < 1 || c.MaxLOSRaysPerTick > 256','false'),
('M55 settings DiscoveryInterval too small',R,'c.DiscoveryIntervalSeconds >= 5.0 &&',''),
('M56 PlaceValid radius unbounded',R,'place.Radius >= 5.0 && place.Radius <= 500.0','true'),
('M57 ExplorersValid MaxExplorers',R,'state.Explorers.Count() > c.MaxExplorers','false'),
('M58 ExplorersValid dup visit',R,'|| places.Find(visited.Id) >= 0',''),
('M59 Apply op range 13 off',R,'q.Op > 13','q.Op > 12'),
('M60 Discover commit not broadcast',V,'if (result == HCGroupCode.OK) Broadcast();\n    }\n\n    HCGroupMember','}\n\n    HCGroupMember'),
('M61 Member roles not set',V,'rosterMember.Role = HCGroupRules.Role(group, uid);',''),
('M62 DiscoveryLayer start refusal off',V,'''            if (!m_Places)
            {''','''            if (false)
            {'''),
]
only=sys.argv[1:]
def setup():
    if os.path.exists(BASE): shutil.rmtree(BASE)
    os.makedirs(BASE)
    for d in ['mods','tests','tools','config']:
        shutil.copytree(os.path.join(SRC,d),os.path.join(BASE,d),ignore=shutil.ignore_patterns('__pycache__'))
setup()
mods=['tests.unit.test_group_server','tests.unit.test_v1_groups','tests.unit.test_group_persistence','tests.unit.test_group_ui','tests.unit.test_group_native_checks','tests.unit.test_group_client','tests.unit.test_group_gameplay_wiring']
import glob
mods=['tests.unit.'+os.path.basename(f)[:-3] for f in glob.glob(os.path.join(BASE,'tests/unit/test_group*.py'))+[os.path.join(BASE,'tests/unit/test_v1_groups.py')]]
res=[]
for name,f,a,b in M:
    if only and not any(name.startswith(o) for o in only): continue
    p=os.path.join(BASE,f); orig=open(p).read()
    if a not in orig: res.append((name,'PATTERN-MISSING'));print(name,'PATTERN-MISSING',flush=True);continue
    open(p,'w').write(orig.replace(a,b,1))
    r=subprocess.run([sys.executable,'-B','-m','unittest']+mods,cwd=BASE,capture_output=True,text=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
    open(p,'w').write(orig)
    out=r.stderr.strip().splitlines()
    failed=[l for l in out if l.startswith(('FAIL:','ERROR:'))]
    status='KILLED' if r.returncode!=0 else 'SURVIVED'
    res.append((name,status));print(name,status,(failed[0][:90] if failed else ''),flush=True)
