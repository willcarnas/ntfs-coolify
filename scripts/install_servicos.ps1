# scripts/install_servicos.ps1
# Registra cada módulo como serviço Windows independente via NSSM (PRD secao 9.4),
# com Start=SERVICE_AUTO_START e reinício automático em falha (isolamento, secao 5.2).
#
# Pré-requisitos:
#   - NSSM disponível no PATH (https://nssm.cc)
#   - Executar em PowerShell ELEVADO (Administrador)
#   - Ter rodado antes:  pwsh -File scripts\setup.ps1   (ou -Mode PerModule)
#
# Uso:
#   pwsh -File scripts\install_servicos.ps1
#   pwsh -File scripts\install_servicos.ps1 -Remover
param(
    [switch]$Remover,
    [switch]$Iniciar
)
$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $PSScriptRoot

if (-not (Get-Command nssm -ErrorAction SilentlyContinue)) {
    Write-Host "NSSM não encontrado no PATH. Baixe de https://nssm.cc e adicione ao PATH." -ForegroundColor Red
    exit 1
}

# Ordem de subida: dados -> sinais -> risco -> alertas -> dashboard (PRD secao 8).
# (servico; nome do servico; script)
$servicos = @(
    @("ModuloB3",        "b3",            "b3\main.py"),
    @("ModuloForex",     "forex",         "forex\main.py"),
    @("ModuloCripto",    "cripto",        "cripto\main.py"),
    @("ModuloNoticias",  "noticias",      "noticias\main.py"),
    @("MonitorSaude",    "scripts",       "scripts\monitor_saude.py"),
    @("MotorSinais",     "sinais",        "sinais\main.py"),
    @("MotorRisco",      "risco",         "risco\main.py"),
    @("ServicoTelegram", "telegram",      "telegram\main.py"),
    @("DashboardWeb",    "dashboard",     "dashboard\main.py")
)

function Get-Python([string]$modulo) {
    $porModulo = Join-Path $raiz "$modulo\venv\Scripts\python.exe"
    if ($modulo -ne "scripts" -and (Test-Path $porModulo)) { return $porModulo }
    $compartilhado = Join-Path $raiz ".venv\Scripts\python.exe"
    if (Test-Path $compartilhado) { return $compartilhado }
    return "python"
}

foreach ($s in $servicos) {
    $nome = $s[0]; $modulo = $s[1]; $script = $s[2]
    if ($Remover) {
        Write-Host "[nssm] removendo $nome..."
        nssm stop $nome 2>$null | Out-Null
        nssm remove $nome confirm 2>$null | Out-Null
        continue
    }
    $py = Get-Python $modulo
    $caminhoScript = Join-Path $raiz $script
    Write-Host "[nssm] instalando $nome -> $py $caminhoScript"
    nssm install $nome $py $caminhoScript
    nssm set $nome AppDirectory $raiz
    nssm set $nome Start SERVICE_AUTO_START
    nssm set $nome AppExit Default Restart
    nssm set $nome AppRestartDelay 5000
    nssm set $nome AppStdout (Join-Path $raiz "logs\$nome.out.log")
    nssm set $nome AppStderr (Join-Path $raiz "logs\$nome.err.log")
    nssm set $nome AppRotateFiles 1
    if ($Iniciar) { nssm start $nome }
}

if ($Remover) { Write-Host "[nssm] serviços removidos." }
else { Write-Host "[nssm] serviços instalados. Use -Iniciar para subir agora." }
