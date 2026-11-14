<#
    Ejecuta el pipeline completo en orden (D-04, D-15, D-20).
    Cada etapa se reintenta una vez tras esperar $RetryDelaySeconds; si el segundo intento falla,
    el proceso se detiene y la corrida queda marcada como fallida en audit.Execution.
    Uso:  .\deployment\run_all.ps1 [-SqlServer '.\SQLTANIA'] [-RetryDelaySeconds 60]
#>
param(
    [string]$SqlServer = '.\SQLTANIA',
    [int]$RetryDelaySeconds = 60
)

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$script:ExecutionId = $null

function Invoke-WithRetry {
    param([string]$Name, [scriptblock]$Action)
    foreach ($attempt in 1, 2) {
        Write-Host "[$(Get-Date -Format 'HH:mm:ss')] Etapa '$Name' (intento $attempt de 2)"
        & $Action
        if ($LASTEXITCODE -eq 0) { return }
        Write-Host "  La etapa '$Name' falló (código $LASTEXITCODE)."
        if ($attempt -eq 1) {
            Write-Host "  Se reintenta en $RetryDelaySeconds s."
            Start-Sleep -Seconds $RetryDelaySeconds
        }
    }
    Stop-Pipeline "La etapa '$Name' falló dos veces."
}

function Stop-Pipeline {
    param([string]$Message)
    Write-Host "ERROR: $Message Se detiene el proceso."
    if ($script:ExecutionId) {
        python -m etl.run_stage fail --execution-id $script:ExecutionId --error $Message
    }
    exit 1
}

function Invoke-Sql {
    param([string]$File)
    sqlcmd -S $SqlServer -E -C -I -b -i $File
}

# 1. Bases y esquemas (scripts idempotentes)
Invoke-WithRetry 'setup' {
    Invoke-Sql 'database\scripts\01_create_databases.sql'
    if ($LASTEXITCODE -ne 0) { return }
    Invoke-Sql 'database\staging\01_staging_schemas.sql'
    if ($LASTEXITCODE -ne 0) { return }
    Invoke-Sql 'database\staging\02_clean_ready.sql'
    if ($LASTEXITCODE -ne 0) { return }
    Invoke-Sql 'database\warehouse\01_dw_schemas.sql'
}

# 2. Alta de la corrida en la auditoría
Invoke-WithRetry 'start' {
    $out = python -m etl.run_stage start
    if ($LASTEXITCODE -eq 0) { $script:ExecutionId = [int]($out | Select-Object -Last 1) }
}
Write-Host "ExecutionID = $script:ExecutionId"

# 3. Etapas del ETL, en orden
foreach ($stage in 'extract', 'clean', 'ready', 'load') {
    Invoke-WithRetry $stage { python -m etl.run_stage $stage --execution-id $script:ExecutionId }
}

# 4. Confirma los watermarks y cierra la corrida (solo si todo salió bien, D-16)
Invoke-WithRetry 'commit' { python -m etl.run_stage commit --execution-id $script:ExecutionId }

# Pendiente: etapas de modelo predictivo y alertas (machine-learning/, notifications/)
Write-Host "Pipeline terminado correctamente. ExecutionID = $script:ExecutionId"
exit 0
