// Hollow Country posed infected: server-side request hook for the HCMasterControl pose layer.
// Experimental: compiled and played by nobody yet; native and two-client acceptance pending.
//
// HC_ZmbM_Sitter asks to sit by itself 2 s after server-side init (EEInit), so spawning it by
// class name is enough. Server code may also call HCRequestPose(1) (sit) or (0) (get up).
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
//   4_World/Entities/Creatures/Infected/ZombieBase.c:203 ModCommandHandlerBefore runs first in CommandHandler
//   4_World/Entities/Creatures/Infected/ZombieMaleBase.c:76 ZmbM_HermitSkinny_Base

class HCPoseCommand extends DayZInfectedCommandScript
{
	static const float RISE_SECONDS = 1.7;    // hc_sit_wall_getup is 1.6 s
	static const float RESEND_SECONDS = 2.0;  // re-announce the pose for clients that streamed in late

	protected HC_ZmbM_Sitter m_HCOwner;
	protected int m_HCSent;
	protected float m_HCRise;
	protected float m_HCResend;

	void HCPoseCommand(DayZInfected pInfected)
	{
		m_HCOwner = HC_ZmbM_Sitter.Cast(pInfected);
		m_HCSent = -1;
		m_HCRise = -1;
		m_HCResend = 0;
	}

	override void OnActivate()
	{
		if (m_HCOwner)
			HCSend(m_HCOwner.HCWantedPose());
	}

	protected void HCSend(int pose)
	{
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
			if (m_HCRise > RISE_SECONDS)
				SetFlagFinished(true);
			return;
		}
		int wanted = m_HCOwner.HCWantedPose();
		m_HCResend += pDt;
		if (wanted != m_HCSent || m_HCResend > RESEND_SECONDS)
		{
			HCSend(wanted);
			if (wanted == 0)
				m_HCRise = 0;
		}
	}

	override bool PostPhysUpdate(float pDt)
	{
		return true;
	}
}

class HC_ZmbM_Sitter extends ZmbM_HermitSkinny_Base
{
	static const int MAX_POSED = 12;   // server-wide budget of posed infected
	static int s_HCPosed;

	protected int m_HCPose;            // 0 stand, 1 sit against a wall or tree
	protected bool m_HCHolding;        // holds one MAX_POSED slot
	protected bool m_HCStarted;        // our scripted command was started
	protected int m_HCPoseCmd = -1;
	protected int m_HCPoseVar = -1;

	//! Server: request a pose. False when not the server, dead, or the posed budget is full.
	bool HCRequestPose(int pose)
	{
		if (!g_Game.IsServer() || !IsAlive())
			return false;
		if (pose == m_HCPose)
			return true;
		if (pose != 0 && !m_HCHolding)
		{
			if (s_HCPosed >= MAX_POSED)
			{
				Print("[HollowCountryAnims] pose refused budget=" + MAX_POSED.ToString());
				return false;
			}
			s_HCPosed++;
			m_HCHolding = true;
		}
		m_HCPose = pose;
		Print("[HollowCountryAnims] pose request pose=" + pose.ToString() + " posed=" + s_HCPosed.ToString());
		return true;
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

	protected void HCRelease()
	{
		if (m_HCHolding)
		{
			m_HCHolding = false;
			s_HCPosed--;
		}
		m_HCPose = 0;
		m_HCStarted = false;
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
			Print("[HollowCountryAnims] pose released posed=" + s_HCPosed.ToString());
			return false;
		}
		StartCommand_ScriptInst(HCPoseCommand);
		m_HCStarted = true;
		Print("[HollowCountryAnims] pose command started pose=" + m_HCPose.ToString());
		return true;
	}

	//! Server: sit by itself once the AI is running (spawned by class name, CE or script).
	override void EEInit()
	{
		super.EEInit();
		if (g_Game.IsServer())
			g_Game.GetCallQueue(CALL_CATEGORY_GAMEPLAY).CallLater(HCRequestSit, 2000, false);
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
