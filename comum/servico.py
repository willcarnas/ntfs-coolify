"""Base para os serviços de longa duração (um por módulo).

Centraliza: logging, heartbeat no banco, tratamento de sinais de término,
isolamento de exceções (um ciclo com erro não mata o serviço) e backoff.
"""
from __future__ import annotations

import os
import signal
import threading
import time
import traceback
from typing import Callable, Optional

from . import repo
from .logger import get_logger


class Servico:
    def __init__(self, nome: str, intervalo: int = 60) -> None:
        self.nome = nome
        self.intervalo = intervalo
        self.log = get_logger(nome)
        self._parar = threading.Event()

    def parar(self, *_args) -> None:  # compatível com signal handlers
        if not self._parar.is_set():
            self.log.info("sinal de término recebido, encerrando...")
        self._parar.set()

    def deve_parar(self) -> bool:
        return self._parar.is_set()

    def _instalar_sinais(self) -> None:
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                signal.signal(sig, self.parar)
            except (ValueError, OSError):  # pragma: no cover - fora do main thread
                pass

    def heartbeat(self, status: str = "ok", mensagem: Optional[str] = None) -> None:
        try:
            repo.heartbeat(self.nome, status, mensagem, pid=os.getpid())
        except Exception:  # pragma: no cover - heartbeat não deve derrubar serviço
            self.log.warning("falha ao registrar heartbeat: %s", traceback.format_exc(limit=1))

    def inicializar(self) -> None:
        """Hook opcional para setup do módulo."""

    def ciclo(self) -> None:
        """Executa um ciclo de trabalho. Deve ser implementado pelo módulo."""
        raise NotImplementedError

    def finalizar(self) -> None:
        """Hook opcional de limpeza."""

    def executar(self, executar_uma_vez: bool = False) -> None:
        self._instalar_sinais()
        self.log.info("iniciando serviço (intervalo=%ss, pid=%s)", self.intervalo, os.getpid())
        try:
            self.inicializar()
        except Exception:
            self.log.error("falha na inicialização:\n%s", traceback.format_exc())
            self.heartbeat("erro", "falha na inicialização")
        self.heartbeat("ok", "iniciado")

        while not self.deve_parar():
            inicio = time.monotonic()
            try:
                self.ciclo()
                self.heartbeat("ok")
            except Exception as exc:  # noqa: BLE001 - isolamento de falha por ciclo
                self.log.error("erro no ciclo: %s\n%s", exc, traceback.format_exc())
                self.heartbeat("degradado", f"erro: {exc}")

            if executar_uma_vez:
                break
            decorrido = time.monotonic() - inicio
            espera = max(1.0, self.intervalo - decorrido)
            # Espera interrompível
            if self._parar.wait(timeout=espera):
                break

        try:
            self.finalizar()
        except Exception:
            self.log.error("erro ao finalizar:\n%s", traceback.format_exc())
        self.heartbeat("parado", "encerrado")
        self.log.info("serviço encerrado")


def modo_uma_vez() -> bool:
    """Ativa execução única (útil para testes manuais de conector - secao 13)."""
    return os.getenv("TRADING_ONESHOT", "0") == "1"
