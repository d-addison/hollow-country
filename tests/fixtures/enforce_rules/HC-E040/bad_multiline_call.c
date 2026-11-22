// A counter call split across lines inside OnInit.
class HCProbeModule : HCModule
{
    override void OnInit()
    {
        HCModuleReadiness
            .HCUse(
                "Probe",
                "multi_line");
    }
}
