$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
docker compose -f deploy/ragflow/compose.yaml up -d
if ($LASTEXITCODE -ne 0) { throw '知识库启动失败，请检查 Docker Desktop。' }
python -m uvicorn api.server:app --host 127.0.0.1 --port 8000
