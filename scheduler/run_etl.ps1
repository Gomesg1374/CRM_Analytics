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

# -----------------------------------------------------------------------
# Executa o ETL
# -----------------------------------------------------------------------
$Python = Join-Path $ProjectDir ".venv\Scripts\python.exe"
$Args   = @((Join-Path $ProjectDir "etl\run.py"))
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
