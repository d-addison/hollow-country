// Extend the existing core lifecycle without editing its owner. A refused
// startup emits a save failure instead of leaving its asynchronous probe pending.
modded class HCServer
{
    override void Start()
    {
        super.Start();
        HCCoreDeadlineProbe deadline = new HCCoreDeadlineProbe;
        HCCoreSelfTestSaveJob job = new HCCoreSelfTestSaveJob;
        HCCoreSelfTest.Begin(deadline, job);
        if (!IsStarted()) { HCCoreSelfTest.Stop(); }
    }

    override void Tick()
    {
        super.Tick();
        HCCoreSelfTest.Pump();
    }

    override void Stop()
    {
        HCCoreSelfTest.Stop();
        super.Stop();
    }
}
