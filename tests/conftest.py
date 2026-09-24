"""Configuração de testes: banco isolado em diretório temporário.

Executado antes da importação dos testes, garante que `comum.config` aponte para
um banco de teste e não para o banco de produção.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="tswcn_test_"))
os.environ["TRADING_DB_PATH"] = str(_TMP / "trading_test.db")
os.environ["TRADING_DATA_DIR"] = str(_TMP)
os.environ["TRADING_BACKUP_DIR"] = str(_TMP / "backups")
os.environ["TRADING_LOG_DIR"] = str(_TMP / "logs")
os.environ["TRADING_ENV"] = "teste"

import pytest  # noqa: E402

from comum import db  # noqa: E402

# Ordem que respeita as chaves estrangeiras (filhos antes dos pais).
TABELAS = [
    "fila_alertas", "operacoes", "sinais", "cotacoes", "velas", "indicadores",
    "noticias", "pre_abertura", "servico_status", "saude", "eventos",
    "circuit_breaker",
]


@pytest.fixture()
def db_limpo():
    db.ensure_schema()
    conn = db.get_conn()
    for tabela in TABELAS:
        conn.execute(f"DELETE FROM {tabela}")
    yield db
