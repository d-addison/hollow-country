// Each hooked entity remembers whether the bounded registry accepted it: a
// repeated EEInit never rebinds (no registry duplicate scan), and only bound
// entities pay the registry walk on EEKilled/EEDelete. Native evidence
// (scripts-1.30.164289): 3_Game/Entities/EntityAI.c:905 EEInit, :946 EEDelete,
// :1104 EEKilled; the flag is script state only, never replicated.
modded class AnimalBase
{
	protected bool m_HCEcoRegistered;

	override void EEInit()
	{
		super.EEInit();
		if (!m_HCEcoRegistered) { m_HCEcoRegistered = HCEcologyRuntime.Register(this, true); }
		// HC-15: only animals the ecology cohort accepted; HCRegister is a no-op off the server.
		if (m_HCEcoRegistered) { HCWildlifeObservation.HCRegister(this); }
	}

	override void EEKilled(Object killer)
	{
		if (m_HCEcoRegistered)
		{
			m_HCEcoRegistered = false;
			HCEcologyRuntime.Unregister(this);
		}
		super.EEKilled(killer);
	}

	override void EEDelete(EntityAI parent)
	{
		if (m_HCEcoRegistered)
		{
			m_HCEcoRegistered = false;
			HCEcologyRuntime.Unregister(this);
		}
		// HC-15 keeps killed animals (carcass facts) after EEKilled cleared the ecology flag,
		// so the wildlife row is released here unconditionally (no-op without an instance).
		HCWildlifeObservation.HCUnregister(this);
		super.EEDelete(parent);
	}
}

modded class ItemBase
{
	protected bool m_HCEcoRegistered;

	override void EEInit()
	{
		super.EEInit();
		if (!m_HCEcoRegistered) { m_HCEcoRegistered = HCEcologyRuntime.Register(this, false); }
	}

	override void EEDelete(EntityAI parent)
	{
		if (m_HCEcoRegistered)
		{
			m_HCEcoRegistered = false;
			HCEcologyRuntime.Unregister(this);
		}
		super.EEDelete(parent);
	}
}

modded class Well
{
	protected bool m_HCEcoRegistered;

	override void EEInit()
	{
		super.EEInit();
		if (!m_HCEcoRegistered) { m_HCEcoRegistered = HCEcologyRuntime.Register(this, false); }
	}

	override void EEDelete(EntityAI parent)
	{
		if (m_HCEcoRegistered)
		{
			m_HCEcoRegistered = false;
			HCEcologyRuntime.Unregister(this);
		}
		super.EEDelete(parent);
	}
}
