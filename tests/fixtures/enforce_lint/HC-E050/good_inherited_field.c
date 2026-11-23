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
        if (!ActorHold) { return false; }
        return Complete;
    }
}
