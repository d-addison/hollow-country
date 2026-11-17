// Native: 1_Core/proto/EnString.c:95 ToType; 1_Core/proto/EnConvert.c:544 Spawn.
// Optional late binding avoids a compile-time Expansion dependency. The type is
// fixed authored data, never an operator/client supplied class. Spawn constructs
// a script provider only; all actor work remains inside the optional addon API.
class HCEventAISelection
{
    static HCEventAIProvider Create()
    {
        string providerName = "HCExpansionAIEventProvider";
        typename providerType = providerName.ToType();
        if (providerType)
        {
            Class instance = providerType.Spawn();
            HCEventAIProvider provider = HCEventAIProvider.Cast(instance);
            if (provider) { return provider; }
        }
        Print("[HC Events] optional Expansion event provider absent; human AI missions excluded");
        return new HCEventAIProvider;
    }
}
