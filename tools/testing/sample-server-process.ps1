#requires -Version 5.1
# Read-only sampler for a running DayZ server process and its storage directory.
# Every IntervalSeconds, for Samples samples, it appends one CSV row with the process WorkingSet64 and
# PrivateMemorySize64, and the total size, file count and newest last-write time of StoragePath.
# It never signals, attaches to or modifies the process, never writes to StoragePath, and writes only the new
# OutputCsv, which it refuses to overwrite. The CSV carries no paths. Parse it with
# tools/testing/baseline_capture.py. Nothing here measures game behaviour or accepts a budget.
#
# Example, from a Windows PowerShell prompt (the caller owns any execution-policy decision):
#   .\sample-server-process.ps1 -ProcessId 1234 -StoragePath D:\server\storage -OutputCsv .\cold.csv `
#       -IntervalSeconds 10 -Samples 180
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateRange(1, 4194304)]
    [int]$ProcessId,
    [Parameter(Mandatory = $true)]
    [string]$StoragePath,
    [Parameter(Mandatory = $true)]
    [string]$OutputCsv,
    [ValidateRange(1, 3600)]
    [int]$IntervalSeconds = 10,
    [ValidateRange(1, 100000)]
    [int]$Samples = 60
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if (Test-Path -LiteralPath $OutputCsv) {
    throw 'OutputCsv already exists; choose a new file name so an earlier capture is never overwritten.'
}
$stamp = "yyyy-MM-ddTHH:mm:ss.fff'Z'"
$culture = [System.Globalization.CultureInfo]::InvariantCulture
$utf8 = New-Object System.Text.UTF8Encoding($false)
$writer = New-Object System.IO.StreamWriter($OutputCsv, $false, $utf8)
try {
    $writer.WriteLine('timestamp_utc,process_alive,working_set_bytes,private_bytes,storage_bytes,storage_files,storage_last_write_utc')
    $writer.Flush()
    $clock = [System.Diagnostics.Stopwatch]::StartNew()
    for ($index = 0; $index -lt $Samples; $index++) {
        $now = (Get-Date).ToUniversalTime().ToString($stamp, $culture)
        $alive = 0
        $workingSet = ''
        $privateBytes = ''
        $process = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
        if ($null -ne $process) {
            # The process can exit between Get-Process and the property reads; record it as lost and stop.
            try {
                $process.Refresh()
                if (-not $process.HasExited) {
                    $workingSet = [string]$process.WorkingSet64
                    $privateBytes = [string]$process.PrivateMemorySize64
                    $alive = 1
                }
            } catch {
                $alive = 0
                $workingSet = ''
                $privateBytes = ''
            }
        }
        $bytes = ''
        $files = ''
        $lastWrite = ''
        if (Test-Path -LiteralPath $StoragePath -PathType Container) {
            $total = [long]0
            $count = [long]0
            $newest = [datetime]::MinValue
            $enumErrors = @()
            $items = @(Get-ChildItem -LiteralPath $StoragePath -Recurse -File -Force -ErrorAction SilentlyContinue -ErrorVariable enumErrors)
            foreach ($item in $items) {
                $total += $item.Length
                $count += 1
                if ($item.LastWriteTimeUtc -gt $newest) { $newest = $item.LastWriteTimeUtc }
            }
            # Any enumeration error leaves this storage sample unmeasured instead of empty or partial.
            if ($enumErrors.Count -gt 0) {
                $bytes = ''
                $files = ''
                $lastWrite = ''
            } else {
                $bytes = [string]$total
                $files = [string]$count
                if ($count -gt 0) { $lastWrite = $newest.ToString($stamp, $culture) }
            }
        }
        $writer.WriteLine(($now, [string]$alive, $workingSet, $privateBytes, $bytes, $files, $lastWrite) -join ',')
        $writer.Flush()
        if ($alive -eq 0) { break }
        if ($index -lt ($Samples - 1)) {
            $waitMs = (($index + 1) * $IntervalSeconds * 1000) - $clock.ElapsedMilliseconds
            if ($waitMs -gt 0) { Start-Sleep -Milliseconds ([int]$waitMs) }
        }
    }
} finally {
    $writer.Dispose()
}
