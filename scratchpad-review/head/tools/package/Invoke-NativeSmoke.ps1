#requires -Version 5.1
# Run in native Windows PowerShell. No WSL interop or Wine. This is a bounded
# real server initialization/Enforce compile smoke, NOT a client acceptance test.
[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [Parameter(Mandatory = $true)][string]$Pbo,
    [Parameter(Mandatory = $true)][string]$RuntimeRoot,
    [string]$ServerRoot = 'D:\SteamLibrary\steamapps\common\DayZServer',
    [string]$Python = 'python',
    [ValidateRange(15, 300)][int]$MaxSeconds = 180,
    [ValidateRange(1024, 65000)][int]$Port = 2402,
    [switch]$LeaveRunning
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# Match the setup script's read-only hashing and no-overwrite verified copy.
# These source snapshots record local provenance, not Steam authenticity.
function Assert-NoReparseAncestors {
    param([string]$Path)
    $cursor = [IO.Path]::GetFullPath($Path)
    while ($cursor) {
        $item = Get-Item -LiteralPath $cursor -ErrorAction SilentlyContinue
        if ($null -ne $item -and ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw "ReparsePoint/junction/symlink is not allowed: $cursor"
        }
        $cursor = [IO.Path]::GetDirectoryName($cursor)
    }
}
function Get-ReadOnlySha256 {
    param([string]$Path)
    $stream = $null
    $algorithm = [Security.Cryptography.SHA256]::Create()
    try {
        $stream = [IO.File]::OpenRead($Path)
        return ([BitConverter]::ToString($algorithm.ComputeHash($stream))).Replace('-', '').ToLowerInvariant()
    } finally {
        if ($null -ne $stream) { $stream.Dispose() }
        $algorithm.Dispose()
    }
}
function Assert-PinnedFile {
    param([string]$Path, $Expected)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "Required file missing: $Path" }
    Assert-NoReparseAncestors $Path
    if ((Get-Item -LiteralPath $Path).Length -ne [long]$Expected.bytes -or
        (Get-ReadOnlySha256 $Path) -ne $Expected.sha256) {
        throw "Dependency source/staged hash or size mismatch: $Path"
    }
}
function Copy-NewVerifiedFile {
    param([string]$Source, [string]$Destination, $Expected)
    Assert-PinnedFile $Source $Expected
    Assert-NoReparseAncestors $Destination
    [IO.File]::Copy($Source, $Destination, $false)
    Assert-PinnedFile $Destination $Expected
    Assert-PinnedFile $Source $Expected
}

$exe = Join-Path $ServerRoot 'DayZServer_x64.exe'
$missionSource = Join-Path $ServerRoot 'mpmissions\dayzOffline.chernarusplus'
foreach ($path in @($exe, $Pbo, (Join-Path $missionSource 'init.c'))) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Missing input: $path" }
}
$runtimeFull = [IO.Path]::GetFullPath($RuntimeRoot)
if ($runtimeFull -match '(?i)\\steamapps\\|\\\.git\\|^\\\\' -or
    $runtimeFull.StartsWith([IO.Path]::GetFullPath($ServerRoot), [StringComparison]::OrdinalIgnoreCase)) { throw 'Runtime must be a private local copy outside the Steam installation/repository.' }
