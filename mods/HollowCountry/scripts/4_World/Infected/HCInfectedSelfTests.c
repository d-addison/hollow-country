// Optional diagnostic policy checks. These do not exercise native gameplay.
class HCInfectedSelfTests
{
    static bool Run()
    {
        bool ok = HCInfectedPolicy.AcceptClue(10, 9, 20, 1, 1, 0);
        ok = ok && !HCInfectedPolicy.AcceptClue(20, 9, 20, 1, 1, 0);
        ok = ok && HCInfectedPolicy.NextHordeState(0, 6, false, false, 0, 0) == 1;
        ok = ok && HCInfectedPolicy.NextHordeState(3, 6, false, false, 10, 20) == 4;
        ok = ok && HCInfectedPolicy.NextHordeState(4, 6, false, false, 61, 81) == 1;
        ok = ok && HCInfectedPolicy.NextHordeState(3, 6, true, true, 0, 3600) == 5;
        ok = ok && HCInfectedPolicy.AfterRestart(3) == 6;
        ok = ok && !HCInfectedPolicy.CanReserve(1, 2, 24, 24, 1);
        ok = ok && !HCInfectedPolicy.CanMaterialize() && !HCInfectedPolicy.CanAbstract();
        ok = ok && HCInfectedPolicy.SuppressStrike(true, true, false);
        ok = ok && HCInfectedPolicy.SearchAnchorBudget(false, false) == 3;
        ok = ok && HCInfectedPolicy.SearchAnchorBudget(true, false) == 1;
        ok = ok && !HCInfectedPolicy.DirectlyObserved(true, 100, 1, false, true);
        ok = ok && !HCInfectedPolicy.RouteAlive(20, 20, 0, true, false);
        ok = ok && !HCInfectedPolicy.AdoptionWorkReady(8) && HCInfectedPolicy.AdoptionWorkReady(9);
        ok = ok && !HCInfectedPolicy.CountsOwnedMember(true, true, false);
        ok = ok && HCInfectedPolicy.MayRetryRelease(2, 110, 105) && !HCInfectedPolicy.MayRetryRelease(3, 110, 105);
        ok = ok && HCInfectedPolicy.MayRelay(12, 10, 25, 1, 0.5, true, true);
        ok = ok && !HCInfectedPolicy.MayRelay(25, 10, 25, 1, 0.5, true, true);
        ok = ok && !HCInfectedPolicy.MayRelay(12, 10, 25, 2, 0.25, true, true);
        ok = ok && !HCInfectedPolicy.ValidMemberIdentity(0, 0, 0, 0, true);
        ok = ok && HCInfectedPolicy.PreferRoom(true, false, 20, 1, 9, 1);
        HCInfectedConfig config = new HCInfectedConfig;
        // Shipped defaults: every capability preference on; diagnostics opt-in.
        ok = ok && config.IsValid() && config.EnableCEAdoption && config.EnableNativePackRoutes && config.EnableInvestigation && config.EnableContactGuard;
        ok = ok && config.EnableSupplementaryChains && config.EnableMemberRecovery && config.EnableVariantPolicies && config.EnableHordeStimulusRoutes;
        ok = ok && !config.RunPolicySelfTests;
        // Requested is not admitted: default preferences are on, qualification is closed.
        // Resolve with every qualification false, not Evaluate: Evaluate also honours the
        // local-acceptance profile markers, which must not fail a DayZDiag self-test.
        HCInfectedAdmission admission = HCInfectedAdmission.Resolve(config, false, false, false, false, false, false);
        ok = ok && !admission.CEAdoption && !admission.NativePackRoutes && !admission.Investigation;
        ok = ok && !admission.SupplementaryChains && !admission.MemberRecovery && !admission.HordeStimulusRoutes;
        ok = ok && admission.CEAdoptionReason == "ce_adoption_unqualified" && admission.HordeStimulusRoutesReason == "horde_stimulus_routes_unqualified";
        // Synthetic seam only: hypothetical qualification admits; explicit false still disables.
        HCInfectedAdmission hypothetical = HCInfectedAdmission.Resolve(config, true, true, true, true, true, true);
        ok = ok && hypothetical.CEAdoption && hypothetical.NativePackRoutes && hypothetical.Investigation;
        ok = ok && hypothetical.SupplementaryChains && hypothetical.MemberRecovery && hypothetical.HordeStimulusRoutes;
        config.EnableInvestigation = false;
        HCInfectedAdmission disabled = HCInfectedAdmission.Resolve(config, true, true, true, true, true, true);
        ok = ok && !disabled.Investigation && disabled.InvestigationReason == "disabled_by_preference";
        config.EnableInvestigation = true;
        Print("[HC Infected] admission selftest " + admission.Describe());
        Print("[HC Infected] scalar policy selftest result=" + ok);
        return ok;
    }
}
