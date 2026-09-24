# scripts/setup.ps1
# Prepara o ambiente Python do projeto.
#
#   -Mode Shared    (padrão) cria um único .venv na raiz e instala tudo.
#   -Mode PerModule cria um venv independente por módulo (exigência do PRD, secao 13).
#
# Uso:
#   pwsh -File scripts\setup.ps1
#   pwsh -File scripts\setup.ps1 -Mode PerModule
param(
    [ValidateSet("Shared", "PerModule")]
    [string]$Mode = "Shared"
)
$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $PSScriptRoot
Set-Location $raiz

if ($Mode -eq "Shared") {
    Write-Host "[setup] criando .venv compartilhado..."
    python -m venv .venv
    & ".\.venv\Scripts\python.exe" -m pip install --upgrade pip
    & ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt
    & ".\.venv\Scripts\python.exe" -m pip install pytest httpx
    Write-Host "[setup] concluído. Ative com: .\.venv\Scripts\Activate.ps1"
}
else {
    $modulos = @("b3", "forex", "cripto", "noticias", "sinais", "risco", "telegram", "dashboard")
    foreach ($m in $modulos) {
        $req = Join-Path $raiz "$m\requirements.txt"
        if (-not (Test-Path $req)) { continue }
        Write-Host "[setup] venv do módulo $m..."
        python -m venv (Join-Path $raiz "$m\venv")
        $py = Join-Path $raiz "$m\venv\Scripts\python.exe"
        & $py -m pip install --upgrade pip
        & $py -m pip install -r $req
    }
    Write-Host "[setup] venvs por módulo concluídos."
}
