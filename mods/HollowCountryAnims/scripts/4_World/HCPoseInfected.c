// Hollow Country posed infected: server-side request hook for the HCMasterControl pose layer.
// Experimental: compiled and played by nobody yet; native and two-client acceptance pending.
//
// Issue #225: all four pose pairs have source generators and graph states. Admission
// remains owned by HCPostureAdmission; the lead must apply the exact scope-boundary
// patch in docs/ANIMATION_PIPELINE.md. No runtime verdict is implied by authoring.
// One synchronized command, pose int and HCPoseFrom identify the get-up being left.
// No re-pose while rising; Variety wake paths still reach HCVarietyPoseWake.
// EEInit submits one request synchronously; no retained CallLater callback can
// outlive deletion. Pose 0 remains cleanup.
// A scripted command holds the infected still and sends the synchronized graph command
// CMD_HC_POSE (int param = pose); hc_poses.agf enters/leaves the pose on that command and
// returns to the vanilla MasterControl on any vanilla death/hit/crawl/attack/vault command.
// Vanilla handlers keep running every tick (we never swallow death or hits); a posed infected
// stands up by itself once its mind state reaches ALERTED.
//
// Native API (scripts-1.30.164289):
//   3_Game/Entities/DayZInfected.c:10 COMMANDID_SCRIPT, :67 DayZInfectedCommandScript,
//     :77 SetFlagFinished, :94 PostPhysUpdate, :123 StartCommand_ScriptInst, :124 GetCommand_Script
//   3_Game/Anim/AnimCommand.c:13 OnActivate, :20 PreAnimUpdate, :27 PreAnim_CallCommand, :29 PreAnim_SetInt
//   3_Game/Entities/DayZAnimal.c:10 BindCommand, :14 BindVariableInt, :35 GetAnimInterface,
//     :175 ModCommandHandlerBefore
//   3_Game/Entities/DayZInfectedInputController.c:9 GetMindState
//   3_Game/Entities/EntityAI.c:905 EEInit, :946 EEDelete
//   3_Game/Global/Game.c:703 CreateObjectEx; 3_Game/CE/CentralEconomy.c:18 ECE_INITAI, :38 ECE_PLACE_ON_SURFACE
//   3_Game/Entities/Object.c:311 SetOrientation
//   1_Core/proto/EnDebug.c:96 Print
//   4_World/Entities/Creatures/Infected/ZombieBase.c:203 ModCommandHandlerBefore runs first in CommandHandler
//   4_World/Entities/Creatures/Infected/ZombieMaleBase.c:76 ZmbM_HermitSkinny_Base

class HCPoseCommand extends DayZInfectedCommandScript
{
	static const float RESEND_SECONDS = 2.0;  // re-announce the pose for clients that streamed in late

	protected HC_ZmbM_Sitter m_HCOwner;
	protected int m_HCSent;
	protected float m_HCRise;
	protected int m_HCRiseFrom;   // pose being left; its clip length bounds the rise
	protected float m_HCResend;

	void HCPoseCommand(DayZInfected pInfected)
	{
		m_HCOwner = HC_ZmbM_Sitter.Cast(pInfected);
		m_HCSent = -1;
		m_HCRise = -1;
		m_HCRiseFrom = -1;
		m_HCResend = 0;
	}

	override void OnActivate()
	{
		if (m_HCOwner)
			HCSend(m_HCOwner.HCWantedPose());
	}

	protected void HCSend(int pose)
	{
		int leaving = 0;
		if (m_HCSent > 0) { leaving = m_HCSent; }
		PreAnim_SetInt(m_HCOwner.HCPoseFromVariable(), leaving);
		PreAnim_SetInt(m_HCOwner.HCPoseVariable(), pose);
		PreAnim_CallCommand(m_HCOwner.HCPoseCommandId(), pose, 0);
		m_HCSent = pose;
		m_HCResend = 0;
	}

	override void PreAnimUpdate(float pDt)
	{
		if (!m_HCOwner)
		{
			SetFlagFinished(true);
			return;
		}
		if (m_HCRise >= 0)
		{
			m_HCRise += pDt;
			if (m_HCRise > HCPostureAdmission.HCRiseSeconds(m_HCRiseFrom))
				SetFlagFinished(true);
			return;
		}
		int wanted = m_HCOwner.HCWantedPose();
		m_HCResend += pDt;
		if (wanted != m_HCSent || m_HCResend > HCPoseCommand.RESEND_SECONDS)
		{
			int leaving = m_HCSent;
			HCSend(wanted);
			if (wanted == 0)
			{
				m_HCRiseFrom = leaving;
				m_HCRise = 0;
				m_HCOwner.HCNoteRise();
			}
		}
	}

	override bool PostPhysUpdate(float pDt)
	{
		return true;
	}
}

class HC_ZmbM_Sitter extends ZmbM_HermitSkinny_Base
{
	static int s_HCPosed;

	protected int m_HCPose;            // 0 stand, 1 sit against a wall or tree, 2 flat sleeper, 3 lying riser, 4 kneel feeding
	protected bool m_HCHolding;        // holds one configured MaxPosed slot
	protected bool m_HCStarted;        // our scripted command was started
	protected bool m_HCRising;         // the get-up clip is playing; no new pose until it ends
	static string s_HCLastRefusal;     // print-once-per-change refusal reason
	protected int m_HCPoseCmd = -1;
	protected int m_HCPoseVar = -1;
	protected int m_HCPoseFromVar = -1;

