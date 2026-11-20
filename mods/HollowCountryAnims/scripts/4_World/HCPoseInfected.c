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
// #279 CE route: HC_ZmbM_Sitter/Sleeper/Riser/Feeder (poses 1..4) and HC_ZmbM_Crawler
// (vanilla graph, native crawl request) are public classes added as children of the
// stock infected events by tools/package/infected_variety.py, so the vanilla CE owns
// spawn, caps and cleanup. EEInit requests this class's pose once; the MaxPosed budget
// still bounds held poses (a body over budget stays a normal standing infected).
// Counters live in the base mod (HCVarietyCounters); per-body lines are capped.
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
	protected bool m_HCPlaying;        // our command was observed as the current command

	//! Pose this class takes when the CE (or a test helper) creates it.
	int HCSpawnPose()
	{
		return HCVarietyCounters.KIND_SIT;
	}

	//! Server: only authored modes admitted by the shared owner may acquire a slot.
	bool HCRequestPose(int pose)
	{
		if (!g_Game.IsServer() || !IsAlive())
			return false;
		// Operator off switches: EnableInfectedVariety=false, infected_variety.disable
		// (both via the variety owner) or infected_poses.disable. Wake/release stay open.
		if (pose != 0 && (!HCInfectedVarietyModule.VarietyActive() || HCInfectedVariety.HCPosesOptedOut()))
		{
			HCVarietyCounters.HCAdd(HCVarietyCounters.REFUSED_OPTOUT);
			return false;
		}
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
				HCVarietyCounters.HCAdd(HCVarietyCounters.REFUSED_BUDGET);
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
			HCVarietyCounters.HCAdd(HCVarietyCounters.POSED);
			HCVarietyCounters.HCSetHeld(s_HCPosed);
		}
		m_HCPose = pose;
		if (HCVarietyCounters.HCDetail())
			Print("[HollowCountryAnims] pose request class=" + GetType() + " pose=" + pose.ToString() + " posed=" + s_HCPosed.ToString() + " runtime=PENDING");
		return true;
	}

	protected bool HCRefusePose(int pose)
	{
		HCVarietyCounters.HCAdd(HCVarietyCounters.REFUSED_ADMISSION);
		string reason = HCPostureAdmission.HCPostureRefusal(HCPostureAdmission.HCPoseMode(pose));
		if (reason != s_HCLastRefusal)
		{
			s_HCLastRefusal = reason;
			Print("[HollowCountryAnims] pose refused pose=" + pose.ToString() + " reason=" + reason + " runtime=PENDING");
		}
		return false;
	}

	//! Begin the get-up once from a held pose; the command plays it, then vanilla resumes.
	protected bool HCWake(int cause)
	{
		if (!m_HCHolding || m_HCPose == 0)
			return false;
		m_HCPose = 0;
		HCVarietyCounters.HCAdd(cause);
		if (HCVarietyCounters.HCDetail())
			Print("[HollowCountryAnims] pose wake class=" + GetType() + " cause=" + cause.ToString() + " runtime=PENDING");
		return true;
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
		if (!HCWake(HCVarietyCounters.WOKEN_OTHER))
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

	//! ended: 0 none (not holding), else the HCVarietyCounters slot describing the end.
	protected void HCRelease(int ended = 0)
	{
		if (m_HCHolding)
		{
			m_HCHolding = false;
			s_HCPosed--;
			HCVarietyCounters.HCSetHeld(s_HCPosed);
			if (ended > 0)
				HCVarietyCounters.HCAdd(ended);
		}
		m_HCPose = 0;
		m_HCStarted = false;
		m_HCRising = false;
		m_HCPlaying = false;
	}

	override bool ModCommandHandlerBefore(float pDt, int pCurrentCommandID, bool pCurrentCommandFinished)
	{
		if (!m_HCHolding)
			return super.ModCommandHandlerBefore(pDt, pCurrentCommandID, pCurrentCommandFinished);
		if (!IsAlive())
		{
			HCRelease(HCVarietyCounters.DELETED);
			return false;
		}
		if (m_HCPose != 0)
		{
			// Native perception only: the AI's own mind state, never a player scan.
			DayZInfectedInputController ic = GetInputController();
			if (ic && ic.GetMindState() >= DayZInfectedConstants.MINDSTATE_ALERTED)
				HCWake(HCVarietyCounters.WOKEN_MIND);   // the command plays the get-up, then vanilla takes over
		}
		if (pCurrentCommandID == DayZInfectedConstants.COMMANDID_SCRIPT)
		{
			if (m_HCStarted && !m_HCPlaying)
			{
				m_HCPlaying = true;
				HCVarietyCounters.HCAdd(HCVarietyCounters.PLAYING);
			}
			return false;   // ours is running; vanilla death/hit/attack handlers still run
		}
		if (m_HCStarted || m_HCPose == 0)
		{
			// Our command finished its get-up or was replaced by a vanilla command.
			int ended = HCVarietyCounters.INTERRUPTED;
			if (m_HCRising && pCurrentCommandID == DayZInfectedConstants.COMMANDID_MOVE)
				ended = HCVarietyCounters.RISEN;
			HCRelease(ended);
			if (HCVarietyCounters.HCDetail())
				Print("[HollowCountryAnims] pose released class=" + GetType() + " ended=" + ended.ToString() + " posed=" + s_HCPosed.ToString() + " runtime=PENDING");
			return false;
		}
		StartCommand_ScriptInst(HCPoseCommand);
		m_HCStarted = true;
		if (HCVarietyCounters.HCDetail())
			Print("[HollowCountryAnims] pose command started class=" + GetType() + " pose=" + m_HCPose.ToString() + " runtime=PENDING");
		return true;
	}

	//! Damage while posed starts the get-up; vanilla HandleDamageHit may replace it with a hit.
	override void EEHitBy(TotalDamageResult damageResult, int damageType, EntityAI source, int component, string dmgZone, string ammo, vector modelPos, float speedCoef)
	{
		if (g_Game.IsServer())
			HCWake(HCVarietyCounters.WOKEN_HIT);
		super.EEHitBy(damageResult, damageType, source, component, dmgZone, ammo, modelPos, speedCoef);
	}

	//! One bounded admission request; unsupported modes keep native AI unchanged.
	override void EEInit()
	{
		super.EEInit();
		if (g_Game.IsServer())
		{
			HCVarietyCounters.HCSpawned(HCSpawnPose());
			HCRequestPose(HCSpawnPose());
		}
	}

	override void EEDelete(EntityAI parent)
	{
		HCRelease(HCVarietyCounters.DELETED);
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

// #279 CE variants: same pose layer, a different spawn pose. Config parents (outfits)
// are vanilla civilian males whose script bases are empty, so behaviour is unchanged.
class HC_ZmbM_Sleeper extends HC_ZmbM_Sitter
{
	override int HCSpawnPose()
	{
		return HCVarietyCounters.KIND_SLEEP;
	}
}

class HC_ZmbM_Riser extends HC_ZmbM_Sitter
{
	override int HCSpawnPose()
	{
		return HCVarietyCounters.KIND_RISER;
	}
}

class HC_ZmbM_Feeder extends HC_ZmbM_Sitter
{
	override int HCSpawnPose()
	{
		return HCVarietyCounters.KIND_FEED;
	}
}

// #279 CE crawler on the vanilla graph. EEInit sets the SAME request the vanilla
// injury path uses (ZombieBase.c:809 m_CrawlTransition, consumed by :811-824
// HandleCrawlTransition, which starts StartCommand_Crawl and syncs m_IsCrawling).
// No health edit, no teleport; native AI drives the crawler and never stands it up.
// The CE spawns it away from players, so the fall into the crawl is not watched.
class HC_ZmbM_Crawler extends ZmbM_CitizenASkinny_Base
{
	protected bool m_HCCrawlSeen;

	override void EEInit()
	{
		super.EEInit();
		if (!g_Game.IsServer())
			return;
		HCVarietyCounters.HCSpawned(HCVarietyCounters.KIND_CRAWL);
		// Same operator gate as the posed classes: with variety off it stays a
		// normal standing infected and counts as refused_optout.
		if (!HCInfectedVarietyModule.VarietyActive())
		{
			HCVarietyCounters.HCAdd(HCVarietyCounters.REFUSED_OPTOUT);
			return;
		}
		if (IsAlive() && !IsCrawling())
			m_CrawlTransition = 0;
	}

	override bool ModCommandHandlerBefore(float pDt, int pCurrentCommandID, bool pCurrentCommandFinished)
	{
		if (!m_HCCrawlSeen && pCurrentCommandID == DayZInfectedConstants.COMMANDID_CRAWL && g_Game.IsServer())
		{
			m_HCCrawlSeen = true;
			HCVarietyCounters.HCAdd(HCVarietyCounters.CRAWLING);
			if (HCVarietyCounters.HCDetail())
				Print("[HollowCountryAnims] crawler crawling class=" + GetType() + " runtime=PENDING");
		}
		return super.ModCommandHandlerBefore(pDt, pCurrentCommandID, pCurrentCommandFinished);
	}
}
