Write-Host "🚀 Installing Markly for Windows..." -ForegroundColor Green

# 1. Dependency Validation
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "Docker is not installed. Please install Docker Desktop for Windows first: https://docs.docker.com/desktop/install/windows-install/"
    exit 1
}

if (-not (docker compose version)) {
    Write-Error "Docker Compose is required. Please enable or install Docker Compose."
    exit 1
}

# 2. Setup Directory
$installDir = Join-Path $HOME ".markly"
$binDir = Join-Path $installDir "bin"
$null = New-Item -ItemType Directory -Force -Path $installDir
$null = New-Item -ItemType Directory -Force -Path $binDir

# 3. Create docker-compose.yml
$composePath = Join-Path $installDir "docker-compose.yml"
$composeContent = @"
version: '3.8'

services:
  postgres:
    image: postgres:16-alpine
    container_name: markly_postgres
    environment:
      POSTGRES_USER: markly
      POSTGRES_PASSWORD: markly
      POSTGRES_DB: markly_dev
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U markly -d markly_dev"]
      interval: 5s
      timeout: 5s
      retries: 5

  chroma:
    image: chromadb/chroma:latest
    container_name: markly_chroma
    ports:
      - "8000:8000"
    volumes:
      - chroma_data:/chroma/chroma
    restart: unless-stopped

  markly-cli:
    image: markly-cli:latest
    container_name: markly_cli
    stdin_open: true
    tty: true
    volumes:
      - .:/app
      - //var/run/docker.sock:/var/run/docker.sock
      - secrets_data:/root/.markly
      - skills_data:/app/markly/memory/skills
    environment:
      - DATABASE_URL=postgresql://markly:markly@postgres:5432/markly_dev
    depends_on:
      postgres:
        condition: service_healthy
      chroma:
        condition: service_started

volumes:
  postgres_data:
  chroma_data:
  secrets_data:
  skills_data:
"@

Set-Content -Path $composePath -Value $composeContent -Encoding utf8

# 4. Pull/Build container
Write-Host "🏗️ Pulling latest Markly Docker container..."
docker compose -f $composePath pull

# 5. Create bat wrapper
$batPath = Join-Path $binDir "markly.bat"
$batContent = @"
@echo off
docker compose -f "$composePath" run --rm -it markly-cli %*
"@

Set-Content -Path $batPath -Value $batContent -Encoding utf8

# 6. Add to User PATH
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -notlike "*$binDir*") {
    Write-Host "⚙️ Adding $binDir to User PATH..."
    $newPath = "$userPath;$binDir"
    [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
    # Update current session path
    $env:Path = "$env:Path;$binDir"
}

Write-Host "✅ Markly successfully installed!" -ForegroundColor Green
Write-Host ""
Write-Host "👉 Next steps (restart your terminal first):" -ForegroundColor Cyan
Write-Host "   1. Run 'markly setup' to configure your API keys."
Write-Host "   2. Start creating with 'markly run `"Your goal here`"'" -ForegroundColor Cyan
Write-Host ""
