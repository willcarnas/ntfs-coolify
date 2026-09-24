"""Configuracao central e carregamento de variaveis de ambiente.

Todas as credenciais (Telegram, corretora) vem de variaveis de ambiente ou do
arquivo `.env` na raiz do projeto, nunca do codigo-fonte (secao 8 - Seguranca).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

# Raiz do projeto = pasta que contem este pacote (`comum/`).
ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    """Carrega .env de forma minimalista, sem dependencia externa."""
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        # Nao sobrescreve variaveis ja definidas no ambiente real.
        os.environ.setdefault(key, value)


_load_dotenv()

# ── Caminhos ────────────────────────────────────────────────────────────────
DATA_DIR = Path(os.getenv("TRADING_DATA_DIR", ROOT / "data"))
BACKUP_DIR = Path(os.getenv("TRADING_BACKUP_DIR", DATA_DIR / "backups"))
LOG_DIR = Path(os.getenv("TRADING_LOG_DIR", ROOT / "logs"))
CONFIG_DIR = ROOT / "config"
DB_PATH = Path(os.getenv("TRADING_DB_PATH", DATA_DIR / "trading.db"))

for _d in (DATA_DIR, BACKUP_DIR, LOG_DIR, CONFIG_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ── Ambiente ────────────────────────────────────────────────────────────────
# `desenvolvimento` permite rodar sem MT5/Telegram, usando mocks e degradacao.
AMBIENTE = os.getenv("TRADING_ENV", "desenvolvimento")
MOCK = os.getenv("TRADING_MOCK", "1" if AMBIENTE != "producao" else "0") == "1"

# ── Telegram ────────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# ── Timeouts / limites ──────────────────────────────────────────────────────
HTTP_TIMEOUT = float(os.getenv("TRADING_HTTP_TIMEOUT", "15"))
HEARTBEAT_INTERVALO = int(os.getenv("TRADING_HEARTBEAT_INTERVALO", "30"))

# Faixas aceitaveis de saude do sistema (RF-14)
LIMITE_CPU_PCT = float(os.getenv("TRADING_LIMITE_CPU", "90"))
LIMITE_RAM_PCT = float(os.getenv("TRADING_LIMITE_RAM", "90"))
LIMITE_DISCO_PCT = float(os.getenv("TRADING_LIMITE_DISCO", "90"))


def load_json(path: str | Path, default: Any = None) -> Any:
    """Carrega um JSON de `config/` (ou caminho absoluto), tolerante a ausencia."""
    p = Path(path)
    if not p.is_absolute():
        p = CONFIG_DIR / p
    if not p.exists():
        return default if default is not None else {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default if default is not None else {}


def save_json(path: str | Path, data: Any) -> Path:
    p = Path(path)
    if not p.is_absolute():
        p = CONFIG_DIR / p
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return p