# Also forbid accidentally storing a full vanilla mission inside this checkout.
$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
if ($runtimeFull.StartsWith($repo.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Runtime cannot be under the source checkout.' }
if (Test-Path -LiteralPath $runtimeFull) { throw 'Runtime already exists; choose a fresh directory.' }
if (-not $PSCmdlet.ShouldProcess($runtimeFull, 'Copy local mission and run a bounded unsigned server smoke requesting gameplay loopback')) { return }
# Even with BattlEye=0, initialization can require the server DLL. Never let
# the smoke write BE state into the installed tree or reuse another runtime.
$sourceBattleye = Join-Path $ServerRoot 'battleye\BEServer_x64.dll'
if (-not (Test-Path -LiteralPath $sourceBattleye -PathType Leaf)) { throw "Required BattlEye dependency missing: $sourceBattleye" }
Assert-NoReparseAncestors $sourceBattleye
Assert-NoReparseAncestors $runtimeFull
$battleyeExpected = [pscustomobject]@{
    bytes = (Get-Item -LiteralPath $sourceBattleye).Length
    sha256 = (Get-ReadOnlySha256 $sourceBattleye)
}
$pythonCommand = Get-Command -Name $Python -CommandType Application -ErrorAction Stop
if ($pythonCommand.Source -match '(?i)\\WindowsApps\\') { throw 'Windows Store python alias is unverified. Supply -Python with a real Python 3.10+ executable.' }
$Python = $pythonCommand.Source
& $Python -c 'import sys; print(sys.version); raise SystemExit(0 if sys.version_info >= (3, 10) else 1)'
if ($LASTEXITCODE -ne 0) { throw 'A working native Windows Python 3.10+ is required; source packaging can still run on Linux.' }
if (Get-Process -Name DayZServer_x64 -ErrorAction SilentlyContinue) { throw 'A server already exists; avoid a second process.' }
& $Python (Join-Path $PSScriptRoot 'pbo.py') verify $Pbo
if ($LASTEXITCODE -ne 0) { throw 'Invalid PBO.' }
$null = New-Item -ItemType Directory -Path $runtimeFull
$mission = Join-Path $runtimeFull 'mpmissions\dayzOffline.chernarusplus'
$null = New-Item -ItemType Directory -Path (Split-Path -Parent $mission)
Copy-Item -LiteralPath $missionSource -Destination $mission -Recurse
$mod = Join-Path $runtimeFull '@HollowCountry'
$addons = Join-Path $mod 'addons'
$null = New-Item -ItemType Directory -Path $addons
Copy-Item -LiteralPath $Pbo -Destination (Join-Path $addons 'hollowcountry.pbo')
$profiles = Join-Path $runtimeFull 'profiles'
$storage = Join-Path $runtimeFull 'storage'
$battleye = Join-Path $runtimeFull 'battleye'
$null = New-Item -ItemType Directory -Path $profiles, $storage, $battleye
Copy-NewVerifiedFile $sourceBattleye (Join-Path $battleye 'BEServer_x64.dll') $battleyeExpected
$config = Join-Path $runtimeFull 'serverDZ.cfg'
$configText = @"
hostname = "Hollow Country private native smoke";
password = "local-native-smoke";
maxPlayers = 6;
verifySignatures = 0;
forceSameBuild = 1;
instanceId = 1;
guaranteedUpdates = 1;
shardId = "hcdev1";
BattlEye = 0;
disableVoN = 1;
steamQueryPort = $($Port + 3);
class Missions { class DayZ { template = "dayzOffline.chernarusplus"; }; };
"@
[IO.File]::WriteAllText($config, $configText)
$argsList = @('-ip=127.0.0.1', "-port=$Port", "-config=$config", "-mission=$mission",
    "-storage=$storage", "-profiles=$profiles", "-mod=$mod", "-BEpath=$battleye", '-doLogs', '-adminLog', '-noPause')
# Start-Process joins arguments into one Windows command line; reject embedded
# quote characters and quote each complete argument to preserve spaces.
foreach ($arg in $argsList) { if ($arg.Contains('"')) { throw 'Quote in native argument.' } }
$quoted = @($argsList | ForEach-Object { '"' + $_ + '"' })
$server = $null
$report = [ordered]@{
    status = 'runtime-acceptance-pending'; server_pid = $null; initialized_marker_observed = $false
    compile_errors = @(); pbo_sha256 = (Get-FileHash -LiteralPath $Pbo -Algorithm SHA256).Hash.ToLowerInvariant()
    server_sha256 = (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash.ToLowerInvariant()
    config_sha256 = (Get-FileHash -LiteralPath $config -Algorithm SHA256).Hash.ToLowerInvariant()
    battleye_source = $sourceBattleye; battleye_path = $battleye; battleye_bytes = $battleyeExpected.bytes
    battleye_source_sha256 = $battleyeExpected.sha256
    battleye_staged_sha256 = (Get-ReadOnlySha256 (Join-Path $battleye 'BEServer_x64.dll'))
    requested_gameplay_loopback = $true; signature_verified = $false; client_count = 0
    forced_stop = $false; runtime_acceptance = 'pending'; logs = @(); socket_samples = @()
}
try {
    $server = Start-Process -FilePath $exe -WorkingDirectory $ServerRoot -ArgumentList $quoted -PassThru
    $report.server_pid = $server.Id
    $deadline = [DateTime]::UtcNow.AddSeconds($MaxSeconds)
    do {
        Start-Sleep -Seconds 2
        $server.Refresh()
        $sample = [ordered]@{ utc = [DateTime]::UtcNow.ToString('o'); udp = @(); tcp = @(); udp_error = $null; tcp_error = $null }
        try { $sample.udp = @(Get-NetUDPEndpoint -OwningProcess $server.Id -ErrorAction Stop | Select-Object LocalAddress, LocalPort, OwningProcess) }
        catch { $sample.udp_error = $_.Exception.Message }
        try { $sample.tcp = @(Get-NetTCPConnection -OwningProcess $server.Id -ErrorAction Stop | Select-Object LocalAddress, LocalPort, RemoteAddress, RemotePort, State, OwningProcess) }
        catch { $sample.tcp_error = $_.Exception.Message }
        $report.socket_samples += $sample
        $logs = @(Get-ChildItem -LiteralPath $profiles -File -Recurse | Where-Object { $_.Extension -in @('.log', '.RPT', '.rpt') })
        $allText = ($logs | ForEach-Object { Get-Content -LiteralPath $_.FullName -Raw -ErrorAction SilentlyContinue }) -join "`n"
        $report.initialized_marker_observed = $allText.Contains('[HollowCountry] Server initialized;')
        $report.compile_errors = @($allText -split "`r?`n" | Where-Object { $_ -match "Can't compile|Cannot compile|SCRIPT\s+\(E\)|Core native self-test FAILED|Error compiling" })
        if ($report.initialized_marker_observed -or $report.compile_errors.Count -or $server.HasExited) { break }
    } while ([DateTime]::UtcNow -lt $deadline)
} finally {
    if ($null -ne $server) {
        $server.Refresh()
        if (-not $server.HasExited -and -not $LeaveRunning) {
            # Prefer WM_CLOSE, bound waiting, then kill only the process we own.
            $null = $server.CloseMainWindow()
            if (-not $server.WaitForExit(5000)) { $server.Kill(); $null = $server.WaitForExit(5000); $report.forced_stop = $true }
        }
        $server.Refresh()
        $report.exited = $server.HasExited
        if ($server.HasExited) { $report.exit_code = $server.ExitCode }
    }
    $report.logs = @(Get-ChildItem -LiteralPath $profiles -File -Recurse | ForEach-Object {
        [ordered]@{ name = $_.FullName.Substring($runtimeFull.Length + 1); bytes = $_.Length
            sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant() }
    })
    [IO.File]::WriteAllText((Join-Path $runtimeFull 'native-smoke-report.json'), ($report | ConvertTo-Json -Depth 8))
}
if ($report.compile_errors.Count -or -not $report.initialized_marker_observed) {
    throw "Smoke did not reach Hollow Country initialization; inspect $runtimeFull\native-smoke-report.json and logs."
}
Write-Output "Observed core initialization marker: $runtimeFull\native-smoke-report.json. Client, signature, restart and gameplay acceptance pending."
