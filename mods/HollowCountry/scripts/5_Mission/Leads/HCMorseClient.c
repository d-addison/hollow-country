// HC-20: Morse presentation retired. No mission hook, subscription, pulse,
// sound allocation or decoded notification. Environmental reports use the
// existing native server notification path in HCRadioChatter. An inert shim
// keeps the old script type harmless; exact-source client restart is required.
class HCMorseClient
{
    void Start() {}
    void Update(float deltaTime) {}
    void Stop() {}
}
