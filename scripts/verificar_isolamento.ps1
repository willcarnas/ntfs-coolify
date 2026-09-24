# Teste de isolamento reproduzível (PRD secao 5.3 / 13).
#
# Sobe todos os módulos (exceto telegram) com limiares de staleness curtos,
# encerra APENAS o processo do módulo cripto e verifica que a dashboard
# continua respondendo e passa a marcar o cripto como desatualizado.
#
# Uso:  pwsh -File scripts\verificar_isolamento.ps1
$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $PSScriptRoot
$py = Join-Path $raiz ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }

$saida = Join-Path $raiz "data\iso_test.txt"
"" | Set-Content -LiteralPath $saida

# Limiares curtos para o teste: 5s para heartbeat de serviço e cotação.
$env:TRADING_STALE_CRIPTO = "5"
$env:TRADING_STALE_COTACAO = "5"

function Log($msg) { $msg | Tee-Object -FilePath $saida -Append }

$runner = Start-Process -FilePath $py -ArgumentList "scripts\run_all.py","--skip","telegram" `
    -WorkingDirectory $raiz -PassThru -WindowStyle Hidden
Log "run_all iniciado (pid $($runner.Id))"

try {
    Start-Sleep -Seconds 30
    $r1 = Invoke-RestMethod "http://127.0.0.1:8080/api/resumo" -TimeoutSec 15
    Log ("ANTES: HTTP 200 | cotacoes=" + $r1.cotacoes.Count + " | servicos=" + (($r1.servicos.servico) -join ","))

    $cripto = Get-CimInstance Win32_Process |
        Where-Object { $_.Name -like "python*" -and $_.CommandLine -like "*cripto\main.py*" -or $_.CommandLine -like "*cripto/main.py*" }
    if ($cripto) {
        $cripto | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
        Log ("cripto encerrado (pids " + (($cripto.ProcessId) -join ",") + ")")
    } else {
        Log "AVISO: processo do cripto nao localizado"
    }

    Start-Sleep -Seconds 10
    $r2 = Invoke-RestMethod "http://127.0.0.1:8080/api/resumo" -TimeoutSec 15
    $svc = $r2.servicos | Where-Object { $_.servico -eq "cripto" }
    $cot = $r2.cotacoes | Where-Object { $_.classe -eq "cripto" }
    $staleCot = if ($cot) { ($cot | Where-Object { $_.desatualizado }).Count } else { 0 }
    Log ("DEPOIS: HTTP 200 | dashboard VIVA | cripto heartbeat idade=" + [math]::Round($svc.idade_segundos) + "s desatualizado=" + $svc.desatualizado)
    Log ("DEPOIS: cotacoes cripto marcadas desatualizadas=" + $staleCot + "/" + @($cot).Count)
    Log "RESULTADO: isolamento OK (demais modulos e dashboard seguiram operando)"
}
catch {
    Log ("FALHA: " + $_)
}
finally {
    if ($runner -and -not $runner.HasExited) { taskkill /PID $runner.Id /T /F | Out-Null }
    Get-CimInstance Win32_Process |
        Where-Object { $_.Name -like "python*" -and $_.CommandLine -like "*TradingSystemWCN*" } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    Log "servicos encerrados"
}
