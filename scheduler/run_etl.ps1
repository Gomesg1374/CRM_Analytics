<#
.SYNOPSIS
    Wrapper que executa o pipeline CRM Analytics ETL.
    Chamado pelo Task Scheduler (ou diretamente para testes manuais).
    Registra toda a saída em logs\etl_YYYYMMDD_HHMMSS.log.
    O exit code do script reflete o do Python: 0 = OK, 1 = falha.

.EXAMPLE
    # Executar manualmente (a partir da raiz do projeto):
    .\scheduler\run_etl.ps1

    # Pular carga no PostgreSQL:
    .\scheduler\run_etl.ps1 -NoDb
#>
param(
    [switch]$NoDb
)

$ProjectDir = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectDir

# -----------------------------------------------------------------------
# Diretório de logs
# -----------------------------------------------------------------------
$LogDir = Join-Path $ProjectDir "logs"
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir | Out-Null }

$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$LogFile   = Join-Path $LogDir "etl_$Timestamp.log"

# -----------------------------------------------------------------------
# Carrega .env se existir (variáveis de PG, SMTP, etc.)
# -----------------------------------------------------------------------
$EnvFile = Join-Path $ProjectDir ".env"
if (Test-Path $EnvFile) {
    Get-Content $EnvFile | ForEach-Object {
        if ($_ -match '^\s*([^#\s][^=]+)=(.*)$') {
            $key = $Matches[1].Trim()
            $val = $Matches[2].Trim().Trim('"').Trim("'")
            [System.Environment]::SetEnvironmentVariable($key, $val, "Process")
        }
    }
    Write-Host "  .env carregado"
}

# Garante encoding UTF-8 no stdout do Python (Windows cp1252 não suporta emojis)
$env:PYTHONIOENCODING = "utf-8"

# -----------------------------------------------------------------------
# Garante que Docker e os containers necessários estão em execução
# -----------------------------------------------------------------------
function Wait-DockerDaemon {
    param([int]$TimeoutSec = 90)
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        docker info 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) { return $true }
        Start-Sleep -Seconds 4
    }
    return $false
}

function Start-Container {
    param([string]$Name)
    $state = (docker inspect --format "{{.State.Status}}" $Name 2>&1).Trim()
    if ($LASTEXITCODE -ne 0) {
        "  [Docker] Container '$Name' nao encontrado — verifique 'docker ps -a'" |
            Tee-Object -FilePath $LogFile -Append
        return $false
    }
    if ($state -eq "running") {
        "  [Docker] $Name ja esta em execucao" | Tee-Object -FilePath $LogFile -Append
        return $true
    }
    "  [Docker] Iniciando $Name (estava: $state)..." | Tee-Object -FilePath $LogFile -Append
    docker start $Name 2>&1 | Out-Null
    Start-Sleep -Seconds 4
    $state = (docker inspect --format "{{.State.Status}}" $Name 2>&1).Trim()
    if ($state -eq "running") {
        "  [Docker] $Name iniciado com sucesso" | Tee-Object -FilePath $LogFile -Append
        return $true
    }
    "  [Docker] AVISO: $Name nao iniciou (estado: $state)" | Tee-Object -FilePath $LogFile -Append
    return $false
}

# Verifica se o daemon do Docker está respondendo; se não, inicia o Docker Desktop
docker info 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    "  [Docker] Daemon nao responde — tentando iniciar Docker Desktop..." |
        Tee-Object -FilePath $LogFile -Append
    $dockerExe = "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe"
    if (Test-Path $dockerExe) {
        Start-Process $dockerExe
        "  [Docker] Aguardando daemon ficar pronto (ate 90s)..." |
            Tee-Object -FilePath $LogFile -Append
        if (Wait-DockerDaemon -TimeoutSec 90) {
            "  [Docker] Daemon pronto" | Tee-Object -FilePath $LogFile -Append
        } else {
            "  [Docker] AVISO: daemon nao ficou pronto — carga no PostgreSQL pode falhar" |
                Tee-Object -FilePath $LogFile -Append
        }
    } else {
        "  [Docker] AVISO: Docker Desktop nao encontrado em $dockerExe" |
            Tee-Object -FilePath $LogFile -Append
    }
}

# Inicia os containers se estiverem parados
Start-Container "crm-postgres" | Out-Null
Start-Container "crm-metabase" | Out-Null

# Aguarda o PostgreSQL aceitar conexoes antes de rodar o ETL
"  [Docker] Aguardando PostgreSQL aceitar conexoes (ate 30s)..." |
    Tee-Object -FilePath $LogFile -Append
$pgReady = $false
$deadline = (Get-Date).AddSeconds(30)
while ((Get-Date) -lt $deadline) {
    docker exec crm-postgres pg_isready -U crm -d crm_analytics 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) { $pgReady = $true; break }
    Start-Sleep -Seconds 3
}
if ($pgReady) {
    "  [Docker] PostgreSQL pronto" | Tee-Object -FilePath $LogFile -Append
} else {
    "  [Docker] AVISO: PostgreSQL nao respondeu a tempo — carga pode falhar" |
        Tee-Object -FilePath $LogFile -Append
}

# -----------------------------------------------------------------------
# Executa o ETL
# -----------------------------------------------------------------------
$Python = Join-Path $ProjectDir ".venv\Scripts\python.exe"
$Args   = @("-m", "etl.run")
if ($NoDb) { $Args += "--no-db" }

"=== CRM Analytics ETL — $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ===" |
    Tee-Object -FilePath $LogFile

& $Python @Args *>&1 | Tee-Object -FilePath $LogFile -Append

$ExitCode = $LASTEXITCODE

"`n=== Finalizado com exit code $ExitCode — $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ===" |
    Tee-Object -FilePath $LogFile -Append

# -----------------------------------------------------------------------
# Remove logs com mais de 30 dias
# -----------------------------------------------------------------------
Get-ChildItem $LogDir -Filter "etl_*.log" -ErrorAction SilentlyContinue |
    Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-30) } |
    Remove-Item -Force

exit $ExitCode
