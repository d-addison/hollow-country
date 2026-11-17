#requires -Version 5.1
# Deterministic original-source PBO; installed official DSSignFile.exe and
# DSCheckSignatures.exe are invoked by sign.py with their actual directory syntax.
[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [Parameter(Mandatory = $true)][string]$AddonRoot,
    [Parameter(Mandatory = $true)][string]$OutputRoot,
    [string]$ToolsRoot = 'D:\SteamLibrary\steamapps\common\DayZ Tools',
    [string]$Python = 'python',
    [switch]$Unsigned,
    [string]$PrivateKey,
    [string]$PublicKey
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if (Test-Path -LiteralPath $OutputRoot) { throw 'Choose a fresh output directory.' }
if (-not $Unsigned -and (-not $PrivateKey -or -not $PublicKey)) { throw 'Signing requires external private/public keys, or explicitly use -Unsigned.' }
if (-not $PSCmdlet.ShouldProcess($OutputRoot, 'Build original-source development PBO and optionally sign/verify with official tools')) { return }
$pythonCommand = Get-Command -Name $Python -CommandType Application -ErrorAction Stop
if ($pythonCommand.Source -match '(?i)\\WindowsApps\\') { throw 'Windows Store python alias is unverified. Supply -Python with a real Python 3.10+ executable.' }
$Python = $pythonCommand.Source
& $Python -c 'import sys; print(sys.version); raise SystemExit(0 if sys.version_info >= (3, 10) else 1)'
if ($LASTEXITCODE -ne 0) { throw 'A working native Windows Python 3.10+ is required; source packaging can still run on Linux.' }
$null = New-Item -ItemType Directory -Path $OutputRoot
$pboPath = Join-Path $OutputRoot 'hollowcountry.pbo'
& $Python (Join-Path $PSScriptRoot 'pbo.py') pbo --addon $AddonRoot --out $pboPath
if ($LASTEXITCODE -ne 0) { throw 'PBO build failed.' }
& $Python (Join-Path $PSScriptRoot 'pbo.py') verify $pboPath
if ($LASTEXITCODE -ne 0) { throw 'PBO structural verification failed.' }
if ($Unsigned) {
    $addons = Join-Path $OutputRoot '@HollowCountry\addons'
    $null = New-Item -ItemType Directory -Path $addons
    Copy-Item -LiteralPath $pboPath -Destination (Join-Path $addons 'hollowcountry.pbo')
    $metadata = Join-Path $AddonRoot 'mod.cpp'
    if (Test-Path -LiteralPath $metadata) { Copy-Item -LiteralPath $metadata -Destination (Join-Path $OutputRoot '@HollowCountry\mod.cpp') }
    Write-Output 'Unsigned development artifact. Native compile, signature, normal client/server and multiplayer acceptance pending.'
    return
}
& $Python (Join-Path $PSScriptRoot 'sign.py') --pbo $pboPath --tools $ToolsRoot --private-key $PrivateKey --public-key $PublicKey --out (Join-Path $OutputRoot '@HollowCountry')
if ($LASTEXITCODE -ne 0) { throw 'Official signing/verification failed; release remains gated.' }
$metadata = Join-Path $AddonRoot 'mod.cpp'
if (Test-Path -LiteralPath $metadata) { Copy-Item -LiteralPath $metadata -Destination (Join-Path $OutputRoot '@HollowCountry\mod.cpp') }
Write-Output 'Official tools verified this development signature. Native/client/multiplayer/performance acceptance still pending.'
