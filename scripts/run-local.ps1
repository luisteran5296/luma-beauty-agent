$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$taskPython = Join-Path $taskRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) { throw 'Run the installation steps in README.md first.' }
$env:LOCAL_DEV_AUTH = 'true'
$env:ENVIRONMENT = 'development'
$env:CATALOG_POINTER_PATH = Join-Path $taskRoot 'data/active-catalog.json'
if (Test-Path -LiteralPath (Join-Path $taskRoot 'data/retrieval-bundle.json')) {
    $env:LOCAL_AGENT = 'true'
    $env:USE_GCLOUD_CREDENTIALS = 'true'
}
# Local bypass never binds to a public interface.
$taskApi = Start-Process -FilePath $taskPython -ArgumentList @('-m','uvicorn','gateway.main:app','--host','127.0.0.1','--port','8000') -WorkingDirectory $taskRoot -WindowStyle Hidden -PassThru
$taskNpm = (Get-Command npm.cmd).Source
$taskWeb = Start-Process -FilePath $taskNpm -ArgumentList @('run','dev') -WorkingDirectory (Join-Path $taskRoot 'frontend') -WindowStyle Hidden -PassThru
Write-Host "Store: http://127.0.0.1:5173 (API PID $($taskApi.Id), frontend launcher PID $($taskWeb.Id))"
Write-Host 'Stop the API/frontend process trees when finished. These servers are local only.'
