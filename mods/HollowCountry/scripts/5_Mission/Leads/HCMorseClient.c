// Issue #62 / EXP-S2. Client-local, default on; server EnableLeads owns delivery.
// Native evidence in scripts-1.30.164289:
// 3_Game/DayZGame.c:991,3144 Event_OnRPC signature/dispatch;
// 3_Game/Global/Game.c:612,944,1120 ConfigIsExisting/GetPlayer/IsServer;
// 1_Core/proto/Serializer.c:58 Read; EnScript.c:94 Cast; EnString.c:199,448 Length/Get;
// 1_Core/proto/EnConvert.c:30 ToString; EnDebug.c:96 Print;
// 3_Game/EffectManager.c:256,280 PlaySoundOnObject/DestroyEffect;
// 3_Game/Effects/EffectSound.c:217,856,878 SoundStop/volume/max volume;
// 3_Game/Client/Notifications/NotificationSystem.c:215 AddNotificationExtended;
// 5_Mission/mission/missionGameplay.c:102,266,287 OnInit/finish/update;
// 3_Game/Entities/Object.c:517 IsAlive; 4_World/Entities/ManBase/PlayerBase.c:1.
// Verified read-only installed config.bin evidence (byte offsets, no copied audio):
// addons/sounds_hpp.pbo: personalradio_staticnoise_SoundSet name @4774028;
// shader @45048 -> native personalradio_staticnoise sample, loop=1, volume .0501.
// nasdara/addons/sounds_nasdara.pbo: bunkerbroadcast_staticnoise_SoundSet
// @4928701; shader @240830 -> MorseCode_StaticNoise sample, loop=1, volume .25.
// The Nasdara set is optional at runtime: use it if loaded, otherwise handheld
// static. Dot/dash envelopes encode E/N 1 km grid and the short code word.
// Never use BunkerBroadcastManager.BroadcastTextAsMorse (all-player delivery).
class HCMorseClient
{
    protected bool m_Listening;
    protected PlayerBase m_Recipient;
    protected ref EffectSound m_Sound;
    protected string m_Units;
    protected string m_Decoded;
    protected int m_Index;
    protected float m_Elapsed;
    protected float m_Duration;
    protected float m_PulseVolume;

    void Start()
    {
        if (m_Listening || GetGame().IsServer()) { return; }
        m_Listening = true;
        DayZGame.Event_OnRPC.Insert(OnRPC);
        Print("[HollowCountry] V2 client morse clues on; holder-only RPC; native acceptance pending");
    }

    protected string Encode(string text)
    {
        string units;
        if (text.Length() > 24) { return ""; }
        for (int characterIndex = 0; characterIndex < text.Length(); characterIndex++)
        {
            string character = text.Get(characterIndex);
            if (character == " ") { units += "0000"; continue; }
            string symbols = HCMorseRpc.Symbols(character);
            if (symbols == "") { return ""; }
            for (int symbolIndex = 0; symbolIndex < symbols.Length(); symbolIndex++)
            {
                if (symbols.Get(symbolIndex) == ".") { units += "10"; }
                else { units += "1110"; }
            }
            units += "00";
        }
        return units;
    }

    void OnRPC(PlayerIdentity sender, Object target, int rpcType, ParamsReadContext ctx)
    {
        if (!m_Listening || GetGame().IsServer() || sender || rpcType != HCMorseRpc.CLUE || !ctx || m_Recipient) { return; }
        PlayerBase viewer = PlayerBase.Cast(GetGame().GetPlayer());
        if (!viewer || target != viewer || !viewer.IsAlive()) { return; }
        int east;
        int north;
        int kind;
        if (!ctx.Read(east) || !ctx.Read(north) || !ctx.Read(kind)) { return; }
        if (east < 0 || east > 15 || north < 0 || north > 15) { return; }
        string word = HCMorseRpc.Word(kind);
        if (word == "") { return; }
        m_Units = Encode("E" + east.ToString() + " N" + north.ToString() + " " + word);
        if (m_Units == "" || m_Units.Length() > 512) { return; }
        m_Recipient = viewer;
        m_Index = 0;
        m_Elapsed = 0;
        m_Duration = 0;
        m_Decoded = "1 km grid E " + east.ToString() + " / N " + north.ToString() + ". Code " + word + ". An optional event was reported there; it may expire.";
        Print("[HollowCountry] V2 client morse clue grid=" + HCMorseRpc.Grid(east, north));
        string soundSet = "bunkerbroadcast_staticnoise_SoundSet";
        m_PulseVolume = 0.18;
        if (!GetGame().ConfigIsExisting("CfgSoundSets " + soundSet))
        {
            soundSet = "personalradio_staticnoise_SoundSet";
            // Its shader is five times quieter than bunker static; keep the
            // envelope audible over the receiving radio's own native loop.
            m_PulseVolume = 1.0;
        }
        if (GetGame().ConfigIsExisting("CfgSoundSets " + soundSet))
        {
            // SEffectManager is local script playback: no networked sound RPC,
            // entity creation, radio broadcast or change to native radio state.
            m_Sound = SEffectManager.PlaySoundOnObject(soundSet, viewer, 0, 0, true);
            if (m_Sound) { Volume(0); }
        }
        if (!m_Sound) { Finish(); }
    }

    protected void Volume(float level)
    {
        if (!m_Sound) { return; }
        m_Sound.SetSoundVolume(level);
        m_Sound.SetSoundMaxVolume(level);
    }

    void Update(float deltaTime)
    {
        if (!m_Recipient) { if (m_Sound) { Clear(); } return; }
        if (GetGame().GetPlayer() != m_Recipient || !m_Recipient.IsAlive()) { Clear(); return; }
        if (!(deltaTime > 0)) { return; }
        m_Duration += deltaTime;
        if (m_Duration > 90) { Finish(); return; }
        m_Elapsed += deltaTime;
        if (m_Elapsed < 0.1) { return; }
        // One symbol unit per frame maximum; a lag spike never emits a burst.
        m_Elapsed = 0;
        if (m_Index >= m_Units.Length()) { Finish(); return; }
        float level = 0;
        if (m_Units.Get(m_Index) == "1") { level = m_PulseVolume; }
        Volume(level);
        m_Index++;
    }

    protected void Finish()
    {
        if (m_Recipient && m_Recipient == GetGame().GetPlayer() && m_Recipient.IsAlive())
        {
            NotificationSystem.AddNotificationExtended(15, "Faint Morse - decoded", m_Decoded);
        }
        Clear();
    }

    protected void Clear()
    {
        if (m_Sound)
        {
            m_Sound.SoundStop();
            SEffectManager.DestroyEffect(m_Sound);
            m_Sound = null;
        }
        m_Recipient = null;
        m_Units = "";
        m_Decoded = "";
    }

    void Stop()
    {
        if (m_Listening) { DayZGame.Event_OnRPC.Remove(OnRPC); }
        m_Listening = false;
        Clear();
    }
}

modded class MissionGameplay
{
    protected ref HCMorseClient m_HCMorseClient;

    override void OnInit()
    {
        super.OnInit();
        if (GetGame().IsServer()) { return; }
        m_HCMorseClient = new HCMorseClient;
        m_HCMorseClient.Start();
    }

    override void OnUpdate(float timeslice)
    {
        super.OnUpdate(timeslice);
        if (m_HCMorseClient) { m_HCMorseClient.Update(timeslice); }
    }

    override void OnMissionFinish()
    {
        if (m_HCMorseClient) { m_HCMorseClient.Stop(); }
        m_HCMorseClient = null;
        super.OnMissionFinish();
    }
}
