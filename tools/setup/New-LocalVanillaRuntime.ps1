#requires -Version 5.1
<#
Stages a fresh, private local vanilla test runtime. Never launches a process.
Run from native Windows PowerShell; see docs/LOCAL_WINDOWS_SETUP.md.
The pinned installed-file baseline is inventory evidence, not engine acceptance.
#>
[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'Medium')]
param(
    [string]$ServerRoot = 'D:\SteamLibrary\steamapps\common\DayZServer',
    [string]$ToolsRoot = 'D:\SteamLibrary\steamapps\common\DayZ Tools',
    [string]$RuntimeRoot = 'D:\HollowCountryLocal\vanilla-p0-001',
    [ValidateRange(10, 180)]
    [int]$SessionMinutes = 30
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if ($env:OS -ne 'Windows_NT') { throw 'Run this script in native Windows PowerShell.' }

function Assert-NoReparseAncestors {
    param([string]$Path)
    $cursor = [System.IO.Path]::GetFullPath($Path)
    while ($cursor) {
        $item = Get-Item -LiteralPath $cursor -ErrorAction SilentlyContinue
        if ($null -ne $item -and ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint)) {
            throw "ReparsePoint/junction/symlink is not allowed: $cursor"
        }
        $cursor = [System.IO.Path]::GetDirectoryName($cursor)
    }
}
function Assert-PinnedFile {
    param([string]$Path, $Expected)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "Required file missing: $Path" }
    Assert-NoReparseAncestors $Path
    if ((Get-Item -LiteralPath $Path).Length -ne [long]$Expected.bytes -or
        (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash -ne $Expected.sha256) {
        throw "Installed baseline mismatch: $Path. Stop; review Steam updates or local edits."
    }
}
function Get-MissionFilePlan {
    param([string]$Directory, [string]$Prefix = '')
    foreach ($item in (Get-ChildItem -LiteralPath $Directory)) {
        # Read directory metadata only; do not traverse/copy any stock save/profile.
        if ($item.Name -match '^(?i:storage.*|profiles?|logs?|exports?|backups?)$') {
            Write-Verbose "Excluded mutable stock path: $($item.FullName)"
            continue
        }
        if ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
            throw "ReparsePoint in mission source: $($item.FullName)"
        }
        $relative = $Prefix + $item.Name
        if ($item.PSIsContainer) {
            Get-MissionFilePlan -Directory $item.FullName -Prefix ($relative + '/')
        } else {
            [pscustomobject]@{ Path = $relative; Source = $item.FullName }
        }
    }
}
function Copy-NewVerifiedFile {
    param([string]$Source, [string]$Destination, $Expected)
    [System.IO.File]::Copy($Source, $Destination, $false)
    Assert-PinnedFile $Destination $Expected
}
function ConvertTo-PowerShellLiteral {
    param([string]$Text)
    return ("'" + $Text.Replace("'", "''") + "'")
}
function Write-NewUtf8File {
    param([string]$Path, [string]$Text)
    $bytes = [System.Text.UTF8Encoding]::new($false).GetBytes($Text)
    $stream = [System.IO.File]::Open($Path, [System.IO.FileMode]::CreateNew,
        [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
    try { $stream.Write($bytes, 0, $bytes.Length) } finally { $stream.Dispose() }
}

# Confine writable state to one fresh direct child of this non-repository path.
$runtimeParent = 'D:\HollowCountryLocal'
foreach ($path in @($ServerRoot, $ToolsRoot, $RuntimeRoot)) {
    if ($path -notmatch '^[A-Za-z]:\\' -or $path.Contains('"')) {
        throw 'Install/runtime paths must be absolute local Windows drive paths without quotes.'
    }
    Assert-NoReparseAncestors $path
}
$ServerRoot = [System.IO.Path]::GetFullPath($ServerRoot).TrimEnd('\')
$ToolsRoot = [System.IO.Path]::GetFullPath($ToolsRoot).TrimEnd('\')
$RuntimeRoot = [System.IO.Path]::GetFullPath($RuntimeRoot).TrimEnd('\')
if ([System.IO.Path]::GetDirectoryName($RuntimeRoot) -ne $runtimeParent -or
    [System.IO.Path]::GetFileName($RuntimeRoot) -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$') {
    throw "RuntimeRoot must be a single named child of $runtimeParent (letters/numbers/dot/dash/underscore)."
}
if (Test-Path -LiteralPath $RuntimeRoot) {
    throw "Runtime already exists; refusing to overwrite runtime, authored files or saves: $RuntimeRoot"
}
if (Get-Process -Name DayZServer_x64 -ErrorAction SilentlyContinue) {
    throw 'A DayZ server process is running. Finish its graceful shutdown before staging.'
}
foreach ($install in @($ServerRoot, $ToolsRoot)) {
    if (-not (Test-Path -LiteralPath $install -PathType Container)) { throw "Install missing: $install" }
}

$baselinePath = Join-Path $PSScriptRoot 'installed-vanilla-baseline.json'
$baseline = Get-Content -LiteralPath $baselinePath -Raw | ConvertFrom-Json
if ($baseline.schema_version -ne 1) { throw 'Unknown installed baseline schema.' }
foreach ($tool in $baseline.tools_required) {
    $toolPath = Join-Path $ToolsRoot $tool
    if (-not (Test-Path -LiteralPath $toolPath -PathType Leaf)) { throw "Official tool missing: $toolPath" }
}
$serverExe = Join-Path $ServerRoot 'DayZServer_x64.exe'
$sourceConfig = Join-Path $ServerRoot 'serverDZ.cfg'
$sourceMission = Join-Path $ServerRoot 'mpmissions\dayzOffline.chernarusplus'
$sourceBattleye = Join-Path $ServerRoot 'battleye\BEServer_x64.dll'
Assert-PinnedFile $serverExe $baseline.server_exe
Assert-PinnedFile $sourceConfig $baseline.server_config
Assert-PinnedFile $sourceBattleye $baseline.battleye_dll
$expectedByPath = @{}
foreach ($entry in $baseline.mission_files) {
    if ($entry.path -match '(^|/)\.\.(/|$)|:|\\|^/' -or $expectedByPath.ContainsKey($entry.path)) {
        throw 'Unsafe/duplicate mission path in baseline.'
    }
    $expectedByPath[$entry.path] = $entry
}
$missionFiles = @(Get-MissionFilePlan $sourceMission | Sort-Object Path)
if ($missionFiles.Count -ne $expectedByPath.Count) { throw 'Mission file count differs from installed baseline.' }
foreach ($entry in $missionFiles) {
    if (-not $expectedByPath.ContainsKey($entry.Path)) { throw "Unexpected mission file: $($entry.Path)" }
    Assert-PinnedFile $entry.Source $expectedByPath[$entry.Path]
}

# Preserve the installed config; only these observed fields are changed locally.
$configText = [System.IO.File]::ReadAllText($sourceConfig)
$overrides = [ordered]@{
    'hostname' = '"Hollow Country P0 local vanilla"'
    'maxPlayers' = '6'
    'verifySignatures' = '2'
    'forceSameBuild' = '1'
}
foreach ($name in $overrides.Keys) {
    $pattern = [regex]::new(('(?m)^[ \t]*' + [regex]::Escape($name) + '[ \t]*=[ \t]*(?:"[^"\r\n]*"|\d+)[ \t]*;'))
    if ($pattern.Matches($configText).Count -ne 1) { throw "Expected exactly one installed config field: $name" }
    $configText = $pattern.Replace($configText, ($name + ' = ' + $overrides[$name] + ';'), 1)
}
$missionDestination = Join-Path $RuntimeRoot 'mpmissions\dayzOffline.chernarusplus'
$backupDestination = Join-Path $RuntimeRoot 'stock-backup'
$backupMission = Join-Path $backupDestination 'mpmissions\dayzOffline.chernarusplus'
$configDestination = Join-Path $RuntimeRoot 'serverDZ.cfg'
$profilesDestination = Join-Path $RuntimeRoot 'profiles'
$storageDestination = Join-Path $RuntimeRoot 'storage'
$battleyeDestination = Join-Path $RuntimeRoot 'battleye'
$launchArguments = @(
    '-ip=127.0.0.1', '-port=2302',
    "-config=$configDestination", "-mission=$missionDestination",
    "-storage=$storageDestination", "-profiles=$profilesDestination",
    "-BEpath=$battleyeDestination", '-doLogs', '-adminLog'
)
# Store a readable command for the user; writing text never invokes it.
$quotedArguments = @($launchArguments | ForEach-Object {
    ConvertTo-PowerShellLiteral ('"' + $_ + '"')
}) -join ', '
$startCommandText = '$server = Start-Process -FilePath ' + (ConvertTo-PowerShellLiteral $serverExe) +
    ' -WorkingDirectory ' + (ConvertTo-PowerShellLiteral $ServerRoot) +
    ' -ArgumentList @(' + $quotedArguments + ') -PassThru' + [Environment]::NewLine
# The source messages file is backed up byte-for-byte; only the staged copy gets
# an official XML shutdown countdown. The installed vanilla init.c is unchanged.
$messagesText = @"
<?xml version="1.0" encoding="UTF-8"?>
<messages>
    <message>
        <deadline>$SessionMinutes</deadline>
        <shutdown>1</shutdown>
        <text>Local P0 session will shutdown in #tmin minutes.</text>
    </message>
</messages>
"@
Write-Output "Source verified: $($missionFiles.Count) pinned mission files; runtime $RuntimeRoot"
Write-Output "Plan: stock backups, vanilla mission copy, isolated profiles/storage/BattlEye, $SessionMinutes-minute shutdown."
Write-Output "Server will NOT be launched. Requested game bind is 127.0.0.1:2302; native socket verification remains mandatory."
if (-not $PSCmdlet.ShouldProcess($RuntimeRoot, 'Create NEW isolated local vanilla runtime and stock backups')) {
    return
}

# All mutations are below the single ShouldProcess gate. Existing roots are never
# merged, repaired, deleted or reused, including after an interrupted prior run.
Assert-NoReparseAncestors $RuntimeRoot
if (-not (Test-Path -LiteralPath $runtimeParent)) {
    $null = New-Item -ItemType Directory -Path $runtimeParent
}
$null = New-Item -ItemType Directory -Path $RuntimeRoot
$directories = @($backupDestination, $backupMission, $missionDestination,
    $profilesDestination, $storageDestination, $battleyeDestination)
foreach ($entry in $missionFiles) {
    $directories += [System.IO.Path]::GetDirectoryName((Join-Path $missionDestination $entry.Path))
    $directories += [System.IO.Path]::GetDirectoryName((Join-Path $backupMission $entry.Path))
}
# Parents first; each item is inside the freshly created runtime.
foreach ($directory in ($directories | Sort-Object -Property @{Expression={$_.Length}}, @{Expression={$_}} -Unique)) {
    if (-not (Test-Path -LiteralPath $directory)) {
        $null = New-Item -ItemType Directory -Path $directory
    }
}
Copy-NewVerifiedFile $sourceConfig (Join-Path $backupDestination 'serverDZ.cfg') $baseline.server_config
foreach ($entry in $missionFiles) {
    $expected = $expectedByPath[$entry.Path]
    Copy-NewVerifiedFile $entry.Source (Join-Path $backupMission $entry.Path) $expected
    if ($entry.Path -ne 'db/messages.xml') {
        Copy-NewVerifiedFile $entry.Source (Join-Path $missionDestination $entry.Path) $expected
    }
}
Copy-NewVerifiedFile $sourceBattleye (Join-Path $battleyeDestination 'BEServer_x64.dll') $baseline.battleye_dll
Write-NewUtf8File $configDestination $configText
Write-NewUtf8File (Join-Path $missionDestination 'db\messages.xml') $messagesText
# Detect Steam/source changes during the copy before producing the completion marker.
Assert-PinnedFile $serverExe $baseline.server_exe
Assert-PinnedFile $sourceConfig $baseline.server_config
foreach ($entry in $missionFiles) { Assert-PinnedFile $entry.Source $expectedByPath[$entry.Path] }
$stagedMission = @(
    foreach ($entry in $missionFiles) {
        $stagedPath = Join-Path $missionDestination $entry.Path
        [ordered]@{ path = $entry.Path; sha256 = (Get-FileHash -LiteralPath $stagedPath -Algorithm SHA256).Hash.ToLowerInvariant() }
    }
)
$launchPlan = [ordered]@{
    schema_version = 1
    staged_utc = [DateTime]::UtcNow.ToString('o')
    status = 'staged-only-not-launched'
    server_exe = $serverExe
    server_exe_sha256 = $baseline.server_exe.sha256
    working_directory = $ServerRoot
    arguments = $launchArguments
    requested_bind = '127.0.0.1:2302'
    runtime_root = $RuntimeRoot
    mission = $missionDestination
    profiles = $profilesDestination
    storage = $storageDestination
    session_minutes = $SessionMinutes
    config_sha256 = (Get-FileHash -LiteralPath $configDestination -Algorithm SHA256).Hash.ToLowerInvariant()
    mission_files = $stagedMission
    source_baseline_sha256 = (Get-FileHash -LiteralPath $baselinePath -Algorithm SHA256).Hash.ToLowerInvariant()
}
Write-NewUtf8File (Join-Path $RuntimeRoot 'start-command.txt') $startCommandText
Write-NewUtf8File (Join-Path $RuntimeRoot 'launch-plan.json') ($launchPlan | ConvertTo-Json -Depth 8)
Write-Output "Staged only: $RuntimeRoot. Completion marker: launch-plan.json"
Write-Output 'Review the runbook and actual Windows socket bindings before connecting. No runtime test has passed yet.'
