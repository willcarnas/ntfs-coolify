"""Circuit breaker reutilizável por fonte de dados (secao 5.2 e 13).

Componente compartilhado e testável: após N falhas consecutivas, a fonte é
"aberta" por um período de cooldown, evitando tentativas contínuas que poderiam
travar o módulo. Implementação com estado em memória e persistência opcional no
banco (tabela `circuit_breaker`).
"""
from __future__ import annotations

import threading
from datetime import timedelta
from typing import Any, Callable, TypeVar

from . import db
from .logger import get_logger

T = TypeVar("T")

ESTADO_FECHADO = "fechado"
ESTADO_ABERTO = "aberto"
ESTADO_MEIO_ABERTO = "meio_aberto"


class CircuitoAberto(Exception):
    """Levantado quando uma chamada é bloqueada por circuit breaker aberto."""


class CircuitBreaker:
    def __init__(
        self,
        fonte: str,
        max_falhas: int = 3,
        cooldown_segundos: int = 300,
        persistir: bool = True,
    ) -> None:
        self.fonte = fonte
        self.max_falhas = max_falhas
        self.cooldown = timedelta(seconds=cooldown_segundos)
        self.persistir = persistir
        self._lock = threading.Lock()
        self._falhas = 0
        self._estado = ESTADO_FECHADO
        self._aberto_em = None
        self._logger = get_logger("circuit_breaker")

    # ── Estado ──────────────────────────────────────────────────────────────
    @property
    def estado(self) -> str:
        with self._lock:
            self._atualizar_estado()
            return self._estado

    @property
    def disponivel(self) -> bool:
        with self._lock:
            self._atualizar_estado()
            return self._estado != ESTADO_ABERTO

    def _atualizar_estado(self) -> None:
        if self._estado == ESTADO_ABERTO and self._aberto_em is not None:
            if db.agora_utc() - self._aberto_em >= self.cooldown:
                self._estado = ESTADO_MEIO_ABERTO
                self._logger.info("fonte=%s cooldown expirado -> meio_aberto", self.fonte)

    def registrar_sucesso(self) -> None:
        with self._lock:
            if self._estado != ESTADO_FECHADO:
                self._logger.info("fonte=%s recuperada -> fechado", self.fonte)
            self._falhas = 0
            self._estado = ESTADO_FECHADO
            self._aberto_em = None
            self._persistir()

    def registrar_falha(self, erro: Exception | str | None = None) -> None:
        with self._lock:
            self._falhas += 1
            if self._falhas >= self.max_falhas:
                if self._estado != ESTADO_ABERTO:
                    self._logger.warning(
                        "fonte=%s ABERTA apos %d falhas (ultimo erro: %s)",
                        self.fonte,
                        self._falhas,
                        erro,
                    )
                self._estado = ESTADO_ABERTO
                self._aberto_em = db.agora_utc()
            self._persistir()

    def permitir_tentativa(self) -> bool:
        """Reserva uma tentativa: se aberto, bloqueia; se meio_aberto, permite 1."""
        with self._lock:
            self._atualizar_estado()
            if self._estado == ESTADO_ABERTO:
                return False
            return True

    def _persistir(self) -> None:
        if not self.persistir:
            return
        try:
            db.execute(
                """
                INSERT INTO circuit_breaker (fonte, estado, falhas, aberto_em, atualizado_em)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(fonte) DO UPDATE SET
                    estado = excluded.estado,
                    falhas = excluded.falhas,
                    aberto_em = excluded.aberto_em,
                    atualizado_em = excluded.atualizado_em
                """,
                (
                    self.fonte,
                    self._estado,
                    self._falhas,
                    db.iso(self._aberto_em) if self._aberto_em else None,
                    db.iso(),
                ),
            )
        except Exception:  # pragma: no cover - persistencia e best-effort
            pass

    # ── Uso ─────────────────────────────────────────────────────────────────
    def chamar(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T | None:
        """Executa `func` protegida pelo breaker; retorna None se bloqueada/erro."""
        if not self.permitir_tentativa():
            self._logger.warning("fonte=%s bloqueada por circuit breaker", self.fonte)
            return None
        try:
            resultado = func(*args, **kwargs)
            self.registrar_sucesso()
            return resultado
        except Exception as exc:  # noqa: BLE001 - queremos capturar qualquer falha de fonte
            self.registrar_falha(exc)
            return None
