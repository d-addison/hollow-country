class HCXTradeInventoryScan
{
    ref HCXAIAgentHold ActorHold;
    bool Complete;
}

class HCXAIAgentHold {}

class HCW38SituationSmokeStock : HCXTradeInventoryScan
{
    bool HCStep(int limit)
    {
        if (!Actor) { return false; }
        return Complete;
    }
}
