"""Acesso ao banco SQLite compartilhado.

Fornece conexao thread-safe (uma por thread), inicializacao de schema e
utilitarios de tempo em UTC. Todos os modulos usam este modulo; a comunicacao
entre dominios acontece apenas atraves das tabelas definidas em schema.sql.
"""
from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from . import config

_SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"
_local = threading.local()
_init_lock = threading.Lock()
_initialized = False


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(
        config.DB_PATH,
        timeout=30,
        isolation_level=None,  # autocommit; usamos BEGIN explicito quando preciso
        check_same_thread=False,
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 30000")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_conn() -> sqlite3.Connection:
    """Retorna uma conexao por thread (SQLite nao gosta de compartilhamento)."""
    conn = getattr(_local, "conn", None)
    if conn is None:
        ensure_schema()
        conn = _connect()
        _local.conn = conn
    return conn


def ensure_schema() -> None:
    global _initialized
    if _initialized:
        return
    with _init_lock:
        if _initialized:
            return
        sql = _SCHEMA_PATH.read_text(encoding="utf-8")
        conn = _connect()
        try:
            conn.executescript(sql)
        finally:
            conn.close()
        _initialized = True


@contextmanager
def transacao() -> Iterator[sqlite3.Connection]:
    """Executa um bloco dentro de uma transacao (rollback em excecao)."""
    conn = get_conn()
    conn.execute("BEGIN")
    try:
        yield conn
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise


def query(sql: str, params: tuple | list = ()) -> list[sqlite3.Row]:
    return get_conn().execute(sql, params).fetchall()


def query_one(sql: str, params: tuple | list = ()) -> sqlite3.Row | None:
    return get_conn().execute(sql, params).fetchone()


def execute(sql: str, params: tuple | list = ()) -> sqlite3.Cursor:
    return get_conn().execute(sql, params)


# ── Tempo ───────────────────────────────────────────────────────────────────
def agora_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime | None = None) -> str:
    """Serializa datetime para ISO-8601 UTC com sufixo 'Z'."""
    dt = dt or agora_utc()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_iso(valor: str | None) -> datetime | None:
    """Converte string ISO-8601 (com Z ou offset) para datetime UTC."""
    if not valor:
        return None
    try:
        texto = valor.strip()
        if texto.endswith("Z"):
            texto = texto[:-1] + "+00:00"
        dt = datetime.fromisoformat(texto)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


def idade_segundos(coletado_em: str | None) -> float | None:
    dt = parse_iso(coletado_em)
    if dt is None:
        return None
    return (agora_utc() - dt).total_seconds()


def reset_para_testes() -> None:
    """Fecha a conexao da thread atual (usado em testes)."""
    global _initialized
    conn = getattr(_local, "conn", None)
    if conn is not None:
        conn.close()
        _local.conn = None
    _initialized = False
