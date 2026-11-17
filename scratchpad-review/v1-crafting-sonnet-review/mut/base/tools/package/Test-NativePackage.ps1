#requires -Version 5.1
# Native AST + synthetic guard checks only. Never starts a real or fake server.
[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
foreach ($name in @('Build-Sign-Verify.ps1', 'Invoke-NativeSmoke.ps1', 'Test-NativePackage.ps1')) {
    $tokens = $null
    $errors = $null
    $null = [System.Management.Automation.Language.Parser]::ParseFile((Join-Path $PSScriptRoot $name), [ref]$tokens, [ref]$errors)
    if ($errors.Count) { throw "Native PowerShell syntax errors in $name : $($errors | Out-String)" }
}
$fixture = Join-Path $env:TEMP ('hc-package-' + [Guid]::NewGuid().ToString('N'))
$serverRoot = Join-Path $fixture 'server'
$mission = Join-Path $serverRoot 'mpmissions\dayzOffline.chernarusplus'
$runtime = Join-Path $fixture 'runtime'
$build = Join-Path $fixture 'build'
$null = New-Item -ItemType Directory -Path $mission
try {
    [IO.File]::WriteAllText((Join-Path $serverRoot 'DayZServer_x64.exe'), 'SYNTHETIC-NOT-EXECUTABLE')
    [IO.File]::WriteAllText((Join-Path $mission 'init.c'), '// synthetic original fixture')
    $fakePbo = Join-Path $fixture 'synthetic.pbo'
    [IO.File]::WriteAllText($fakePbo, 'SYNTHETIC-NOT-PBO')
    & (Join-Path $PSScriptRoot 'Invoke-NativeSmoke.ps1') -Pbo $fakePbo -RuntimeRoot $runtime -ServerRoot $serverRoot -Python 'MUST-NOT-EXECUTE' -WhatIf
    if (Test-Path -LiteralPath $runtime) { throw 'Smoke WhatIf wrote a runtime.' }
    & (Join-Path $PSScriptRoot 'Build-Sign-Verify.ps1') -AddonRoot $fixture -OutputRoot $build -Unsigned -Python 'MUST-NOT-EXECUTE' -WhatIf
    if (Test-Path -LiteralPath $build) { throw 'Build WhatIf wrote output.' }
    $null = New-Item -ItemType Directory -Path $runtime
    $rejected = $false
    try { & (Join-Path $PSScriptRoot 'Invoke-NativeSmoke.ps1') -Pbo $fakePbo -RuntimeRoot $runtime -ServerRoot $serverRoot -WhatIf }
    catch { $rejected = $_.Exception.Message -like '*Runtime already exists*' }
    if (-not $rejected) { throw 'Existing runtime was not rejected.' }
    $steamTarget = Join-Path $fixture 'SteamLibrary\steamapps\common\DayZServer\runtime'
    $rejected = $false
    try { & (Join-Path $PSScriptRoot 'Invoke-NativeSmoke.ps1') -Pbo $fakePbo -RuntimeRoot $steamTarget -ServerRoot $serverRoot -WhatIf }
    catch { $rejected = $_.Exception.Message -like '*outside the Steam*' }
    if (-not $rejected) { throw 'Steam installation target was not rejected.' }
    $rejected = $false
    try { & (Join-Path $PSScriptRoot 'Build-Sign-Verify.ps1') -AddonRoot $fixture -OutputRoot $build -WhatIf }
    catch { $rejected = $_.Exception.Message -like '*requires external*' }
    if (-not $rejected) { throw 'Missing signing keys were not rejected.' }
    Write-Output 'PASS native AST and synthetic guards. No DayZ execution or signature claim.'
} finally {
    # Only this GUID-named, synthetic directory is removed.
    if (Test-Path -LiteralPath $fixture) { Remove-Item -LiteralPath $fixture -Recurse -Force }
}
