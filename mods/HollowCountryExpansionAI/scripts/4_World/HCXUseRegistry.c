// Readiness declares inventory; only successful gameplay actions increment it.
modded class HCModuleReadiness
{
    override static void HCRegisterModuleUses(string module)
    {
        super.HCRegisterModuleUses(module);
        if (module == "AIIncidents")
        {
            HCRegisterUse("AIIncidents", "response_started");
            return;
        }
        if (module == "AIRoles")
        {
            HCRegisterUse("AIRoles", "activity_started");
            return;
        }
        if (module == "AISelfDefence")
        {
            HCRegisterUse("AISelfDefence", "hit_reaction");
            return;
        }
        if (module == "AITactics")
        {
            HCRegisterUse("AITactics", "tactic_chosen");
            return;
        }
        if (module == "ZoneGuards")
        {
            HCRegisterUse("ZoneGuards", "guards_posted");
            return;
        }
        if (module == "MaterializerBridge")
        {
            HCRegisterUse("MaterializerBridge", "party_materialized");
            return;
        }
        if (module == "hcxai-live-map")
        {
            HCRegisterUse("hcxai-live-map", "report_published");
            return;
        }
        if (module == "optional-expansion-human-ai")
        {
            HCRegisterUse("optional-expansion-human-ai", "actor_spawned");
            HCRegisterUse("optional-expansion-human-ai", "convoy_astar");
            HCRegisterUse("optional-expansion-human-ai", "stuck_recovery");
            return;
        }
        if (module == "v2-expansion-living-world")
        {
            HCRegisterUse("v2-expansion-living-world", "actor_admitted");
            return;
        }
    }
}
