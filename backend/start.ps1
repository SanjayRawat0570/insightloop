$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# Load local .env (if present) without overriding already-set env vars.
if (Test-Path .env) {
  Get-Content .env |
    Where-Object { $_ -and $_ -notmatch '^\s*#' } |
    ForEach-Object {
      $name, $value = $_ -split '=', 2
      if ($name -and -not (Test-Path "Env:$name")) {
        Set-Item -Path "Env:$name" -Value $value
      }
    }
}

& .\venv\Scripts\uvicorn.exe api.main:app --host 0.0.0.0 --port 8000 --reload
