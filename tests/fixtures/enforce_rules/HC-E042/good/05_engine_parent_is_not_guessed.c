// The parent is an engine class with no script body: an override cannot be judged offline.
class HCNoiseSource : ParticleSource
{
    override void OnCreated(string reason)
    {
    }
}
