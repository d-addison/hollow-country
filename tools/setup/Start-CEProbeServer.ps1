#requires -Version 5.1
# Launch ONE staged disposable Central Economy probe runtime (see tools/setup/ce_probe.py),
# wait for the probe sentinel, stop only the server process this script started and record
# observations. No client launch, remoting, service or scheduled task. Nothing here accepts
# anything: the observation file only lists what was seen.
[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [Parameter(Mandatory = $true)]
    [string]$Runtime,
    [ValidateSet('ce-fill-probe', 'ce-probe', 'ce-site-probe', 'taped-light-probe', 'weather-probe', 'interior-sampler', 'infected-competence-probe')]
    [string]$Kind = 'ce-probe',
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
function Test-ReparsePoint {
    param([string]$Path)
    $attributes = [System.IO.File]::GetAttributes($Path)
    return (($attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0)
}
# Junctions, symlinks and mount points redirect paths the lexical checks cannot see. Reject
# them on the runtime root, on every ancestor and (unless -AncestorsOnly) on every descendant.
function Assert-NoReparsePoints {
    param([string]$Path, [switch]$AncestorsOnly)
    $current = $Path
    while (-not [string]::IsNullOrEmpty($current)) {
        if (Test-ReparsePoint $current) { throw "Reparse point refused (junction/symlink): $current" }
        $current = Split-Path -Parent $current
    }
    if ($AncestorsOnly) { return }
    $pending = New-Object System.Collections.Generic.Stack[string]
    $pending.Push($Path)
    $seen = 0
    while ($pending.Count -gt 0) {
        $directory = $pending.Pop()
        foreach ($entry in [System.IO.Directory]::GetFileSystemEntries($directory)) {
            $seen++
            if ($seen -gt 5000) { throw 'Runtime tree is larger than the CE probe budget.' }
            if (Test-ReparsePoint $entry) { throw "Reparse point refused (junction/symlink): $entry" }
            if ([System.IO.Directory]::Exists($entry)) { $pending.Push($entry) }
        }
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
# A server that refuses the mission script stays alive on its error dialog until stopped
# (taped-light-probe-002). Read only a bounded tail of the newest script log, sharing the file
# with the server that is still writing it. A crash_*.log alone is not a compile failure: the
# completed taped-light-probe-003 run also wrote one, for non-fatal script VM exceptions.
function Test-CompileRefused {
    param([string]$Directory)
    if (-not [System.IO.Directory]::Exists($Directory)) { return $false }
    $newest = @([System.IO.Directory]::GetFiles($Directory, 'script_*.log') | Sort-Object { [System.IO.File]::GetLastWriteTimeUtc($_) } | Select-Object -Last 1)
    if ($newest.Count -eq 0) { return $false }
    $tail = 65536
    $stream = $null
    try {
        $stream = [System.IO.File]::Open($newest[0], [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
        $start = [Math]::Max([long]0, $stream.Length - $tail)
        [void]$stream.Seek($start, [System.IO.SeekOrigin]::Begin)
        $buffer = New-Object byte[] ([int]($stream.Length - $start))
        $read = $stream.Read($buffer, 0, $buffer.Length)
        $text = [System.Text.Encoding]::UTF8.GetString($buffer, 0, $read)
        return ($text.Contains("Can't compile"))
    } catch [System.IO.IOException] {
        return $false
    } finally {
        if ($null -ne $stream) { $stream.Dispose() }
    }
}

$parent = 'D:\HollowCountryLocal'
$install = 'D:\SteamLibrary\steamapps\common\DayZServer'
$exe = 'D:\SteamLibrary\steamapps\common\DayZServer\DayZServer_x64.exe'
$exeSha256 = '987fbc47bab1dab37f74d7f700aa2e5b6af936a7181a62f5ba9f0090aebba805'
$root = $Runtime.TrimEnd('\')
$name = Split-Path -Leaf $root
# The last character may not be a dot or space (Windows strips them, so 'vanilla-p0-001.' would
# name the verified runtime), and reserved device names (CON, NUL, COM1, ... even with an
# extension) are refused. Mirrors NAME_RULE in tools/setup/probe_runtime.py.
if ($root -match '\.\.' -or (Split-Path -Parent $root) -ne $parent -or
    $name -notmatch '^[A-Za-z0-9](?:[A-Za-z0-9._-]{0,62}[A-Za-z0-9_-])?$' -or
    $name -match '^(?i:(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9]))(\..*)?$' -or
    $name.TrimEnd('.', ' ').ToLowerInvariant() -eq 'vanilla-p0-001') { throw 'Runtime must be one named child of D:\HollowCountryLocal, not a reserved device name and not the verified vanilla-p0-001 runtime.' }
if (-not [System.IO.Directory]::Exists($root)) { throw "Runtime directory not found: $root" }
Assert-NoReparsePoints -Path $root
Assert-NoReparsePoints -Path $install -AncestorsOnly
# Each probe kind maps to a fixed plan file, profile directory and output file; nothing here
# is read from the plan, so a tampered plan cannot redirect the sentinel or output paths.
$probes = @{
    'ce-fill-probe' = @{ Plan = 'ce-fill-probe-plan.json'; Directory = 'HCCEFillProbe'; Output = 'complete.txt' }
    'ce-site-probe' = @{ Plan = 'ce-site-probe-plan.json'; Directory = 'HCCESiteProbe'; Output = 'complete.txt' }
    'ce-probe' = @{ Plan = 'ce-probe-plan.json'; Directory = 'HCCEProbe'; Output = 'census.json' }
    'taped-light-probe' = @{ Plan = 'taped-light-probe-plan.json'; Directory = 'HCTapedLightProbe'; Output = 'observations.json' }
    'weather-probe' = @{ Plan = 'weather-probe-plan.json'; Directory = 'HCWeatherProbe'; Output = 'observations.json' }
    'interior-sampler' = @{ Plan = 'interior-sampler-plan.json'; Directory = 'HCInteriorSampler'; Output = 'census.json' }
    'infected-competence-probe' = @{ Plan = 'infected-competence-probe-plan.json'; Directory = 'HCInfectedCompetence'; Output = 'observations.json' }
}
$probe = $probes[$Kind]
$planPath = Join-Path $root $probe.Plan
$plan = Get-Content -LiteralPath $planPath -Raw | ConvertFrom-Json
$mission = "$root\mpmissions\dayzOffline.chernarusplus"
$expectedArguments = @('-ip=127.0.0.1', '-port=2302',
    "-config=$root\serverDZ.cfg", "-mission=$mission",
    "-storage=$root\storage", "-profiles=$root\profiles", "-BEpath=$root\battleye", '-doLogs', '-adminLog')
# Only this experiment admits the friend's full, in-place mod set. Every PBO
# and the exact inventory are pinned; the plan cannot introduce arbitrary switches.
if ($Kind -eq 'ce-fill-probe') {
    $seenMods = @{}
    $switches = @($plan.mods.PSObject.Properties)
    if ($switches.Count -lt 1 -or $switches.Count -gt 2) { throw 'Missing fill-probe mod list.' }
    foreach ($property in $switches) {
        if ($property.Name -cne '-mod' -and $property.Name -cne '-serverMod') { throw 'Unexpected mod switch.' }
        $paths = @()
        foreach ($mod in @($property.Value)) {
            if ($mod.path -cnotmatch '^E:\\HollowCountryLocal\\friend-local-1\\@[A-Za-z0-9_-]+$' -or
                $seenMods.ContainsKey($mod.path.ToLowerInvariant())) { throw 'Unexpected friend mod directory.' }
            $seenMods[$mod.path.ToLowerInvariant()] = $true
            Assert-NoReparsePoints -Path $mod.path
            $pins = @{}
            foreach ($pbo in @($mod.pbos)) {
                if ($pbo.path -notmatch '^[A-Za-z0-9_./ -]+\.pbo$' -or $pbo.path -match '(^|/)\.\.(/|$)|^/' -or
                    $pbo.sha256 -cnotmatch '^[a-f0-9]{64}$' -or $pins.ContainsKey($pbo.path.ToLowerInvariant())) {
                    throw 'Invalid PBO pin.'
                }
                $local = Join-Path $mod.path ($pbo.path -replace '/', '\')
                if ((Read-Sha256 $local) -cne $pbo.sha256) { throw 'Friend mod PBO drift; restage the experiment.' }
                $pins[$pbo.path.ToLowerInvariant()] = $true
            }
            $actual = @([System.IO.Directory]::GetFiles($mod.path, '*', [System.IO.SearchOption]::AllDirectories) |
                Where-Object { [System.IO.Path]::GetExtension($_) -ieq '.pbo' })
            if ($pins.Count -lt 1 -or $pins.Count -gt 4096 -or $actual.Count -ne $pins.Count) { throw 'Friend mod PBO inventory drift.' }
            foreach ($path in $actual) {
                $relative = $path.Substring($mod.path.Length + 1).Replace('\', '/').ToLowerInvariant()
                if (-not $pins.ContainsKey($relative)) { throw 'Unlisted friend mod PBO.' }
            }
            $paths += $mod.path
        }
        if ($paths.Count -eq 0) { throw 'Empty mod switch.' }
        $expectedArguments += $property.Name + '=' + ($paths -join ';')
    }
}
if ($plan.status -ne 'staged-only-not-launched' -or $plan.kind -ne $Kind -or $plan.runtime_root -ne $root -or
    $plan.server_exe -ne $exe -or $plan.working_directory -ne $install -or $plan.mission -ne $mission -or
    $plan.port -ne 2302 -or $plan.server_exe_sha256 -ne $exeSha256 -or
    (@($plan.arguments) -join ' ') -ne ($expectedArguments -join ' ')) { throw "Unexpected CE probe plan for kind $Kind." }
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
    if (-not $staged.ContainsKey($path.ToLowerInvariant())) { throw "Unexpected probe runtime file (stage a fresh runtime): $path" }
}
foreach ($directory in @("$root\storage", "$root\profiles")) {
    if (-not [System.IO.Directory]::Exists($directory) -or
        (($Kind -ne 'ce-fill-probe' -or $directory -eq "$root\storage") -and
         [System.IO.Directory]::GetFileSystemEntries($directory).Count -ne 0)) {
        throw 'storage and profiles must be empty for a fresh probe run.'
    }
}
if (Get-Process -Name DayZServer_x64 -ErrorAction SilentlyContinue) { throw 'A DayZ server is already running; do not start a duplicate.' }

$minutes = $TimeoutMinutes
if ($minutes -eq 0) { $minutes = [int]$plan.probe.wait_minutes }
if ($minutes -lt 5 -or $minutes -gt 120) { throw 'Timeout minutes must be 5..120.' }
$sentinel = Join-Path $root ('profiles\' + $probe.Directory + '\complete.txt')
$census = Join-Path $root ('profiles\' + $probe.Directory + '\' + $probe.Output)
if (-not $PSCmdlet.ShouldProcess($root, "Launch the staged $Kind server and wait up to $minutes minutes for complete.txt")) { return }

Assert-NoReparsePoints -Path $root
if (Get-Process -Name DayZServer_x64 -ErrorAction SilentlyContinue) { throw 'A DayZ server is already running; do not start a duplicate.' }
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
        if (Test-CompileRefused "$root\profiles") { $outcome = 'compile-failed'; break }
    }
    if ($outcome -eq 'sentinel-seen') { Start-Sleep -Seconds 5 }
} finally {
    $server.Refresh()
    if (-not $server.HasExited) {
        # Graceful stop only: a hard kill loses the buffered RPT tail (the done sentinel and
        # late CE lines) and can tear storage mid-save. If the window does not close in time,
        # leave the server running and record it; the operator stops it gracefully.
        [void]$server.CloseMainWindow()
        $stopDeadline = [DateTime]::UtcNow.AddSeconds(90)
        while (-not $server.HasExited -and [DateTime]::UtcNow -lt $stopDeadline) {
            Start-Sleep -Seconds 2
            $server.Refresh()
        }
        if (-not $server.HasExited) { $outcome = $outcome + '-stop-pending' }
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
    kind = $Kind + '-observation'
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
    crash_logs = @(Get-FileRecords $profiles 'crash_*.log' ([System.IO.SearchOption]::TopDirectoryOnly))
    error_logs = @(Get-FileRecords $profiles 'error_*.log' ([System.IO.SearchOption]::TopDirectoryOnly))
    admin_logs = @(Get-FileRecords $profiles '*.ADM' ([System.IO.SearchOption]::TopDirectoryOnly))
    probe_outputs = @(Get-FileRecords "$profiles\$($probe.Directory)" '*' ([System.IO.SearchOption]::TopDirectoryOnly))
    storage_files = @(Get-FileRecords "$root\storage" '*' ([System.IO.SearchOption]::AllDirectories))
    export_candidates = @(Get-FileRecords $root 'mapgroupproto*.xml' ([System.IO.SearchOption]::AllDirectories))
    note = 'Observation only. Export file location is unobserved before this run; storage_files and export_candidates list what appeared.'
}
$reportPath = Join-Path $root ($Kind + '-observation-' + [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss') + '.json')
$bytes = [System.Text.Encoding]::UTF8.GetBytes(($report | ConvertTo-Json -Depth 8))
$output = [System.IO.File]::Open($reportPath, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write)
try { $output.Write($bytes, 0, $bytes.Length) } finally { $output.Dispose() }
Write-Output "Outcome: $outcome. Saved observations: $reportPath. Native acceptance is still pending."
