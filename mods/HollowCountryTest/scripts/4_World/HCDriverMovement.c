// Native scripts-1.30.164289: PlayerBase.c:3206-3211 CommandHandler/super;
// Systems/Bot/Bot_MovementRandomizer.c:38-39 ONE_FRAME after super; human.c:253/256.
// PluginDayzPlayerDebug.c:966 targets own player; DayZPlayerImplement.c:3855-3866
// receives on server and overrides that player's controller (DEVELOPER precedent only).
class HCDriverMovement
{
    static const int MIRROR = 0;
    static const int SERVER_ONLY = 1;
    static const int CLIENT_ONLY = 2;
    static int Variant = 0;
    static bool Pending;
    static float Speed;
    static float Angle;
    static int CommandId;
    static int AppliedFrames;
    static bool Calibrated;
    static float AngleSign = 1.0; // Derived diagnostic alias; steering uses AngleScale.
    static float AngleScale = 1.0;
    static bool HeadingFrame;
    static float HeadingOffset;
    static PlayerBase Owner;
    static float Lease;
    static int Serial;
    static bool Active;
    static bool StopPending;
    static int LastSend;
    static ref array<int> Sent = new array<int>;

    static string VariantName()
    {
        if (Variant == MIRROR) { return "mirror"; }
        if (Variant == SERVER_ONLY) { return "server"; }
        return "client";
    }

#ifndef SERVER
    // Native Global/Game.c:1535 GetTime is local milliseconds; leases are receiver-relative.
    // 1_Core/proto/EnScript.c:470 RemoveOrdered preserves the oldest-first rate window.
    static void Send(PlayerBase player, bool stop)
    {
        int now = GetGame().GetTime();
        while (Sent.Count() > 0 && now - Sent[0] >= 1000) { Sent.RemoveOrdered(0); }
        if (Sent.Count() >= 10 || (!stop && now - LastSend < 125)) { return; }
        ScriptRPC rpc = new ScriptRPC;
        rpc.Write(Serial);
        rpc.Write(Speed);
        rpc.Write(Angle);
        float lease = 0.5;
        if (stop) { lease = 0; }
        rpc.Write(lease);
        rpc.Write(Variant != CLIENT_ONLY);
        rpc.Send(player, HCDriverMoveWire.RPC_MOVE, true);
        Sent.Insert(now);
        LastSend = now;
        if (stop) { StopPending = false; }
    }
#endif

    static void Request(float speed, float angle)
    {
#ifndef SERVER
        if (!Active)
        {
            // Finish a throttled stop before opening another serial.
            if (StopPending && Owner) { Send(Owner, true); }
            if (StopPending) { return; }
            Owner = null;
            Serial++;
            Active = true;
        }
        Speed = speed;
        Angle = angle;
        Pending = true;
        Lease = 0.5;
#endif
    }

    static void Clear(PlayerBase player)
    {
        if (!player) { return; }
        HumanInputController input = player.GetInputController();
        if (!input) { return; }
        input.OverrideMovementSpeed(HumanInputControllerOverrideType.DISABLED, 0);
        input.OverrideMovementAngle(HumanInputControllerOverrideType.DISABLED, 0);
    }

    static void Stop()
    {
#ifndef SERVER
        Pending = false;
        Lease = 0;
        if (Active && Owner) { StopPending = true; }
        Active = false;
        // A request not yet consumed has never reached a controller or the wire.
        if (!Owner) { StopPending = false; }
        Clear(Owner);
        if (StopPending && Owner) { Send(Owner, true); }
        if (!StopPending) { Owner = null; }
#endif
    }

#ifndef SERVER
    static bool Guard(PlayerBase player, float dt)
    {
        Lease = Lease - dt;
        Mission mission = GetGame().GetMission();
        if (player != GetGame().GetPlayer() || !player.IsAlive() || player.IsUnconscious() || !player.GetCommand_Move() || !player.GetInputController() || !mission || mission.IsControlDisabled() || Lease <= 0)
        {
            Stop();
            return false;
        }
        return true;
    }

    static void Consume(PlayerBase player)
    {
        if (!Pending) { return; }
        Pending = false;
        if (Owner && Owner != player) { Stop(); return; }
        Owner = player;
        Send(player, false);
        if (Variant == SERVER_ONLY) { return; }
        HumanInputController input = player.GetInputController();
        input.OverrideMovementSpeed(HumanInputControllerOverrideType.ONE_FRAME, Speed);
        input.OverrideMovementAngle(HumanInputControllerOverrideType.ONE_FRAME, Angle);
        if (AppliedFrames < 1000000) { AppliedFrames++; }
    }
#endif
}

