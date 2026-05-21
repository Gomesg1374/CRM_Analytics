<#
.SYNOPSIS
    Registra uma tarefa no Windows Task Scheduler para executar o ETL diariamente.
    Deve ser executado como Administrador (ou o usuário que vai rodar a tarefa).

.PARAMETER TaskName
    Nome da tarefa no Task Scheduler. Default: CRM_Analytics_ETL

.PARAMETER RunTime
    Horário de execução diária (formato 24h). Default: 07:00

.PARAMETER ProjectDir
    Caminho completo do projeto. Default: detectado automaticamente.

.PARAMETER NoDb
    Se presente, passa --no-db para o ETL (pula carga no PostgreSQL).

.EXAMPLE
    # Instalar com padrões (07:00, usuário atual):
    .\scheduler\setup_task.ps1

    # Instalar para rodar às 06:30:
    .\scheduler\setup_task.ps1 -RunTime "06:30"

    # Remover a tarefa:
    Unregister-ScheduledTask -TaskName "CRM_Analytics_ETL" -Confirm:$false
#>
param(
    [string]$TaskName   = "CRM_Analytics_ETL",
    [string]$RunTime    = "16:00",
    [string]$ProjectDir = "",
    [switch]$NoDb
)

# Detecta raiz do projeto a partir da localização deste script
if (-not $ProjectDir) {
    $ProjectDir = Split-Path -Parent $PSScriptRoot
}

$WrapperScript = Join-Path $ProjectDir "scheduler\run_etl.ps1"

if (-not (Test-Path $WrapperScript)) {
    Write-Error "Script não encontrado: $WrapperScript"
    exit 1
}

$ScriptArgs = "-NonInteractive -ExecutionPolicy Bypass -File `"$WrapperScript`""
if ($NoDb) { $ScriptArgs += " -NoDb" }

# -----------------------------------------------------------------------
# Ação: executar run_etl.ps1 via PowerShell
# -----------------------------------------------------------------------
$Action = New-ScheduledTaskAction `
    -Execute        "powershell.exe" `
    -Argument       $ScriptArgs `
    -WorkingDirectory $ProjectDir

# -----------------------------------------------------------------------
# Trigger: todos os dias no horário especificado
# -----------------------------------------------------------------------
$Trigger = New-ScheduledTaskTrigger -Daily -At $RunTime

# -----------------------------------------------------------------------
# Configurações: timeout 2h, 1 retry em 30 min, inicia mesmo atrasado
# -----------------------------------------------------------------------
$Settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit  (New-TimeSpan -Hours 2) `
    -RestartCount        1 `
    -RestartInterval     (New-TimeSpan -Minutes 30) `
    -StartWhenAvailable `
    -MultipleInstances   IgnoreNew

# -----------------------------------------------------------------------
# Principal: usuário atual, nível mais alto de privilégios
# -----------------------------------------------------------------------
$CurrentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$Principal = New-ScheduledTaskPrincipal `
    -UserId   $CurrentUser `
    -LogonType Interactive `
    -RunLevel Highest

# -----------------------------------------------------------------------
# Registra (ou atualiza) a tarefa
# -----------------------------------------------------------------------
Register-ScheduledTask `
    -TaskName  $TaskName `
    -Action    $Action `
    -Trigger   $Trigger `
    -Settings  $Settings `
    -Principal $Principal `
    -Force | Out-Null

$NextRun = (Get-ScheduledTask -TaskName $TaskName | Get-ScheduledTaskInfo).NextRunTime

Write-Host ""
Write-Host "✅  Tarefa registrada: $TaskName"
Write-Host "    Horário:           diariamente às $RunTime"
Write-Host "    Próxima execução:  $NextRun"
Write-Host "    Usuário:           $CurrentUser"
Write-Host "    Script:            $WrapperScript"
Write-Host "    Logs:              $ProjectDir\logs\"
Write-Host ""
Write-Host "Comandos úteis:"
Write-Host "    Executar agora:  Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "    Ver status:      Get-ScheduledTask    -TaskName '$TaskName' | Get-ScheduledTaskInfo"
Write-Host "    Remover tarefa:  Unregister-ScheduledTask -TaskName '$TaskName' -Confirm:`$false"
