#requires -Version 5.1
# One native bootstrap: launch the previously verified local runtime and record
# observations for the agent. No client launch, remoting, service or scheduled task.
[CmdletBinding(SupportsShouldProcess = $true)]
param()
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
$runtime = 'D:\HollowCountryLocal\vanilla-p0-001'
$install = 'D:\SteamLibrary\steamapps\common\DayZServer'
$exe = Join-Path $install 'DayZServer_x64.exe'
$plan = Get-Content -LiteralPath (Join-Path $runtime 'launch-plan.json') -Raw | ConvertFrom-Json
if ($plan.status -ne 'staged-only-not-launched' -or $plan.runtime_root -ne $runtime -or
    $plan.server_exe -ne $exe -or $plan.working_directory -ne $install) { throw 'Unexpected staging plan.' }
if ((Read-Sha256 $exe) -ne '987fbc47bab1dab37f74d7f700aa2e5b6af936a7181a62f5ba9f0090aebba805' -or
    (Read-Sha256 (Join-Path $runtime 'serverDZ.cfg')) -ne 'e862cbe251c283aa77d432e4211148f7aa9b42d43d26928f611fdc869eb5d1c0') { throw 'Verified executable/config changed.' }
foreach ($file in $plan.mission_files) {
    if ($file.path -match '(^|/)\.\.(/|$)|:|\\|^/') { throw 'Unsafe mission manifest path.' }
    if ((Read-Sha256 (Join-Path $runtime ('mpmissions\dayzOffline.chernarusplus\' + $file.path))) -ne $file.sha256) { throw "Staged mission changed: $($file.path)" }
}
if (Get-Process -Name DayZServer_x64 -ErrorAction SilentlyContinue) { throw 'A DayZ server is already running; do not start a duplicate.' }
$arguments = @('-ip=127.0.0.1', '-port=2302',
    "-config=$runtime\serverDZ.cfg", "-mission=$runtime\mpmissions\dayzOffline.chernarusplus",
    "-storage=$runtime\storage", "-profiles=$runtime\profiles", "-BEpath=$runtime\battleye", '-doLogs', '-adminLog')
if (-not $PSCmdlet.ShouldProcess($runtime, 'Launch verified vanilla server and record 30 seconds of process/socket observations')) { return }
$quoted = @($arguments | ForEach-Object { [char]34 + $_ + [char]34 })
$server = Start-Process -FilePath $exe -WorkingDirectory $install -ArgumentList $quoted -PassThru
Write-Output "ServerPID=$($server.Id). Collecting observations; leave this window open."
$samples = @()
for ($i = 0; $i -lt 6; $i++) {
    Start-Sleep -Seconds 5
    $server.Refresh()
    $samples += [ordered]@{
        utc = [DateTime]::UtcNow.ToString('o'); exited = $server.HasExited
        udp = @(Get-NetUDPEndpoint -OwningProcess $server.Id -ErrorAction SilentlyContinue | Select-Object LocalAddress, LocalPort, OwningProcess)
        tcp = @(Get-NetTCPConnection -OwningProcess $server.Id -ErrorAction SilentlyContinue | Select-Object LocalAddress, LocalPort, RemoteAddress, RemotePort, State)
    }
    if ($server.HasExited) { break }
}
$report = [ordered]@{ server_pid = $server.Id; samples = $samples; status = 'observed-not-accepted' }
$reportPath = Join-Path $runtime ('launch-observation-' + [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss') + '.json')
[System.IO.File]::WriteAllText($reportPath, ($report | ConvertTo-Json -Depth 8))
Write-Output "Saved observations: $reportPath. Keep the server open; native acceptance is still pending."
