modded class AnimalBase
{
	override void EEInit()
	{
		super.EEInit();
		HCEcologyRuntime.Register(this, true);
	}

	override void EEKilled(Object killer)
	{
		HCEcologyRuntime.Unregister(this);
		super.EEKilled(killer);
	}

	override void EEDelete(EntityAI parent)
	{
		HCEcologyRuntime.Unregister(this);
		super.EEDelete(parent);
	}
}

modded class ItemBase
{
	override void EEInit()
	{
		super.EEInit();
		HCEcologyRuntime.Register(this, false);
	}

	override void EEDelete(EntityAI parent)
	{
		HCEcologyRuntime.Unregister(this);
		super.EEDelete(parent);
	}
}

modded class Well
{
	override void EEInit()
	{
		super.EEInit();
		HCEcologyRuntime.Register(this, false);
	}

	override void EEDelete(EntityAI parent)
	{
		HCEcologyRuntime.Unregister(this);
		super.EEDelete(parent);
	}
}
