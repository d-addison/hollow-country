#requires -Version 5.1
# Deterministic original-source PBO; installed official DSSignFile.exe and
# DSCheckSignatures.exe are invoked by sign.py with their actual directory syntax.
[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [Parameter(Mandatory = $true)][string]$AddonRoot,
    [Parameter(Mandatory = $true)][string]$OutputRoot,
    [string]$ExpansionAddonRoot,
    [string]$DayZAddons = 'D:\SteamLibrary\steamapps\common\DayZServer\Addons',
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
# HollowCountryAnims ships as an extra signed PBO inside @HollowCountry (owner 2026-11-18). Its .anm clips
# are generated from the installed DayZ data at build time and never live in Git.
$animsRoot = Join-Path $OutputRoot 'anims'
$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
& $Python (Join-Path $repoRoot 'tools\anim\build_infected_clips.py') --addons $DayZAddons --out $animsRoot
if ($LASTEXITCODE -ne 0) { throw 'Animation clip generation failed: HollowCountryAnims' }
& $Python (Join-Path $repoRoot 'tools\anim\build_anims_addon.py') --addons $DayZAddons --out $animsRoot
if ($LASTEXITCODE -ne 0) { throw 'PBO build failed: HollowCountryAnims' }
$animsPbo = Join-Path $OutputRoot 'hollowcountryanims.pbo'
Copy-Item -LiteralPath (Join-Path $animsRoot 'addons\HollowCountryAnims.pbo') -Destination $animsPbo
& $Python (Join-Path $PSScriptRoot 'pbo.py') verify --prefix HollowCountryAnims $animsPbo
if ($LASTEXITCODE -ne 0) { throw 'PBO structural verification failed: HollowCountryAnims' }
$baseAddons = Join-Path (Join-Path $OutputRoot '@HollowCountry') 'addons'
if ($Unsigned) {
    Copy-Item -LiteralPath $animsPbo -Destination (Join-Path $baseAddons 'hollowcountryanims.pbo')
} else {
    $animsSigned = Join-Path $OutputRoot 'signed-anims'
    & $Python (Join-Path $PSScriptRoot 'sign.py') --pbo $animsPbo --tools $ToolsRoot --private-key $PrivateKey --public-key $PublicKey --out $animsSigned
    if ($LASTEXITCODE -ne 0) { throw 'Official signing/verification failed: HollowCountryAnims' }
    Copy-Item -Path (Join-Path $animsSigned 'addons\*') -Destination $baseAddons
}
# One opt-in shared with Python release/compile staging; unset leaves the build unchanged.
if ($env:HC_ASSETS_PLAN) {
    $assetsRoot = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath((Join-Path $OutputRoot 'assets'))
    $assetsPlan = (Resolve-Path -LiteralPath $env:HC_ASSETS_PLAN).Path
    Push-Location $repoRoot
    try {
        & $Python -B -m tools.package.build_assets_addon --plan $assetsPlan --out $assetsRoot
        if ($LASTEXITCODE -ne 0) { throw 'PBO build failed: HollowCountryAssets (sealed ODOL required)' }
    } finally { Pop-Location }
    $assetsPbo = Join-Path $assetsRoot 'addons\HollowCountryAssets.pbo'
    & $Python (Join-Path $PSScriptRoot 'pbo.py') verify --prefix HollowCountryAssets $assetsPbo
    if ($LASTEXITCODE -ne 0) { throw 'PBO structural verification failed: HollowCountryAssets' }
    if ($Unsigned) {
        Copy-Item -LiteralPath $assetsPbo -Destination (Join-Path $baseAddons 'hollowcountryassets.pbo')
    } else {
        $assetsSigned = Join-Path $OutputRoot 'signed-assets'
        & $Python (Join-Path $PSScriptRoot 'sign.py') --pbo $assetsPbo --tools $ToolsRoot --private-key $PrivateKey --public-key $PublicKey --out $assetsSigned
        if ($LASTEXITCODE -ne 0) { throw 'Official signing/verification failed: HollowCountryAssets' }
        Copy-Item -Path (Join-Path $assetsSigned 'addons\*') -Destination $baseAddons
    }
}
if ($Unsigned) {
    Write-Output 'All development addons built unsigned; signatures not checked.'
} else {
    Write-Output 'All development addons built and signatures checked.'
}
Write-Output 'Native compile, normal server/client and multiplayer acceptance pending.'
