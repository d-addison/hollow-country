#requires -Version 5.1
# Launch ONE staged disposable Central Economy probe runtime (see tools/setup/ce_probe.py),
# wait for the probe sentinel, stop only the server process this script started and record
# observations. No client launch, remoting, service or scheduled task. Nothing here accepts
# anything: the observation file only lists what was seen.
[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [Parameter(Mandatory = $true)]
    [string]$Runtime,
    [ValidateRange(0, 120)]
    [int]$TimeoutMinutes = 0
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
function Read-Sha256 {
    param([string]$Path)
    $algorithm = [System.Security.Cryptography.SHA256]::Create()
    $stream = $null
    try {
        $stream = [System.IO.File]::OpenRead($Path)
        return ([BitConverter]::ToString($algorithm.ComputeHash($stream))).Replace('-', '').ToLowerInvariant()
    } finally {
        if ($null -ne $stream) { $stream.Dispose() }
        $algorithm.Dispose()
    }
}
function Get-FileRecords {
    param([string]$Directory, [string]$Pattern, [string]$Scope)
    $records = @()
    if (-not [System.IO.Directory]::Exists($Directory)) { return $records }
    foreach ($path in @([System.IO.Directory]::GetFiles($Directory, $Pattern, $Scope) | Select-Object -First 200)) {
        $info = New-Object System.IO.FileInfo($path)
        $records += [ordered]@{ path = $path; bytes = $info.Length; modified_utc = $info.LastWriteTimeUtc.ToString('o') }
    }
    return $records
}

$parent = 'D:\HollowCountryLocal'
$install = 'D:\SteamLibrary\steamapps\common\DayZServer'
$exe = 'D:\SteamLibrary\steamapps\common\DayZServer\DayZServer_x64.exe'
$exeSha256 = '987fbc47bab1dab37f74d7f700aa2e5b6af936a7181a62f5ba9f0090aebba805'
$root = $Runtime.TrimEnd('\')
$name = Split-Path -Leaf $root
if ($root -match '\.\.' -or (Split-Path -Parent $root) -ne $parent -or $name -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$' -or
    $name -eq 'vanilla-p0-001') { throw 'Runtime must be one named child of D:\HollowCountryLocal and not the verified vanilla-p0-001 runtime.' }
$planPath = Join-Path $root 'ce-probe-plan.json'
$plan = Get-Content -LiteralPath $planPath -Raw | ConvertFrom-Json
$mission = "$root\mpmissions\dayzOffline.chernarusplus"
$expectedArguments = @('-ip=127.0.0.1', '-port=2302',
    "-config=$root\serverDZ.cfg", "-mission=$mission",
    "-storage=$root\storage", "-profiles=$root\profiles", "-BEpath=$root\battleye", '-doLogs', '-adminLog')
if ($plan.status -ne 'staged-only-not-launched' -or $plan.kind -ne 'ce-probe' -or $plan.runtime_root -ne $root -or
    $plan.server_exe -ne $exe -or $plan.working_directory -ne $install -or $plan.mission -ne $mission -or
    $plan.port -ne 2302 -or $plan.server_exe_sha256 -ne $exeSha256 -or
    (@($plan.arguments) -join ' ') -ne ($expectedArguments -join ' ')) { throw 'Unexpected CE probe plan.' }
if ((Read-Sha256 $exe) -ne $exeSha256) { throw 'Server executable changed since the plan was staged.' }

$staged = @{}
foreach ($file in $plan.staged_files) {
    if ($file.path -match '(^|/)\.\.(/|$)|:|\\|^/') { throw 'Unsafe staged file path.' }
    $local = Join-Path $root ($file.path -replace '/', '\')
    if (-not [System.IO.File]::Exists($local) -or (Read-Sha256 $local) -ne $file.sha256) { throw "Staged file changed: $($file.path)" }
    $staged[$local.ToLowerInvariant()] = $true
}
$staged[$planPath.ToLowerInvariant()] = $true
foreach ($path in [System.IO.Directory]::GetFiles($root, '*', [System.IO.SearchOption]::AllDirectories)) {
    if (-not $staged.ContainsKey($path.ToLowerInvariant())) { throw "Unexpected CE probe runtime file (stage a fresh runtime): $path" }
}
foreach ($directory in @("$root\storage", "$root\profiles")) {
    if (-not [System.IO.Directory]::Exists($directory) -or [System.IO.Directory]::GetFileSystemEntries($directory).Count -ne 0) {
        throw 'storage and profiles must be empty for a fresh probe run.'
    }
}
if (Get-Process -Name DayZServer_x64 -ErrorAction SilentlyContinue) { throw 'A DayZ server is already running; do not start a duplicate.' }

$minutes = $TimeoutMinutes
if ($minutes -eq 0) { $minutes = [int]$plan.probe.wait_minutes }
if ($minutes -lt 5 -or $minutes -gt 120) { throw 'Timeout minutes must be 5..120.' }
$sentinel = Join-Path $root 'profiles\HCCEProbe\complete.txt'
$census = Join-Path $root 'profiles\HCCEProbe\census.json'
if (-not $PSCmdlet.ShouldProcess($root, "Launch the staged CE probe server and wait up to $minutes minutes for complete.txt")) { return }

$quoted = @($expectedArguments | ForEach-Object { [char]34 + $_ + [char]34 })
$startedUtc = [DateTime]::UtcNow
$server = Start-Process -FilePath $exe -WorkingDirectory $install -ArgumentList $quoted -PassThru
Write-Output "ServerPID=$($server.Id). Waiting up to $minutes minutes for $sentinel; leave this window open."
$outcome = 'timeout-no-sentinel'
$deadline = $startedUtc.AddMinutes($minutes)
$exitCode = $null
try {
    while ([DateTime]::UtcNow -lt $deadline) {
        Start-Sleep -Seconds 5
        $server.Refresh()
        if ([System.IO.File]::Exists($sentinel)) { $outcome = 'sentinel-seen'; break }
        if ($server.HasExited) { $outcome = 'process-exited-before-sentinel'; break }
    }
    if ($outcome -eq 'sentinel-seen') { Start-Sleep -Seconds 5 }
} finally {
    $server.Refresh()
    if (-not $server.HasExited) {
        Stop-Process -Id $server.Id -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 3
        $server.Refresh()
    }
    if ($server.HasExited) { $exitCode = $server.ExitCode }
}
$endedUtc = [DateTime]::UtcNow

$profiles = "$root\profiles"
$censusRecord = [ordered]@{ path = $census; exists = [System.IO.File]::Exists($census) }
if ($censusRecord.exists) {
    $censusRecord.bytes = (New-Object System.IO.FileInfo($census)).Length
    $censusRecord.sha256 = Read-Sha256 $census
}
$sentinelRecord = [ordered]@{ path = $sentinel; exists = [System.IO.File]::Exists($sentinel) }
if ($sentinelRecord.exists) { $sentinelRecord.text = ([System.IO.File]::ReadAllText($sentinel)).Trim() }
$report = [ordered]@{
    kind = 'ce-probe-observation'
    status = 'observed-not-accepted'
    outcome = $outcome
    server_pid = $server.Id
    server_exited = $server.HasExited
    exit_code = $exitCode
    started_utc = $startedUtc.ToString('o')
    ended_utc = $endedUtc.ToString('o')
    timeout_minutes = $minutes
    runtime_root = $root
    plan_variant = $plan.variant
    census = $censusRecord
    sentinel = $sentinelRecord
    rpt_logs = @(Get-FileRecords $profiles '*.RPT' ([System.IO.SearchOption]::TopDirectoryOnly))
    script_logs = @(Get-FileRecords $profiles 'script_*.log' ([System.IO.SearchOption]::TopDirectoryOnly))
    error_logs = @(Get-FileRecords $profiles 'error_*.log' ([System.IO.SearchOption]::TopDirectoryOnly))
    admin_logs = @(Get-FileRecords $profiles '*.ADM' ([System.IO.SearchOption]::TopDirectoryOnly))
    probe_outputs = @(Get-FileRecords "$profiles\HCCEProbe" '*' ([System.IO.SearchOption]::TopDirectoryOnly))
    storage_files = @(Get-FileRecords "$root\storage" '*' ([System.IO.SearchOption]::AllDirectories))
    export_candidates = @(Get-FileRecords $root 'mapgroupproto*.xml' ([System.IO.SearchOption]::AllDirectories))
    note = 'Observation only. Export file location is unobserved before this run; storage_files and export_candidates list what appeared.'
}
$reportPath = Join-Path $root ('ce-probe-observation-' + [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss') + '.json')
$bytes = [System.Text.Encoding]::UTF8.GetBytes(($report | ConvertTo-Json -Depth 8))
$output = [System.IO.File]::Open($reportPath, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write)
try { $output.Write($bytes, 0, $bytes.Length) } finally { $output.Dispose() }
Write-Output "Outcome: $outcome. Saved observations: $reportPath. Native acceptance is still pending."
