$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = "$Root;$Root\packages\common"
$env:JWT_SECRET = "dev-secret-change-me"
$env:DATABASE_URL = "sqlite:///$Root/database.db"
$env:REDIS_URL = "redis://127.0.0.1:6379/0"
$env:UPLOAD_DIR = "$Root\uploads"

Write-Host "Starting Asyncgram microservices (requires Redis on 6379)"
Write-Host "Gateway: configure nginx with infra/nginx/asyncgram.conf or call services directly"

$services = @(
  @{ Name = "auth"; Module = "services.auth_service.app.main:app"; Port = 8001 },
  @{ Name = "chat"; Module = "services.chat_service.app.main:app"; Port = 8002 },
  @{ Name = "ws"; Module = "services.ws_gateway.app.main:app"; Port = 8003 },
  @{ Name = "media"; Module = "services.media_service.app.main:app"; Port = 8004 },
  @{ Name = "admin"; Module = "services.admin_service.app.main:app"; Port = 8005 }
)

foreach ($svc in $services) {
  Start-Process -FilePath "python" -ArgumentList @(
    "-m", "uvicorn", $svc.Module,
    "--host", "127.0.0.1",
    "--port", "$($svc.Port)",
    "--reload"
  ) -WorkingDirectory $Root -WindowStyle Normal
  Write-Host "Started $($svc.Name) on port $($svc.Port)"
}

Write-Host "Frontend: cd frontend && npm run dev (VITE_API_BASE=http://127.0.0.1:8080 with nginx, or http://127.0.0.1:8002 for chat-only dev)"
