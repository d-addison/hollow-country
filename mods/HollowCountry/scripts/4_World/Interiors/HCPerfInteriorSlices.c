// Native scripts-1.30.164289: 1_Core/proto/EnDebug.c:96 Print.
// w45 #138. Final modded link: the pack reader declares m_PackBudget in
// HCInteriorTemplates.c. Earlier links never call methods introduced here.
// Cap BOTH metadata and leaf/validation steps using the existing reader cursor.
modded class HCInteriorsModule
{
    override void OnStart(HCSettings settings)
    {
        super.OnStart(settings);
        m_PackBudget = new HCPerfSlices("Interiors");
        Print("[HC PerfControl] Interiors pack slicing admitted; runtime=PENDING");
    }
}
