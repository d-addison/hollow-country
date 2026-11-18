#requires -Version 5.1
# Deterministic original-source PBO; installed official DSSignFile.exe and
# DSCheckSignatures.exe are invoked by sign.py with their actual directory syntax.
[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [Parameter(Mandatory = $true)][string]$AddonRoot,
    [Parameter(Mandatory = $true)][string]$OutputRoot,
    [string]$ExpansionAddonRoot,
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
if (-not $ExpansionAddonRoot) { $ExpansionAddonRoot = Join-Path (Split-Path -Parent $AddonRoot) 'HollowCountryExpansionAI' }
if (-not (Test-Path -LiteralPath (Join-Path $ExpansionAddonRoot 'config.cpp'))) { throw 'HCX addon source is required; supply -ExpansionAddonRoot.' }
$null = New-Item -ItemType Directory -Path $OutputRoot
$builds = @(
    @{ Root = $AddonRoot; Prefix = 'HollowCountry'; Name = 'hollowcountry' },
    @{ Root = $ExpansionAddonRoot; Prefix = 'HollowCountryExpansionAI'; Name = 'hollowcountryexpansionai' }
)
foreach ($build in $builds) {
    $pboPath = Join-Path $OutputRoot ($build.Name + '.pbo')
    & $Python (Join-Path $PSScriptRoot 'pbo.py') pbo --addon $build.Root --prefix $build.Prefix --out $pboPath
    if ($LASTEXITCODE -ne 0) { throw ('PBO build failed: ' + $build.Prefix) }
    & $Python (Join-Path $PSScriptRoot 'pbo.py') verify --prefix $build.Prefix $pboPath
    if ($LASTEXITCODE -ne 0) { throw ('PBO structural verification failed: ' + $build.Prefix) }
    $modRoot = Join-Path $OutputRoot ('@' + $build.Prefix)
    if ($Unsigned) {
        $addons = Join-Path $modRoot 'addons'
        $null = New-Item -ItemType Directory -Path $addons -Force
        Copy-Item -LiteralPath $pboPath -Destination (Join-Path $addons ($build.Name + '.pbo'))
    } else {
        & $Python (Join-Path $PSScriptRoot 'sign.py') --pbo $pboPath --tools $ToolsRoot --private-key $PrivateKey --public-key $PublicKey --out $modRoot
        if ($LASTEXITCODE -ne 0) { throw ('Official signing/verification failed: ' + $build.Prefix) }
    }
    $metadata = Join-Path $build.Root 'mod.cpp'
    if (Test-Path -LiteralPath $metadata) { Copy-Item -LiteralPath $metadata -Destination (Join-Path $modRoot 'mod.cpp') }
}
if ($Unsigned) {
    Write-Output 'Both development addons built unsigned; signatures not checked.'
} else {
    Write-Output 'Both development addons built and signatures checked.'
}
Write-Output 'Native compile, normal server/client and multiplayer acceptance pending.'
