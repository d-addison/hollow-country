#requires -Version 5.1
<#
.SYNOPSIS
Launch the installed vanilla DayZ client against a running loopback test server.
.EXAMPLE
.\Start-LocalClient.ps1 -ClientRoot 'D:\SteamLibrary\steamapps\common\DayZ' -WhatIf
#>
[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [Parameter(Mandatory = $true)]
    [string]$ClientRoot,
    [ValidateRange(1024, 65533)]
    [int]$GamePort = 2302,
    [ValidateRange(1024, 65535)]
    [int]$QueryPort = 27016
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$launcher = Join-Path $ClientRoot 'DayZ_BE.exe'
$client = Join-Path $ClientRoot 'DayZ_x64.exe'
if (-not (Test-Path -LiteralPath $launcher -PathType Leaf) -or
    -not (Test-Path -LiteralPath $client -PathType Leaf)) {
    throw 'ClientRoot must contain the installed DayZ_BE.exe and DayZ_x64.exe.'
}
$servers = @(Get-Process -Name DayZServer_x64 -ErrorAction SilentlyContinue)
$bindings = @(Get-NetUDPEndpoint -ErrorAction Stop | Where-Object {
    $_.LocalAddress -eq '127.0.0.1' -and $_.LocalPort -eq $GamePort -and
    $_.OwningProcess -in @($servers | ForEach-Object { $_.Id })
})
if ($bindings.Count -ne 1) {
    throw 'Expected exactly one running DayZ server on the requested loopback game port.'
}
$arguments = @('0', '1', '1', '-exe', 'DayZ_x64.exe',
    "-connect=127.0.0.1:${GamePort}:${QueryPort}", "-port=$GamePort")
Write-Output "Local connection: 127.0.0.1:${GamePort}:${QueryPort}; no mods requested."
if (-not $PSCmdlet.ShouldProcess($client, 'Launch vanilla DayZ through BattlEye with explicit game and Steam query ports')) {
    return
}
if (Get-Process -Name DayZ_x64 -ErrorAction SilentlyContinue) {
    throw 'DayZ is already running. Close the game before launching another client.'
}
$launched = Start-Process -FilePath $launcher -WorkingDirectory $ClientRoot -ArgumentList $arguments -PassThru
Write-Output "BattlEye launcher PID: $($launched.Id). Confirm connection in the server log and client."
