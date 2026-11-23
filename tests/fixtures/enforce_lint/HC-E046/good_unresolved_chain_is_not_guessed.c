class HCXAIProbe
{
    bool Held(EngineThing thing)
    {
        return thing.Walker.m_PartnerGroup != null;
    }
}