modded class PlayerBase
{
#ifdef SERVER
    protected int m_HCMoveSerial;
    protected int m_HCMoveClosed;
    protected int m_HCMoveDeadline;
    protected float m_HCMoveSpeed;
    protected float m_HCMoveAngle;
    protected bool m_HCMoveApply;
    protected int m_HCMoveFrames;
    protected int m_HCMoveLogs;
    protected string m_HCMoveRefused = "none";
    protected ref array<int> m_HCMoveReceived = new array<int>;

    // Native Man.c:21 GetIdentity; gameplay.c:377 GetPlayer; PlayerBase.c:2638 disconnect.
    protected string HCMoveGuard()
    {
        if (!GetIdentity() || IsPlayerDisconnected()) { return "disconnected"; }
        if (!IsAlive()) { return "dead"; }
        if (IsUnconscious()) { return "unconscious"; }
        if (!GetCommand_Move()) { return "command-change"; }
        if (!GetInputController()) { return "no-controller"; }
        return "none";
    }

    protected void HCMoveLog(int frames, string reason, int serial)
    {
        if (m_HCMoveLogs >= 128) { return; }
        Print("[HC Driver] server-move applied_frames=" + frames.ToString() + " refused=" + reason + " serial=" + serial.ToString());
        m_HCMoveLogs++;
    }

    protected void HCMoveClose(string reason)
    {
        if (m_HCMoveSerial <= m_HCMoveClosed) { return; }
        if (m_HCMoveApply) { HCDriverMovement.Clear(this); }
        if (m_HCMoveRefused == "none" && reason != "none") { m_HCMoveRefused = reason; }
        // One summary per serial, hard cap per player lifetime; no identity data.
        HCMoveLog(m_HCMoveFrames, m_HCMoveRefused, m_HCMoveSerial);
        m_HCMoveClosed = m_HCMoveSerial;
        m_HCMoveDeadline = 0;
        m_HCMoveApply = false;
    }

    override void OnRPC(PlayerIdentity sender, int rpc_type, ParamsReadContext ctx)
    {
        if (rpc_type != HCDriverMoveWire.RPC_MOVE) { super.OnRPC(sender, rpc_type, ctx); return; }
        // Never clear or mutate someone else's controller, even for a forged stop.
        // Match by identity id: sender and GetIdentity() are not the same script
        // reference on the server (soak 190t: every RPC refused; HCAdminModule precedent).
        PlayerIdentity hcMoveOwn = GetIdentity();
        string hcMoveOwner = "none";
        if (!sender) { hcMoveOwner = "no-sender"; }
        else if (!hcMoveOwn) { hcMoveOwner = "no-identity"; }
        else if (hcMoveOwn.GetId() != sender.GetId()) { hcMoveOwner = "not-owner"; }
        if (hcMoveOwner != "none")
        {
            HCMoveLog(0, hcMoveOwner, 0);
            return;
        }
        int serial;
        float speed;
        float angle;
        float lease;
        bool apply;
        bool read = ctx.Read(serial) && ctx.Read(speed) && ctx.Read(angle) && ctx.Read(lease) && ctx.Read(apply);
        int now = GetGame().GetTime();
        while (m_HCMoveReceived.Count() > 0 && now - m_HCMoveReceived[0] >= 1000) { m_HCMoveReceived.RemoveOrdered(0); }
        bool limited = m_HCMoveReceived.Count() >= 10;
        if (!limited) { m_HCMoveReceived.Insert(now); }
        if (!read || serial <= 0)
        {
            if (m_HCMoveSerial > m_HCMoveClosed) { HCMoveClose("malformed"); }
            else { HCMoveLog(0, "malformed", 0); }
            return;
        }
        // Already summarized serials cannot revive a stopped/expired probe; no duplicate line.
        if (serial <= m_HCMoveClosed || serial < m_HCMoveSerial) { return; }
        if (serial > m_HCMoveSerial)
        {
            string previous = "superseded";
            if (m_HCMoveDeadline > 0 && now >= m_HCMoveDeadline) { previous = "lease-expired"; }
            HCMoveClose(previous);
            m_HCMoveSerial = serial;
            m_HCMoveFrames = 0;
            m_HCMoveRefused = "none";
        }
        string reason = "none";
        if (limited) { reason = "rate-limit"; }
        // Positive range checks reject NaNs as well as infinities/out-of-range values.
        else if (!(speed >= 0 && speed <= 3)) { reason = "speed-range"; }
        else if (!(angle >= -180 && angle <= 180)) { reason = "angle-range"; }
        else if (!(lease >= 0 && lease <= 0.5)) { reason = "lease-range"; }
        else if (m_HCMoveDeadline > 0 && now >= m_HCMoveDeadline) { reason = "lease-expired"; }
        else { reason = HCMoveGuard(); }
        if (reason != "none") { HCMoveClose(reason); return; }
        if (lease == 0) { HCMoveClose("none"); return; }
        m_HCMoveSpeed = speed;
        m_HCMoveAngle = angle;
        if (m_HCMoveApply && !apply) { HCDriverMovement.Clear(this); }
        m_HCMoveApply = apply;
        m_HCMoveDeadline = now + Math.Floor(lease * 1000);
    }

    // Native PlayerBase.c:7647 OnDisconnect, :1214 EEKilled; release before super.
    override void OnDisconnect()
    {
        HCMoveClose("disconnected");
        super.OnDisconnect();
    }

    override void EEKilled(Object killer)
    {
        HCMoveClose("dead");
        super.EEKilled(killer);
    }
#endif

    override void CommandHandler(float pDt, int pCurrentCommandID, bool pCurrentCommandFinished)
    {
#ifndef SERVER
        bool localDriver = this == GetGame().GetPlayer() || this == HCDriverMovement.Owner;
        if (localDriver) { HCDriverMovement.CommandId = pCurrentCommandID; }
#endif
        super.CommandHandler(pDt, pCurrentCommandID, pCurrentCommandFinished);
#ifdef SERVER
        if (m_HCMoveSerial > m_HCMoveClosed)
        {
            string reason = HCMoveGuard();
            if (reason == "none" && GetGame().GetTime() >= m_HCMoveDeadline) { reason = "lease-expired"; }
            if (reason != "none") { HCMoveClose(reason); return; }
            if (m_HCMoveApply)
            {
                HumanInputController input = GetInputController();
                input.OverrideMovementSpeed(HumanInputControllerOverrideType.ONE_FRAME, m_HCMoveSpeed);
                input.OverrideMovementAngle(HumanInputControllerOverrideType.ONE_FRAME, m_HCMoveAngle);
                if (m_HCMoveFrames < 1000000) { m_HCMoveFrames++; }
            }
        }
#else
        if (localDriver && HCDriverMovement.Guard(this, pDt)) { HCDriverMovement.Consume(this); }
#endif
    }
}
