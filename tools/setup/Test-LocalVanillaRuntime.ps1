#requires -Version 5.1
# Native synthetic integration test. No game binaries, server process or assets.
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$id = [Guid]::NewGuid().ToString('N')
$fixture = Join-Path $env:TEMP "hc-setup-$id"
$runtime = "D:\HollowCountryLocal\ci-$id"
$server = Join-Path $fixture 'server'
$tools = Join-Path $fixture 'tools'
$mission = Join-Path $server 'mpmissions\dayzOffline.chernarusplus'
$null = New-Item -ItemType Directory -Path $fixture, $tools, $mission, (Join-Path $mission 'db'), (Join-Path $server 'battleye')
function Write-Fixture {
    param([string]$Path, [string]$Text)
    [System.IO.File]::WriteAllText($Path, $Text)
}
function Pin-Fixture {
    param([string]$Path)
    $sha = [System.Security.Cryptography.SHA256]::Create()
    $stream = [System.IO.File]::OpenRead($Path)
    try {
        return @{ bytes = $stream.Length; sha256 = ([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-', '').ToLowerInvariant() }
    } finally { $stream.Dispose(); $sha.Dispose() }
}
try {
    # Names satisfy inventory checks; contents are deliberately synthetic text.
    Write-Fixture (Join-Path $server 'DayZServer_x64.exe') 'SYNTHETIC-NOT-EXECUTABLE'
    Write-Fixture (Join-Path $server 'battleye\BEServer_x64.dll') 'SYNTHETIC-NOT-DLL'
    Write-Fixture (Join-Path $server 'serverDZ.cfg') "hostname = `"synthetic`";`nmaxPlayers = 60;`nverifySignatures = 2;`nforceSameBuild = 1;`n"
    Write-Fixture (Join-Path $mission 'init.c') '// synthetic fixture only'
    Write-Fixture (Join-Path $mission 'db\messages.xml') '<messages />'
    $files = @('init.c', 'db/messages.xml')
    $pins = @(foreach ($name in $files) {
        $pin = Pin-Fixture (Join-Path $mission $name)
        $pin.path = $name
        $pin
    })
    $baseline = @{
        schema_version = 1; tools_required = @(); mission_files = $pins
        server_exe = (Pin-Fixture (Join-Path $server 'DayZServer_x64.exe'))
        server_config = (Pin-Fixture (Join-Path $server 'serverDZ.cfg'))
        battleye_dll = (Pin-Fixture (Join-Path $server 'battleye\BEServer_x64.dll'))
    }
    $copy = Join-Path $fixture 'New-LocalVanillaRuntime.ps1'
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'New-LocalVanillaRuntime.ps1') -Destination $copy
    Write-Fixture (Join-Path $fixture 'installed-vanilla-baseline.json') ($baseline | ConvertTo-Json -Depth 6)
    & $copy -ServerRoot $server -ToolsRoot $tools -RuntimeRoot $runtime -WhatIf
    if (Test-Path -LiteralPath $runtime) { throw 'WhatIf created a runtime.' }
    & $copy -ServerRoot $server -ToolsRoot $tools -RuntimeRoot $runtime
    $plan = Get-Content -LiteralPath (Join-Path $runtime 'launch-plan.json') -Raw | ConvertFrom-Json
    if ($plan.status -ne 'staged-only-not-launched') { throw 'Missing completion status.' }
    if ($plan.server_exe_sha256 -ne $baseline.server_exe.sha256) { throw 'Hash mismatch.' }
    foreach ($name in $files) {
        if ((Pin-Fixture (Join-Path $mission $name)).sha256 -ne ($pins | Where-Object path -eq $name).sha256) { throw 'Source was modified.' }
    }
    $rejected = $false
    try { & $copy -ServerRoot $server -ToolsRoot $tools -RuntimeRoot $runtime } catch { $rejected = $_.Exception.Message -like '*Runtime already exists*' }
    if (-not $rejected) { throw 'Existing runtime was not rejected.' }
    Write-Output 'PASS: native synthetic WhatIf, hashing, staging, source preservation and overwrite refusal. No DayZ runtime acceptance.'
} finally {
    # Only these GUID-named synthetic paths are created/removed by this test.
    if (Test-Path -LiteralPath $runtime) { Remove-Item -LiteralPath $runtime -Recurse -Force }
    if (Test-Path -LiteralPath $fixture) { Remove-Item -LiteralPath $fixture -Recurse -Force }
}
