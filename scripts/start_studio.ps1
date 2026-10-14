<#
.SYNOPSIS  Start the CURRENT Creature Forge Studio on http://127.0.0.1:8000 (Windows).
.DESCRIPTION
  1. Finds whatever is listening on the port. A Creature Forge Studio from an older run is stopped
     (identified by its command line containing run_studio.py); anything else is left alone and reported.
  2. Rebuilds the frontend if studio\src is newer than studio\dist.
  3. Starts the server from the repository root with the project .venv, waits for /api/version, and verifies
     that the routes the frontend needs exist. Then opens the browser (use -NoBrowser to skip).
  Usage:  powershell -ExecutionPolicy Bypass -File scripts\start_studio.ps1 [-Port 8000] [-NoBrowser]
#>
param([int]$Port = 8000, [switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$py = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path $py)) { throw "Missing $py. Create the environment as described in docs/FREE_MEMORY_QUICKSTART.md; do not use another interpreter." }

# 1. Port owner
$conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($conn) {
  $owner = Get-CimInstance Win32_Process -Filter "ProcessId=$($conn.OwningProcess)"
  if ($owner.CommandLine -match 'run_studio\.py') {
    Write-Host "Stopping older Creature Forge Studio on port $Port (PID $($owner.ProcessId), started $($owner.CreationDate))."
    $parent = Get-CimInstance Win32_Process -Filter "ProcessId=$($owner.ParentProcessId)" -ErrorAction SilentlyContinue
    if ($parent -and $parent.CommandLine -match 'run_studio\.py') { Stop-Process -Id $parent.ProcessId -Force }
    Stop-Process -Id $owner.ProcessId -Force
    Start-Sleep -Seconds 1
  } else {
    throw "Port $Port is used by another program (PID $($owner.ProcessId): $($owner.CommandLine)). Not touching it; free the port or pass -Port <other>."
  }
}

# 2. Frontend freshness
$dist = Join-Path $root 'studio\dist\index.html'
$newestSrc = Get-ChildItem (Join-Path $root 'studio\src') -Recurse -File | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not (Test-Path $dist) -or $newestSrc.LastWriteTime -gt (Get-Item $dist).LastWriteTime) {
  Write-Host 'Frontend build is missing or older than its sources; building...'
  npm --prefix studio install --no-audit --no-fund | Out-Null
  npm --prefix studio run build
  if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
}

# 3. Start and verify
$env:CREATURE_FORGE_PORT = "$Port"
$proc = Start-Process -FilePath $py -ArgumentList 'scripts\run_studio.py' -WorkingDirectory $root -PassThru -WindowStyle Minimized
$base = "http://127.0.0.1:$Port"
$ver = $null
for ($i = 0; $i -lt 120 -and -not $ver; $i++) {
  Start-Sleep -Milliseconds 500
  if ($proc.HasExited) { throw "Studio exited early (code $($proc.ExitCode)). Run `"$py scripts\run_studio.py`" in a terminal to see the error." }
  try { $ver = Invoke-RestMethod "$base/api/version" -TimeoutSec 2 } catch { }
}
if (-not $ver) { throw "Studio did not answer on $base/api/version within 60 s." }
$need = '/api/lab/trials', '/api/locomotion/summary', '/api/demo/runs', '/api/overview', '/api/investigations'
$missing = $need | Where-Object { $ver.api_routes -notcontains $_ }
if ($missing) { throw "Server is missing routes: $($missing -join ', ')" }
Write-Host "Creature Forge Studio is running: $base  (commit $($ver.git_commit) on $($ver.git_branch), frontend built $($ver.dist_built))"
Write-Host "Stop it with:  Stop-Process -Id $($proc.Id)"
if (-not $NoBrowser) { Start-Process $base }
