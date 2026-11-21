// Lifecycle hooks for the passive admin registry. Native scripts-1.30.164289:
// 4_World/Entities/Vehicles/CarScript.c:94, BoatScript.c:41, MotorbikeScript.c:53,
// HelicopterScript.c:4; Entities/EntityAI.c EEInit/EEDelete. The engine refuses
// 'modded class Transport' (compile gate), so each script base is hooked here.
modded class CarScript
{
    override void EEInit() { super.EEInit(); HCAdminVehicleRegistry.Add(this); }
    override void EEDelete(EntityAI parent) { HCAdminVehicleRegistry.Remove(this); super.EEDelete(parent); }
}
modded class BoatScript
{
    override void EEInit() { super.EEInit(); HCAdminVehicleRegistry.Add(this); }
    override void EEDelete(EntityAI parent) { HCAdminVehicleRegistry.Remove(this); super.EEDelete(parent); }
}
modded class MotorbikeScript
{
    override void EEInit() { super.EEInit(); HCAdminVehicleRegistry.Add(this); }
    override void EEDelete(EntityAI parent) { HCAdminVehicleRegistry.Remove(this); super.EEDelete(parent); }
}
modded class HelicopterScript
{
    override void EEInit() { super.EEInit(); HCAdminVehicleRegistry.Add(this); }
    override void EEDelete(EntityAI parent) { HCAdminVehicleRegistry.Remove(this); super.EEDelete(parent); }
}
