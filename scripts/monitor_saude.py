"""Monitoramento de saúde do mini PC (RF-14).

Serviço independente. Mede CPU, RAM, disco e conectividade; grava em `saude`,
emite evento e enfileira alerta no Telegram quando uma faixa aceitável é
ultrapassada (simulável via variáveis de ambiente para testes).
"""
from __future__ import annotations

import os
import socket
import sys
import time
from pathlib import Path
from typing import Optional

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from comum import config, db, repo  # noqa: E402
from comum.servico import Servico, modo_uma_vez  # noqa: E402

MODULO = "monitor_saude"


def _psutil():
    try:
        import psutil  # type: ignore

        return psutil
    except Exception:  # pragma: no cover
        return None


def medir_internet(host: str = "1.1.1.1", porta: int = 53, timeout: float = 3.0) -> tuple[bool, Optional[float]]:
    inicio = time.perf_counter()
    try:
        with socket.create_connection((host, porta), timeout=timeout):
            pass
        return True, round((time.perf_counter() - inicio) * 1000, 1)
    except OSError:
        return False, None


class ServicoSaude(Servico):
    def __init__(self) -> None:
        super().__init__(MODULO, intervalo=int(os.getenv("TRADING_SAUDE_INTERVALO", "60")))
        self._ultimo_alerta = 0.0

    def ciclo(self) -> None:
        cpu = ram = disco = 0.0
        ram_usada = 0.0
        psutil = _psutil()
        if psutil is not None:
            cpu = float(psutil.cpu_percent(interval=1.0))
            mem = psutil.virtual_memory()
            ram = float(mem.percent)
            ram_usada = round(mem.used / (1024 * 1024), 1)
            disco = float(psutil.disk_usage(str(config.ROOT)).percent)
        else:
            # Fallback: mede apenas disco via shutil (RAM/CPU ficam em 0).
            import shutil

            uso = shutil.disk_usage(str(config.ROOT))
            disco = round(uso.used / uso.total * 100, 1)

        internet_ok, latencia = medir_internet()

        # Simulação de teste manual (critério de aceite RF-14)
        if os.getenv("TRADING_TESTE_DISCO_CHEIO") == "1":
            disco = 99.9
        if os.getenv("TRADING_TESTE_SEM_REDE") == "1":
            internet_ok = False

        alertas = []
        if cpu > config.LIMITE_CPU_PCT:
            alertas.append(f"CPU {cpu:.0f}% > {config.LIMITE_CPU_PCT:.0f}%")
        if ram > config.LIMITE_RAM_PCT:
            alertas.append(f"RAM {ram:.0f}% > {config.LIMITE_RAM_PCT:.0f}%")
        if disco > config.LIMITE_DISCO_PCT:
            alertas.append(f"Disco {disco:.0f}% > {config.LIMITE_DISCO_PCT:.0f}%")
        if not internet_ok:
            alertas.append("Sem conectividade com a internet")

        texto_alerta = "; ".join(alertas) if alertas else None
        repo.registrar_saude(cpu, ram, ram_usada, disco, internet_ok, latencia, texto_alerta)

        if texto_alerta:
            self.log.warning("saúde fora da faixa: %s", texto_alerta)
            repo.registrar_evento("saude_alerta", MODULO, {"alerta": texto_alerta})
            # Evita spam: no máximo 1 alerta a cada 15 min.
            if time.monotonic() - self._ultimo_alerta > 900:
                self._ultimo_alerta = time.monotonic()
                repo.enfileirar_alerta(
                    None,
                    {"tipo": "saude", "mensagem": f"⚠ <b>Saúde do sistema</b>\n{texto_alerta}"},
                )
            self.heartbeat("degradado", texto_alerta)
        else:
            self.log.info("saúde ok: cpu=%.0f%% ram=%.0f%% disco=%.0f%% net=%s",
                          cpu, ram, disco, "ok" if internet_ok else "off")


if __name__ == "__main__":
    ServicoSaude().executar(executar_uma_vez=modo_uma_vez())
