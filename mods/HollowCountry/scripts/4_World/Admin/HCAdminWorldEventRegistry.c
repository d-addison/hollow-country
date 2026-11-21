// Native: 4_World/Entities/Building/CrashBase.c:34/48 EEInit/EEDelete;
// 4_World/Classes/ContaminatedArea/ContaminatedArea_Dynamic.c:1 inheritance.
modded class CrashBase
{
    override void EEInit() { super.EEInit(); HCAdminVehicleRegistry.AddEvent(this); }
    override void EEDelete(EntityAI parent) { HCAdminVehicleRegistry.RemoveEvent(this); super.EEDelete(parent); }
}
modded class ContaminatedArea_Dynamic
{
    override void EEInit() { super.EEInit(); HCAdminVehicleRegistry.AddEvent(this); }
    override void EEDelete(EntityAI parent) { HCAdminVehicleRegistry.RemoveEvent(this); super.EEDelete(parent); }
}
