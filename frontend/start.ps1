$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
npm run dev -- --hostname 0.0.0.0 --port 3000