	//! Server: only authored modes admitted by the shared owner may acquire a slot.
	bool HCRequestPose(int pose)
	{
		if (!g_Game.IsServer() || !IsAlive())
			return false;
		if (pose != 0 && HCInfectedVariety.HCPosesOptedOut())
			return false;
		if (pose != 0 && !HCPostureAdmission.HCCanEnter(HCPostureAdmission.HCPoseMode(pose)))
			return HCRefusePose(pose);
		if (pose != 0 && (m_HCRising || (m_HCStarted && pose != m_HCPose)))
			return false;   // finish the get-up (interruption safety); never snap into a new pose
		if (pose == m_HCPose)
			return true;
		if (pose != 0 && !m_HCHolding)
		{
			int maxPosed = HCInfectedVariety.HCMaxPosed();
			if (s_HCPosed >= maxPosed)
			{
				string budgetReason = "max_posed_budget=" + maxPosed.ToString();
				if (budgetReason != s_HCLastRefusal)
				{
					s_HCLastRefusal = budgetReason;
					Print("[HollowCountryAnims] pose refused reason=" + budgetReason + " runtime=PENDING");
				}
				return false;
			}
			s_HCPosed++;
			m_HCHolding = true;
		}
		m_HCPose = pose;
		Print("[HollowCountryAnims] pose request pose=" + pose.ToString() + " posed=" + s_HCPosed.ToString() + " runtime=PENDING");
		return true;
	}

	protected bool HCRefusePose(int pose)
	{
		string reason = HCPostureAdmission.HCPostureRefusal(HCPostureAdmission.HCPoseMode(pose));
		if (reason != s_HCLastRefusal)
		{
			s_HCLastRefusal = reason;
			Print("[HollowCountryAnims] pose refused pose=" + pose.ToString() + " reason=" + reason + " runtime=PENDING");
		}
		return false;
	}

	//! Called by our command when the get-up clip starts; cleared on release.
	void HCNoteRise()
	{
		m_HCRising = true;
	}

	//! Variety fresh posed body: the pose layer holds it; Variety owns the wake.
	override bool HCVarietyPoseRequest(int pose)
	{
		return HCRequestPose(pose);
	}

	//! Variety wake (proximity, noise, shot, damage, cap, stop): begin the get-up once.
	override void HCVarietyPoseWake()
	{
		HCRequestPose(0);
	}

	int HCWantedPose()
	{
		return m_HCPose;
	}

	int HCPoseCommandId()
	{
		if (m_HCPoseCmd < 0)
			m_HCPoseCmd = GetAnimInterface().BindCommand("CMD_HC_POSE");
		return m_HCPoseCmd;
	}

	int HCPoseVariable()
	{
		if (m_HCPoseVar < 0)
			m_HCPoseVar = GetAnimInterface().BindVariableInt("HCPose");
		return m_HCPoseVar;
	}

	int HCPoseFromVariable()
	{
		if (m_HCPoseFromVar < 0)
			m_HCPoseFromVar = GetAnimInterface().BindVariableInt("HCPoseFrom");
		return m_HCPoseFromVar;
	}

	protected void HCRelease()
	{
		if (m_HCHolding)
		{
			m_HCHolding = false;
			s_HCPosed--;
		}
		m_HCPose = 0;
		m_HCStarted = false;
		m_HCRising = false;
	}

	override bool ModCommandHandlerBefore(float pDt, int pCurrentCommandID, bool pCurrentCommandFinished)
	{
		if (!m_HCHolding)
			return super.ModCommandHandlerBefore(pDt, pCurrentCommandID, pCurrentCommandFinished);
		if (!IsAlive())
		{
			HCRelease();
			return false;
		}
		if (m_HCPose != 0)
		{
			DayZInfectedInputController ic = GetInputController();
			if (ic && ic.GetMindState() >= DayZInfectedConstants.MINDSTATE_ALERTED)
				m_HCPose = 0;   // wake: the command plays the get-up, then vanilla takes over
		}
		if (pCurrentCommandID == DayZInfectedConstants.COMMANDID_SCRIPT)
			return false;   // ours is running; vanilla death/hit/attack handlers still run
		if (m_HCStarted || m_HCPose == 0)
		{
			// Our command finished its get-up or was replaced by a vanilla command.
			HCRelease();
			Print("[HollowCountryAnims] pose released posed=" + s_HCPosed.ToString() + " runtime=PENDING");
			return false;
		}
		StartCommand_ScriptInst(HCPoseCommand);
		m_HCStarted = true;
		Print("[HollowCountryAnims] pose command started pose=" + m_HCPose.ToString() + " runtime=PENDING");
		return true;
	}

	//! One bounded admission request; unsupported modes keep native AI unchanged.
	override void EEInit()
	{
		super.EEInit();
		if (g_Game.IsServer())
			HCRequestSit();
	}

	override void EEDelete(EntityAI parent)
	{
		HCRelease();
		super.EEDelete(parent);
	}

	//! Server test helper: spawn one sitter facing yaw; it sits by itself (EEInit).
	static HC_ZmbM_Sitter HCSpawnSitting(vector pos, float yaw)
	{
		HC_ZmbM_Sitter z = HC_ZmbM_Sitter.Cast(g_Game.CreateObjectEx("HC_ZmbM_Sitter", pos, ECE_PLACE_ON_SURFACE | ECE_INITAI));
		if (!z)
			return null;
		z.SetOrientation(Vector(yaw, 0, 0));
		return z;
	}

	void HCRequestSit()
	{
		HCRequestPose(1);
	}
}
