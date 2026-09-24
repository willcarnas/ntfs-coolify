"""Backup diário do banco (RF-13).

Copia o SQLite de forma consistente (API de backup) para a pasta de backups,
com carimbo de data/hora, e remove backups mais antigos que `retencao_dias`.
Pode rodar via Agendador de Tarefas do Windows ou serviço.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from comum import config, repo  # noqa: E402
from comum.logger import get_logger  # noqa: E402

log = get_logger("backup")


def executar(retencao_dias: int = 7) -> Path:
    config.BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    carimbo = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    destino = config.BACKUP_DIR / f"trading_{carimbo}.db"

    origem = sqlite3.connect(str(config.DB_PATH))
    try:
        bkp = sqlite3.connect(str(destino))
        try:
            origem.backup(bkp)
        finally:
            bkp.close()
    finally:
        origem.close()

    tamanho_kb = round(destino.stat().st_size / 1024, 1)
    log.info("backup criado: %s (%.1f KB)", destino.name, tamanho_kb)
    try:
        repo.registrar_evento("backup", "scripts.backup_diario", {"arquivo": destino.name, "kb": tamanho_kb})
    except Exception:  # pragma: no cover - banco pode estar bloqueado
        pass

    limite = datetime.now(timezone.utc) - timedelta(days=retencao_dias)
    for antigo in config.BACKUP_DIR.glob("trading_*.db"):
        try:
            mtime = datetime.fromtimestamp(antigo.stat().st_mtime, tz=timezone.utc)
            if mtime < limite:
                antigo.unlink()
                log.info("backup antigo removido: %s", antigo.name)
        except OSError:
            continue
    return destino


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backup diário do banco de trading")
    parser.add_argument("--retencao-dias", type=int, default=7)
    args = parser.parse_args()
    caminho = executar(args.retencao_dias)
    print(f"Backup gerado em: {caminho}")
