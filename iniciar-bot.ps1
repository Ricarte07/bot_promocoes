# Sobe o Bufos Promo nesta máquina: o Redis no Docker e, cada um na sua janela,
# o scraper (coleta os preços) e o notifier (manda as promoções para o Telegram).
#
# Uso, na raiz do projeto:
#   powershell -ExecutionPolicy Bypass -File .\iniciar-bot.ps1
#   powershell -ExecutionPolicy Bypass -File .\iniciar-bot.ps1 -ComPainel   # abre também o painel web
param([switch]$ComPainel)

$ErrorActionPreference = 'Stop'
$raiz = $PSScriptRoot

if (-not (Test-Path (Join-Path $raiz '.env'))) {
    throw 'Falta o arquivo .env na raiz do projeto (copie de .env.example e preencha).'
}
if (-not (Test-Path (Join-Path $raiz 'services\scraper\.venv\Scripts\python.exe'))) {
    throw 'Falta o ambiente Python do scraper (services\scraper\.venv). Veja o README.'
}

# Dois scrapers ao mesmo tempo coletariam tudo em dobro.
$rodando = Get-CimInstance Win32_Process -Filter "Name like 'python%' or Name like 'notifier%'" |
    Where-Object { $_.CommandLine -match 'interfaces\.agendador' -or $_.Name -like 'notifier*' }
if ($rodando) {
    Write-Host 'O bot já está rodando nesta máquina. Feche as janelas dele antes de subir de novo.' -ForegroundColor Yellow
    exit 1
}

docker info *> $null
if ($LASTEXITCODE -ne 0) { throw 'O Docker não está rodando. Abra o Docker Desktop, espere ele iniciar e rode de novo.' }

Write-Host 'Subindo o Redis...'
docker compose -f (Join-Path $raiz 'docker-compose.yml') up -d --wait redis
if ($LASTEXITCODE -ne 0) { throw 'O Redis não subiu. Veja: docker compose logs redis' }

Start-Process powershell -WorkingDirectory (Join-Path $raiz 'services\scraper') -ArgumentList @(
    '-NoExit', '-Command',
    '$Host.UI.RawUI.WindowTitle = ''Bufos Promo - scraper''; .\.venv\Scripts\python -m interfaces.agendador --persistencia postgres --eventos redis'
)
Start-Process powershell -WorkingDirectory (Join-Path $raiz 'services\notifier') -ArgumentList @(
    '-NoExit', '-Command',
    '$Host.UI.RawUI.WindowTitle = ''Bufos Promo - notifier''; go run ./cmd/notifier'
)
if ($ComPainel) {
    Start-Process powershell -WorkingDirectory (Join-Path $raiz 'services\web') -ArgumentList @(
        '-NoExit', '-Command',
        '$Host.UI.RawUI.WindowTitle = ''Bufos Promo - painel''; npm run dev'
    )
}

Write-Host ''
Write-Host 'Bufos Promo no ar:' -ForegroundColor Green
Write-Host '  - scraper e notifier abertos em janelas próprias (feche a janela para parar)'
if ($ComPainel) { Write-Host '  - painel em http://localhost:3000 (pode levar alguns segundos)' }
Write-Host '  - deixe o notebook sem suspender enquanto o bot roda'
