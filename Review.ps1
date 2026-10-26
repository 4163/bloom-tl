param([int]$Port = 8765, [string]$Python, [switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$taskUrl = "http://127.0.0.1:$Port/"
$taskForeignService = $false
try {
    $taskResponse = Invoke-WebRequest -Uri ($taskUrl + 'api/catalog') -TimeoutSec 2
    $taskCatalog = $taskResponse.Content | ConvertFrom-Json
    if ($taskResponse.StatusCode -eq 200 -and $taskCatalog.workspace -eq $PSScriptRoot) {
        if (-not $NoBrowser) { Start-Process $taskUrl }
        return
    }
    $taskForeignService = $true
} catch {}
if ($taskForeignService) { throw "Port $Port is serving another workspace. Choose a different -Port." }
if (-not $Python) {
    $taskCandidates = @(
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python313\python.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python311\python.exe')
    )
    $Python = $taskCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    if (-not $Python) { $Python = (Get-Command python -ErrorAction Stop).Source }
}
$taskLogDir = Join-Path $PSScriptRoot '.runtime\review'
New-Item -ItemType Directory -Path $taskLogDir -Force | Out-Null
$taskArguments = '-I -B "' + (Join-Path $PSScriptRoot 'manga.py') + '" serve --port ' + $Port
$taskProcess = Start-Process -FilePath $Python -ArgumentList $taskArguments -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $taskLogDir 'stdout.log') -RedirectStandardError (Join-Path $taskLogDir 'stderr.log')
for ($taskAttempt = 0; $taskAttempt -lt 30; $taskAttempt++) {
    Start-Sleep -Milliseconds 300
    if ($taskProcess.HasExited) { throw "Review server exited. See $taskLogDir\stderr.log" }
    try {
        $taskResponse = Invoke-WebRequest -Uri ($taskUrl + 'api/catalog') -TimeoutSec 2
        $taskCatalog = $taskResponse.Content | ConvertFrom-Json
        if ($taskResponse.StatusCode -eq 200 -and $taskCatalog.workspace -eq $PSScriptRoot) {
            Write-Host "Review server PID $($taskProcess.Id) at $taskUrl"
            if (-not $NoBrowser) { Start-Process $taskUrl }
            return
        }
    } catch {}
}
throw "Review server did not become ready. See $taskLogDir."
